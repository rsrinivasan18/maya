/**
 * MAYA Web UI — Session 12
 * WebSocket chat client with model/agent selection, history sidebar,
 * character picker, 12-state CSS avatar animations, and voice I/O.
 *
 * Voice input:  Web Speech API (SpeechRecognition) — mic button
 * Voice output: SpeechSynthesis API — speaker toggle in header
 */

'use strict';

// ── PIN lock ──────────────────────────────────────────────────────────────────
(function pinLock() {
  const CORRECT = '2026';
  const LS_KEY  = 'maya_pin_ok';
  const overlay = document.getElementById('pin-overlay');

  // Already unlocked this session → remove overlay immediately, no animation
  if (localStorage.getItem(LS_KEY) === '1') {
    overlay.remove();
    return;
  }

  let digits = '';

  const dots    = [0,1,2,3].map(i => document.getElementById('pin-d' + i));
  const dotsWrap = document.getElementById('pin-dots');
  const errEl   = document.getElementById('pin-error');

  function renderDots() {
    dots.forEach((d, i) => {
      d.classList.toggle('filled', i < digits.length);
      d.classList.remove('error');
    });
    errEl.hidden = true;
  }

  function showError() {
    dots.forEach(d => { d.classList.remove('filled'); d.classList.add('error'); });
    errEl.hidden = false;
    dotsWrap.classList.add('shake');
    dotsWrap.addEventListener('animationend', () => {
      dotsWrap.classList.remove('shake');
    }, { once: true });
    // Clear after 650ms so user can try again
    setTimeout(() => {
      digits = '';
      renderDots();
    }, 650);
  }

  function unlock() {
    localStorage.setItem(LS_KEY, '1');
    overlay.classList.add('pin-fade-out');
    overlay.addEventListener('transitionend', () => overlay.remove(), { once: true });
  }

  function pressDigit(d) {
    if (digits.length >= 4) return;
    digits += d;
    renderDots();
    if (digits.length === 4) {
      if (digits === CORRECT) {
        unlock();
      } else {
        showError();
      }
    }
  }

  function pressDelete() {
    if (digits.length > 0) {
      digits = digits.slice(0, -1);
      renderDots();
    }
  }

  // Numpad button clicks
  document.querySelectorAll('.pin-key[data-n]').forEach(btn => {
    btn.addEventListener('click', () => pressDigit(btn.dataset.n));
  });
  document.getElementById('pin-del').addEventListener('click', pressDelete);

  // Physical keyboard
  document.addEventListener('keydown', (e) => {
    if (!document.getElementById('pin-overlay')) return; // overlay already gone
    if (e.key >= '0' && e.key <= '9') { pressDigit(e.key); }
    else if (e.key === 'Backspace')    { pressDelete(); }
  });
})();

// ── DOM References ────────────────────────────────────────────────────────────
const el = {
  statusDot:      document.getElementById('status-dot'),
  statusText:     document.getElementById('status-text'),
  messages:       document.getElementById('messages'),
  input:          document.getElementById('input'),
  sendBtn:        document.getElementById('send-btn'),
  micBtn:         document.getElementById('mic-btn'),
  voiceToggle:    document.getElementById('voice-toggle'),
  thinking:       document.getElementById('thinking'),
  thinkingEmoji:  document.getElementById('thinking-emoji'),
  modelSelect:    document.getElementById('model-select'),
  agentSelect:    document.getElementById('agent-select'),
  mayaEyes:       document.getElementById('maya-eyes'),
  emotionLabel:   document.getElementById('emotion-label'),
  caption:        document.getElementById('maya-caption'),
  recentTopics:   document.getElementById('recent-topics'),
  masteryList:    document.getElementById('mastery-list'),
  sidebar:        document.getElementById('sidebar'),
  sidebarToggle:  document.getElementById('sidebar-toggle'),
  sidebarOverlay: document.getElementById('sidebar-overlay'),
};

// ── State ─────────────────────────────────────────────────────────────────────
let currentChar   = localStorage.getItem('maya_char') || '🦋';
let isConnected   = false;
let isBusy        = false;       // true while a /chat request is in flight
let sessionId     = '';          // assigned by /api/session
let messageHistory = [];         // accumulated across turns, sent with each request
let lastDoneState = 'idle';   // Avatar state to restore after talking ends
let captionTimer  = null;     // Auto-hide caption timer

// ── Character picker ──────────────────────────────────────────────────────────
function setCharacter(char) {
  currentChar = char;
  localStorage.setItem('maya_char', char);
  el.thinkingEmoji.textContent = char;
  document.querySelectorAll('.char-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.char === char);
  });
}

// Apply saved character on load
setCharacter(currentChar);

document.querySelectorAll('.char-btn').forEach(btn => {
  btn.addEventListener('click', () => setCharacter(btn.dataset.char));
});

// ── Avatar state machine ──────────────────────────────────────────────────────
/**
 * Sets the avatar's data-state attribute.
 * CSS [data-state] selectors automatically switch the @keyframes animation.
 */
function setAvatarState(state) {
  if (el.mayaEyes) el.mayaEyes.setAttribute('data-state', state);
  if (el.emotionLabel) el.emotionLabel.textContent = state;
  if (window.mayaEyesSetState) window.mayaEyesSetState(state);
  if (typeof triggerCelebration === 'function' && state === 'celebrating') triggerCelebration();
}

/** Map graph intents to avatar states shown DURING LLM processing. */
const INTENT_THINKING_STATE = {
  greeting: 'excited',
  farewell: 'sad',
  math:     'focused',
  question: 'thinking',
  general:  'thinking',
};

/** Map graph intents to avatar states shown AFTER response delivered. */
const INTENT_DONE_STATE = {
  greeting: 'happy',
  farewell: 'waving',
  math:     'celebrating',
  question: 'happy',
  general:  'idle',
};

// ── Voice output (SpeechSynthesis) ────────────────────────────────────────────
let voiceEnabled = localStorage.getItem('maya_voice') === 'true';

// ── Voice picker — Indian female, soft ────────────────────────────────────────
let preferredVoice = null;

function pickVoice() {
  const voices = speechSynthesis.getVoices();
  if (!voices.length) return;

  // Priority list: best Indian female first, graceful fallback
  const tests = [
    v => /heera/i.test(v.name),                                 // Microsoft Heera (en-IN female, Windows)
    v => /female/i.test(v.name) && v.lang === 'en-IN',          // any labelled female en-IN
    v => v.lang === 'en-IN',                                     // any en-IN
    v => /female/i.test(v.name) && v.lang === 'hi-IN',          // Hindi female
    v => v.lang === 'hi-IN',                                     // any Hindi
    v => /female/i.test(v.name) && v.lang.startsWith('en'),     // any English female
  ];

  for (const test of tests) {
    const match = voices.find(test);
    if (match) { preferredVoice = match; return; }
  }
}

// Voices load asynchronously on first call
if (window.speechSynthesis) {
  speechSynthesis.onvoiceschanged = pickVoice;
  pickVoice(); // also try immediately (Chrome sometimes has them ready)
}

function updateVoiceBtn() {
  el.voiceToggle.textContent = voiceEnabled ? '🔊' : '🔇';
  el.voiceToggle.title = voiceEnabled
    ? 'Voice on — click to mute'
    : 'Voice off — click to enable';
}

// Show text as caption in the hero panel, auto-hide after `ms` milliseconds
function showCaption(text, ms = 7000) {
  if (!el.caption) return;
  clearTimeout(captionTimer);
  el.caption.textContent = text;
  el.caption.classList.add('visible');
  captionTimer = setTimeout(() => el.caption.classList.remove('visible'), ms);
}

function hideCaption() {
  clearTimeout(captionTimer);
  el.caption?.classList.remove('visible');
}

function stripEmoji(text) {
  // Remove emoji and pictographic characters before TTS — they'd be read aloud
  return String(text)
    .replace(/[\p{Emoji_Presentation}\p{Extended_Pictographic}]/gu, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
}

function speakText(text, lang) {
  if (!voiceEnabled || !window.speechSynthesis) return;

  speechSynthesis.cancel();
  text = stripEmoji(stripMarkdownForTTS(text));

  const utt = new SpeechSynthesisUtterance(text);
  utt.rate  = 0.92;
  utt.pitch = 1.15;

  if (preferredVoice) {
    utt.voice = preferredVoice;
    utt.lang  = preferredVoice.lang;
  } else {
    utt.lang = (lang && lang !== 'english') ? 'hi-IN' : 'en-IN';
  }

  // Safety: if speechSynthesis.onend never fires (common on Windows/Chrome),
  // restore avatar after a reasonable maximum wait so it never gets stuck.
  let talkEndFired = false;
  const safetyMs = Math.min(Math.max(text.length * 80, 10000), 60000);
  let safetyTimer = null;

  const _onTalkEnd = () => {
    if (talkEndFired) return;
    talkEndFired = true;
    clearTimeout(safetyTimer);
    isTalking = false;
    setAvatarState(lastDoneState);
    hideCaption();
    el.micBtn.classList.remove('maya-talking');
    el.micBtn.title = 'Hold to speak';
  };

  safetyTimer = setTimeout(_onTalkEnd, safetyMs);

  utt.onstart = () => {
    isTalking = true;
    setAvatarState('talking');
    el.micBtn.classList.add('maya-talking');
    el.micBtn.title = 'Hold to interrupt';
  };
  utt.onend   = _onTalkEnd;
  utt.onerror = _onTalkEnd;

  speechSynthesis.speak(utt);
}

el.voiceToggle.addEventListener('click', () => {
  voiceEnabled = !voiceEnabled;
  localStorage.setItem('maya_voice', voiceEnabled);
  updateVoiceBtn();
  // Stop any ongoing speech when muting
  if (!voiceEnabled && window.speechSynthesis) {
    speechSynthesis.cancel();
    setAvatarState(lastDoneState);
  }
});

// Init voice button label
updateVoiceBtn();

// ── Voice input (SpeechRecognition) ──────────────────────────────────────────
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition  = null;
let isListening  = false;
let isTalking    = false;   // true while SpeechSynthesis is speaking

// Always show the mic button — handle unavailability gracefully on click
el.micBtn.hidden = false;

if (SpeechRecognition) {
  recognition = new SpeechRecognition();
  recognition.continuous      = false;
  recognition.interimResults  = true;
  recognition.lang            = 'en-US';

  recognition.onresult = (event) => {
    const transcript = Array.from(event.results)
      .map(r => r[0].transcript)
      .join('');
    el.input.value = transcript;
    el.input.dispatchEvent(new Event('input'));
  };

  recognition.onend = () => {
    isListening = false;
    el.micBtn.classList.remove('ptt-active');
    el.micBtn.title = 'Hold to speak';
    if (el.input.value.trim() && isConnected && !isBusy) sendMessage();
  };

  recognition.onerror = (event) => {
    isListening = false;
    el.micBtn.classList.remove('ptt-active');
    el.micBtn.title = 'Hold to speak';
    if (event.error !== 'no-speech') {
      console.warn('MAYA voice input error:', event.error);
    }
  };
}

// ── Push-to-talk: hold to record, release to send ────────────────────────────
function startListening() {
  if (!recognition) {
    el.input.placeholder = 'Mic needs HTTPS or localhost — type your message';
    setTimeout(() => { el.input.placeholder = 'Ask me anything…'; }, 3500);
    return;
  }
  // Interrupt MAYA if she's speaking
  if (isTalking || window.speechSynthesis?.speaking) {
    speechSynthesis.cancel();
    isTalking = false;
    setAvatarState(lastDoneState);
    hideCaption();
    el.micBtn.classList.remove('maya-talking');
  }
  if (isListening) return;
  try {
    recognition.start();
    isListening = true;
    el.micBtn.classList.add('ptt-active');
    el.micBtn.title = 'Release to send';
  } catch (_) { /* already running */ }
}

function stopListening() {
  if (!isListening) return;
  recognition.stop(); // triggers onend → cleans up class → sendMessage
}

// Mouse: press and hold on desktop
el.micBtn.addEventListener('mousedown', (e) => {
  e.preventDefault();
  startListening();
  document.addEventListener('mouseup', stopListening, { once: true });
});

// Touch: hold on mobile/tablet
el.micBtn.addEventListener('touchstart', (e) => {
  e.preventDefault();
  startListening();
}, { passive: false });

el.micBtn.addEventListener('touchend', (e) => {
  e.preventDefault();
  stopListening();
}, { passive: false });

el.micBtn.addEventListener('touchcancel', stopListening);

// ── WebSocket ─────────────────────────────────────────────────────────────────
// ── HTTP streaming transport ──────────────────────────────────────────────────

async function initSession() {
  setStatus('connecting…', 'warn');
  try {
    const res  = await fetch('/api/session');
    const data = await res.json();
    sessionId = data.session_id;
    onMessage(data);   // fires 'connected' handler — sets isConnected, updates status
  } catch (e) {
    setStatus('offline — retrying…', 'offline');
    setTimeout(initSession, 3000);
  }
}

// ── Incoming message handler ──────────────────────────────────────────────────
function onMessage(data) {
  switch (data.type) {

    case 'connected':
      isConnected = true;
      el.sendBtn.disabled = !el.input.value.trim();
      setStatus(`session ${data.session_count} — ready`, 'online');
      setAvatarState('idle');
      addSystemMessage(`Session ${data.session_count}  ·  Hi, ${data.user_name}! 🦋`);
      refreshSidebar();
      refreshTodos();
      break;

    case 'thinking':
      showThinking();
      setAvatarState('thinking');
      break;

    case 'response': {
      hideThinking();
      // Double-strip on client side — catches any think tags the server missed
      const cleanText = stripThink(data.text);
      if (!cleanText) break;   // Never render an empty bubble
      addMessage('maya', cleanText, {
        intent:   data.intent,
        language: data.language,
        steps:    data.steps || [],
        isOnline: data.is_online,
      });
      setStatus(
        data.is_online ? 'online' : 'offline (Ollama)',
        data.is_online ? 'online' : 'offline'
      );
      lastDoneState = INTENT_DONE_STATE[data.intent] || 'idle';
      setAvatarState(lastDoneState);
      el.sendBtn.disabled = !el.input.value.trim();
      // Show caption in hero panel (visible with or without voice)
      showCaption(cleanText, voiceEnabled ? 12000 : 6000);
      // Speak the response — avatar switches to 'talking' during playback
      speakText(cleanText, data.language);
      setTimeout(refreshSidebar, 1200);
      if (data.intent === 'reminder') setTimeout(refreshTodos, 1200);
      break;
    }

    case 'error':
      hideThinking();
      addMessage('maya', `⚠️  ${data.text}`, { intent: 'error' });
      setAvatarState('idle');
      el.sendBtn.disabled = !el.input.value.trim();
      break;
  }
}

// ── Send message ──────────────────────────────────────────────────────────────
async function sendMessage() {
  const text = el.input.value.trim();
  if (!text || isBusy || !isConnected) return;

  // Stop any active voice input before sending
  if (isListening && recognition) recognition.stop();

  addMessage('user', text);
  el.sendBtn.disabled = true;
  isBusy = true;

  el.input.value = '';
  el.input.style.height = 'auto';

  try {
    const res = await fetch('/chat', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        text,
        model:           el.modelSelect.value,
        agent:           el.agentSelect.value,
        session_id:      sessionId,
        message_history: messageHistory,
      }),
    });

    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let   buf     = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop();   // keep any incomplete trailing line
      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const data = JSON.parse(line);
          // Server echoes updated history — store it for next turn
          if (data.message_history) {
            messageHistory = data.message_history;
            delete data.message_history;
          }
          onMessage(data);
        } catch (e) {
          console.error('MAYA: bad line:', line, e);
        }
      }
    }
  } catch (e) {
    onMessage({ type: 'error', text: 'Connection error. Please try again.' });
  }

  isBusy = false;
  el.sendBtn.disabled = !el.input.value.trim() || !isConnected;
  // (input is already cleared above — this just re-enables if user typed while waiting)
}

// ── Message rendering ─────────────────────────────────────────────────────────
function addMessage(role, text, meta = {}) {
  const wrap = document.createElement('div');
  wrap.className = `message ${role}`;

  // Extract provider label from steps (e.g. "[help_response/sarvam]" → "sarvam")
  let providerBadge = '';
  if (meta.steps && meta.steps.length) {
    const step = meta.steps.find(s => s.includes('_response/'));
    if (step) {
      const m = step.match(/_response\/(\w+)/);
      if (m) providerBadge = `<span class="provider-badge">via ${m[1]}</span>`;
    }
  }

  // Language badge (only for non-English)
  const langBadge = (meta.language && meta.language !== 'english')
    ? `<span class="lang-badge">${meta.language}</span>`
    : '';

  const badges = (providerBadge || langBadge)
    ? `<div class="message-badges">${providerBadge}${langBadge}</div>`
    : '';

  if (role === 'maya') {
    wrap.innerHTML = `
      <span class="message-avatar">${currentChar}</span>
      <div class="message-content">
        <div class="bubble">${renderMarkdown(text)}</div>
        ${badges}
      </div>`;
  } else {
    wrap.innerHTML = `
      <div class="message-content">
        <div class="bubble">${escapeHtml(text)}</div>
      </div>
      <span class="message-avatar user-icon">👤</span>`;
  }

  el.messages.appendChild(wrap);
  scrollToBottom();
}

function addSystemMessage(text) {
  const div = document.createElement('div');
  div.className = 'system-message';
  div.textContent = text;
  el.messages.appendChild(div);
  scrollToBottom();
}

// ── Thinking indicator ────────────────────────────────────────────────────────
function showThinking() {
  el.thinking.hidden = false;
  scrollToBottom();
}

function hideThinking() {
  el.thinking.hidden = true;
}

// ── Status bar ────────────────────────────────────────────────────────────────
function setStatus(text, type) {
  el.statusText.textContent = text;
  el.statusDot.className    = `status-dot ${type}`;
}

// ── Sidebar data ──────────────────────────────────────────────────────────────
async function refreshSidebar() {
  try {
    const res  = await fetch('/api/history');
    const data = await res.json();

    if (data.recent_topics && data.recent_topics.length) {
      el.recentTopics.innerHTML = data.recent_topics.map(t => `
        <li title="${escapeAttr(t)}">
          <span class="topic-text">${escapeHtml(t)}</span>
          <button class="history-del-btn" data-topic="${escapeAttr(t)}" data-type="topic" title="Remove">×</button>
        </li>`).join('');
    } else {
      el.recentTopics.innerHTML = '<li class="empty">No topics yet</li>';
    }

    if (data.mastery && data.mastery.length) {
      el.masteryList.innerHTML = data.mastery.map(m => `
        <li>
          <span class="mastery-topic" title="${escapeAttr(m.topic)}">${escapeHtml(m.topic)}</span>
          <span class="mastery-badge level-${m.level}">${m.level} ${m.count}×</span>
          <button class="history-del-btn" data-topic="${escapeAttr(m.topic)}" data-type="mastery" title="Remove">×</button>
        </li>`).join('');
    } else {
      el.masteryList.innerHTML = '<li class="empty">Start exploring!</li>';
    }

    // Wire up delete buttons
    document.querySelectorAll('.history-del-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const type  = btn.dataset.type;
        const topic = btn.dataset.topic;
        const url   = type === 'mastery'
          ? `/api/history/mastery?topic=${encodeURIComponent(topic)}`
          : `/api/history/topic?topic=${encodeURIComponent(topic)}`;
        await fetch(url, { method: 'DELETE' });
        refreshSidebar();
      });
    });
  } catch (_) {
    // Network error — sidebar stays as-is
  }
}

async function clearAllHistory() {
  if (!confirm('Clear all history and mastery? This cannot be undone.')) return;
  await fetch('/api/history/all', { method: 'DELETE' });
  refreshSidebar();
}

// ── Models API ────────────────────────────────────────────────────────────────
async function loadModels() {
  try {
    const res  = await fetch('/api/models');
    const data = await res.json();
    el.modelSelect.innerHTML = data.models.map(m =>
      `<option value="${m}">${m.charAt(0).toUpperCase() + m.slice(1)}</option>`
    ).join('');
    const saved = localStorage.getItem('maya_model') || 'auto';
    if (data.models.includes(saved)) el.modelSelect.value = saved;
  } catch (_) {
    // Keep default "Auto" option
  }
}

// Persist preferences across sessions
el.modelSelect.addEventListener('change', () => {
  localStorage.setItem('maya_model', el.modelSelect.value);
});
el.agentSelect.addEventListener('change', () => {
  localStorage.setItem('maya_agent', el.agentSelect.value);
});

// Restore saved agent preference
const savedAgent = localStorage.getItem('maya_agent') || 'auto';
if ([...el.agentSelect.options].some(o => o.value === savedAgent)) {
  el.agentSelect.value = savedAgent;
}

// ── Sidebar toggle ────────────────────────────────────────────────────────────
function toggleSidebar() {
  el.sidebar.classList.toggle('open');
  el.sidebarOverlay.classList.toggle('visible', el.sidebar.classList.contains('open'));
}

el.sidebarToggle.addEventListener('click', toggleSidebar);
el.sidebarOverlay.addEventListener('click', toggleSidebar);

// ── Sidebar tabs ──────────────────────────────────────────────────────────────
const PERSONA_FIELDS = ['tone', 'language', 'grade_level', 'greeting_style', 'response_style', 'avoid'];

document.querySelectorAll('.sidebar-tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.sidebar-tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    const tab = btn.dataset.tab;
    document.getElementById('panel-history').hidden   = (tab !== 'history');
    document.getElementById('panel-reminders').hidden = (tab !== 'reminders');
    document.getElementById('panel-persona').hidden   = (tab !== 'persona');
    if (tab === 'persona')   loadPersonaConfig();
    if (tab === 'reminders') refreshTodos();
  });
});

// ── Persona config load/save ──────────────────────────────────────────────────
async function loadPersonaConfig() {
  try {
    const res  = await fetch('/api/persona-config?persona=srinika');
    const data = await res.json();
    const cfg  = data.config || {};
    PERSONA_FIELDS.forEach(key => {
      const field = document.getElementById(`pf-${key}`);
      if (field) field.value = cfg[key] || '';
    });
  } catch (_) {
    // Server not reachable — fields stay blank
  }
}

async function savePersonaConfig() {
  const btn = document.getElementById('save-persona-btn');
  btn.disabled = true;
  try {
    await Promise.all(PERSONA_FIELDS.map(key => {
      const field = document.getElementById(`pf-${key}`);
      if (!field) return Promise.resolve();
      return fetch('/api/persona-config', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ persona_name: 'srinika', field_key: key, field_value: field.value }),
      });
    }));
    showPersonaToast();
  } catch (_) {
    // Network error — silently ignore, user can retry
  } finally {
    btn.disabled = false;
  }
}

function showPersonaToast() {
  const toast = document.getElementById('persona-toast');
  if (!toast) return;
  toast.hidden = false;
  setTimeout(() => { toast.hidden = true; }, 2200);
}

document.getElementById('save-persona-btn')?.addEventListener('click', savePersonaConfig);

// ── Todos / Reminders ─────────────────────────────────────────────────────────
async function refreshTodos() {
  try {
    const res  = await fetch('/api/todos');
    const data = await res.json();
    renderTodoList(data.todos || []);
    updateTodoBadge(data.todos || []);
  } catch (_) { /* server unreachable */ }
}

function renderTodoList(todos) {
  const ul = document.getElementById('todo-list');
  if (!ul) return;
  if (!todos.length) {
    ul.innerHTML = '<li class="empty">No reminders yet!</li>';
    return;
  }
  ul.innerHTML = todos.map(t => `
    <li class="todo-item" data-id="${t.id}">
      <button class="todo-done-btn" title="Mark done" data-id="${t.id}">✓</button>
      <span class="todo-text">${escapeHtml(t.text)}${t.due_date ? `<span class="todo-due-label"> · ${escapeHtml(t.due_date)}</span>` : ''}</span>
      <button class="todo-del-btn" title="Delete" data-id="${t.id}">×</button>
    </li>`).join('');

  ul.querySelectorAll('.todo-done-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      await fetch(`/api/todos/${btn.dataset.id}/done`, { method: 'PATCH' });
      refreshTodos();
    });
  });
  ul.querySelectorAll('.todo-del-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      await fetch(`/api/todos/${btn.dataset.id}`, { method: 'DELETE' });
      refreshTodos();
    });
  });
}

function updateTodoBadge(todos) {
  const badge = document.getElementById('todo-badge');
  if (!badge) return;
  if (todos.length > 0) {
    badge.textContent = todos.length;
    badge.hidden = false;
  } else {
    badge.hidden = true;
  }
}

async function addTodoFromUI() {
  const input = document.getElementById('todo-input');
  const due   = document.getElementById('todo-due');
  const text  = input?.value.trim();
  if (!text) return;
  await fetch('/api/todos', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ text, due_date: due?.value || null }),
  });
  if (input) input.value = '';
  if (due)   due.value   = '';
  refreshTodos();
}

document.getElementById('todo-add-btn')?.addEventListener('click', addTodoFromUI);
document.getElementById('todo-input')?.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); addTodoFromUI(); }
});

// ── Input handling ────────────────────────────────────────────────────────────
el.input.addEventListener('input', () => {
  el.input.style.height = 'auto';
  el.input.style.height = Math.min(el.input.scrollHeight, 120) + 'px';
  el.sendBtn.disabled = !el.input.value.trim() || !isConnected;
});

el.input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (!el.sendBtn.disabled) sendMessage();
  }
});

el.sendBtn.addEventListener('click', sendMessage);

// ── Idle sleepy timer (30 s) ──────────────────────────────────────────────────
let idleTimer = null;

function resetIdleTimer() {
  clearTimeout(idleTimer);
  if (el.mayaEyes?.getAttribute('data-state') === 'sleepy') setAvatarState('idle');
  idleTimer = setTimeout(() => {
    if (isConnected) setAvatarState('sleepy');
  }, 30_000);
}

document.addEventListener('keydown',    resetIdleTimer);
document.addEventListener('mousedown',  resetIdleTimer);
document.addEventListener('touchstart', resetIdleTimer);

// ── Utilities ─────────────────────────────────────────────────────────────────
/**
 * Client-side safety strip for LLM reasoning blocks.
 * Matches server logic: if stripping <think> leaves nothing, the model wrapped
 * its full response in <think> (Sarvam style) — remove tags but keep content.
 */
function stripThink(text) {
  const cleaned = String(text)
    .replace(/<think>[\s\S]*?<\/think>/gi, '')  // remove complete blocks
    .replace(/<think>[\s\S]*/gi, '')            // remove unclosed tail
    .trim();
  // If nothing survived the strip, just remove the tags and keep the inner content
  if (!cleaned) {
    return String(text).replace(/<\/?think>/gi, '').trim();
  }
  return cleaned;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Render markdown to safe HTML for MAYA chat bubbles.
 * Escapes HTML first (XSS-safe), then applies markdown patterns.
 * Handles: ## headings, **bold**, - bullets, 1. numbered lists, line breaks.
 */
function renderMarkdown(text) {
  const lines = String(text).split('\n');
  const out = [];
  let listTag = null;

  function closeList() {
    if (listTag) { out.push(`</${listTag}>`); listTag = null; }
  }

  function inlineFormat(raw) {
    let t = escapeHtml(raw);
    t = t.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    t = t.replace(/\*(.+?)\*/g, '<em>$1</em>');
    return t;
  }

  for (const line of lines) {
    const trimmed = line.trim();

    const hMatch = trimmed.match(/^#{1,3} (.+)/);
    if (hMatch) { closeList(); out.push(`<strong class="md-heading">${inlineFormat(hMatch[1])}</strong><br>`); continue; }

    const ulMatch = trimmed.match(/^[-*] (.+)/);
    if (ulMatch) {
      if (listTag !== 'ul') { closeList(); out.push('<ul>'); listTag = 'ul'; }
      out.push(`<li>${inlineFormat(ulMatch[1])}</li>`);
      continue;
    }

    const olMatch = trimmed.match(/^(\d+)\. (.+)/);
    if (olMatch) {
      if (listTag !== 'ol') { closeList(); out.push('<ol>'); listTag = 'ol'; }
      out.push(`<li>${inlineFormat(olMatch[2])}</li>`);
      continue;
    }

    closeList();
    if (trimmed === '') { out.push('<br>'); continue; }
    out.push(inlineFormat(trimmed) + '<br>');
  }
  closeList();
  return out.join('').replace(/(<br>)+$/, '');
}

/**
 * Strip markdown syntax before TTS so it is not read aloud.
 * "## Dancing Raisins" → "Dancing Raisins"
 * "**What you need:**" → "What you need:"
 */
function stripMarkdownForTTS(text) {
  return String(text)
    .replace(/#{1,3} /g, '')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/^[-*] /gm, '')
    .replace(/^\d+\. /gm, '')
    .replace(/\n+/g, ' ')
    .replace(/\s{2,}/g, ' ')
    .trim();
}

function escapeAttr(str) {
  return String(str).replace(/"/g, '&quot;');
}

function scrollToBottom() {
  el.messages.scrollTop = el.messages.scrollHeight;
}

// ── Hero resize handle ────────────────────────────────────────────────────────
(function () {
  const HERO_MIN_VH = 15;
  const HERO_MAX_VH = 78;
  const handle = document.getElementById('hero-resize');

  // Restore saved height
  const saved = localStorage.getItem('maya_hero_h');
  if (saved) document.documentElement.style.setProperty('--hero-h', saved + 'vh');

  if (!handle) return;

  let dragging = false;

  function setHeroH(clientY) {
    const headerH = document.getElementById('header').offsetHeight;
    const vh = ((clientY - headerH) / window.innerHeight) * 100;
    const clamped = Math.min(HERO_MAX_VH, Math.max(HERO_MIN_VH, vh));
    document.documentElement.style.setProperty('--hero-h', clamped + 'vh');
    return clamped;
  }

  function onMove(e) {
    if (!dragging) return;
    e.preventDefault();
    setHeroH(e.touches ? e.touches[0].clientY : e.clientY);
  }

  function onEnd(e) {
    if (!dragging) return;
    dragging = false;
    handle.classList.remove('dragging');
    const clientY = e.changedTouches ? e.changedTouches[0].clientY : e.clientY;
    const final = setHeroH(clientY);
    localStorage.setItem('maya_hero_h', final.toFixed(1));
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onEnd);
    document.removeEventListener('touchmove', onMove);
    document.removeEventListener('touchend', onEnd);
  }

  handle.addEventListener('mousedown', (e) => {
    dragging = true;
    handle.classList.add('dragging');
    e.preventDefault();
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onEnd);
  });

  handle.addEventListener('touchstart', (_e) => {
    dragging = true;
    handle.classList.add('dragging');
    document.addEventListener('touchmove', onMove, { passive: false });
    document.addEventListener('touchend', onEnd);
  }, { passive: true });
}());

// ── Init ──────────────────────────────────────────────────────────────────────
loadModels();      // Populate model selector from /api/models
initSession();     // Start session via GET /api/session (replaces WebSocket)
resetIdleTimer();  // Start idle timer

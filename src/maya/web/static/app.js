/**
 * MAYA Web UI — Session 12
 * WebSocket chat client with model/agent selection, history sidebar,
 * character picker, 12-state CSS avatar animations, and voice I/O.
 *
 * Voice input:  Web Speech API (SpeechRecognition) — mic button
 * Voice output: SpeechSynthesis API — speaker toggle in header
 */

'use strict';

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
let ws            = null;
let reconnectMs   = 1000;
let currentChar   = localStorage.getItem('maya_char') || '🦋';
let isConnected   = false;
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

function speakText(text, lang) {
  if (!voiceEnabled || !window.speechSynthesis) return;

  speechSynthesis.cancel();

  const utt = new SpeechSynthesisUtterance(text);
  utt.rate  = 0.92;
  utt.pitch = 1.15;

  if (preferredVoice) {
    utt.voice = preferredVoice;
    utt.lang  = preferredVoice.lang;
  } else {
    utt.lang = (lang && lang !== 'english') ? 'hi-IN' : 'en-IN';
  }

  utt.onstart = () => setAvatarState('talking');
  utt.onend   = () => { setAvatarState(lastDoneState); hideCaption(); };
  utt.onerror = () => { setAvatarState(lastDoneState); hideCaption(); };

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
    el.micBtn.classList.remove('listening');
    el.micBtn.title = 'Voice input';
    if (el.input.value.trim() && isConnected) sendMessage();
  };

  recognition.onerror = (event) => {
    isListening = false;
    el.micBtn.classList.remove('listening');
    el.micBtn.title = 'Voice input';
    if (event.error !== 'no-speech') {
      console.warn('MAYA voice input error:', event.error);
    }
  };
}

function toggleListening() {
  if (!recognition) {
    // SpeechRecognition unavailable — needs HTTPS or localhost
    el.input.placeholder = 'Mic needs HTTPS or localhost — type your message';
    setTimeout(() => {
      el.input.placeholder = 'Ask MAYA anything… (Enter to send, Shift+Enter for new line)';
    }, 3500);
    return;
  }
  if (isListening) {
    recognition.stop();
  } else {
    recognition.start();
    isListening = true;
    el.micBtn.classList.add('listening');
    el.micBtn.title = 'Stop listening';
  }
}

el.micBtn.addEventListener('click', toggleListening);

// ── WebSocket ─────────────────────────────────────────────────────────────────
function connect() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${location.host}/ws`);

  ws.onopen = () => {
    setStatus('connected', 'warn');    // Waiting for "connected" message
    reconnectMs = 1000;
  };

  ws.onclose = () => {
    isConnected = false;
    el.sendBtn.disabled = true;
    setStatus(`reconnecting in ${reconnectMs / 1000}s…`, 'offline');
    setAvatarState('idle');
    setTimeout(connect, reconnectMs);
    reconnectMs = Math.min(reconnectMs * 2, 20000);
  };

  ws.onerror = () => { /* onclose fires after onerror — handled there */ };

  ws.onmessage = (event) => {
    try {
      onMessage(JSON.parse(event.data));
    } catch (e) {
      console.error('MAYA: bad message:', event.data, e);
    }
  };
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
      break;

    case 'thinking':
      showThinking();
      setAvatarState('thinking');
      break;

    case 'response': {
      hideThinking();
      addMessage('maya', data.text, {
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
      showCaption(data.text, voiceEnabled ? 12000 : 6000);
      // Speak the response — avatar switches to 'talking' during playback
      speakText(data.text, data.language);
      setTimeout(refreshSidebar, 1200);
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
function sendMessage() {
  const text = el.input.value.trim();
  if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;

  // Stop any active voice input before sending
  if (isListening && recognition) recognition.stop();

  addMessage('user', text);
  el.sendBtn.disabled = true;   // Re-enabled when response arrives

  ws.send(JSON.stringify({
    text:  text,
    model: el.modelSelect.value,
    agent: el.agentSelect.value,
  }));

  el.input.value = '';
  el.input.style.height = 'auto';
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
        <div class="bubble">${escapeHtml(text)}</div>
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
      el.recentTopics.innerHTML = data.recent_topics
        .map(t => `<li title="${escapeAttr(t)}">${escapeHtml(t)}</li>`)
        .join('');
    } else {
      el.recentTopics.innerHTML = '<li class="empty">No topics yet</li>';
    }

    if (data.mastery && data.mastery.length) {
      el.masteryList.innerHTML = data.mastery.map(m => `
        <li>
          <span class="mastery-topic" title="${escapeAttr(m.topic)}">${escapeHtml(m.topic)}</span>
          <span class="mastery-badge level-${m.level}">${m.level} ${m.count}×</span>
        </li>`).join('');
    } else {
      el.masteryList.innerHTML = '<li class="empty">Start exploring!</li>';
    }
  } catch (_) {
    // Network error — sidebar stays as-is
  }
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
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escapeAttr(str) {
  return String(str).replace(/"/g, '&quot;');
}

function scrollToBottom() {
  el.messages.scrollTop = el.messages.scrollHeight;
}

// ── Init ──────────────────────────────────────────────────────────────────────
loadModels();     // Populate model selector from /api/models
connect();        // Open WebSocket connection
resetIdleTimer(); // Start idle timer

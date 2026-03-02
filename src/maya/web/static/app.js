/**
 * MAYA Web UI — Session 11
 * WebSocket chat client with model/agent selection, history sidebar,
 * character picker, and avatar state management.
 *
 * Session 12 will add:
 *   - 12-state CSS avatar animations
 *   - Web Speech API (voice input)
 *   - SpeechSynthesis (voice output)
 */

'use strict';

// ── DOM References ────────────────────────────────────────────────────────────
const el = {
  statusDot:      document.getElementById('status-dot'),
  statusText:     document.getElementById('status-text'),
  messages:       document.getElementById('messages'),
  input:          document.getElementById('input'),
  sendBtn:        document.getElementById('send-btn'),
  thinking:       document.getElementById('thinking'),
  thinkingEmoji:  document.getElementById('thinking-emoji'),
  modelSelect:    document.getElementById('model-select'),
  agentSelect:    document.getElementById('agent-select'),
  avatar:         document.getElementById('avatar'),
  avatarEmoji:    document.getElementById('avatar-emoji'),
  avatarLabel:    document.getElementById('avatar-label'),
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

// ── Character picker ──────────────────────────────────────────────────────────
function setCharacter(char) {
  currentChar = char;
  localStorage.setItem('maya_char', char);
  el.avatarEmoji.textContent   = char;
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
 * Session 11: only idle-pulse CSS animation is active — state is stored but not
 * yet animated differently. Session 12 adds all 12 @keyframes.
 */
function setAvatarState(state) {
  el.avatar.dataset.state = state;
  el.avatarLabel.textContent = state;
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
      // Load sidebar data
      refreshSidebar();
      break;

    case 'thinking':
      showThinking();
      // Avatar will be updated once we know the intent (in 'response')
      setAvatarState('thinking');
      break;

    case 'response':
      hideThinking();
      addMessage('maya', data.text, {
        intent:   data.intent,
        language: data.language,
        steps:    data.steps || [],
        isOnline: data.is_online,
      });
      // Update status dot to reflect actual online/offline after first LLM call
      setStatus(
        data.is_online ? 'online' : 'offline (Ollama)',
        data.is_online ? 'online' : 'offline'
      );
      setAvatarState(INTENT_DONE_STATE[data.intent] || 'idle');
      el.sendBtn.disabled = !el.input.value.trim();
      // Refresh sidebar with any new topics/mastery
      setTimeout(refreshSidebar, 1200);
      break;

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

    // Recent topics
    if (data.recent_topics && data.recent_topics.length) {
      el.recentTopics.innerHTML = data.recent_topics
        .map(t => `<li title="${escapeAttr(t)}">${escapeHtml(t)}</li>`)
        .join('');
    } else {
      el.recentTopics.innerHTML = '<li class="empty">No topics yet</li>';
    }

    // Mastery
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
    // Restore saved preference
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
  // Auto-grow up to max-height (set in CSS)
  el.input.style.height = 'auto';
  el.input.style.height = Math.min(el.input.scrollHeight, 120) + 'px';
  // Enable send only when there's text and we're connected
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
// Placeholder: Session 12 will hook this into the CSS animation system
let idleTimer = null;

function resetIdleTimer() {
  clearTimeout(idleTimer);
  if (el.avatar.dataset.state === 'sleepy') setAvatarState('idle');
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
loadModels();   // Populate model selector from /api/models
connect();      // Open WebSocket connection
resetIdleTimer(); // Start idle timer

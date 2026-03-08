# MAYA Session 13 — RoboEyes Frontend Spec
**Date:** March 5, 2026  
**Goal:** Replace static emoji avatar with expressive SVG RoboEyes  
**Deadline:** April 3, 2026 (Srinika's second test)  
**Constraint:** RPi-friendly, no external dependencies, vanilla JS, no build step

---

## 1. Current State

```
avatar = CSS-animated emoji inside purple circle
location = top of left sidebar (small, ~80px)
state machine = setAvatarState(state) in app.js ← KEEP THIS, wire to new eyes
12 states already defined: idle, thinking, talking, excited, happy, 
                            celebrating, proud, sad, waving, focused, sleepy, patient
```

**Problem:** Static emoji is forgettable. Srinika needs something alive.

---

## 2. Target State

```
avatar = SVG RoboEyes (two expressive eyes)
style  = cyan eyes on dark rounded panel
size   = large, prominent (min 200x120px, centered)
motion = smooth CSS keyframe transitions per state
hook   = same setAvatarState(state) function — zero backend changes
tests  = 46/46 still passing (no Python changes)
```

**Inspiration:** FluxGarage RoboEyes Arduino library (recreated as SVG+CSS for browser)  
**Reference:** https://github.com/FluxGarage/RoboEyes

---

## 3. SVG Structure

Replace the current avatar emoji div with this SVG structure:

```html
<!-- MAYA Face Panel -->
<div class="maya-face-panel" id="maya-face-panel">
  <svg id="maya-eyes" viewBox="0 0 220 100" 
       xmlns="http://www.w3.org/2000/svg"
       width="220" height="100">
    
    <!-- Left Eye -->
    <rect id="eye-left" 
          x="20" y="10" 
          width="70" height="80" 
          rx="20" ry="20"
          fill="#00e5ff"/>
    
    <!-- Right Eye -->
    <rect id="eye-right" 
          x="130" y="10" 
          width="70" height="80" 
          rx="20" ry="20"
          fill="#00e5ff"/>

    <!-- Left Eye Shine (small white dot, top-right of eye) -->
    <circle id="shine-left" cx="78" cy="22" r="6" fill="white" opacity="0.6"/>
    
    <!-- Right Eye Shine -->
    <circle id="shine-right" cx="188" cy="22" r="6" fill="white" opacity="0.6"/>

  </svg>

  <!-- Emotion label (debug only, hidden in production) -->
  <div id="emotion-label" class="emotion-label">idle</div>
</div>
```

---

## 4. CSS — Eye Panel + All 12 States

```css
/* ── Face Panel ── */
.maya-face-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #0a0a0f;
  border-radius: 24px;
  padding: 16px 20px;
  width: 260px;
  margin: 0 auto 12px auto;
  border: 1px solid #1a1a2e;
}

#maya-eyes {
  display: block;
  overflow: visible;
}

/* Eye base color */
#eye-left, #eye-right {
  fill: #00e5ff;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.emotion-label {
  font-size: 10px;
  color: #444;
  text-transform: uppercase;
  letter-spacing: 2px;
  margin-top: 6px;
  display: none; /* show for debug: display: block */
}

/* ── Keyframe Definitions ── */

/* IDLE — gentle slow pulse */
@keyframes eye-idle {
  0%, 100% { transform: scaleY(1); }
  50%       { transform: scaleY(0.92); }
}

/* BLINK — snap shut, open smooth */
@keyframes eye-blink {
  0%, 90%, 100% { transform: scaleY(1); }
  45%           { transform: scaleY(0.05); }
}

/* THINKING — look up, tilt */
@keyframes eye-think-left {
  0%, 100% { transform: translate(0,0) scaleX(1); }
  40%      { transform: translate(-4px, -6px) scaleX(0.85); }
}
@keyframes eye-think-right {
  0%, 100% { transform: translate(0,0) scaleX(1); }
  40%      { transform: translate(4px, -6px) scaleX(0.85); }
}

/* TALKING — fast vertical bounce */
@keyframes eye-talk {
  0%, 100% { transform: scaleY(1); }
  25%      { transform: scaleY(0.7); }
  75%      { transform: scaleY(1.1); }
}

/* EXCITED — wide open, rapid blink */
@keyframes eye-excited {
  0%, 100% { transform: scaleY(1.2) scaleX(1.1); }
  50%      { transform: scaleY(1.3) scaleX(1.15); }
}

/* HAPPY — eyes curve up (arch shape via ry) */
@keyframes eye-happy {
  0%, 100% { transform: translateY(0); }
  50%      { transform: translateY(-3px); }
}

/* CELEBRATING — spin + grow + sparkle */
@keyframes eye-celebrate {
  0%   { transform: scale(1) rotate(0deg); fill: #00e5ff; }
  25%  { transform: scale(1.3) rotate(-10deg); fill: #ffd700; }
  50%  { transform: scale(1.4) rotate(10deg); fill: #ff6ec7; }
  75%  { transform: scale(1.3) rotate(-5deg); fill: #00ff88; }
  100% { transform: scale(1) rotate(0deg); fill: #00e5ff; }
}

/* PROUD — scale up + glow */
@keyframes eye-proud {
  0%, 100% { transform: scale(1); filter: drop-shadow(0 0 4px #00e5ff); }
  50%      { transform: scale(1.1); filter: drop-shadow(0 0 12px #00e5ff); }
}

/* SAD — droop down */
@keyframes eye-sad {
  0%, 100% { transform: translateY(0) scaleY(1); opacity: 1; }
  50%      { transform: translateY(6px) scaleY(0.75); opacity: 0.7; }
}

/* WAVING — sway left-right */
@keyframes eye-wave-left {
  0%, 100% { transform: translateX(0); }
  25%      { transform: translateX(-8px); }
  75%      { transform: translateX(4px); }
}
@keyframes eye-wave-right {
  0%, 100% { transform: translateX(0); }
  25%      { transform: translateX(8px); }
  75%      { transform: translateX(-4px); }
}

/* FOCUSED — tight squint */
@keyframes eye-focused {
  0%, 100% { transform: scaleY(0.6); }
  50%      { transform: scaleY(0.55); }
}

/* SLEEPY — slow droop, half-close */
@keyframes eye-sleepy {
  0%, 100% { transform: scaleY(0.45); opacity: 0.5; }
  50%      { transform: scaleY(0.4); opacity: 0.4; }
}

/* PATIENT — very slow gentle pulse */
@keyframes eye-patient {
  0%, 100% { transform: scaleY(1); opacity: 1; }
  50%      { transform: scaleY(0.95); opacity: 0.85; }
}

/* ── State → Animation Binding ── */

/* IDLE */
#maya-eyes[data-state="idle"] #eye-left,
#maya-eyes[data-state="idle"] #eye-right {
  animation: eye-idle 3s ease-in-out infinite, 
             eye-blink 5s ease-in-out infinite;
  transform-origin: center center;
  transform-box: fill-box;
}

/* THINKING */
#maya-eyes[data-state="thinking"] #eye-left {
  animation: eye-think-left 2s ease-in-out infinite;
  transform-origin: center center;
  transform-box: fill-box;
}
#maya-eyes[data-state="thinking"] #eye-right {
  animation: eye-think-right 2s ease-in-out infinite;
  transform-origin: center center;
  transform-box: fill-box;
}

/* TALKING */
#maya-eyes[data-state="talking"] #eye-left,
#maya-eyes[data-state="talking"] #eye-right {
  animation: eye-talk 0.4s ease-in-out infinite;
  transform-origin: center center;
  transform-box: fill-box;
}

/* EXCITED */
#maya-eyes[data-state="excited"] #eye-left,
#maya-eyes[data-state="excited"] #eye-right {
  animation: eye-excited 0.5s ease-in-out infinite;
  transform-origin: center center;
  transform-box: fill-box;
}

/* HAPPY */
#maya-eyes[data-state="happy"] #eye-left,
#maya-eyes[data-state="happy"] #eye-right {
  animation: eye-happy 2s ease-in-out infinite;
  transform-origin: center center;
  transform-box: fill-box;
}

/* CELEBRATING */
#maya-eyes[data-state="celebrating"] #eye-left,
#maya-eyes[data-state="celebrating"] #eye-right {
  animation: eye-celebrate 0.8s ease-in-out infinite;
  transform-origin: center center;
  transform-box: fill-box;
}

/* PROUD */
#maya-eyes[data-state="proud"] #eye-left,
#maya-eyes[data-state="proud"] #eye-right {
  animation: eye-proud 1.5s ease-in-out infinite;
  transform-origin: center center;
  transform-box: fill-box;
}

/* SAD */
#maya-eyes[data-state="sad"] #eye-left,
#maya-eyes[data-state="sad"] #eye-right {
  animation: eye-sad 2s ease-in-out infinite;
  transform-origin: center center;
  transform-box: fill-box;
}

/* WAVING */
#maya-eyes[data-state="waving"] #eye-left {
  animation: eye-wave-left 1s ease-in-out infinite;
  transform-origin: center center;
  transform-box: fill-box;
}
#maya-eyes[data-state="waving"] #eye-right {
  animation: eye-wave-right 1s ease-in-out infinite;
  transform-origin: center center;
  transform-box: fill-box;
}

/* FOCUSED */
#maya-eyes[data-state="focused"] #eye-left,
#maya-eyes[data-state="focused"] #eye-right {
  animation: eye-focused 1.5s ease-in-out infinite;
  transform-origin: center center;
  transform-box: fill-box;
}

/* SLEEPY */
#maya-eyes[data-state="sleepy"] #eye-left,
#maya-eyes[data-state="sleepy"] #eye-right {
  animation: eye-sleepy 4s ease-in-out infinite;
  transform-origin: center center;
  transform-box: fill-box;
}

/* PATIENT */
#maya-eyes[data-state="patient"] #eye-left,
#maya-eyes[data-state="patient"] #eye-right {
  animation: eye-patient 3s ease-in-out infinite;
  transform-origin: center center;
  transform-box: fill-box;
}

/* ── Celebrating Fullscreen Popup ── */
#celebration-popup {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.85);
  z-index: 9999;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  animation: fadeIn 0.3s ease;
}
#celebration-popup.active {
  display: flex;
}
#celebration-eyes {
  width: 440px;
  height: 200px;
}
#celebration-text {
  color: #ffd700;
  font-size: 2rem;
  font-weight: bold;
  margin-top: 24px;
  text-align: center;
  text-shadow: 0 0 20px #ffd700;
}
#celebration-sub {
  color: #00e5ff;
  font-size: 1.1rem;
  margin-top: 8px;
}
@keyframes fadeIn {
  from { opacity: 0; transform: scale(0.95); }
  to   { opacity: 1; transform: scale(1); }
}

/* ── Confetti Canvas ── */
#confetti-canvas {
  position: fixed;
  top: 0; left: 0;
  width: 100%; height: 100%;
  pointer-events: none;
  z-index: 10000;
}
```

---

## 5. JavaScript Changes (app.js)

### 5a. Update setAvatarState()

```javascript
function setAvatarState(state) {
  // Update main eyes
  const eyesSvg = document.getElementById('maya-eyes');
  if (eyesSvg) eyesSvg.setAttribute('data-state', state);
  
  // Update emotion label (debug)
  const label = document.getElementById('emotion-label');
  if (label) label.textContent = state;

  // Trigger celebration popup for 'celebrating' state
  if (state === 'celebrating') {
    triggerCelebration();
  }
}
```

### 5b. Celebration Popup

```javascript
function triggerCelebration() {
  const popup = document.getElementById('celebration-popup');
  if (!popup) return;

  // Set celebration text (rotate through messages)
  const messages = [
    { main: "Bilkul Sahi! 🌟", sub: "Perfect answer, Srinika!" },
    { main: "Shabash! ✨",      sub: "You're so smart!" },
    { main: "Waah! 🎉",         sub: "Getting better every day!" },
    { main: "Excellent! 💫",    sub: "MAYA is proud of you!" },
  ];
  const msg = messages[Math.floor(Math.random() * messages.length)];
  document.getElementById('celebration-text').textContent = msg.main;
  document.getElementById('celebration-sub').textContent = msg.sub;

  // Show popup
  popup.classList.add('active');

  // Launch confetti
  launchConfetti();

  // Auto-dismiss after 4 seconds
  setTimeout(() => dismissCelebration(), 4000);
}

function dismissCelebration() {
  const popup = document.getElementById('celebration-popup');
  if (popup) popup.classList.remove('active');
  stopConfetti();
}

// Tap anywhere to dismiss
document.getElementById('celebration-popup')
  ?.addEventListener('click', dismissCelebration);
```

### 5c. Confetti (pure canvas — no library)

```javascript
let confettiParticles = [];
let confettiFrame = null;
const CONFETTI_COLORS = ['#00e5ff','#ffd700','#ff6ec7','#00ff88','#ff4444','#ffffff'];

function launchConfetti() {
  const canvas = document.getElementById('confetti-canvas');
  const ctx = canvas.getContext('2d');
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;

  confettiParticles = Array.from({length: 120}, () => ({
    x: Math.random() * canvas.width,
    y: Math.random() * canvas.height - canvas.height,
    w: Math.random() * 10 + 5,
    h: Math.random() * 6 + 3,
    color: CONFETTI_COLORS[Math.floor(Math.random() * CONFETTI_COLORS.length)],
    speed: Math.random() * 3 + 2,
    angle: Math.random() * 360,
    spin: Math.random() * 4 - 2,
    drift: Math.random() * 2 - 1,
  }));

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    confettiParticles.forEach(p => {
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.angle * Math.PI / 180);
      ctx.fillStyle = p.color;
      ctx.fillRect(-p.w/2, -p.h/2, p.w, p.h);
      ctx.restore();
      p.y += p.speed;
      p.x += p.drift;
      p.angle += p.spin;
      if (p.y > canvas.height) {
        p.y = -10;
        p.x = Math.random() * canvas.width;
      }
    });
    confettiFrame = requestAnimationFrame(draw);
  }
  draw();
}

function stopConfetti() {
  if (confettiFrame) cancelAnimationFrame(confettiFrame);
  const canvas = document.getElementById('confetti-canvas');
  if (canvas) canvas.getContext('2d').clearRect(0,0,canvas.width,canvas.height);
  confettiParticles = [];
}
```

---

## 6. HTML Changes (index.html)

### 6a. Replace avatar div

**REMOVE:**
```html
<div class="avatar" id="avatar">🐱</div>
```

**REPLACE WITH:**
```html
<!-- RoboEyes Face Panel -->
<div class="maya-face-panel" id="maya-face-panel">
  <svg id="maya-eyes" viewBox="0 0 220 100"
       xmlns="http://www.w3.org/2000/svg"
       data-state="idle">
    <rect id="eye-left"  x="20"  y="10" width="70" height="80" rx="20" ry="20" fill="#00e5ff"/>
    <rect id="eye-right" x="130" y="10" width="70" height="80" rx="20" ry="20" fill="#00e5ff"/>
    <circle id="shine-left"  cx="78"  cy="22" r="6" fill="white" opacity="0.6"/>
    <circle id="shine-right" cx="188" cy="22" r="6" fill="white" opacity="0.6"/>
  </svg>
  <div id="emotion-label" class="emotion-label">idle</div>
</div>
```

### 6b. Add celebration popup (before closing body tag)

```html
<!-- Celebration Popup -->
<div id="celebration-popup">
  <svg id="celebration-eyes" viewBox="0 0 440 200"
       xmlns="http://www.w3.org/2000/svg"
       data-state="celebrating">
    <rect x="40"  y="20" width="140" height="160" rx="40" ry="40" fill="#ffd700"/>
    <rect x="260" y="20" width="140" height="160" rx="40" ry="40" fill="#ffd700"/>
    <circle cx="168" cy="44" r="12" fill="white" opacity="0.7"/>
    <circle cx="388" cy="44" r="12" fill="white" opacity="0.7"/>
  </svg>
  <div id="celebration-text">Bilkul Sahi! 🌟</div>
  <div id="celebration-sub">Perfect answer, Srinika!</div>
</div>

<!-- Confetti Canvas -->
<canvas id="confetti-canvas"></canvas>
```

---

## 7. State → Trigger Mapping

| State | Triggered by | What Srinika sees |
|-------|-------------|-------------------|
| `idle` | Default / waiting | Eyes slow pulse + auto-blink |
| `thinking` | After message sent | Eyes look up asymmetrically |
| `talking` | TTS playing | Eyes bounce fast |
| `excited` | Greeting intent | Eyes wide + rapid pulse |
| `happy` | After any response | Eyes float up gently |
| `celebrating` | Math correct answer | **FULLSCREEN popup + confetti + gold eyes** |
| `proud` | After good session | Eyes glow cyan |
| `sad` | Farewell intent | Eyes droop down |
| `waving` | After farewell response | Eyes sway left-right |
| `focused` | Math processing | Eyes squint/narrow |
| `sleepy` | 30s idle timeout | Eyes half-closed |
| `patient` | Waiting for retry | Very slow pulse |

---

## 8. What Does NOT Change

```
✅ app.py (FastAPI)          — no changes
✅ hello_world_graph.py      — no changes  
✅ llm_router.py             — no changes
✅ memory_store.py           — no changes
✅ setAvatarState() signature — same, just new implementation
✅ WebSocket protocol         — no changes
✅ 46/46 tests               — must still pass
```

**Session 13 touches ONLY:**
- `index.html` — SVG structure + popup HTML
- `style.css` — eye animations + panel styles
- `app.js` — setAvatarState() + celebration + confetti

---

## 9. Step-by-Step Instructions for Claude Code

```
STEP 1: SVG Eyes (no animation yet)
→ Replace avatar div with maya-face-panel + SVG structure
→ Verify eyes render correctly in browser
→ SHOW ME. WAIT FOR APPROVAL.

STEP 2: CSS Animations (all 12 states)
→ Add all keyframes + state bindings to style.css
→ Test by manually setting data-state in browser console:
  document.getElementById('maya-eyes').setAttribute('data-state', 'celebrating')
→ SHOW ME each state. WAIT FOR APPROVAL.

STEP 3: Celebration Popup + Confetti
→ Add popup HTML, CSS, JS
→ Wire to setAvatarState('celebrating')
→ Test: trigger celebrating state, verify popup + confetti appear
→ Auto-dismiss after 4s, tap-to-dismiss working
→ SHOW ME. WAIT FOR APPROVAL.

STEP 4: Cleanup
→ Remove old emoji avatar CSS (.avatar class)
→ Remove character picker (sidebar emoji grid) — no longer needed
→ Verify 46/46 tests still passing
→ SHOW ME final result.
```

---

## 10. Success Criteria

```
✅ RoboEyes visible and animated in browser
✅ All 12 states render with distinct animations
✅ Celebrating → fullscreen popup + gold eyes + confetti
✅ Confetti auto-stops after 4s
✅ Tap anywhere dismisses popup
✅ setAvatarState() works identically to before
✅ No external JS libraries added
✅ Works on Raspberry Pi (tested on low-power browser)
✅ 46/46 tests passing
✅ Srinika says WOW on April 3rd 🎯
```

---

*Session 13 spec written: March 5, 2026*  
*Next: Session 14 — Layout redesign (MAYA face as hero, mobile-first)*  
*Voice response + personality context adjustments: post Session 13*

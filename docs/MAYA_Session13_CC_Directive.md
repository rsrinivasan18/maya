# MAYA Session 13 — Claude Code Directive
# Expressive RoboEyes with p5.js (Touch + Mouse Tracking)

---

## CONTEXT

MAYA is a bilingual Hindi/English STEM companion for a 9-year-old girl (Srinika).
Current avatar = static emoji in sidebar. Goal = living, expressive eyes she can't stop playing with.

Current web stack:
- FastAPI + WebSocket backend (app.py)
- Vanilla JS frontend (app.js)
- CSS (style.css)
- Single page (index.html)
- No build step, CDN only
- Must run on Raspberry Pi 5

Current avatar state machine in app.js:
```javascript
setAvatarState(state) // already exists, called by WebSocket events
```
States: idle, thinking, talking, excited, happy, celebrating, proud, 
        sad, waving, focused, sleepy, patient

46/46 tests currently passing. DO NOT touch any Python files.

---

## GOAL

Replace static emoji avatar with p5.js expressive eyes that:
1. Follow mouse on PC
2. Follow finger touch on tablet/iPhone
3. Smoothly morph per emotion state
4. Auto-blink randomly (every 3-5 seconds)
5. Have micro-jitter when idle (feels alive, breathing)
6. Trigger fullscreen celebration popup on 'celebrating' state

---

## STEP 1 — Add p5.js canvas, draw basic eyes, follow mouse/touch
### DO THIS STEP ONLY. SHOW ME RESULT. WAIT FOR APPROVAL.

### 1a. Add to index.html (in sidebar, replace current avatar div)

REMOVE this (or equivalent avatar element):
```html
<div class="avatar" id="avatar">🐱</div>
```

REPLACE WITH:
```html
<div id="maya-eyes-container">
  <div id="maya-p5-canvas"></div>
  <div id="emotion-label" class="emotion-label">idle</div>
</div>
```

Add p5.js CDN just before closing </body>:
```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/p5.js/1.9.0/p5.min.js"></script>
<script src="/static/maya_eyes.js"></script>
```

### 1b. Add to style.css

```css
#maya-eyes-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin: 0 auto 12px auto;
}

#maya-p5-canvas canvas {
  border-radius: 20px;
  display: block;
}

.emotion-label {
  font-size: 10px;
  color: #444;
  text-transform: uppercase;
  letter-spacing: 2px;
  margin-top: 4px;
  display: none; /* change to block for debugging */
}
```

### 1c. Create new file: maya/src/maya/web/static/maya_eyes.js

```javascript
// ─────────────────────────────────────────────
// MAYA RoboEyes — p5.js expressive eye system
// ─────────────────────────────────────────────

const MAYA_EYES = new p5(function(p) {

  // ── Canvas size ──
  const W = 220;
  const H = 110;

  // ── Eye geometry ──
  const EYE = {
    leftX:  65,
    rightX: 155,
    y:      55,
    w:      70,   // full open width
    h:      72,   // full open height
    radius: 22,   // corner radius
    pupilR: 14,   // pupil radius
    pupilMaxOffset: 16, // max pupil travel from center
    shineR: 5,    // shine dot radius
  };

  // ── State ──
  let currentState = 'idle';
  let leftPupil  = { x: EYE.leftX,  y: EYE.y };
  let rightPupil = { x: EYE.rightX, y: EYE.y };
  let targetLeft  = { x: EYE.leftX,  y: EYE.y };
  let targetRight = { x: EYE.rightX, y: EYE.y };

  // ── Eyelid (0=fully open, 1=fully closed) ──
  let lidLeft  = 0;
  let lidRight = 0;
  let targetLidLeft  = 0;
  let targetLidRight = 0;

  // ── Blink timer ──
  let nextBlink = 0;

  // ── Micro-jitter ──
  let jitterX = 0;
  let jitterY = 0;

  // ── Eye color ──
  let eyeColor = [0, 229, 255]; // cyan default

  // ── Pointer tracking ──
  let pointerX = W / 2;
  let pointerY = H / 2;

  // ─────────────────────────────────────────
  p.setup = function() {
    let canvas = p.createCanvas(W, H);
    canvas.parent('maya-p5-canvas');
    p.frameRate(60);
    nextBlink = p.millis() + randomBlinkInterval();

    // Mouse tracking
    canvas.mouseMoved(function() {
      let rect = canvas.elt.getBoundingClientRect();
      pointerX = p.mouseX;
      pointerY = p.mouseY;
    });

    // Touch tracking (tablet/iPhone)
    canvas.touchMoved(function(e) {
      let rect = canvas.elt.getBoundingClientRect();
      if (e.touches && e.touches[0]) {
        pointerX = e.touches[0].clientX - rect.left;
        pointerY = e.touches[0].clientY - rect.top;
      }
      return false; // prevent scroll
    });
  };

  // ─────────────────────────────────────────
  p.draw = function() {
    p.clear();
    p.background(10, 10, 15); // near black

    updatePupilTargets();
    updateBlink();
    applyMicroJitter();
    smoothMove();

    drawEye(EYE.leftX,  EYE.y, leftPupil,  lidLeft);
    drawEye(EYE.rightX, EYE.y, rightPupil, lidRight);
  };

  // ─────────────────────────────────────────
  // Draw one eye at (cx, cy)
  function drawEye(cx, cy, pupil, lid) {
    let eh = EYE.h * (1 - lid * 0.95); // shrink height when lid closes
    let ew = EYE.w;

    p.push();
    p.translate(cx + jitterX, cy + jitterY);

    // Eye white/body
    p.noStroke();
    p.fill(eyeColor[0], eyeColor[1], eyeColor[2]);
    roundRect(-ew/2, -eh/2, ew, eh, EYE.radius);

    // Pupil (dark circle)
    let px = pupil.x - cx;
    let py = pupil.y - cy;
    p.fill(0, 20, 30);
    p.ellipse(px, py, EYE.pupilR * 2, EYE.pupilR * 2 * (1 - lid * 0.5));

    // Pupil shine
    p.fill(255, 255, 255, 200);
    p.ellipse(px + EYE.shineR * 0.6, py - EYE.shineR * 0.8,
              EYE.shineR, EYE.shineR);

    // Eyelid overlay (top-down rect that covers eye when closing)
    if (lid > 0.05) {
      p.fill(10, 10, 15);
      p.noStroke();
      let lidH = EYE.h * lid;
      roundRect(-ew/2 - 2, -EYE.h/2 - 2, ew + 4, lidH + EYE.radius, EYE.radius);
    }

    p.pop();
  }

  // ─────────────────────────────────────────
  // Rounded rect helper (p5.js doesn't have built-in)
  function roundRect(x, y, w, h, r) {
    p.beginShape();
    p.vertex(x + r, y);
    p.vertex(x + w - r, y);
    p.quadraticVertex(x + w, y, x + w, y + r);
    p.vertex(x + w, y + h - r);
    p.quadraticVertex(x + w, y + h, x + w - r, y + h);
    p.vertex(x + r, y + h);
    p.quadraticVertex(x, y + h, x, y + h - r);
    p.vertex(x, y + r);
    p.quadraticVertex(x, y, x + r, y);
    p.endShape(p.CLOSE);
  }

  // ─────────────────────────────────────────
  // Move pupils toward pointer (clamped to eye boundary)
  function updatePupilTargets() {
    let dx = pointerX - EYE.leftX;
    let dy = pointerY - EYE.y;
    let dist = Math.sqrt(dx*dx + dy*dy);
    let maxD = EYE.pupilMaxOffset;
    let scale = dist > maxD ? maxD / dist : 1;

    targetLeft  = { x: EYE.leftX  + dx * scale * 0.5,
                    y: EYE.y      + dy * scale * 0.5 };
    targetRight = { x: EYE.rightX + (pointerX - EYE.rightX) * scale * 0.5,
                    y: EYE.y      + (pointerY - EYE.y) * scale * 0.5 };

    // State overrides
    if (currentState === 'thinking') {
      targetLeft  = { x: EYE.leftX  - 6, y: EYE.y - 14 };
      targetRight = { x: EYE.rightX + 6, y: EYE.y - 14 };
    } else if (currentState === 'sad') {
      targetLeft  = { x: EYE.leftX  - 4, y: EYE.y + 12 };
      targetRight = { x: EYE.rightX + 4, y: EYE.y + 12 };
    } else if (currentState === 'sleepy') {
      targetLeft  = { x: EYE.leftX,  y: EYE.y + 8 };
      targetRight = { x: EYE.rightX, y: EYE.y + 8 };
    } else if (currentState === 'focused') {
      targetLeft  = { x: EYE.leftX,  y: EYE.y };
      targetRight = { x: EYE.rightX, y: EYE.y };
    }
  }

  // ─────────────────────────────────────────
  // Smooth lerp pupils toward target
  function smoothMove() {
    let speed = currentState === 'excited' ? 0.18 : 0.08;
    leftPupil.x  = p.lerp(leftPupil.x,  targetLeft.x,  speed);
    leftPupil.y  = p.lerp(leftPupil.y,  targetLeft.y,  speed);
    rightPupil.x = p.lerp(rightPupil.x, targetRight.x, speed);
    rightPupil.y = p.lerp(rightPupil.y, targetRight.y, speed);
    lidLeft  = p.lerp(lidLeft,  targetLidLeft,  0.12);
    lidRight = p.lerp(lidRight, targetLidRight, 0.12);
  }

  // ─────────────────────────────────────────
  // Auto blink + state-based lid control
  function updateBlink() {
    let now = p.millis();

    // State lid overrides
    if (currentState === 'sleepy') {
      targetLidLeft = targetLidRight = 0.55;
    } else if (currentState === 'focused') {
      targetLidLeft  = 0.3;
      targetLidRight = 0.1;
    } else if (currentState === 'sad') {
      targetLidLeft = targetLidRight = 0.35;
    } else if (currentState === 'waving') {
      // wink right eye
      targetLidLeft  = 0;
      targetLidRight = p.sin(now * 0.005) > 0 ? 0.9 : 0;
    } else {
      targetLidLeft = targetLidRight = 0;
    }

    // Auto blink
    if (now > nextBlink) {
      triggerBlink();
      nextBlink = now + randomBlinkInterval();
    }
  }

  function triggerBlink() {
    targetLidLeft = targetLidRight = 1;
    setTimeout(() => {
      targetLidLeft = targetLidRight = 
        currentState === 'sleepy' ? 0.55 : 0;
    }, 150);
  }

  function randomBlinkInterval() {
    return 3000 + Math.random() * 4000; // 3-7 seconds
  }

  // ─────────────────────────────────────────
  // Micro-jitter (idle breathing feel)
  function applyMicroJitter() {
    if (currentState === 'idle' || currentState === 'happy' || currentState === 'patient') {
      let t = p.millis() * 0.001;
      jitterX = Math.sin(t * 0.7) * 1.2;
      jitterY = Math.sin(t * 0.5) * 0.8;
    } else if (currentState === 'excited' || currentState === 'celebrating') {
      jitterX = (Math.random() - 0.5) * 4;
      jitterY = (Math.random() - 0.5) * 4;
    } else {
      jitterX = p.lerp(jitterX, 0, 0.1);
      jitterY = p.lerp(jitterY, 0, 0.1);
    }
  }

  // ─────────────────────────────────────────
  // Public API — called by app.js setAvatarState()
  const STATE_COLORS = {
    idle:        [0, 229, 255],   // cyan
    thinking:    [130, 100, 255], // purple
    talking:     [0, 229, 255],   // cyan
    excited:     [255, 200, 0],   // yellow
    happy:       [0, 255, 140],   // green
    celebrating: [255, 215, 0],   // gold
    proud:       [0, 229, 255],   // cyan bright
    sad:         [100, 150, 255], // blue
    waving:      [0, 229, 255],   // cyan
    focused:     [255, 140, 0],   // orange
    sleepy:      [80, 80, 150],   // dim blue
    patient:     [0, 229, 255],   // cyan
  };

  window.mayaEyesSetState = function(state) {
    currentState = state;
    eyeColor = STATE_COLORS[state] || STATE_COLORS.idle;

    // Update debug label
    const label = document.getElementById('emotion-label');
    if (label) label.textContent = state;
  };

}, document.getElementById('maya-p5-canvas') || document.body);
```

### 1d. Update setAvatarState() in app.js

FIND the existing setAvatarState function and ADD this line inside it:

```javascript
function setAvatarState(state) {
  // ... existing code stays ...

  // ADD THIS LINE:
  if (window.mayaEyesSetState) window.mayaEyesSetState(state);

  // Trigger celebration popup
  if (state === 'celebrating') triggerCelebration();
}
```

### STEP 1 SUCCESS CRITERIA:
- Eyes render in browser (two cyan rounded rectangles)
- Pupils follow mouse cursor on PC
- Pupils follow finger on touch (test in browser mobile simulator)
- Auto-blink every 3-7 seconds
- Micro-jitter visible when idle (subtle breathing)
- No console errors
- 46/46 tests still passing

### SHOW ME RESULT. WAIT FOR APPROVAL BEFORE STEP 2.

---

## STEP 2 — Wire all 12 emotion states
### DO THIS STEP ONLY. SHOW ME RESULT. WAIT FOR APPROVAL.

Test each state by running in browser console:
```javascript
window.mayaEyesSetState('thinking')
window.mayaEyesSetState('celebrating')
window.mayaEyesSetState('sleepy')
// etc.
```

Verify these specific behaviours:

| State | Eye Color | Pupils | Lids | Feel |
|-------|-----------|--------|------|------|
| idle | cyan | follow pointer | open | gentle jitter |
| thinking | purple | look UP | open | asymmetric |
| talking | cyan | follow pointer | flutter | fast blink |
| excited | yellow | follow fast | wide | rapid jitter |
| happy | green | follow pointer | open | float |
| celebrating | gold | spin/wild | open | heavy jitter |
| proud | cyan bright | center | open | glow |
| sad | blue | look DOWN | half | slow |
| waving | cyan | follow | wink right | sway |
| focused | orange | locked center | squint left | tight |
| sleepy | dim blue | look down | half closed | slow drift |
| patient | cyan | follow pointer | open | very slow |

For TALKING state — add rapid lid flutter:
```javascript
// In updateBlink(), add talking case:
} else if (currentState === 'talking') {
  let t = p.millis();
  targetLidLeft = targetLidRight = 
    Math.sin(t * 0.025) > 0.3 ? 0.6 : 0;
}
```

### SHOW ME ALL STATES. WAIT FOR APPROVAL BEFORE STEP 3.

---

## STEP 3 — Fullscreen Celebration Popup + Canvas Confetti
### DO THIS STEP ONLY. SHOW ME RESULT. WAIT FOR APPROVAL.

### 3a. Add to index.html (before closing </body>):

```html
<!-- Celebration Popup -->
<div id="celebration-popup">
  <div id="celebration-eyes-wrap">
    <!-- Big p5 eyes go here — reuse same canvas scaled up -->
  </div>
  <div id="celebration-text">Bilkul Sahi! 🌟</div>
  <div id="celebration-sub">Perfect answer, Srinika!</div>
  <div id="celebration-hint">tap anywhere to continue</div>
</div>

<!-- Confetti Canvas (always on top) -->
<canvas id="confetti-canvas"></canvas>
```

### 3b. Add to style.css:

```css
#celebration-popup {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.92);
  z-index: 9999;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  animation: popupFadeIn 0.4s ease;
}
#celebration-popup.active {
  display: flex;
}
#celebration-text {
  color: #ffd700;
  font-size: 2.4rem;
  font-weight: 800;
  margin-top: 28px;
  text-align: center;
  text-shadow: 0 0 30px #ffd700, 0 0 60px #ffd700;
  animation: textPulse 0.8s ease-in-out infinite;
}
#celebration-sub {
  color: #00e5ff;
  font-size: 1.2rem;
  margin-top: 10px;
  opacity: 0.9;
}
#celebration-hint {
  color: #444;
  font-size: 0.75rem;
  margin-top: 32px;
  letter-spacing: 2px;
  text-transform: uppercase;
}
@keyframes popupFadeIn {
  from { opacity: 0; transform: scale(0.92); }
  to   { opacity: 1; transform: scale(1); }
}
@keyframes textPulse {
  0%, 100% { transform: scale(1); }
  50%      { transform: scale(1.05); }
}
#confetti-canvas {
  position: fixed;
  top: 0; left: 0;
  width: 100%; height: 100%;
  pointer-events: none;
  z-index: 10000;
}
```

### 3c. Add to app.js:

```javascript
// ── Celebration messages (Hindi/English mix) ──
const CELEBRATE_MSGS = [
  { main: "Bilkul Sahi! 🌟",  sub: "Perfect answer, Srinika!" },
  { main: "Shabash! ✨",       sub: "You're amazing!" },
  { main: "Waah Waah! 🎉",    sub: "MAYA is so proud of you!" },
  { main: "Excellent! 💫",    sub: "Getting smarter every day!" },
  { main: "Sahi Jawab! 🌈",   sub: "You nailed it!" },
];

function triggerCelebration() {
  const popup = document.getElementById('celebration-popup');
  if (!popup) return;
  const msg = CELEBRATE_MSGS[Math.floor(Math.random() * CELEBRATE_MSGS.length)];
  document.getElementById('celebration-text').textContent = msg.main;
  document.getElementById('celebration-sub').textContent  = msg.sub;
  popup.classList.add('active');
  launchConfetti();
  setTimeout(dismissCelebration, 4000);
}

function dismissCelebration() {
  document.getElementById('celebration-popup')?.classList.remove('active');
  stopConfetti();
}

document.getElementById('celebration-popup')
  ?.addEventListener('click', dismissCelebration);

// ── Pure canvas confetti (no library) ──
const CONFETTI_COLORS = ['#00e5ff','#ffd700','#ff6ec7','#00ff88','#ff4444','#c084fc'];
let confettiParticles = [];
let confettiFrame     = null;

function launchConfetti() {
  const canvas = document.getElementById('confetti-canvas');
  const ctx    = canvas.getContext('2d');
  canvas.width  = window.innerWidth;
  canvas.height = window.innerHeight;

  confettiParticles = Array.from({ length: 150 }, () => ({
    x:     Math.random() * canvas.width,
    y:     Math.random() * canvas.height - canvas.height,
    w:     Math.random() * 12 + 4,
    h:     Math.random() * 7  + 3,
    color: CONFETTI_COLORS[Math.floor(Math.random() * CONFETTI_COLORS.length)],
    speed: Math.random() * 3 + 2,
    angle: Math.random() * 360,
    spin:  Math.random() * 5 - 2.5,
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
      p.y     += p.speed;
      p.x     += p.drift;
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
  const c = document.getElementById('confetti-canvas');
  if (c) c.getContext('2d').clearRect(0, 0, c.width, c.height);
  confettiParticles = [];
  confettiFrame = null;
}
```

### STEP 3 SUCCESS CRITERIA:
- Math correct answer → fullscreen popup appears
- Gold eyes in popup + celebration text
- Confetti falls from top
- Auto-dismisses after 4 seconds
- Tap anywhere dismisses immediately
- SHOW ME. WAIT FOR APPROVAL BEFORE STEP 4.

---

## STEP 4 — Cleanup + Final Verification
### DO THIS STEP ONLY. SHOW ME RESULT. WAIT FOR APPROVAL.

```
1. Remove old .avatar CSS class entirely from style.css
2. Remove character picker grid from sidebar (no longer needed)
   — the p5 eyes ARE the character now
3. Remove old emoji avatar HTML element
4. Verify no console errors on page load
5. Run: pytest tests/ -v
6. Confirm 46/46 passing
7. Test on mobile browser (Chrome DevTools → iPhone view)
   → touch simulation → pupils follow finger
```

---

## FILES TOUCHED IN THIS SESSION

```
MODIFIED:
  maya/src/maya/web/static/index.html   ← SVG structure + popup HTML
  maya/src/maya/web/static/style.css    ← eye panel + popup + confetti CSS
  maya/src/maya/web/static/app.js       ← setAvatarState() + celebration + confetti

NEW FILE:
  maya/src/maya/web/static/maya_eyes.js ← full p5.js eye system

NOT TOUCHED (zero changes):
  app.py, hello_world_graph.py, llm_router.py,
  memory_store.py, settings.py, state.py,
  chat_loop.py, tests/
```

---

## GOLDEN RULE

```
ONE STEP AT A TIME.
Show me after each step.
Wait for my approval.
Never proceed to next step without confirmation.
46/46 tests must pass at end of session.
```

---

## SUCCESS = SRINIKA SAYS WOW ON APRIL 3RD 🎯

*Spec written: March 5, 2026*
*Session 14 next: Layout redesign — MAYA face as hero, mobile-first*

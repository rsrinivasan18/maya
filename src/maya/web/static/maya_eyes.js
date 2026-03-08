// ─────────────────────────────────────────────
// MAYA RoboEyes — p5.js expressive eye system
// Session 13 CC Directive — Step 2 (girly + mouth)
// ─────────────────────────────────────────────

const MAYA_EYES = new p5(function(p) {

  // ── Dynamic canvas dimensions ──
  let W = 600;
  let H = 390;   // W × 0.65 — taller to fit mouth

  // ── Geometry (computed in initGeometry) ──
  let EYE   = {};
  let MOUTH = {};

  // ── State ──
  let currentState = 'idle';
  let leftPupil   = { x: 0, y: 0 };
  let rightPupil  = { x: 0, y: 0 };
  let targetLeft  = { x: 0, y: 0 };
  let targetRight = { x: 0, y: 0 };

  // ── Eyelids ──
  let lidLeft  = 0,  lidRight  = 0;
  let targetLidLeft = 0, targetLidRight = 0;

  // ── Mouth ──
  let mouthOpen        = 0;
  let targetMouthOpen  = 0;

  // ── Blush (cheek hearts) ──
  let blushAlpha       = 0;
  let targetBlushAlpha = 0;

  // ── Timers & jitter ──
  let nextBlink = 0;
  let jitterX = 0, jitterY = 0;

  // ── Color ──
  let eyeColor = [0, 229, 255];

  // ── Pointer ──
  let pointerX = 0, pointerY = 0;

  // ─────────────────────────────────────────
  function initGeometry() {
    // Hero is 46vh; canvas gets ~30% of viewport height, leaving room for caption+padding
    H = Math.max(Math.round(window.innerHeight * 0.30), 150);
    W = Math.round(H / 0.65);

    const s = W / 220;

    EYE = {
      leftX:          62  * s,
      rightX:         158 * s,
      y:              H   * 0.38,   // upper 38% of canvas
      w:              66  * s,      // eye width
      h:              84  * s,      // tall oval — feminine
      pupilR:         16  * s,
      pupilMaxOffset: 13  * s,
      shineR:         6   * s,
      lashLen:        12  * s,
      lashW:          max(1.5, 2 * s),
    };

    MOUTH = {
      x:  W / 2,
      y:  H * 0.80,
      w:  52 * s,   // smile arc width
      h:  22 * s,   // mouth open height
    };

    leftPupil  = { x: EYE.leftX,  y: EYE.y };
    rightPupil = { x: EYE.rightX, y: EYE.y };
    targetLeft  = { x: EYE.leftX,  y: EYE.y };
    targetRight = { x: EYE.rightX, y: EYE.y };
    pointerX = W / 2;
    pointerY = H * 0.38;
  }

  function max(a, b) { return a > b ? a : b; }

  // ─────────────────────────────────────────
  p.setup = function() {
    initGeometry();
    let canvas = p.createCanvas(W, H);
    canvas.parent('maya-p5-canvas');
    p.frameRate(60);
    nextBlink = p.millis() + randomBlinkInterval();

    canvas.mouseMoved(function() {
      pointerX = p.mouseX;
      pointerY = p.mouseY;
    });

    canvas.touchMoved(function(e) {
      let rect = canvas.elt.getBoundingClientRect();
      if (e.touches && e.touches[0]) {
        pointerX = e.touches[0].clientX - rect.left;
        pointerY = e.touches[0].clientY - rect.top;
      }
      return false;
    });
  };

  p.windowResized = function() {
    initGeometry();
    p.resizeCanvas(W, H);
  };

  // ─────────────────────────────────────────
  p.draw = function() {
    p.clear();
    p.background(8, 8, 16);

    updatePupilTargets();
    updateBlink();
    updateMouth();
    applyMicroJitter();
    smoothMove();

    drawBlush();
    drawEye(EYE.leftX,  EYE.y, leftPupil,  lidLeft,  true);
    drawEye(EYE.rightX, EYE.y, rightPupil, lidRight, false);
    drawMouth();
  };

  // ─────────────────────────────────────────
  // Draw one GIRLY oval eye with eyelid + lashes
  function drawEye(cx, cy, pupil, lid, isLeft) {
    const ew = EYE.w;
    const eh_full = EYE.h;
    const eh = eh_full * (1 - lid * 0.96); // shrink vertically as lid closes

    p.push();
    p.translate(cx + jitterX, cy + jitterY);

    // ── 1. Iris (tall oval — feminine) ───────────────────────────
    p.noStroke();
    p.fill(eyeColor[0], eyeColor[1], eyeColor[2]);
    p.ellipse(0, 0, ew, eh);

    // ── 2. Pupil ──────────────────────────────────────────────────
    let px = pupil.x - cx;
    let py = pupil.y - cy;
    // Clamp pupil inside visible iris area
    let maxPY = eh * 0.45 - EYE.pupilR;
    py = Math.max(-maxPY, Math.min(maxPY, py));

    p.fill(10, 5, 20);
    p.ellipse(px, py, EYE.pupilR * 2, EYE.pupilR * 2);

    // ── 3. Sparkle × 2 ───────────────────────────────────────────
    p.fill(255, 255, 255, 240);
    p.ellipse(px + EYE.shineR * 0.8,  py - EYE.shineR * 0.9,
              EYE.shineR * 1.4, EYE.shineR * 1.4);
    p.fill(255, 255, 255, 130);
    p.ellipse(px - EYE.shineR * 0.45, py + EYE.shineR * 0.55,
              EYE.shineR * 0.7, EYE.shineR * 0.7);

    // ── 4. Curved eyelid overlay ──────────────────────────────────
    if (lid > 0.02) {
      p.fill(8, 8, 16);
      const lidEdge = -eh_full / 2 + eh_full * lid;
      p.beginShape();
      p.vertex(-ew / 2 - 3, -eh_full);      // top-left
      p.vertex( ew / 2 + 3, -eh_full);      // top-right
      p.vertex( ew / 2 + 3, -eh_full / 2);  // right side near eye top
      p.quadraticVertex(0, lidEdge, -ew / 2 - 3, -eh_full / 2); // curved bottom
      p.endShape(p.CLOSE);
    }

    // ── 5. Upper lid arc + eyelashes ─────────────────────────────
    const openRatio = 1 - lid;
    if (openRatio > 0.1) {
      // Upper lid outline arc
      p.stroke(25, 10, 45);
      p.strokeWeight(EYE.lashW * 1.6);
      p.noFill();
      p.arc(0, 0, ew, eh, p.PI, p.TWO_PI);

      // 5 eyelashes radiating from upper arc
      p.strokeWeight(EYE.lashW);
      const lashFracs = [-0.42, -0.21, 0, 0.21, 0.42];
      for (let i = 0; i < lashFracs.length; i++) {
        const xf = lashFracs[i];
        // Point on ellipse top
        const baseX = xf * ew;
        const baseY = -Math.sqrt(Math.max(0, 1 - xf * xf)) * eh / 2;
        // Lash direction: tangent normal + slight outward fan
        const tilt   = isLeft ? -0.22 : 0.22;
        const spread = (i - 2) * 0.14; // fan outward
        const lashAngle = -p.PI / 2 + spread + tilt * Math.abs(xf);
        const lashLen = EYE.lashLen * openRatio;
        p.line(baseX, baseY,
               baseX + Math.cos(lashAngle) * lashLen,
               baseY + Math.sin(lashAngle) * lashLen);
      }
      p.noStroke();
    }

    p.pop();
  }

  // ─────────────────────────────────────────
  // Mouth: smile / open lip-sync / frown
  function drawMouth() {
    const mx = MOUTH.x + jitterX * 0.4;
    const my = MOUTH.y + jitterY * 0.4;
    const mw = MOUTH.w;
    const mh = MOUTH.h;
    const c  = [eyeColor[0] * 0.75, eyeColor[1] * 0.75, eyeColor[2] * 0.75];

    p.push();
    p.translate(mx, my);

    if (currentState === 'sad') {
      // ── Frown arc ─────────────────────────────────────
      p.stroke(c[0], c[1], c[2]);
      p.strokeWeight(max(1.5, 2.5 * W / 220));
      p.noFill();
      p.arc(0, mh * 0.25, mw * 0.75, mh, 0, p.PI); // inverted
      p.noStroke();

    } else if (mouthOpen > 0.06) {
      // ── Lip-sync open mouth ───────────────────────────
      const openH = mh * mouthOpen;

      // Mouth cavity
      p.noStroke();
      p.fill(18, 8, 28);
      p.ellipse(0, openH * 0.1, mw * 0.75, openH * 1.3 + mh * 0.2);

      // Teeth (top row)
      p.fill(245, 240, 250);
      p.ellipse(0, -openH * 0.2, mw * 0.6, mh * 0.28);

      // Upper lip curve
      p.stroke(c[0], c[1], c[2]);
      p.strokeWeight(max(1.5, 2.5 * W / 220));
      p.noFill();
      p.arc(0, -openH * 0.5, mw * 0.75, mh * 0.5, p.PI, p.TWO_PI);
      p.noStroke();

    } else {
      // ── Closed smile ──────────────────────────────────
      const bigSmile = ['happy', 'excited', 'celebrating', 'proud', 'waving'].includes(currentState);
      const smileH   = bigSmile ? mh * 0.85 : mh * 0.45;

      p.stroke(c[0], c[1], c[2]);
      p.strokeWeight(max(1.5, 2.5 * W / 220));
      p.noFill();
      p.arc(0, 0, mw, smileH, 0, p.PI);
      p.noStroke();

      // Tiny cheek dimples for big smile
      if (bigSmile) {
        p.fill(c[0], c[1], c[2], 80);
        const dimpleR = mw * 0.08;
        p.ellipse(-mw * 0.52, mh * 0.1, dimpleR, dimpleR * 0.7);
        p.ellipse( mw * 0.52, mh * 0.1, dimpleR, dimpleR * 0.7);
      }
    }

    p.pop();
  }

  // ─────────────────────────────────────────
  // Blush — soft cheek circles for happy/excited
  function drawBlush() {
    blushAlpha = p.lerp(blushAlpha, targetBlushAlpha, 0.06);
    if (blushAlpha < 2) return;

    p.noStroke();
    const br = EYE.w * 0.55;
    const by = EYE.y + EYE.h * 0.28;

    p.fill(255, 120, 160, blushAlpha * 0.55);
    p.ellipse(EYE.leftX  - EYE.w * 0.55, by, br, br * 0.6);
    p.ellipse(EYE.rightX + EYE.w * 0.55, by, br, br * 0.6);
  }

  // ─────────────────────────────────────────
  function updateMouth() {
    if (currentState === 'talking') {
      const t = p.millis() * 0.001;
      targetMouthOpen = Math.max(0, Math.sin(t * 9) * 0.65 + 0.35);
    } else if (currentState === 'excited' || currentState === 'celebrating') {
      targetMouthOpen = 0.75;
    } else {
      targetMouthOpen = 0;
    }
    mouthOpen = p.lerp(mouthOpen, targetMouthOpen, 0.18);

    // Blush target
    targetBlushAlpha = ['happy', 'excited', 'celebrating', 'proud'].includes(currentState) ? 200 : 0;
  }

  // ─────────────────────────────────────────
  function updatePupilTargets() {
    const dx    = pointerX - EYE.leftX;
    const dy    = pointerY - EYE.y;
    const dist  = Math.sqrt(dx * dx + dy * dy);
    const maxD  = EYE.pupilMaxOffset;
    const scale = dist > maxD ? maxD / dist : 1;

    targetLeft  = { x: EYE.leftX  + dx * scale * 0.5,
                    y: EYE.y      + dy * scale * 0.5 };
    targetRight = { x: EYE.rightX + (pointerX - EYE.rightX) * scale * 0.5,
                    y: EYE.y      + (pointerY - EYE.y)       * scale * 0.5 };

    // State overrides
    if (currentState === 'thinking') {
      targetLeft  = { x: EYE.leftX  - EYE.pupilMaxOffset * 0.4, y: EYE.y - EYE.pupilMaxOffset * 0.9 };
      targetRight = { x: EYE.rightX + EYE.pupilMaxOffset * 0.4, y: EYE.y - EYE.pupilMaxOffset * 0.9 };
    } else if (currentState === 'sad') {
      targetLeft  = { x: EYE.leftX  - EYE.pupilMaxOffset * 0.2, y: EYE.y + EYE.pupilMaxOffset * 0.7 };
      targetRight = { x: EYE.rightX + EYE.pupilMaxOffset * 0.2, y: EYE.y + EYE.pupilMaxOffset * 0.7 };
    } else if (currentState === 'sleepy') {
      targetLeft  = { x: EYE.leftX,  y: EYE.y + EYE.pupilMaxOffset * 0.5 };
      targetRight = { x: EYE.rightX, y: EYE.y + EYE.pupilMaxOffset * 0.5 };
    } else if (currentState === 'focused' || currentState === 'proud') {
      targetLeft  = { x: EYE.leftX,  y: EYE.y };
      targetRight = { x: EYE.rightX, y: EYE.y };
    }
  }

  // ─────────────────────────────────────────
  function smoothMove() {
    const speed = currentState === 'excited' ? 0.18
                : currentState === 'patient' ? 0.03
                : 0.08;
    leftPupil.x  = p.lerp(leftPupil.x,  targetLeft.x,  speed);
    leftPupil.y  = p.lerp(leftPupil.y,  targetLeft.y,  speed);
    rightPupil.x = p.lerp(rightPupil.x, targetRight.x, speed);
    rightPupil.y = p.lerp(rightPupil.y, targetRight.y, speed);
    lidLeft  = p.lerp(lidLeft,  targetLidLeft,  0.12);
    lidRight = p.lerp(lidRight, targetLidRight, 0.12);
  }

  // ─────────────────────────────────────────
  function updateBlink() {
    const now = p.millis();

    if (currentState === 'sleepy') {
      targetLidLeft = targetLidRight = 0.55;
    } else if (currentState === 'focused') {
      targetLidLeft  = 0.3;
      targetLidRight = 0.1;
    } else if (currentState === 'sad') {
      targetLidLeft = targetLidRight = 0.35;
    } else if (currentState === 'waving') {
      targetLidLeft  = 0;
      targetLidRight = p.sin(now * 0.005) > 0 ? 0.9 : 0;
    } else if (currentState === 'talking') {
      // Gentle soft crinkle — cute, not angry
      targetLidLeft = targetLidRight = Math.sin(now * 0.01) > 0.5 ? 0.16 : 0;
    } else {
      targetLidLeft = targetLidRight = 0;
    }

    if (now > nextBlink) {
      triggerBlink();
      nextBlink = now + randomBlinkInterval();
    }
  }

  function triggerBlink() {
    targetLidLeft = targetLidRight = 1;
    setTimeout(() => {
      targetLidLeft = targetLidRight = currentState === 'sleepy' ? 0.55 : 0;
    }, 140);
  }

  function randomBlinkInterval() {
    return 3000 + Math.random() * 4000;
  }

  // ─────────────────────────────────────────
  function applyMicroJitter() {
    if (['idle', 'happy', 'patient'].includes(currentState)) {
      const t = p.millis() * 0.001;
      jitterX = Math.sin(t * 0.7) * 1.2;
      jitterY = Math.sin(t * 0.5) * 0.8;
    } else if (['excited', 'celebrating'].includes(currentState)) {
      jitterX = (Math.random() - 0.5) * 4;
      jitterY = (Math.random() - 0.5) * 4;
    } else {
      jitterX = p.lerp(jitterX, 0, 0.1);
      jitterY = p.lerp(jitterY, 0, 0.1);
    }
  }

  // ─────────────────────────────────────────
  const STATE_COLORS = {
    idle:        [0,   229, 255],
    thinking:    [130, 100, 255],
    talking:     [0,   229, 255],
    excited:     [255, 200,   0],
    happy:       [0,   255, 140],
    celebrating: [255, 215,   0],
    proud:       [0,   255, 255],
    sad:         [100, 150, 255],
    waving:      [0,   229, 255],
    focused:     [255, 140,   0],
    sleepy:      [80,   80, 150],
    patient:     [0,   229, 255],
  };

  window.mayaEyesSetState = function(state) {
    currentState = state;
    eyeColor     = STATE_COLORS[state] || STATE_COLORS.idle;
    const label  = document.getElementById('emotion-label');
    if (label) label.textContent = state;
  };

}, document.getElementById('maya-p5-canvas') || document.body);

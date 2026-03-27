# MAYA Dev Log - 2026-03-26

---

## Session 19 — Kids UX Improvements

### Goals
- Remove adult UI controls (model/agent dropdowns, hamburger) from Srinika's view
- Fix RoboEyes eye symmetry bug noticed by Srinika
- Remove black box around RoboEyes — eyes should float on background
- Upgrade background: warmer, animated, more magical
- Upgrade chat bubbles: MAYA purple+gold, Srinika amber
- Improve input box for 9-year-old readability
- Fix thinking indicator text

Branch: `feature/kids-ux` → merged to master

---

### Change 1 — Header Cleanup

**Removed from view:** Model dropdown, Agent dropdown, hamburger menu button

**Kept:** MAYA logo, green online dot, speaker button

**Approach:** Selects kept in DOM as `hidden` elements — app.js references them by ID and would crash if they were fully removed. Guard added for `sidebarToggle` null reference (was causing silent JS crash that blocked `initSession()` from running → MAYA showed "connecting…" forever).

**Files:** `index.html`, `app.js`

---

### Change 2 — RoboEyes Eye Symmetry Fix

**Bug:** Left eye appeared more active / larger than right eye.

**Root causes (two issues):**

1. **Pupil tracking asymmetry** — original code computed `scale` from distance to the LEFT eye only, then applied it to both eyes. When pointer was near the right eye, left eye's scale was wrong → asymmetric movement.

   **Fix:** Compute a single offset from the midpoint between both eyes and apply the same `(offX, offY)` to both pupils. Both eyes now always move identically.

2. **Eye position rounding** — `leftX = 62*s` and `rightX = 158*s` could have sub-pixel differences when `s` is a non-integer.

   **Fix:** `leftX = cx - 48*s`, `rightX = cx + 48*s` where `cx = W/2` — guaranteed pixel-perfect symmetry.

3. **`focused` state lids** — was `targetLidLeft=0.3, targetLidRight=0.1` (asymmetric). Fixed to `0.2/0.2`.

**File:** `maya_eyes.js`

---

### Change 3 — Remove Black Box Around Eyes

**Problem:** `p.background(8, 8, 16)` filled the p5 canvas with a dark rectangle every frame. Eyes appeared inside a black box.

**Fix:** Removed `p.background(8, 8, 16)`. Canvas now uses only `p.clear()` → fully transparent. Eyes float directly on the hero background.

**Side effect:** Eyelid overlay (`fill(8,8,16)`) and lash arc stroke (`stroke(25,10,45)`) were invisible against the old black background but showed as dark bars on transparent canvas.
- Eyelid overlay: changed to `fill(13, 11, 26)` — matches `--bg` page colour
- Lash/arc stroke: changed to dark teal derived from eye colour (`eyeColor * 0.12 + offset`)
- `border-radius: 24px` on canvas removed (no box to round)

**File:** `maya_eyes.js`, `style.css`

---

### Change 4 — Background Upgrade

**Changes to `#maya-hero` background:**
- Purple radials strengthened (opacity 0.18 → 0.30)
- Added warm gold hint at bottom edge: `rgba(251,191,36,0.08)`
- Deeper base gradient: `#1a0840 → #0d0624 → #090518`

**CSS star field (28 stars):**
- Sizes increased ~40% (0.8–1.5px → 1.2–2.4px)
- Opacities increased ~30% (0.30–0.70 → 0.55–0.95)
- `star-twinkle` animation: 5s → 8s, added subtle `scale` pulse

**Nebula glow (`::after`):**
- Wider: `min(60vw,420px)` → `min(70vw,480px)`
- Richer gradient with two radial stops
- Slower: 6s → 8s

**`hero-aurora` animation (new):**
- Applied to `#maya-hero` (14s ease-in-out alternate)
- `brightness` + `saturate` only — NO `hue-rotate` (hue-rotate was shifting cyan eyes to green)

**`isolation: isolate` on `#maya-eyes-container`** — creates new stacking context to shield eyes from any future parent filters.

**File:** `style.css`

---

### Change 5 — Chat Bubble Upgrade

**MAYA bubble:**
- Background: translucent purple `rgba(93,55,180,0.55)` — visible but lets starfield show through
- Border: `2px solid #FFD700` (gold)
- Speech tail colour updated to match new background

**Srinika bubble:**
- Colour: warm amber/gold gradient `#c97c10 → #e89a20 → #f5b942`
- Text: dark `#1c0800` (readable on gold)
- `font-weight: 600`

**General:**
- Font size: 15px → 16px
- Line height: 1.75 → 1.8
- Bubble padding: `13px 18px` → `14px 20px`
- Border radius: `--radius-msg (26px)` → `28px`

**File:** `style.css`

---

### Change 6 — Input Box Upgrade

- `border-radius`: `var(--radius-pill)` → `32px` (noticeably rounder)
- Padding: `12px 22px` → `14px 26px` (bigger feel)
- Font size: 15px → 16px
- Placeholder: `"Ask me anything, Srinika!"` — non-italic, `text-muted` colour, `font-weight: 500`
- Focus ring: purple glow + subtle gold tint

**File:** `style.css`

---

### Change 7 — Eye Colour Fix

**Problem:** Eyes appeared green. Two causes:
1. `happy` state (triggered after greetings) used `[0, 255, 140]` — visually green
2. `hero-aurora` originally used `hue-rotate` which shifted cyan to green (fixed by removing hue-rotate)

**Final eye colour: Cyan `#00BFFF` = `[0, 191, 255]`**

Updated states: `idle`, `talking`, `happy`, `waving`, `patient`, `proud` → all use cyan `[0, 191, 255]`
Special states unchanged: `thinking` (purple), `excited` (gold), `celebrating` (gold), `sad` (blue), `focused` (amber), `sleepy` (dark indigo)

**File:** `maya_eyes.js`

---

### Bugs Fixed This Session

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| MAYA showing "connecting…" forever | `sidebarToggle` null crash halted JS init | Guard: `if (el.sidebarToggle)` |
| Eyes green (not cyan) | `happy` state = `[0,255,140]`; `hue-rotate` in aurora | Fixed state colour + removed hue-rotate |
| Black box around eyes | `p.background(8,8,16)` drawn every frame | Removed; canvas transparent |
| Dark bars above eyes after box removal | Lash/eyelid colours matched old black bg | Matched to page bg colour |
| Eye asymmetry | Scale computed from left eye only; sub-pixel position rounding | Midpoint offset + `cx ± 48s` positioning |

---

### Files Changed

| File | Changes |
|------|---------|
| `src/maya/web/static/index.html` | Header simplified, thinking text, input placeholder |
| `src/maya/web/static/app.js` | sidebarToggle null guard |
| `src/maya/web/static/maya_eyes.js` | Symmetry fix, transparent canvas, eye colours |
| `src/maya/web/static/style.css` | Background, bubbles, input, aurora animation |

---

### Pending (Next Session)

- Rebuild Docker image + push to ECR + redeploy App Runner (`www.mayaai.ink`)
- Session 20: Curriculum integration (waiting for Srinika's textbook index pages)
- Session 21: Gamification — badges, streaks, quest agent

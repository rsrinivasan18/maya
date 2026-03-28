# MAYA — Lessons Learned
## CC (Claude Code) Learning Log
*Reviewed at the start of every session. These are gold.*

---

## Lesson 2026-03-28-A
**What happened:** LLM ignored no-markdown instruction in base.md — bold text appeared in responses.
**What should have happened:** Plain conversational text always.
**Rule going forward:** Format constraints need two layers:
1. Inject in Python code at runtime (not just in .md files)
2. Post-process the response text before returning from the node
Never rely on prompt files alone for hard format rules.

---

## Lesson 2026-03-28-B
**What happened:** RoboEyes face pushed to the right side on production.
**What should have happened:** Always horizontally centred.
**Rule going forward:** p5.js `canvas.parent('id')` does not centre the canvas inside the div.
Always add `display:flex; justify-content:center` to the canvas wrapper div.
Test on mobile viewport before considering centering "done".

---

## Lesson 2026-03-28-C
**What happened:** RoboEyes froze on mobile/App Runner — draw() loop silently stopped.
**What should have happened:** Animation runs continuously.
**Rule going forward:** Any p5.js sketch deployed to cloud or mobile needs a watchdog timer.
Use `setInterval` + `lastDrawMs` heartbeat pattern. If draw() hasn't run in 10s, call `p.loop()`.
Browser tab backgrounding, App Runner Envoy, and mobile lifecycle all can kill RAF silently.

---

## Lesson 2026-03-28-D
**What happened:** Eye colour turned yellow after math responses because `celebrating` state = gold.
**What should have happened:** Eyes always cyan — MAYA's identity colour.
**Rule going forward:** For a character with a defined identity colour, don't use colour for emotion.
Express emotion through shape (lid position, mouth curve), movement (blink speed, pupil jitter),
and blush — not hue changes. Colour changes break character identity.

---

## Lesson 2026-03-24-A
**What happened:** App Runner blocks WebSocket upgrades (Envoy proxy → 403 Forbidden).
**What should have happened:** Real-time communication working on cloud.
**Rule going forward:** App Runner does not support WebSocket. Use HTTP streaming (NDJSON) instead.
Pattern: `GET /api/session` (init) + `POST /chat` (StreamingResponse, NDJSON).
Keep WebSocket in app.py only for local dev / Raspberry Pi.

---

## Lesson 2026-03-24-B
**What happened:** Pydantic v2 rejected `session_id` as int when field typed as `str`.
**What should have happened:** Flexible type accepted both.
**Rule going forward:** Pydantic v2 does NOT coerce `int → str` in lax mode.
When a field can come from different sources (API returning int, localStorage returning str),
type it as `int | str` not just `str`.

---

## Lesson 2026-03-24-C
**What happened:** App Runner CREATE_FAILED — `/health` returned 404. Root cause: old Docker image.
**What should have happened:** Health check passed → service running.
**Rule going forward:** Whenever adding a new health check endpoint, always rebuild + push the image
BEFORE deploying the App Runner service. The App Runner health check runs against the actual running
image, not the Terraform configuration.

---

## Lesson 2026-03-24-D
**What happened:** Secrets injection failed because IAM instance role wasn't ready when App Runner deployed.
**What should have happened:** App Runner had permissions at startup.
**Rule going forward:** In Terraform, always add `depends_on` for IAM role + policy resources
when an App Runner service depends on them. IAM propagation is not instantaneous.
```
depends_on = [
  aws_iam_role_policy.apprunner_instance,
  aws_iam_role_policy_attachment.apprunner_ecr
]
```

---

## Lesson 2026-03-24-E
**What happened:** `requirements-web.txt` had `litellm>=1.0.0` — vulnerable to supply chain attack.
**What should have happened:** Version pinned to last clean version.
**Rule going forward:** Any dependency used in the Docker/cloud image must be version-pinned.
`>=` ranges allow automatic updates to malicious versions.
`litellm` pinned to `==1.82.6` — 1.82.7/1.82.8 contained credential-stealing malware (TeamPCP, 2026-03-24).

---

## Lesson 2026-03-20-A
**What happened:** Tried to commit with "Co-Authored-By: Claude" in message — user rejected this.
**What should have happened:** Clean commit message, no attribution lines.
**Rule going forward:** NEVER add "Co-Authored-By" to any commit message for this project.
User has explicitly rejected this multiple times.

---

## Lesson 2026-03-20-B
**What happened:** Made Python file changes during a frontend-only session.
**What should have happened:** Zero Python file changes.
**Rule going forward:** When directive says "frontend only", do not touch:
app.py, hello_world_graph.py, memory_store.py, llm_router.py, or any .py file.
Only: index.html, app.js, style.css, maya_eyes.js.

---

## Lesson 2026-03-20-C
**What happened:** hue-rotate in `hero-aurora` CSS animation shifted cyan eye colour to green/yellow.
**What should have happened:** Eyes always cyan.
**Rule going forward:** CSS `filter` on a parent element affects ALL children including p5.js canvas.
`isolation: isolate` does NOT protect from parent filters.
Never use `hue-rotate` on a container that holds the eyes canvas.
Only use `brightness` and `saturate` in aurora-type animations.

---

## Meta-rules (always apply)

- 57/57 tests must pass after every change. Run before committing.
- Never mark a task done without proving it works.
- One step at a time. Show result. Wait for approval. Then next step.
- Never add "Co-Authored-By" to commits.
- requirements-web.txt is the Docker image — version-pin everything in it.
- p5.js always needs: local file (no CDN), canvas centering, watchdog timer.

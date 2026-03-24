# 🤖 MAYA — Session 17
## AWS Cloud Deployment + HTTP Streaming + CBSE Grade 5 Curriculum
**Claude Code Directive | April 3rd Deadline**

---

## 1. Context & Why This Session

MAYA was running locally and on Docker. Session 17 makes it publicly accessible on AWS, aligns the curriculum to Srinika's actual school grade, and fixes a transport-layer blocker that prevented the WebSocket from working behind App Runner.

---

## 2. Session Goals

| Goal | Status |
|------|--------|
| Docker image (web-only, no voice deps) | ✅ Done |
| AWS infrastructure via Terraform (ECR, RDS, Secrets Manager, IAM, App Runner) | ✅ Done |
| Custom domain: www.mayaai.ink → App Runner | ✅ Done |
| SSL certificate (ACM, Route 53 validated) | ✅ Done |
| Replace WebSocket with HTTP streaming (App Runner blocks WS) | ✅ Done |
| CBSE Grade 5 curriculum base for all subject prompts | ✅ Done |
| Mythology analogies in base.md (Rama, Arjuna/Krishna) | ✅ Done |
| Claude sonnet-4-5 as primary LLM (Sarvam → TTS/STT only) | ✅ Done |
| No-markdown rule in all prompts | ✅ Done |
| MAYA identity fix (never reveal Claude/AI) | ✅ Done |

---

## 3. Architecture Changes

### 3.1 Docker Split

`requirements-web.txt` strips all voice/hardware deps:
- Removed: `piper-tts`, `faster-whisper`, `sounddevice`, `numpy`, `ollama`, `pytest`
- Final image: 720 MB disk / 155 MB compressed
- Dockerfile uses `python:3.12-slim` + `libpq5` for PostgreSQL

### 3.2 AWS Infrastructure (Terraform)

```
ECR (maya-web)
  ↓ image pull
App Runner (256 CPU / 512 MB, ap-southeast-1)
  ↓ /health check every 20s
  ↓ secrets injected from Secrets Manager at runtime
RDS PostgreSQL 15 (db.t3.micro, 20GB, encrypted)
Secrets Manager (/maya/anthropic-api-key, /maya/database-url, etc.)
IAM access role (ECR pull) + instance role (Secrets + CloudWatch)
Route 53 (www.mayaai.ink CNAME → App Runner)
ACM SSL cert (validated via Route 53 CNAME records)
```

### 3.3 WebSocket → HTTP Streaming

**Problem:** App Runner's Envoy proxy returns `403 Forbidden` on all WebSocket upgrade requests. Confirmed via `curl -i` with `Connection: Upgrade` header.

**Solution:** Replaced WebSocket transport with two HTTP endpoints:

| Old | New |
|-----|-----|
| `ws://host/ws` | `GET /api/session` (init, returns session_id) |
| `ws.send(message)` | `POST /chat` (NDJSON streaming response) |

Response format (newline-delimited JSON):
```
{"type": "thinking"}
{"type": "response", "text": "...", "intent": "...", "language": "...", "message_history": [...]}
```

Client-side: `fetch() + ReadableStream` replaces `WebSocket`. `messageHistory` accumulates in browser and is sent with each POST for context continuity.

WebSocket endpoint kept in app.py for local dev / Raspberry Pi.

### 3.4 LLM Routing Change

| Tier | Before | After |
|------|--------|-------|
| Tier 1 | Ollama llama3.2:3b | Claude sonnet-4-5 |
| Tier 2 | Claude sonnet-4-5 | OpenAI gpt-4o-mini |
| TTS/STT | Sarvam | Sarvam (unchanged) |

Rationale: Cloud deployment has reliable internet; Claude gives best quality for Srinika.

---

## 4. Prompt Changes

### base.md
- MAYA identity: never reveal it's Claude or an AI — always "MAYA, your learning didi"
- No-markdown rule: plain text responses only (no `**bold**`, no bullet points, no headers)
- CBSE Grade 5 / Narayana Techno School context
- Mythology analogies:
  - PRIMARY: Rama (full emotional connection, Sony Ramayan reference)
  - SECONDARY: Arjuna/Krishna (confusion → guidance, problem-solving)

### math_tutor.md, science_agent.md, story_agent.md
- Added CBSE Grade 5 student context
- Mythology/history analogies over cooking references

---

## 5. Bugs Fixed

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| App Runner WebSocket 403 | Envoy proxy blocks upgrade requests | HTTP streaming (POST /chat) |
| POST /chat 422 Unprocessable Content | Pydantic v2 won't coerce `int` → `str` | `session_id: int \| str = ""` |
| App Runner CREATE_FAILED (storedBytes=0) | Old image built before `/health` endpoint | Rebuild + push new image |
| ECR login 400 in Git Bash | Shell pipe encoding issue | Run in PowerShell |
| IAM race condition on deploy | Instance role not ready when App Runner starts | `depends_on` for IAM role + attachment |

---

## 6. Files Changed

| File | Change |
|------|--------|
| `requirements-web.txt` | New — web-only deps |
| `Dockerfile` | New — production image |
| `.dockerignore` | New — exclude tests, voice, .env |
| `infrastructure/main.tf` | New — full Terraform config |
| `infrastructure/Makefile` | New — fill-secrets, redeploy targets |
| `infrastructure/variables.tf` | New |
| `infrastructure/outputs.tf` | New |
| `src/maya/web/app.py` | Added `/health`, `/api/session`, `POST /chat` streaming |
| `src/maya/web/static/app.js` | WebSocket → HTTP streaming (initSession + sendMessage) |
| `src/maya/web/static/index.html` | Minor updates |
| `src/maya/web/static/style.css` | Minor updates |
| `src/maya/agents/llm_router.py` | Claude → Tier 1, Sarvam → TTS only |
| `src/maya/prompts/base.md` | MAYA identity, no-markdown, Grade 5, mythology |
| `src/maya/prompts/math_tutor.md` | Grade 5 context |
| `src/maya/prompts/science_agent.md` | Grade 5 context |
| `src/maya/prompts/story_agent.md` | Grade 5 context |

---

## 7. Live URL

**https://www.mayaai.ink** — MAYA is publicly accessible.

---

## 8. Pending (Next Session)

- Root domain redirect: `mayaai.ink` → `www.mayaai.ink`
- Push persona config (Grade 5 / mythology style) to cloud RDS
- Voice (TTS/STT) testing on cloud build
- Add Terraform state to S3 backend (currently local tfstate)

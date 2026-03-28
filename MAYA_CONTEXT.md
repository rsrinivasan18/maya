# MAYA — Master Project Context
## Version: 3.1 | Updated: 2026-03-28 | Status: PRODUCTION LIVE

---

## PROJECT IDENTITY

**Name:** MAYA (Multi-Agent hYbrid Assistant)
**Named by:** Srinivasan's daughter Srinika ❤️
**Sanskrit meaning:** माया (Magic/Illusion)
**Tagline:** Bilingual AI learning companion for curious kids
**Live URL:** https://www.mayaai.ink (PIN: 2026)
**Backup URL:** https://fedcdx6x5d.ap-southeast-1.awsapprunner.com

---

## BUILDER CONTEXT

**Who:** Srinivasan — AI Architect/Contractor at BNP Paribas Singapore
**Experience:** 17+ years (Data Engineering, ML, MLOps, GenAI)
**Current stack at work:** LangGraph, LangChain, LangSmith, Azure OpenAI
**Role:** BNP GenAI Ambassador — teaching LangGraph across organisation
**Philosophy:** Ship to validate. Build fast, understand, iterate.
**GitHub:** Push every session, even messy code

---

## PRIMARY USER — SRINIKA

```
Name:     Srinika
Age:      9 years old
Grade:    5 (CBSE)
School:   Narayana Techno School, Bhopal (faster CBSE pacing)
Language: English primary, Hindi comfortable, Hinglish natural
Voice:    Replaces R with W sound (fwiction=friction, wiver=river)
Loves:    Rama/Ramayana (watched entire Sony Ramayan series)
Learning: Arjuna/Krishna being introduced by father
Dislikes: Dry social science explanations
Responds to: Cricket (India only), food analogies, puzzle/mystery framing,
             mythology analogies
PIN:      2026
```

---

## VISION & PURPOSE

MAYA is a bilingual Hindi/English AI tutor for Srinika — browser-based,
mobile-friendly, voice-enabled. Not a chatbot. A relationship.

MAYA is NOT:
- A generic AI assistant
- Claude (never breaks character)
- Markdown-heavy or formal
- Tied to any hardware (RPi dropped from roadmap)

MAYA IS:
- Srinika's learning didi
- CBSE Grade 5 curriculum-aware
- Warm, playful, never formal
- Plain conversational text only (no markdown ever)
- Always "I'm MAYA, your learning didi" — never "I'm Claude" or "I'm an AI"

---

## CURRENT STATE — SESSION 18 COMPLETE

```
Sessions 1-12:  Core foundation (LangGraph, STT, TTS, memory, agents)
Session 13:     Multi-agent routing + p5.js RoboEyes avatar ✅
Session 14:     Persona settings panel ✅
Session 15:     UX corrections ✅
Session 16:     Kids UX redesign (starfield, Nunito font, speech bubbles) ✅
Session 17:     AWS deployment + HTTP streaming + CBSE G5 curriculum ✅
Session 18:     AWS deployment fixed + DNS + RDS user + smoke test ✅
Session 19:     Kids UX — header cleanup, RoboEyes fixes, bubbles, background ✅
Post-S19:       Production bug fixes — markdown strip, eye colour, centering, freeze watchdog ✅
Session 20:     Curriculum integration (NEXT — waiting for Srinika's textbook chapters)
Session 20+:    WhatsApp integration
```

### Smoke Test Results (March 25, 2026) — 8/8 PASS
```
✅ PIN screen → 2026 → enters app
✅ General agent → warm response, no markdown
✅ Maths agent → tutor-style explanation
✅ Science agent → Grade 5 level
✅ Hindi agent → Hindi/Hinglish Ramayana response
✅ Story agent → engaging, Srinika style
✅ Reminders agent → saves correctly
✅ Voice TTS → audio plays back
```

### What MAYA Can Do (Production Ready)
```
✅ Hindi/English/Hinglish conversation
✅ Math tutor (CBSE Grade 5)
✅ Subject agents: Science, Maths, Social Science,
   English, Hindi, GK, Computer Science, Story, General
✅ Reminders/Todo agent (voice + text)
✅ Conversation history with mastery tracking
✅ RoboEyes animated face (12 emotion states)
✅ Persona settings panel (6 config keys per user)
✅ Voice input (Web Speech API STT) + Sarvam TTS
✅ PIN screen (PIN: 2026, localStorage)
✅ CBSE Grade 5 Narayana Techno curriculum context
✅ Srinika learning profile (Rama/Ramayana analogies)
✅ Spelling/voice forgiveness (fwiction→friction etc.)
✅ Claude Sonnet as primary LLM brain
✅ Sarvam for TTS voice only
✅ Ollama offline fallback
✅ User profile system (profiles/srinika.json)
✅ STT corrections via voice profile (srinika_voice.json)
✅ MAYA identity — never breaks character
✅ No markdown in responses (plain conversational text)
✅ /health endpoint returns 200
✅ Nunito font, speech bubbles, starfield background
✅ HTTP streaming transport (WebSocket dropped for App Runner)
```

---

## ARCHITECTURE

### Stack
```
Frontend:   HTML/CSS/JS (single file, no framework)
            Web Speech API (STT)
            Sarvam API (TTS)
            p5.js RoboEyes animation (local, no CDN)
            Nunito font (local TTF)
            PIN screen (PIN: 2026, localStorage)

Backend:    FastAPI (Python 3.12)
            LangGraph (agent orchestration)
            SQLAlchemy → PostgreSQL (AWS RDS)
            Claude claude-sonnet-4-5 (primary LLM, Tier 1)
            OpenAI gpt-4o-mini (Tier 2 fallback)
            Sarvam (TTS only)
            Ollama (offline fallback)
            LangSmith (observability)

Transport:  HTTP streaming (NDJSON) — NOT WebSocket
            WebSocket kept in app.py for local dev only
            App Runner blocks WebSocket upgrades (Envoy proxy)

Container:  Docker (python:3.12-slim)
            Port: 8080
            Image: 720MB disk / 155MB compressed
            requirements-web.txt (voice/hardware deps stripped)

Infrastructure: AWS App Runner (ap-southeast-1)
                AWS RDS PostgreSQL 15 (db.t3.micro, free tier)
                AWS ECR (image registry)
                AWS Secrets Manager (6 secrets)
                AWS Route 53 (DNS — migrated from Namecheap)
                Terraform (IaC)
                Namecheap (domain registrar only now)
```

### Transport Layer (IMPORTANT)
```
Old (local dev):  ws://host/ws persistent WebSocket
New (production): GET /api/session → returns session_id
                  POST /chat → NDJSON streaming response

Stream format:
  {"type": "thinking"}\n
  {"type": "response", "text": "...", "intent": "...", "message_history": [...]}\n

Client: fetch() + ReadableStream decoder
        messageHistory accumulates in browser
        Sent with each POST request
        Server echoes updated history in response
```

### Agent Architecture (LangGraph)
```
understand_intent node classifies:
  farewell → greeting → math → science → story → general → reminders

Each agent has its own system prompt in src/maya/prompts/
agent_override field in MayaState lets frontend force a specific agent
(Currently exposed as dropdown — PLANNED: remove dropdown, auto-detect only)
```

### LLM Routing
```
Tier 1: Claude claude-sonnet-4-5 (primary)
Tier 2: OpenAI gpt-4o-mini (fallback)
TTS:    Sarvam API
STT:    Web Speech API (browser-native)
Local:  Ollama (offline fallback)
```

---

## KEY FILES

```
src/maya/
  web/
    app.py                  ← FastAPI + HTTP streaming endpoints
    static/
      index.html            ← Full UI + PIN screen
      app.js                ← All frontend logic + fetch streaming
      style.css             ← MAYA night palette + Nunito + bubbles
      maya_eyes.js          ← p5.js RoboEyes (12 emotion states)
      p5.min.js             ← p5.js local (no CDN)
  agents/
    hello_world_graph.py    ← LangGraph graph + all agent nodes
    llm_router.py           ← Claude/Sarvam/Ollama routing
    memory_store.py         ← SQLAlchemy PostgreSQL layer
  prompts/
    base.md                 ← Srinika profile + Rama analogies
    math_tutor.md           ← CBSE G5 maths
    science_agent.md        ← CBSE G5 science
    story_agent.md
    hindi_agent.md
    social_science_agent.md
    english_agent.md
    gk_agent.md
    cs_agent.md
    reminders_agent.md
  profile_loader.py         ← User profile system

profiles/
  srinika.json              ← User config
  srinika_voice.json        ← STT corrections (fwiction→friction etc.)
  srinika_curriculum.md     ← CBSE G5 Narayana Techno
  srinika_learning.md       ← Learning style + analogies

infrastructure/
  main.tf                   ← All AWS resources (Terraform)
  variables.tf
  outputs.tf
  terraform.tfvars          ← GITIGNORED (has db_password)
  Makefile                  ← make fill-secrets, make redeploy
  route53-records.json      ← ACM validation CNAMEs
  route53-root.json         ← A alias record for root domain

requirements-web.txt        ← Production deps (no voice/hardware)
requirements.txt            ← Full deps including local dev
Dockerfile
```

---

## AWS INFRASTRUCTURE

```
Region:  ap-southeast-1 (Singapore)
Account: 221227165737

ECR:     221227165737.dkr.ecr.ap-southeast-1.amazonaws.com/maya-web:latest
         Image: sha256:cae564877a6968b2909df147301558dbe4a1b758aea0647324b057e2d2407b72

App Runner:
  Service: maya-web — RUNNING ✅
  ARN: arn:aws:apprunner:ap-southeast-1:221227165737:service/maya-web/18c7a644911346269d11ae8933da12d9
  URL: fedcdx6x5d.ap-southeast-1.awsapprunner.com
  CPU: 256 / RAM: 512MB
  Health: GET /health every 20s

RDS PostgreSQL 15:
  Identifier: maya-db
  Endpoint: maya-db.cbekemyu0b80.ap-southeast-1.rds.amazonaws.com:5432
  DB: mayadb
  Master: mayaadmin (admin only, not used by app)
  App user: mayaapp ✅ (limited permissions, sequence grants included)
  SSL: forced, Encrypted: yes, Backup: 7 days

Secrets Manager (6 secrets):
  /maya/anthropic-api-key
  /maya/sarvam-api-key
  /maya/sarvam-api-url
  /maya/database-url → postgresql://mayaapp:...@maya-db...
  /maya/connectivity-host → api.anthropic.com
  /maya/connectivity-port → 443

Route 53:
  Hosted Zone: Z093189637BZIF1UE7NU0
  Records:
    A      mayaai.ink      → App Runner alias (Z09819469CZ3KQ8PWMCL)
    CNAME  www.mayaai.ink  → fedcdx6x5d.ap-southeast-1.awsapprunner.com
    CNAME  (3x ACM validation records — 2/3 validated)
```

### Key AWS Commands
```bash
# Check service status
aws apprunner describe-service \
  --service-arn "arn:aws:apprunner:ap-southeast-1:221227165737:service/maya-web/18c7a644911346269d11ae8933da12d9" \
  --region ap-southeast-1 --query "Service.Status"

# Redeploy (after new image push)
aws apprunner start-deployment \
  --service-arn "arn:aws:apprunner:ap-southeast-1:221227165737:service/maya-web/18c7a644911346269d11ae8933da12d9" \
  --region ap-southeast-1

# View logs
aws logs tail /aws/apprunner/maya-web/18c7a644911346269d11ae8933da12d9/application \
  --region ap-southeast-1

# Connect to RDS (as admin)
psql "postgresql://mayaadmin@maya-db.cbekemyu0b80.ap-southeast-1.rds.amazonaws.com:5432/mayadb?sslmode=require"

# Build and push new image
docker build -t maya-web .
docker tag maya-web:latest 221227165737.dkr.ecr.ap-southeast-1.amazonaws.com/maya-web:latest
aws ecr get-login-password --region ap-southeast-1 | docker login --username AWS --password-stdin 221227165737.dkr.ecr.ap-southeast-1.amazonaws.com
docker push 221227165737.dkr.ecr.ap-southeast-1.amazonaws.com/maya-web:latest
```

---

## DOMAINS

```
mayaai.ink     → PRIMARY (live, DNS → Route 53 → App Runner)
mayaai.live    → PARKED (future staging env for MAYA 2.0)
srinivasai.com → Personal brand (not yet configured)

All registered on Namecheap (registrar only now)
DNS: Route 53 (migrated from Namecheap BasicDNS on March 25, 2026)
```

---

## DATABASE SCHEMA (PostgreSQL)

```sql
-- Core tables (auto-created by memory_store.py on startup)
conversations     -- session history
topics            -- turn-level topic log
profile           -- user profile (session_count, total_turns)
persona_config    -- 6 config keys per user
                  -- greeting_style, tone, language_mix,
                  -- response_length, use_analogies, avoid_topics
reminders         -- reminders/todos
```

---

## PERSONA CONFIG (Srinika)

```
greeting_style: warm welcome back with last topic
tone:           warm and playful didi, never formal
language_mix:   Hinglish preferred, pure Hindi/English both fine
response_length: short — max 3 sentences for simple questions
use_analogies:  always — Rama/Ramayana primary, cricket/food secondary
avoid_topics:   adult content, scary stories, violence
```

---

## IDENTITY RULES (CRITICAL — NEVER BREAK)

```
1. MAYA is always "MAYA, your learning didi" — never Claude, never AI
2. No markdown ever — plain conversational text only
3. No session numbers or mastery counts in chat (sidebar only)
4. Hinglish first — match Srinika's language naturally
5. Max 3 sentences for simple answers
6. Always use analogies (Rama primary, cricket/food secondary)
7. Correct fwiction→friction etc. silently, never embarrass her
```

---

## PLANNED NEXT (PRIORITY ORDER)

### Session 19 — Kids UX Improvements ✅ COMPLETE
```
Branch: git checkout -b feature/kids-ux

Change 1: Hide adult UI elements
  → Remove Model dropdown
  → Remove Agent dropdown
  → Remove hamburger menu
  → Keep: MAYA logo, online dot, voice/speaker button only

Change 2: Auto subject detection
  → MAYA auto-detects subject from message content
  → Remove manual agent_override from frontend
  → MAYA announces subject switch naturally:
    "Ooh a maths question! Let me think..."
    "Science explorer mode ON!"
  → If unsure: "Is this maths or science? Tell me more!"

Change 3: Background upgrade
  → Remove black box/border around RoboEyes
  → Eyes float directly on background
  → Warmer animated gradient: deep purple → violet → hints of gold
  → More visible animated stars/particles

Change 4: Chat bubbles
  → MAYA bubble: soft purple with gold border, rounder
  → Srinika bubble: warm gold/amber
  → Minimum 16px font
  → "thinking..." → "hmm, let me think... ✨"

Change 5: Input box
  → Bigger, more inviting
  → Placeholder: "Ask me anything, Srinika!"
  → Rounder corners

Change 6: Fix RoboEyes eye symmetry bug
  → Srinika noticed one eye more active than other
  → Fix p5.js blink/movement timing — must be symmetric
```

### Session 20 — Curriculum Integration
```
→ Wait for Srinika's textbook index pages (Science, English,
  Social Science, Maths — CBSE Grade 5 Narayana Techno)
→ Update srinika_curriculum.md with real chapter names
→ MAYA knows "Chapter 3 is Rocks and Minerals" etc.
→ Weekly study planner via Reminders agent
→ Badge system tied to chapters:
  Complete Chapter 1 Science → "Explorer Badge"
  3 correct Maths in a row   → "Aryabhata Badge"
```

### Session 21 — Gamification
```
→ Badges + Streaks (PostgreSQL: badges_earned, learning_streak)
→ Quest Agent (wrap lessons in Rama/ISRO narrative)
→ Friday Quiz Agent (pulls from completed chapters)
```

### Session 22+ — WhatsApp Integration
```
→ n8n as plumbing layer
→ 7am daily brief for Srinika
→ Reminder notifications via WhatsApp
→ Same LangGraph brain, new interface
```

---

## MAYA 2.0 (POST APRIL 3RD)

```
→ Session memory + lesson planning
→ Progress tracking dashboard
→ Multi-model support
→ 3D character (Spline or Rive)
   Indian girl avatar: purple + gold, bindi, dupatta
   Animated: eyes, head bob, mouth sync with TTS
→ Use mayaai.live as staging environment
```

---

## KNOWN BUGS / TECH DEBT

```
Bug 1: RoboEyes eye symmetry ✅ FIXED (Session 19)
Bug 2: Eyes green after math response ✅ FIXED (celebrating state → cyan)
Bug 3: Face off-centre on production ✅ FIXED (#maya-p5-canvas flex centering)
Bug 4: Avatar freeze on mobile/App Runner ✅ FIXED (watchdog timer)
Bug 5: Markdown in responses ✅ FIXED (_strip_markdown + _NO_MARKDOWN injection)

Bug 3: SSL cert record 3 pending
  Long ACM validation CNAME — Namecheap rejected (60 char limit)
  Added to Route 53 — should auto-validate
  Monitor with: aws apprunner describe-custom-domains ...

Tech debt 1: litellm pinned to 1.82.6
  TeamPCP supply chain attack on 1.82.7/1.82.8 (March 24, 2026)
  requirements.txt updated — redeploy pending

Tech debt 2: Terraform state local
  Should move to S3 backend — deferred

Tech debt 3: mayaapp RDS user permissions
  Sequence grants added manually — should be in Terraform
```

---

## DEPENDENCIES (requirements-web.txt key packages)

```
anthropic>=0.40.0       ← Claude API
sarvamai>=0.1.0         ← Sarvam TTS
openai>=1.0.0           ← OpenAI fallback
litellm==1.82.6         ← PINNED (supply chain attack on 1.82.7/1.82.8)
langgraph                ← Agent orchestration
langchain                ← LLM framework
fastapi                  ← Backend
sqlalchemy               ← ORM
psycopg2-binary          ← PostgreSQL driver
uvicorn                  ← ASGI server
```

---

## DECISIONS LOG

| Decision | Choice | Reason |
|----------|--------|--------|
| Hardware | Dropped RPi/Hailo | Not in roadmap — web first |
| Transport | HTTP streaming (NDJSON) | App Runner blocks WebSocket |
| Primary LLM | Claude claude-sonnet-4-5 | Best quality for Srinika |
| Database | PostgreSQL (RDS) | Replaced SQLite for production |
| DNS | Route 53 | Namecheap 60-char limit on ACM records |
| TTS | Sarvam API | Indian voice quality |
| STT | Web Speech API | Browser-native, no server needed |
| Font | Nunito (local TTF) | No CDN, kid-friendly rounded font |
| p5.js | Local file | No CDN dependency |
| litellm | Pinned ==1.82.6 | Supply chain attack on 1.82.7/1.82.8 |
| Agent UI | Remove dropdowns | Auto-detect better for 9-year-old |
| Character | Indian girl avatar | Purple+gold, bindi, dupatta (MAYA 2.0) |

---

## HOW TO USE THIS FILE

**Starting CC session:**
```
Read MAYA_CONTEXT.md first.
Today's task: [specific task]
Work on feature branch: git checkout -b feature/[name]
Do NOT touch infrastructure/ or terraform files.
```

**After each CC session:**
Ask CC to update the dev log with what was built.
Sync this MAYA_CONTEXT.md with any architectural changes.

**This file is maintained by:** Srinivasan + Claude.ai
**Dev logs are maintained by:** Claude Code (CC)
**Sync frequency:** After every meaningful session

---

*Single source of truth for MAYA project.*
*Version 3.1 — March 28, 2026*
*MAYA is live. Srinika is the QA engineer. April 3rd is the next test.*

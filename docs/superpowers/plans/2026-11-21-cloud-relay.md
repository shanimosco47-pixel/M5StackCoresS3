# Hebrew cloud relay implementation plan

> **For agentic workers:** use superpowers:executing-plans inline. The user explicitly requested continuous implementation and delegated routine choices; no further plan approval pause is needed.

**Goal:** a tested server relay returning Hebrew text, source citations and WAV speech, ready for authenticated provider setup and subsequent CoreS3 integration.

**Architecture:** retain the current firmware and add a server boundary rather than replace the UI/audio drivers. FastAPI accepts bounded PCM WAV, uses Groq STT, configurable OpenRouter LLM/tool calls, Tavily basic search and Azure Hebrew TTS. Versioned v2 returns structured JSON with base64 WAV; v1 returns WAV for compatibility.

**Tech stack:** Python, FastAPI, httpx, unittest, container deployment to Cloud Run after authenticated project/provider verification.

**Spec:** docs/ARCHITECTURE_REVIEW.md, docs/reference/VOICE_ASSISTANT_DESIGN.md, with current actual state in docs/STATUS.md.

## Global constraints

- Preserve existing faces, readable Hebrew and touch interruption; do not flash incomplete replacements.
- Keys only in private runtime configuration/Secret Manager, never logs, source or chat.
- Authenticate before reading audio; bound actual streamed input, WAV duration and response sizes.
- No insecure TLS; no model/provider fallback bypassing privacy policy.
- Private profile requires explicit approval of the entire provider chain and an allowed model.
- Local request limits are a defense, not a billing guarantee or durable distributed quota.
- No claim of production readiness before durable cost controls and live API/device verification.

## Review focus

Cancellation during provider calls; oversized/chunked bodies; malformed WAV; API errors containing secrets;
model-generated tool arguments and source instructions; silent/empty audio; replays and concurrent requests.

## Task 1: relay boundary and pipeline

Files: server/relay/app.py, config.py, audio.py, service.py, tests/test_turn.py.
- [ ] Write behavior tests for authentication, body and WAV validation, Hebrew response contract,
  compatibility v1, privacy denial, silent input, missing settings, provider failures, cancellation and concurrency.
- [ ] Observe expected failure, implement the smallest working boundary/pipeline, rerun suite.

## Task 2: provider integrations and internet search

Files: server/relay/providers.py, tests/test_providers.py.
- [ ] Write tests at actual HTTP request/response boundaries using httpx MockTransport.
- [ ] Implement Groq multipart STT, OpenRouter restricted routing and bounded web_search tool loop,
  Tavily basic search with URL validation and Azure escaped SSML with validated WAV result.
- [ ] Verify sanitised errors, malformed output and no unauthorized provider/model fallbacks.

## Task 3: reproducible operation and deployment preparation

Files: server/requirements.txt, Dockerfile, .dockerignore, README.md, .env.example, scripts.
- [ ] Pin tested dependencies, document v1/v2 contract, limits and unresolved live-account requirements.
- [ ] Exercise local health/ready endpoints and all tests; confirm no text/audio is logged.
- [ ] Inspect cloud authentication and prepare deploy commands; do not target an unverified project.
- [ ] Independent review, fix significant findings, secret scan, commit/push one targeted change.
- [ ] Update STATUS.md and session handoff honestly; continue device integration after live service validation.

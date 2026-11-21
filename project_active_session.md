# Active M5 project session

Last consolidated: 2026-11-21. Current state supersedes older session entries in Git history.

## Exact user instructions

- תעשה מה שצריך כדי לפתור את הבעיה ותסדר לי פתרון עובד
- מבחינתי תעשה כמה שיותר בעצמך
- אל תעצור
- תשמור את כל העבודה והתיעוד כאן — https://github.com/shanimosco47-pixel/M5StackCoresS3
- make sure there is a working github indipendent review working
- כשתסיים תשמיע צליל ב M5 או יותר טוב - שיגיד שהוא סיים את העדכון
- Latest instructions: "זה קריטי או שאפשר בלי?" (Azure), approved Google Cloud TTS alternative with "מצויין" and "GO".
- Groq, OpenRouter and Tavily secrets each have an enabled version1, verified by metadata only.

Goal: Hebrew CoreS3 assistant with faces, readable subtitles, touch interruption, internet search
and swappable cloud models. Announce completion on the device only after actual end-to-end validation.

## Repository and physical device

Work checkout: work/M5StackCoresS3, branch feature/cloud-voice-relay, PR1. Base main is d8a6f97.
M5Unified submodule is intentionally dirty from the documented upstream patch; preserve it.
Physical device still runs stable upstream v0.14.3, with volume180 and bargein_en=1.
User confirmed Hebrew spoken replies, faces, center-tap interruption and top-left mute.
Custom Hebrew/search firmware was built and tested but has not been flashed. Device has no relay adapter yet.
Original flash/NVS backups and credentials remain local, never published.

## Completed relay and review work

FastAPI v1 WAV / v2 text+sources+audio, Groq/OpenRouter/Tavily/Azure adapters, authentication,
bounded uploads, WAV validation, silence filtering, tool limits, privacy denial, cancellation,
timeouts and replay protection implemented. Private routing remains unapproved by default.
38 relay tests and8actual-workflow gate tests pass after the Google speech change (recheck before commit).
Ruff and Bandit medium/high pass; dependencies unchanged from the audited versions.
Separate reviewer reproduced upload/replay/cancellation/deadline defects; all fixed with regressions.
Actual Codex GitHub review found a replay-cache eviction bypass; reproduced, fixed and thread resolved.
Codex reviewed1c57a31with no findings; all GitHub checks green on that commit.
After any further push, an authorized owner/agent must comment @codex review. Actions-bot triggers
cannot authenticate to Codex. Read-only gate checks bot identity, exact commit, completion and no findings.
Copilot was tested and ineligible; CodeRabbit CLI availability unknown. Do not claim either reviewed the code.

## Current cloud target and verified deployment

User created project M5Stack, ID m5stack-515405, replacing the earlier hey-usa target.
New open billing account linked; billingEnabled=true verified. Do not relink billing or repeat login.
Required APIs enabled. Region europe-west1, service voice-relay.
Separate m5-voice-runtime and m5-voice-builder identities exist; builder has roles/run.builder.
Runtime can access five scoped voice-relay secret containers. Device secret, Groq, OpenRouter and
Tavily each have an enabled version1. Azure remains empty and is no longer required.
Google TTS API is enabled; runtime has roles/serviceusage.serviceUsageConsumer.
Google mode uses attached identity, fixed he-IL-Standard-A voice, no new keys. A live CLI-identity
speech call returned200with validated16kHz mono PCM WAV,5.893375seconds/188632bytes.
This does not yet verify the Cloud Run runtime identity or device audio.

Native Cloud Run monthly spend cap5ILSverified CONFIGURED. Overall project alert5ILSis NOT a hard cap.
Cloud Build, storage and external provider charges are outside the Cloud Run service cap.
Bootstrap rerun verified idempotence and preserved device-secret version1.

Deployed source:1c57a31dc7bc42f90a5677139238178c2bd1a96b.
Latest verified revision:voice-relay-00002-vpx.
URL:https://voice-relay-kdmuqgf46a-ew.a.run.app
Live verify_private.py passed:anonymous /health403;authenticated /health200ok:true;
authenticated /ready503configured:false. IAM has no broad public invocation binding.
Cloud Run uses min0/max1,CPU1,memory256Mi,HTTP concurrency4and one ASGI worker.

Google Frontend intercepted /healthz with404 although the route existed in OpenAPI.
Confirmed official reserved-path limitation; canonical /health and /ready aliases now work in cloud.
Legacy z-ending routes remain only for compatibility. No insecure TLS or public-access workaround used.

Browser control was unavailable; normal gcloud/API access works. No active local test server remains.
Python clean venv:work/relay-venv. Operational helpers and current documentation are committed in the PR.

## Remaining work

Active task: replace required Azure Speech with Google Cloud Standard Hebrew TTS using the existing
Cloud Run identity (no new user key/account). Verify pricing, bounded authenticated provider calls,
test failures before implementation, live Hebrew audio, private deployment and exact-head GitHub review.
Preserve Azure compatibility, the physical firmware, fail-closed private routing and existing cost controls.

1. Finish any current documentation-only push/review and save exact verification links in PR1.
2. Three provider keys are stored. Do not request keys in chat or create paid subscriptions.
3. Use tools/cloud/set_provider_secrets.py in the user's interactive terminal, or Secret Manager UI.
4. Validate real provider calls and approved model; verify full-chain privacy and cost controls.
5. Map provider secrets and finish runtime configuration while keeping private routing fail-closed until approved.
6. Implement the CoreS3 relay adapter, preserving faces/subtitles/touch; validate actual speech/search/interruption.
7. Only then arm update_notice and verify the M5 speaks the completion announcement.

Current staging is healthy, private and intentionally not ready for voice. Do not describe the whole device
migration as complete, do not flash an incomplete replacement, and do not claim an alert is a global cap.

# Session handoff

Last consolidated: 2026-11-21. Authoritative current state: STATUS.md.

## User goals and preferences

Fix the physical M5 voice assistant; keep Hebrew speech; increase quiet volume;
make subtitles readable; support touch interruption and internet search.
At the actual end of the update, have the M5 say in Hebrew that the update has finished.
The user wants as much done autonomously as possible and prefers avoiding recurring costs.
User asked for this repository to hold all project work and documentation.

## Diagnosis and completed repair

The original 2025 OpenAI demo embedded a retired preview model endpoint.
The phone hotspot was functional; the actual failure followed network connection.
Full backup preceded replacing the firmware with maintained stackchan-idf v0.14.3.
Hebrew voice conversation now works; center-tap interruption was enabled and confirmed.
Custom fonts/search/announcement were subsequently implemented, reviewed and built, not yet installed.

## Subsequent architecture discussion

User considered API costs, then accepted exploring Gemini Live + Tavily free quotas.
Browser inspection reached sign-in pages for both services; no accounts/keys were provisioned.
User later supplied VOICE_ASSISTANT_DESIGN.md proposing a cloud relay with Groq/OpenRouter/Azure.
We recommended the relay concept while preserving existing firmware and fixing the documented issues.
The source appendix was saved as reference, not treated as tested code.
The user subsequently said “אל תעצור” and explicitly requested a working independent GitHub review.
The relay is now implemented in server/ with32passing local tests and a separate read-only review.
Provider tests use controlled HTTP transports; no new-provider live inference has run.
The user subsequently created project M5Stack, IDm5stack-515405, and a new open billing account.
The new project was linked and required APIs enabled. Private Cloud Run staging was deployed in europe-west1.
Separate runtime/builder identities and five secret containers exist; only a generated device secret has a value.
Native Cloud Run spend cap5ILS/month is verified CONFIGURED; total project alert5ILSis not a hard overall cap.
Update: user has now stored Groq/OpenRouter/Tavily keys (enabled version1metadata verified).
Azure signup required an account upgrade; user approved Google Cloud TTS instead, then said GO.
Google support uses attached runtime identity, fixed he-IL-Standard-A and bounded PCM16 WAV.
Google API enabled and runtime granted serviceusage.serviceUsageConsumer; no JSON key created.
A live CLI-identity synthesis returned200and valid188632-byte/5.893375-second Hebrew PCM WAV.
Runtime identity and hardware playback still need verification; do not claim they passed.
Code is on feature/cloud-voice-relay; GitHub checks and exact-head Copilot review must be observed before
calling the GitHub review integration operational. The original Copilot gate failed eligibility;
the existing Codex app actually reviewed the PR and found a replay-cache issue, fixed with regression.
Actions-bot comments cannot authenticate to Codex: after pushing, the authorized owner/agent must request
@codex review; the read-only gate then verifies current-head completion and no unresolved findings.
The first staging deployment exposed Google Frontend's reserved /healthz path. Canonical aliases /health
and /ready were added with a failing-then-passing regression test; use those for Cloud Run verification.
Current suite:38relay tests and8review-gate tests. See CLOUD_DEPLOYMENT.md and PR1for live revision checks.
No firmware deployment occurred, and the device has no relay adapter yet.

## Sensitive material deliberately omitted

Original full flash backup; all NVS snapshots; provisioning CSV/binaries; Wi-Fi details;
API credentials; raw serial captures; personal account/session data. They remain local.
Do not ask the user to paste credentials in chat. Use provider/account UI or private local settings.

## Resume order

Read STATUS.md, ARCHITECTURE_REVIEW.md, BUILD_AND_RECOVERY.md and VALIDATION.md.
Verify current device/software state before any write. Continue the selected architecture once
provider accounts and privacy/cost constraints are settled; retain working hardware behavior.
The existing experimental OpenAI binary is an archive, not a claim that the free-provider migration is complete.

# Google Hebrew speech alternative

User approved replacing the Azure requirement with Google Cloud TTS on the existing project,
then instructed GO. Routine implementation choices are delegated; no extra account is needed.

Design: keep the HTTP/WAV/device contract. Select Google using TTS_PROVIDER=google and
GOOGLE_CLOUD_PROJECT; retain explicit Azure compatibility. Fix Google voice to he-IL-Standard-A
to avoid selecting a premium model accidentally. Get a short-lived token from the attached
Cloud Run identity, using the fixed metadata endpoint asynchronously, without key files.
Bound responses, reject redirects, sanitize errors and validate decoded 16kHz PCM WAV.

Alternatives: Azure requires account upgrade for this user; a new speech vendor adds another
account/key; Google reuses authorized infrastructure and has a published Standard free quota.
The free quota is not a hard spending cap. The Cloud Run service cap does not cover TTS.

Files: server/relay/config.py and providers.py; provider boundary tests; runtime template;
tools/cloud/deploy_private.ps1; current operational documentation and active session memory.

- [x] Verify official Hebrew voice, encoding, pricing and runtime identity documentation.
- [x] Observe new provider tests fail before implementing Google support.
- [x] Implement and pass provider/audio/error tests; retain the complete existing suite.
- [x] Produce an actual Hebrew PCM WAV through Google, using CLI credentials in process memory.
- [x] Independent read-only code review; no actionable findings.
- [x] Verify private deployment and attached-identity synthesis using the deployed image.
- [x] Reproduce and fix review finding: reject narrowed budget filters, retain API defaults.
- [ ] Finish exact-head GitHub review after the budget regression fix.

Hardware adapter and full conversation/search are subsequent tasks. Do not announce completion
on the M5 until its actual end-to-end behavior has been verified.

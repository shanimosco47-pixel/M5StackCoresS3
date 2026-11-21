# Working CoreS3 cloud conversation

User accepts the current Google Standard Hebrew voice and asks to proceed. Earlier instructions
delegate routine choices, require GitHub documentation/independent review, preserve touch interruption
and request a spoken completion announcement only after hardware validation.

## Design and rulings

- Keep the existing firmware UI/audio coordinator. Add Provider::Relay=3 (append, never renumber),
  with HTTPS relay_url and relay_token in private NVS. Do not put cloud credentials in firmware.
- Root diagnosis: OpenRouter require_parameters plus parallel_tool_calls excludes compatible free
  endpoints; reasoning can consume the entire300-token output budget. Remove the optional parallel
  parameter and keep server enforcement of one call. Retain OpenRouter as an operator choice.
- Initial conversation uses Groq openai/gpt-oss-120b with low reasoning; real public/synthetic probes
  passed Hebrew and tool calling. Existing Groq key suffices. No account upgrade/credit purchase.
- Cloud Run IAM-private staging cannot be called by an unattended ESP32 without another identity
  boundary. Use application authentication with the existing random device secret, and only enable
  direct device reachability after durable admission limits fail closed across process restarts.
  Keep min0/max1 and the verified Cloud Run cap. No global-zero-cost claim.
- Durable Firestore admission stores counters/opaque UUIDs only:6/minute,100/day,3000000reserved
  TTS characters/month,1000characters reserved per turn,10minute dedupe. CAS updateTime/exists
  preconditions prevent concurrent instances overspending reservations. Never refund failures.
- Current no-training requirement remains binding; verify Groq/Google/Tavily terms and distinguish
  no-training from zero retention. Do not route personal context to unapproved free NVIDIA trials.
- New v3 response avoids base64 memory amplification on8MB PSRAM:12-byte envelope, magic M5R3,
  little-endian uint32 JSON length then uint32 WAV length, bounded UTF-8 metadata then PCM WAV.
  JSON has version3, request_id, transcript, answer, sources and timings; no audio/base64 field.
  JSON<=16384bytes, WAV<=1500000bytes. POST/v3/turn uses the existing raw16kHz mono PCM16 request,
  X-Device-Secret, X-Request-ID UUID and X-Profile. v1/v2 remain compatible. DELETE/v2/turn/{UUID}
  cancels all versions. POST/v3/notice returns the same envelope with a fixed completion sentence,
  authenticated and quota-controlled, no arbitrary user-supplied text.
- Device client performs local energy VAD with prefix, minimum speech and silence hysteresis;
  uploads from its worker, never blocks the audio coordinator. Verified TLS, no redirects, bounded
  request/response sizes, fresh UUID per turn, no transcript/key/response-body logs.
- Touch stops local playback immediately; cancel/generation checks discard stale worker events.
  Allow up to50seconds thinking for relay instead of the old15second realtime assumption.

## Tasks and ownership

1. Root: LLM provider/config and v3/notice/app integration, cloud setup, actual end-to-end probes.
2. Quota implementer: server/relay/quota.py plus server/tests/test_quota.py only; expose
   FirestoreQuota(project, client=None, clock=time.time), async admit(identifier), QuotaDenied(reason)
   (duplicate/minute/day/month) and QuotaUnavailable. No infrastructure mutation or commits.
3. Firmware implementer: firmware/stackchan-idf source only, host tests, build instructions.
   Integrate RelayClient into coordinator/config/UI and preserve patched M5Unified. No flash/commit.
4. Root: review both tasks, build ESP-IDF5.5.5, fresh private backup, flash only verified app/needed
   individual NVS values, observe boot and ask for real voice/search/interrupt feedback.
5. Root: independent review, fix findings, all GitHub checks on current head, honest docs/hand-off.

## Preflight conflict scan

| Tasks | Shared interface | Ruling |
|---|---|---|
| Root/quota | async admit(UUID), typed errors | Root alone edits app/config, quota implementer owns module/test. |
| Root/firmware | v3 binary contract, paths, HTTPS shared secret | Fixed contract above; no cross-editing. |
| Quota/firmware | cancellation/replay | Cancellation does not refund quota; generation rejects stale replies. |
| Root | API/provider tests and deployment | Test before implementation; deploy after dependency verification. |
| Quota | durable CAS vs process-memory counters | Firestore is authority; local counters remain defense only. |
| Firmware | worker transport vs coordinator audio ownership | Network worker only emits events; coordinator owns I2S. |

## Progress

- Plan saved before delegated implementation; active session tracks the exact user continuation.
- Current branch feature/cloud-voice-relay is an existing suitable checkout, not main.
- Root already observed/fixed optional-parameter regression;43tests pass locally, not yet committed.

- Implementation/integration complete: durable admission, v3, Relay firmware, private backup/provision, build/flash.
-71server tests,8gate tests, firmware hosttests pass. Real provider chain and directdevice auth validated.
- User responsiveness feedback added local Hebrew hearing/thinking/speaking and touch badge.
- USD freshness live failure fixed using structured official BankofIsrael lookup, tested live in deployedrevision8.
- Current-headGitHubreview and user final physical checks pending; completionnotice unarmed.

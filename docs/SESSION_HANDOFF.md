# Session handoff

Last updated: 2026-11-21. Read STATUS.md and project_active_session.md first.

The user accepted Google Standard Hebrew voice and asked to continue autonomously. They explicitly
approved regular Tavily search after disclosure that queries may be used to improve models.
Keep all code/docs in shanimosco47-pixel/M5StackCoresS3 and maintain actual independent GitHub review.

Current chain: Groq Whisper → Groq openai/gpt-oss-120b (low reasoning, max1200completiontokens) →
optional one Tavily search → Google he-IL-Standard-A, PCM16mono16kHz. OpenRouter and Azure remain
operator choices. No credits/subscriptions purchased. OpenRouter diagnosis: requiring optional
parallel_tool_calls excluded compatible free endpoints; reasoning exhausted the small output budget.

Cloud target m5stack-515405/europe-west1/voice-relay, sourceb5bea5c, revision00008-r6v.
IAM invocation is public for unattended ESP32 access; the app authenticates every voice/cancel/notice
request using a random device secret from scoped Secret Manager. Runtime identity accesses Google
without a JSON key. Firestore(default) holds counters/opaque UUIDs only; CAS admission enforces6/min,
100/day,3MreservedTTSchars/month,1000reservedperturn and10min dedupe across restarts. Fail closed.
5ILSCloudRunservice cap verified; overall5ILSalert is not a global cap.

Actual live chain returned200, Hebrew answer,4sources and12.8566875seconds of validated WAV.
Post-restart duplicate409 and unchanged durable counter verified. verify_device.py passed with
health200/ready200/missingsecret401/authenticatedsilence204/noAIcalls.

Firmware Relay provider3 added without renumbering old providers. Async worker, localVAD, binaryv3,
verifiedTLS, private profile, touch cancellation and stale-event epochs preserve the coordinator UI/I2S.
Independent review found delayed relisten and JSON recursion issues; both fixed with host regressions.
Hardware showed intermittent TLS failures; SDK dynamicRX partial-header behavior was implicated, not proven. HTTP_TLS_DYN_BUF_RX_STATIC selected
per connection; latest build/flashedapp3738896bytes, SHA256
deff20097d92b35fd8ebdd187c463851ae571a0ed4e4a028bca42d8bea3018c3.
Firmware treeb6679ad0f40dd26c1ed8389620827e5bef341843. App-only0x1a0000, QuadPSRAM, IDF5.5.5.

Fresh full16MBbackupSHA25605e81a5cadd65bc407166aed3182ee43d0ef3eb3cabeb0262cbaf3d4322ed36d
is private in original outputs. It contains credentials; never publish. NVS was reread immediately
before provisioning; only provider/relay_url/relay_token changed. Volume180/bargein1 preserved.
No bootloader/partition/exttab writes. Both physicalexttabcopies validatedCRC and main0x1a0000/0x500000.

The hotspot was off; user turned it on. Device subsequently played responses; current staticRXbuild
logged6.2seconds playback at nominal16kHz, safe heap/worker stack. Poll warnings are nonfatal; verify
actual successful turns rather than assuming every warning is failure. User tests for Hebrew display,
search and immediate touch/relisten are pending. Do not arm update_notice before those pass.

71servertests +8gate tests +portable firmware tests pass. GitHub Codex reviewede601a44with no findings.
After final firmware/docs push, request @codex review as the authenticated owner, wait for exact-head
completion/no unresolved findings and all checks. Actions-bot cannot authenticate to Codex. Copilot
account was ineligible; never claim it or CodeRabbit reviewed.

Preserve intentionally dirty M5Unified patch. No raw captures/NVS/WiFi/provider keys in Git. The old
experimental2026-11-20binary remains an archive, distinct from the newly flashed Relay binary.

## User feedback and responsive status — 2026-11-21

User confirmed Hebrew conversation worked, then reported a black screen. Device audio/task logs remained
alive; USB reset restored faces (user confirmed). Cause is not established; no speculative PMIC repair.
Added render frame/brightness/phase metadata. Latest app flashed/hash verified: Hebrew status badge
shows ready/hearing/thinking/speaking/error and immediate400ms touch acknowledgement. Brief VAD noise
returns to ready. Loggedrenderframes1449/brightness127, interruption, then new speech capture.
Final user confirmation of the badge/search/interrupt remains pending; completion notice is unarmed.

Generic Tavily snippets still yielded an old dollar quote in live testing. CurrentUSD/ILSquestions now
use BankofIsrael official API directly, validate rate/unit/currency/date (at most4daysold, not future),
and speak an exact representative quote with publicationdate, never relabeled a live market quote.
Live local lookup returned the20.11.2026publication. Other changing facts force search and receiveUTCdate.
71server tests pass, including stale/future/malformed/unavailable rate regressions.

Context and latency question: current turns are stateless and audio is a complete WAV before playback.
Short conversation memory and streaming remain follow-up work, not implemented features.

Live deployed revision voice-relay-00008-r6v/sourceb5bea5c passed device verifier and a synthetic Hebrew
USD/ILS v3 turn:200, official20.11.2026publication, spoken deterministic source/date,425204audio bytes.
Timings: STT237ms, officiallookup290ms, TTS835ms (1362msprovider stages; not device end-to-end latency).

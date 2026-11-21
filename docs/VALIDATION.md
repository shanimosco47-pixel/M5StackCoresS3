# Validation evidence

## Actual device (stable upstream v0.14.3; before custom build)

ESP32-S3 rev0.2, 16MB flash, 8MB Quad PSRAM; CoreS3 board auto-detected.
Flash writes verified by esptool hashes. Wi-Fi address acquisition, validated TLS,
WebSocket connection, session.created/session.updated and session-ready observed.
Microphone transcript and Hebrew assistant audio observed; user confirmed faces and speech.
NVS-only volume change preserved other settings; later NVS barge-in change hash-verified.
User confirmed immediate center-tap interruption and top-left mute.
Raw serial logs, NVS dumps and backup images are deliberately local because they may contain credentials.

## Custom source and build

Source: ciniml/stackchan-idf tag v0.14.3, commit 1d94b02990bf23da51a01164de1db74e54b9cab4.
ESP-IDF 5.5.5 build completed, including the one-shot announcement hook.
Application size 0x38d500 = 3,724,544 bytes; 29% of its 0x500000 app partition remains free.
Build ran on Windows with PYTHONUTF8=1 and PYTHONIOENCODING=utf-8.

Passed host checks:
- 13 Unicode subtitle ordering cases, including Hebrew/Latin/numbers/brackets/isolates.
- 228-glyph font coverage at 12px and 24px; glyph heights 16/22px and 29/40px panels.
- Web request/result parser cases: actual search marker, citations, malformed/empty arguments,
  bounds, incomplete results, HTTP errors, unsafe citation schemes and duplicate sources.
- Announcement payload: Hebrew text, audio modality, no tools, empty/oversized rejection.
- git diff --check.

The exact generated Hebrew bitmap preview was visually inspected; see images/hebrew-subtitle-preview.png.
This is a host preview, not a photo of the physical screen.

## Cloud API probes (separate from device validation)

Existing OpenAI key accepted an actual Realtime response with gpt-realtime.
gpt-realtime-2.1-mini accepted a GA WebSocket session update.
gpt-4.1 Responses web_search returned HTTP 200, completed search and cited results.
These probes do not establish device-side concurrent WebSocket + HTTPS memory/timing behavior.
The above probes precede the subsequently verified Groq/Tavily/Google pipeline below.

## Publication checks

Repository snapshot preserves tracked upstream source plus all custom source/tests/assets.
Third-party Git dependencies retain pinned SHAs through root .gitmodules.
M5Unified local changes are reproduced by the existing patches/m5unified.patch.
Machine-specific dependency path normalized in the publication copy only.
No build directories, private settings, account keys, original full flash or raw logs are published.

## Relay continuation — 2026-11-21

71server/provider/budget/admission tests and8actual-review-gate tests passed. Portable firmware core
compiled with Zig C++20 -Wall -Wextra -Werror and passed WAV, v3 framing, VAD, cancellation/epoch,
poll gaps/EOF/cached data and JSON depth regressions. GitHub CI now executes that core with g++.

Real cloud chain: synthetic Hebrew WAV → Groq Whisper → Groq openai/gpt-oss-120b → Tavily4sources →
Google Standard Hebrew WAV. Result200,12.8566875seconds/411458audio bytes. Timings: STT402ms,
LLM+search5636ms,TTS688ms. Separate live check after a new revision: missing/wrong device secret401,
same admitted UUID409and unchanged durable counter. verify_device.py passed with no provider calls.

Fresh full16MBbackup completed using four verified-size segments after a single full read failed
near its end; the failed read was never treated as a valid backup. Partition/exttabCRC/layout and NVS
CRCs/unrelated records verified. App/NVS flash hashes verified. Later TLS strategy fix flashed app only.
The source and image fingerprints are in artifacts/cores3-relay-2026-11-21.json.

User re-enabled hotspot after initial failed Wi-Fi attempts. CoreS3 then played actual responses;
latest stableRXbuild logged6.2seconds playback near nominal16kHz, ~41KBfree internal and4.55MBPSRAM
after the turn. User confirmation of final display/search/interrupt is still pending; no completion
announcement has been armed. Expected nonfatal WANT_READ/poll messages are not success/failure proof.

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

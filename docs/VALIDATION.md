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
Gemini/Tavily and the proposed Groq/OpenRouter/Azure relay have not been end-to-end tested.

## Publication checks

Repository snapshot preserves tracked upstream source plus all custom source/tests/assets.
Third-party Git dependencies retain pinned SHAs through root .gitmodules.
M5Unified local changes are reproduced by the existing patches/m5unified.patch.
Machine-specific dependency path normalized in the publication copy only.
No build directories, private settings, account keys, original full flash or raw logs are published.

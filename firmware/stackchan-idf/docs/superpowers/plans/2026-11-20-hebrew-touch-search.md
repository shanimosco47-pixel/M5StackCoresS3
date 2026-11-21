# Hebrew display, touch interruption, and internet search implementation plan

Goal: Preserve the working standalone Hebrew CoreS3 voice assistant while fixing subtitle rendering and touch interruption, and adding voice-requested internet search.

Architecture: Keep the existing GA Realtime client and hardware drivers. Add Hebrew-capable font and RTL preparation only at the subtitle boundary. Enable the existing barge-in setting, and expose an OpenAI Responses web_search call through the existing Realtime function result mechanism. Use device NVS credentials privately.

Authorization: User requested a working solution and delegated implementation choices; then reported squares, noninterrupting taps, and explicitly requested internet search. User confirmed top-left mute works. No further design approval needed.

Constraints: Back up before flashing; preserve volume 180, SSID, credentials, and other settings. Do not print credentials. Do not disable subtitles or switch the spoken language to work around missing Hebrew. No external relay/server. Source tag v0.14.3 with local focused changes, ESP-IDF 5.5.5, Quad PSRAM CoreS3 configuration. Search must return real sources or a clear error, not an invented result.

- [ ] Font and RTL: demonstrate missing Hebrew glyphs, add tested font coverage and bidi behavior for Hebrew/mixed digits/Latin punctuation, render preview.
- [ ] Touch: enable persisted bargein_en; retain separate top-left mute and top-right settings; verify center tap cancels audible reply.
- [ ] Search: bounded authenticated TLS Responses request, registered tool, Hebrew concise answer and source evidence; test success, malformed JSON, API errors, response limits, cancellation.
- [ ] Build with supported current Realtime model gpt-realtime-2.1-mini and verify account API access.
- [ ] Back up current settings, flash app with matching layout, retain recovery and NVS; verify image hashes and boot.
- [ ] On-device tests: session ready, readable Hebrew, tap interruption log and user confirmation, current web search call and spoken answer.
- [ ] Save deliverable firmware/source patch and usage notes with honest limitations.

Review focus: mixed-direction punctuation and numbers; firmware heap usage during concurrent TLS search; touch during Thinking/Speaking; search failure recovery; no exposure of API keys in logs or artifacts.

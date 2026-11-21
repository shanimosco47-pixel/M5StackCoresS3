# Active M5 project session

Last consolidated: 2026-11-21. This checkpoint supersedes earlier session history.

## Exact user instructions

- תעשה מה שצריך כדי לפתור את הבעיה ותסדר לי פתרון עובד
- מבחינתי תעשה כמה שיותר בעצמך
- אל תעצור
- תשמור את כל העבודה והתיעוד כאן — https://github.com/shanimosco47-pixel/M5StackCoresS3
- make sure there is a working github indipendent review working
- כשתסיים תשמיע צליל ב M5 או יותר טוב - שיגיד שהוא סיים את העדכון
- Accepted Google voice: בסדר, אפשר להתקדם עם זה, יש יותר טובים מזה, אבל בואו נתחיל עם זה.
- Approved Tavily: לאפשר חיפוש רגיל, בידיעה שהשאילתה נשלחת ל־Tavily
- Latest: מאד חשוב התגובתיות - שתהיה אינדיקציה שהוא מרגיש שאני נוגע במסך, ששהוא חושב וכו׳; שהוא מאזין
- Latest question: איך אפשר להגביר את מהירות התגובה שלו ולשפר את החוכמה והבנת ההקשרים

Goal: Hebrew CoreS3 assistant, faces/readable subtitles, touch interruption, actual internet search,
swappable cloud models. Announce completion on the device only after end-to-end physical validation.

## Current device

Checkout work/M5StackCoresS3, branch feature/cloud-voice-relay, PR1. Preserve intentionally dirty
M5Unified submodule: documented patch, no changed gitlink. COM5, CoreS3 ESP32-S3,16MBflash,8MBQuadPSRAM.
Relay provider3 is installed. Existing boot/recovery/exttab untouched, app-only0x1a0000.
Latest flashed app3738896bytes, SHA256deff20097d92b35fd8ebdd187c463851ae571a0ed4e4a028bca42d8bea3018c3.
Firmware subtree b6679ad0f40dd26c1ed8389620827e5bef341843. Artifact manifest records exact image/tree.
Volume180/bargein1/Wi-Fi preserved. Device URL/token provisioned from private NVS, CRC and all unrelated
records verified. No actual Wi-Fi/API/device secrets in image or changed source (four-value scan passed).
Fresh pre-relay16MBbackup in original outputs, SHA25605e81a5cadd65bc407166aed3182ee43d0ef3eb3cabeb0262cbaf3d4322ed36d.
Never publish NVS/full flash/raw serial logs. Four4MBbackup parts verified after a failed full read.

User re-enabled hotspot, then confirmed Hebrew conversation worked. Later reported black display.
Device remained alive, speaking; render task and heap remained active. USB reset restored faces,
explicitly confirmed by user: חזרו. Boot PMIC0x03=4A/0x90=BF; cause of earlier blackout NOT proven.
Added render frame/brightness/phase metadata every30s, no personal content. Latest loggedframes1449,
brightness127, Speaking; touch interrupted audio, then new speech started/stopped. User visual confirmation
of NEW Hebrew status badge and final search/interrupt still pending (they replied with a latency/context question).
Badge: מאזין / שומע אותך / חושב / מדבר / error; touch flashes400ms. Brief VAD noise returns to ready.
TLS dynamicRX async-header behavior implicated in prior INVALID_RECORD; per-connection staticRX selected
in PSRAM. Playback succeeded after mitigation; do not claim exact internal cause proven.
Completion update_notice flag is NOT armed.

## Cloud and actual verification

Project m5stack-515405, regioneurope-west1, servicevoice-relay. Billing linked; do not relink/relogin.
URL https://voice-relay-kdmuqgf46a-ew.a.run.app
Server sourceb5bea5c3161c477e6f8ef6bcf1cd8aa54f67ce78 adds official USD/ILS lookup; revision00008-r6v deployed100%.
Previous revision00007-grx/source6587163 passed verify_device.py: health200/ready200/missingsecret401,
authenticatedsilence204, no provider calls, durablequota required.
Chain Groq Whisper → Groq openai/gpt-oss-120b, lowreasoning/max1200 → optionalTavily → Googlehe-IL-Standard-A.
No Azure account required. OpenRouter remains selectable; optionalparallel_tool_calls excluded otherwise
compatible free endpoints; other reasoning models exhausted small budgets. No credits/subscriptions purchased.
Runtime attached Google identity (no JSON key), scoped SecretAccessor/ServiceUsageConsumer/DatastoreUser.
BuilderRunBuilder, no runtime secret/db access. Four provider/device secrets pinnedversion1; Azure empty.
IAM invocation public for unattended ESP32; voice/cancel/notice require strong X-Device-Secret in app.
Durable FirestoreCAS6/min,100/UTCday,3MreservedTTSchars/month,1000perturn,10minUUIDdedupe,failclosed.
Only counters/timestamps/opaqueUUIDs stored. No refunds. Restart replay409and unchangedcounter verified.
NativeCloudRun5ILScap verified; project5ILSalert NOT global hardcap. Other services/provider charges possible.
Groq data retention is not zero by default. Google TTS does not log text/audio. Tavily training use disclosed
and explicitly accepted; private_search_approved=true. Do not claim entire pipeline zero-retention.

Actual full cloudv3 chain200,4sources,12.8566875saudio; STT402ms/LLM+search5636ms/TTS688ms.
Device actualPOST200and playback observed. APIv3 magicM5R3+LEJSON/WAVlengths, metadata16KB/audio1.5MBbound.
/v3/notice fixed Hebrew completion phrase only; same auth/quota. Do not request until hardware accepted.
Freshness diagnosis: generic search returned an old Xe rate even with date instructions. Current dollar
questions now use fixed BankofIsrael HTTPS GET endpoint, validate currency/unit/finitepositivevalue,
aware timestamp no more than4daysold/no future, return deterministic Hebrew source/date/representativerate.
Never let model rewrite it as a live quote. Live local check obtained20.11.2026; no keys/personal text sent.
Weather/news/othercurrency requests force search; all LLM turns receive currentUTCdate and freshness rules.

## Verification and remaining work

71server/provider/quota/budget tests,8GitHubgate tests pass; portable firmware C++20/Werror tests pass.
Ruff/Bandit passed before latest official-rate change; rerun on final source. IDF5.5.5 build and app flash
hash verification passed. CI adds g++firmwarecore test and includes diagnostics staticchecks.
Actual GitHub Codex reviewed e601a44 clean; final firmware/current server still needs exact-head review.
Owner must post @codex review after finalpush; Actionsbot cannot authenticate. Gate verifies actual bot,
exacthead, completion and nofindings. CodeRabbit unavailable/Copilotineligible; do not claim either reviewed.
Subagent secondreview hit usagecap; don't claim completed. Root uses real GitHub independentreview.

1. Complete current Cloud deployment, run verify_device and official-rate live verification.
2. Finish honest docs/artifact, commit/push finalbundle, owner@codexreview; wait actual completed review
   and greenchecks, resolve findings and repeat as needed. Do not merge while physical checks pending.
3. User must confirm new badge/touch and search; do not treat previous question as yes.
4. After actual physical validation, fresh-readNVS, safely set only update_notice=1+CRC, flashNVSonly,
   reboot and verify fixed completionphrase playback. Do not announce taskdoneearly.
5. Context/latency: explained current turns are stateless and audio waits completeWAV. Short conversation
   memory then streaming are useful next changes; not implemented or promised complete. No speculative model switch.

Legacy deploy_private.ps1 resets settings/IAM to unconfiguredprivate staging. Do not rerun on live device mode.
verify_private.py also describes old IAM-only staging; use verify_device.py now.
CleanPythonvenv work/relay-venv; IDFpython ~/.espressif/python_env/idf5.5_py3.11_env/Scripts/python.exe.
IDF CMake regenerates absolute local m5gfx path in dependencies.lock; normalize to third_party/m5gfx after build.

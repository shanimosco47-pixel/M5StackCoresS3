# Hebrew Voice Assistant on M5Stack CoreS3: Design & Handoff

> **Audience:** a coding agent (Codex) taking over implementation.
> **Status:** architecture decided; v1 code drafted but **not yet run on hardware or against live APIs**; Phase 0 setup script written but **not yet executed**.
> Read sections 1 to 6 before writing code. Section 9 lists the rules you must follow.

---

## 1. Goal

A personal, hardware-based voice assistant on an **M5Stack CoreS3** (ESP32-S3, dual mics, speaker, touch screen, camera, 16MB flash, 8MB PSRAM). It replaces the official OpenAI Realtime demo firmware, which is too closed.

## 2. Requirements and constraints

| # | Requirement | Implication |
|---|---|---|
| R1 | Natural, high-quality **Hebrew** for both STT and TTS | Use cloud providers with strong Hebrew (Whisper large-v3, Azure neural he-IL voices). |
| R2 | **Swap LLMs freely** (Gemini, Claude, GPT, free models) **without reflashing** | Model choice must live in cloud config, never in firmware. |
| R3 | **No local model execution** at home | All AI runs in cloud services. |
| R4 | **No always-on home server** | Rules out Home Assistant as orchestrator. |
| R5 | **Cost: $0 to a few ILS per month**, pay-as-you-go, no commitments | Free tiers plus small prepaid credit; hard caps where possible. |
| R6 | **Privacy for personal data** (added later, see section 7) | Personal context only goes to providers that do not train on data. |
| R7 | Future extensibility: own actions, UI, personas, knowledge | Logic lives in the cloud relay, where it is easy to change. |

## 3. Decision

**Architecture: "thin device + serverless relay in the cloud".**

```
CoreS3 (thin client)          Google Cloud Run (relay, Python/FastAPI)
  record WAV  ── HTTPS POST ──▶  auth (X-Device-Secret)
                                 ├─ STT : Groq Whisper large-v3 (language=he)
                                 ├─ LLM : OpenRouter (model = env var LLM_MODEL)
                                 └─ TTS : Azure Speech he-IL-HilaNeural, PCM WAV
  play WAV    ◀── audio/wav ───┘
```

- The device only records, uploads, and plays. It knows one URL and one shared secret.
- All provider keys live in **Google Secret Manager**, never on the device.
- Switching LLM = changing `LLM_MODEL` on Cloud Run (new revision in seconds, no reflash).

## 4. Alternatives considered and why they were rejected

| Option | Why rejected |
|---|---|
| **ESPHome + Home Assistant** (device as satellite, HA as orchestrator) | Mature and stable, but needs an always-on box at home (violates R4). No Hebrew on-device wake word anyway. |
| **Direct-to-cloud firmware** (C++ on device calls every API) | API keys burned into firmware; every provider quirk lives in C++; switching providers requires reflashing (violates R2). Fine as a learning project, poor as a daily tool. |
| **Upgrade to ESP32-P4** (e.g. M5Stack Tab5) | Does not remove the need for an orchestrator; cannot run HA (no Linux) or quality Hebrew STT locally; no built-in Wi-Fi (needs companion ESP32-C6). Only worth it later for richer UI/video. |
| **xiaozhi-esp32 + xiaozhi-esp32-server** (open source, supports CoreS3) | Mature firmware, but defaults/docs are Chinese-oriented, uses persistent WebSocket + Opus (poor fit for Cloud Run billing), heavy deployment, and we would inherit foreign decisions. **Use as an idea source only** (UI, OTA, streaming), MIT licensed. |
| **Cloudflare Workers** | 10ms CPU limit on free plan is risky for audio handling; no standard Python runtime. |
| **Deno Deploy** | No credit card required (a plus), but JS/TS only. Kept as fallback. Cloud Run chosen; user has a GCP project with billing. |
| **Home-built relay from scratch vs fork** | From scratch: the relay is ~150 lines and firmware ~200 lines. Lean on **libraries** (M5Unified, ArduinoJson, OpenAI Python SDK against OpenRouter, pgvector), not on whole frameworks or forks. |

## 5. v1 contract and technical decisions

### 5.1 API contract (v1)

`POST /v1/turn`

| Item | Value |
|---|---|
| Request headers | `X-Device-Secret: <secret>`, `Content-Type: audio/wav` |
| Request body | WAV, PCM 16kHz, 16-bit, mono, max 2MB |
| `200` | Body is `audio/wav` (Azure `riff-16khz-16bit-mono-pcm`) |
| `204` | Nothing to say: audio < 0.5s, empty transcript, or empty LLM answer |
| `401` | Bad secret |
| `413` | Body too large |
| `502` | Upstream failure; header `X-Error-Stage: stt\|llm\|tts` |

`GET /healthz` returns `{"ok": true}`.

**Planned change (v2):** move to a structured response (JSON with text, actions, profile state, plus audio). Version it as `/v2/turn`; do not break `/v1/turn`.

### 5.2 Decisions with rationale

| Decision | Rationale |
|---|---|
| **WAV both directions in v1** (not MP3 back) | M5Unified plays WAV natively (`M5.Speaker.playWav`); MP3 needs an extra decoder lib. A 15s reply is ~480KB, trivial over Wi-Fi. Latency is dominated by the STT, LLM, TTS chain, not by compression. MP3/streaming are later optimizations. |
| **Mic and speaker never active together** | On CoreS3 they share the I2S bus. Always `M5.Mic.end()` before `M5.Speaker.begin()` and vice versa. |
| **Fixed PSRAM buffers allocated once in `setup()`** | Avoids dependence on `Content-Length`, avoids fragmentation. Response buffer 1.5MB (~47s audio). Read until stream ends, buffer full, or 5s stall. Check `ps_malloc` results; fail loudly. |
| **No transcript/answer in response headers** | URL-encoded Hebrew inflates headers (6 bytes/char) and `HTTPClient` ignores headers not registered via `collectHeaders()`. Log text on the server instead (Cloud Run logs). Screen text comes later via the v2 JSON contract. |
| **Auth via `X-Device-Secret`** | Constant-time compare (`hmac.compare_digest` on bytes). HTTPS only. Rotate if device is lost. |
| **Device-side and server-side filtering of short audio (< 0.5s)** | Saves calls; Whisper hallucinates text on silence/noise (e.g. "thank you", subtitle credits). |
| **Guard empty LLM content** | Some models (especially reasoning models) return `content: null` or spend `max_tokens` on reasoning. Return 204 and log. Prefer non-reasoning models in v1. |
| **Strip Markdown before TTS** | Otherwise TTS reads asterisks/hashes. System prompt also asks for short spoken answers, no lists, no emoji. |
| **Per-stage error logging and timings** | Without it, debugging is guesswork. |
| **Status shown on screen in English** | The built-in font has no Hebrew glyphs and no RTL. Hebrew UI is a separate milestone (VLW font + RTL reversal). |
| **`client.setInsecure()` only in development** | Production must pin a root CA via `setCACert`. |
| **Wi-Fi reconnect before each request** | Device is long-running; connections drop. |
| **Cloud Run: `min-instances=0`, `max-instances=1`** | Stays in free tier and caps blast radius. Cost: 1 to 3s cold start after idle. |
| **Dedicated runtime service account** with access to the 4 secrets only | Least privilege. |

### 5.3 Expected latency (v1, non-streaming)

STT 0.5 to 1s, LLM 1 to 3s, TTS 0.5 to 1s, plus cold start when idle. Realistic total: **2 to 5 seconds**. The main future improvement is sentence-level streaming, not audio compression.

## 6. Providers, cost, and guardrails

| Component | Provider | Cost model | Guardrail |
|---|---|---|---|
| Relay | Google Cloud Run | Free tier (requires billing account) | Budget alert at $5; `max-instances=1` |
| Secrets | Google Secret Manager | Free tier | Least-privilege SA |
| STT | Groq `whisper-large-v3` | Free tier | Rate limits; verify data-use terms |
| LLM | OpenRouter | Prepaid credit (e.g. $5) | Credit runs out, service stops; no overage |
| TTS | Azure Speech, F0 tier | Free monthly quota | F0 throttles instead of charging |
| Knowledge store (v3+) | Supabase (Postgres + pgvector) | Free tier | Free projects pause after ~1 week of inactivity |

Estimated LLM spend for the private path (about 30 turns/day, about 3k tokens/turn, fast model): roughly $1 to $2/month. **All prices and quotas change; verify current numbers before relying on them.**

## 7. Privacy model (decided)

Some free tiers (parts of the Gemini API free tier, some free OpenRouter models) may use request content to improve models.

**Rule: route by data, not by profile.**
- Any turn that includes personal context (persona, memory, personal documents, calendar) goes **only** to the paid/approved path: OpenRouter with training-on-data providers **disabled** and zero-retention providers preferred.
- A separate **"playground" profile** carries **no** persona, memory, or personal documents, and may use any model including free ones. This preserves the model-experimentation goal.
- Embeddings of personal documents also go through the paid path (one-time indexing costs cents).
- Implementation: each profile has `private: true|false`; private profiles load personal context and are restricted to an allowlist of models/providers.
- Option "do not store sensitive data at all" was explicitly rejected by the user.

## 8. Roadmap

| Version | Scope | Notes |
|---|---|---|
| **v1** | Push-to-talk turn: record, STT, LLM, TTS, play | Code in appendix; needs real testing. |
| **v1.x** | OTA firmware updates; root CA pinning | OTA is a prerequisite for every later device feature. |
| **v2** | External persona file (Cloud Storage/Firestore, editable without redeploy); conversation history; date/time/location injected; **structured JSON response contract**; profiles with `private` flag | Device change: send `profile` id; parse JSON. |
| **v3** | Tool-calling loop on the server; learning memory (`remember`/`recall`) | Use OpenAI Python SDK against OpenRouter. Not all free models do tool calling reliably. Show "Searching..." on screen during tool calls. |
| **v4** | Live tools: calendar, weather, shopping/task lists, Telegram bot, webhooks; web search (likely paid) | Server only. |
| **v5** | RAG over professional and personal documents (Drive, Notion, PDFs) with nightly sync (Cloud Scheduler); Supabase pgvector | Retrieve 3 to 5 chunks; instruct model to compress retrieved text into 2 to 3 spoken sentences. Validate Hebrew retrieval quality on real data. |
| Later | Sentence-level streaming TTS; on-device wake word; simple animated eyes (M5GFX sprites, not full LVGL); camera "snap and ask" (VGA 0.3MP: scene questions yes, small labels no); proximity sensor as secondary trigger only (range of a few cm); settings web page on Cloud Run; morning briefing via device polling; local timers driven by LLM actions | Keep logic in the cloud; device stays thin. |

### Knowledge architecture (v2 to v5)

One context-assembly layer on the server:

- **Always in prompt** (keep to a few thousand tokens): persona and rules, stable personal facts, active profile rules, date/time/location.
- **On demand via tools**: `search_knowledge` (RAG), `remember`/`recall`, `get_calendar`, `get_weather`, `web_search`.

Rationale: simple questions do not pay retrieval latency or tokens.

## 9. Rules for the implementing agent

1. **Never put secrets in code, logs, commits, or chat.** Keys live in Secret Manager; device secret lives in an untracked `secrets.h`.
2. **Keep the device thin.** New features belong in the relay unless they are inherently local (audio I/O, display, sensors, timers).
3. **Do not break `/v1/turn`.** Introduce new contracts under a new version.
4. **Verify library APIs against current versions** (M5Unified `Mic.record`, `Speaker.playWav`, `Touch`; arduino-esp32 `HTTPClient`; provider endpoints and model IDs). The appendix code was written from knowledge, not compiled.
5. **Respect the privacy rule in section 7** when adding any feature that touches personal data.
6. **Hebrew specifics:** STT `language=he` (switch to auto-detect only for a translator profile); TTS via SSML with `xml:lang='he-IL'`; spoken style, no Markdown; screen text needs a Hebrew font and RTL handling.
7. **Test in this order:** server alone with `curl` and a real WAV file, then device recording/playback offline, then end to end. Log per-stage timings.
8. **Cost safety:** keep `max-instances=1`, prepaid credit on OpenRouter, Azure F0; never add a provider without a spending cap or a clear free tier.

## 10. Open items and unverified assumptions

- Phase 0 script (appendix C) has not been run. It may need an extra Cloud Build permission on newer projects (`roles/run.builder` on the build service account).
- Whether the Cloud Run free tier applies in the chosen region (`europe-west1` in the deploy command).
- CoreS3 mic gain level (`magnification`) needs a listening test.
- Whether M5Unified keeps speaker volume across `Speaker.end()`/`begin()` (code re-applies it each time to be safe).
- Data-use terms for Groq free tier and Azure F0 need confirmation.
- OpenRouter key-check endpoint used in the setup script (`/api/v1/auth/key`) may have moved; a warning there does not necessarily mean a bad key.

---

## Appendix A: Server (`server/`)

### `requirements.txt`
```text
fastapi==0.115.6
uvicorn==0.32.1
httpx==0.28.1
```

### `Dockerfile`
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
```

### `main.py`
```python
import os
import re
import hmac
import time
import logging
from xml.sax.saxutils import escape

import httpx
from fastapi import FastAPI, Request, Header, Response

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("relay")

DEVICE_SECRET = os.environ["DEVICE_SECRET"].encode()
GROQ_KEY = os.environ["GROQ_API_KEY"]
OPENROUTER_KEY = os.environ["OPENROUTER_API_KEY"]
AZURE_KEY = os.environ["AZURE_SPEECH_KEY"]
AZURE_REGION = os.environ["AZURE_REGION"]
MODEL = os.environ.get("LLM_MODEL", "google/gemini-2.5-flash")
VOICE = os.environ.get("TTS_VOICE", "he-IL-HilaNeural")
SYSTEM = os.environ.get(
    "SYSTEM_PROMPT",
    "אתה עוזר קולי. ענה בעברית, בקצרה ובשפה מדוברת. "
    "בלי רשימות, בלי Markdown ובלי אימוג'י.",
)

MAX_BODY = 2_000_000          # about 60s of WAV
MIN_BODY = 44 + 16_000        # 0.5s at 16kHz/16-bit
MD_CHARS = re.compile(r"[*#_`>|~]")

app = FastAPI()


def check(r: httpx.Response, stage: str) -> None:
    if r.is_error:
        log.error("stage=%s status=%s body=%s", stage, r.status_code, r.text[:500])
        r.raise_for_status()


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.post("/v1/turn")
async def turn(request: Request, x_device_secret: str = Header(default="")):
    if not hmac.compare_digest(x_device_secret.encode(), DEVICE_SECRET):
        return Response(status_code=401)

    wav = await request.body()
    if len(wav) > MAX_BODY:
        return Response(status_code=413)
    if len(wav) < MIN_BODY:
        return Response(status_code=204)

    stage = "stt"
    t0 = time.perf_counter()
    timings = {}
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            # 1. STT
            r = await c.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {GROQ_KEY}"},
                files={"file": ("in.wav", wav, "audio/wav")},
                data={"model": "whisper-large-v3", "language": "he"},
            )
            check(r, stage)
            text = (r.json().get("text") or "").strip()
            timings["stt"] = time.perf_counter() - t0
            if not text:
                log.info("empty transcript")
                return Response(status_code=204)

            # 2. LLM
            stage = "llm"
            t1 = time.perf_counter()
            r = await c.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
                json={
                    "model": MODEL,
                    "max_tokens": 300,
                    "messages": [
                        {"role": "system", "content": SYSTEM},
                        {"role": "user", "content": text},
                    ],
                },
            )
            check(r, stage)
            choices = r.json().get("choices") or []
            msg = choices[0].get("message", {}) if choices else {}
            answer = MD_CHARS.sub("", (msg.get("content") or "")).strip()
            timings["llm"] = time.perf_counter() - t1
            if not answer:
                log.warning("empty LLM answer, model=%s", MODEL)
                return Response(status_code=204)

            # 3. TTS
            stage = "tts"
            t2 = time.perf_counter()
            ssml = (
                "<speak version='1.0' xml:lang='he-IL'>"
                f"<voice name='{VOICE}'>{escape(answer)}</voice></speak>"
            )
            r = await c.post(
                f"https://{AZURE_REGION}.tts.speech.microsoft.com/cognitiveservices/v1",
                headers={
                    "Ocp-Apim-Subscription-Key": AZURE_KEY,
                    "Content-Type": "application/ssml+xml",
                    "X-Microsoft-OutputFormat": "riff-16khz-16bit-mono-pcm",
                    "User-Agent": "voice-relay",
                },
                content=ssml.encode("utf-8"),
            )
            check(r, stage)
            timings["tts"] = time.perf_counter() - t2

    except (httpx.HTTPError, ValueError, KeyError, IndexError) as e:
        log.error("stage=%s failed: %r", stage, e)
        return Response(status_code=502, headers={"X-Error-Stage": stage})

    log.info(
        "STT=%r | LLM(%s)=%r | t=%s total=%.2fs",
        text, MODEL, answer,
        {k: round(v, 2) for k, v in timings.items()},
        time.perf_counter() - t0,
    )
    return Response(r.content, media_type="audio/wav")
```

### Deploy (from `server/`, after Phase 0)
```bash
source ~/voice-relay/config.env
gcloud run deploy voice-relay --source . --region europe-west1 \
  --service-account "$SA_EMAIL" \
  --allow-unauthenticated --max-instances 1 --min-instances 0 \
  --set-env-vars AZURE_REGION=$AZURE_REGION,LLM_MODEL=google/gemini-2.5-flash \
  --set-secrets DEVICE_SECRET=device-secret:latest,GROQ_API_KEY=groq-key:latest,OPENROUTER_API_KEY=openrouter-key:latest,AZURE_SPEECH_KEY=azure-speech-key:latest
```

### Smoke test
```bash
ffmpeg -i recording.m4a -ar 16000 -ac 1 -sample_fmt s16 test.wav
curl -X POST "$URL/v1/turn" -H "X-Device-Secret: $SECRET" \
  -H "Content-Type: audio/wav" --data-binary @test.wav -o reply.wav
```

## Appendix B: Firmware (`firmware/`)

Arduino IDE: install **M5Unified**; Board **M5CoreS3**; **Tools > PSRAM: OPI PSRAM**.

### `secrets.h` (untracked; add to `.gitignore`)
```cpp
#pragma once
#define WIFI_SSID     "your-wifi"
#define WIFI_PASS     "your-password"
#define RELAY_URL     "https://voice-relay-xxxxx.a.run.app/v1/turn"
#define DEVICE_SECRET "value from: gcloud secrets versions access latest --secret=device-secret"
```

### `voice_assistant.ino`
```cpp
#include <M5Unified.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include "secrets.h"

constexpr uint32_t SR          = 16000;
constexpr size_t   MAX_SAMPLES = SR * 10;      // 10 s
constexpr size_t   MIN_SAMPLES = SR / 2;       // 0.5 s
constexpr size_t   CHUNK       = 1600;         // 100 ms
constexpr size_t   RESP_MAX    = 1500000;      // about 47 s of audio
constexpr uint8_t  VOLUME      = 160;

uint8_t* wavBuf  = nullptr;   // 44-byte header + samples
uint8_t* respBuf = nullptr;

// ---------- UI ----------
void showStatus(const char* msg, uint16_t color = TFT_WHITE) {
  M5.Display.fillScreen(TFT_BLACK);
  M5.Display.setTextColor(color);
  M5.Display.setTextSize(2);
  M5.Display.setCursor(10, 100);
  M5.Display.println(msg);
}

void fatal(const char* msg) {
  showStatus(msg, TFT_RED);
  while (true) delay(1000);
}

// ---------- WiFi ----------
bool ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) return true;
  showStatus("Connecting WiFi...", TFT_YELLOW);
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 15000) delay(200);
  return WiFi.status() == WL_CONNECTED;
}

// ---------- Audio ----------
void writeWavHeader(uint8_t* h, uint32_t dataBytes) {
  uint32_t v; uint16_t s;
  memcpy(h, "RIFF", 4);         v = 36 + dataBytes; memcpy(h + 4, &v, 4);
  memcpy(h + 8, "WAVEfmt ", 8); v = 16;             memcpy(h + 16, &v, 4);
  s = 1;  memcpy(h + 20, &s, 2);                    // PCM
  s = 1;  memcpy(h + 22, &s, 2);                    // mono
  v = SR; memcpy(h + 24, &v, 4);
  v = SR * 2; memcpy(h + 28, &v, 4);                // byte rate
  s = 2;  memcpy(h + 32, &s, 2);                    // block align
  s = 16; memcpy(h + 34, &s, 2);                    // bits per sample
  memcpy(h + 36, "data", 4); memcpy(h + 40, &dataBytes, 4);
}

size_t recordWhilePressed() {
  int16_t* samples = (int16_t*)(wavBuf + 44);
  size_t n = 0;
  while (M5.Touch.getDetail().isPressed() && n + CHUNK <= MAX_SAMPLES) {
    if (M5.Mic.record(samples + n, CHUNK, SR)) n += CHUNK;
    M5.update();
  }
  while (M5.Mic.isRecording()) delay(1);
  return n;
}

void playResponse(size_t len) {
  M5.Mic.end();                 // mic and speaker share I2S
  M5.Speaker.begin();
  M5.Speaker.setVolume(VOLUME);
  M5.Speaker.playWav(respBuf, len);
  while (M5.Speaker.isPlaying()) delay(10);
  M5.Speaker.end();
  M5.Mic.begin();
}

// ---------- HTTP ----------
size_t readBody(HTTPClient& http) {
  WiFiClient* st = http.getStreamPtr();
  size_t got = 0;
  uint32_t last = millis();
  while (got < RESP_MAX && (http.connected() || st->available())) {
    int a = st->available();
    if (a > 0) {
      got += st->readBytes(respBuf + got, min((size_t)a, RESP_MAX - got));
      last = millis();
    } else if (millis() - last > 5000) {
      break;                    // stalled stream
    } else {
      delay(1);
    }
  }
  return got;
}

// ---------- Main ----------
void setup() {
  auto cfg = M5.config();
  M5.begin(cfg);

  wavBuf  = (uint8_t*)ps_malloc(44 + MAX_SAMPLES * 2);
  respBuf = (uint8_t*)ps_malloc(RESP_MAX);
  if (!wavBuf || !respBuf) fatal("PSRAM alloc failed.\nEnable OPI PSRAM.");

  auto mc = M5.Mic.config();
  mc.sample_rate = SR;
  // mc.magnification = 16;     // raise if recordings are too quiet
  M5.Mic.config(mc);

  if (!ensureWiFi()) fatal("WiFi failed");
  M5.Speaker.end();
  M5.Mic.begin();
  showStatus("Ready.\nHold to talk.");
}

void loop() {
  M5.update();
  if (!M5.Touch.getDetail().isPressed()) { delay(10); return; }

  showStatus("Listening...", TFT_GREEN);
  size_t n = recordWhilePressed();
  if (n < MIN_SAMPLES) { showStatus("Too short.\nHold to talk."); return; }
  writeWavHeader(wavBuf, n * 2);

  if (!ensureWiFi()) { showStatus("WiFi failed", TFT_RED); return; }
  showStatus("Thinking...", TFT_CYAN);

  WiFiClientSecure client;
  client.setInsecure();         // DEV ONLY. Production: client.setCACert(rootCA)
  HTTPClient http;
  if (!http.begin(client, RELAY_URL)) { showStatus("HTTP begin failed", TFT_RED); return; }
  http.setConnectTimeout(10000);
  http.setTimeout(30000);
  http.addHeader("X-Device-Secret", DEVICE_SECRET);
  http.addHeader("Content-Type", "audio/wav");
  const char* keys[] = {"X-Error-Stage"};
  http.collectHeaders(keys, 1);

  int code = http.POST(wavBuf, 44 + n * 2);
  size_t len = 0;
  String errStage;
  if (code == 200) len = readBody(http);
  else errStage = http.header("X-Error-Stage");
  http.end();                   // close before playback

  if (code == 200 && len > 44) {
    showStatus("Speaking...", TFT_MAGENTA);
    playResponse(len);
    showStatus("Ready.\nHold to talk.");
  } else if (code == 204) {
    showStatus("Didn't catch that.\nHold to talk.", TFT_YELLOW);
  } else {
    char buf[64];
    snprintf(buf, sizeof(buf), "Error %d %s", code, errStage.c_str());
    showStatus(buf, TFT_RED);
  }
}
```

## Appendix C: Phase 0 setup script (`scripts/setup.sh`, run in Google Cloud Shell)

Idempotent. Enables APIs, creates a least-privilege runtime service account, prompts for keys with hidden input and validates each against its provider, stores them in Secret Manager, generates the device secret, grants permissions, writes `~/voice-relay/config.env`.

```bash
#!/usr/bin/env bash
# Voice relay: Phase 0 setup. Idempotent, safe to re-run.
set -euo pipefail

say()  { printf '\n\033[1;36m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32mOK\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!!\033[0m %s\n' "$*"; }

ask_secret() {
  local v
  while true; do
    read -rsp "  $1: " v </dev/tty; echo >&2
    [ -n "$v" ] && { printf '%s' "$v"; return; }
    echo "  Empty, try again." >&2
  done
}

put_secret() {
  local name=$1 value=$2
  if gcloud secrets describe "$name" >/dev/null 2>&1; then
    printf '%s' "$value" | gcloud secrets versions add "$name" --data-file=- >/dev/null
    ok "updated secret: $name"
  else
    printf '%s' "$value" | gcloud secrets create "$name" --data-file=- --replication-policy=automatic >/dev/null
    ok "created secret: $name"
  fi
}

http_code() { curl -s -o /dev/null -w '%{http_code}' "$@" || echo 000; }

# 1. Project
say "1/6 Project"
DEFAULT_PROJECT="$(gcloud config get-value project 2>/dev/null || true)"
read -rp "  GCP project ID [${DEFAULT_PROJECT}]: " P </dev/tty
PROJECT_ID="${P:-$DEFAULT_PROJECT}"
[ -z "$PROJECT_ID" ] && { echo "No project ID given."; exit 1; }
gcloud config set project "$PROJECT_ID" >/dev/null
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
ok "project: $PROJECT_ID ($PROJECT_NUMBER)"

# 2. APIs
say "2/6 Enabling APIs (can take a minute)"
gcloud services enable run.googleapis.com secretmanager.googleapis.com \
  cloudbuild.googleapis.com artifactregistry.googleapis.com iam.googleapis.com
ok "APIs enabled"

# 3. Runtime service account (least privilege)
say "3/6 Service account"
SA_NAME=voice-relay-sa
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "$SA_EMAIL" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SA_NAME" --display-name="Voice relay runtime" >/dev/null
fi
ok "$SA_EMAIL"

# 4. API keys (input is hidden)
say "4/6 API keys (paste each one, nothing will be shown)"
GROQ_KEY="$(ask_secret 'Groq API key')"
c=$(http_code https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_KEY")
[ "$c" = 200 ] && ok "Groq key works" || warn "Groq returned HTTP $c, check the key"

OR_KEY="$(ask_secret 'OpenRouter API key')"
c=$(http_code https://openrouter.ai/api/v1/auth/key -H "Authorization: Bearer $OR_KEY")
[ "$c" = 200 ] && ok "OpenRouter key works" || warn "OpenRouter returned HTTP $c, check the key"

read -rp "  Azure Speech region [westeurope]: " R </dev/tty
AZURE_REGION="${R:-westeurope}"
AZ_KEY="$(ask_secret 'Azure Speech key')"
c=$(http_code "https://${AZURE_REGION}.tts.speech.microsoft.com/cognitiveservices/voices/list" -H "Ocp-Apim-Subscription-Key: $AZ_KEY")
[ "$c" = 200 ] && ok "Azure key works" || warn "Azure returned HTTP $c, check key and region"

# 5. Secrets
say "5/6 Secret Manager"
put_secret groq-key "$GROQ_KEY"
put_secret openrouter-key "$OR_KEY"
put_secret azure-speech-key "$AZ_KEY"
if gcloud secrets describe device-secret >/dev/null 2>&1; then
  ok "device-secret already exists, keeping it"
else
  put_secret device-secret "$(openssl rand -hex 32)"
fi
unset GROQ_KEY OR_KEY AZ_KEY

# 6. Permissions
say "6/6 Permissions"
for s in device-secret groq-key openrouter-key azure-speech-key; do
  gcloud secrets add-iam-policy-binding "$s" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role=roles/secretmanager.secretAccessor >/dev/null
done
ok "runtime account can read the 4 secrets"

COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
if gcloud iam service-accounts describe "$COMPUTE_SA" >/dev/null 2>&1; then
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${COMPUTE_SA}" --role=roles/run.builder \
    --condition=None >/dev/null 2>&1 \
    && ok "build account can build from source" \
    || warn "could not grant build role (handle in Phase 1 if needed)"
fi

mkdir -p ~/voice-relay
cat > ~/voice-relay/config.env <<CFG
PROJECT_ID=${PROJECT_ID}
AZURE_REGION=${AZURE_REGION}
SA_EMAIL=${SA_EMAIL}
CFG

say "Done. Phase 0 complete."
echo "  Config saved to ~/voice-relay/config.env"
echo "  To view the device secret later (for secrets.h):"
echo "    gcloud secrets versions access latest --secret=device-secret"
echo "  Note: new permissions can take 1-2 minutes to propagate."
```

## Suggested repository layout

```
voice-assistant/
├── README.md                 # this document
├── server/
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── firmware/
│   ├── voice_assistant.ino
│   └── secrets.h.example     # real secrets.h is gitignored
├── scripts/
│   └── setup.sh
└── .gitignore                # firmware/secrets.h, *.wav, .env*
```

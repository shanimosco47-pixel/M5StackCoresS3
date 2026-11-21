# Build and recovery

## Source layout

`firmware/stackchan-idf/` is a source snapshot of upstream v0.14.3 with the custom
Hebrew subtitles, OpenAI search, completion announcement and Windows CMake path fix.
Upstream documentation, licenses and source are retained. The upstream Git history is not imported;
the base commit and submodule pins are recorded in UPSTREAM.md and root .gitmodules.

Clone with dependencies:

```sh
git clone --recurse-submodules https://github.com/shanimosco47-pixel/M5StackCoresS3.git
cd M5StackCoresS3/firmware/stackchan-idf
bash tools/apply-m5-patches.sh
```

Use ESP-IDF 5.5.5. Activate its environment first. For the matching CoreS3 configuration:

```sh
idf.py -B build-cores3 -DSDKCONFIG=build-cores3/sdkconfig '-DSDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.defaults.esp32s3;sdkconfig.defaults.cores3' build
```

On Windows set PYTHONUTF8=1 and PYTHONIOENCODING=utf-8 before building.
This CoreS3 uses Quad PSRAM. The source default voice model is gpt-realtime-2.1-mini;
the experimental search implementation uses OpenAI Responses with gpt-4.1. Neither is a free-only configuration.
Models and availability must be checked before deploying. No credentials are included.

## Experimental binary

`artifacts/cores3-experimental-2026-11-20.bin` is APP ONLY, built successfully but
NOT flashed or hardware-validated. See manifest.json for SHA256 and prerequisites.
It requires the matching v0.14.3 16MB CoreS3 partition/recovery layout already installed.
Its app address is **0x1a0000**, never 0x0. Do not use it as a merged M5Burner image.
Before any future flash, take a fresh local backup and verify the existing partition layout.
No flash should be implied by the repository upload.

## Private settings

NVS namespace stackchan_cfg stores credentials and device settings separately from the app.
The tested device currently has spk_vol_pct=180 and bargein_en=1.
Do not replace its NVS with example/default settings. Do not commit NVS dumps or generated settings CSV files.
The update_notice u8 flag should only be armed after final end-to-end validation;
it is consumed before sending the one-time Hebrew completion announcement.

## Relay build and installation — 2026-11-21

The new Relay application was built and flashed at0x1a0000after a fresh complete16MBbackup,
SHA25605e81a5cadd65bc407166aed3182ee43d0ef3eb3cabeb0262cbaf3d4322ed36d. Both actual extension
table copies had valid CRCs and main0x1a0000/0x500000. No bootloader/partition/recovery/exttab write.
The new image and source-tree fingerprint are in artifacts/cores3-relay-2026-11-21.json.
The older experimental image/manifest above remain historical and were not used for this flash.

Provider::Relay=3 is append-only. NVS relay_url/relay_token configure the verified HTTPS base URL
and a random device secret; cloud provider keys stay server-side. Volume180/barge-in1/Wi-Fi preserved.
tools/diagnostics/provision_relay.py prepares a new private NVS file from a fresh backup using the
installed IDF parser, validates all CRCs and byte-preserves unrelated records, including Wi-Fi blobs.
It does not flash; output inside the repository and overwriting an existing file are refused.
The helper appends only new Relay settings and refuses to replace existing Relay credentials;
later changes use the device settings API. Do not publish any NVS file or full backup.

Independent review exposed delayed relisten and unbounded JSON recursion; host regressions cover
the fixed gate/reader/depth behavior. Hardware exposed intermittent TLS INVALID_RECORD with dynamic
RX polling. The selected per-connection HTTP_TLS_DYN_BUF_RX_STATIC strategy retains receive state;
hardware playback was observed afterwards. Do not replace verified TLS with an insecure workaround.

## Original recovery archive

The original full 16MB flash backup is retained locally by the user and excluded from Git.
SHA256: A674BD19B7B8EF728BDBCA92C3029CABBFABA18160D928173009484D06CC5B5B.
It includes credentials. Restoring it also restores the original obsolete OpenAI demo and its incompatibility.
Normal recovery should prefer the verified stable upstream release and preserve current settings.
Choose the current serial port at recovery time; do not assume the old COM port is unchanged.

Latest responsive-status image:3738896bytes, SHA256deff20097d92b35fd8ebdd187c463851ae571a0ed4e4a028bca42d8bea3018c3.
App-only flash verified. A reported black display recovered after USB reset; PMIC boot registers were
healthy. Root cause remains unknown. Render frames/brightness/phase metadata now helps diagnose recurrence.

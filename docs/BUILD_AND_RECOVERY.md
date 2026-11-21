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

## Recovery

The original full 16MB flash backup is retained locally by the user and excluded from Git.
SHA256: A674BD19B7B8EF728BDBCA92C3029CABBFABA18160D928173009484D06CC5B5B.
It includes credentials. Restoring it also restores the original obsolete OpenAI demo and its incompatibility.
Normal recovery should prefer the verified stable upstream release and preserve current settings.
Choose the current serial port at recovery time; do not assume the old COM port is unchanged.

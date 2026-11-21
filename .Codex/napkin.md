# Napkin Runbook

## Curation Rules
- Keep recurring, high-value guidance only, highest priority first.
- Each entry includes a date and a concrete "Do instead" action.
- Maximum 10 entries per category.

## Execution and Validation
1. **[2026-11-21] Distinguish a successful build from a device update.**
   Do instead: read docs/STATUS.md, verify the actual device and record hardware validation separately.
2. **[2026-11-21] Preserve the known working CoreS3 layout and settings.**
   Do instead: take a fresh private backup, use Quad PSRAM, and verify partitions before any write. The archived experimental binary is app-only at 0x1a0000.

## Shell and Build Reliability
1. **[2026-11-21] Windows IDF tools need UTF-8.**
   Do instead: set PYTHONUTF8=1 and PYTHONIOENCODING=utf-8 before activating ESP-IDF 5.5.5.
2. **[2026-11-21] Dependencies are pinned at the repository root.**
   Do instead: initialize root Git submodules, then apply firmware/stackchan-idf/tools/apply-m5-patches.sh before building.

## Data and User Preferences
1. **[2026-11-21] The repository is public.**
   Do instead: exclude API keys, Wi-Fi details, NVS/flash backups and raw logs; scan selected files before publishing.
2. **[2026-11-21] Preserve Hebrew speech, readable subtitles and touch interruption.**
   Do instead: add the relay as a backend to the current firmware and test mixed Hebrew/Latin/numbers plus physical interruption.

The two generated 1-bit fonts cover Hebrew letters and final forms, Hebrew
punctuation, ASCII, Latin accents, curly quotes, en/em dashes, ellipsis and
the shekel sign. Font selection changes only for subtitles containing Hebrew;
other subtitles keep the existing Japanese font.

Source: Noto Sans Hebrew from
https://github.com/google/fonts/tree/main/ofl/notosanshebrew
(`NotoSansHebrew[wdth,wght].ttf`). The generated file records its source SHA-256.
The font data is licensed under the SIL Open Font License in OFL.txt.

Regenerate with Pillow and fonttools installed:

    python generate.py /path/to/NotoSansHebrew.ttf

No TTF parser or font file is required on the device. All glyph data is const
and remains in flash. Text is reordered once when set, using SheenBidi's Unicode
Bidirectional Algorithm; numbers, Latin runs, isolates and bracket mirroring are
preserved. Long RTL paragraphs scroll left-to-right, showing their beginning
first. M5GFX cannot position combining marks, so the display omits Hebrew niqqud
and cantillation; the original text sent to speech is unchanged.

Host validation:

    cmake -S ../test/host -B /path/to/build
    cmake --build /path/to/build
    ctest --test-dir /path/to/build
    python ../test/host/test_font.py

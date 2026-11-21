// SPDX-FileCopyrightText: 2026 Kenta IDA <fuga@fugafuga.org>
// SPDX-License-Identifier: BSL-1.0
#include "subtitle_text.hpp"

#include <vector>
#include <SheenBidi/SheenBidi.h>

namespace stackchan::avatar::internal {
namespace {
void append_utf8(std::string& out, SBCodepoint c) {
    if (c < 0x80) {
        out.push_back(static_cast<char>(c));
    } else if (c < 0x800) {
        out.push_back(static_cast<char>(0xC0 | (c >> 6)));
        out.push_back(static_cast<char>(0x80 | (c & 63)));
    } else if (c < 0x10000) {
        out.push_back(static_cast<char>(0xE0 | (c >> 12)));
        out.push_back(static_cast<char>(0x80 | ((c >> 6) & 63)));
        out.push_back(static_cast<char>(0x80 | (c & 63)));
    } else {
        out.push_back(static_cast<char>(0xF0 | (c >> 18)));
        out.push_back(static_cast<char>(0x80 | ((c >> 12) & 63)));
        out.push_back(static_cast<char>(0x80 | ((c >> 6) & 63)));
        out.push_back(static_cast<char>(0x80 | (c & 63)));
    }
}

bool invisible(SBCodepoint c) {
    // M5GFX has no combining-mark positioning. Display Hebrew without niqqud
    // or cantillation rather than painting detached marks / missing glyphs.
    return (c >= 0x591 && c <= 0x5BD) || c == 0x5BF || c == 0x5C1 || c == 0x5C2 || c == 0x5C4 || c == 0x5C5 ||
           c == 0x5C7 || c == 0x200E || c == 0x200F || (c >= 0x202A && c <= 0x202E) || (c >= 0x2066 && c <= 0x2069) ||
           c == 0xFEFF;
}
} // namespace

SubtitleText prepare_subtitle(std::string_view logical) {
    SubtitleText result{std::string(logical)};
    if (logical.empty())
        return result;
    const SBCodepointSequence input{SBStringEncodingUTF8, logical.data(), logical.size()};
    std::vector<SBCodepoint> codepoints;
    codepoints.reserve(logical.size());
    SBUInteger index = 0;
    while (index < logical.size()) {
        auto c = SBCodepointSequenceGetCodepointAt(&input, &index);
        if (c >= 0x5D0 && c <= 0x5F4)
            result.hebrew = true;
        // The balloon is one scrolling line. Flatten line separators first so
        // the bidi algorithm processes the same line that the display paints.
        if (SBCodepointGetBidiType(c) == SBBidiTypeB || c == '\t' || c == 0x2028)
            c = ' ';
        codepoints.push_back(c);
    }
    if (!result.hebrew)
        return result; // Preserve existing Japanese/Latin rendering.

    const SBCodepointSequence sequence{SBStringEncodingUTF32, codepoints.data(), codepoints.size()};
    auto algorithm = SBAlgorithmCreate(&sequence);
    if (!algorithm)
        return result;
    auto paragraph = SBAlgorithmCreateParagraph(algorithm, 0, codepoints.size(), SBLevelDefaultLTR);
    if (paragraph) {
        result.rtl = (SBParagraphGetBaseLevel(paragraph) & 1) != 0;
        auto line = SBParagraphCreateLine(paragraph, 0, SBParagraphGetLength(paragraph));
        if (line) {
            result.visual.clear();
            result.visual.reserve(logical.size());
            const auto* runs = SBLineGetRunsPtr(line);
            for (SBUInteger r = 0; r < SBLineGetRunCount(line); ++r) {
                const auto& run = runs[r];
                for (SBUInteger i = 0; i < run.length; ++i) {
                    auto c = codepoints[run.offset + ((run.level & 1) ? run.length - 1 - i : i)];
                    if (invisible(c))
                        continue;
                    if (run.level & 1) {
                        const auto mirror = SBCodepointGetMirror(c);
                        if (mirror)
                            c = mirror;
                    }
                    append_utf8(result.visual, c);
                }
            }
            SBLineRelease(line);
        }
        SBParagraphRelease(paragraph);
    }
    SBAlgorithmRelease(algorithm);
    return result;
}
} // namespace stackchan::avatar::internal

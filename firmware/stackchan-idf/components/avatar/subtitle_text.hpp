// SPDX-FileCopyrightText: 2026 Kenta IDA <fuga@fugafuga.org>
// SPDX-License-Identifier: BSL-1.0
#pragma once

#include <string>
#include <string_view>

namespace stackchan::avatar::internal {
struct SubtitleText {
    std::string visual;
    bool hebrew = false;
    bool rtl = false;
};

// Convert logical UTF-8 to the visual order required by M5GFX's LTR renderer.
// Call on text changes, never from the frame loop. Speech keeps its original text.
SubtitleText prepare_subtitle(std::string_view logical);
} // namespace stackchan::avatar::internal

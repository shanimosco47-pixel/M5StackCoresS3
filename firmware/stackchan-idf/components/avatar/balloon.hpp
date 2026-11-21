// SPDX-FileCopyrightText: 2026 Kenta IDA <fuga@fugafuga.org>
// SPDX-License-Identifier: BSL-1.0

#pragma once

#include "avatar/canvas.hpp"
#include "avatar/draw_context.hpp"

namespace stackchan::avatar::internal {

void draw_balloon(RichCanvas& canvas, DrawContext& ctx, bool hebrew = false, bool rtl = false);

} // namespace stackchan::avatar::internal

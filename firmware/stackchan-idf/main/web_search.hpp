// SPDX-FileCopyrightText: 2026 Kenta IDA <fuga@fugafuga.org>
// SPDX-License-Identifier: BSL-1.0
#pragma once
#include <functional>
#include <optional>
#include <string>
#include <string_view>
namespace stackchan::app::web_search {
inline constexpr std::size_t kMaxResponseBytes = 48 * 1024;
std::optional<std::string> make_request(std::string_view arguments, const char* model);
std::string extract_result(std::string_view body, int http_status);
// Only the OpenAI provider can use this: api_key must be its existing credential.
std::string search(const std::string& api_key, const std::string& arguments, const std::function<bool()>& cancelled);
} // namespace stackchan::app::web_search

// SPDX-FileCopyrightText: 2026 Kenta IDA <fuga@fugafuga.org>
// SPDX-License-Identifier: BSL-1.0
#pragma once
#include <cJSON.h>
#include <string>
#include <string_view>
namespace stackchan::conversation {
// Caller owns the returned JSON tree, matching send_json's existing convention.
inline cJSON* make_announcement_request(std::string_view text) {
    if (text.empty() || text.size() > 512)
        return nullptr;
    cJSON* root = cJSON_CreateObject();
    if (!root)
        return nullptr;
    cJSON* response = cJSON_AddObjectToObject(root, "response");
    cJSON* modalities = response ? cJSON_AddArrayToObject(response, "output_modalities") : nullptr;
    const std::string instructions =
        "Say exactly the following text in Hebrew, once, with no introduction, additions, or tools: " +
        std::string(text);
    if (!response || !modalities || !cJSON_AddStringToObject(root, "type", "response.create") ||
        !cJSON_AddStringToObject(response, "tool_choice", "none") ||
        !cJSON_AddStringToObject(response, "instructions", instructions.c_str()) ||
        !cJSON_AddItemToArray(modalities, cJSON_CreateString("audio"))) {
        cJSON_Delete(root);
        return nullptr;
    }
    return root;
}
} // namespace stackchan::conversation

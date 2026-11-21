// SPDX-FileCopyrightText: 2026 Kenta IDA <fuga@fugafuga.org>
// SPDX-License-Identifier: BSL-1.0
#include "announcement.hpp"
#include <cassert>
#include <cstring>
#include <iostream>
int main() {
    using stackchan::conversation::make_announcement_request;
    assert(make_announcement_request("") == nullptr);
    assert(make_announcement_request(std::string(513, 'x')) == nullptr);
    const std::string text = "העדכון הושלם. אני מוכן לשיחה ולחיפוש באינטרנט.";
    cJSON* root = make_announcement_request(text);
    assert(root);
    assert(std::strcmp(cJSON_GetObjectItem(root, "type")->valuestring, "response.create") == 0);
    const auto* response = cJSON_GetObjectItem(root, "response");
    assert(std::strcmp(cJSON_GetObjectItem(response, "tool_choice")->valuestring, "none") == 0);
    const auto* modalities = cJSON_GetObjectItem(response, "output_modalities");
    assert(cJSON_GetArraySize(modalities) == 1);
    assert(std::strcmp(cJSON_GetArrayItem(modalities, 0)->valuestring, "audio") == 0);
    const std::string instructions = cJSON_GetObjectItem(response, "instructions")->valuestring;
    assert(instructions.find(text) != std::string::npos);
    cJSON_Delete(root);
    std::cout << "announcement payload tests passed\n";
}

// SPDX-FileCopyrightText: 2026 Kenta IDA <fuga@fugafuga.org>
// SPDX-License-Identifier: BSL-1.0
// Host: c++ -std=c++20 -Imain -I<idf>/components/json/cJSON tools/test_web_search.cpp
//       main/web_search_json.cpp <idf>/components/json/cJSON/cJSON.c -o test_web_search
#include "web_search.hpp"
#include <cJSON.h>
#include <cassert>
#include <iostream>
#include <memory>
using namespace stackchan::app::web_search;
using Json = std::unique_ptr<cJSON, decltype(&cJSON_Delete)>;
Json parse(const std::string& s) {
    return Json(cJSON_Parse(s.c_str()), cJSON_Delete);
}
int main() {
    auto request = make_request(R"({"query":"מזג אוויר \"היום\""})", "gpt-4.1");
    assert(request);
    auto req = parse(*request);
    assert(req);
    assert(std::string(cJSON_GetObjectItem(req.get(), "tool_choice")->valuestring) == "required");
    assert(!cJSON_IsTrue(cJSON_GetObjectItem(req.get(), "store")));
    assert(std::string(cJSON_GetObjectItem(req.get(), "input")->valuestring) == "מזג אוויר \"היום\"");
    assert(!make_request("{", "gpt-4.1"));
    assert(!make_request(R"({"query":23})", "gpt-4.1"));
    assert(!make_request(R"({"query":"  "})", "gpt-4.1"));
    assert(!make_request("{\"query\":\"" + std::string(769, 'x') + "\"}", "gpt-4.1"));
    const std::string fixture =
        R"({"status":"completed","output":[{"type":"web_search_call","status":"completed"},{"type":"message","content":[{"type":"output_text","text":"תשובה מעודכנת","annotations":[{"type":"url_citation","url":"https://example.org/","title":"Example"},{"type":"url_citation","url":"https://example.org/","title":"Duplicate"},{"type":"url_citation","url":"javascript:bad","title":"bad"}]}]}]})";
    auto result = parse(extract_result(fixture, 200));
    assert(cJSON_IsTrue(cJSON_GetObjectItem(result.get(), "ok")));
    assert(std::string(cJSON_GetObjectItem(result.get(), "answer")->valuestring) == "תשובה מעודכנת");
    assert(cJSON_GetArraySize(cJSON_GetObjectItem(result.get(), "sources")) == 1);
    for (
        auto body :
        {"{", "{}", R"({"status":"incomplete","output":[]})",
         R"({"status":"completed","output":[{"type":"message","content":[{"type":"output_text","text":"invented"}]}]})"}) {
        auto error = parse(extract_result(body, 200));
        assert(cJSON_IsFalse(cJSON_GetObjectItem(error.get(), "ok")));
    }
    auto error = parse(extract_result(R"({"error":{"message":"secret provider detail"}})", 401));
    assert(cJSON_IsFalse(cJSON_GetObjectItem(error.get(), "ok")));
    assert(extract_result("secret", 429).find("secret") == std::string::npos);
    std::cout << "web search request and result tests passed\n";
}

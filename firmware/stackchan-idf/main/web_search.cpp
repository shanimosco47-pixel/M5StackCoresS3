// SPDX-FileCopyrightText: 2026 Kenta IDA <fuga@fugafuga.org>
// SPDX-License-Identifier: BSL-1.0
#include "web_search.hpp"
#include <esp_crt_bundle.h>
#include <esp_http_client.h>
#include <esp_log.h>
#include <esp_heap_caps.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <sdkconfig.h>
#include <cstring>
#include <memory>
namespace stackchan::app::web_search {
namespace {
struct Response {
    std::unique_ptr<char, decltype(&heap_caps_free)> body{nullptr, heap_caps_free};
    std::size_t size = 0;
    bool oversized = false;
};
esp_err_t receive(esp_http_client_event_t* event) {
    auto& response = *static_cast<Response*>(event->user_data);
    if (event->event_id == HTTP_EVENT_ON_DATA && event->data_len > 0) {
        const auto size = static_cast<std::size_t>(event->data_len);
        if (response.size + size > kMaxResponseBytes) {
            response.oversized = true;
            return ESP_FAIL;
        }
        std::memcpy(response.body.get() + response.size, event->data, size);
        response.size += size;
    }
    return ESP_OK;
}
} // namespace
std::string search(const std::string& api_key, const std::string& arguments, const std::function<bool()>& cancelled) {
    auto request = make_request(arguments, CONFIG_STACKCHAN_OPENAI_SEARCH_MODEL);
    if (!request)
        return R"({"ok":false,"error":"query required, at most 768 UTF-8 bytes"})";
    if (api_key.empty())
        return R"({"ok":false,"error":"OpenAI API key unavailable"})";
    if (cancelled())
        return R"({"ok":false,"error":"search cancelled"})";
    Response response;
    response.body.reset(static_cast<char*>(heap_caps_malloc(kMaxResponseBytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT)));
    if (!response.body)
        return R"({"ok":false,"error":"search response allocation failed"})";
    esp_http_client_config_t config{};
    config.url = "https://api.openai.com/v1/responses";
    config.method = HTTP_METHOD_POST;
    config.crt_bundle_attach = esp_crt_bundle_attach;
    config.timeout_ms = 1000;
    config.buffer_size = 1024;
    config.buffer_size_tx = 1024;
    config.is_async = true;
    config.disable_auto_redirect = true; // never send bearer credentials to a redirect target
    config.event_handler = receive;
    config.user_data = &response;
    auto* client = esp_http_client_init(&config);
    if (!client)
        return R"({"ok":false,"error":"search connection allocation failed"})";
    const std::string authorization = "Bearer " + api_key;
    esp_err_t error = esp_http_client_set_header(client, "Authorization", authorization.c_str());
    if (error == ESP_OK)
        error = esp_http_client_set_header(client, "Content-Type", "application/json");
    if (error == ESP_OK)
        error = esp_http_client_set_post_field(client, request->data(), request->size());
    const auto deadline = esp_timer_get_time() + 30LL * 1000 * 1000;
    bool interrupted = false;
    bool timed_out = false;
    if (error == ESP_OK) {
        do {
            interrupted = cancelled();
            timed_out = esp_timer_get_time() >= deadline;
            if (interrupted || timed_out || response.oversized)
                break;
            error = esp_http_client_perform(client);
            if (error == ESP_ERR_HTTP_EAGAIN)
                vTaskDelay(pdMS_TO_TICKS(20));
        } while (error == ESP_ERR_HTTP_EAGAIN);
    }
    const int status = esp_http_client_get_status_code(client);
    esp_http_client_cleanup(client);
    // No headers, raw bodies, user queries, or credentials in logs.
    ESP_LOGI("web-search", "completed: http=%d transport=%d bytes=%u cancelled=%d timeout=%d", status,
             static_cast<int>(error), static_cast<unsigned>(response.size), interrupted, timed_out);
    if (interrupted)
        return R"({"ok":false,"error":"search cancelled"})";
    if (timed_out)
        return R"({"ok":false,"error":"search timed out; do not invent current information"})";
    if (response.oversized)
        return R"({"ok":false,"error":"search response too large"})";
    if (error != ESP_OK)
        return R"({"ok":false,"error":"web search connection failed"})";
    return extract_result(std::string_view(response.body.get(), response.size), status);
}
} // namespace stackchan::app::web_search

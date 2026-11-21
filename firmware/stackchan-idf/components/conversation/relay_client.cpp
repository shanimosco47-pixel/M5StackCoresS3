#include "conversation/relay_client.hpp"
#include "relay_core.hpp"

#include <algorithm>
#include <array>
#include <cstdio>
#include <cstring>
#include <cerrno>
#include <sys/select.h>
#include <cJSON.h>
#include <esp_crt_bundle.h>
#include <esp_heap_caps.h>
#include <esp_http_client.h>
#include <esp_random.h>
#include <esp_timer.h>

namespace stackchan::conversation {
namespace {
struct Free { void operator()(std::uint8_t* p) const { heap_caps_free(p); } };
using Bytes = std::unique_ptr<std::uint8_t, Free>;
Bytes allocate(std::size_t n) {
    return Bytes{static_cast<std::uint8_t*>(heap_caps_malloc(n, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT))};
}
constexpr std::size_t kCaptureBytes = 44 + relay::kMaxChunks * relay::kChunkSamples * 2;
std::string uuid() {
    std::uint8_t b[16]; esp_fill_random(b, sizeof(b));
    b[6] = (b[6] & 15) | 64; b[8] = (b[8] & 63) | 128;
    char result[37];
    std::snprintf(result, sizeof(result),
        "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
        b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7], b[8], b[9], b[10], b[11], b[12], b[13], b[14], b[15]);
    return result;
}
struct Response {
    Bytes bytes;
    std::size_t size = 0;
};
struct Connection { bool ready = false; };
esp_err_t connected(esp_http_client_event_t* ev) {
    if (ev->event_id == HTTP_EVENT_ON_CONNECTED) {
        static_cast<Connection*>(ev->user_data)->ready = true;
        esp_http_client_set_timeout_ms(ev->client, 50);
    }
    return ESP_OK;
}
// Wait before fetching headers: IDF logs a warning for every fetch timeout.
// A timed-out fetch drained TLS's pending bytes, so polling the socket before
// its next call cannot strand already-buffered TLS headers.
bool readable(esp_http_client_handle_t handle) {
    const int socket = esp_http_client_get_socket(handle);
    if (socket < 0) return false;
    fd_set descriptors; FD_ZERO(&descriptors); FD_SET(socket, &descriptors);
    timeval timeout{0, 50000};
    return select(socket + 1, &descriptors, nullptr, nullptr, &timeout) > 0;
}
bool valid_url(const std::string& url) {
    if (!url.starts_with("https://") || url.size() < 9 || url.size() > 256) return false;
    if (url.find_first_of("\r\n\t @?#\\") != std::string::npos) return false;
    return url[8] != '/';
}
} // namespace

struct RelayClient::Capture {
    relay::Vad vad;
    Bytes bytes;
    std::array<std::int16_t, relay::kPrefixChunks * relay::kChunkSamples> prefix{};
    std::size_t prefix_pos = 0, prefix_size = 0, samples = 0;
    bool recording = false;
    void reset() { vad.reset(); samples = prefix_pos = prefix_size = 0; recording = false; }
};
struct RelayClient::Job {
    Bytes request;
    std::size_t size;
    std::uint32_t generation;
    bool notice;
    std::string id;
};

RelayClient::RelayClient(std::string url, std::string token)
    : url_(std::move(url)), token_(std::move(token)), capture_(std::make_unique<Capture>()),
      gate_(std::make_unique<relay::TurnGate>()) {
    while (url_.ends_with('/')) url_.pop_back();
}
RelayClient::~RelayClient() {
    stop();
    terminating_.store(true);
    // Only destruction joins the worker; stop()/touch never wait for transport.
    while (!exited_.load()) vTaskDelay(pdMS_TO_TICKS(10));
    if (jobs_) {
        Job* job = nullptr;
        while (xQueueReceive(jobs_, &job, 0) == pdTRUE) delete job;
        vQueueDelete(jobs_);
    }
}

tl::expected<void, ConversationError> RelayClient::start(const ConversationConfig&) {
    stop();
    if (!valid_url(url_) || token_.empty() || token_.size() > 256 ||
        token_.find_first_of("\r\n") != std::string::npos) return tl::unexpected{ConversationError::TransportInit};
    if (!jobs_) jobs_ = xQueueCreate(1, sizeof(Job*));
    if (!jobs_) return tl::unexpected{ConversationError::OutOfMemory};
    if (!task_) {
        exited_.store(false);
        if (xTaskCreate([](void* p) { static_cast<RelayClient*>(p)->worker(); },
                        "relay-http", 8192, this, 4, &task_) != pdPASS) {
            exited_.store(true); task_ = nullptr;
            return tl::unexpected{ConversationError::OutOfMemory};
        }
    }
    active_.store(true);
    state_.store(ConversationState::Listening);
    emit({.type = ConversationEventType::StateChanged, .state = ConversationState::Listening}, gate_->current());
    return {};
}
void RelayClient::stop() {
    active_.store(false);
    gate_->cancel();
    capture_->reset();
    capture_->bytes.reset();
    state_.store(ConversationState::Idle);
}
bool RelayClient::accepts_event(const ConversationEvent& ev) const {
    return relay::current_event(active_.load(), gate_->current(), ev.generation);
}
bool RelayClient::transport_stopped() const {
    return outstanding_.load() == 0;
}
void RelayClient::emit(ConversationEvent ev, std::uint32_t generation) {
    ev.generation = generation;
    ev.emit_us = esp_timer_get_time();
    if (accepts_event(ev) && callback_) callback_(ev);
}

tl::expected<void, ConversationError> RelayClient::push_audio(std::span<const std::int16_t> pcm) {
    if (!active_.load()) return tl::unexpected{ConversationError::NotConnected};
    if (gate_->busy()) return {};
    if (pcm.size() != relay::kChunkSamples) return tl::unexpected{ConversationError::ProtocolError};
    auto& c = *capture_;
    if (!c.bytes) c.bytes = allocate(kCaptureBytes);
    if (!c.bytes) return tl::unexpected{ConversationError::OutOfMemory};
    const auto decision = c.vad.push(pcm);
    if (decision == relay::VadResult::Started) {
        c.recording = true; c.samples = 0;
        for (std::size_t i = 0; i < c.prefix_size; ++i) {
            const auto sample = c.prefix[(c.prefix_pos + c.prefix.size() - c.prefix_size + i) % c.prefix.size()];
            std::memcpy(c.bytes.get() + 44 + c.samples++ * 2, &sample, 2);
        }
        emit({.type = ConversationEventType::SpeechStarted}, gate_->current());
    }
    if (c.recording) {
        if (c.samples + pcm.size() > relay::kMaxChunks * relay::kChunkSamples) {
            c.reset(); return tl::unexpected{ConversationError::ProtocolError};
        }
        std::memcpy(c.bytes.get() + 44 + c.samples * 2, pcm.data(), pcm.size_bytes());
        c.samples += pcm.size();
    } else {
        for (auto sample : pcm) {
            c.prefix[c.prefix_pos] = sample;
            c.prefix_pos = (c.prefix_pos + 1) % c.prefix.size();
            c.prefix_size = std::min(c.prefix_size + 1, c.prefix.size());
        }
    }
    if (decision == relay::VadResult::Complete) return submit(false);
    if (decision == relay::VadResult::Discard) {
        c.reset();
        emit({.type = ConversationEventType::StateChanged, .state = ConversationState::Listening}, gate_->current());
    }
    return {};
}
tl::expected<void, ConversationError> RelayClient::commit_audio() {
    // VAD alone decides accepted utterances; callers cannot upload silence.
    return {};
}
tl::expected<void, ConversationError> RelayClient::submit(bool notice) {
    if (!active_.load()) return tl::unexpected{ConversationError::NotConnected};
    const auto accepted = gate_->begin();
    if (!accepted) return tl::unexpected{ConversationError::InvalidState};
    auto& c = *capture_;
    const std::size_t size = notice ? 0 : 44 + c.samples * 2;
    if (!notice) {
        auto* h = c.bytes.get();
        std::memcpy(h, "RIFF", 4); relay::put32(h + 4, size - 8);
        std::memcpy(h + 8, "WAVEfmt ", 8); relay::put32(h + 16, 16);
        h[20] = h[22] = 1; h[21] = h[23] = 0;
        relay::put32(h + 24, 16000); relay::put32(h + 28, 32000);
        h[32] = 2; h[33] = 0; h[34] = 16; h[35] = 0;
        std::memcpy(h + 36, "data", 4); relay::put32(h + 40, size - 44);
    }
    const auto generation = *accepted;
    auto* job = new Job{notice ? Bytes{} : std::move(c.bytes), size, generation, notice, uuid()};
    c.reset();
    state_.store(ConversationState::Thinking);
    // Queue this milestone before the worker can possibly deliver its reply.
    if (!notice) emit({.type = ConversationEventType::SpeechStopped}, generation);
    outstanding_.fetch_add(1);
    if (xQueueSend(jobs_, &job, 0) != pdTRUE) {
        outstanding_.fetch_sub(1);
        delete job; gate_->complete(generation);
        emit({.type = ConversationEventType::ResponseDone}, generation);
        return tl::unexpected{ConversationError::SendFailed};
    }
    return {};
}
tl::expected<void, ConversationError> RelayClient::request_announcement(std::string_view) { return submit(true); }
tl::expected<void, ConversationError> RelayClient::cancel_response() {
    gate_->cancel();
    capture_->reset();
    state_.store(ConversationState::Listening);
    return {};
}

void RelayClient::worker() {
    while (!terminating_.load()) {
        Job* raw = nullptr;
        if (xQueueReceive(jobs_, &raw, pdMS_TO_TICKS(50)) != pdTRUE) continue;
        std::unique_ptr<Job> job{raw};
        execute(*job);
        if (active_.load() && gate_->current() == job->generation) state_.store(ConversationState::Listening);
        gate_->complete(job->generation);
        outstanding_.fetch_sub(1);
    }
    exited_.store(true);
    vTaskDelete(nullptr);
}

void RelayClient::execute(Job& job) {
    auto current = [&] { return active_.load() && !terminating_.load() && gate_->current() == job.generation; };
    if (!current()) return;
    Response response{allocate(relay::kMaxResponse)};
    auto fail = [&] {
        emit({.type = ConversationEventType::Error, .text = "Relay request failed", .error = ConversationError::ServerError}, job.generation);
        emit({.type = ConversationEventType::ResponseDone}, job.generation);
    };
    if (!response.bytes) { fail(); return; }
    const std::string endpoint = url_ + (job.notice ? "/v3/notice" : "/v3/turn");
    esp_http_client_config_t cfg{};
    cfg.url = endpoint.c_str();
    cfg.crt_bundle_attach = esp_crt_bundle_attach;
    cfg.method = HTTP_METHOD_POST;
    cfg.timeout_ms = 5000; // async TLS connect budget, shortened to 50 ms onConnected
    cfg.is_async = true;
#if CONFIG_MBEDTLS_DYNAMIC_BUFFER
    // The dynamic RX wrapper peeks a TLS header into a stack buffer. A
    // nonblocking partial header can leave in_left pointing at that expired
    // buffer and the next poll reports INVALID_RECORD. Keep RX stable after
    // handshake; our SDK allocates this buffer in PSRAM, not scarce DMA RAM.
    cfg.tls_dyn_buf_strategy = HTTP_TLS_DYN_BUF_RX_STATIC;
#endif
    cfg.disable_auto_redirect = true;
    cfg.event_handler = connected;
    Connection connection;
    cfg.user_data = &connection;
    auto handle = esp_http_client_init(&cfg);
    if (!handle) { fail(); return; }
    esp_http_client_set_header(handle, "X-Device-Secret", token_.c_str());
    esp_http_client_set_header(handle, "X-Request-ID", job.id.c_str());
    // Persona/memory and extra provider headers are deliberately never sent.
    esp_http_client_set_header(handle, "X-Profile", "private");
    esp_http_client_set_header(handle, "Content-Type", job.notice ? "application/json" : "audio/wav");
    const auto deadline = esp_timer_get_time() + 45000000;
    auto within_deadline = [&] { return current() && esp_timer_get_time() < deadline; };
    esp_err_t opened;
    do {
        opened = esp_http_client_open(handle, job.size);
        // open() re-prepares HTTP headers when called again. Poll only during
        // TLS connect; never repeat a partially written request after connect.
        if (opened != ESP_ERR_HTTP_EAGAIN || connection.ready) break;
        vTaskDelay(pdMS_TO_TICKS(10));
    } while (within_deadline());
    bool received = false;
    std::size_t sent = 0;
    if (opened == ESP_OK) {
        // Explicit writes/reads preserve stream state across 50 ms poll gaps.
        // esp_http_client_perform() would reset it on a body read timeout.
        while (sent < job.size && within_deadline()) {
            const auto count = std::min<std::size_t>(1024, job.size - sent);
            const int n = esp_http_client_write(handle, reinterpret_cast<const char*>(job.request.get() + sent), count);
            if (n < 0 && errno != EAGAIN) break;
            if (n > 0) sent += n;
            else vTaskDelay(pdMS_TO_TICKS(10));
        }
        std::int64_t length = -ESP_ERR_HTTP_EAGAIN;
        while (sent == job.size && within_deadline() && length == -ESP_ERR_HTTP_EAGAIN) {
            if (!readable(handle)) continue;
            length = esp_http_client_fetch_headers(handle);
        }
        if (length >= 0 && length <= std::int64_t(relay::kMaxResponse)) {
            received = relay::receive_body({response.bytes.get(), relay::kMaxResponse}, response.size,
                [&](std::span<std::uint8_t> bytes) {
                    const int n = esp_http_client_read(handle, reinterpret_cast<char*>(bytes.data()), bytes.size());
                    if (n == -ESP_ERR_HTTP_EAGAIN) return -2;
                    return n < 0 ? -1 : n;
                }, [&] { return esp_http_client_is_complete_data_received(handle); }, within_deadline);
        }
    }
    const int status = esp_http_client_get_status_code(handle);
    esp_http_client_cleanup(handle);
    job.request.reset();
    if (!current()) {
        // A separate short, non-retried request is best effort. It never holds
        // the audio coordinator and cancellation never refunds admission.
        response.bytes.reset();
        const std::string cancel_url = url_ + "/v2/turn/" + job.id;
        esp_http_client_config_t cancel{};
        cancel.url = cancel_url.c_str(); cancel.method = HTTP_METHOD_DELETE;
        cancel.crt_bundle_attach = esp_crt_bundle_attach;
        cancel.timeout_ms = 5000; cancel.disable_auto_redirect = true;
        cancel.is_async = true;
#if CONFIG_MBEDTLS_DYNAMIC_BUFFER
        cancel.tls_dyn_buf_strategy = HTTP_TLS_DYN_BUF_RX_STATIC;
#endif
        cancel.event_handler = connected;
        Connection cancel_connection;
        cancel.user_data = &cancel_connection;
        auto h = esp_http_client_init(&cancel);
        if (h) {
            esp_http_client_set_header(h, "X-Device-Secret", token_.c_str());
            const auto cancel_deadline = esp_timer_get_time() + 1500000;
            esp_err_t cancelled;
            do {
                // DELETE has no body. Once all headers are written the server
                // has the complete best-effort cancellation; do not wait for
                // its response while the next utterance is already recording.
                cancelled = esp_http_client_open(h, 0);
                if (cancelled != ESP_ERR_HTTP_EAGAIN || cancel_connection.ready) break;
                vTaskDelay(pdMS_TO_TICKS(10));
            } while (esp_timer_get_time() < cancel_deadline);
            esp_http_client_cleanup(h);
        }
        return;
    }
    if (!received || status != 200) { fail(); return; }
    relay::Envelope envelope;
    std::span<const std::uint8_t> pcm;
    if (!relay::envelope({response.bytes.get(), response.size}, envelope) || !relay::wav_pcm(envelope.wav, pcm)) { fail(); return; }
    const std::string metadata(reinterpret_cast<const char*>(envelope.json.data()), envelope.json.size());
    if (!relay::json_depth_ok(metadata)) { fail(); return; }
    cJSON* root = cJSON_ParseWithLengthOpts(metadata.c_str(), metadata.size() + 1, nullptr, true);
    const auto* version = cJSON_GetObjectItemCaseSensitive(root, "version");
    const auto* id = cJSON_GetObjectItemCaseSensitive(root, "request_id");
    const auto* transcript = cJSON_GetObjectItemCaseSensitive(root, "transcript");
    const auto* answer = cJSON_GetObjectItemCaseSensitive(root, "answer");
    if (!cJSON_IsNumber(version) || version->valuedouble != 3 || !cJSON_IsString(id) || id->valuestring != job.id ||
        !cJSON_IsString(transcript) || !cJSON_IsString(answer) ||
        !cJSON_IsArray(cJSON_GetObjectItemCaseSensitive(root, "sources")) ||
        !cJSON_IsObject(cJSON_GetObjectItemCaseSensitive(root, "timings")) ||
        cJSON_GetObjectItemCaseSensitive(root, "audio") || cJSON_GetObjectItemCaseSensitive(root, "base64")) {
        cJSON_Delete(root); fail(); return;
    }
    std::string user_text = transcript->valuestring, answer_text = answer->valuestring;
    cJSON_Delete(root);
    auto audio = std::make_shared<std::vector<std::int16_t>>(pcm.size() / 2);
    for (std::size_t i = 0; i < audio->size(); ++i) (*audio)[i] = static_cast<std::int16_t>(relay::le16(pcm.data() + i * 2));
    response.bytes.reset();
    emit({.type = ConversationEventType::UserTranscript, .text = std::move(user_text)}, job.generation);
    emit({.type = ConversationEventType::AssistantTextDone, .text = std::move(answer_text)}, job.generation);
    emit({.type = ConversationEventType::AssistantAudioChunk, .audio = std::move(audio)}, job.generation);
    emit({.type = ConversationEventType::AssistantAudioDone}, job.generation);
    emit({.type = ConversationEventType::ResponseDone}, job.generation);
}
} // namespace stackchan::conversation

#pragma once

#include "conversation/conversation_service.hpp"
#include <atomic>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/task.h>

namespace stackchan::conversation {
namespace relay { class TurnGate; }
// HTTPS relay owns no audio hardware. All network calls run in its worker.
class RelayClient final : public ConversationService {
public:
    RelayClient(std::string url, std::string token);
    ~RelayClient() override;
    void set_event_callback(EventCallback cb) override { callback_ = std::move(cb); }
    tl::expected<void, ConversationError> start(const ConversationConfig&) override;
    void stop() override;
    bool transport_stopped() const override;
    tl::expected<void, ConversationError> push_audio(std::span<const std::int16_t>) override;
    tl::expected<void, ConversationError> commit_audio() override;
    tl::expected<void, ConversationError> cancel_response() override;
    tl::expected<void, ConversationError> request_announcement(std::string_view) override;
    tl::expected<void, ConversationError> submit_tool_result(std::string_view, std::string_view) override {
        return tl::unexpected{ConversationError::InvalidState};
    }
    ConversationState state() const override { return state_.load(); }
    bool accepts_event(const ConversationEvent& ev) const override;
private:
    struct Capture;
    struct Job;
    void worker();
    void execute(Job&);
    void emit(ConversationEvent, std::uint32_t generation);
    tl::expected<void, ConversationError> submit(bool notice);
    std::string url_, token_;
    EventCallback callback_;
    std::unique_ptr<Capture> capture_;
    std::unique_ptr<relay::TurnGate> gate_;
    QueueHandle_t jobs_ = nullptr;
    TaskHandle_t task_ = nullptr;
    std::atomic<bool> active_{false}, terminating_{false}, exited_{true};
    std::atomic<unsigned> outstanding_{0};
    std::atomic<ConversationState> state_{ConversationState::Idle};
};
} // namespace stackchan::conversation

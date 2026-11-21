#pragma once

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <span>
#include <atomic>
#include <optional>
#include <string_view>

namespace stackchan::conversation::relay {
constexpr std::size_t kChunkSamples = 640; // 16 kHz, 40 ms
constexpr std::size_t kPrefixChunks = 8;
constexpr std::size_t kMaxChunks = 500; // twenty seconds, including prefix
constexpr std::size_t kMaxJson = 16384;
constexpr std::size_t kMaxWav = 1500000;
constexpr std::size_t kMaxResponse = 12 + kMaxJson + kMaxWav;

inline bool current_event(bool active, std::uint32_t current, std::uint32_t event) {
    return active && current == event;
}

// One atomic word owns both the turn epoch and its capture gate. Completion of
// an old cancelled transport must never clear the busy bit of a newer turn.
class TurnGate {
public:
    std::optional<std::uint32_t> begin() {
        auto value = word_.load();
        do {
            if (value & 1u) return std::nullopt;
        } while (!word_.compare_exchange_weak(value, (value + 2u) | 1u));
        return (value + 2u) >> 1;
    }
    void cancel() {
        auto value = word_.load();
        while (!word_.compare_exchange_weak(value, (value + 2u) & ~1u)) {}
    }
    void complete(std::uint32_t generation) {
        auto expected = (generation << 1) | 1u;
        word_.compare_exchange_strong(expected, generation << 1);
    }
    bool busy() const { return word_.load() & 1u; }
    std::uint32_t current() const { return word_.load() >> 1; }
private:
    std::atomic<std::uint32_t> word_{0};
};

// Bound cJSON's recursive descent before it can consume the worker stack.
// Braces in strings, including escaped quotes/backslashes, do not add depth.
inline bool json_depth_ok(std::string_view json) {
    unsigned depth = 0;
    bool quoted = false, escaped = false;
    for (char c : json) {
        if (quoted) {
            if (escaped) escaped = false;
            else if (c == '\\') escaped = true;
            else if (c == '"') quoted = false;
        } else if (c == '"') quoted = true;
        else if (c == '{' || c == '[') { if (++depth > 16) return false; }
        else if (c == '}' || c == ']') { if (!depth) return false; --depth; }
    }
    return !quoted && !depth;
}

// Reader returns bytes, -2 for a poll timeout, -1 for failure, or 0 for EOF.
// Poll timeouts retain all accumulated bytes; EOF never implies completion.
template <typename Reader, typename Complete, typename Current>
bool receive_body(std::span<std::uint8_t> output, std::size_t& size,
                  Reader read, Complete complete, Current current) {
    bool first = true; // fetch_headers may already have cached a complete body
    while (current() && (first || !complete())) {
        first = false;
        if (size == output.size()) return false;
        const auto capacity = output.size() - size;
        const int n = read(output.subspan(size, capacity > 4096 ? 4096 : capacity));
        if (n == -2) continue;
        if (n < 0 || std::size_t(n) > capacity) return false;
        if (!n) return current() && complete();
        size += n;
    }
    return current() && complete();
}

inline std::uint32_t le32(const std::uint8_t* p) {
    return p[0] | (std::uint32_t(p[1]) << 8) | (std::uint32_t(p[2]) << 16) | (std::uint32_t(p[3]) << 24);
}
inline std::uint16_t le16(const std::uint8_t* p) { return p[0] | (std::uint16_t(p[1]) << 8); }
inline void put32(std::uint8_t* p, std::uint32_t v) {
    for (unsigned i = 0; i < 4; ++i) p[i] = v >> (8 * i);
}

struct Envelope { std::span<const std::uint8_t> json, wav; };
inline bool envelope(std::span<const std::uint8_t> bytes, Envelope& out) {
    if (bytes.size() < 12 || std::memcmp(bytes.data(), "M5R3", 4)) return false;
    const auto j = le32(bytes.data() + 4), w = le32(bytes.data() + 8);
    if (!j || j > kMaxJson || w > kMaxWav || w < 44 || bytes.size() != 12u + j + w) return false;
    out = {bytes.subspan(12, j), bytes.subspan(12 + j, w)};
    return true;
}

// Walk RIFF chunks, including unknown chunks and odd-byte padding. Never assume
// Google emits the minimal 44-byte header. Only the agreed PCM format is playable.
inline bool wav_pcm(std::span<const std::uint8_t> wav, std::span<const std::uint8_t>& pcm) {
    if (wav.size() < 12 || std::memcmp(wav.data(), "RIFF", 4) ||
        std::memcmp(wav.data() + 8, "WAVE", 4) || le32(wav.data() + 4) != wav.size() - 8) return false;
    bool format = false, data = false;
    for (std::size_t pos = 12; pos < wav.size();) {
        if (wav.size() - pos < 8) return false;
        const auto* p = wav.data() + pos;
        const std::size_t n = le32(p + 4);
        pos += 8;
        if (n > wav.size() - pos) return false;
        if (!std::memcmp(p, "fmt ", 4)) {
            if (format || n < 16 || le16(p + 8) != 1 || le16(p + 10) != 1 ||
                le32(p + 12) != 16000 || le32(p + 16) != 32000 ||
                le16(p + 20) != 2 || le16(p + 22) != 16) return false;
            format = true;
        } else if (!std::memcmp(p, "data", 4)) {
            if (data || !n || n % 2) return false;
            pcm = wav.subspan(pos, n);
            data = true;
        }
        pos += n;
        if (n & 1u) { if (pos == wav.size()) return false; ++pos; }
    }
    return format && data;
}

enum class VadResult { Quiet, Started, Continue, Complete, Discard };
class Vad {
public:
    VadResult push(std::span<const std::int16_t> samples) {
        if (samples.size() != kChunkSamples) return VadResult::Quiet;
        std::uint32_t energy = 0;
        for (auto s : samples) energy += s < 0 ? -std::int32_t(s) : s;
        const bool loud = energy / samples.size() >= 500;
        if (!active_) {
            if (!loud) return VadResult::Quiet;
            active_ = true; speech_ = 1; chunks_ = kPrefixChunks + 1; silence_ = 0;
            return VadResult::Started;
        }
        ++chunks_;
        if (loud) { ++speech_; silence_ = 0; } else ++silence_;
        if (silence_ >= 15 || chunks_ >= kMaxChunks) {
            const bool accepted = speech_ >= 5; // at least 200 ms of speech
            reset();
            return accepted ? VadResult::Complete : VadResult::Discard;
        }
        return VadResult::Continue;
    }
    void reset() { active_ = false; speech_ = silence_ = chunks_ = 0; }
private:
    bool active_ = false;
    unsigned speech_ = 0, silence_ = 0, chunks_ = 0;
};
} // namespace stackchan::conversation::relay

// Host: zig c++ -std=c++20 -Icomponents/conversation tools/test_relay.cpp -o test_relay.exe
#include "relay_core.hpp"
#include <array>
#include <cassert>
#include <iostream>
#include <vector>

using namespace stackchan::conversation::relay;
static std::vector<std::uint8_t> wav() {
    std::vector<std::uint8_t> w(48);
    std::memcpy(w.data(), "RIFF", 4); put32(w.data() + 4, 40);
    std::memcpy(w.data() + 8, "WAVEfmt ", 8); put32(w.data() + 16, 16);
    w[20] = w[22] = 1; put32(w.data() + 24, 16000); put32(w.data() + 28, 32000);
    w[32] = 2; w[34] = 16;
    std::memcpy(w.data() + 36, "data", 4); put32(w.data() + 40, 4);
    w[44] = 0xff; w[45] = 0x7f; w[46] = 0; w[47] = 0x80;
    return w;
}
static void wav_tests() {
    auto w = wav();
    std::span<const std::uint8_t> pcm;
    assert(wav_pcm(w, pcm) && pcm.size() == 4);
    assert(le16(pcm.data()) == 32767 && le16(pcm.data() + 2) == 32768);
    // Metadata chunk before fmt/data with odd byte padding.
    w.insert(w.begin() + 12, {'J','U','N','K',1,0,0,0,'x',0});
    put32(w.data() + 4, w.size() - 8);
    assert(wav_pcm(w, pcm) && pcm.size() == 4);
    auto bad = w; put32(bad.data() + 16, 0xffffffff); assert(!wav_pcm(bad, pcm));
    bad = w; bad[34] = 0x44; assert(!wav_pcm(bad, pcm)); // non-16kHz
    bad = w; bad[30] = 3; assert(!wav_pcm(bad, pcm)); // float format
    bad = w; bad.push_back(0); assert(!wav_pcm(bad, pcm));
    for (std::size_t n = 0; n < w.size(); ++n) assert(!wav_pcm({w.data(), n}, pcm));
    bad = wav(); put32(bad.data() + 40, 3); assert(!wav_pcm(bad, pcm));
    bad = wav(); bad.insert(bad.end(), {'d','a','t','a',2,0,0,0,0,0});
    put32(bad.data() + 4, bad.size() - 8); assert(!wav_pcm(bad, pcm));
}
static void envelope_tests() {
    auto w = wav();
    const char json[] = "{\"version\":3}";
    std::vector<std::uint8_t> bytes(12 + sizeof(json) - 1 + w.size());
    std::memcpy(bytes.data(), "M5R3", 4);
    put32(bytes.data() + 4, sizeof(json) - 1); put32(bytes.data() + 8, w.size());
    std::memcpy(bytes.data() + 12, json, sizeof(json) - 1);
    std::memcpy(bytes.data() + 12 + sizeof(json) - 1, w.data(), w.size());
    Envelope e;
    assert(envelope(bytes, e) && e.json.size() == sizeof(json) - 1 && e.wav.size() == w.size());
    for (std::size_t n = 0; n < bytes.size(); ++n) assert(!envelope({bytes.data(), n}, e));
    auto bad = bytes; bad[3] = '2'; assert(!envelope(bad, e));
    bad = bytes; put32(bad.data() + 4, kMaxJson + 1); assert(!envelope(bad, e));
    bad = bytes; put32(bad.data() + 8, kMaxWav + 1); assert(!envelope(bad, e));
    bad = bytes; put32(bad.data() + 4, 0xffffffff); assert(!envelope(bad, e));
    bad = bytes; bad.push_back(0); assert(!envelope(bad, e));
}
static void vad_tests() {
    std::array<std::int16_t, kChunkSamples> quiet{}, loud{};
    loud.fill(1000);
    Vad vad;
    for (int i = 0; i < 100; ++i) assert(vad.push(quiet) == VadResult::Quiet);
    assert(vad.push(loud) == VadResult::Started);
    for (int i = 0; i < 14; ++i) assert(vad.push(quiet) == VadResult::Continue);
    assert(vad.push(quiet) == VadResult::Discard); // click/brief noise
    assert(vad.push(loud) == VadResult::Started);
    for (int i = 0; i < 4; ++i) assert(vad.push(loud) == VadResult::Continue);
    for (int i = 0; i < 14; ++i) assert(vad.push(quiet) == VadResult::Continue);
    // Silence hysteresis resets on resumed speech.
    assert(vad.push(loud) == VadResult::Continue);
    for (int i = 0; i < 14; ++i) assert(vad.push(quiet) == VadResult::Continue);
    assert(vad.push(quiet) == VadResult::Complete);
    assert(vad.push(loud) == VadResult::Started);
    std::size_t chunks = kPrefixChunks + 1;
    while (++chunks < kMaxChunks) assert(vad.push(loud) == VadResult::Continue);
    assert(vad.push(loud) == VadResult::Complete); // bounded continuous speech
    assert(vad.push(loud) == VadResult::Started);
    vad.reset(); // touch/cancellation must abandon partial utterance
    assert(vad.push(quiet) == VadResult::Quiet);
    assert(vad.push({quiet.data(), 320}) == VadResult::Quiet);
    loud.fill(-32768);
    assert(vad.push(loud) == VadResult::Started); // signed-energy overflow guard
}
static void transport_tests() {
    std::array<std::uint8_t, 16> buffer{};
    std::size_t size = 0;
    int calls = 0;
    // Response gaps must preserve stream bytes rather than announce completion
    // or restart a POST. Simulate body fragments separated by poll timeouts.
    assert(receive_body(buffer, size, [&](std::span<std::uint8_t> bytes) {
        ++calls;
        if (calls == 1 || calls == 3) return -2;
        bytes[0] = calls == 2 ? 'a' : 'b'; return 1;
    }, [&] { return calls == 4; }, [] { return true; }));
    assert(calls == 4 && size == 2 && buffer[0] == 'a' && buffer[1] == 'b');
    size = 0;
    assert(!receive_body(buffer, size, [](auto) { return 0; }, [] { return false; }, [] { return true; }));
    size = 0; calls = 0;
    TurnGate gate; auto old = gate.begin(); assert(old);
    assert(!receive_body(buffer, size, [&](auto) {
        ++calls; gate.cancel(); return -2;
    }, [] { return false; }, [&] { return gate.current() == *old; }));
    assert(calls == 1 && !gate.busy()); // one poll then immediate recording admission
    auto next = gate.begin(); assert(next);
    gate.complete(*old); assert(gate.busy()); // old DELETE cannot drop new capture
    size = 0;
    assert(receive_body(buffer, size, [](auto bytes) { bytes[0] = 'x'; return 1; },
                        [] { return true; }, [] { return true; }));
    assert(size == 1); // complete body cached while fetching headers is drained
    size = 0;
    assert(!receive_body(buffer, size, [](auto bytes) { return int(bytes.size()); },
                         [] { return false; }, [] { return true; }));
    assert(size == buffer.size()); // hard response cap
}
int main() {
    wav_tests(); envelope_tests(); vad_tests(); transport_tests();
    assert(current_event(true, 10, 10));
    assert(!current_event(true, 11, 10)); // touch invalidates worker + queued audio/text
    assert(!current_event(false, 11, 11)); // stopped client cannot publish
    assert(!current_event(true, 12, 11)); // reconnect cannot revive stale events
    TurnGate gate;
    const auto first = gate.begin(); assert(first && gate.busy());
    assert(!gate.begin());
    gate.cancel(); assert(!gate.busy());
    const auto second = gate.begin(); assert(second && *second != *first);
    gate.complete(*first); assert(gate.busy()); // old DELETE completion cannot clear a new turn
    assert(gate.current() == *second);
    gate.complete(*second); assert(!gate.busy());
    assert(json_depth_ok(R"({"sources":[],"timings":{"x":1},"quoted":"[{\\\"}]"})"));
    assert(!json_depth_ok(std::string(17, '[') + std::string(17, ']')));
    assert(json_depth_ok(std::string(16, '[') + std::string(16, ']')));
    assert(!json_depth_ok(R"({"x":"unterminated})"));
    std::cout << "Relay WAV, envelope, VAD and capture-reset tests passed\n";
}

// SPDX-FileCopyrightText: 2026 Kenta IDA <fuga@fugafuga.org>
// SPDX-License-Identifier: BSL-1.0
#include "subtitle_text.hpp"
#include <cstdlib>
#include <iostream>
#include <string>
#include <string_view>

using stackchan::avatar::internal::prepare_subtitle;

int main(int argc, char** argv) {
    if (argc == 2) {
        // stdin transports UTF-8 unchanged even when Windows narrow argv uses
        // a legacy active codepage.
        std::string logical;
        if (std::string_view(argv[1]) == "--stdin")
            std::getline(std::cin, logical);
        else
            logical = argv[1];
        std::cout << prepare_subtitle(logical).visual;
        return 0;
    }
    struct Case {
        std::string_view logical, visual;
        bool hebrew, rtl;
    };
    const Case cases[] = {
        {"", "", false, false},
        {"Hello 123!", "Hello 123!", false, false},
        {"こんにちは", "こんにちは", false, false},
        {"שלום", "םולש", true, true},
        {"שלום עולם!", "!םלוע םולש", true, true},
        {"שלום 123", "123 םולש", true, true},
        {"שלום 12:34", "12:34 םולש", true, true},
        {"שלום (123)", "(123) םולש", true, true},
        {"שלום (Hello 123)", "(Hello 123) םולש", true, true},
        {"Hello שלום 123", "Hello 123 םולש", true, false},
        {"שלום\nעולם", "םלוע םולש", true, true},
        {"שָׁלוֹם", "םולש", true, true},
        {"שלום \xE2\x81\xA6"
         "ABC 123"
         "\xE2\x81\xA9",
         "ABC 123 םולש", true, true},
    };
    for (const auto& test : cases) {
        const auto result = prepare_subtitle(test.logical);
        if (result.visual != test.visual || result.hebrew != test.hebrew || result.rtl != test.rtl) {
            std::cerr << "Failed: " << test.logical << "\nExpected: " << test.visual << "\nActual: " << result.visual
                      << '\n';
            return EXIT_FAILURE;
        }
    }
    std::cout << "Passed " << std::size(cases) << " subtitle ordering cases\n";
}

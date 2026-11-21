idf_component_register(
    SRCS
        "avatar.cpp"
        "balloon.cpp"
        "animation.cpp"
        "subtitle_text.cpp"
        "fonts/hebrew_font.cpp"
        "third_party/sheenbidi/Source/SheenBidi.c"
    INCLUDE_DIRS "include"
    PRIV_INCLUDE_DIRS "." "third_party/sheenbidi/Headers"
    REQUIRES
        m5gfx
        M5Unified
        avatar_vm
)
target_compile_features(${COMPONENT_LIB} PUBLIC cxx_std_20)
target_compile_definitions(${COMPONENT_LIB} PRIVATE SB_CONFIG_UNITY)

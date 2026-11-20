cmake_minimum_required(VERSION 3.20)
project(nfl2k5_native_dsp_tests LANGUAGES C)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

set(DSP "${CMAKE_CURRENT_LIST_DIR}/../../external/xboxrecomp/src/apu/dsp")
add_executable(dsp_dispatch ../web/test_dsp_dispatch.c)
add_executable(dsp_firmware ../web/test_dsp56300.c
    "${DSP}/dsp.c" "${DSP}/dsp_cpu.c" "${DSP}/dsp_dma.c")

foreach(target dsp_dispatch dsp_firmware)
    target_include_directories(${target} PRIVATE "${DSP}")
    # These fixtures use assertions to check state and perform DSP operations.
    # Keep them active even in the optimized configuration used by the game.
    if(MSVC)
        target_compile_options(${target} PRIVATE /UNDEBUG)
        target_compile_definitions(${target} PRIVATE _CRT_SECURE_NO_WARNINGS)
    else()
        target_compile_options(${target} PRIVATE -UNDEBUG)
    endif()
endforeach()

enable_testing()
add_test(NAME dsp_dispatch_equivalence COMMAND dsp_dispatch)
add_test(NAME dsp_firmware_and_dma COMMAND dsp_firmware)
set_tests_properties(dsp_dispatch_equivalence dsp_firmware_and_dma
    PROPERTIES TIMEOUT 120)

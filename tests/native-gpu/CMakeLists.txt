cmake_minimum_required(VERSION 3.20)
project(nfl2k5_native_gpu_tests LANGUAGES C)
find_package(Python3 REQUIRED COMPONENTS Interpreter)
set(KERNEL "${CMAKE_CURRENT_LIST_DIR}/../../external/xboxrecomp/src/kernel")
set(SOURCE "${CMAKE_CURRENT_BINARY_DIR}/vp_hlsl_check.c")
add_custom_command(OUTPUT "${SOURCE}"
    COMMAND "${Python3_EXECUTABLE}" -I "${CMAKE_CURRENT_LIST_DIR}/gen_vp_hlsl_check.py" "${SOURCE}"
    DEPENDS gen_vp_hlsl_check.py "${KERNEL}/nv2a_gpu_vp.inc.c" "${KERNEL}/nv2a_pb_exec.c"
    VERBATIM)
add_executable(vp_hlsl_check "${SOURCE}")
target_compile_features(vp_hlsl_check PRIVATE c_std_11)
target_link_libraries(vp_hlsl_check PRIVATE d3dcompiler)
enable_testing()
add_test(NAME vp_hlsl_comparisons COMMAND vp_hlsl_check)

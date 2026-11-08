# Web smoke module for tests/web/test_web_av.js (built by tools/test-web.sh).
cmake_minimum_required(VERSION 3.20)
project(web_smoke C CXX)   # C++: the kernel's WebGPU port links as C++
get_filename_component(NFL2K5_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../.." ABSOLUTE)
add_subdirectory("${NFL2K5_ROOT}/external/xboxrecomp" xboxrecomp)
add_executable(web_smoke web_smoke.c save_replace.c "${NFL2K5_ROOT}/src/platform/web/web_sdl.c"
    "${NFL2K5_ROOT}/src/platform/web/web_fs.c" "${NFL2K5_ROOT}/src/nfl2k5_controls.c")
target_link_libraries(web_smoke PRIVATE xboxrecomp)
target_link_options(web_smoke PRIVATE -pthread -sPROXY_TO_PTHREAD -sPTHREAD_POOL_SIZE=12
    -sWASMFS=1 -sFORCE_FILESYSTEM=1
    -sALLOW_MEMORY_GROWTH=1 -sINITIAL_MEMORY=512MB -sMAXIMUM_MEMORY=4GB
    -sMODULARIZE=1 -sEXPORT_NAME=createSmoke -sEXPORTED_RUNTIME_METHODS=ENV
    -sENVIRONMENT=web,worker -sEXIT_RUNTIME=0 -sERROR_ON_UNDEFINED_SYMBOLS=0)
set_target_properties(web_smoke PROPERTIES SUFFIX ".js" LINKER_LANGUAGE CXX)
# On every build, not only when the module relinks: the page and scripts
# change on their own.
add_custom_target(web_smoke_page ALL
  COMMAND "${CMAKE_COMMAND}" -E copy "${NFL2K5_ROOT}/web/launch.js" "${NFL2K5_ROOT}/web/audio-worklet.js"
          "${NFL2K5_ROOT}/web/storage.js" "${NFL2K5_ROOT}/web/save-format.js" "${NFL2K5_ROOT}/web/save-worker.js"
          "${CMAKE_CURRENT_SOURCE_DIR}/smoke.html" "${CMAKE_BINARY_DIR}"
  VERBATIM)
add_dependencies(web_smoke web_smoke_page)

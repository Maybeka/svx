cmake_minimum_required(VERSION 3.20)
project(svx LANGUAGES CXX)

include(GNUInstallDirs)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module)
find_package(Python3 COMPONENTS Development.Embed)

add_library(svx SHARED
  svx_runtime/src/context.cpp
  svx_runtime/src/process.cpp
  svx_runtime/src/python_bindings.cpp
  svx_runtime/src/python_runtime.cpp
  svx_runtime/src/signal.cpp
  svx_runtime/src/sv_dpi.cpp
  svx_runtime/src/svx.cpp
)

target_include_directories(svx PRIVATE
  svx_runtime/include
  ${Python3_INCLUDE_DIRS}
)

target_link_libraries(svx PRIVATE
  Python3::Module
  ${CMAKE_DL_LIBS}
)

if(TARGET Python3::Python)
  target_link_libraries(svx PRIVATE Python3::Python)
endif()

if(APPLE)
  target_link_options(svx PRIVATE "-undefined" "dynamic_lookup")
endif()

set_target_properties(svx PROPERTIES
  PREFIX "lib"
  OUTPUT_NAME "svx"
)

execute_process(
  COMMAND "${Python3_EXECUTABLE}" -c "import sysconfig; print(sysconfig.get_config_var('EXT_SUFFIX') or '.so')"
  OUTPUT_VARIABLE PY_EXT_SUFFIX
  OUTPUT_STRIP_TRAILING_WHITESPACE
)

add_custom_command(TARGET svx POST_BUILD
  COMMAND ${CMAKE_COMMAND} -E create_symlink
    "$<TARGET_FILE_NAME:svx>"
    "_svx_native${PY_EXT_SUFFIX}"
  WORKING_DIRECTORY "$<TARGET_FILE_DIR:svx>"
)

install(TARGETS svx
  LIBRARY DESTINATION "${CMAKE_INSTALL_LIBDIR}"
  RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}"
)
install(DIRECTORY sv/ DESTINATION "${CMAKE_INSTALL_DATADIR}/svx/sv")
install(FILES LICENSE DESTINATION "${CMAKE_INSTALL_DATADIR}/licenses/svx")

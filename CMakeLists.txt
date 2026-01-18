cmake_minimum_required(VERSION 3.14)
project(PortfolioOptimizerCppRunner)

set(CMAKE_CXX_STANDARD 17)

# Find Python and pybind11
find_package(Python3 COMPONENTS Interpreter Development REQUIRED)
find_package(pybind11 REQUIRED)

# Add executable
add_executable(cpp_strategy_runner cpp_strategy_runner.cpp)

# Link pybind11 and Python
# pybind11::embed links Python runtime for embedding
# If you installed pybind11 via pip, you may need to set PYBIND11_DIR or use pybind11_add_subdirectory
# If not found, you can use FetchContent to download pybind11

target_link_libraries(cpp_strategy_runner PRIVATE pybind11::embed Python3::Python)

# Optionally, set include directories if needed
# target_include_directories(cpp_strategy_runner PRIVATE ${Python3_INCLUDE_DIRS})

# Optionally, set runtime path for Python DLLs on Windows
if(WIN32)
    set_target_properties(cpp_strategy_runner PROPERTIES
        VS_DEBUGGER_ENVIRONMENT "PATH=$ENV{PATH};${Python3_RUNTIME_LIBRARY_DIRS}")
endif()

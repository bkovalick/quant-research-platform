cmake_minimum_required(VERSION 3.14)
project(PortfolioOptimizerCppRunner)

set(CMAKE_CXX_STANDARD 17)

# Find Python and pybind11
find_package(Python3 COMPONENTS Interpreter Development REQUIRED)
# find_package(pybind11 REQUIRED) # Commented out if CMake can't find pybind11

# If pybind11 is installed via pip, add its include directory manually
execute_process(
    COMMAND python -m pybind11 --includes
    OUTPUT_VARIABLE PYBIND11_INCLUDES
    OUTPUT_STRIP_TRAILING_WHITESPACE
)
string(REPLACE "-I" "" PYBIND11_INCLUDES ${PYBIND11_INCLUDES})
separate_arguments(PYBIND11_INCLUDES)
include_directories(${PYBIND11_INCLUDES})


# Add executable

# Add cpp_strategy_runner executable
add_executable(cpp_strategy_runner cpp_strategy_runner.cpp)
if (pybind11_FOUND)
    target_link_libraries(cpp_strategy_runner PRIVATE pybind11::embed)
endif()
target_link_libraries(cpp_strategy_runner PRIVATE Python3::Python Threads::Threads)

# Optionally, set runtime path for Python DLLs on Windows
if(WIN32)
    set_target_properties(cpp_strategy_runner PROPERTIES
        VS_DEBUGGER_ENVIRONMENT "PATH=$ENV{PATH};${Python3_RUNTIME_LIBRARY_DIRS}")
endif()

# Link Python and pybind11 embed
find_package(Threads REQUIRED)
# If pybind11 is available as a CMake package, link pybind11::embed
find_package(pybind11 QUIET)

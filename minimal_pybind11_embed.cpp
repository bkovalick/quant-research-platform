// Minimal pybind11 embed test
#include <pybind11/embed.h>
#include <iostream>

namespace py = pybind11;

int main() {
    try {
        py::scoped_interpreter guard{};
        py::module sys = py::module::import("sys");
        std::cout << "Python interpreter started." << std::endl;
        py::module math_mod = py::module::import("math");
        std::cout << "Imported math module successfully." << std::endl;
        std::cout << "math.sqrt(16) = " << math_mod.attr("sqrt")(16).cast<double>() << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "Exception: " << e.what() << std::endl;
        return 1;
    }
    return 0;
}

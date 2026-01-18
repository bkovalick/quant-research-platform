// C++ wrapper using pybind11 to run Python strategies in parallel
#include <pybind11/embed.h>
#include <pybind11/stl.h>
#include <thread>
#include <vector>
#include <iostream>

namespace py = pybind11;
// using namespace pybind11::literals; // Not needed if not using _a

// Worker function to run a single strategy
void run_strategy_worker(const py::object& run_strategy, const std::string& program_type, std::vector<py::object>& results, int idx) {
    py::gil_scoped_acquire acquire; // Acquire GIL in each thread
    try {
        py::dict config;
        config["program_type"] = program_type;
        results[idx] = run_strategy(config);
    } catch (const py::error_already_set& e) {
        std::cerr << "Python exception in thread " << idx << ": " << e.what() << std::endl;
        results[idx] = py::none();
    } catch (const std::exception& e) {
        std::cerr << "C++ exception in thread " << idx << ": " << e.what() << std::endl;
        results[idx] = py::none();
    }
}

int main() {
    py::scoped_interpreter guard{};
    std::cout << "Python interpreter started." << std::endl;
    py::module sys;
    py::module strategy_runner;
    py::object run_strategy;
    try {
        sys = py::module::import("sys");
        std::cout << "Imported sys module." << std::endl;
        sys.attr("path").attr("insert")(0, R"(d:\repos\portfolio-optimizer\src)"); // Use raw string for Windows path
        std::cout << "Set PYTHONPATH to d:\\repos\\portfolio-optimizer\\src." << std::endl;
        strategy_runner = py::module::import("strategy_runner");
        std::cout << "Imported strategy_runner module." << std::endl;
        run_strategy = strategy_runner.attr("run_strategy");
        std::cout << "Obtained run_strategy function." << std::endl;
    } catch (const py::error_already_set& e) {
        std::cerr << "Python exception during import: " << e.what() << std::endl;
        return 1;
    } catch (const std::exception& e) {
        std::cerr << "C++ exception during import: " << e.what() << std::endl;
        return 1;
    }

    // Example: list of program types (replace with your actual configs)
    std::vector<std::string> program_types = {"fixed_weights", "maximize_sharpe", "mean_variance"};
    std::vector<py::object> results(program_types.size());
    // Run strategies sequentially (no threads)
    for (size_t i = 0; i < program_types.size(); ++i) {
        py::dict config;
        config["program_type"] = program_types[i];
        try {
            results[i] = run_strategy(config);
        } catch (const py::error_already_set& e) {
            std::cerr << "Python exception for " << program_types[i] << ": " << e.what() << std::endl;
            results[i] = py::none();
        }
    }

    // Print results
    for (const auto& res : results) {
        py::print(res);
    }
    std::cout << "cpp_strategy_runner execution complete." << std::endl;
    std::cout.flush();
    std::cerr.flush();
    return 0;
}

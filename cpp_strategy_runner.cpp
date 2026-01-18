// C++ wrapper using pybind11 to run Python strategies in parallel
#include <pybind11/embed.h>
#include <pybind11/stl.h>
#include <thread>
#include <vector>
#include <iostream>

namespace py = pybind11;

// Worker function to run a single strategy
void run_strategy_worker(const py::object& run_strategy, py::dict config, std::vector<py::object>& results, int idx) {
    results[idx] = run_strategy(config);
}

int main() {
    py::scoped_interpreter guard{};
    py::module sys = py::module::import("sys");
    sys.attr("path").attr("insert")(0, "./src"); // Ensure src/ is in PYTHONPATH
    py::module strategy_runner = py::module::import("strategy_runner");
    py::object run_strategy = strategy_runner.attr("run_strategy");

    // Example: list of configs (replace with your actual configs)
    std::vector<py::dict> configs = {
        py::dict("program_type"_a="fixed_weights"),
        py::dict("program_type"_a="maximize_sharpe"),
        py::dict("program_type"_a="mean_variance")
    };
    std::vector<py::object> results(configs.size());
    std::vector<std::thread> threads;

    // Launch threads
    for (size_t i = 0; i < configs.size(); ++i) {
        threads.emplace_back(run_strategy_worker, run_strategy, configs[i], std::ref(results), i);
    }
    for (auto& t : threads) t.join();

    // Print results
    for (const auto& res : results) {
        py::print(res);
    }
    return 0;
}

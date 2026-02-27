from application.experiment_runner import ExperimentRunner
import json

if __name__ == '__main__':
    with open(f"src/config/experiment_20260220.json", 'r') as f:
        config = json.load(f)

    config = config.copy()
    experiment_run = ExperimentRunner(config)
    experiment_results = experiment_run.run_parallel()
    print(experiment_results)

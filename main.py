import importlib
import logging
import os
import sys
import time

# Configure logging to output to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

PIPELINE_MODULES = {
    "real_time": "pipelines.real_time",
    "delayed": "pipelines.delayed",
    "eod": "pipelines.eod",
}


def parse_pipelines(pipelines_env):
    return [p.strip().lower() for p in pipelines_env.split(",") if p.strip()]


def load_pipeline_module(p_name, importer=importlib.import_module):
    module_name = PIPELINE_MODULES.get(p_name)
    if not module_name:
        raise ValueError(f"Unknown pipeline configured: '{p_name}'.")
    return importer(module_name)


def main(pipelines_env=None, importer=importlib.import_module):
    start_time = time.time()
    if pipelines_env is None:
        pipelines_env = os.getenv("PIPELINES", "real_time,delayed,eod")
    pipelines_to_run = parse_pipelines(pipelines_env)

    logging.info(f"Main orchestrator starting execution. Pipelines selected: {pipelines_to_run}")
    failures = []

    if not pipelines_to_run:
        logging.error("No pipelines selected.")
        return 1

    for p_name in pipelines_to_run:
        logging.info(f"==========================================")
        logging.info(f"Executing Pipeline: {p_name.upper()}")
        logging.info(f"==========================================")

        try:
            module = load_pipeline_module(p_name, importer=importer)
            module.run()
        except Exception as exc:
            logging.error(
                "Pipeline %s execution failed with %s.",
                p_name,
                exc.__class__.__name__,
            )
            failures.append(p_name)

        logging.info(f"Finished Pipeline: {p_name.upper()}\n")

    logging.info(f"All pipelines finished. Total elapsed time: {time.time() - start_time:.2f} seconds.")
    if failures:
        logging.error(f"The following pipelines failed: {', '.join(failures)}")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())

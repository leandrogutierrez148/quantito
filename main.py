import importlib
import logging
import os
import sys
import time

# Configure logging to output to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

PIPELINE_MODULES = {
    "real_time": "pipelines.real_time",
    "delayed": "pipelines.delayed",
    "eod": "pipelines.eod",
}

logger = logging.getLogger(__name__)


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

    logger.info(f"Main orchestrator starting execution. Pipelines selected: {pipelines_to_run}")
    failures = []

    if not pipelines_to_run:
        logger.error("No pipelines selected.")
        return 1

    for p_name in pipelines_to_run:
        logger.info(f"Executing Pipeline: {p_name.upper()}")

        try:
            module = load_pipeline_module(p_name, importer=importer)
            module.run()
        except Exception as exc:
            logger.error(
                "Pipeline %s execution failed with %s.",
                p_name,
                exc.__class__.__name__,
            )
            failures.append(p_name)

        logging.info(f"Finished Pipeline: {p_name.upper()}\n")

    logging.info(
        f"All pipelines finished. Total elapsed time: {time.time() - start_time:.2f} seconds."
    )
    if failures:
        logging.error(f"The following pipelines failed: {', '.join(failures)}")
        return 1
    return 0
    logger.info(f"Main orchestrator starting execution. Pipelines selected: {pipelines_to_run}")

    for p_name in pipelines_to_run:
        logger.info("==========================================")
        logger.info(f"Executing Pipeline: {p_name.upper()}")
        logger.info("==========================================")

        try:
            if p_name == "real_time":
                import pipelines.real_time

                # Reload module if run multiple times in same python interpreter context if needed,
                # but for CLI runs simple import and run is perfect.
                pipelines.real_time.run()
            elif p_name == "delayed":
                import pipelines.delayed

                pipelines.delayed.run()
            elif p_name == "eod":
                import pipelines.eod

                pipelines.eod.run()
            else:
                logger.warning(f"Unknown pipeline configured: '{p_name}'. Skipping.")
        except Exception as e:
            logger.error(f"Pipeline {p_name} execution failed: {e}")

        logger.info(f"Finished Pipeline: {p_name.upper()}\n")

    logger.info(
        f"All pipelines finished. Total elapsed time: {time.time() - start_time:.2f} seconds."
    )


if __name__ == "__main__":
    sys.exit(main())

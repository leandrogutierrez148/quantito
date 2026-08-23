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

logger = logging.getLogger(__name__)


def main():
    start_time = time.time()
    pipelines_env = os.getenv("PIPELINES", "real_time,delayed,eod")
    pipelines_to_run = [p.strip().lower() for p in pipelines_env.split(",") if p.strip()]

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
    main()

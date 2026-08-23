import io
import logging
import os
import pathlib
import subprocess
import sys
import types
import unittest

import main

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


class MainTests(unittest.TestCase):
    def test_all_selected_pipelines_succeed(self):
        executed = []

        def importer(module_name):
            short_name = module_name.rsplit(".", 1)[-1]
            return types.SimpleNamespace(run=lambda: executed.append(short_name))

        exit_code = main.main(
            pipelines_env="real_time,delayed,eod",
            importer=importer,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(executed, ["real_time", "delayed", "eod"])

    def test_exception_in_pipeline_returns_non_zero(self):
        executed = []

        def importer(module_name):
            short_name = module_name.rsplit(".", 1)[-1]
            if short_name == "delayed":

                def run():
                    executed.append(short_name)
                    raise RuntimeError("boom")
            else:

                def run():
                    executed.append(short_name)

            return types.SimpleNamespace(run=run)

        exit_code = main.main(
            pipelines_env="real_time,delayed,eod",
            importer=importer,
        )

        self.assertEqual(exit_code, 1)
        self.assertEqual(executed, ["real_time", "delayed", "eod"])

    def test_unknown_pipeline_counts_as_failure(self):
        exit_code = main.main(pipelines_env="unknown_pipeline")
        self.assertEqual(exit_code, 1)

    def test_empty_pipeline_selection_returns_non_zero(self):
        exit_code = main.main(pipelines_env="")
        self.assertEqual(exit_code, 1)

    def test_success_and_failure_combination_reports_aggregated_failure(self):
        executed = []

        def importer(module_name):
            short_name = module_name.rsplit(".", 1)[-1]

            def run():
                executed.append(short_name)
                if short_name == "eod":
                    raise RuntimeError("failed eod")

            return types.SimpleNamespace(run=run)

        exit_code = main.main(
            pipelines_env="real_time,delayed,eod",
            importer=importer,
        )

        self.assertEqual(exit_code, 1)
        self.assertEqual(executed, ["real_time", "delayed", "eod"])

    def test_cli_exit_code_for_unknown_pipeline(self):
        result = subprocess.run(
            [sys.executable, "main.py"],
            cwd=REPO_ROOT,
            env={**os.environ, "PIPELINES": "unknown_pipeline"},
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "Pipeline unknown_pipeline execution failed with ValueError.",
            result.stdout + result.stderr,
        )

    def test_cli_exit_code_for_empty_pipeline_selection(self):
        result = subprocess.run(
            [sys.executable, "main.py"],
            cwd=REPO_ROOT,
            env={**os.environ, "PIPELINES": ""},
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("No pipelines selected.", result.stdout + result.stderr)

    def test_logs_do_not_leak_exception_contents(self):
        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        previous_level = root_logger.level
        root_logger.setLevel(logging.INFO)

        def importer(_module_name):
            def run():
                raise RuntimeError("api_token=SHOULD_NOT_APPEAR")

            return types.SimpleNamespace(run=run)

        try:
            exit_code = main.main(
                pipelines_env="real_time",
                importer=importer,
            )
        finally:
            root_logger.removeHandler(handler)
            root_logger.setLevel(previous_level)

        log_output = log_stream.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("Pipeline real_time execution failed with RuntimeError.", log_output)
        self.assertNotIn("SHOULD_NOT_APPEAR", log_output)

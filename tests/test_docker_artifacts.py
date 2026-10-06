import pathlib
import shutil
import subprocess
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def dockerignore_includes(path_str, rules):
    included = True
    for raw_rule in rules:
        rule = raw_rule.strip()
        if not rule or rule.startswith("#"):
            continue
        negate = rule.startswith("!")
        pattern = rule[1:] if negate else rule

        matches = (
            path_str == pattern
            or path_str.startswith(f"{pattern.rstrip('/')}/")
            or pathlib.PurePosixPath(path_str).match(pattern)
        )
        if matches:
            included = negate
    return included


class DockerArtifactTests(unittest.TestCase):
    def test_dockerfile_includes_only_required_runtime_files(self):
        dockerfile = (REPO_ROOT / "Dockerfile").read_text()

        self.assertNotIn("COPY . .", dockerfile)
        self.assertIn("COPY pyproject.toml README.md ./", dockerfile)
        self.assertIn("COPY main.py ./main.py", dockerfile)
        self.assertIn("COPY engine ./engine", dockerfile)
        self.assertNotIn("COPY pipelines", dockerfile)
        self.assertNotIn("COPY utils", dockerfile)
        self.assertNotIn("eodhd-api.httpbook", dockerfile)

    def test_dockerignore_is_runtime_allowlist(self):
        rules = (REPO_ROOT / ".dockerignore").read_text().splitlines()

        self.assertTrue(dockerignore_includes("README.md", rules))
        self.assertTrue(dockerignore_includes("pyproject.toml", rules))
        self.assertFalse(dockerignore_includes("utils/eodhd-api.httpbook", rules))
        self.assertFalse(dockerignore_includes(".git/config", rules))
        self.assertTrue(dockerignore_includes("main.py", rules))
        self.assertTrue(dockerignore_includes("engine/models.py", rules))
        self.assertFalse(dockerignore_includes("pipelines/real_time.py", rules))

    def test_import_container_smoke_script_exists(self):
        script_path = REPO_ROOT / "scripts" / "import_container_smoke_test.sh"
        self.assertTrue(script_path.exists())
        script_contents = script_path.read_text()
        self.assertIn("docker build -t", script_contents)
        self.assertIn("import main, engine, engine.server", script_contents)

    def test_import_container_smoke_script(self):
        if not shutil.which("docker"):
            self.skipTest("docker CLI is not installed")

        info = subprocess.run(
            ["docker", "info"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if info.returncode != 0:
            self.skipTest("docker daemon is not available")

        subprocess.run(
            ["bash", "scripts/import_container_smoke_test.sh", "quantito-import-smoke-test"],
            cwd=REPO_ROOT,
            check=True,
        )

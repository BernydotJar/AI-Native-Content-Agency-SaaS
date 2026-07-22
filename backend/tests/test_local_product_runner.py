import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run-local-product.sh"
PACKAGE = ROOT / "package.json"
LOCAL_BUILD_LOCK = ROOT / "backend" / "requirements-local-build.lock"


class LocalProductRunnerTests(unittest.TestCase):
    def test_package_exposes_integrated_local_product_command(self):
        package = json.loads(PACKAGE.read_text())
        self.assertEqual(
            package["scripts"]["start:local"],
            "./scripts/run-local-product.sh",
        )
        source = SCRIPT.read_text()
        self.assertIn("--require-hashes -r backend/requirements.lock", source)
        self.assertIn("requirements-local-build.lock", source)
        self.assertIn("if ! install_build_toolchain", source)
        self.assertIn("-m pip wheel", source)
        self.assertTrue(LOCAL_BUILD_LOCK.is_file())
        compatibility_lock = LOCAL_BUILD_LOCK.read_text()
        self.assertIn("pip==24.3.1", compatibility_lock)
        self.assertIn("--hash=sha256:", compatibility_lock)
        self.assertIn('AGENCY_STATIC_DIR="$ROOT_DIR/dist"', source)
        self.assertIn("AGENCY_SESSION_COOKIE_SECURE=false", source)
        self.assertNotIn("set -x", source)
        self.assertNotIn("eval ", source)

    def test_runner_check_is_loopback_only_and_does_not_start_providers(self):
        environment = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "AGENCY_PYTHON_BIN": sys.executable,
            "AGENCY_IDENTITY_CREDENTIALS_JSON": json.dumps(
                [
                    {
                        "tenant_id": "local-tenant",
                        "subject_id": "local-admin",
                        "role": "admin",
                        "key_id": "local-check-v1",
                        "api_key": "local-check-only-key-1234567890",
                        "active": True,
                    }
                ]
            ),
        }
        completed = subprocess.run(
            [str(SCRIPT), "--check"],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("local_product_config=pass", completed.stdout)
        self.assertIn("host=127.0.0.1", completed.stdout)
        self.assertIn("python_version=", completed.stdout)
        self.assertIn("build_lock_strategy=primary_then_hash_locked_compatibility", completed.stdout)
        self.assertIn("external_provider_calls=not_started", completed.stdout)
        self.assertNotIn("local-check-only-key", completed.stdout)

        denied = subprocess.run(
            [str(SCRIPT), "--check"],
            cwd=ROOT,
            env={**environment, "AGENCY_HOST": "0.0.0.0"},
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        self.assertNotEqual(denied.returncode, 0)
        self.assertIn("refuses non-loopback host", denied.stderr)

    def test_runner_rejects_an_explicit_unsupported_python_before_build(self):
        with tempfile.TemporaryDirectory() as tempdir:
            fake_python = Path(tempdir) / "python3.10"
            fake_python.write_text(
                "#!/bin/sh\n"
                'if [ "${1:-}" = "--version" ]; then\n'
                "  echo 'Python 3.10.1'\n"
                "  exit 0\n"
                "fi\n"
                "exit 1\n"
            )
            fake_python.chmod(0o755)
            completed = subprocess.run(
                [str(SCRIPT), "--check"],
                cwd=ROOT,
                env={
                    "PATH": "/usr/local/bin:/usr/bin:/bin",
                    "AGENCY_PYTHON_BIN": str(fake_python),
                    "AGENCY_IDENTITY_CREDENTIALS_JSON": "[]",
                },
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
        self.assertEqual(completed.returncode, 69)
        self.assertIn("must be Python 3.11 through 3.13", completed.stderr)


if __name__ == "__main__":
    unittest.main()

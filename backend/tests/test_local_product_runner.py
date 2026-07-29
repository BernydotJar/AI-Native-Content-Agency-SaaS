import base64
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
WORKSPACE_UP = ROOT / "scripts" / "workspace-up.sh"
SOCIAL_KEY_SCRIPT = ROOT / "scripts" / "generate-social-encryption-key.py"
ENV_EXAMPLE = ROOT / ".env.example"


class LocalProductRunnerTests(unittest.TestCase):
    def test_package_exposes_integrated_local_product_command(self):
        package = json.loads(PACKAGE.read_text())
        self.assertEqual(
            package["scripts"]["start:local"],
            "./scripts/run-local-product.sh",
        )
        self.assertEqual(
            package["scripts"]["generate:social-key"],
            "python3 scripts/generate-social-encryption-key.py --env-file .env.local",
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
        self.assertIn(
            'AGENCY_MEMORY_DB:-$ROOT_DIR/.local/ai-native-content-agency-local.sqlite3',
            source,
        )
        workspace_source = WORKSPACE_UP.read_text()
        self.assertIn(
            'AGENCY_MEMORY_DB:-$ROOT_DIR/.local/ai-native-content-agency-local.sqlite3',
            workspace_source,
        )
        self.assertNotIn(
            'AGENCY_MEMORY_DB:-/tmp/ai-native-content-agency-local.sqlite3',
            workspace_source,
        )
        self.assertNotIn(
            'AGENCY_MEMORY_DB:-/tmp/ai-native-content-agency-local.sqlite3',
            source,
        )
        self.assertIn("watch-social-connection-backups.py", workspace_source)
        self.assertIn("AGENCY_CLOUDFLARE_TUNNEL_TOKEN", workspace_source)
        self.assertIn("AGENCY_CLOUDFLARE_PUBLIC_URL", workspace_source)
        self.assertIn("--token-file", workspace_source)
        self.assertNotIn('--token "$token"', workspace_source)
        self.assertNotIn(
            "stop_stale_tunnel() {\n  stop_stale_tunnel",
            workspace_source,
        )
        self.assertIn("AGENCY_SESSION_COOKIE_SAMESITE", source)
        self.assertIn("AGENCY_SESSION_COOKIE_SECURE", source)
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

    def test_runner_uses_secure_lax_cookie_for_public_https_social_callback(self):
        with tempfile.TemporaryDirectory() as tempdir:
            env_file = Path(tempdir) / ".env.local"
            env_file.write_text(
                "AGENCY_INSTAGRAM_REDIRECT_URI=https://agency.example/api/v1/social-channels/instagram/oauth/callback\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [str(SCRIPT), "--check"],
                cwd=ROOT,
                env={
                    "PATH": "/usr/local/bin:/usr/bin:/bin",
                    "AGENCY_PYTHON_BIN": sys.executable,
                    "AGENCY_ENV_FILE": str(env_file),
                    "AGENCY_IDENTITY_CREDENTIALS_JSON": "[]",
                },
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("session_cookie_secure=true", completed.stdout)
        self.assertIn("session_cookie_samesite=lax", completed.stdout)

    def test_runner_loads_untracked_env_file_without_printing_values(self):
        with tempfile.TemporaryDirectory() as tempdir:
            env_file = Path(tempdir) / ".env.local"
            env_file.write_text(
                "AGENCY_X_CONSUMER_SECRET=runner-secret-must-not-leak\n"
                "AGENCY_SOCIAL_TOKEN_ACTIVE_KEY_ID=runner-social-v1\n"
            )
            completed = subprocess.run(
                [str(SCRIPT), "--check"],
                cwd=ROOT,
                env={
                    "PATH": "/usr/local/bin:/usr/bin:/bin",
                    "AGENCY_PYTHON_BIN": sys.executable,
                    "AGENCY_ENV_FILE": str(env_file),
                    "AGENCY_IDENTITY_CREDENTIALS_JSON": "[]",
                },
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("loaded local environment: .env.local (values hidden)", completed.stdout)
        self.assertNotIn("runner-secret-must-not-leak", completed.stdout + completed.stderr)

    def test_runner_refuses_a_tracked_environment_file(self):
        completed = subprocess.run(
            [str(SCRIPT), "--check"],
            cwd=ROOT,
            env={
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "AGENCY_PYTHON_BIN": sys.executable,
                "AGENCY_ENV_FILE": str(ROOT / ".env.example"),
                "AGENCY_IDENTITY_CREDENTIALS_JSON": "[]",
            },
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        self.assertEqual(completed.returncode, 66)
        self.assertIn("refusing tracked local environment file", completed.stderr)

    def test_social_key_generator_emits_a_fresh_32_byte_base64url_key(self):
        first = subprocess.run(
            [sys.executable, str(SOCIAL_KEY_SCRIPT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout
        second = subprocess.run(
            [sys.executable, str(SOCIAL_KEY_SCRIPT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout
        self.assertNotEqual(first, second)
        line = next(
            item for item in first.splitlines()
            if item.startswith("AGENCY_SOCIAL_TOKEN_ENCRYPTION_KEYS_JSON=")
        )
        encoded_json = line.split("=", 1)[1].strip("'")
        payload = json.loads(encoded_json)
        encoded = payload["local-social-v1"]
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        self.assertEqual(len(raw), 32)
        self.assertNotIn(encoded, SOCIAL_KEY_SCRIPT.read_text())

    def test_social_key_generator_safely_updates_an_untracked_env_file(self):
        with tempfile.TemporaryDirectory() as tempdir:
            env_file = Path(tempdir) / ".env.local"
            env_file.write_text(
                "AGENCY_X_CONSUMER_KEY=\n"
                "AGENCY_SOCIAL_TOKEN_ENCRYPTION_KEYS_JSON=\n"
                "AGENCY_SOCIAL_TOKEN_ACTIVE_KEY_ID=\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [sys.executable, str(SOCIAL_KEY_SCRIPT), "--env-file", str(env_file)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            content = env_file.read_text(encoding="utf-8")
            mode = env_file.stat().st_mode & 0o777
            repeated = subprocess.run(
                [sys.executable, str(SOCIAL_KEY_SCRIPT), "--env-file", str(env_file)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("value hidden", completed.stdout)
        self.assertNotIn("local-social-v1\":", completed.stdout)
        self.assertIn("AGENCY_X_CONSUMER_KEY=", content)
        self.assertIn("AGENCY_SOCIAL_TOKEN_ACTIVE_KEY_ID=local-social-v1", content)
        self.assertIn("AGENCY_SOCIAL_TOKEN_ENCRYPTION_KEYS_JSON='{", content)
        self.assertEqual(mode, 0o600)
        self.assertEqual(repeated.returncode, 65)
        self.assertIn("already configured", repeated.stderr)

    def test_social_key_generator_refuses_a_tracked_env_file(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(SOCIAL_KEY_SCRIPT),
                "--env-file",
                str(ROOT / ".env.example"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        self.assertEqual(completed.returncode, 65)
        self.assertIn("refusing tracked environment file", completed.stderr)

    def test_env_example_keeps_social_token_bootstrap_opt_in(self):
        assignments = {}
        for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            assignments[name] = value
        self.assertEqual(assignments["AGENCY_SOCIAL_BOOTSTRAP_TENANT_ID"], "")
        self.assertEqual(assignments["AGENCY_X_USER_ACCESS_TOKEN"], "")
        self.assertEqual(assignments["AGENCY_INSTAGRAM_ACCESS_TOKEN"], "")

    def test_runner_rejects_bootstrap_tenant_without_tokens_before_build(self):
        with tempfile.TemporaryDirectory() as tempdir:
            env_file = Path(tempdir) / ".env.local"
            env_file.write_text(
                "AGENCY_SOCIAL_BOOTSTRAP_TENANT_ID=local-tenant\n"
                "AGENCY_X_CONSUMER_KEY=oauth-app-key\n"
                "AGENCY_X_CONSUMER_SECRET=oauth-app-secret\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [str(SCRIPT), "--check"],
                cwd=ROOT,
                env={
                    "PATH": "/usr/local/bin:/usr/bin:/bin",
                    "AGENCY_PYTHON_BIN": sys.executable,
                    "AGENCY_ENV_FILE": str(env_file),
                    "AGENCY_IDENTITY_CREDENTIALS_JSON": "[]",
                },
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
        self.assertEqual(completed.returncode, 65)
        self.assertIn("clear AGENCY_SOCIAL_BOOTSTRAP_TENANT_ID", completed.stderr)
        self.assertNotIn("oauth-app-secret", completed.stdout + completed.stderr)
        self.assertNotIn("building production web bundle", completed.stdout)

    def test_runner_accepts_oauth_only_configuration_without_bootstrap_tenant(self):
        with tempfile.TemporaryDirectory() as tempdir:
            env_file = Path(tempdir) / ".env.local"
            env_file.write_text(
                "AGENCY_SOCIAL_BOOTSTRAP_TENANT_ID=\n"
                "AGENCY_X_CONSUMER_KEY=oauth-app-key\n"
                "AGENCY_X_CONSUMER_SECRET=oauth-app-secret\n"
                "AGENCY_X_REDIRECT_URI=http://127.0.0.1:4175/api/v1/social-channels/x/oauth/callback\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [str(SCRIPT), "--check"],
                cwd=ROOT,
                env={
                    "PATH": "/usr/local/bin:/usr/bin:/bin",
                    "AGENCY_PYTHON_BIN": sys.executable,
                    "AGENCY_ENV_FILE": str(env_file),
                    "AGENCY_IDENTITY_CREDENTIALS_JSON": "[]",
                },
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("local_product_config=pass", completed.stdout)
        self.assertNotIn("oauth-app-secret", completed.stdout + completed.stderr)

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

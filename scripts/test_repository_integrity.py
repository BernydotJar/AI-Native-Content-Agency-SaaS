from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.repository_integrity import ROOT, _content_findings, scan


class RepositoryIntegrityTest(unittest.TestCase):
    def _temporary_repo_file(self, content: bytes, suffix: str = ".txt") -> Path:
        handle = tempfile.NamedTemporaryFile(
            dir=ROOT,
            prefix="integrity-test-",
            suffix=suffix,
            delete=False,
        )
        self.addCleanup(Path(handle.name).unlink, missing_ok=True)
        handle.write(content)
        handle.close()
        return Path(handle.name)

    def test_reports_rule_and_path_without_echoing_secret(self) -> None:
        token = b"gh" + b"p_" + (b"A" * 36)
        path = self._temporary_repo_file(b"token=" + token)

        findings = scan([path])

        self.assertEqual(findings[0]["rule"], "github_token")
        self.assertNotIn(token.decode(), str(findings))

    def test_detects_personal_path_and_credential_artifact(self) -> None:
        personal = b"/" + b"Users" + b"/example/private.txt"
        path = self._temporary_repo_file(personal, suffix=".pem")

        rules = {finding["rule"] for finding in scan([path])}

        self.assertEqual(rules, {"credential_file_extension", "macos_personal_path"})

    def test_allows_documented_placeholders(self) -> None:
        path = self._temporary_repo_file(
            b"GCP_BILLING_ACCOUNT=AAAAAA-BBBBBB-CCCCCC\n"
            b"POSTGRES_PASSWORD=compose-validation-only\n"
        )

        self.assertEqual(scan([path]), [])

    def test_history_content_helper_never_reports_the_matched_value(self) -> None:
        key = b"AKIA" + (b"A" * 16)

        findings = _content_findings(b"removed=" + key, "git-history")

        self.assertEqual(findings, [{"path": "git-history", "rule": "aws_access_key"}])
        self.assertNotIn(key.decode(), str(findings))


if __name__ == "__main__":
    unittest.main()

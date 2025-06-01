"""Tests for secret detection scanner."""

from __future__ import annotations

from pathlib import Path

from config_shepherd.models import Severity
from config_shepherd.secret_scanner import SecretScanner


class TestSecretScanner:
    def test_detects_aws_access_key(self, tmp_path: Path) -> None:
        f = tmp_path / "config.yaml"
        f.write_text("aws_key: AKIAIOSFODNN7EXAMPLE\n")
        findings = SecretScanner().scan_file(f)
        assert len(findings) >= 1
        assert any("AWS" in fi.pattern_name for fi in findings)

    def test_detects_generic_api_key(self, tmp_path: Path) -> None:
        f = tmp_path / "env.yaml"
        f.write_text("api_key: sk-1234567890abcdef\n")
        findings = SecretScanner().scan_file(f)
        assert len(findings) >= 1

    def test_detects_password(self, tmp_path: Path) -> None:
        f = tmp_path / "db.yaml"
        f.write_text("database:\n  password: super_secret_123\n")
        findings = SecretScanner().scan_file(f)
        assert len(findings) >= 1
        assert any("Password" in fi.pattern_name for fi in findings)

    def test_detects_private_key(self, tmp_path: Path) -> None:
        f = tmp_path / "key.pem"
        f.write_text("-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----\n")
        findings = SecretScanner().scan_file(f)
        assert len(findings) >= 1
        assert any("Private Key" in fi.pattern_name for fi in findings)

    def test_detects_connection_string(self, tmp_path: Path) -> None:
        f = tmp_path / "conn.yaml"
        f.write_text("db_url: postgres://admin:password@host:5432/db\n")
        findings = SecretScanner().scan_file(f)
        assert len(findings) >= 1

    def test_detects_github_token(self, tmp_path: Path) -> None:
        f = tmp_path / "ci.yaml"
        f.write_text("token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij\n")
        findings = SecretScanner().scan_file(f)
        assert len(findings) >= 1

    def test_clean_file_no_findings(self, tmp_path: Path) -> None:
        f = tmp_path / "clean.yaml"
        f.write_text("app:\n  name: my-app\n  version: 1.0.0\n")
        findings = SecretScanner().scan_file(f)
        assert findings == []

    def test_skips_binary_files(self, tmp_path: Path) -> None:
        f = tmp_path / "image.bin"
        f.write_bytes(b"\x00\x01\x02password: secret\xff\xfe")
        findings = SecretScanner().scan_file(f)
        assert findings == []

    def test_scan_directory(self, tmp_path: Path) -> None:
        (tmp_path / "a.yaml").write_text("api_key: abc123\n")
        (tmp_path / "b.yaml").write_text("app: clean\n")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "c.yaml").write_text("password: secret\n")
        findings = SecretScanner().scan_directory(tmp_path, recursive=True)
        assert len(findings) >= 2

    def test_redacted_text(self, tmp_path: Path) -> None:
        f = tmp_path / "t.yaml"
        f.write_text("password: my_long_secret_value\n")
        findings = SecretScanner().scan_file(f)
        assert findings
        redacted = findings[0].redacted_text
        assert "***" in redacted
        assert "my_long_secret_value" not in redacted

    def test_custom_patterns(self, tmp_path: Path) -> None:
        scanner = SecretScanner.from_patterns([
            ("Custom", r"CUSTOM-[A-Z]{10}", Severity.WARNING),
        ])
        f = tmp_path / "custom.txt"
        f.write_text("key: CUSTOM-ABCDEFGHIJ\n")
        findings = scanner.scan_file(f)
        assert len(findings) == 1
        assert findings[0].pattern_name == "Custom"
        assert findings[0].severity == Severity.WARNING

    def test_nonexistent_file(self) -> None:
        findings = SecretScanner().scan_file(Path("/nonexistent/file.yaml"))
        assert findings == []

    def test_finding_str(self, tmp_path: Path) -> None:
        f = tmp_path / "t.yaml"
        f.write_text("password: secret123\n")
        findings = SecretScanner().scan_file(f)
        assert findings
        text = str(findings[0])
        assert "Password" in text
        assert str(f) in text

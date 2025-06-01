"""Pattern-based secret detection in configuration files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from config_shepherd.models import SecretFinding, Severity

DEFAULT_PATTERNS: list[tuple[str, str, Severity]] = [
    ("AWS Access Key", r"(?:^|[^A-Za-z0-9/+=])AKIA[0-9A-Z]{16}(?:[^A-Za-z0-9/+=]|$)", Severity.ERROR),
    ("AWS Secret Key", r"(?i)aws[_\-]?secret[_\-]?access[_\-]?key\s*[:=]\s*\S+", Severity.ERROR),
    ("Generic API Key", r"(?i)(?:api[_\-]?key|apikey)\s*[:=]\s*\S+", Severity.ERROR),
    ("Generic Secret", r"(?i)(?:secret|secret_key)\s*[:=]\s*\S+", Severity.ERROR),
    ("Password field", r"(?i)(?:password|passwd|pwd)\s*[:=]\s*\S+", Severity.ERROR),
    ("Private Key header", r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", Severity.ERROR),
    ("Generic Token", r"(?i)(?:token|auth_token|access_token)\s*[:=]\s*\S+", Severity.WARNING),
    ("Connection String", r"(?i)(?:mysql|postgres|mongodb|redis)://\S+:\S+@\S+", Severity.ERROR),
    ("Slack Webhook", r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+", Severity.ERROR),
    ("GitHub Token", r"gh[ps]_[A-Za-z0-9_]{36,}", Severity.ERROR),
]

BINARY_CHECK_BYTES = 8192


@dataclass
class SecretScanner:
    """Configurable scanner that checks files for secret-like patterns."""

    patterns: list[tuple[str, re.Pattern[str], Severity]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.patterns:
            self.patterns = [
                (name, re.compile(regex), sev)
                for name, regex, sev in DEFAULT_PATTERNS
            ]

    @classmethod
    def from_patterns(
        cls, patterns: list[tuple[str, str, Severity]]
    ) -> SecretScanner:
        compiled = [
            (name, re.compile(regex), sev)
            for name, regex, sev in patterns
        ]
        return cls(patterns=compiled)

    def scan_text(self, text: str, source: Path) -> list[SecretFinding]:
        """Scan a string for secrets, returning all findings."""
        findings: list[SecretFinding] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            for name, pattern, sev in self.patterns:
                match = pattern.search(line)
                if match:
                    findings.append(
                        SecretFinding(
                            file=source,
                            line_number=line_number,
                            pattern_name=name,
                            matched_text=match.group(0).strip(),
                            severity=sev,
                        )
                    )
        return findings

    def scan_file(self, path: Path) -> list[SecretFinding]:
        """Scan a single file. Skips binary files gracefully."""
        path = Path(path)
        if not path.is_file():
            return []
        if _is_binary(path):
            return []
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        return self.scan_text(text, path)

    def scan_directory(self, root: Path, recursive: bool = True) -> list[SecretFinding]:
        """Scan all files under *root*."""
        root = Path(root)
        findings: list[SecretFinding] = []
        glob_pattern = "**/*" if recursive else "*"
        for path in sorted(root.glob(glob_pattern)):
            if path.is_file():
                findings.extend(self.scan_file(path))
        return findings


def _is_binary(path: Path) -> bool:
    """Heuristic check: if the first chunk contains null bytes, treat as binary."""
    try:
        chunk = path.read_bytes()[:BINARY_CHECK_BYTES]
        return b"\x00" in chunk
    except OSError:
        return True

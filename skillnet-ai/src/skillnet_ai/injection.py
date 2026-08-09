"""
Deterministic prompt-injection screening for skill packages.

The evaluator sends attacker-authored SKILL.md / references / scripts content to an
LLM judge. Skill files are third-party content pulled from arbitrary GitHub repos,
so that content can contain instructions aimed at the judge itself rather than at
the end user's agent.

This module runs *before* the judge and returns structured findings. It is
deliberately deterministic (regex + unicode inspection, no model call) so that it
cannot itself be argued out of a verdict by the content it is inspecting.

Design notes
------------
- Rules are conservative and keyed to imperative phrasing, not topic. A skill
  *about* prompt injection (a red-teaming guide, a security checklist) legitimately
  contains the words "prompt injection", so topic keywords alone are never a hit.
- Findings never mutate a rating on their own. They are surfaced to the caller and
  attached to the judge prompt as an out-of-band signal, so a human or the judge
  can weigh them. Silent auto-fail on regex is how false positives become invisible.
- Every finding carries file/line/excerpt so it is actionable and auditable.
"""

from __future__ import annotations

import base64
import binascii
import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

__all__ = [
    "InjectionFinding",
    "InjectionReport",
    "SkillInjectionScanner",
    "SEVERITY_ORDER",
]

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}

# Characters with no legitimate use in a SKILL.md that are routinely used to hide
# instructions from human reviewers while remaining visible to a tokenizer.
_ZERO_WIDTH = {
    "\u200b": "ZERO WIDTH SPACE",
    "\u200c": "ZERO WIDTH NON-JOINER",
    "\u200d": "ZERO WIDTH JOINER",
    "\u2060": "WORD JOINER",
    "\ufeff": "ZERO WIDTH NO-BREAK SPACE",
}
_BIDI_CONTROLS = {
    "\u202a": "LEFT-TO-RIGHT EMBEDDING",
    "\u202b": "RIGHT-TO-LEFT EMBEDDING",
    "\u202d": "LEFT-TO-RIGHT OVERRIDE",
    "\u202e": "RIGHT-TO-LEFT OVERRIDE",
    "\u2066": "LEFT-TO-RIGHT ISOLATE",
    "\u2067": "RIGHT-TO-LEFT ISOLATE",
    "\u2068": "FIRST STRONG ISOLATE",
}


@dataclass
class InjectionFinding:
    """A single suspected injection artifact."""

    rule_id: str
    severity: str  # "low" | "medium" | "high"
    file: str
    line: int
    excerpt: str
    message: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "excerpt": self.excerpt,
            "message": self.message,
        }


@dataclass
class InjectionReport:
    """Aggregated scan result for one skill."""

    findings: List[InjectionFinding] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.findings

    @property
    def max_severity(self) -> Optional[str]:
        if not self.findings:
            return None
        return max(self.findings, key=lambda f: SEVERITY_ORDER[f.severity]).severity

    def to_dict(self) -> Dict[str, object]:
        return {
            "clean": self.clean,
            "max_severity": self.max_severity,
            "count": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
        }

    def to_prompt_block(self, limit: int = 20) -> str:
        """Render findings for inclusion in the judge prompt as out-of-band evidence."""
        if not self.findings:
            return "[No suspected prompt-injection artifacts detected]"
        ordered = sorted(
            self.findings,
            key=lambda f: (-SEVERITY_ORDER[f.severity], f.file, f.line),
        )
        lines = [
            f"- [{f.severity.upper()}] {f.rule_id} {f.file}:{f.line} — {f.message} "
            f"| excerpt: {f.excerpt}"
            for f in ordered[:limit]
        ]
        if len(ordered) > limit:
            lines.append(f"- ...and {len(ordered) - limit} more finding(s)")
        return "\n".join(lines)


# --------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------
# Each rule: (rule_id, severity, compiled pattern, message)
# Patterns target imperative constructions aimed at a *reader model*, which is what
# separates an attack from documentation about attacks.

_TEXT_RULES = [
    (
        "SN-INJ-001",
        "high",
        re.compile(
            r"\b(ignore|disregard|forget|override|bypass)\b[^.\n]{0,40}?\b"
            r"(all\s+)?(previous|prior|above|earlier|preceding|system|original)\b"
            r"[^.\n]{0,20}?\b(instruction|prompt|rule|direction|rubric|guideline|context)s?\b",
            re.IGNORECASE,
        ),
        "Instruction-override phrasing directed at the reading model.",
    ),
    (
        "SN-INJ-002",
        "high",
        re.compile(
            r"\b(rate|score|grade|mark|classify|set|assign|report)\b[^.\n]{0,50}?"
            r"\b(safety|completeness|executability|maintainability|cost[- ]awareness|"
            r"this\s+skill|all\s+dimensions?|every\s+dimension)\b[^.\n]{0,50}?"
            r"\b(good|highest|maximum|max|perfect|safe|pass(ing)?|5\s*/\s*5)\b",
            re.IGNORECASE,
        ),
        "Attempts to dictate the evaluation verdict (self-referential grading attack).",
    ),
    (
        "SN-INJ-002",
        "high",
        re.compile(
            r"\b(good|highest|maximum|perfect|pass(ing)?)\b[^.\n]{0,30}?"
            r"\b(rating|score|grade)\b[^.\n]{0,30}?\b(on|for|across)\b[^.\n]{0,30}?"
            r"\b(all|every|each)\b[^.\n]{0,20}?\bdimensions?\b",
            re.IGNORECASE,
        ),
        "Attempts to dictate the evaluation verdict (self-referential grading attack).",
    ),
    (
        "SN-INJ-003",
        "high",
        re.compile(
            r"(<\|(im_start|im_end|system|endoftext)\|>)"
            r"|(^\s*(===+\s*)?(SYSTEM|ASSISTANT|DEVELOPER)\s*(MESSAGE|PROMPT)?\s*(===+)?\s*:?\s*$)"
            r"|(^\s*\[\s*(system|assistant|developer)\s*\]\s*:?)"
            r"|(^\s*###\s*(system|assistant)\s*(instruction|message)s?)",
            re.IGNORECASE | re.MULTILINE,
        ),
        "Forged conversation-role or system-message marker embedded in skill content.",
    ),
    (
        "SN-INJ-004",
        "high",
        re.compile(
            r"^\s*===\s*(METADATA|SKILL\.md|REFERENCES/|SCRIPTS/|"
            r"SCRIPT EXECUTION RESULTS)\s*===\s*$"
            r"|^\s*Rating scale\b"
            r"|^\s*Evaluation dimensions\b",
            re.IGNORECASE | re.MULTILINE,
        ),
        "Content forges SkillNet's own evaluation-prompt section delimiters "
        "(section-confusion / delimiter-spoofing attack).",
    ),
    (
        "SN-INJ-005",
        "medium",
        re.compile(
            r"<!--(?:(?!-->).)*?\b(ignore|disregard|you must|do not mention|"
            r"secretly|without telling|rate this|the user cannot see|hidden instruction)\b"
            r"(?:(?!-->).)*?-->",
            re.IGNORECASE | re.DOTALL,
        ),
        "HTML comment containing imperative text (hidden from rendered view).",
    ),
    (
        "SN-INJ-006",
        "medium",
        re.compile(
            r"\b(do not|don't|never)\b[^.\n]{0,30}?\b(mention|reveal|disclose|tell|report|"
            r"show|inform)\b[^.\n]{0,30}?\b(this|the user|the human|the reviewer|the operator|anyone)\b",
            re.IGNORECASE,
        ),
        "Instructs the model to conceal information from the user or reviewer.",
    ),
]

# Rules applied only to files under scripts/ (executable payload surface).
_SCRIPT_RULES = [
    (
        "SN-INJ-007",
        "high",
        re.compile(
            r"\b(os\.environ|getenv|environ\.get)\b[^\n]{0,120}?"
            r"|(\.aws/credentials|\.ssh/id_[a-z0-9_]+|\.netrc|/etc/shadow)",
            re.IGNORECASE,
        ),
        "Reads credential material or environment secrets.",
    ),
    (
        "SN-INJ-008",
        "high",
        re.compile(
            r"\b(eval|exec)\s*\(\s*(base64|bytes\.fromhex|codecs\.decode|"
            r"__import__\s*\(\s*['\"]base64)",
            re.IGNORECASE,
        ),
        "Executes decoded/obfuscated content at runtime.",
    ),
    (
        "SN-INJ-009",
        "medium",
        re.compile(
            r"\b(requests\.(post|put)|urllib\.request\.urlopen|httpx\.(post|put)|"
            r"curl\s+[^\n]*\s-(d|-data|T|-upload-file)|wget\s+[^\n]*--post-)",
            re.IGNORECASE,
        ),
        "Outbound data transmission; verify destination and payload.",
    ),
]

# A base64 blob this long inside documentation is almost never legitimate prose.
_B64_BLOB = re.compile(r"[A-Za-z0-9+/]{120,}={0,2}")


class SkillInjectionScanner:
    """Scan a skill package for content that targets the evaluating model."""

    #: Files whose content is interpolated into the judge prompt.
    TEXT_SUFFIXES = (".md", ".txt", ".rst", ".json", ".yaml", ".yml", ".toml")
    SCRIPT_SUFFIXES = (".py", ".sh", ".bash", ".js", ".ts")

    def __init__(self, max_file_bytes: int = 512_000, max_excerpt: int = 120):
        self.max_file_bytes = max_file_bytes
        self.max_excerpt = max_excerpt

    # -- public API --------------------------------------------------------

    def scan_skill(self, skill_dir: str) -> InjectionReport:
        """Walk a skill directory and scan every prompt-reachable file."""
        report = InjectionReport()
        if not os.path.isdir(skill_dir):
            return report

        for root, dirs, files in os.walk(skill_dir):
            dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", "node_modules"}]
            for name in sorted(files):
                path = os.path.join(root, name)
                rel = os.path.relpath(path, skill_dir)
                lowered = name.lower()
                if lowered.endswith(self.TEXT_SUFFIXES):
                    report.findings.extend(self._scan_file(path, rel, scripts=False))
                elif lowered.endswith(self.SCRIPT_SUFFIXES):
                    report.findings.extend(self._scan_file(path, rel, scripts=True))
        return report

    def scan_text(
        self, text: str, filename: str = "<inline>", scripts: bool = False
    ) -> List[InjectionFinding]:
        """Scan a single in-memory blob. Used for content already read by the caller."""
        findings: List[InjectionFinding] = []
        findings.extend(self._apply_rules(text, filename, _TEXT_RULES))
        if scripts:
            findings.extend(self._apply_rules(text, filename, _SCRIPT_RULES))
            findings.extend(self._scan_b64(text, filename))
        findings.extend(self._scan_hidden_unicode(text, filename))
        return self._dedupe(findings)

    # -- internals ---------------------------------------------------------

    def _scan_file(self, path: str, rel: str, scripts: bool) -> List[InjectionFinding]:
        try:
            if os.path.getsize(path) > self.max_file_bytes:
                return []
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            return []
        return self.scan_text(text, rel, scripts=scripts)

    def _apply_rules(self, text: str, filename: str, rules) -> List[InjectionFinding]:
        found: List[InjectionFinding] = []
        for rule_id, severity, pattern, message in rules:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                found.append(
                    InjectionFinding(
                        rule_id=rule_id,
                        severity=severity,
                        file=filename,
                        line=line,
                        excerpt=self._excerpt(match.group(0)),
                        message=message,
                    )
                )
        return found

    def _scan_hidden_unicode(self, text: str, filename: str) -> List[InjectionFinding]:
        found: List[InjectionFinding] = []
        seen_lines: Dict[int, set] = {}
        for idx, ch in enumerate(text):
            label = _ZERO_WIDTH.get(ch) or _BIDI_CONTROLS.get(ch)
            if label is None and 0xE0000 <= ord(ch) <= 0xE007F:
                label = "UNICODE TAG CHARACTER"
            if label is None:
                continue
            line = text.count("\n", 0, idx) + 1
            bucket = seen_lines.setdefault(line, set())
            if label in bucket:
                continue
            bucket.add(label)
            severity = "high" if label == "UNICODE TAG CHARACTER" else "medium"
            found.append(
                InjectionFinding(
                    rule_id="SN-INJ-010",
                    severity=severity,
                    file=filename,
                    line=line,
                    excerpt=f"U+{ord(ch):04X} ({label})",
                    message=(
                        "Invisible control character in skill content; may hide "
                        "instructions from human review while remaining model-readable."
                    ),
                )
            )
        return found

    def _scan_b64(self, text: str, filename: str) -> List[InjectionFinding]:
        found: List[InjectionFinding] = []
        for match in _B64_BLOB.finditer(text):
            blob = match.group(0)
            try:
                decoded = base64.b64decode(blob, validate=True).decode("utf-8", "ignore")
            except (binascii.Error, ValueError):
                continue
            printable = sum(ch.isprintable() or ch.isspace() for ch in decoded)
            if not decoded or printable / len(decoded) < 0.85:
                continue
            nested = self._apply_rules(decoded, filename, _TEXT_RULES)
            line = text.count("\n", 0, match.start()) + 1
            found.append(
                InjectionFinding(
                    rule_id="SN-INJ-011",
                    severity="high" if nested else "low",
                    file=filename,
                    line=line,
                    excerpt=self._excerpt(decoded),
                    message=(
                        "Base64 blob decodes to instruction-like text."
                        if nested
                        else "Large base64 blob decodes to readable text; inspect manually."
                    ),
                )
            )
        return found

    def _excerpt(self, raw: str) -> str:
        cleaned = " ".join(
            ch for ch in raw.replace("\n", " ").split() if unicodedata.category(ch[:1]) != "Cf"
        )
        if len(cleaned) > self.max_excerpt:
            return cleaned[: self.max_excerpt - 3] + "..."
        return cleaned

    @staticmethod
    def _dedupe(findings: Iterable[InjectionFinding]) -> List[InjectionFinding]:
        seen = set()
        out: List[InjectionFinding] = []
        for f in findings:
            key = (f.rule_id, f.file, f.line, f.excerpt)
            if key in seen:
                continue
            seen.add(key)
            out.append(f)
        return out

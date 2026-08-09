import ast
import json
import re
import logging
import os
import secrets
import shlex
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple, Callable, Iterator

from openai import OpenAI
from json_repair import repair_json
from tqdm import tqdm

from skillnet_ai.downloader import SkillDownloader
from skillnet_ai.injection import InjectionReport, SkillInjectionScanner
from skillnet_ai.prompts import SKILL_EVALUATION_PROMPT

logger = logging.getLogger(__name__)


# ==========================================================================
# Configuration and data models
# ==========================================================================

@dataclass
class EvaluatorConfig:
    """Configuration for the skill evaluator."""
    api_key: str
    base_url: str
    model: str
    max_workers: int = 5
    temperature: float = 0.3
    cache_dir: str = "./evaluate_cache_dir"
    run_scripts: bool = False
    script_timeout_sec: int = 8
    max_script_runs: int = 5
    script_python: str = "python"
    include_script_results: bool = False
    max_script_output_chars: int = 400
    github_token: Optional[str] = None
    scan_injection: bool = True


@dataclass
class Skill:
    """Unified representation of a skill."""
    path: str  # Local path to the skill root directory
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    url: Optional[str] = None  # Original URL (when created from URL)
    
    @classmethod
    def from_url(
        cls,
        url: str,
        downloader: 'SkillDownloader',
        cache_dir: str,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        **kwargs
    ) -> Tuple[Optional['Skill'], Optional[str]]:
        """
        Create a Skill from a GitHub URL.
        download fails, it will retry, finally return (None, error_msg) instead of throwing an exception.

        Returns:
            (Skill, None) success; (None, error_msg) failure.
        """
        normalized_url = cls._normalize_url(url)
        if not normalized_url:
            return None, f"Invalid GitHub URL: {url}"
        # Derive skill name from URL if not provided
        name = kwargs.get('name') or normalized_url.rstrip('/').split('/')[-1]

        # Download to local cache (with retries in evaluator)
        local_path = None
        for attempt in range(max_retries):
            local_path = downloader.download(normalized_url, target_dir=cache_dir)
            if local_path:
                break
            if attempt < max_retries - 1:
                logger.warning(
                    "Download failed (attempt %d/%d). Retrying in %.1fs...",
                    attempt + 1, max_retries, retry_delay,
                )
                time.sleep(retry_delay)
        if not local_path:
            return None, f"Failed to download after {max_retries} retries: {url}"

        return cls(
            path=local_path,
            name=name,
            url=url,
            description=kwargs.get('description'),
            category=kwargs.get('category')
        ), None
    
    @classmethod
    def from_path(cls, path: str, **kwargs) -> Tuple[Optional['Skill'], Optional[str]]:
        """Create a Skill from a local directory path.

        Returns:
            (Skill, None) success; (None, error_msg) failure.
        """
        abs_path = os.path.abspath(path)
        if not os.path.isdir(abs_path):
            return None, f"Invalid skill path: {path}"

        name = kwargs.get('name') or os.path.basename(abs_path)

        return (
            cls(
                path=abs_path,
                name=name,
                description=kwargs.get('description'),
                category=kwargs.get('category')
            ),
            None,
        )
    
    @staticmethod
    def _normalize_url(url: str) -> Optional[str]:
        """Normalize GitHub URL to /tree/ format."""
        if not url:
            return None
        if "/blob/" in url:
            return url.replace("/blob/", "/tree/")
        if "/tree/" in url:
            return url
        return None


@dataclass
class ScriptExecutionResult:
    """Result of executing a single script."""
    path: str
    status: str  # success | compiled_only | failed | timeout | skipped
    command: str
    exit_code: Optional[int] = None
    error: Optional[str] = None
    duration_sec: Optional[float] = None
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "status": self.status,
            "command": self.command,
            "exit_code": self.exit_code,
            "error": self.error,
            "duration_sec": self.duration_sec,
            "note": self.note,
        }


class ScriptRunner:
    """Execute python scripts under scripts/ with safe defaults."""

    PATH_LIKE_EXTS = {
        ".xml",
        ".json",
        ".yaml",
        ".yml",
        ".csv",
        ".tsv",
        ".txt",
        ".md",
        ".ini",
        ".toml",
        ".coverage",
        ".db",
        ".sqlite",
        ".sql",
        ".parquet",
    }

    def __init__(self, python_bin: str, timeout_sec: int, max_runs: int,
                 max_output_chars: int):
        self.python_bin = python_bin
        self.timeout_sec = timeout_sec
        self.max_runs = max_runs
        self.max_output_chars = max_output_chars

    def run_for_skill(
        self, skill_dir: str, skip_paths: Optional[set] = None
    ) -> List[ScriptExecutionResult]:
        """Execute discovered scripts, except those in ``skip_paths``.

        ``skip_paths`` holds skill-relative paths (as produced by the
        injection pre-screen) that must not be executed — they are reported
        as skipped rather than run.
        """
        skip_paths = skip_paths or set()
        scripts = self._discover_py_scripts(skill_dir)
        results: List[ScriptExecutionResult] = []
        runnable: List[str] = []

        for script_path in scripts:
            rel_path = os.path.relpath(script_path, skill_dir)
            if rel_path in skip_paths:
                results.append(self._result_skipped_high_risk(rel_path))
                continue
            runnable.append(script_path)

        for script_path in runnable[: self.max_runs]:
            results.append(self._run_script(skill_dir, script_path))

        if len(runnable) > self.max_runs:
            logger.info(
                "Found %s runnable scripts, truncated to %s for execution",
                len(runnable),
                self.max_runs
            )

        return results

    def _result_skipped_high_risk(self, rel_path: str) -> ScriptExecutionResult:
        return ScriptExecutionResult(
            path=rel_path,
            status="skipped",
            command="[not executed]",
            note=(
                "Skipped: the prompt-injection pre-screen flagged this script for "
                "credential access, obfuscated exec, or outbound data transmission. "
                "Inspect manually before running."
            ),
        )

    def _discover_py_scripts(self, skill_dir: str) -> List[str]:
        paths: List[str] = []
        for root, _, files in os.walk(skill_dir):
            if "scripts" not in root.split(os.sep):
                continue
            for filename in files:
                if filename.lower().endswith(".py"):
                    paths.append(os.path.join(root, filename))
        return sorted(paths)

    def _run_script(self, skill_dir: str, script_path: str) -> ScriptExecutionResult:
        rel_path = os.path.relpath(script_path, skill_dir)
        usage_cmd = self._build_usage_command(script_path, rel_path)
        if usage_cmd:
            missing_inputs = self._detect_missing_inputs(usage_cmd, skill_dir)
            if missing_inputs:
                compile_result = self._run_command(
                    [self.python_bin, "-m", "py_compile", rel_path],
                    skill_dir
                )
                note = f"missing inputs: {', '.join(missing_inputs)}"
                if compile_result["timed_out"]:
                    return self._result_timeout(rel_path, compile_result, note=note)
                if compile_result["exit_code"] == 0:
                    return self._result_compiled_only(rel_path, compile_result, note=note)
                return self._result_failed(rel_path, compile_result, note=note)
            run_result = self._run_command(usage_cmd, skill_dir)
            note = "usage-derived command"
            if run_result["timed_out"]:
                return self._result_timeout(rel_path, run_result, note=note)
            if run_result["exit_code"] == 0:
                return self._result_success(rel_path, run_result, note=note)
            return self._result_failed(rel_path, run_result, note=note)

        compile_result = self._run_command(
            [self.python_bin, "-m", "py_compile", rel_path],
            skill_dir
        )
        if compile_result["timed_out"]:
            return self._result_timeout(rel_path, compile_result)
        if compile_result["exit_code"] == 0:
            return self._result_compiled_only(
                rel_path,
                compile_result,
                note="no usage examples found; py_compile succeeded",
            )

        return self._result_failed(
            rel_path,
            compile_result,
            note="no usage examples found",
        )

    def _result_timeout(self, rel_path: str, result: Dict[str, Any], note: Optional[str] = None) -> ScriptExecutionResult:
        return ScriptExecutionResult(
            path=rel_path,
            status="timeout",
            command=result["command"],
            exit_code=None,
            error=result.get("error"),
            duration_sec=result["duration_sec"],
            note=note,
        )

    def _result_success(self, rel_path: str, result: Dict[str, Any], note: Optional[str] = None) -> ScriptExecutionResult:
        return ScriptExecutionResult(
            path=rel_path,
            status="success",
            command=result["command"],
            exit_code=result.get("exit_code"),
            duration_sec=result["duration_sec"],
            note=note,
        )

    def _result_compiled_only(self, rel_path: str, result: Dict[str, Any], note: Optional[str] = None) -> ScriptExecutionResult:
        return ScriptExecutionResult(
            path=rel_path,
            status="compiled_only",
            command=result["command"],
            exit_code=result.get("exit_code"),
            error=self._pick_error(result),
            duration_sec=result["duration_sec"],
            note=note,
        )

    def _result_failed(self, rel_path: str, result: Dict[str, Any], note: Optional[str] = None) -> ScriptExecutionResult:
        return ScriptExecutionResult(
            path=rel_path,
            status="failed",
            command=result["command"],
            exit_code=result.get("exit_code"),
            error=self._pick_error(result),
            duration_sec=result["duration_sec"],
            note=note,
        )

    def _build_usage_command(self, script_path: str,
                             rel_path: str) -> Optional[List[str]]:
        script_name = os.path.basename(script_path)
        usage_lines = self._extract_usage_lines(script_path, script_name)
        if not usage_lines:
            return None

        candidates: List[List[str]] = []
        for line in usage_lines:
            cmd = self._parse_usage_line(line, rel_path, script_name)
            if cmd:
                candidates.append(cmd)

        if not candidates:
            return None

        # Prefer runnable commands:
        # - Commands containing placeholder tokens like "<file>", "[options]", "{path}" are
        #   often documentation examples and not directly runnable.
        # - If placeholders exist, prefer a help-style command to at least verify the script
        #   starts up, otherwise fall back to compilation-only.
        runnable = [cmd for cmd in candidates if not self._has_placeholder_tokens(cmd)]
        for cmd in runnable:
            if not self._is_help_command(cmd):
                return cmd

        for cmd in candidates:
            if self._is_help_command(cmd):
                return cmd

        return None
    
    def _extract_usage_lines(self, script_path: str,
                             script_name: str) -> List[str]:
        try:
            with open(script_path, "r", encoding="utf-8", errors="ignore") as f:
                source = f.read()
        except Exception as e:
            logger.warning("Failed to read %s: %s", script_path, e)
            return []

        try:
            tree = ast.parse(source)
            doc = ast.get_docstring(tree) or ""
        except Exception:
            doc = ""

        if not doc:
            return []

        lines = doc.splitlines()
        usage_lines: List[str] = []
        for idx, line in enumerate(lines):
            if line.strip().lower().startswith("usage:"):
                for follow in lines[idx + 1:]:
                    if not follow.strip():
                        break
                    usage_lines.append(follow.strip())

        if usage_lines:
            return usage_lines

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(("./", "python", "python3")):
                usage_lines.append(stripped)
                continue
            if stripped.startswith(script_name):
                usage_lines.append(stripped)

        return usage_lines

    def _parse_usage_line(self, line: str, rel_path: str,
                          script_name: str) -> Optional[List[str]]:
        try:
            tokens = shlex.split(line)
        except ValueError:
            return None

        if not tokens:
            return None

        python_prefix = tokens[0].startswith("python")
        if python_prefix:
            tokens = [self.python_bin] + tokens[1:]

        script_idx = None
        for idx, token in enumerate(tokens):
            token_base = os.path.basename(token)
            if token_base == script_name:
                script_idx = idx
                break

        if script_idx is None:
            return None

        tokens[script_idx] = rel_path

        if not python_prefix:
            tokens = [self.python_bin] + tokens[script_idx:]

        return tokens

    def _iter_non_flag_tokens(self, cmd: List[str]) -> Iterator[str]:
        for token in cmd:
            if not token or token.startswith("-"):
                continue
            if token == self.python_bin:
                continue
            yield token

    def _is_help_command(self, cmd: List[str]) -> bool:
        for token in cmd:
            lowered = token.lower()
            if lowered in {"--help", "-h", "help"}:
                return True
        return False

    def _has_placeholder_tokens(self, cmd: List[str]) -> bool:
        for token in self._iter_non_flag_tokens(cmd):
            if self._is_placeholder_token(token):
                return True
        return False

    @staticmethod
    def _is_placeholder_token(token: str) -> bool:
        # Common usage placeholders: <...>, [...], {...}
        if any(ch in token for ch in ("<", ">", "[", "]", "{", "}")):
            return True
        lowered = token.strip().lower()
        return lowered in {"options", "[options]", "<options>", "{options}"}

    def _detect_missing_inputs(self, cmd: List[str], cwd: str) -> List[str]:
        missing: List[str] = []
        for token in self._iter_non_flag_tokens(cmd):
            if self._is_placeholder_token(token):
                continue
            if not self._looks_like_path(token):
                continue
            path = token if os.path.isabs(token) else os.path.join(cwd, token)
            if not os.path.exists(path):
                missing.append(token)
        return missing

    def _looks_like_path(self, token: str) -> bool:
        if "/" in token or token.startswith("."):
            return True
        _, ext = os.path.splitext(token)
        return ext.lower() in self.PATH_LIKE_EXTS

    def _run_command(self, cmd: List[str], cwd: str) -> Dict[str, Any]:
        command_str = shlex.join(cmd)
        start = time.time()
        try:
            completed = subprocess.run(
                cmd,
                cwd=cwd,
                text=True,
                capture_output=True,
                timeout=self.timeout_sec
            )
            duration = time.time() - start
            return {
                "command": command_str,
                "exit_code": completed.returncode,
                "stdout": self._truncate(completed.stdout),
                "stderr": self._truncate(completed.stderr),
                "duration_sec": round(duration, 3),
                "timed_out": False
            }
        except subprocess.TimeoutExpired:
            duration = time.time() - start
            return {
                "command": command_str,
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "duration_sec": round(duration, 3),
                "timed_out": True,
                "error": f"Timeout after {self.timeout_sec}s"
            }
        except FileNotFoundError as e:
            duration = time.time() - start
            return {
                "command": command_str,
                "exit_code": None,
                "stdout": "",
                "stderr": str(e),
                "duration_sec": round(duration, 3),
                "timed_out": False,
                "error": str(e)
            }

    def _truncate(self, text: str) -> str:
        if not text:
            return ""
        if len(text) <= self.max_output_chars:
            return text
        return text[: self.max_output_chars] + "...[truncated]"

    def _pick_error(self, *results: Dict[str, Any]) -> Optional[str]:
        for result in results:
            if not result:
                continue
            stderr = result.get("stderr") or ""
            stdout = result.get("stdout") or ""
            if stderr.strip():
                return stderr.strip()
            if stdout.strip():
                return stdout.strip()
            if result.get("error"):
                return str(result.get("error"))
        return None


# ==========================================================================
# Skill content loader
# ==========================================================================

class SkillLoader:
    """Load SKILL.md, scripts, and reference files for a skill."""

    REFERENCE_ALLOWED_EXTS = {
        ".md",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
        ".ini",
        ".toml",
        ".cfg",
        ".csv",
        ".tsv",
    }
    
    @staticmethod
    def _walk_and_load(skill_dir: str, max_files: int, max_chars: int,
                       root_filter: Callable[[str], bool],
                       file_filter: Callable[[str], bool],
                       skip_skill_md: bool) -> List[Dict[str, str]]:
        items: List[Dict[str, str]] = []
        for root, _, files in os.walk(skill_dir):
            if not root_filter(root):
                continue
            for filename in files:
                if len(items) >= max_files:
                    return items
                if skip_skill_md and filename.lower() == "skill.md":
                    continue
                if not file_filter(filename):
                    continue
                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, skill_dir)
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(max_chars)
                    items.append({"path": rel_path, "content": content})
                except Exception as e:
                    logger.warning(f"Skip {filepath}: {e}")
        return items
    
    @staticmethod
    def load_skill_md(skill_dir: str, max_chars: int = 12000) -> Optional[str]:
        """Load SKILL.md content with optional truncation."""
        path = SkillLoader._find_file(skill_dir, "skill.md")
        if not path:
            logger.warning(f"SKILL.md not found in {skill_dir}")
            return None
        
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n...[truncated]..."
        
        return content
    
    @staticmethod
    def load_scripts(skill_dir: str, max_files: int = 5, 
                    max_chars: int = 1200) -> List[Dict[str, str]]:
        """Load a sample of files under the scripts directory."""
        return SkillLoader._walk_and_load(
            skill_dir,
            max_files=max_files,
            max_chars=max_chars,
            root_filter=lambda root: "scripts" in root.split(os.sep),
            file_filter=lambda _filename: True,
            skip_skill_md=False,
        )
    
    @staticmethod
    def load_references(
        skill_dir: str,
        max_files: int = 10,
        max_chars: int = 4000,
    ) -> List[Dict[str, str]]:
        """
        Load non-script reference files for a skill.

        This is intended for files other than SKILL.md and scripts/,
        e.g. README.md, references/, assets/, etc.
        """
        def file_filter(filename: str) -> bool:
            ext = os.path.splitext(filename)[1].lower()
            return (not ext) or (ext in SkillLoader.REFERENCE_ALLOWED_EXTS)

        return SkillLoader._walk_and_load(
            skill_dir,
            max_files=max_files,
            max_chars=max_chars,
            root_filter=lambda root: "scripts" not in root.split(os.sep),
            file_filter=file_filter,
            skip_skill_md=True,
        )

    @staticmethod
    def _find_file(directory: str, filename: str) -> Optional[str]:
        """Recursively find a file in directory (case-insensitive)."""
        for root, _, files in os.walk(directory):
            for f in files:
                if f.lower() == filename.lower():
                    return os.path.join(root, f)
        return None


# ==========================================================================
# Prompt builder
# ==========================================================================

class PromptBuilder:
    """Build prompts for skill evaluation."""

    @staticmethod
    def _format_file_items(items: List[Dict[str, str]], empty_message: str) -> str:
        formatted: List[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            path = item.get("path") or "[unknown path]"
            content = item.get("content") or ""
            formatted.append(f"# {path}\n{content}\n")
        return "\n".join(formatted) if formatted else empty_message

    @staticmethod
    def _fence(body: str, nonce: str) -> str:
        """Wrap untrusted content so it cannot terminate its own section."""
        return f"{nonce}\n{body}\n{nonce}"
    
    @staticmethod
    def build(skill: Skill, skill_md: Optional[str],
              scripts: List[Dict[str, str]],
              references: Optional[List[Dict[str, str]]] = None,
              script_exec_results: Optional[List[ScriptExecutionResult]] = None,
              injection_report: Optional[InjectionReport] = None) -> str:
        """Build the evaluation prompt for a given skill."""
        nonce = f"<<<UNTRUSTED-{secrets.token_hex(8)}>>>"
        skill_md_block = skill_md or "[SKILL.md not found]"

        if references:
            references_block = PromptBuilder._format_file_items(
                references,
                "[No references or additional assets found]",
            )
        else:
            references_block = "[No references or additional assets found]"
        
        if scripts:
            scripts_block = PromptBuilder._format_file_items(
                scripts,
                "[No scripts found]",
            )
        else:
            scripts_block = "[No scripts found]"

        if script_exec_results is None:
            script_exec_block = "[Scripts not executed]"
        elif not script_exec_results:
            script_exec_block = "[No runnable python scripts found]"
        else:
            script_exec_block = "\n".join(
                PromptBuilder._format_exec_result(r)
                for r in script_exec_results
            )

        skill_md_block = PromptBuilder._fence(skill_md_block, nonce)
        references_block = PromptBuilder._fence(references_block, nonce)
        scripts_block = PromptBuilder._fence(scripts_block, nonce)
        # Script stdout/stderr is attacker-influenced (a script can print forged
        # section headers) just like the blocks above, so it gets the same fence.
        script_exec_block = PromptBuilder._fence(script_exec_block, nonce)

        injection_block = (
            injection_report.to_prompt_block()
            if injection_report is not None
            else "[Pre-screen not run]"
        )
        # The pre-screen quotes matched excerpts of skill content verbatim, so it
        # carries the same risk of forged headers/imperatives as the raw content
        # above and must be fenced too rather than left as free text next to the
        # output-format instructions.
        injection_block = PromptBuilder._fence(injection_block, nonce)

        return SKILL_EVALUATION_PROMPT.format(
            nonce=nonce,
            injection_block=injection_block,
            skill_name=skill.name,
            skill_description=skill.description or "N/A",
            category=skill.category or "N/A",
            repo_name="N/A",
            author="N/A",
            skill_md_block=skill_md_block,
            references_block=references_block,
            scripts_block=scripts_block,
            script_exec_block=script_exec_block
        )

    @staticmethod
    def _format_exec_result(result: ScriptExecutionResult) -> str:
        base = f"- {result.path}: {result.status}"
        if result.exit_code is not None:
            base += f" (exit={result.exit_code})"
        base += f" | cmd: {result.command}"
        if result.note:
            base += f" | note: {result.note}"
        if result.error:
            clean_error = " ".join(result.error.splitlines())
            base += f" | error: {clean_error}"
        return base


# ==========================================================================
# LLM client
# ==========================================================================

class LLMClient:
    """Thin wrapper around the OpenAI client for evaluation calls."""
    
    def __init__(self, config: EvaluatorConfig):
        self.client = OpenAI(api_key=config.api_key, base_url=config.base_url)
        self.model = config.model
        self.temperature = config.temperature
    
    @staticmethod
    def _parse_json_response(raw_response: Optional[str]) -> Dict[str, Any]:
        """Parse a JSON response from the LLM with multi-stage fallback.

        Handles empty responses, markdown-wrapped JSON, trailing commas,
        single-quoted keys, and other common malformations from
        OpenAI-compatible providers that do not strictly honour
        ``response_format``.
        """
        # Stage 1: empty / None check
        cleaned = (raw_response or "").strip()
        if not cleaned:
            raise ValueError("LLM returned an empty response")

        # Stage 2: strip markdown code fences (```json ... ``` or ``` ... ```)
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
        cleaned = cleaned.strip()

        # Stage 3: try standard json.loads first (fast path)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Stage 4: attempt repair via json-repair
        logger.warning(
            "JSON parsing failed, attempting repair. raw_response=%r",
            cleaned[:200],
        )
        try:
            repaired = repair_json(cleaned, return_objects=False)
            return json.loads(repaired)
        except Exception as exc:
            raise ValueError(
                f"Unable to parse LLM response as JSON even after repair: {exc}"
            ) from exc

    def evaluate(self, prompt: str) -> Dict[str, Any]:
        """Call the LLM with the given prompt and parse JSON response."""
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert evaluator of AI Agent Skills. "
                    "Follow the JSON schema and constraints exactly. "
                    "Use ONLY the provided metadata, SKILL.md, reference files, and scripts snippets. "
                    "Return ONLY a valid JSON object. Do not include markdown, explanations, or extra text."
                )
            },
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=self.temperature
            )
            raw_response = response.choices[0].message.content
            return self._parse_json_response(raw_response)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise


# ==========================================================================
# Core evaluator
# ==========================================================================

class SkillEvaluator:
    """
    Main entry point for evaluating AI skills.

    Typical usage:
        config = EvaluatorConfig(api_key="your-key")
        evaluator = SkillEvaluator(config)

        # Single skill from URL
        skill, err = Skill.from_url("https://github.com/.../skill", evaluator.downloader, config.cache_dir)
        if err:
            result = evaluator._create_error_result(err)
        else:
            result = evaluator.evaluate(skill)

        # Single skill from local path
        skill = Skill.from_path("/path/to/skill")
        result = evaluator.evaluate(skill)

        # Batch evaluation
        skills = [skill1, skill2, skill3]
        results = evaluator.evaluate_batch(skills)
    """

    #: injection.py rule ids that fire only on scripts/ files and indicate the
    #: script itself is dangerous to run (credential access, obfuscated exec,
    #: outbound data transmission) rather than merely a prompt-injection risk.
    _SCRIPT_RISK_RULE_IDS = frozenset({"SN-INJ-007", "SN-INJ-008", "SN-INJ-009"})

    def __init__(self, config: EvaluatorConfig):
        """Initialize the evaluator with configuration."""
        if not config.api_key:
            raise ValueError("API key is required")

        self.config = config
        self.downloader = SkillDownloader(api_token=config.github_token)
        self.loader = SkillLoader()
        self.prompt_builder = PromptBuilder()
        self.llm_client = LLMClient(config)
        self.script_runner = ScriptRunner(
            python_bin=config.script_python,
            timeout_sec=config.script_timeout_sec,
            max_runs=config.max_script_runs,
            max_output_chars=config.max_script_output_chars
        )

    @classmethod
    def _high_risk_script_paths(
        cls, injection_report: Optional[InjectionReport]
    ) -> set:
        """Relative paths of scripts the pre-screen flagged as unsafe to execute."""
        if injection_report is None:
            return set()
        return {
            f.file
            for f in injection_report.findings
            if f.rule_id in cls._SCRIPT_RISK_RULE_IDS
        }

    def evaluate(self, skill: Skill) -> Dict[str, Any]:
        """
        Evaluate a single skill.

        Args:
            skill: A Skill instance to evaluate.

        Returns:
            A dict containing the evaluation result.
        """
        try:
            # Load content
            skill_md = self.loader.load_skill_md(skill.path)
            scripts = self.loader.load_scripts(skill.path)
            references = self.loader.load_references(skill.path)

            # Deterministic pre-screen of untrusted skill content. This runs
            # *before* any script execution below so a script flagged for
            # credential access, obfuscated exec, or outbound transmission can
            # be skipped instead of run — a finding produced after
            # subprocess.run() has already executed the script cannot undo
            # whatever side effect (secret leak, outbound POST) it flags.
            injection_report: Optional[InjectionReport] = None
            if self.config.scan_injection:
                injection_report = SkillInjectionScanner().scan_skill(skill.path)

            # Optional script execution
            script_exec_results: Optional[List[ScriptExecutionResult]] = None
            if self.config.run_scripts:
                script_exec_results = self.script_runner.run_for_skill(
                    skill.path,
                    skip_paths=self._high_risk_script_paths(injection_report),
                )

            # Build prompt
            prompt = self.prompt_builder.build(
                skill,
                skill_md,
                scripts,
                references=references,
                script_exec_results=script_exec_results,
                injection_report=injection_report,
            )
            
            # Call LLM
            result = self.llm_client.evaluate(prompt)
            if self.config.include_script_results and script_exec_results is not None:
                result["script_execution"] = [
                    r.to_dict() for r in script_exec_results
                ]
            if injection_report is not None:
                result["prompt_injection_scan"] = injection_report.to_dict()
            return result
            
        except Exception as e:
            skill_name = getattr(skill, "name", "[unknown skill]")
            logger.exception("Evaluation failed for %s: %s", skill_name, e)
            return self._create_error_result(str(e))
    
    def evaluate_batch(self, skills: List[Skill]) -> List[Dict[str, Any]]:
        """
        Evaluate multiple skills in parallel.

        Args:
            skills: List of Skill objects.

        Returns:
            List of evaluation results in the same order as input.
        """
        results: List[Optional[Dict[str, Any]]] = [None] * len(skills)

        max_workers = max(1, int(self.config.max_workers))
        max_in_flight = max_workers * 2

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            it = iter(enumerate(skills))
            in_flight: set = set()
            future_to_idx: Dict[Any, int] = {}

            def _submit_next() -> bool:
                try:
                    idx, skill = next(it)
                except StopIteration:
                    return False
                fut = executor.submit(self.evaluate, skill)
                in_flight.add(fut)
                future_to_idx[fut] = idx
                return True

            for _ in range(min(max_in_flight, len(skills))):
                _submit_next()

            with tqdm(total=len(skills), desc="Evaluating skills") as pbar:
                try:
                    while in_flight:
                        done, pending = wait(in_flight, return_when=FIRST_COMPLETED)
                        in_flight = set(pending)
                        for fut in done:
                            idx = future_to_idx.pop(fut)
                            results[idx] = fut.result()
                            pbar.update(1)
                            if len(in_flight) < max_in_flight:
                                _submit_next()
                except KeyboardInterrupt:
                    for fut in in_flight:
                        fut.cancel()
                    executor.shutdown(wait=False, cancel_futures=True)
                    raise

        return [r if r is not None else self._create_error_result("Missing result") for r in results]
    
    def evaluate_from_url(self, url: str, **kwargs) -> Dict[str, Any]:
        """Convenience helper: create and evaluate a skill from a URL."""
        skill, err = Skill.from_url(
            url,
            self.downloader,
            self.config.cache_dir,
            **kwargs
        )
        if err:
            return self._create_error_result(err)
        return self.evaluate(skill)
    
    def evaluate_from_path(self, path: str, **kwargs) -> Dict[str, Any]:
        """Convenience helper: create and evaluate a skill from a local path."""
        skill, err = Skill.from_path(
            path, **kwargs
        )
        if err:
            return self._create_error_result(err)
        return self.evaluate(skill)
    
    @staticmethod
    def _create_error_result(error_msg: str) -> Dict[str, Any]:
        """Create a default error-shaped evaluation result."""
        error_item = {"level": "Poor", "reason": f"Evaluation failed: {error_msg}"}
        return {
            "error": error_msg,
            "safety": error_item,
            "completeness": error_item,
            "executability": error_item,
            "maintainability": error_item,
            "cost_awareness": error_item
        }


# ==========================================================================
# CLI entry point
# ==========================================================================

if __name__ == '__main__':
    """Command line entry point for batch evaluation from JSONL."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Evaluate AI Agent Skills')
    parser.add_argument('--input', required=True, help='Input JSONL file')
    parser.add_argument('--output', required=True, help='Output JSONL file')
    parser.add_argument('--api-key', help='OpenAI API key')
    parser.add_argument('--base-url', help='OpenAI API base URL')
    parser.add_argument('--github-token', help='GitHub token for downloading private repos or avoiding rate limits')
    parser.add_argument('--model', default='gpt-4o', help='Model name')
    parser.add_argument('--max-workers', type=int, default=5, help='Max workers')
    parser.add_argument('--cache-dir', default='skill_downloads', help='Cache directory')
    parser.add_argument('--limit', type=int, default=-1, help='Limit number of input records to process (0 = all)')
    parser.add_argument('--run-scripts', action='store_true',
                        help='Execute python scripts under scripts/')
    parser.add_argument('--script-timeout', type=int, default=8,
                        help='Timeout seconds per script run')
    parser.add_argument('--max-script-runs', type=int, default=5,
                        help='Max python scripts to execute per skill')
    parser.add_argument('--script-python', default='python',
                        help='Python executable for running scripts')
    parser.add_argument('--include-script-results', action='store_true',
                        help='Attach script execution results to evaluation output')
    parser.add_argument('--max-script-output-chars', type=int, default=400,
                        help='Max chars of script stdout/stderr to keep')
    
    args = parser.parse_args()
    
    def _load_records(jsonl_path: str) -> List[Dict[str, Any]]:
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            return [json.loads(line) for line in f if line.strip()]

    def _evaluate_records_streaming(
        records: List[Dict[str, Any]],
        evaluator: 'SkillEvaluator',
        config: EvaluatorConfig,
    ) -> List[Dict[str, Any]]:
        results: List[Optional[Dict[str, Any]]] = [None] * len(records)

        max_workers = max(1, int(config.max_workers))
        max_in_flight = max_workers * 2

        def _run_one(idx: int, rec: Dict[str, Any]) -> Dict[str, Any]:
            if 'skill_url' in rec:
                skill, err = Skill.from_url(
                    rec['skill_url'],
                    evaluator.downloader,
                    config.cache_dir,
                    name=rec.get('skill_name'),
                    description=rec.get('skill_description'),
                    category=rec.get('category'),
                )
                if err:
                    return evaluator._create_error_result(err)
                return evaluator.evaluate(skill)

            if 'skill_path' in rec:
                skill, err = Skill.from_path(
                    rec['skill_path'],
                    name=rec.get('skill_name'),
                    description=rec.get('skill_description'),
                    category=rec.get('category'),
                )
                if err:
                    return evaluator._create_error_result(err)
                return evaluator.evaluate(skill)

            return evaluator._create_error_result("Record must have 'skill_url' or 'skill_path'")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            it = iter(enumerate(records))
            in_flight: set = set()
            future_to_idx: Dict[Any, int] = {}

            def _submit_next() -> bool:
                try:
                    idx, rec = next(it)
                except StopIteration:
                    return False
                fut = executor.submit(_run_one, idx, rec)
                in_flight.add(fut)
                future_to_idx[fut] = idx
                return True

            for _ in range(min(max_in_flight, len(records))):
                _submit_next()

            with tqdm(total=len(records), desc="Downloading & evaluating") as pbar:
                try:
                    while in_flight:
                        done, pending = wait(in_flight, return_when=FIRST_COMPLETED)
                        in_flight = set(pending)
                        for fut in done:
                            idx = future_to_idx.pop(fut)
                            results[idx] = fut.result()
                            pbar.update(1)
                            if len(in_flight) < max_in_flight:
                                _submit_next()
                except KeyboardInterrupt:
                    for fut in in_flight:
                        fut.cancel()
                    executor.shutdown(wait=False, cancel_futures=True)
                    raise

        return [r if r is not None else evaluator._create_error_result("Missing result") for r in results]
    
    def _write_outputs(records: List[Dict[str, Any]], output_jsonl_path: str) -> str:
        with open(output_jsonl_path, 'w', encoding='utf-8') as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        json_path = output_jsonl_path.replace('.jsonl', '.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({str(i): rec for i, rec in enumerate(records)},
                     f, ensure_ascii=False, indent=2)
        return json_path

    config = EvaluatorConfig(
        api_key=args.api_key or os.getenv('API_KEY'),
        base_url=args.base_url or os.getenv('BASE_URL'),
        model=args.model,
        max_workers=args.max_workers,
        cache_dir=args.cache_dir,
        run_scripts=args.run_scripts,
        script_timeout_sec=args.script_timeout,
        max_script_runs=args.max_script_runs,
        script_python=args.script_python,
        include_script_results=args.include_script_results,
        max_script_output_chars=args.max_script_output_chars,
        github_token=args.github_token or os.getenv('GITHUB_TOKEN'),
    )
    evaluator = SkillEvaluator(config)
    records = _load_records(args.input)
    if args.limit and args.limit > 0:
        records = records[: args.limit]

    results = _evaluate_records_streaming(records, evaluator, config)
    for rec, result in zip(records, results):
        rec['evaluation'] = result
    json_path = _write_outputs(records, args.output)
    
    print(f"✓ Evaluated {len(results)} skills")
    print(f"✓ Results saved to {args.output} and {json_path}")
import getpass
import json
import logging
import os
import shutil
import sys
from contextlib import redirect_stdout
from importlib.metadata import version
from pathlib import Path
from typing import Any

import requests
import typer
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from skillnet_ai.core.config import config_path, redact, resolve_settings, save_config
from skillnet_ai.core.llm import error_details
from skillnet_ai.core.models import AnalysisOptions, RouteOptions
from skillnet_ai.core.validation import DIMENSIONS, validate_evaluation, validate_skill
from skillnet_ai.interfaces.client import SkillNetClient

app = typer.Typer(help="SkillNet AI CLI Tool", no_args_is_help=True)
console = Console()


@app.command()
def ui(
    skills_dir: Path | None = typer.Option(
        None, "--skills-dir", help="Open a local skills folder."
    ),
    port: int = typer.Option(8765, min=1, max=65535),
    browser: bool = typer.Option(True, "--browser/--no-browser"),
    dev: bool = typer.Option(False, help="Allow the Vite development UI on localhost:5173."),
):
    """Browse local skills and analysis results in your browser; no model calls."""
    try:
        from skillnet_ai.web.server import serve
    except ModuleNotFoundError as exc:
        if exc.name not in {"fastapi", "starlette", "uvicorn"}:
            raise
        console.print('Install the web extra: pip install "skillnet-ai[ui]"', markup=False)
        raise typer.Exit(1) from exc
    try:
        serve(skills_dir=skills_dir, port=port, open_browser=browser, dev=dev)
    except (OSError, ValueError) as exc:
        _fail(exc, False)


class RedactedFormatter(logging.Formatter):
    def format(self, record):
        return redact(super().format(record))


@app.callback(invoke_without_command=True)
def main(version_flag: bool = typer.Option(False, "--version", is_eager=True)):
    """Search, download, create and evaluate reusable skills."""
    if version_flag:
        typer.echo(version("skillnet-ai"))
        raise typer.Exit()
    logger = logging.getLogger("skillnet_ai")
    for handler in list(logger.handlers):
        if getattr(handler, "_skillnet_cli", False):
            logger.removeHandler(handler)
    handler = logging.StreamHandler()
    handler._skillnet_cli = True
    handler.setFormatter(RedactedFormatter("%(levelname)s: %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False


def _json_safe(value: Any):
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump())
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _emit(data, json_output: bool, *, error=None):
    if json_output:
        # ASCII escapes keep redirected JSON portable in Windows legacy codepages.
        typer.echo(json.dumps({"ok": error is None, "data": _json_safe(data), "error": error}))
    elif error:
        diagnostics = Console(stderr=True)
        diagnostics.print(f"Error: {error['message']}", markup=False)
        diagnostics.print(error["hint"], markup=False)
        if data is not None:
            diagnostics.print_json(data=_json_safe(data))


def _fail(exc, json_output, data=None):
    _emit(data, json_output, error=error_details(exc))
    raise typer.Exit(code=1)


@app.command()
def search(
    q: str = typer.Argument(...),
    mode: str = typer.Option("keyword", help="keyword or vector"),
    category: str | None = typer.Option(None),
    limit: int = typer.Option(20, min=1, max=50),
    page: int = typer.Option(1, min=1),
    min_stars: int = typer.Option(0, min=0),
    sort_by: str = typer.Option("relevance", help="relevance, stars or recent; descending"),
    threshold: float = typer.Option(0.8, min=0, max=1),
    json_output: bool = typer.Option(False, "--json"),
):
    """Search SkillNet; no LLM key required."""
    try:
        with redirect_stdout(sys.stderr):
            results = SkillNetClient().search(
                q,
                mode=mode,
                category=category,
                limit=limit,
                page=page,
                min_stars=min_stars,
                sort_by=sort_by,
                threshold=threshold,
            )
    except Exception as exc:
        _fail(exc, json_output)
    if json_output:
        _emit(results, True)
    elif not results:
        console.print("No results found.")
    else:
        table = Table(title="Search Results", show_lines=True)
        for name in (
            "Skill / Source",
            "Category",
            "Repo Stars",
            "Description",
            "Evaluation",
            "URL",
        ):
            table.add_column(name)
        for item in results:
            identity = Text(item.skill_name, style="bold", overflow="fold")
            if item.repo_name:
                identity.append(f"\n{item.repo_name}", style="default")
            if item.skill_dir:
                directory = item.skill_dir
                if item.repo_name:
                    directory = directory.removeprefix(item.repo_name + "/")
                    if item.skill_dir.rstrip("/") == item.repo_name:
                        directory = "."
                identity.append(f"\n{directory}", style="default")
            ratings = (
                "\n".join(
                    f"{d}: {item.evaluation.get(d, {}).get('level', 'N/A')}" for d in DIMENSIONS
                )
                if item.evaluation
                else "N/A"
            )
            table.add_row(
                identity,
                item.category or "",
                str(item.stars),
                item.skill_description or "",
                ratings,
                item.skill_url or "",
            )
        console.print(table)


@app.command()
def download(
    url: str = typer.Argument(...),
    target_dir: str = typer.Option(".", "--target-dir", "-d"),
    token: str | None = typer.Option(
        None, "--token", "-t", help="Prefer GITHUB_TOKEN over a shell argument."
    ),
    mirror: str | None = typer.Option(None, "--mirror", "-m"),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Replace an existing skill after complete download."
    ),
    json_output: bool = typer.Option(False, "--json"),
):
    """Download and structurally validate a GitHub skill folder."""
    try:
        with redirect_stdout(sys.stderr):
            path = SkillNetClient(github_token=token).download(
                url, target_dir=target_dir, mirror_url=mirror, overwrite=overwrite
            )
        _emit({"path": path}, json_output)
        if not json_output:
            console.print(f"Downloaded and structurally validated: {path}", markup=False)
    except Exception as exc:
        _fail(exc, json_output)


@app.command()
def create(
    trajectory_file: Path | None = typer.Argument(None),
    github: str | None = typer.Option(None, "--github", "-g"),
    office: Path | None = typer.Option(None, "--office", "-o"),
    prompt: str | None = typer.Option(None, "--prompt", "-p"),
    output_dir: Path = typer.Option(Path("./generated_skills"), "--output-dir", "-d"),
    model: str | None = typer.Option(None, "--model", "-m"),
    max_files: int = typer.Option(50, min=1),
    auto_evaluate: bool = typer.Option(False, "--evaluate/--no-evaluate"),
    json_mode: str | None = typer.Option(
        None, "--json-mode", help="auto, on or off for evaluation JSON mode."
    ),
    json_output: bool = typer.Option(False, "--json"),
):
    """Create from exactly one source; optionally evaluate the resulting skills."""
    data = {"paths": [], "validation": {}, "evaluations": {}}
    try:
        if sum(x is not None for x in (trajectory_file, github, office, prompt)) != 1:
            raise ValueError(
                "Provide exactly one source: trajectory file, --github, --office or --prompt."
            )
        kwargs = {"output_dir": output_dir, "model": model, "max_files": max_files}
        if trajectory_file is not None:
            kwargs["trajectory_content"] = trajectory_file.read_text(encoding="utf-8")
            if not kwargs["trajectory_content"].strip():
                raise ValueError("Trajectory file is empty.")
        elif github is not None:
            kwargs["github_url"] = github
        elif office is not None:
            kwargs["office_file"] = str(office)
        else:
            kwargs["prompt"] = prompt
        with redirect_stdout(sys.stderr):
            client = SkillNetClient(json_mode=json_mode)
            paths = client.create(**kwargs)
        data["paths"] = [str(Path(p).resolve()) for p in paths]
        if not paths:
            raise ValueError("No skills were generated. Check the input and model response.")
        for path in data["paths"]:
            data["validation"][path] = validate_skill(path)
        if any(not v["valid"] for v in data["validation"].values()):
            raise ValueError(
                "Generated skills failed structural validation; inspect validation errors and retained paths."
            )
        if auto_evaluate:
            for path in data["paths"]:
                try:
                    with redirect_stdout(sys.stderr):
                        report = validate_evaluation(client.evaluate(path, model=model))
                    data["evaluations"][path] = {"ok": True, "report": report, "error": None}
                except Exception as exc:
                    data["evaluations"][path] = {
                        "ok": False,
                        "report": None,
                        "error": error_details(exc),
                    }
            if any(not r["ok"] for r in data["evaluations"].values()):
                raise ValueError(
                    "Skills were created, but evaluation failed. Retry evaluation on the retained paths."
                )
    except Exception as exc:
        if not data["paths"]:
            data["paths"] = [str(Path(p).resolve()) for p in getattr(exc, "created_paths", [])]
        _fail(exc, json_output, data)
    _emit(data, json_output)
    if not json_output:
        for path in data["paths"]:
            console.print(f"Created and structurally validated: {path}", markup=False)
            if path in data["evaluations"]:
                _display_evaluation_report(path, data["evaluations"][path]["report"])
        console.print("Model evaluation is advisory; verify the skill on a real task.")


@app.command()
def evaluate(
    target: str = typer.Argument(...),
    name: str | None = typer.Option(None),
    category: str | None = typer.Option(None),
    description: str | None = typer.Option(None),
    model: str | None = typer.Option(None, "--model", "-m"),
    max_workers: int = typer.Option(5, min=1),
    json_mode: str | None = typer.Option(None, "--json-mode"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Evaluate a local skill or GitHub URL through the configured model API."""
    try:
        with redirect_stdout(sys.stderr):
            report = SkillNetClient(json_mode=json_mode).evaluate(
                target,
                name=name,
                category=category,
                description=description,
                model=model,
                max_workers=max_workers,
            )
            validate_evaluation(report)
        _emit(report, json_output)
        if not json_output:
            _display_evaluation_report(target, report)
    except Exception as exc:
        _fail(exc, json_output)


@app.command("validate")
def validate_command(
    skill_dir: Path = typer.Argument(...),
    strict: bool = typer.Option(False, "--strict", help="Also fail on portability warnings."),
    json_output: bool = typer.Option(False, "--json"),
):
    """Check skill structure locally, without a model call or script execution."""
    report = validate_skill(skill_dir)
    if not report["valid"] or (strict and report["warnings"]):
        _fail(ValueError("Skill validation found issues."), json_output, report)
    _emit(report, json_output)
    if not json_output:
        console.print("Structure valid.")
        for warning in report["warnings"]:
            console.print(warning, markup=False)


@app.command()
def configure(
    base_url: str | None = typer.Option(None, "--base-url"),
    model: str | None = typer.Option(None, "--model"),
    api_key_env: str | None = typer.Option(
        None, "--api-key-env", help="Name of an environment variable, not the key."
    ),
    api_key_stdin: bool = typer.Option(False, "--api-key-stdin"),
    github_token_env: str | None = typer.Option(None, "--github-token-env"),
    skillnet_api_url: str | None = typer.Option(None, "--skillnet-api-url"),
    github_mirror: str | None = typer.Option(None, "--github-mirror"),
    json_mode: str | None = typer.Option(None, "--json-mode"),
    embedding_base_url: str | None = typer.Option(None, "--embedding-base-url"),
    embedding_model: str | None = typer.Option(None, "--embedding-model"),
    embedding_api_key_env: str | None = typer.Option(None, "--embedding-api-key-env"),
    explorer_base_url: str | None = typer.Option(None, "--explorer-base-url"),
    explorer_model: str | None = typer.Option(None, "--explorer-model"),
    explorer_api_key_env: str | None = typer.Option(None, "--explorer-api-key-env"),
    explorer_backend: str | None = typer.Option(None, "--explorer-backend"),
    interactive: bool = typer.Option(False, "--interactive"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Save optional user settings; prompts only with --interactive."""
    try:
        if api_key_env and api_key_stdin:
            raise ValueError("Choose --api-key-env or --api-key-stdin, not both.")
        updates = {
            k: v
            for k, v in {
                "base_url": base_url,
                "model": model,
                "skillnet_api_url": skillnet_api_url,
                "github_mirror": github_mirror,
                "json_mode": json_mode,
                "embedding_base_url": embedding_base_url,
                "embedding_model": embedding_model,
                "explorer_base_url": explorer_base_url,
                "explorer_model": explorer_model,
                "explorer_backend": explorer_backend,
            }.items()
            if v is not None
        }
        for field, env in (
            ("api_key", api_key_env),
            ("github_token", github_token_env),
            ("embedding_api_key", embedding_api_key_env),
            ("explorer_api_key", explorer_api_key_env),
        ):
            if env is not None:
                if not os.environ.get(env):
                    raise ValueError(f"Environment variable {env} is empty or absent.")
                updates[field] = os.environ[env]
        if api_key_stdin:
            key = sys.stdin.readline().strip()
            if not key:
                raise ValueError("No API key supplied on stdin.")
            updates["api_key"] = key
        if interactive:
            if not sys.stdin.isatty():
                raise ValueError(
                    "Interactive setup requires a terminal. Use flags, environment variables or stdin."
                )
            settings = resolve_settings(**updates)
            with redirect_stdout(sys.stderr):
                updates["base_url"] = (
                    input(f"Model API base URL [{settings.base_url}]: ").strip()
                    or settings.base_url
                )
                updates["model"] = input(f"Model [{settings.model}]: ").strip() or settings.model
                key_prompt = (
                    "API key (Enter to keep existing): "
                    if settings.api_key
                    else "API key (saved in your user config): "
                )
                key = getpass.getpass(key_prompt).strip()
                if key:
                    updates["api_key"] = key
                elif not settings.api_key:
                    raise ValueError("API key is empty; configuration was not saved.")
        if not updates:
            raise ValueError(
                "Provide configuration flags or run skillnet configure --interactive in a terminal."
            )
        path = save_config(updates)
        _emit({"path": str(path), "updated": sorted(updates)}, json_output)
        if not json_output:
            console.print(f"Saved user configuration: {path}", markup=False)
    except Exception as exc:
        _fail(exc, json_output)


@app.command()
def doctor(
    check_network: bool = typer.Option(False, "--check-network"),
    check_llm: bool = typer.Option(
        False, "--check-llm", help="Send one small potentially billable model request."
    ),
    check_explorer: bool = typer.Option(
        False,
        "--check-explorer",
        help="Run a billable SDK exploration and structured-output check.",
    ),
    json_output: bool = typer.Option(False, "--json"),
):
    """Inspect local setup. Network and LLM checks are opt-in."""
    data = {}
    try:
        settings = resolve_settings()
        from skillnet_ai.core.config import local_checks

        data = {
            "version": version("skillnet-ai"),
            "python": sys.executable,
            "cli": shutil.which("skillnet"),
            "config_path": str(config_path()),
            "settings": settings.public(),
            "checks": {},
            "routing": local_checks(settings),
            "missing_for_create_evaluate": [] if settings.api_key else ["API_KEY"],
            "hint": "Run configure for missing model settings. Search/public download need no LLM key.",
        }
        with redirect_stdout(sys.stderr):
            if check_network:
                SkillNetClient().search("pdf", limit=1)
                data["checks"]["search"] = "passed"
                response = requests.get("https://api.github.com/rate_limit", timeout=15)
                response.raise_for_status()
                data["checks"]["github"] = "passed"
            if check_llm:
                if not settings.api_key:
                    raise ValueError("API_KEY is required for --check-llm.")
                from openai import OpenAI

                from skillnet_ai.core.llm import chat_completion

                response = chat_completion(
                    OpenAI(
                        api_key=settings.api_key,
                        base_url=settings.base_url,
                        timeout=30,
                        max_retries=0,
                    ),
                    model=settings.model,
                    messages=[{"role": "user", "content": "Reply with OK only."}],
                )
                if not response.choices or not response.choices[0].message.content:
                    raise ValueError("Model returned no content.")
                data["checks"]["llm"] = "passed"
            if check_explorer:
                from skillnet_ai.router.router import check_explorer_runtime

                check_explorer_runtime(settings)
                data["checks"]["explorer"] = "passed"
        _emit(data, json_output)
        if not json_output:
            console.print_json(data=data)
    except Exception as exc:
        _fail(exc, json_output, data)


def _display_evaluation_report(target_name: str, data: dict):
    """Helper to render the JSON evaluation result into a nice Rich UI."""
    console.print(
        f"\n[bold underline]Evaluation Report: {os.path.basename(target_name)}[/bold underline]\n"
    )

    # Dimensions to display
    dimensions = ["safety", "completeness", "executability", "maintainability", "cost_awareness"]

    # Create a grid of panels
    panels = []
    for dim in dimensions:
        info = data.get(dim, {})
        level = info.get("level", "Unknown")
        reason = info.get("reason", "No details provided.")

        # Color coding based on level
        color = "white"
        if "Excellent" in level:
            color = "green"
        elif "Good" in level:
            color = "blue"
        elif "Fair" in level:
            color = "yellow"
        elif "Poor" in level:
            color = "red"

        panel_content = f"[bold]{level}[/bold]\n\n[dim]{reason}[/dim]"
        panels.append(Panel(panel_content, title=f"[{color}]{dim.title()}[/{color}]", expand=True))

    console.print(Columns(panels, equal=True, expand=True))

    # Display Score if present
    overall_score = data.get("overall_score")
    if overall_score:
        score_color = "green" if overall_score >= 8 else "yellow" if overall_score >= 5 else "red"
        console.print(
            f"\n[bold]Overall Score:[/bold] [{score_color}]{overall_score}/10[/{score_color}]"
        )

    # Summary
    summary = data.get("summary")
    if summary:
        console.print(Panel(summary, title="Executive Summary", border_style="cyan"))


@app.command()
def analyze(
    skills_dir: Path = typer.Argument(..., exists=True, file_okay=False),
    output_dir: Path | None = typer.Option(None, "--output-dir"),
    model: str | None = typer.Option(None, "--model", "-m"),
    max_workers: int = typer.Option(4, "--max-workers", min=1),
    candidate_limit: int = typer.Option(8, "--candidate-limit", min=1),
    embedding_batch_size: int = typer.Option(8, "--embedding-batch-size", min=1),
    reasoning_effort: str | None = typer.Option(None, "--reasoning-effort"),
    timeout: float = typer.Option(120, "--timeout", min=0.001),
    json_mode: str = typer.Option("on", "--json-mode", help="on or off; no automatic downgrade."),
    force: bool = typer.Option(False, "--force"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Build a reusable scenario graph and Wiki from local skill folders."""
    try:
        options = AnalysisOptions(
            max_workers=max_workers,
            candidate_limit=candidate_limit,
            embedding_batch_size=embedding_batch_size,
            reasoning_effort=reasoning_effort,
            timeout=timeout,
            json_mode=json_mode,
        )
        with redirect_stdout(sys.stderr):
            result = SkillNetClient().analyze(
                skills_dir, output_dir=output_dir, model=model, options=options, force=force
            )
        _emit(result, json_output)
        if not json_output:
            console.print_json(data=_json_safe(result))
    except Exception as exc:
        _fail(exc, json_output)


@app.command()
def route(
    query: str = typer.Argument(...),
    index_dir: Path = typer.Option(..., "--index-dir", exists=True, file_okay=False),
    k: int = typer.Option(5, "--k", min=1),
    backend: str | None = typer.Option(None, "--backend", help="claude, codex or dsh"),
    seed_limit: int = typer.Option(24, "--seed-limit", min=1),
    candidate_limit: int = typer.Option(100, "--candidate-limit", min=1),
    max_depth: int = typer.Option(2, "--max-depth", min=0),
    timeout: float = typer.Option(300, "--timeout", min=0.001),
    max_turns: int = typer.Option(24, "--max-turns", min=1),
    json_output: bool = typer.Option(False, "--json"),
):
    """Choose up to k task-relevant skills using a configured Agent SDK."""
    try:
        if backend not in {None, "claude", "codex", "dsh"}:
            raise ValueError("backend must be claude, codex or dsh")
        options = RouteOptions(
            seed_limit=seed_limit,
            candidate_limit=candidate_limit,
            max_depth=max_depth,
            timeout=timeout,
            max_turns=max_turns,
        )
        with redirect_stdout(sys.stderr):
            result = SkillNetClient().route(
                query, index_dir=index_dir, k=k, backend=backend, options=options
            )
        _emit(result, json_output)
        if not json_output:
            console.print_json(data=_json_safe(result))
    except Exception as exc:
        _fail(exc, json_output)

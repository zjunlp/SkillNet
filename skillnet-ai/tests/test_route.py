"""Routing and SDK contracts; all model and agent calls stay offline."""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import threading
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from pydantic import RootModel, SecretStr
from typer.testing import CliRunner

from skillnet_ai import Endpoint, RouteOptions, SkillNetClient
from skillnet_ai.core.config import ENVIRONMENT
from skillnet_ai.core.models import (
    AnalyzedSkill,
    Exploration,
    GraphSnapshot,
    Relation,
    SkillProfile,
    SkillSelection,
)
from skillnet_ai.interfaces.cli import app
from skillnet_ai.router import explorer as explorer_module
from skillnet_ai.router.explorer import ClaudeExplorer, CodexExplorer, DshExplorer

ENDPOINT = Endpoint(api_key=SecretStr("test-key"), base_url="https://model.test/v1", model="test")


def selection(skill_id: str = "stats") -> SkillSelection:
    """A small SDK response; paths must still be resolved by SkillNet."""
    return SkillSelection.model_validate(
        {
            "skills": [
                {
                    "skill_id": skill_id,
                    "reason": "The user already has CSV.",
                }
            ],
        }
    )


@pytest.fixture
def index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Persist three skill records without using analysis or any model."""
    np = pytest.importorskip("numpy")
    from skillnet_ai.router import router
    from skillnet_ai.router.index import build_bm25

    for variable in ENVIRONMENT.values():
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("SKILLNET_CONFIG", str(tmp_path / "config.json"))
    for prefix in ("EMBEDDING_", "SKILLNET_EXPLORER_"):
        monkeypatch.setenv(prefix + "API_KEY", "test-key")
        monkeypatch.setenv(prefix + "BASE_URL", ENDPOINT.base_url)
        monkeypatch.setenv(prefix + "MODEL", ENDPOINT.model)
    skills = []
    for key, text in {
        "stats": "Compute statistics from CSV.",
        "extract": "Extract CSV from PDF.",
        "alternative": "Extract CSV using another PDF engine.",
    }.items():
        profile = SkillProfile.model_validate(
            {
                "capability": {"text": text, "evidence": [{"line": 1}]},
                "when_to_use": [],
                "inputs": [],
                "outputs": [],
                "scenarios": [],
                "constraints": [],
                "tools": [],
            }
        )
        skills.append(
            AnalyzedSkill(
                skill_id=key,
                name=key,
                path=str(tmp_path / "original" / key),
                source=text,
                content_hash=key,
                profile=profile,
            )
        )
    relations = [
        Relation.model_validate(
            {
                "source": "extract",
                "target": target,
                "type": kind,
                "contexts": [
                    {
                        "scenario": "CSV analysis",
                        "explanation": "A CSV handoff or alternative.",
                        "conditions": [],
                        "source_evidence": [{"line": 1}],
                        "target_evidence": [{"line": 1}],
                    }
                ],
            }
        )
        for target, kind in (("stats", "compose_with"), ("alternative", "similar_to"))
    ]
    graph = GraphSnapshot(
        embedding_model=ENDPOINT.model,
        embedding_base_url=ENDPOINT.base_url,
        skills=skills,
        relations=relations,
    )
    snapshot = tmp_path / "snapshot-test"
    snapshot.mkdir()
    (snapshot / "graph.json").write_text(graph.model_dump_json(), encoding="utf-8")
    (tmp_path / "CURRENT").write_text(snapshot.name, encoding="utf-8")
    np.savez(
        snapshot / "embeddings.npz",
        ids=[s.skill_id for s in skills],
        vectors=[[1.0, 0.0], [0.0, 1.0], [0.0, 1.0]],
    )
    build_bm25(skills, snapshot / "bm25.sqlite")
    monkeypatch.setattr(router, "embed", lambda *args, **kwargs: [[1.0, 0.0]])
    return tmp_path


@pytest.mark.parametrize("supported", [True, False])
@pytest.mark.parametrize("backend", ["claude", "codex", "dsh"])
def test_route_selects_from_snapshot(
    index: Path, monkeypatch: pytest.MonkeyPatch, supported: bool, backend: str
) -> None:
    """Retrieval expands the graph, but does not force related skills or fill k."""
    from skillnet_ai.router import router as explorer

    def explore(
        self: object, root: Path, query: str, k: int, endpoint: Endpoint, options: RouteOptions
    ) -> Exploration:
        assert all(
            (root / f"sources/{key}.md").is_file() for key in ("stats", "extract", "alternative")
        )
        assert json.loads((root / "relations.json").read_text())[0]["source"] == "extract"
        answer = selection() if supported else SkillSelection(skills=[])
        return Exploration(answer)

    monkeypatch.setattr(type(explorer.backend_for(backend)), "explore", explore)
    result = SkillNetClient().route(
        "statistics from existing CSV" if supported else "edit a video",
        index_dir=index,
        backend=backend,
        options=RouteOptions(seed_limit=1, candidate_limit=3),
    )
    assert [s.skill_id for s in result.skills] == (["stats"] if supported else [])
    assert set(result.model_dump()) == {"skills", "usage"}
    if supported:
        assert result.skills[0].path == str(index / "original/stats")
        assert set(result.skills[0].model_dump()) == {"skill_id", "name", "path", "reason"}
        assert not Path(result.skills[0].path).exists()  # Routing uses the source snapshot.
    cli = CliRunner().invoke(
        app, ["route", "statistics CSV", "--index-dir", str(index), "--backend", backend, "--json"]
    )
    assert cli.exit_code == 0 and json.loads(cli.stdout)["ok"] is True
    assert set(json.loads(cli.stdout)["data"]) == {"skills", "usage"}
    assert "evidence" not in cli.stdout


@pytest.mark.parametrize("problem", ["unknown", "duplicate", "limit"])
def test_route_rejects_unsupported_selection(index: Path, problem: str) -> None:
    """Selection needs known, unique IDs within the requested limit."""
    from skillnet_ai.router.index import load_snapshot
    from skillnet_ai.router.router import validate_selection

    answer = selection("missing" if problem == "unknown" else "stats")
    if problem == "duplicate":
        answer.skills *= 2
    elif problem == "limit":
        answer.skills.extend(selection("extract").skills)
    with pytest.raises(ValueError):
        validate_selection(
            Exploration(answer),
            load_snapshot(index)[1].skills,
            1 if problem == "limit" else 5,
        )


@pytest.mark.parametrize("problem", ["model", "dimension"])
def test_embedding_mismatch_fails(
    index: Path, monkeypatch: pytest.MonkeyPatch, problem: str
) -> None:
    """An incompatible index must fail before starting an Explorer."""
    from skillnet_ai.router import router

    def unexpected(*args: object, **kwargs: object) -> None:
        pytest.fail("An incompatible embedding must not start an Explorer")

    monkeypatch.setattr(router, "explore", unexpected)
    monkeypatch.setattr(router, "embed", lambda *args, **kwargs: [[1.0, 0.0, 0.0]])
    embedding = ENDPOINT.model_copy(update={"model": "other"}) if problem == "model" else ENDPOINT
    with pytest.raises(ValueError, match="endpoint/model" if problem == "model" else "dimension"):
        SkillNetClient().route("task", index_dir=index, embedding=embedding)


@pytest.mark.parametrize("timeout", [False, True])
def test_claude_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, timeout: bool) -> None:
    """Exercise SDK options, tool permissions, structured output and timeout cleanup."""
    sdk = ModuleType("claude_agent_sdk")
    sdk.ClaudeAgentOptions = sdk.HookMatcher = SimpleNamespace
    sdk.ResultMessage = type("ResultMessage", (SimpleNamespace,), {})
    closed = threading.Event()

    async def query(
        *, prompt: AsyncIterator[dict], options: SimpleNamespace
    ) -> AsyncIterator[object]:
        try:
            assert [item async for item in prompt]
            assert options.model == ENDPOINT.model and options.setting_sources == []
            assert options.env["ANTHROPIC_BASE_URL"] == ENDPOINT.base_url
            assert options.output_format["schema"]["additionalProperties"] is False
            assert set(options.output_format["schema"]["properties"]) == {"skills"}
            assert set(options.output_format["schema"]["$defs"]["Selection"]["properties"]) == {
                "skill_id",
                "reason",
            }
            if timeout:
                await asyncio.Event().wait()
            hook = options.hooks["PreToolUse"][0]
            assert hook.matcher == "Read|LS|Glob|Grep"
            denied = await hook.hooks[0](
                {"tool_name": "Read", "tool_input": {"file_path": "../outside"}}, None, {}
            )
            assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"
            read = {"tool_name": "Read", "tool_input": {"file_path": "sources/stats.md"}}
            allowed = await hook.hooks[0](read, None, {})
            assert allowed["hookSpecificOutput"]["permissionDecision"] == "allow"
            yield sdk.ResultMessage(
                is_error=False,
                structured_output=selection().model_dump(),
                usage={"input_tokens": 5},
            )
        finally:
            closed.set()

    sdk.query = query
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", sdk)
    if timeout:
        with pytest.raises(TimeoutError):
            ClaudeExplorer().explore(tmp_path, "task", 1, ENDPOINT, RouteOptions(timeout=0.05))
    else:
        result = ClaudeExplorer().explore(tmp_path, "task", 1, ENDPOINT, RouteOptions())
        assert result.selection == selection()
        assert result.usage == {"input_tokens": 5}
    assert closed.is_set()


@pytest.mark.parametrize("failure", [None, "provider", "timeout", "outside", "tool", "windows"])
def test_codex_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str | None
) -> None:
    """Exercise parsed SDK tool events and close the session on all exit paths."""
    sdk, types = ModuleType("openai_codex"), ModuleType("openai_codex.types")
    sdk.CodexConfig, types.ReasoningEffort = SimpleNamespace, str
    sdk.ApprovalMode, sdk.Sandbox = (
        SimpleNamespace(deny_all="never"),
        SimpleNamespace(read_only="read-only"),
    )
    closed = threading.Event()
    if failure == "windows":
        monkeypatch.setattr(explorer_module, "sys", SimpleNamespace(platform="win32"))

    def event(method: str, payload: dict[str, object]) -> SimpleNamespace:
        return SimpleNamespace(method=method, payload=RootModel[dict](payload))

    class Turn:
        def stream(self) -> Iterator[SimpleNamespace]:
            if failure == "timeout":
                assert closed.wait(2)
                return
            if failure == "provider":
                raise RuntimeError("provider failed")
            item = {
                "type": "commandExecution",
                "cwd": str(tmp_path),
                "exitCode": None,
                "commandActions": [
                    {
                        "type": "unknown" if failure in {"tool", "windows"} else "search",
                        "path": "../outside" if failure == "outside" else "sources/stats.md",
                        "command": "python -V",
                    }
                ],
            }
            if failure == "windows":
                item["commandActions"][0]["command"] = explorer_module.POWERSHELL_UTF8_PREFIX + (
                    "Get-Content -LiteralPath 'sources/stats.md' -Encoding UTF8"
                )
            yield event("item/started", {"item": item})
            yield event("item/completed", {"item": {**item, "exitCode": 0}})
            yield event(
                "item/completed",
                {
                    "item": {
                        "type": "agentMessage",
                        "phase": "final_answer",
                        "text": selection().model_dump_json(),
                    }
                },
            )
            yield event("turn/completed", {"turn": {"status": "completed"}})

    class Codex:
        def __init__(self, *, config: SimpleNamespace) -> None:
            assert config.env["OPENAI_API_KEY"] == "test-key"
            assert {
                "features.plugins=false",
                "features.remote_plugin=false",
            } <= set(config.config_overrides)

        def __enter__(self) -> "Codex":
            return self

        def login_api_key(self, key: str) -> None:
            assert key == "test-key"

        def thread_start(self, **kwargs: object) -> SimpleNamespace:
            assert kwargs["sandbox"] == "read-only" and kwargs["ephemeral"] is True
            assert kwargs["config"]["model_providers"]["skillnet"]["base_url"] == ENDPOINT.base_url
            return SimpleNamespace(turn=self.turn)

        def turn(self, prompt: str, **kwargs: object) -> Turn:
            assert kwargs["output_schema"]["additionalProperties"] is False
            assert set(kwargs["output_schema"]["properties"]) == {"skills"}
            assert set(kwargs["output_schema"]["$defs"]["Selection"]["properties"]) == {
                "skill_id",
                "reason",
            }
            return Turn()

        def close(self) -> None:
            closed.set()

    sdk.Codex = Codex
    monkeypatch.setitem(sys.modules, "openai_codex", sdk)
    monkeypatch.setitem(sys.modules, "openai_codex.types", types)
    options = RouteOptions(timeout=0.05 if failure == "timeout" else 300)
    if failure and failure != "windows":
        error = {
            "provider": RuntimeError,
            "timeout": TimeoutError,
            "outside": ValueError,
            "tool": ValueError,
        }[failure]
        with pytest.raises(error):
            CodexExplorer().explore(tmp_path, "task", 1, ENDPOINT, options)
    else:
        result = CodexExplorer().explore(tmp_path, "task", 1, ENDPOINT, options)
        assert result.selection == selection()
    assert closed.is_set()


@pytest.mark.parametrize("prefix", ["", explorer_module.POWERSHELL_UTF8_PREFIX])
@pytest.mark.parametrize("platform", ["win32", "linux", "darwin"])
@pytest.mark.parametrize(
    ("command", "allowed"),
    [
        ("Get-Content -LiteralPath 'sources/stats notes.md' -Encoding UTF8", True),
        ("Get-Content -LiteralPath 'sources/中文 notes.md' -Encoding UTF8", True),
        ("Get-ChildItem -LiteralPath '.' -Name", True),
        ("Get-Content -LiteralPath '../outside.md' -Encoding UTF8", False),
        ("Get-Content -LiteralPath 'Env:OPENAI_API_KEY' -Encoding UTF8", False),
        ("Get-Content -LiteralPath '~/outside.md' -Encoding UTF8", False),
        ("Get-ChildItem -LiteralPath '.' -Name; Remove-Item 'index.md'", False),
        ("Get-Content -LiteralPath 'index.md' -Encoding UTF8 | Invoke-Expression", False),
    ],
)
def test_powershell_wiki_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prefix: str,
    platform: str,
    command: str,
    allowed: bool,
) -> None:
    monkeypatch.setattr(explorer_module, "sys", SimpleNamespace(platform=platform))
    item = {
        "cwd": str(tmp_path),
        "commandActions": [{"type": "unknown", "command": prefix + command}],
    }
    with nullcontext() if allowed and platform == "win32" else pytest.raises(ValueError):
        explorer_module.validate_wiki_command(item, tmp_path)


@pytest.mark.parametrize("quote", ["\u2018", "\u2019", "\u201a", "\u201b"])
@pytest.mark.parametrize("prefix", ["", explorer_module.POWERSHELL_UTF8_PREFIX])
@pytest.mark.parametrize(
    ("cmdlet", "argument"), [("Get-Content", "-Encoding UTF8"), ("Get-ChildItem", "-Name")]
)
def test_powershell_rejects_typographic_quote_breakout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    quote: str,
    prefix: str,
    cmdlet: str,
    argument: str,
) -> None:
    """PowerShell treats typographic single quotes as string delimiters too."""
    monkeypatch.setattr(explorer_module, "sys", SimpleNamespace(platform="win32"))
    command = f"{prefix}{cmdlet} -LiteralPath 'index.md{quote}; Write-Output marker; #x' {argument}"
    item = {"cwd": str(tmp_path), "commandActions": [{"type": "unknown", "command": command}]}
    with pytest.raises(ValueError, match="literal PowerShell"):
        explorer_module.validate_wiki_command(item, tmp_path)


@pytest.mark.parametrize("phase", ["launch", "initialize", "before_prompt"])
def test_dsh_deadline_prevents_late_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    """An expired startup must never proceed to a model request."""
    sdk = ModuleType("deepseek_harness")
    now = [0.0]
    closed = []
    calls = []
    monkeypatch.setattr(explorer_module, "time", SimpleNamespace(monotonic=lambda: now[0]))

    if phase == "before_prompt":

        class ImmediateTimer:
            def __init__(self, seconds: float, callback: Callable[[], None]) -> None:
                self.callback = callback

            def start(self) -> None:
                now[0] = 4
                self.callback()

            def cancel(self) -> None:
                pass

            def join(self) -> None:
                pass

            def is_alive(self) -> bool:
                return False

        monkeypatch.setattr(
            explorer_module,
            "threading",
            SimpleNamespace(Event=threading.Event, Timer=ImmediateTimer),
        )

    class Harness:
        def __init__(self, **kwargs: object) -> None:
            self.client = SimpleNamespace(
                start=self.launch,
                config=SimpleNamespace(initialize_timeout_seconds=3, request_timeout_seconds=3),
            )

        def launch(self) -> None:
            if phase == "launch":
                now[0] = 4

        def start_session(self) -> "Harness":
            if phase == "initialize":
                now[0] = 4
            return self

        def run(self, prompt: str) -> SimpleNamespace:
            calls.append(prompt)
            return SimpleNamespace(
                finish_reason="completed", final_response=selection().model_dump_json()
            )

        def close(self) -> None:
            closed.append(True)

    sdk.DeepSeekHarness = Harness
    monkeypatch.setitem(sys.modules, "deepseek_harness", sdk)
    with pytest.raises(TimeoutError, match="exceeded 3 seconds"):
        DshExplorer().explore(tmp_path, "task", 1, ENDPOINT, RouteOptions(timeout=3))
    assert calls == []
    assert closed


def test_dsh_reports_provider_error_without_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Report the last turn's error while redacting the configured credential."""
    sdk = ModuleType("deepseek_harness")

    class Harness:
        def __init__(self, **kwargs: object) -> None:
            self.client = SimpleNamespace(start=lambda: None, config=SimpleNamespace())

        def start_session(self) -> "Harness":
            return self

        def run(self, prompt: str) -> SimpleNamespace:
            return SimpleNamespace(
                finish_reason="error",
                events=[
                    {
                        "type": "turn/end",
                        "data": {
                            "reason": {
                                "kind": "error",
                                "error": {
                                    "code": "AUTH",
                                    "status": 401,
                                    "message": "Invalid credential: test-key\nTry another key.",
                                },
                            }
                        },
                    }
                ],
            )

        def close(self) -> None:
            pass

    sdk.DeepSeekHarness = Harness
    monkeypatch.setitem(sys.modules, "deepseek_harness", sdk)
    with pytest.raises(RuntimeError) as caught:
        DshExplorer().explore(tmp_path, "task", 1, ENDPOINT, RouteOptions())
    message = str(caught.value)
    assert "AUTH" in message and "401" in message and "Invalid credential" in message
    assert "test-key" not in message and "\n" not in message


@pytest.mark.parametrize(
    ("name", "expected"),
    [("claude", ClaudeExplorer), ("codex", CodexExplorer), ("dsh", DshExplorer)],
)
def test_explorer_backend_dispatch(name: str, expected: type) -> None:
    from skillnet_ai.router.router import backend_for

    assert isinstance(backend_for(name), expected)


def test_dsh_requires_optional_sdk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "deepseek_harness", None)
    with pytest.raises(ImportError, match=r"skillnet-ai\[graph,dsh\]"):
        DshExplorer().explore(tmp_path, "task", 1, ENDPOINT, RouteOptions())


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "timeout",
        "invalid",
        "provider",
        "interrupted",
        "cleanup",
        "failed_cleanup",
        "timer_start",
    ],
)
def test_dsh_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str | None) -> None:
    """Check runtime configuration, response validation and cleanup on every exit path."""
    sdk = ModuleType("deepseek_harness")
    closed = threading.Event()
    state_dirs = []
    options = RouteOptions(timeout=0.1 if failure == "timeout" else 300, read_limit=5, max_turns=2)
    if failure == "timer_start":

        class FailingTimer(threading.Timer):
            def start(self) -> None:
                raise RuntimeError("timer start failed")

        monkeypatch.setattr(
            explorer_module, "threading", SimpleNamespace(Event=threading.Event, Timer=FailingTimer)
        )

    class Harness:
        def __init__(self, **kwargs: object) -> None:
            assert kwargs["api_key"] == "test-key"
            assert kwargs["base_url"] == ENDPOINT.base_url
            assert kwargs["model"] == ENDPOINT.model
            assert kwargs["provider"] == "deepseek-official"
            assert kwargs["profile"] == "sdk-minimal"
            assert kwargs["cwd"] == str(tmp_path)
            assert kwargs["reasoning_effort"] == "high"
            state_dir = Path(kwargs["dsh_home"])
            state_dirs.append(state_dir)
            assert not state_dir.is_relative_to(tmp_path)
            patch = json.loads(Path(kwargs["patches"][0]).read_text())
            assert {row["id"] for row in patch if row.get("disabled")} == {
                "persistent-bash",
                "persistent-pwsh",
                "tool-fs",
                "tool-working-directory",
                "plugin-package-inventory-deepseek",
            }
            assert {"id": "session-log-deepseek", "config": {"enabled": False}} in patch
            assert (
                patch[-1]["insert"][0]["name"]
                == Path(explorer_module.__file__).with_name("dsh.mjs").as_uri()
            )
            env = kwargs["env"]
            assert env["SKILLNET_WIKI_ROOT"] == str(tmp_path)
            assert env["SKILLNET_WIKI_READ_LIMIT"] == "5"
            assert env["SKILLNET_WIKI_MAX_STEPS"] == "2"
            assert "read_wiki" in env["DSH_SYSTEM_PROMPT"]
            assert json.dumps(SkillSelection.model_json_schema()) in env["DSH_SYSTEM_PROMPT"]
            self.client = SimpleNamespace(start=lambda: None, config=SimpleNamespace())

        def start_session(self) -> "Harness":
            assert 0 < self.client.config.initialize_timeout_seconds <= options.timeout
            return self

        def run(self, prompt: str) -> SimpleNamespace:
            assert 0 < self.client.config.request_timeout_seconds <= options.timeout
            assert "task" in prompt
            if failure == "timeout":
                assert closed.wait(2), "The deadline must close an active runtime."
                raise RuntimeError("runtime closed")
            if failure in {"provider", "failed_cleanup"}:
                raise RuntimeError("provider failed")
            if failure == "interrupted":
                raise KeyboardInterrupt
            return SimpleNamespace(
                finish_reason="completed",
                final_response="invalid JSON"
                if failure == "invalid"
                else selection().model_dump_json(),
            )

        def close(self) -> None:
            closed.set()
            if failure in {"cleanup", "failed_cleanup"}:
                raise RuntimeError("cleanup failed")

    sdk.DeepSeekHarness = Harness
    monkeypatch.setitem(sys.modules, "deepseek_harness", sdk)
    errors = {
        "timeout": (TimeoutError, "exceeded"),
        "invalid": (ValueError, "Invalid JSON"),
        "provider": (RuntimeError, "provider failed"),
        "interrupted": (KeyboardInterrupt, None),
        "cleanup": (RuntimeError, "cleanup failed"),
        "failed_cleanup": (RuntimeError, "provider failed"),
        "timer_start": (RuntimeError, "timer start failed"),
    }
    if failure is None:
        result = DshExplorer().explore(tmp_path, "task", 1, ENDPOINT, options)
        assert result.selection == selection()
        assert result.usage is None
    else:
        error, message = errors[failure]
        with pytest.raises(error, match=message):
            DshExplorer().explore(tmp_path, "task", 1, ENDPOINT, options)
    assert closed.is_set()
    assert all(not directory.exists() for directory in state_dirs)


def test_dsh_wiki_tools(tmp_path: Path) -> None:
    """Run the shipped JavaScript against real files without a model or SDK."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the Wiki plugin test.")
    root = tmp_path / "wiki"
    root.mkdir()
    (root / "index.md").write_text("Wiki contents", encoding="utf-8")
    (root / "sources").mkdir()
    (tmp_path / "outside.md").write_text("outside", encoding="utf-8")
    plugin = Path(explorer_module.__file__).with_name("dsh.mjs")
    result = subprocess.run(
        [
            node,
            "--input-type=module",
            "-e",
            r"""
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
const { apply } = await import(process.argv[1]);
const root = process.env.SKILLNET_WIKI_ROOT;
const tools = new Map();
let guard, step;
apply({
  tools: {
    register(tool) { tools.set(tool.name, tool); },
    guard(callback) { guard = callback; },
  },
  on(event, callback) {
    assert.equal(event, 'agent/pre-step');
    step = callback;
  },
});
const exec = { signal: new AbortController().signal };
const read = file => tools.get('read_wiki').execute({ path: file }, exec);
const list = () => tools.get('list_wiki').execute({ path: '.' }, exec);
assert.deepEqual([...tools.keys()], ['read_wiki', 'list_wiki']);
assert.equal(guard({ name: 'read_wiki' }), undefined);
assert.equal(guard({ name: 'list_wiki' }), undefined);
assert.match(guard({ name: 'bash' }), /Only read-only/);
assert.throws(() => read(path.join(root, 'index.md')), /relative Wiki path/);
assert.throws(() => read('../outside.md'), /outside the task Wiki/);
if (process.platform !== 'win32') {
  fs.symlinkSync('../outside.md', path.join(root, 'escape.md'));
  assert.throws(() => read('escape.md'), /outside the task Wiki/);
}
assert.throws(() => read('.'), /regular Wiki file/);
assert.throws(() => tools.get('read_wiki').execute(
  { path: 'index.md' }, { signal: AbortSignal.abort() },
));
assert.equal(read('index.md'), 'Wiki contents');
assert.equal(read('index.md'), 'Wiki contents');
assert.throws(() => read('index.md'), /read budget exceeded/);
for (let i = 0; i < 3; i++) {
  const listing = list().split('\n');
  assert(listing.includes('index.md'));
  assert(listing.includes('sources/'));
}
assert.throws(list, /listing budget exceeded/);
assert.equal(step({}, () => 'next'), 'next');
assert.equal(step({}, () => 'next'), 'next');
assert.throws(() => step({}, () => assert.fail('step limit bypassed')), /step budget exceeded/);
""",
            plugin.as_uri(),
        ],
        env={
            **os.environ,
            "SKILLNET_WIKI_ROOT": str(root),
            "SKILLNET_WIKI_READ_LIMIT": "2",
            "SKILLNET_WIKI_MAX_STEPS": "2",
        },
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr

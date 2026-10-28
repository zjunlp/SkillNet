"""Offline DSH lifecycle, configuration and actual Wiki-tool policy checks."""

import json
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import SecretStr, ValidationError
from typer.testing import CliRunner

from skillnet_ai import Endpoint, RouteOptions
from skillnet_ai.core.config import Settings, local_checks, read_config, save_config
from skillnet_ai.interfaces.cli import app
from skillnet_ai.router.dsh import DshExplorer
from skillnet_ai.router.router import backend_for

ENDPOINT = Endpoint(api_key=SecretStr("test-key"), base_url="https://model.test", model="test")
RESPONSE = '{"skills":[{"skill_id":"csv","reason":"Checks required columns."}]}'


def fake_sdk(
    monkeypatch,
    *,
    response=RESPONSE,
    finish="completed",
    block=False,
    startup_error=False,
    close_error=False,
):
    """Capture SDK ownership while exercising the real adapter and watchdog."""
    instances = []

    class Harness:
        def __init__(self, **kwargs):
            self.options = kwargs
            self.closed = threading.Event()
            self.close_calls = 0
            instances.append(self)

        def start(self):
            assert Path(self.options["dsh_home"]).is_dir()
            assert self.options["dsh_home"] != self.options["cwd"]
            assert "test-key" not in Path(self.options["patches"][0]).read_text(encoding="utf-8")
            if startup_error:
                raise RuntimeError("startup failed")

        def run(self, prompt):
            self.prompt = prompt
            if block:
                assert self.closed.wait(3)
                raise RuntimeError("runtime closed")
            return SimpleNamespace(finish_reason=finish, final_response=response)

        def close(self):
            self.close_calls += 1
            self.closed.set()
            if close_error:
                raise RuntimeError("cleanup failed")

    monkeypatch.setitem(sys.modules, "deepseek_harness", SimpleNamespace(DeepSeekHarness=Harness))
    return instances


def test_dsh_owns_isolated_minimal_runtime(tmp_path, monkeypatch):
    instances = fake_sdk(monkeypatch)
    answer = DshExplorer().explore(tmp_path, "Find a CSV checker", 1, ENDPOINT, RouteOptions())
    runtime = instances[0]
    assert answer.selection.skills[0].skill_id == "csv"
    assert answer.usage is None
    assert runtime.options["profile"] == "sdk-minimal"
    assert runtime.options["env"]["SKILLNET_WIKI_ROOT"] == str(tmp_path.resolve())
    assert runtime.options["env"]["SKILLNET_WIKI_READ_LIMIT"] == "4"
    assert runtime.options["reasoning_effort"] == "high"
    assert runtime.options["max_tokens"] == 8192
    assert json.loads(runtime.prompt) == {"task": "Find a CSV checker"}
    assert runtime.close_calls == 1
    assert not Path(runtime.options["dsh_home"]).exists()


@pytest.mark.parametrize(
    ("response", "finish", "error"),
    [
        ("not json", "completed", ValidationError),
        (RESPONSE, "error", RuntimeError),
        ("```json\n" + RESPONSE + "\n```", "completed", ValidationError),
    ],
)
def test_dsh_rejects_failed_or_unstructured_completion(
    tmp_path, monkeypatch, response, finish, error
):
    instances = fake_sdk(monkeypatch, response=response, finish=finish)
    with pytest.raises(error):
        DshExplorer().explore(tmp_path, "task", 1, ENDPOINT, RouteOptions())
    assert instances[0].close_calls == 1


def test_dsh_wall_clock_timeout_closes_runtime(tmp_path, monkeypatch):
    instances = fake_sdk(monkeypatch, block=True)
    with pytest.raises(TimeoutError, match="exceeded"):
        DshExplorer().explore(tmp_path, "task", 1, ENDPOINT, RouteOptions(timeout=0.05))
    assert instances[0].close_calls == 1
    assert not Path(instances[0].options["dsh_home"]).exists()


def test_dsh_startup_failure_closes_runtime(tmp_path, monkeypatch):
    instances = fake_sdk(monkeypatch, startup_error=True)
    with pytest.raises(RuntimeError, match="startup failed"):
        DshExplorer().explore(tmp_path, "task", 1, ENDPOINT, RouteOptions())
    assert instances[0].close_calls == 1
    assert not Path(instances[0].options["dsh_home"]).exists()


def test_dsh_cleanup_failure_is_not_a_success(tmp_path, monkeypatch):
    fake_sdk(monkeypatch, close_error=True)
    with pytest.raises(RuntimeError, match="cleanup failed"):
        DshExplorer().explore(tmp_path, "task", 1, ENDPOINT, RouteOptions())


@pytest.mark.parametrize(
    ("effort", "mapped"), [("low", "low"), ("medium", "high"), ("high", "max")]
)
def test_dsh_reasoning_mapping(tmp_path, monkeypatch, effort, mapped):
    instances = fake_sdk(monkeypatch)
    DshExplorer().explore(tmp_path, "task", 1, ENDPOINT, RouteOptions(reasoning_effort=effort))
    assert instances[0].options["reasoning_effort"] == mapped


def test_dsh_dependency_is_optional(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "deepseek_harness", None)
    with pytest.raises(ImportError, match=r"skillnet-ai\[graph,dsh\]"):
        DshExplorer().explore(tmp_path, "task", 1, ENDPOINT, RouteOptions())


def test_dsh_config_and_cli_choice(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILLNET_CONFIG", str(tmp_path / "config.json"))
    save_config({"explorer_backend": "dsh"})
    assert read_config()["explorer_backend"] == "dsh"
    assert isinstance(backend_for("dsh"), DshExplorer)
    assert "dsh" in local_checks(Settings())["dependencies"]
    response = CliRunner().invoke(app, ["route", "--help"])
    assert response.exit_code == 0
    assert "dsh" in response.output


def test_wiki_tools_enforce_paths_and_budgets(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is needed to exercise the JavaScript Wiki tool policy")
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "index.md").write_text("a CSV checker", encoding="utf-8")
    (tmp_path / "private.txt").write_text("outside Wiki", encoding="utf-8")
    try:
        (wiki / "escape").symlink_to(tmp_path / "private.txt")
        symlink = True
    except OSError:
        symlink = False
    from skillnet_ai.router import dsh

    policy = Path(dsh.__file__).with_name("dsh_wiki.mjs")
    script = r"""
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
process.env.SKILLNET_WIKI_ROOT = process.argv[2];
process.env.SKILLNET_WIKI_READ_LIMIT = '2';
process.env.SKILLNET_WIKI_MAX_STEPS = '2';
const tools = new Map(); let guard; let preStep;
const {apply} = await import(pathToFileURL(process.argv[1]).href);
apply({tools: {register(t) {tools.set(t.name, t);}, guard(g) {guard = g;}},
       on(name, handler) {assert.equal(name, 'agent/pre-step'); preStep = handler;}});
const exec = {signal: new AbortController().signal};
const read = args => tools.get('read_wiki').execute(args, exec);
const list = args => tools.get('list_wiki').execute(args, exec);
assert.match(list({path: '.'}), /index.md/);
assert.throws(() => read({path: '../private.txt'}), /outside/);
assert.throws(() => read({path: process.argv[2] + '/index.md'}), /relative/);
if (process.argv[3] === 'yes') assert.throws(() => read({path: 'escape'}), /outside/);
assert.throws(() => read({path: 'index.md', offset: -1}), /range/);
assert.match(read({path: 'index.md', limit: 1}), /More content/);
assert.equal(read({path: 'index.md', offset: 2}), 'CSV checker');
assert.throws(() => read({path: 'index.md'}), /budget/);
list({path: '.'}); list({path: '.'});
assert.throws(() => list({path: '.'}), /budget/);
assert.equal(guard({name: 'read_wiki'}), undefined);
for (const name of ['pwsh', 'bash', 'write', 'read_image', 'unknown']) assert.ok(guard({name}));
const decision = {kind: 'enter', messages: []};
assert.equal(preStep({}, () => decision), decision);
assert.equal(preStep({}, () => decision), decision);
assert.throws(() => preStep({}, () => decision), /step budget/);
"""
    subprocess.run(
        [
            node,
            "--input-type=module",
            "-e",
            script,
            str(policy),
            str(wiki),
            "yes" if symlink else "no",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

<div align="center">

# skillnet-ai

**The Python SDK and CLI package for SkillNet.**

[![PyPI version](https://badge.fury.io/py/skillnet-ai.svg)](https://pypi.org/project/skillnet-ai/)
[![Downloads](https://img.shields.io/pypi/dm/skillnet-ai.svg)](https://pypi.org/project/skillnet-ai/)
[![GitHub stars](https://img.shields.io/github/stars/zjunlp/SkillNet?style=social)](https://github.com/zjunlp/SkillNet)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

[Website](http://skillnet.openkg.cn/) · [GitHub](https://github.com/zjunlp/SkillNet) · [PyPI](https://pypi.org/project/skillnet-ai/)

</div>

---

## What Is SkillNet?

`skillnet-ai` provides the Python SDK and CLI for SkillNet, with six operations for working with reusable agent skills:

- **Search** for skills by keyword or semantic intent.
- **Download** skill folders and their resources from GitHub.
- **Create** structured skill packages from prompts, execution traces, repositories, or documents.
- **Evaluate** skill quality across safety, completeness, executability, maintainability, and cost awareness.
- **Analyze** local skill capabilities, usage scenarios, and relationships to build a reusable graph.
- **Route** a task through a local skill Wiki and return up to `k` skills with selection reasons.

Search and public downloads need no API key. Create, evaluate, and analyze use an
OpenAI-compatible Chat Completions endpoint. Analyze also needs an embedding
endpoint; route uses that same embedding endpoint and a separately configured
Claude, Codex or DeepSeek Harness SDK.

The optional [browser interface](#browser-interface) opens local skills and saved
analysis results with `skillnet ui`.

For the full project overview, research context, integrations, and roadmap, see the [main SkillNet repository](https://github.com/zjunlp/SkillNet).

---

## Installation

Requires Python 3.10 or newer.

```bash
pip install skillnet-ai
```

Install optional dependencies for analysis and routing:

```bash
pip install "skillnet-ai[graph]"         # scenario analysis
pip install "skillnet-ai[graph,claude]"  # analysis and routing via Claude
pip install "skillnet-ai[graph,codex]"   # analysis and routing via Codex
pip install "skillnet-ai[graph,dsh]"     # analysis and routing via DeepSeek Harness
```

---

## Quick Start

```python
from skillnet_ai import SkillNetClient

client = SkillNetClient()

results = client.search(q="pdf", limit=5)
for skill in results:
    print(skill.skill_name, skill.skill_url)

skill = next((item for item in results if item.skill_url), None)
if skill is not None:
    local_path = client.download(skill.skill_url, target_dir="./my_skills")
    print(local_path)
```

Equivalent CLI:

```bash
skillnet search "pdf" --limit 5
skillnet download <skill_url> -d ./my_skills
```

---

## Feature Overview

| Feature | SDK | CLI | External services |
| :-- | :-- | :-- | :-- |
| Search skills | `client.search(...)` | `skillnet search ...` | Public search API |
| Download skills | `client.download(...)` | `skillnet download ...` | GitHub; token optional for public repos |
| Create skills | `client.create(...)` | `skillnet create ...` | Chat Completions API |
| Evaluate skills | `client.evaluate(...)` | `skillnet evaluate ...` | Chat Completions API |
| Analyze relationships | `client.analyze(...)` | `skillnet analyze ...` | Chat Completions + embeddings |
| Route local skills | `client.route(...)` | `skillnet route ...` | Embeddings + Claude, Codex or DeepSeek Harness SDK |
| Browse local skills | — | `skillnet ui` | None |

---

## Python SDK

### Initialize

```python
from skillnet_ai import SkillNetClient

client = SkillNetClient()
```

The client reads environment variables and saved settings. Configure model APIs
before using create, evaluate, analyze, or route; see [Configuration](#configuration).
You can override client settings with `api_key`, `base_url`, `model`,
`github_token`, `skillnet_api_url`, and `json_mode`. Embedding and Explorer
endpoints are configured separately.

### Search

Query the hosted SkillNet catalog and return a list of skill records. Keyword
search uses BM25 across skill names, descriptions, and tags, ranked by relevance
by default. Use `sort_by="stars"` or `sort_by="recent"` to change the order.

Since 0.1.4, SDK and CLI keyword searches default to relevance instead of stars.
Upgrade with `pip install --upgrade skillnet-ai`. To retain star-based sorting,
pass `sort_by="stars"` in Python or `--sort-by stars` in the CLI.

For natural-language tasks, use vector search, which returns results in similarity
order using the hosted service's embeddings. `EMBEDDING_*` settings apply to local
analysis and routing.

```python
results = client.search(
    q="analyze financial PDF reports",
    mode="vector",
    threshold=0.85,
    limit=10,
)

for skill in results:
    print(skill.skill_name, skill.stars, skill.skill_url)
```

Each result includes the repository (`repo_name`), source directory (`skill_dir`,
including the repository prefix), and download URL (`skill_url`). Different
repositories or version directories may share a skill name. `stars` records the
repository's star count at collection time.

The CLI displays the repository and directory below each skill name; `--json`
includes both fields. Source metadata is `None` when unavailable.

<details>
<summary><b>Search parameters</b></summary>

| Parameter | Type | Default | Description |
| :-- | :-- | :-- | :-- |
| `q` | `str` | required | Keyword query or natural language description |
| `mode` | `str` | `"keyword"` | `"keyword"` or `"vector"` |
| `category` | `str` | `None` | Category filter |
| `limit` | `int` | `20` | Results requested; the public service accepts 1–50 |
| `page` | `int` | `1` | Page number for keyword search |
| `min_stars` | `int` | `0` | Minimum star count for keyword search |
| `sort_by` | `str` | `"relevance"` | `"relevance"`, `"stars"` or `"recent"`, descending; keyword only |
| `threshold` | `float` | `0.8` | Similarity threshold for vector search |

</details>

### Download

Download the skill folder and its resources, validate its structure, and return
the installed directory path. Use `overwrite=True` to replace an existing folder.

```python
local_path = client.download(
    url="https://github.com/anthropics/skills/tree/main/skills/pdf",
    target_dir="./my_skills",
)
print(f"Installed at: {local_path}")
```

A failed replacement keeps the previous installation. For private repositories,
set `GITHUB_TOKEN`. `mirror_url` (CLI: `--mirror`) is a fallback for public file
downloads and is disabled when a GitHub token is in use.

URLs containing a commit SHA or an encoded branch slash (`feature%2Fcsv`) can
identify a specific revision when a branch name would otherwise be ambiguous.

### Create

Choose one input source per call: a conversation or execution trace, GitHub
repository, PDF/Word/PowerPoint document, or direct prompt. The returned list
contains generated directory paths. Use `evaluate` for a model assessment of
the result, or `skillnet validate <skill_dir>` to check its structure locally.

```python
# From a conversation or execution trace
client.create(
    trajectory_content=(
        "User: Check orders.csv for missing values.\n"
        "Agent: Read the CSV without modifying it, counted blank cells per column, "
        "and wrote quality-report.json."
    ),
    output_dir="./my_skills",
)

# From a GitHub repository
client.create(
    github_url="https://github.com/zjunlp/DeepKE",
    output_dir="./my_skills",
)

# From an office document
client.create(
    office_file="./guide.pdf",
    output_dir="./my_skills",
)

# From a direct prompt
paths = client.create(
    prompt=(
        "Create a csv-quality-checker skill that checks CSV files for missing "
        "values and duplicate rows without modifying the input."
    ),
    output_dir="./my_skills",
)
print(paths)
```

Generated packages use the [standard skill layout](#skill-package-layout).

### Evaluate

Assess a local skill directory or a GitHub skill URL. Each dimension contains a
`level` (`Good`, `Average`, or `Poor`) and a `reason`. The SDK reviews instructions
and supporting files without executing the skill's scripts.

```python
report = client.evaluate("./my_skills/pdf")

print(report["safety"]["level"], report["safety"]["reason"])
print(report["maintainability"]["level"], report["maintainability"]["reason"])
```

The five dimensions are safety, completeness, executability, maintainability,
and cost awareness. Ratings are model judgments about the supplied materials.

<details>
<summary><b>Reading limits and JSON compatibility</b></summary>

Evaluation reads up to 12,000 characters from `SKILL.md`, five script files at
12,000 characters each, and ten reference files at 4,000 characters each.
The report includes `prompt_injection_scan`; when files are skipped or truncated,
its `complete` field is `false` and `scan_issues` explains what was omitted.

`json_mode="auto"` requests JSON output and retries without that optional API
parameter if the provider explicitly rejects it. `"on"` requires the parameter;
`"off"` omits it. All modes parse and validate the five-dimension report.
This setting is independent of analysis's `AnalysisOptions.json_mode`.

</details>

### Analyze

Extract scenarios and capabilities from local skills, then build a reusable
relationship graph, retrieval index and Wiki for routing.

```python
analysis = client.analyze("./my_skills", output_dir="./skillnet_index")
print(analysis.index_dir)
print(analysis.skill_count, analysis.relation_counts)
```

`compose_with` is directed: A's output or established state can support B's next
operation in a stated scenario. `similar_to` is undirected: two skills offer
comparable capabilities for a task or subtask, subject to their own constraints.

Place each skill in a direct child folder containing a YAML-frontmatter `SKILL.md`.
Folder names are stable IDs; display names may repeat. Analysis reads the full
SKILL.md but does not execute or automatically inspect linked scripts/references.
The `graph` extra provides NumPy; BM25 requires SQLite FTS5.
See [endpoint configuration](#analysis-and-routing-endpoints) for the analysis
model and embedding settings.

Pass budgets through `options=AnalysisOptions(...)`, imported from `skillnet_ai`.

<details>
<summary><b>Analysis options</b></summary>

| Analysis option | Default | Meaning |
| :-- | :-- | :-- |
| `max_workers` | `4` | Parallel profile extractions or pair judgments |
| `candidate_limit` | `8` | Per-skill limit for capability matches and a separate limit for scenario handoffs; explicit references are additional |
| `embedding_batch_size` | `8` | Texts per embedding request |
| `timeout` | `120` | Model/embedding request timeout in seconds, not a whole-build deadline |
| `request_retries` | `0` | Transport retries; no content-generation retry loop |
| `json_mode` | `"on"` | Strict JSON Schema; `"off"` requests JSON through the prompt only |
| `reasoning_effort` | `None` | Omitted unless explicitly set to a model-supported none/low/medium/high |

Set `AnalysisOptions(reasoning_effort="medium")` (CLI: `--reasoning-effort medium`)
when your model supports that setting. If your endpoint does not support strict
JSON Schema output, choose `json_mode="off"` explicitly; the response must still
match the required schema.

</details>

`AnalysisResult` contains `index_dir`, `skill_count`, `relation_counts`, and
`cache_hits`. Output defaults to `<skills_dir>/.skillnet`; use `output_dir` to
choose a location. Rerun analysis after editing skills. Valid cached results are
reused; `force=True` (CLI: `--force`) recomputes them.

<details>
<summary><b>Index files and caching</b></summary>

Each successful analysis creates a snapshot containing `graph.json`,
`embeddings.npz`, `bm25.sqlite`, and a generated `wiki/`. The graph stores skill
profiles, relationship evidence, and the analyzed `SKILL.md` text. Wiki pages
are generated from these records without additional model calls.

`cache.sqlite` stores successful profile, embedding, and relationship results,
including judgments that two skills have no relationship. Cache reuse depends
on source content, model settings, and explicit prompt versions.

The `CURRENT` pointer changes only after all snapshot files are ready, so a failed
build leaves the previous index available. Older snapshots can be removed once
no routing calls are using them.

</details>

### Route

Select up to `k` skills for a task using an index created by `analyze`. Hybrid
search combines BM25 and vector rankings, then graph expansion adds related
candidates. A Claude, Codex or DeepSeek Harness SDK compares them in a task Wiki containing
skill profiles, relationships, and source text.

```python
result = client.route(
    "Extract tables from my PDF report and check the resulting CSV "
    "for missing values and duplicate rows.",
    index_dir="./skillnet_index",
    k=5,
)
for skill in result.skills:
    print(skill.skill_id, skill.name, skill.path, skill.reason)
```

Relations guide candidate exploration; the task and each skill's constraints
determine the final selection. Agent SDK extras are loaded only for routing;
install the `graph` extra and one of `claude`, `codex` or `dsh`.
See [endpoint configuration](#analysis-and-routing-endpoints) for the Explorer
and embedding settings.

Pass budgets through `options=RouteOptions(...)`, imported from `skillnet_ai`.

<details>
<summary><b>Routing options</b></summary>

| Routing option | Default | Meaning |
| :-- | :-- | :-- |
| `seed_limit` | `24` | Seeds from BM25/vector reciprocal rank fusion |
| `candidate_limit` | `100` | Total candidates after graph expansion; must be at least seed_limit |
| `max_depth` | `2` | Graph expansion depth; zero keeps only seeds |
| `timeout` | `300` | Query embedding timeout and a separate SDK exploration timeout, in seconds |
| `max_turns` | `24` | Claude turn or DSH model-step limit; unused by Codex |
| `read_limit` | `None` | Defaults to 2 + 2*k; Claude/DSH read-call budget; Codex command budget adds 9 |
| `reasoning_effort` | `"medium"` | Explorer reasoning: low/medium/high |

</details>

`RouteResult` contains `skills` and `usage`. Each skill has a `skill_id`, `name`,
local `path`, and selection `reason`. Usage comes from the Agent SDK and is
`None` when unavailable; it does not include the query embedding request.

`k` defaults to 5 and sets an upper limit. The result can contain fewer skills,
including none, and may cover only part of a task. Dataset, format, and environment
constraints affect the selection. Related skills are candidates, not mandatory
selections. The result is a skill set: routing neither executes the task nor
specifies an execution order.

Routing uses the latest successful analysis snapshot and generates a temporary
task Wiki. It requires the same embedding endpoint and model used for analysis,
with compatible vector dimensions. Edit the original skills and rerun `analyze`
to update the index; editing generated Wiki pages does not update routing.

Invalid model responses, damaged indexes, and SDK timeouts raise errors. A failed
Explorer call does not return a substitute selection based on retrieval rank.

---

## Browser Interface

Browse local skills and saved analysis results with the optional browser interface,
available in **0.1.2+**:

```bash
pip install "skillnet-ai[ui]>=0.1.2"
skillnet ui --skills-dir "/absolute/path/to/skills"
```

The service opens `http://127.0.0.1:8765`. Omit `--skills-dir` to choose a folder
in the interface; use `--no-browser` to suppress opening a tab, or `--port` to
change the port. Stop it with Ctrl+C.

- Browse local `SKILL.md` files and search the skill list.
- Switch **View** to **Analysis results** to inspect saved `compose_with` and
  `similar_to` relationships in a graph or list, and follow evidence to source lines.
- Import a complete SDK `graph.json`, or read the analysis in a folder's `.skillnet/`
  directory. Generate analysis separately with `client.analyze(...)` or
  `skillnet analyze`; the interface makes no model calls.

Install `skillnet-ai[ui,graph]` if you also want to generate analysis locally.
Browsing requires no model key, database, or Node.js.

The implementation lives in `src/skillnet_ai/web/`: Python serves local data and
compiled assets, while `web/ui/` contains the React source. See the
[interface guide](https://github.com/zjunlp/SkillNet/blob/main/skillnet-ai/src/skillnet_ai/web/ui/README.md)
for storage, limits, and development details.

---

## CLI

The CLI is installed with the package. You can also invoke it as
`python -m skillnet_ai`:

```bash
skillnet --help
skillnet <command> --help
```

### Commands

| Command | What it does | Example |
| :-- | :-- | :-- |
| `search` | Search SkillNet | `skillnet search "pdf" --mode vector` |
| `download` | Install a skill | `skillnet download <url> -d ./my_skills` |
| `create` | Create a skill package | `skillnet create --prompt "A skill for table extraction"` |
| `evaluate` | Evaluate a local or remote skill | `skillnet evaluate ./my_skill` |
| `analyze` | Build a local scenario graph and index | `skillnet analyze ./my_skills --output-dir ./skillnet_index` |
| `route` | Select local skills for a task | `skillnet route "analyze my CSV" --index-dir ./skillnet_index` |
| `ui` | Browse local skills and saved analysis | `skillnet ui --skills-dir /absolute/path/to/skills` |

### Search

```bash
skillnet search "pdf"
skillnet search "analyze financial reports" --mode vector --threshold 0.85
skillnet search "visualization" --category "Development" --sort-by stars --limit 10
```

### Download

```bash
skillnet download https://github.com/anthropics/skills/tree/main/skills/algorithmic-art
skillnet download <url> -d ./my_agent/skills
# With GITHUB_TOKEN already configured:
skillnet download <private_url>
skillnet download <url> --mirror https://ghfast.top/
```

### Create

```bash
skillnet create ./logs/trajectory.txt -d ./my_skills
skillnet create --github https://github.com/owner/repo
skillnet create --office ./docs/guide.pdf
skillnet create --prompt "A skill for table extraction"
skillnet create --office report.pdf --model gpt-4o
```

`create` requires exactly one source and checks the generated package structure.
Add `--evaluate` to run a model assessment after creation. If that assessment
fails, the command returns a nonzero exit code and retains the generated files
for inspection or reevaluation. A `Poor` rating is a valid result, not a command
failure.

### Evaluate

```bash
skillnet evaluate ./my_skills/pdf
skillnet evaluate https://github.com/anthropics/skills/tree/main/skills/algorithmic-art
skillnet evaluate ./my_skill --category "Development" --model gpt-4o
```

### Analyze

```bash
skillnet analyze ./my_skills --output-dir ./skillnet_index --json
```

### Route

```bash
skillnet route "Check my CSV for missing values and duplicate rows" --index-dir ./skillnet_index --k 5 --json
```

All six commands accept `--json`. Command results use one `{ok, data, error}`
JSON object on stdout; logs go to stderr. Use this mode when calling the CLI
from scripts or agents. See the
[output contract](https://github.com/zjunlp/SkillNet/blob/main/skills/skillnet/references/api-reference.md) for details.

## Use with Agents

The [SkillNet skill](https://github.com/zjunlp/SkillNet/blob/main/skills/skillnet/SKILL.md) gives compatible agents access
to the same CLI and SDK. Install the complete skill directory with its scripts
and references; see [installation and configuration](https://github.com/zjunlp/SkillNet/blob/main/skills/skillnet/references/setup.md)
and [agent-specific setup](https://github.com/zjunlp/SkillNet/blob/main/skills/skillnet/references/platforms.md).

Use `skillnet validate <skill_dir> --json` to check a skill's structure locally,
and `skillnet doctor --json` to inspect the environment visible to the agent.

<details>
<summary><b>Migrating to 0.1.1</b></summary>

Remove analyze's `mode` and `save_to_file`, configure embeddings, and rebuild old
graphs. Replace `orchestrate(query, scene=...)` with
`route(query, index_dir=..., k=...)`. The old aliases, preset scenes, and
`depend_on` relations have been removed. Search, download, create, and evaluate
retain their public APIs.

</details>

## Configuration

Settings resolve in this order: explicit arguments → environment variables →
`~/.skillnet/config.json` → defaults. Use `SKILLNET_CONFIG` to select another
configuration file. The SDK does not load `.env` files automatically; load them
into your process environment before creating the client.

| Variable | Purpose | Default |
| :-- | :-- | :-- |
| `API_KEY` | `create`, `evaluate`, `analyze` | unset |
| `BASE_URL` | Chat Completions endpoint for create, evaluate and analyze | `https://api.openai.com/v1` |
| `SKILLNET_MODEL` | Model for create, evaluate, and analyze | `gpt-4o` |
| `GITHUB_TOKEN` | Private repos or higher GitHub rate limits | unset |
| `GITHUB_MIRROR` | Public raw-file fallback mirror (disabled with GitHub authentication) | unset |
| `SKILLNET_API_URL` | Search service base URL | `http://api-skillnet.openkg.cn` |
| `SKILLNET_JSON_MODE` | Evaluation JSON mode: auto/on/off | `auto` |
| `SKILLNET_CONFIG` | Optional user config path | `~/.skillnet/config.json` |
| `EMBEDDING_API_KEY` | `analyze` and `route` | unset |
| `EMBEDDING_BASE_URL` | `analyze` and `route` | unset |
| `EMBEDDING_MODEL` | `analyze` and `route` | unset |
| `SKILLNET_EXPLORER_BACKEND` | `route`: claude, codex or dsh | `claude` |
| `SKILLNET_EXPLORER_API_KEY` | `route` SDK credential | unset |
| `SKILLNET_EXPLORER_BASE_URL` | `route` SDK-compatible base URL | unset |
| `SKILLNET_EXPLORER_MODEL` | `route` SDK model | unset |

`search` and public `download` require no credentials.

Linux / macOS:

```bash
export API_KEY="your-api-key"
export BASE_URL="https://api.openai.com/v1"
export SKILLNET_MODEL="gpt-4o"
```

Windows PowerShell:

```powershell
$env:API_KEY = "your-api-key"
$env:BASE_URL = "https://api.openai.com/v1"
$env:SKILLNET_MODEL = "gpt-4o"
```

For an interactive setup, run `skillnet configure --interactive`. It saves
settings for subsequent SDK and CLI calls. Configuration may contain API keys
in plaintext; keep it outside version control.

`skillnet doctor --json` inspects configuration and installed dependencies locally.
Add `--check-network` to check search and GitHub connectivity, `--check-llm` for a
model request, or `--check-explorer` for an Agent SDK exploration check. The latter
two use your configured model services and may incur charges.

### Analysis and routing endpoints

Analysis, embeddings, and the Explorer have separate endpoint settings. The
commands below read secrets from existing environment variables named
`MY_CHAT_KEY`, `MY_EMBEDDING_KEY`, and `MY_AGENT_KEY`; replace the example URLs
and model names with those supplied by your providers:

```bash
skillnet configure --base-url https://chat.example/v1 --model analysis-model \
  --api-key-env MY_CHAT_KEY
skillnet configure --embedding-base-url https://embedding.example/v1 \
  --embedding-model embedding-model --embedding-api-key-env MY_EMBEDDING_KEY
skillnet configure --explorer-backend claude --explorer-base-url https://agent.example \
  --explorer-model explorer-model --explorer-api-key-env MY_AGENT_KEY
skillnet doctor --json
```

Analysis uses Chat Completions; embeddings use the embeddings API. The Explorer
gateway must support the selected SDK's protocol, tool calls, and structured
output. A Chat Completions endpoint alone does not establish SDK compatibility.
Set all three endpoint configurations explicitly, even when one provider serves
them all. The default backend is `claude`; select Codex with
`client.route(..., backend="codex")` or `skillnet route ... --backend codex`.

For per-call configuration, pass `Endpoint(api_key=..., base_url=..., model=...)`
as `embedding` or `explorer`; import `Endpoint` from `skillnet_ai`. The analyze
`model` keyword changes only the analysis model, retaining the client's URL and key.

### DeepSeek Harness Explorer

DeepSeek Harness routing requires skillnet-ai 0.1.5 or later.
Install `skillnet-ai[graph,dsh]>=0.1.5` and configure a DeepSeek Messages-compatible
Explorer endpoint:

```bash
skillnet configure --explorer-backend dsh --explorer-base-url https://agent.example/anthropic \
  --explorer-model explorer-model --explorer-api-key-env MY_AGENT_KEY
skillnet route "Check required columns in my CSV" --index-dir ./skillnet_index --backend dsh --json
```

Replace the example URL and model with your provider's values. Python callers use
`backend="dsh"` with the existing `explorer=Endpoint(...)`. Analysis and embedding
settings remain separate. The SDK supplies its runtime and reads the task Wiki
in an isolated session with read/list tools. `max_turns` limits model steps;
low/medium/high reasoning maps to DSH low/high/max. Usage is returned as `None`.
The timeout covers SDK startup and exploration; process launch and cleanup can delay
return. If startup exhausts the budget, exploration does not begin.

---

## Skill Package Layout

A skill package has a `SKILL.md` entry point and optional supporting directories:

```text
skill-name/
├── SKILL.md          # required metadata and instructions
├── scripts/          # optional executable helpers
├── references/       # optional reference material
└── assets/           # optional templates, examples, or media
```

Keep the name, description, and usage instructions in `SKILL.md`. Put executable
helpers in `scripts/`, detailed guidance in `references/`, and templates or other
resources in `assets/`. Analysis reads `SKILL.md`; agents can load supporting files
when they use the selected skill.

---

## Contributing

Contributions are welcome. Open an issue for bugs, feature requests, or documentation improvements, and submit pull requests for focused changes.

The top level contains the main capabilities: `searcher.py`, `downloader.py`,
`creator.py`, `evaluator.py` and `analyzer.py`. Analysis owns source extraction,
relationship construction and model-result caching. `router/` contains the routing
flow (`router.py`), index construction/loading/retrieval (`index.py`), Wiki rendering
(`wiki.py`) and the Agent SDK implementations (`explorer.py`).

`core/` contains data contracts, prompts, model requests, configuration, validation
and the existing injection scanner. It does not import the business modules.
`interfaces/client.py` and `interfaces/cli.py` expose the Python and CLI entry points.
The public Python entry point is `from skillnet_ai import SkillNetClient`; the CLI
entry point is `skillnet_ai.interfaces.cli:app`.

When changing extraction or relation schemas/semantics, increment the explicit
versions in `src/skillnet_ai/core/prompts.py` to invalidate obsolete cached results.

From the `skillnet-ai/` directory:

```bash
pip install -e ".[ui,graph,dev,claude,codex,dsh]"
pytest -q
mypy
# Build the website before producing a wheel or source distribution (Node.js 20 or 22+).
npm --prefix src/skillnet_ai/web/ui ci
npm --prefix src/skillnet_ai/web/ui run build
python -m build
```

Use Ruff to check and format the Python modules you change, with the settings in
`pyproject.toml`. The test suite uses offline model and Agent SDK fixtures; it does
not require model credentials. Live routing quality needs a separate check with
real skills and your configured providers.

## License

SkillNet is licensed under [MIT](https://github.com/zjunlp/SkillNet/blob/main/LICENSE).
Skills from external repositories retain their own licenses.

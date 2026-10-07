<div align="center">
<a href="http://skillnet.openkg.cn/">
    <img src="images/skillnet.png" width="190" alt="SkillNet Logo">
</a>

# SkillNet

**Open infrastructure for discovering, evaluating, analyzing, and routing reusable AI agent skills.**

[![PyPI version](https://badge.fury.io/py/skillnet-ai.svg)](https://pypi.org/project/skillnet-ai/)
[![GitHub stars](https://img.shields.io/github/stars/zjunlp/SkillNet?style=social)](https://github.com/zjunlp/SkillNet)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![arXiv](https://img.shields.io/badge/arXiv-b5212f.svg?logo=arxiv)](https://arxiv.org/abs/2603.04448)
[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-FFD21E)](https://huggingface.co/blog/xzwnlp/skillnet)
[![Website](https://img.shields.io/badge/Website-skillnet.openkg.cn-0078D4.svg)](http://skillnet.openkg.cn/)
[![On StackMap](https://img.shields.io/endpoint?url=https%3A%2F%2Fstackmap.shipwithai.xyz%2Fapi%2Fbadge%2Fskillnet.json)](https://stackmap.shipwithai.xyz/repos/zjunlp/skillnet?utm_source=badge)

[Website](http://skillnet.openkg.cn/) · [Python SDK](./skillnet-ai) · [Local UI](#local-browser-interface) · [Examples](./examples) · [Experiments](./experiments) · [Paper](https://arxiv.org/abs/2603.04448)

</div>

---

SkillNet provides unified infrastructure for the agent skill lifecycle:

- **Discovery:** search a public skill library by keyword or semantic intent.
- **Installation:** download skill folders from GitHub into local agent workspaces.
- **Creation:** generate structured skills from repositories, documents, prompts, or execution traces.
- **Evaluation:** assess skills for safety, completeness, executability, maintainability, and cost awareness.
- **Analysis:** extract capabilities and usage scenarios, and infer relationships between local skills.
- **Routing:** select skills for a task from your local library, with selection reasons.

<div align="center">

![SkillNet overview: skill categories, relationships, and evaluation dimensions](https://github.com/user-attachments/assets/1d27d046-48a1-4ab2-a6f5-58c8fa07a134)

</div>

---

## News

- **[2026-09-24]** [**skillnet-ai 0.1.2**](https://pypi.org/project/skillnet-ai/0.1.2/)
  adds a [local browser interface](#local-browser-interface) for exploring skill
  folders, analyzed relationships, and source evidence. Launch it with `skillnet ui`.

- **[2026-08-20]** The updated [**SkillNet report**](https://arxiv.org/abs/2603.04448) presents
  **SkillNet-Gym**, with executable benchmarks for skill construction, retrieval, and composition,
  and **SkillNet-Fabric**, which routes tasks through a Wiki built for each task.

- **[2026-07-11]** The [**SkillNet library**](http://skillnet.openkg.cn/) now indexes
  **500K+ GitHub skills**, with improved deduplication and broader coverage of scientific research
  and data analysis. This update also adds local scenario graphs and orchestration.

- **[2026-03-26]** [**JiuwenClaw**](./examples/JiuwenClaw/README.md) integrates SkillNet as a
  built-in skill marketplace, bringing skill discovery and installation into its agent workflow.

- **[2026-03-12]** The [**SkillNet MCP server**](https://github.com/CycleChain/skillnet-mcp),
  maintained by [CycleChain](https://github.com/CycleChain), makes SkillNet tools available to
  MCP-compatible agents.

- **[2026-03-04]** [**SkillNet: Create, Evaluate, and Connect AI Skills**](https://arxiv.org/abs/2603.04448)
  is now available on arXiv, describing the project's approach to reusable agent skills.

- **[2026-02-23]** [**OpenClaw**](https://github.com/openclaw/openclaw) now includes SkillNet
  as a built-in skill for discovering and reusing agent capabilities.

---

## Web Platform

Explore the public skill library on [skillnet.openkg.cn](http://skillnet.openkg.cn/).

- **Find skills:** search the [skill library](http://skillnet.openkg.cn/resources) by keyword or semantic intent, and filter by category.
- **Review skills:** inspect descriptions, evaluation ratings, and GitHub sources, with download links for reuse.
- **Explore collections:** browse [curated skill collections](http://skillnet.openkg.cn/package) for specific domains and tasks, and inspect the relationships between their skills.

The site also introduces [SkillNet-Gym](http://skillnet.openkg.cn/skillgym) for skill graph construction and lifecycle benchmarking, and [SkillNet-Fabric](http://skillnet.openkg.cn/skillfabric) for Wiki-based skill routing, including research results and a guided routing demo.

<div align="center">

https://github.com/user-attachments/assets/9f9d35b0-36fd-4d7d-a072-39afa380b241

</div>

---

## Local Browser Interface

The [browser interface](skillnet-ai/src/skillnet_ai/web/ui/README.md) is part of the
Python package. Browse your own skill folders, inspect saved analysis graphs,
and follow relationship evidence to the original source lines.

Available in **skillnet-ai 0.1.2+**. Install and launch it with:

```bash
pip install "skillnet-ai[ui]>=0.1.2"
skillnet ui --skills-dir "/absolute/path/to/skills"
```

Open `http://127.0.0.1:8765`. Choose **Current skill files** to read the sources or
**Analysis results** to explore saved `compose_with` and `similar_to` relationships.
You can also import a `graph.json` generated by `skillnet analyze`.

Packaged releases include the website; users do not need Node.js or model keys
to browse. Generate analysis separately with the SDK or CLI, then view the same
results here. The interface starts with an empty personal library.

---

## Python SDK

### Install

Requires Python 3.10 or newer.

```bash
pip install skillnet-ai
```

Install optional dependencies for analysis and routing:

```bash
pip install "skillnet-ai[graph]"         # scenario analysis
pip install "skillnet-ai[graph,claude]"  # analysis and routing via Claude
pip install "skillnet-ai[graph,codex]"   # analysis and routing via Codex
```

### Initialize

```python
from skillnet_ai import SkillNetClient

client = SkillNetClient()
```

The client reads environment variables and saved settings. See
[Configuration](#configuration) to set up model endpoints or GitHub authentication.

### Search

Search the hosted SkillNet catalog by keyword or semantic intent. Keyword search
defaults to sorting by stars; vector search uses the search service's embeddings.

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

### Download

Download a GitHub skill folder and its resources, check its structure, and return
the installed path. Use `overwrite=True` to replace an existing folder.

```python
local_path = client.download(
    url="https://github.com/anthropics/skills/tree/main/skills/pdf",
    target_dir="./my_skills",
)
print(local_path)
```

### Create

Generate skill packages from a prompt, repository, document, or execution trace.
Choose one source per call; the result is a list of generated directory paths.

```python
paths = client.create(
    prompt=(
        "Create a csv-quality-checker skill that checks CSV files for missing "
        "values and duplicate rows without modifying the input."
    ),
    output_dir="./my_skills",
)
print(paths)

client.create(
    github_url="https://github.com/zjunlp/DeepKE",
    output_dir="./my_skills",
)

client.create(
    office_file="./guide.pdf",
    output_dir="./my_skills",
)
```

### Evaluate

Assess a local skill or GitHub skill URL across five quality dimensions. Each
dimension contains a `level` (`Good`, `Average`, or `Poor`) and a `reason`.
Evaluation reviews the skill's instructions and supporting files without executing
its scripts.

```python
report = client.evaluate("./my_skills/pdf")
print(report["safety"]["level"], report["safety"]["reason"])
print(report["maintainability"]["level"], report["maintainability"]["reason"])
```

### Analyze

Extract scenarios and capabilities from local skills, then build a reusable
relationship graph, retrieval index and Wiki for routing.

```python
analysis = client.analyze("./my_skills", output_dir="./skillnet_index")
print(analysis.index_dir)
print(analysis.skill_count, analysis.relation_counts)
```

The graph has two relations: directed `compose_with` for an output or state from
one skill that supports another, and undirected `similar_to` for comparable
capabilities. Both are tied to specific scenarios.

`analyze` reads direct child folders containing `SKILL.md`. Its default output is
`<skills_dir>/.skillnet`; pass `output_dir` to choose another location. Reanalyze
after editing skills to update the snapshot used by routing.
See [analysis options and index details](skillnet-ai/README.md#analyze).

### Route

Select up to `k` skills for a task using an index created by `analyze`. Hybrid
search and graph expansion identify candidates; a Claude or Codex Agent SDK
compares them in a task Wiki containing skill profiles, relationships, and source text.

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
determine the final selection.

`route` returns `skills` (`skill_id`, `name`, `path`, `reason`) and available SDK
`usage`. It selects up to `k` skills, possibly none. The selected set may cover
only part of a task, and its order does not specify execution order.

See [routing options](skillnet-ai/README.md#route) and
[endpoint configuration](skillnet-ai/README.md#analysis-and-routing-endpoints).

## CLI

The CLI exposes the same six operations. Use `python -m skillnet_ai` wherever
the `skillnet` command is unavailable on your PATH.

| Command | What it does | Example |
| :-- | :-- | :-- |
| `search` | Search SkillNet | `skillnet search "pdf" --mode vector` |
| `download` | Install a skill | `skillnet download <url> -d ./my_skills` |
| `create` | Create a skill package | `skillnet create --prompt "A skill for table extraction"` |
| `evaluate` | Evaluate a local or remote skill | `skillnet evaluate ./my_skill` |
| `analyze` | Build a local scenario graph and index | `skillnet analyze ./my_skills --output-dir ./skillnet_index` |
| `route` | Select local skills for a task | `skillnet route "analyze my CSV" --index-dir ./skillnet_index` |
| `ui` | Browse local skills and saved analysis | `skillnet ui --skills-dir /absolute/path/to/skills` |

Use `skillnet <command> --help` for full options, or see the
[CLI examples](skillnet-ai/README.md#cli). Add `--json` for a structured
`{ok, data, error}` response on stdout; logs go to stderr.

`create` checks the generated package structure; add `--evaluate` to request a
model assessment as well. Use `skillnet validate <skill_dir>` for a local structure
check without a model call.

## Configuration

Search and public downloads need no API key. Create, evaluate, and analyze use an
OpenAI-compatible Chat Completions endpoint. Analyze also needs an embedding
endpoint; route uses that same embedding endpoint and a separately configured
Claude or Codex Agent SDK.

Settings resolve in this order: explicit arguments → environment variables →
user configuration → defaults. Load any `.env` file into your environment before
calling the SDK; it does not load one automatically.

| Variable | Purpose | Default |
| :-- | :-- | :-- |
| `API_KEY` | `create`, `evaluate`, `analyze` | unset |
| `BASE_URL` | Chat Completions endpoint for create, evaluate and analyze | `https://api.openai.com/v1` |
| `SKILLNET_MODEL` | Model for create, evaluate, and analyze | `gpt-4o` |
| `GITHUB_TOKEN` | Private repos or higher GitHub rate limits | unset |
| `GITHUB_MIRROR` | Public download fallback; disabled with GitHub authentication | unset |
| `SKILLNET_API_URL` | Hosted search service URL | `http://api-skillnet.openkg.cn` |
| `EMBEDDING_API_KEY` | `analyze` and `route` | unset |
| `EMBEDDING_BASE_URL` | `analyze` and `route` | unset |
| `EMBEDDING_MODEL` | `analyze` and `route` | unset |
| `SKILLNET_EXPLORER_BACKEND` | `route`: claude or codex | `claude` |
| `SKILLNET_EXPLORER_API_KEY` | `route` SDK credential | unset |
| `SKILLNET_EXPLORER_BASE_URL` | `route` SDK-compatible base URL | unset |
| `SKILLNET_EXPLORER_MODEL` | `route` SDK model | unset |

Linux and macOS:

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

Analysis and routing require additional settings from the table above. See
[endpoint configuration](skillnet-ai/README.md#analysis-and-routing-endpoints)
for complete examples. `skillnet configure --interactive` saves settings locally;
`skillnet doctor --json` checks configuration and optional dependencies.

---

## REST API

The SkillNet search API is public and requires no authentication.

```bash
curl "http://api-skillnet.openkg.cn/v1/search?q=pdf&sort_by=stars&limit=5"
curl "http://api-skillnet.openkg.cn/v1/search?q=reading%20charts&mode=vector&threshold=0.8"
```

<details>
<summary><b>Search API parameters</b></summary>

**Endpoint:** `GET http://api-skillnet.openkg.cn/v1/search`

| Parameter | Type | Default | Description |
| :-- | :-- | :-- | :-- |
| `q` | string | required | Search query, keywords or natural language |
| `mode` | string | `keyword` | `keyword` or `vector` |
| `category` | string | unset | Filter by category |
| `limit` | int | `10` | Results per page, max 50 |
| `page` | int | `1` | Page number, keyword mode only |
| `min_stars` | int | `0` | Minimum star count, keyword mode only |
| `sort_by` | string | `stars` | `stars` or `recent`, keyword mode only |
| `sort_order` | string | `desc` | `desc` or `asc`, keyword mode only; REST API only |
| `threshold` | float | `0.8` | Similarity threshold, vector mode only |

</details>

---

## Use SkillNet Inside Agents

Install the [SkillNet skill](skills/skillnet/) to give your agent access to all
six operations. See [installation and configuration](skills/skillnet/references/setup.md)
and [agent setup](skills/skillnet/references/platforms.md) for instructions.

The demo below shows Claude Code using the SkillNet skill.

<div align="center">

https://github.com/user-attachments/assets/ae6020d9-6846-4672-84ce-fa9c8057e92b

</div>

### Model Context Protocol

The community [SkillNet MCP server](https://github.com/CycleChain/skillnet-mcp),
maintained by [CycleChain](https://github.com/CycleChain), wraps the SkillNet CLI.
It requires Python, Node.js, and an installed `skillnet-ai` package.

```bash
git clone https://github.com/CycleChain/skillnet-mcp
cd skillnet-mcp
npm install
```

Docker:

```bash
docker pull fmdogancan/skillnet-mcp:latest
```

Follow the [MCP setup guide](https://github.com/CycleChain/skillnet-mcp#ide--tool-configuration-guide)
to register the server with your agent and check its available tools and
configuration requirements.

### OpenClaw and JiuwenClaw

[OpenClaw](https://github.com/openclaw/openclaw) includes SkillNet as a built-in
skill; [JiuwenClaw](https://github.com/openJiuwen-ai/jiuwenclaw) integrates it into
its skill marketplace. See the [JiuwenClaw guide](./examples/JiuwenClaw/README.md).

The demo below shows SkillNet running inside OpenClaw to discover and use reusable skills.

<div align="center">

https://github.com/user-attachments/assets/9d49a00c-827d-47a4-8954-0e6b977ca547

</div>

---

## Examples and Experiments

### Scientific discovery

The scientific workflow notebook illustrates skill discovery and reuse for
scRNA-seq analysis, pathway lookup, and target validation. It uses a predefined
plan and simulated data for parts of the demonstration.

![Scientific discovery demo](https://github.com/user-attachments/assets/5b65865a-312a-4dd7-ae80-ee1f968e2702)

[Open the scientific workflow notebook](./examples/scientific_workflow_demo.ipynb).

### More examples and benchmarks

- [`examples/`](./examples): SDK demos and notebook workflows.
- [`experiments/`](./experiments): reproduction scripts for ALFWorld, WebShop, and ScienceWorld.

Complete the [benchmark environment setup](experiments/README.md) before running
the experiments. Each benchmark has separate environment and data dependencies.

```bash
cd experiments

python alfworld_run.py --model o4-mini --split dev --max_workers 10 --exp_name alf_test --use_skill
python scienceworld_run.py --model o4-mini --split test --max_workers 5 --exp_name sci_test --use_skill
python webshop_run.py --model o4-mini --max_workers 3 --exp_name web_test --use_skill
```

---

## Roadmap

- Broader evaluation of task routing across local skill libraries.
- More curated skill collections and routing Wikis.
- Stronger skill evaluation and regression testing.
- Extend SkillNet-Fabric routing across skill collections.
- Expand SkillNet-Gym lifecycle evaluation and training environments.

---

## Contributing

Contributions are welcome: bug fixes, documentation, examples, integrations, and new skills all help. Please keep pull requests focused and include reproduction steps or examples when possible.

See the [SDK development guide](skillnet-ai/README.md#contributing) for code
organization and local checks.

---

## Citation

If SkillNet is useful in your research or agent system, please cite:

```bibtex
@article{liang2026skillnet,
  title={{SkillNet}: Create, Evaluate, and Connect {AI} Skills},
  author={Liang, Yuan and Zhong, Ruobin and Xu, Haoming and Jiang, Chen and Zhong, Yi and Fang, Runnan and Gu, Jia-Chen and Deng, Shumin and Yao, Yunzhi and Wang, Mengru and others},
  journal={arXiv preprint arXiv:2603.04448},
  year={2026}
}
```

---

## License

SkillNet is licensed under [MIT](LICENSE). Skills from external repositories
retain their own licenses.

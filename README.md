<div align="center">
<a href="http://skillnet.openkg.cn/">
    <img src="images/skillnet.png" width="190" alt="SkillNet Logo">
</a>

# SkillNet

**Open infrastructure for discovering, evaluating, composing, and orchestrating reusable AI agent skills.**

<p>
SkillNet treats agent skills as software assets: searchable, installable, inspectable, evaluable, and composable.
</p>

[![PyPI version](https://badge.fury.io/py/skillnet-ai.svg)](https://pypi.org/project/skillnet-ai/)
[![GitHub stars](https://img.shields.io/github/stars/zjunlp/SkillNet?style=social)](https://github.com/zjunlp/SkillNet)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![arXiv](https://img.shields.io/badge/arXiv-b5212f.svg?logo=arxiv)](https://arxiv.org/abs/2603.04448)
[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-FFD21E)](https://huggingface.co/blog/xzwnlp/skillnet)
[![Website](https://img.shields.io/badge/Website-skillnet.openkg.cn-0078D4.svg)](http://skillnet.openkg.cn/)
[![On StackMap](https://img.shields.io/endpoint?url=https%3A%2F%2Fstackmap.shipwithai.xyz%2Fapi%2Fbadge%2Fskillnet.json)](https://stackmap.shipwithai.xyz/repos/zjunlp/skillnet?utm_source=badge)

[Website](http://skillnet.openkg.cn/) · [Python SDK](./skillnet-ai) · [Examples](./examples) · [Experiments](./experiments) · [Paper](https://arxiv.org/abs/2603.04448)

</div>

---

## Why SkillNet?

Agents should not rebuild the same capability from scratch every time. SkillNet provides the infrastructure layer for skill reuse:

- **Discovery:** search a public skill library by keyword or semantic intent.
- **Installation:** download skill folders from GitHub into local agent workspaces.
- **Creation:** generate structured skills from repositories, documents, prompts, or execution traces.
- **Evaluation:** score skills for safety, completeness, executability, maintainability, and cost awareness.
- **Composition:** infer relationships and scenario handoffs between local skills.
- **Orchestration:** select scene-specific skills and generate a prompt for a downstream execution agent.

Search and public skill installation are credential-free. Create, evaluate, and analyze work with OpenAI-compatible endpoints. Orchestration runs through Claude Agent SDK and requires a compatible gateway configured with the same `API_KEY`, `BASE_URL`, and `SKILLNET_MODEL` variables.

---

## Quick Start

Install the SDK and CLI:

```bash
pip install skillnet-ai
```

Search and install a skill:

```python
from skillnet_ai import SkillNetClient

client = SkillNetClient()

results = client.search("pdf understanding", limit=5)
print(results[0].skill_name)
print(results[0].skill_url)

client.download(results[0].skill_url, target_dir="./my_skills")
```

CLI equivalent:

```bash
skillnet search "pdf understanding" --limit 5
skillnet download <skill_url> -d ./my_skills
```

No API key is required for search or public GitHub downloads.

---

## News

- **[2026-08-20] SkillNet paper update.** **SkillNet-Gym** brings executable benchmarks for
  skill construction, retrieval, and composition; **SkillNet-Fabric** provides task time routing
  through a task specific Wiki. [Paper](https://arxiv.org/abs/2603.04448).
- **[2026-07-11] SkillNet update.** The library now indexes 500K+ GitHub skills with improved deduplication, expands scientific-research and data-analysis skill coverage, and adds local scenario graphs plus orchestration.
- **[2026-03-26] JiuwenClaw integration released.** JiuwenClaw now includes SkillNet as a built-in skill marketplace. [View guide](./examples/JiuwenClaw/README.md)
- **[2026-03-12] SkillNet MCP server released.** MCP support is maintained by [CycleChain](https://github.com/CycleChain).
- **[2026-03-04] Technical report released.** Read the SkillNet report on [arXiv](https://arxiv.org/abs/2603.04448).
- **[2026-02-23] OpenClaw integration released.** SkillNet is available as a built-in skill for [OpenClaw](https://github.com/openclaw/openclaw).

---

## What You Can Build

| Layer | Capability | What it enables |
| :-- | :-- | :-- |
| Skill library | Search and download | Reuse existing agent skills instead of rebuilding them |
| Skill authoring | Create | Turn traces, prompts, repositories, and documents into portable skill packages |
| Skill quality | Evaluate | Compare skill readiness before putting it in an agent workflow |
| Skill graph | Analyze | Discover `compose_with`, `depend_on`, and scenario-level handoff relationships |
| Orchestration | Orchestrate | Pick skills for a task in a curated scene and return an execution-ready prompt |
| Integrations | Agent skills, MCP, OpenClaw, JiuwenClaw | Use SkillNet inside existing agent runtimes |

---

## SkillNet Explorer

[SkillNet Explorer](http://skillnet.openkg.cn/) is the visual entry point for the public skill library. It is designed for browsing skills the way developers browse packages, datasets, or model hubs.

Use it to:

- search skills by keyword or semantic meaning
- inspect quality-ranked skills and curated collections
- explore skill graph visualizations
- copy installable GitHub skill URLs

<div align="center">

![Skill graph demo](https://github.com/user-attachments/assets/1d27d046-48a1-4ab2-a6f5-58c8fa07a134)

</div>

The website also includes interactive scenarios for web scraping, paper summarization, and experiment planning.

<div align="center">

https://github.com/user-attachments/assets/9f9d35b0-36fd-4d7d-a072-39afa380b241

</div>

---

## Python SDK

### Install

```bash
pip install skillnet-ai
```

Optional extras:

```bash
pip install "skillnet-ai[graph]"        # scenario-level graph analysis
pip install "skillnet-ai[orchestrate]"  # scene orchestration
```

### Initialize

```python
from skillnet_ai import SkillNetClient

client = SkillNetClient(
    api_key="your-api-key",       # required for create, evaluate, analyze, orchestrate
    base_url="https://api.openai.com/v1",
    github_token=None,            # optional, for private repos or higher GitHub rate limits
)
```

Credentials can also be set through environment variables: `API_KEY`, `BASE_URL`, `SKILLNET_MODEL`, and `GITHUB_TOKEN`.

### Search

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

```python
local_path = client.download(
    url="https://github.com/anthropics/skills/tree/main/skills/skill-creator",
    target_dir="./my_skills",
)
print(local_path)
```

### Create

```python
client.create(
    prompt="A skill for extracting tables from academic PDFs",
    output_dir="./skills",
)

client.create(
    github_url="https://github.com/zjunlp/DeepKE",
    output_dir="./skills",
)

client.create(
    office_file="./guide.pdf",
    output_dir="./skills",
)
```

### Evaluate

```python
report = client.evaluate("./my_skills/table-extractor")
print(report["overall_score"])
print(report["summary"])
```

### Analyze

Basic relationship analysis:

```python
relationships = client.analyze("./my_skills")

for rel in relationships:
    print(f"{rel['source']} --[{rel['type']}]--> {rel['target']}")
```

Scenario graph analysis:

```python
graph = client.analyze(
    "./my_skills",
    mode="scenario",
    embedding_api_key="your-embedding-api-key",
    embedding_base_url="https://embedding.example/v1",
    embedding_model="your-embedding-model",
    output_dir="./my_skills/skillnet_graph",
    timeout=120,
)

print(graph["scenario_skill_graph"]["edges"])
```

### Orchestrate

`orchestrate` requires `API_KEY`. It selects skills for a preset scene and returns a skill collection URL, selected skill names, and a downstream agent prompt. The first release supports `scene="sciatlas"`.
Its `BASE_URL` must support Claude Agent SDK requests; an OpenAI-only endpoint is not sufficient.

```bash
pip install "skillnet-ai[orchestrate]"
```

```python
result = client.orchestrate(
    "Find recent papers on retrieval-augmented generation and propose three follow-up ideas.",
    scene="sciatlas",
    timeout=240,
)

print(result.package_url)
print([skill.name for skill in result.skills])
print(result.prompt)
```

---

## CLI

The CLI ships with `skillnet-ai`.

| Command | What it does | Example |
| :-- | :-- | :-- |
| `search` | Search SkillNet | `skillnet search "pdf" --mode vector` |
| `download` | Install a skill | `skillnet download <url> -d ./skills` |
| `create` | Create a skill package | `skillnet create --prompt "A skill for table extraction"` |
| `evaluate` | Evaluate a local or remote skill | `skillnet evaluate ./my_skill` |
| `analyze` | Analyze local skill relationships | `skillnet analyze ./my_skills` |
| `orchestrate` | Build a scene skill handoff | `skillnet orchestrate "search papers about RAG"` |

Use `skillnet <command> --help` for full options.

### Common commands

```bash
skillnet search "pdf"
skillnet search "analyze financial reports" --mode vector --threshold 0.85

skillnet download <url> -d ./my_agent/skills
skillnet download <url> --mirror https://ghfast.top/

skillnet create --prompt "A skill for extracting tables from images"
skillnet evaluate ./my_skills/table_extractor
skillnet analyze ./my_skills
```

Scenario graph analysis:

```bash
pip install "skillnet-ai[graph]"

skillnet analyze ./my_skills --mode scenario \
  --embedding-api-key "$EMBEDDING_API_KEY" \
  --embedding-base-url "$EMBEDDING_BASE_URL" \
  --embedding-model "$EMBEDDING_MODEL" \
  --output-dir ./my_skills/skillnet_graph \
  --timeout 120
```

### Orchestrate

```bash
pip install "skillnet-ai[orchestrate]"

skillnet orchestrate "Find recent RAG papers and propose three follow-up ideas" \
  --scene sciatlas \
  --timeout 240
```

The command returns the SciAtlas skill collection URL, selected skills, and a downstream agent prompt. Use `--json` for machine-readable output.

---

## Configuration

| Variable | Required for | Default |
| :-- | :-- | :-- |
| `API_KEY` | `create`, `evaluate`, `analyze`, `orchestrate` | unset |
| `BASE_URL` | Custom LLM endpoint; orchestration requires a Claude Agent SDK-compatible gateway | `https://api.openai.com/v1` |
| `SKILLNET_MODEL` | Default LLM model | `gpt-4o` |
| `GITHUB_TOKEN` | Private repos or higher GitHub rate limits | unset |
| `GITHUB_MIRROR` | GitHub download mirror | unset |
| `EMBEDDING_API_KEY` | `analyze --mode scenario` | unset |
| `EMBEDDING_BASE_URL` | `analyze --mode scenario` | unset |
| `EMBEDDING_MODEL` | `analyze --mode scenario` | unset |

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

`search` and public GitHub downloads require no credentials.

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
| `threshold` | float | `0.8` | Similarity threshold, vector mode only |

</details>

---

## Use SkillNet Inside Agents

SkillNet is packaged as a portable agent skill at [`skills/skillnet/`](https://github.com/zjunlp/SkillNet/tree/main/skills/skillnet). Install it into an agent runtime and the agent can search, download, create, evaluate, and analyze skills during coding or research tasks.

### Claude Code

```bash
git clone https://github.com/zjunlp/SkillNet.git
cd SkillNet

mkdir -p ~/.claude/skills
cp -R skills/skillnet ~/.claude/skills/skillnet
```

Try:

```text
Use SkillNet to search for a docker skill and summarize the top result.
```

### Codex

```bash
git clone https://github.com/zjunlp/SkillNet.git
cd SkillNet

CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
mkdir -p "$CODEX_HOME/skills"
cp -R skills/skillnet "$CODEX_HOME/skills/skillnet"
```

Try:

```text
Use $skillnet to search for a LangGraph skill before planning this task.
```

### Model Context Protocol

The SkillNet MCP server is maintained by [CycleChain](https://github.com/CycleChain).

```bash
git clone https://github.com/CycleChain/skillnet-mcp
cd skillnet-mcp
npm install && npm run build
```

Docker:

```bash
docker pull fmdogancan/skillnet-mcp:latest
```

`search_skills` and `download_skill` do not require an API key. `create`, `evaluate`, and `analyze` do.

### OpenClaw and JiuwenClaw

SkillNet integrates with [OpenClaw](https://github.com/openclaw/openclaw) and [JiuwenClaw](https://github.com/openJiuwen-ai/jiuwenclaw) as a built-in skill marketplace. See the [JiuwenClaw guide](./examples/JiuwenClaw/README.md).

---

## Examples and Experiments

- [`examples/`](./examples): SDK demos and notebook workflows.
- [`experiments/`](./experiments): reproduction scripts for ALFWorld, WebShop, and ScienceWorld.
- [Scientific workflow demo](./examples/scientific_workflow_demo.ipynb): using skills in a multi-step scientific discovery workflow.

```bash
cd experiments

python alfworld_run.py --model o4-mini --split dev --max_workers 10 --exp_name alf_test --use_skill
python scienceworld_run.py --model o4-mini --split test --max_workers 5 --exp_name sci_test --use_skill
python webshop_run.py --model o4-mini --max_workers 3 --exp_name web_test --use_skill
```

---

## Roadmap

- Broader scene orchestration beyond SciAtlas.
- More curated skill collections and routing wikis.
- Stronger skill evaluation and regression testing.
- SkillFabric workflow substrates for routing across skill collections.
- SkillGym lifecycle evaluation and training environments.

---

## Contributing

Contributions are welcome: bug fixes, documentation, examples, integrations, and new skills all help. Please keep pull requests focused and include reproduction steps or examples when possible.

---

## Citation

If SkillNet is useful in your research or agent system, please cite:

```bibtex
@article{liang2026skillnet,
  title={Skillnet: Create, evaluate, and connect ai skills},
  author={Liang, Yuan and Zhong, Ruobin and Xu, Haoming and Jiang, Chen and Zhong, Yi and Fang, Runnan and Gu, Jia-Chen and Deng, Shumin and Yao, Yunzhi and Wang, Mengru and others},
  journal={arXiv preprint arXiv:2603.04448},
  year={2026}
}
```

---

## License

[MIT](LICENSE)

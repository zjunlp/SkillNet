# CLI and SDK reference

Requires skillnet-ai 0.1.1+. Run `skillnet <command> --help` for complete flags.
The Python facade is `from skillnet_ai import SkillNetClient`; it uses the same
runtime configuration as the CLI. Existing list/path/report SDK return types are
preserved. `python -m skillnet_ai` exposes the same CLI.

## Workflows

| Command | Important options |
|---|---|
| `search QUERY` | `--mode keyword|vector`, `--limit`, `--category`; keyword: `--page`, `--min-stars`, `--sort-by`; vector: `--threshold` |
| `download URL` | `--target-dir/-d`, `--overwrite`, `--mirror`; prefer configured `GITHUB_TOKEN` to `--token` |
| `create [TRAJECTORY_FILE]` | Exactly one source: positional trajectory, `--github`, `--office`, `--prompt`; `--output-dir/-d`, `--model/-m`, `--max-files`, `--evaluate/--no-evaluate`, `--json-mode` |
| `evaluate TARGET` | Local directory or GitHub skill URL; `--model/-m`, `--json-mode`, optional name/category/description overrides |
| `analyze SKILLS_DIR` | `--output-dir`, `--model`, `--force`; direct child folders with `SKILL.md`; requires analysis and embedding endpoints |
| `route QUERY` | `--index-dir` (required), `--k`, `--backend claude|codex|dsh`; requires embedding and Explorer endpoints |

All accept `--json`. Plain `create` does not evaluate unless `--evaluate` is
supplied. The skill's default workflow and legacy create helper enable evaluation.
Generated structure is checked before a requested evaluation.

See [routing.md](routing.md) for analysis/routing configuration, budgets and
snapshot behavior. `route` replaces `orchestrate`; old graphs must be rebuilt.

Downloads accept HTTPS GitHub `tree` URLs. A `blob/.../SKILL.md` link downloads its
parent package including resources. Encode a slash inside a branch name as `%2F`,
or use a commit SHA, to disambiguate it from the directory path. Raw single-file
SDK downloads remain available through `client.download(..., require_skill=False)`.
A non-skill file is not an installable skill. A directory listing at GitHub's
1000-entry limit is rejected because the complete file set cannot be verified.

## Machine output

Business results use one JSON document on stdout:

```json
{"ok": true, "data": {}, "error": null}
```

| Command | `data` |
|---|---|
| search | Array of existing skill objects: `skill_name`, `skill_url`, `skill_description`, `category`, `stars`, `evaluation`, etc. |
| download | `{"path": "/absolute/installed/skill"}` |
| create | `paths` (absolute paths), `validation` (per-path errors/warnings), `evaluations` (per-path `ok`, `report`, `error`) |
| evaluate | Five-dimension report, retaining additional fields such as `prompt_injection_scan` |
| analyze | `index_dir`, `skill_count`, `relation_counts`, `cache_hits`; the full graph is in the analysis directory |
| route | `skills` with IDs, names, original paths and reasons; available `usage` |

Search records include nullable `repo_name` (`owner/repository`) and `skill_dir`
(the source directory including that repository prefix). SDK/CLI 0.1.3+ versions
preserve these fields; older SDK versions ignore them, and older servers may omit
them. The CLI displays the repository and directory below the skill name.

`skill_name` is not unique: repositories and version directories may share names.
Do not merge results by name or name plus repository. Use `skill_url` to distinguish
returned source links and select a download; use `skill_dir`, when available, to
group a source directory across updates. It is not a content-version identifier.
`stars` belongs to the source repository at collection time. Short keywords work
with `--mode keyword`; use `--mode vector` for natural-language tasks and similarity
ordering.

A failed operation has `ok: false`, `error: {code, message, hint}` and exits 1.
Partial creation data remains available. Empty search results are successful.
CLI usage errors (invalid flags or argument types) use exit 2 and stderr; stdout
may be empty. Logs and progress go to stderr, not into JSON. Check the exit code
before consuming the result.

Each evaluation dimension (`safety`, `completeness`, `executability`,
`maintainability`, `cost_awareness`) has `level: Good|Average|Poor` and a nonempty
`reason`. A valid Poor rating is not an API failure. There is no guaranteed
`overall_score` or `summary` field. Evaluation samples content; inspect any
injection scan's `complete` and `scan_issues` fields for coverage limitations.

The evaluation reader reads up to 12,000 characters of SKILL.md, up to 5 scripts with
12,000 characters per file, and up to 10 reference files with 4,000 characters
per file. The script portion is therefore bounded at 60,000 characters. These
are character limits, not token limits. Small scripts are read in full; exceeding
either a file-count or character limit is reported as incomplete coverage.
The CLI and this skill use these same SDK defaults.

## Provider compatibility

For creation and evaluation, `BASE_URL` points to a Chat Completions-compatible base, not the search API or an
agent login endpoint. Create uses model/messages; evaluation also requests JSON
and a sampling temperature:

- `auto`: request JSON mode; if the server explicitly rejects `response_format`,
  remove that parameter and retry once on the same endpoint/model.
- `on`: require server JSON mode; report rejection without removing it.
- `off`: request JSON through the prompt only, without `response_format`.

An explicitly unsupported temperature can likewise be removed once. JSON parsing
and repair are followed by schema validation in all modes. Authentication, model
and account failures are not reasons to change providers or use host-generated
substitutes. Model transport errors are returned for recovery without hidden SDK retries;
compatibility fallback is bounded by the optional parameters and does not perform
repeated content-generation loops.

Analysis instead requires strict JSON Schema by default, with an explicit
prompt-only mode for compatible gateways. Analysis/routing never repair JSON,
drop unsupported parameters or retry a failed exploration. Embeddings and the
Explorer use their separately configured APIs; see [routing.md](routing.md).

## Recovery

| Symptom | Next step |
|---|---|
| Missing CLI or wrong Python | Follow setup.md; use the verified CLI or its full Python path |
| Missing key | Configure once; search and public download remain usable |
| Authentication/access rejected | Check endpoint-specific key/access and GitHub rate limit when relevant |
| Model/resource not found | Check exact base URL, model name, branch and skill folder |
| Quota/rate limit | Resolve account allowance or wait; do not repeat unchanged paid calls |
| Invalid evaluation structure | Keep the skill; inspect endpoint/model configuration, then retry evaluation only |
| Partial download | Existing installation is preserved; fix connectivity and retry |
| Existing destination | Reuse it, select another target, or explicitly request replacement |
| Search service failure | Report unavailable; do not call it “no results” |

`skillnet validate PATH --json` is an offline structural check; `--strict` also
fails on portability warnings. Optional scripts/references directories are not
required. Validation does not execute downloaded code or prove task success.

The SDK's lower-level downloader now raises on incomplete downloads. Evaluator
caches may be replaced by the evaluator; regular downloads preserve existing
folders unless overwrite was explicitly requested.

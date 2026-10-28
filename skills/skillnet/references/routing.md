# Analyze and route local skills

Analysis requires skillnet-ai 0.1.1 with the `graph` extra.
Routing additionally requires one of the `claude`, `codex` or `dsh` extras.
Use the user's existing model configuration; do not read agent login credentials.

1. Configure analysis (`API_KEY`, `BASE_URL`, `SKILLNET_MODEL`), embeddings
   (`EMBEDDING_API_KEY`, `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL`), and the Explorer
   (`SKILLNET_EXPLORER_API_KEY`, `SKILLNET_EXPLORER_BASE_URL`,
   `SKILLNET_EXPLORER_MODEL`, `SKILLNET_EXPLORER_BACKEND`). Channels may be shared
   only when the service supports each required protocol. Default backend: claude.
2. Run `skillnet analyze SKILLS_DIR --output-dir INDEX_DIR --json` on direct child
   skill folders. Analysis makes model calls and writes a reusable local index.
3. Run `skillnet route "TASK" --index-dir INDEX_DIR --k 5 --json`.
4. Present selected skills, original paths and reasons. Applying
   skills is a subsequent user task; routing itself does not execute them.

Composition edges are directed, scenario-conditioned suggestions. Similarity
edges identify comparable capabilities. Neither requires selecting both skills.
The result may contain fewer than k skills, including zero when no suitable skill is found.

Reanalyze after editing skills. The index preserves the analyzed source snapshot.
`--force` recomputes API results. Failures are explicit; do not describe a failed
SDK call as a successful empty selection or substitute a retrieval-only result.

`skillnet doctor --json` is offline. `--check-explorer` is an explicit, billable
check of the chosen SDK's exploration and structured-output behavior.

For DeepSeek Harness, install `skillnet-ai[graph,dsh]` and select `--backend dsh`
(or `SKILLNET_EXPLORER_BACKEND=dsh`). Configure a DeepSeek Messages-compatible
Explorer URL, API key and model. The SDK starts an isolated runtime with bounded
read-only Wiki tools; it does not reuse the host's GUI login or execute the task.
See the [DSH Explorer setup](https://github.com/zjunlp/SkillNet/blob/main/skillnet-ai/README.md#deepseek-harness-explorer)
for endpoint and budget details.

Version 0.1.1 removes basic/scenario mode switches, preset scenes and orchestrate.
Old graphs must be rebuilt; no execution prompt is returned.

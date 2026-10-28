"""Task routing through hybrid retrieval, graph expansion and SDK exploration."""

from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from skillnet_ai.core.config import Settings, model_endpoint
from skillnet_ai.core.llm import embed
from skillnet_ai.core.models import (
    AnalyzedSkill,
    Citation,
    Endpoint,
    Exploration,
    GroundedField,
    Relation,
    RoutedSkill,
    RouteOptions,
    RouteResult,
    SkillProfile,
)
from skillnet_ai.router.wiki import materialize_wiki

if TYPE_CHECKING:
    from skillnet_ai.router.dsh import DshExplorer
    from skillnet_ai.router.explorer import ClaudeExplorer, CodexExplorer


def route(
    query: str,
    index_dir: Path,
    *,
    k: int,
    embedding: Endpoint,
    endpoint: Endpoint,
    backend: str,
    options: RouteOptions,
) -> RouteResult:
    """Return a bounded skill set from one successful analysis snapshot."""

    try:
        import numpy as np
    except ModuleNotFoundError as exc:
        if exc.name == "numpy":
            raise ImportError("Install skillnet-ai[graph] for local routing.") from exc
        raise

    from skillnet_ai.router.index import fuse, load_snapshot, nearest, normalize, search_bm25

    if not query.strip():
        raise ValueError("Route query must not be empty.")
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k must be a positive integer.")
    root, graph = load_snapshot(index_dir)
    if (embedding.model, embedding.base_url.rstrip("/")) != (
        graph.embedding_model,
        graph.embedding_base_url.rstrip("/"),
    ):
        raise ValueError(
            "Embedding endpoint/model differs from the index; reanalyze or restore it."
        )
    ids = [s.skill_id for s in graph.skills]
    with np.load(root / "embeddings.npz", allow_pickle=False) as data:
        if data["ids"].tolist() != ids or len(data["vectors"]) != len(ids):
            raise ValueError("Embedding index IDs differ from the skill graph; reanalyze.")
        vectors = normalize(data["vectors"])
    query_vector = normalize(embed(embedding, [query], timeout=options.timeout))[0]
    seeds = fuse(
        [
            search_bm25(root / "bm25.sqlite", query, len(ids)),
            nearest(query_vector, vectors, ids, len(ids)),
        ],
        options.seed_limit,
    )
    chosen = expand(seeds, graph.relations, limit=options.candidate_limit, depth=options.max_depth)
    by_id = {s.skill_id: s for s in graph.skills}
    candidates = [by_id[key] for key in chosen]
    chosen_ids = set(chosen)
    edges = [e for e in graph.relations if e.source in chosen_ids and e.target in chosen_ids]
    with TemporaryDirectory(prefix="skillnet-route-") as temporary:
        wiki = Path(temporary) / "wiki"
        materialize_wiki(wiki, candidates, edges, query=query)
        return explore(wiki, query, candidates, k, endpoint, options, backend)


def backend_for(name: str) -> "ClaudeExplorer | CodexExplorer | DshExplorer":
    """Import only the requested runtime; never switch backends on failure."""

    if name == "claude":
        from skillnet_ai.router.explorer import ClaudeExplorer

        return ClaudeExplorer()
    if name == "codex":
        from skillnet_ai.router.explorer import CodexExplorer

        return CodexExplorer()
    if name == "dsh":
        from skillnet_ai.router.dsh import DshExplorer

        return DshExplorer()
    raise ValueError("Explorer backend must be claude, codex or dsh.")


def validate_selection(run: Exploration, candidates: list[AnalyzedSkill], k: int) -> RouteResult:
    """Validate candidate IDs and selection limits, then resolve package paths."""

    selection = run.selection
    ids = [s.skill_id for s in selection.skills]
    if len(ids) > k or len(set(ids)) != len(ids):
        raise ValueError("Explorer returned duplicate skills or exceeded k.")
    by_id = {s.skill_id: s for s in candidates}
    result = []
    for selected in selection.skills:
        if selected.skill_id not in by_id:
            raise ValueError("Explorer selected a skill outside the task Wiki.")
        skill = by_id[selected.skill_id]
        result.append(
            RoutedSkill(
                skill_id=selected.skill_id,
                name=skill.name,
                path=skill.path,
                reason=selected.reason,
            )
        )
    return RouteResult(skills=result, usage=run.usage)


def explore(
    root: Path,
    query: str,
    candidates: list[AnalyzedSkill],
    k: int,
    endpoint: Endpoint,
    options: RouteOptions,
    backend: str,
) -> RouteResult:
    """Run one SDK exploration and validate it; no ranked-list fallback."""

    run = backend_for(backend).explore(root, query, k, endpoint, options)
    return validate_selection(run, candidates, k)


def expand(seeds: list[str], edges: list[Relation], *, limit: int, depth: int) -> list[str]:
    """Keep all seeds and rank reachable neighbors by path strength and seed rank."""

    adjacency: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for edge in edges:
        forward, reverse = (0.7, 0.5) if edge.type == "compose_with" else (0.3, 0.3)
        adjacency[edge.source].append((edge.target, forward))
        adjacency[edge.target].append((edge.source, reverse))
    priorities: dict[str, float] = {}
    frontier = {seed: 1 / (60 + i) for i, seed in enumerate(seeds, 1)}
    best = dict(frontier)
    for _ in range(depth):
        following: dict[str, float] = {}
        for current, score in frontier.items():
            for neighbor, weight in adjacency[current]:
                value = score * weight
                if value > best.get(neighbor, 0):
                    best[neighbor] = value
                    following[neighbor] = max(value, following.get(neighbor, 0))
                    if neighbor not in seeds:
                        priorities[neighbor] = max(value, priorities.get(neighbor, 0))
        frontier = following
    ranked = sorted(priorities, key=lambda key: (-priorities[key], key))
    return seeds + ranked[: max(0, limit - len(seeds))]


def check_explorer_runtime(settings: Settings) -> None:
    """Check SDK exploration and structured selection on a one-skill Wiki."""

    capability = GroundedField(
        text="Count rows in a supplied CSV file.", evidence=[Citation(line=1)]
    )
    skill = AnalyzedSkill(
        skill_id="csv-counter",
        name="csv-counter",
        path="diagnostic-only",
        source=capability.text,
        content_hash="diagnostic",
        profile=SkillProfile(
            capability=capability,
            when_to_use=[capability],
            scenarios=[],
            inputs=[],
            outputs=[],
            constraints=[],
            tools=[],
        ),
    )
    with TemporaryDirectory(prefix="skillnet-doctor-") as temporary:
        root = Path(temporary) / "wiki"
        materialize_wiki(root, [skill], [])
        result = explore(
            root,
            "Choose a skill to count rows in my CSV. Do not execute it.",
            [skill],
            1,
            model_endpoint(settings, "explorer"),
            RouteOptions(),
            settings.explorer_backend,
        )
    if [item.skill_id for item in result.skills] != [skill.skill_id]:
        raise ValueError("Explorer connected but did not select the diagnostic skill.")

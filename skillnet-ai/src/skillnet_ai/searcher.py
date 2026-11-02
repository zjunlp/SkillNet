import logging
from typing import Literal

import requests

from skillnet_ai.core.config import resolve_settings
from skillnet_ai.core.models import SearchResponse, SkillModel

# Configure logger
logger = logging.getLogger(__name__)


class SkillNetSearcher:
    """
    Skill searcher for interacting with the SkillNet Search API.
    """

    def __init__(self, skillnet_api_url: str | None = None) -> None:
        self.skillnet_api_url = resolve_settings(
            skillnet_api_url=skillnet_api_url
        ).skillnet_api_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "SkillNet-Python-SDK/0.1.5"})

    def search(
        self,
        q: str,
        mode: Literal["keyword", "vector"] = "keyword",
        category: str | None = None,
        limit: int = 20,
        # --- Keyword mode ---
        page: int = 1,
        min_stars: int = 0,
        sort_by: str = "relevance",
        # --- Vector mode ---
        threshold: float = 0.8,
    ) -> list[SkillModel]:
        """
        Unified search for skills (supports both Keyword and AI Vector search).

        Args:
            q: Search query (Keywords or Natural Language).
            mode: 'keyword' for BM25 matching, 'vector' for semantic AI search.
            category: Filter by category (e.g., 'Development').
            limit: Items per page (keyword) or Match count (vector).

            # Keyword specific:
            page: Page number.
            min_stars: Minimum stars filter.
            sort_by: Sort field ('relevance', 'stars' or 'recent'), descending.

            # Vector specific:
            threshold: Similarity threshold (0.0 to 1.0).

        Returns:
            A list of skill records.
        """
        if mode not in {"keyword", "vector"}:
            raise ValueError("Search mode must be keyword or vector.")
        if not 1 <= limit <= 50 or page < 1 or not 0 <= threshold <= 1:
            raise ValueError("Use limit 1–50, page >= 1 and threshold 0–1.")
        endpoint = f"{self.skillnet_api_url}/v1/search"

        # 1. Construct base parameters
        params: dict[str, str | int | float | None] = {
            "q": q,
            "mode": mode,
            "category": category,
            "limit": limit,
        }

        # 2. Add mode-specific parameters
        if mode == "keyword":
            params.update(
                {
                    "page": page,
                    "min_stars": min_stars,
                    "sort_by": sort_by,
                }
            )
        elif mode == "vector":
            params.update({"threshold": threshold})

        # 3. Clean None values
        params = {k: v for k, v in params.items() if v is not None}

        try:
            logger.debug(f"Searching skills ({mode} mode) with params: {params}")

            # Make the request
            response = self.session.get(endpoint, params=params, timeout=15)
            response.raise_for_status()

            # Parse response
            search_res = SearchResponse(**response.json())

            if not search_res.success:
                raise RuntimeError(
                    "Search API returned success=False; this is not an empty result."
                )

            return search_res.data

        except requests.exceptions.RequestException as e:
            logger.error(f"Search request failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Data parsing failed: {e}")
            raise

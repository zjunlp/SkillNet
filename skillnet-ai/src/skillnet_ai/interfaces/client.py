import os
from pathlib import Path
from typing import Any, Literal

from skillnet_ai.core.config import model_endpoint, resolve_settings
from skillnet_ai.core.models import (
    AnalysisOptions,
    AnalysisResult,
    Endpoint,
    RouteOptions,
    RouteResult,
    SkillModel,
)
from skillnet_ai.creator import SkillCreator
from skillnet_ai.downloader import GitHubAPIError, SkillDownloader
from skillnet_ai.evaluator import EvaluatorConfig, SkillEvaluator
from skillnet_ai.searcher import SkillNetSearcher


class SkillNetError(Exception):
    """Custom exception class for SkillNet Client errors."""

    pass


class SkillNetClient:
    """
    A Python SDK client for interacting with SkillNet services.

    This client exposes search, download, create, evaluate, analyze and route.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        github_token: str | None = None,
        *,
        model: str | None = None,
        skillnet_api_url: str | None = None,
        json_mode: str | None = None,
    ):
        """
        Initialize the SkillNet Client.

        Args:
            api_key: Model API key. Uses API_KEY then optional user config.
            base_url: Base URL for the LLM API. Defaults to env var BASE_URL or OpenAI default.
            github_token: GitHub token for downloading private skills or avoiding rate limits.
                          Defaults to env var GITHUB_TOKEN.
        """
        self.settings = resolve_settings(
            api_key=api_key,
            base_url=base_url,
            github_token=github_token,
            model=model,
            skillnet_api_url=skillnet_api_url,
            json_mode=json_mode,
        )
        self.api_key = self.settings.api_key
        self.base_url = self.settings.base_url
        self.github_token = self.settings.github_token
        self.model = self.settings.model

    def search(
        self,
        q: str,
        mode: Literal["keyword", "vector"] = "keyword",
        category: str | None = None,
        limit: int = 20,
        page: int = 1,
        min_stars: int = 0,
        sort_by: str = "relevance",
        threshold: float = 0.8,
    ) -> list[SkillModel]:
        """
        Search for skills on SkillNet.

        Args:
            q: The search query.
            mode: 'keyword' or 'vector'.
            category: Filter by category.
            limit: Max results.
            page: Page number (keyword mode only).
            min_stars: Filter by stars (keyword mode only).
            sort_by: 'relevance', 'stars' or 'recent', descending (keyword mode only).
            threshold: Similarity threshold (vector mode only).

        Returns:
            A list of skill objects found.
        """
        try:
            searcher = SkillNetSearcher(skillnet_api_url=self.settings.skillnet_api_url)
            results = searcher.search(
                q=q,
                mode=mode,
                category=category,
                limit=limit,
                page=page,
                min_stars=min_stars,
                sort_by=sort_by,
                threshold=threshold,
            )
            return results
        except Exception as e:
            raise SkillNetError(f"Search failed: {str(e)}") from e

    def download(
        self,
        url: str,
        target_dir: str = ".",
        token: str | None = None,
        mirror_url: str | None = None,
        *,
        overwrite: bool = False,
        require_skill: bool = True,
    ) -> str:
        """
        Download a skill from a GitHub URL.

        Args:
            url: The GitHub URL of the specific skill folder.
            target_dir: Local directory to install into.
            token: Optional override for GitHub token.
            overwrite: Explicitly replace an existing folder after complete download.
            require_skill: Validate SKILL.md before publishing (default True).
            mirror_url: Public raw-file fallback; disabled with GitHub authentication.
                        Configure via GITHUB_MIRROR env var or pass explicitly.
                        Example mirrors: https://ghfast.top/, https://ghproxy.com/

        Returns:
            str: The absolute path to the installed skill folder.

        Raises:
            SkillNetError: If download fails.
        """
        # Use instance token if specific token not provided
        use_token = token if token is not None else self.github_token
        downloader = SkillDownloader(
            api_token=use_token,
            mirror_url=mirror_url if mirror_url is not None else self.settings.github_mirror,
        )

        try:
            installed_path = downloader.download(
                folder_url=url,
                target_dir=target_dir,
                overwrite=overwrite,
                require_skill=require_skill,
            )
            if not installed_path:
                # Raised only when download returns None (e.g., URL parsing failed, no files)
                raise SkillNetError("Download failed: No files were found or downloaded.")
            return os.path.abspath(installed_path)

        except GitHubAPIError as e:
            # 1. Base error message from GitHub
            error_detail = f"GitHub API Error [{e.status_code}]: {e.message}"

            # 2. Append actionable hints based on status code
            if e.status_code == 403:
                error_detail += " \n\n💡 Tip: You may have hit the GitHub API rate limit. Please provide a GitHub token to increase limits."
            elif e.status_code == 404:
                error_detail += " \n\n💡 Tip: Resource not found. Ensure the URL is correct and the repository is public, or provide a GitHub token for private repository access."

            # 3. Raise the final error with the hint attached
            raise SkillNetError(error_detail) from e

        except Exception as e:
            # Fallback for other unexpected errors
            raise SkillNetError(f"Download failed: {str(e)}") from e

    def create(
        self,
        input_type: str = "auto",
        trajectory_content: str | None = None,
        github_url: str | None = None,
        office_file: str | None = None,
        prompt: str | None = None,
        output_dir: str | Path = "./generated_skills",
        model: str | None = None,
        max_files: int = 50,
    ) -> list[str]:
        """
        Generate executable skills from various input sources.

        Args:
            input_type: Input source type. One of:
                - "auto": Auto-detect based on provided parameters (default)
                - "github": Create from GitHub repository
                - "trajectory": Create from execution log/trajectory
                - "office": Create from PDF/PPT/Word document
                - "prompt": Create from user's direct description
            trajectory_content: The text content of the execution log/trajectory.
            github_url: Full URL to GitHub repository.
            office_file: Path to office document (PDF, PPT, Word).
            prompt: User's description for prompt-based skill creation.
            output_dir: Directory where new skills will be saved.
            model: The LLM model to use.
            max_files: Maximum code files to analyze (GitHub mode only).

        Returns:
            List[str]: A list of paths to the generated skill folders.
        """
        if not self.api_key:
            raise SkillNetError("API_KEY is required for skill creation.")

        # Auto-detect input type if not specified
        if input_type == "auto":
            if github_url:
                input_type = "github"
            elif trajectory_content:
                input_type = "trajectory"
            elif office_file:
                input_type = "office"
            elif prompt:
                input_type = "prompt"
            else:
                raise SkillNetError(
                    "Must provide one of: trajectory_content, github_url, "
                    "office_file, or diy_prompt."
                )

        # Validate input_type
        valid_types = {"github", "trajectory", "office", "prompt", "auto"}
        if input_type not in valid_types:
            raise SkillNetError(f"Invalid input_type: {input_type}. Must be one of {valid_types}")

        try:
            creator = SkillCreator(
                api_key=self.api_key,
                base_url=self.base_url,
                model=model if model is not None else self.model,
            )

            if input_type == "github":
                if not github_url:
                    raise SkillNetError("github_url is required for github input type.")
                created_paths = creator.create_from_github(
                    github_url=github_url,
                    output_dir=str(output_dir),
                    api_token=self.github_token,
                    max_files=max_files,
                )
            elif input_type == "trajectory":
                if not trajectory_content:
                    raise SkillNetError("trajectory_content is required for trajectory input type.")
                created_paths = creator.create_from_trajectory(
                    trajectory=trajectory_content, output_dir=str(output_dir)
                )
            elif input_type == "office":
                if not office_file:
                    raise SkillNetError("office_file is required for office input type.")
                created_paths = creator.create_from_office(
                    file_path=office_file, output_dir=str(output_dir)
                )
            elif input_type == "prompt":
                if not prompt:
                    raise SkillNetError("prompt is required for prompt input type.")
                created_paths = creator.create_from_prompt(
                    user_input=prompt, output_dir=str(output_dir)
                )
            else:
                raise SkillNetError(f"Unknown input_type: {input_type}")

            return created_paths if created_paths else []
        except Exception as e:
            error = SkillNetError(f"Creation failed: {str(e)}")
            error.created_paths = getattr(e, "created_paths", [])
            raise error from e

    def evaluate(
        self,
        target: str,
        name: str | None = None,
        category: str | None = None,
        description: str | None = None,
        model: str | None = None,
        max_workers: int = 5,
        cache_dir: str | Path = "./evaluate_cache_dir",
        json_mode: str | None = None,
    ) -> dict[str, Any]:
        """
        Evaluate a skill (local path or URL).

        Args:
            target: Local folder path OR GitHub URL.
            name: Override skill name.
            category: Override skill category.
            description: Override skill description.
            model: LLM model for evaluation.
            max_workers: Concurrency limit.

        Returns:
            Dict[str, Any]: The evaluation report dictionary.
        """
        if not self.api_key:
            raise SkillNetError("API_KEY is required for evaluation.")

        config = EvaluatorConfig(
            api_key=self.api_key,
            base_url=self.base_url,
            model=model if model is not None else self.model,
            max_workers=max_workers,
            cache_dir=cache_dir,
            github_token=self.github_token,
            json_mode=json_mode if json_mode is not None else self.settings.json_mode,
        )
        evaluator = SkillEvaluator(config)

        try:
            is_url = target.startswith("http://") or target.startswith("https://")

            if is_url:
                result = evaluator.evaluate_from_url(
                    url=target, name=name, category=category, description=description
                )
            else:
                result = evaluator.evaluate_from_path(
                    path=target, name=name, category=category, description=description
                )

            if "error" in result:
                error = SkillNetError(f"Evaluation logic returned error: {result['error']}")
                error.details = result.get("error_details")
                raise error

            return result

        except Exception as e:
            raise SkillNetError(f"Evaluation process failed: {str(e)}") from e

    def analyze(
        self,
        skills_dir: str | Path,
        *,
        output_dir: str | Path | None = None,
        model: str | None = None,
        embedding: Endpoint | None = None,
        options: AnalysisOptions | None = None,
        force: bool = False,
    ) -> AnalysisResult:
        """Build a reusable scenario graph, retrieval index and Wiki from local skills.

        Reads direct child skill folders. Output defaults to skills_dir/.skillnet.
        Existing valid model results are reused unless force=True. Changing live
        sources takes effect only after another successful analysis.
        """
        try:
            from skillnet_ai.analyzer import analyze
        except ModuleNotFoundError as exc:
            if exc.name == "numpy":
                raise ImportError("Install skillnet-ai[graph] for local analysis.") from exc
            raise
        root = Path(skills_dir).expanduser().resolve()
        target = (
            Path(output_dir).expanduser().resolve()
            if output_dir is not None
            else root / ".skillnet"
        )
        endpoint = model_endpoint(self.settings, "analysis")
        if model is not None:
            endpoint = Endpoint(api_key=endpoint.api_key, base_url=endpoint.base_url, model=model)
        return analyze(
            root,
            target,
            endpoint=endpoint,
            embedding=embedding or model_endpoint(self.settings, "embedding"),
            options=options or AnalysisOptions(),
            force=force,
        )

    def route(
        self,
        query: str,
        *,
        index_dir: str | Path,
        k: int = 5,
        backend: Literal["claude", "codex", "dsh"] | None = None,
        explorer: Endpoint | None = None,
        embedding: Endpoint | None = None,
        options: RouteOptions | None = None,
    ) -> RouteResult:
        """Select at most k task-relevant skills from a successful analysis.

        Explorer and embedding endpoints are configured independently from the
        analysis model. No task execution or execution prompt is generated.
        """
        from skillnet_ai.router import route

        return route(
            query,
            Path(index_dir).expanduser().resolve(),
            k=k,
            embedding=embedding or model_endpoint(self.settings, "embedding"),
            endpoint=explorer or model_endpoint(self.settings, "explorer"),
            backend=backend or self.settings.explorer_backend,
            options=options or RouteOptions(),
        )

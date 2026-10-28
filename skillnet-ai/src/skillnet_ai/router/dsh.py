"""DeepSeek Harness exploration with an isolated, read-only Wiki tool surface."""

import json
import logging
import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from skillnet_ai.core.models import Endpoint, Exploration, RouteOptions, SkillSelection
from skillnet_ai.core.prompts import explorer_prompt, task_prompt

logger = logging.getLogger(__name__)


class DshExplorer:
    """Run one SDK conversation; keep runtime state outside the supplied Wiki."""

    def explore(
        self, root: Path, query: str, k: int, endpoint: Endpoint, options: RouteOptions
    ) -> Exploration:
        try:
            from deepseek_harness import DeepSeekHarness
        except ImportError as exc:
            raise ImportError("Install skillnet-ai[graph,dsh] to use this backend.") from exc

        root = root.resolve()
        read_limit = options.read_limit or 2 + 2 * k
        started = time.monotonic()
        with TemporaryDirectory(prefix="skillnet-dsh-") as state_dir:
            patch = Path(state_dir) / "wiki.patch.yml"
            # JSON is also valid YAML. Keep the shipped minimal profile's SDK/LLM
            # services, but remove its shell, image and directory-changing tools.
            entries: list[dict[str, object]] = [
                {"id": name, "disabled": True}
                for name in (
                    "persistent-bash",
                    "persistent-pwsh",
                    "tool-fs",
                    "tool-working-directory",
                    "plugin-package-inventory-deepseek",
                )
            ]
            entries += [
                {"id": "session-log-deepseek", "config": {"enabled": False}},
                {
                    "insert": [
                        {
                            "id": "skillnet-wiki",
                            "name": Path(__file__).with_name("dsh_wiki.mjs").as_posix(),
                        }
                    ]
                },
            ]
            patch.write_text(json.dumps(entries), encoding="utf-8")
            prompt = explorer_prompt(k, read_limit) + (
                "\nUse only read_wiki and list_wiki with paths relative to this Wiki. "
                "read_wiki supports character offset/limit for longer documents. "
                "Return exactly one JSON object, without Markdown, matching this schema:\n"
                + json.dumps(SkillSelection.model_json_schema())
            )
            client = DeepSeekHarness(
                provider="deepseek-official",
                model=endpoint.model,
                reasoning_effort={"low": "low", "medium": "high", "high": "max"}[
                    options.reasoning_effort
                ],
                max_tokens=8192,
                cwd=str(root),
                dsh_home=state_dir,
                profile="sdk-minimal",
                patches=(str(patch),),
                base_url=endpoint.base_url,
                api_key=endpoint.api_key.get_secret_value(),
                env={
                    "DSH_SYSTEM_PROMPT": prompt,
                    "SKILLNET_WIKI_ROOT": str(root),
                    "SKILLNET_WIKI_READ_LIMIT": str(read_limit),
                    "SKILLNET_WIKI_MAX_STEPS": str(options.max_turns),
                },
                initialize_timeout_seconds=options.timeout,
                request_timeout_seconds=options.timeout,
                shutdown_timeout_seconds=1,
            )
            expired = threading.Event()
            close_lock = threading.Lock()
            closed = False

            def close() -> None:
                nonlocal closed
                with close_lock:
                    if not closed:
                        closed = True
                        client.close()

            def expire() -> None:
                expired.set()
                try:
                    close()
                except Exception:
                    logger.warning("DSH timeout cleanup failed", exc_info=False)

            watchdog: threading.Timer | None = None
            failed = False
            try:
                client.start()
                remaining = options.timeout - (time.monotonic() - started)
                if remaining <= 0:
                    expired.set()
                    raise TimeoutError("DSH Explorer timed out during initialization.")
                watchdog = threading.Timer(remaining, expire)
                watchdog.daemon = True
                watchdog.start()
                result = client.run(task_prompt(query))
                if expired.is_set():
                    raise TimeoutError("DSH Explorer timed out.")
                if result.finish_reason != "completed":
                    raise RuntimeError(f"DSH Explorer failed: {result.finish_reason}")
                selection = SkillSelection.model_validate_json(result.final_response)
                return Exploration(selection)
            except BaseException as exc:
                failed = True
                if expired.is_set() or time.monotonic() - started >= options.timeout:
                    raise TimeoutError(
                        f"DSH Explorer exceeded {options.timeout:g} seconds."
                    ) from exc
                raise
            finally:
                if watchdog is not None:
                    watchdog.cancel()
                try:
                    close()
                except Exception:
                    if not failed:
                        raise
                    logger.warning("DSH cleanup failed", exc_info=False)

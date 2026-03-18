"""
Snapshot test: verifies that the refactored prompts subpackage exports
exactly the same prompt values as the original monolithic prompts.py.

The original file is kept verbatim as _original_prompts.py in this directory.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load the original monolithic prompts.py (saved as _original_prompts.py)
# without going through the package __init__.
# ---------------------------------------------------------------------------

_FIXTURE = Path(__file__).parent / "_original_prompts.py"


def _load_original():
    spec = importlib.util.spec_from_file_location("_original_prompts", _FIXTURE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Collect all uppercase names from the original module
_original_mod = _load_original()
_PROMPT_NAMES = sorted(
    n for n in dir(_original_mod) if n.isupper() and not n.startswith("_")
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _get_new_prompts():
    """Import the refactored prompts subpackage."""
    # Ensure we can import it even without full package deps installed
    pkg_root = Path(__file__).resolve().parents[1] / "src"
    if str(pkg_root) not in sys.path:
        sys.path.insert(0, str(pkg_root))
    spec = importlib.util.spec_from_file_location(
        "skillnet_ai.prompts",
        pkg_root / "skillnet_ai" / "prompts" / "__init__.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def new_prompts():
    return _get_new_prompts()


@pytest.fixture(scope="module")
def original_prompts():
    return _original_mod


class TestPromptCompleteness:
    """All original prompt variables must still be exported."""

    def test_all_names_present(self, new_prompts):
        new_names = {n for n in dir(new_prompts) if n.isupper() and not n.startswith("_")}
        for name in _PROMPT_NAMES:
            assert name in new_names, f"Missing prompt variable: {name}"

    def test_no_extra_names(self, new_prompts):
        new_names = {n for n in dir(new_prompts) if n.isupper() and not n.startswith("_")}
        original_names = set(_PROMPT_NAMES)
        extra = new_names - original_names
        assert not extra, f"Unexpected extra prompt variables: {extra}"


class TestPromptEquality:
    """Each prompt value must be identical character-for-character."""

    @pytest.mark.parametrize("name", _PROMPT_NAMES)
    def test_prompt_unchanged(self, name, new_prompts, original_prompts):
        original_value = getattr(original_prompts, name)
        new_value = getattr(new_prompts, name)
        assert new_value == original_value, (
            f"Prompt {name} changed!\n"
            f"Original length: {len(original_value)}\n"
            f"New length:      {len(new_value)}"
        )

    @pytest.mark.parametrize("name", _PROMPT_NAMES)
    def test_prompt_type_is_str(self, name, new_prompts):
        assert isinstance(getattr(new_prompts, name), str)

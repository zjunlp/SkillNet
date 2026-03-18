"""
Prompt templates used for generating skills from trajectories.

Long prompts (>3 lines) are stored in separate .md files under templates/.
Short prompts are defined inline below.
All variables are re-exported here so external imports remain unchanged:
    from skillnet_ai.prompts import CANDIDATE_METADATA_SYSTEM_PROMPT
"""

from pathlib import Path

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _load_template(filename: str) -> str:
    """Read a prompt template from a .md file."""
    return (_TEMPLATE_DIR / filename).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Short prompts (≤3 lines) — kept inline
# ---------------------------------------------------------------------------

CANDIDATE_METADATA_SYSTEM_PROMPT = "You are a helpful assistant."

SKILL_CONTENT_SYSTEM_PROMPT = "You are an expert Technical Writer specializing in creating SKILL for AI agents."

RELATIONSHIP_ANALYSIS_SYSTEM_PROMPT = """
You are the SkillNet Architect.
"""

# ---------------------------------------------------------------------------
# Long prompts — loaded from templates/*.md
# ---------------------------------------------------------------------------

CANDIDATE_METADATA_USER_PROMPT_TEMPLATE = _load_template("candidate_metadata_user.md")

SKILL_CONTENT_USER_PROMPT_TEMPLATE = _load_template("skill_content_user.md")

SKILL_EVALUATION_PROMPT = _load_template("skill_evaluation.md")

GITHUB_SKILL_SYSTEM_PROMPT = _load_template("github_skill_system.md")

GITHUB_SKILL_USER_PROMPT_TEMPLATE = _load_template("github_skill_user.md")

OFFICE_SKILL_SYSTEM_PROMPT = _load_template("office_skill_system.md")

OFFICE_SKILL_USER_PROMPT_TEMPLATE = _load_template("office_skill_user.md")

PROMPT_SKILL_SYSTEM_PROMPT = _load_template("prompt_skill_system.md")

PROMPT_SKILL_USER_PROMPT_TEMPLATE = _load_template("prompt_skill_user.md")

RELATIONSHIP_ANALYSIS_USER_PROMPT_TEMPLATE = _load_template("relationship_analysis_user.md")

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "CANDIDATE_METADATA_SYSTEM_PROMPT",
    "CANDIDATE_METADATA_USER_PROMPT_TEMPLATE",
    "SKILL_CONTENT_SYSTEM_PROMPT",
    "SKILL_CONTENT_USER_PROMPT_TEMPLATE",
    "SKILL_EVALUATION_PROMPT",
    "GITHUB_SKILL_SYSTEM_PROMPT",
    "GITHUB_SKILL_USER_PROMPT_TEMPLATE",
    "OFFICE_SKILL_SYSTEM_PROMPT",
    "OFFICE_SKILL_USER_PROMPT_TEMPLATE",
    "PROMPT_SKILL_SYSTEM_PROMPT",
    "PROMPT_SKILL_USER_PROMPT_TEMPLATE",
    "RELATIONSHIP_ANALYSIS_SYSTEM_PROMPT",
    "RELATIONSHIP_ANALYSIS_USER_PROMPT_TEMPLATE",
]

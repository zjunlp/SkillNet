"""
This module contains the prompt templates used for generating skills from trajectories.
"""

# Prompt to extract metadata (candidates) from a raw trajectory
CANDIDATE_METADATA_SYSTEM_PROMPT = "You are a helpful assistant."

CANDIDATE_METADATA_USER_PROMPT_TEMPLATE = """
Your goal is to analyze an interaction trajectory and extract **reusable Skills**.

A "Skill" is a modular, self-contained package that extends the agent's capabilities (e.g., "PDF Processor", "Market Analyzer", "Code Reviewer").

# Core Objective
1. Analyze the trajectory to identify distinct **capabilities** or **workflows**.
2. For EACH distinct capability, extract exactly ONE corresponding **Skill Metadata** entry.

*Note: Avoid over-fragmentation. If the trajectory is a coherent workflow (e.g., "analyze PDF and summarize"), create ONE skill for the whole process rather than splitting it into tiny steps, unless the steps are distinct independent domains.*

# Input Data
**Execution Trajectory:**
{trajectory}

# Step 1: Skill Identification
Identify skills that are:
- **Reusable**: Useful for future, similar requests.
- **Modular**: Self-contained with clear inputs and outputs.
- **Domain Specific**: Provides specialized knowledge or workflow logic.

# Step 2: Metadata Extraction Rules
For EACH identified skill, generate metadata with:

### `name` requirements:
- **kebab-case** (e.g., `financial-report-generator`, `code-refactor-tool`).
- Concise but descriptive.

### `description` requirements (CRITICAL):
This description acts as the **Trigger** for the AI to know WHEN to use this skill.
It must be a **When-To-Use** statement containing:
1. **Context**: The specific situation or user intent (e.g., "When the user asks to analyze a PDF...").
2. **Capabilities**: What the skill provides (e.g., "...extracts text and summarizes financial metrics").
3. **Triggers**: Specific keywords or file types associated with this skill.

# Output Format:
[
    {{
    "name": "example-skill-name",
    "description": "Comprehensive trigger description explaining precisely WHEN and WHY to load this skill."
    }},
    ...
]

Keep your output in the format below:
<Skill_Candidate_Metadata>
your generated candidate metadata list in JSON format here
</Skill_Candidate_Metadata>
"""

# Prompt to generate actual file content for a specific skill
SKILL_CONTENT_SYSTEM_PROMPT = "You are an expert Technical Writer specializing in creating SKILL for AI agents."

SKILL_CONTENT_USER_PROMPT_TEMPLATE = """
Your task is to generate a **skill package** based on the provided execution trajectory, skill name, and skill description.
This includes the main `SKILL.md` orchestration file and any necessary bundled resources (scripts, references, assets).

# Input Data
1. **Trajectory:** {trajectory}
2. **Skill Name:** {name}
3. **Skill Description:** {description}

# Skill Structure Standard
You must output the skill using the following directory structure:

```text
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter metadata (required)
│   │   ├── name: (required)
│   │   └── description: (required)
│   └── Markdown instructions (required)
└── Bundled Resources (optional)
    ├── scripts/          - Executable code (Python/Bash/etc.)
    ├── references/       - Documentation intended to be loaded into context as needed
    └── assets/           - Files used in output (templates, icons, fonts, etc.)
```

# Core Design Principles
1. Context is a Public Good: Be concise. Only add context in SKILL.md that is essential.
2. Progressive Disclosure:
- Keep SKILL.md lean.
- Offload heavy documentation/schemas to references/.
- Offload repeatable, deterministic logic to scripts/.
3. Degrees of Freedom:
- Use scripts (Low Freedom) for fragile, error-prone, or strict sequence tasks found in the trajectory.
- Use text instructions (High Freedom) for creative decisions.

# Output Format (STRICT)
You must output the files using the following strict format so that a script can parse and save them.
For every file (including SKILL.md, scripts, references, etc.), use this exact pattern:

## FILE: <directory_name>/<path_to_file>
```<language_tag_if_applicable>
<file_content_here>
```

**Example Output:**

## FILE: pdf-processor/SKILL.md
```yaml
---
name: pdf-processor
description: Extracts text from PDFs and summarizes them.
---
# Instructions
1. Run the extraction script.
2. Summarize the output.
```

## FILE: pdf-processor/scripts/extract.py
```python
import pdfplumber
# ... code ...
```

## FILE: pdf-processor/references/api_docs.md
```markdown
# API Documentation
...
```

Now, generate the complete skill package based on the provided trajectory, name, and description.
"""


SKILL_EVALUATION_PROMPT = """You will evaluate an AI Agent Skill using the metadata and (if present) the SKILL.md content, reference files, and scripts snippets below.
- Judge clarity, safety, and practical usability based on what is explicitly stated.
- If information is missing, reflect that in the rating and explain the uncertainty in the reason.

=== METADATA ===
- Name: {skill_name}
- Description: {skill_description}
- Category: {category}

=== SKILL.md ===
{skill_md_block}

=== REFERENCES/ ===
{references_block}

=== SCRIPTS/ ===
{scripts_block}

=== SCRIPT EXECUTION RESULTS ===
{script_exec_block}

Rating scale (3 levels only):
- Good: Clear, safe-by-default, and practically usable as described; low ambiguity; low risk.
- Average: Some ambiguity, missing caveats, or limited detail; likely usable but with notable gaps/risks.
- Poor: Vague, risky, misleading, or missing critical information; likely unsafe or impractical as described.

Evaluation dimensions and how to judge them (apply these rules even if the overall description looks polished; audit formulas/code/allowed_tools line-by-line and err on the side of conservative, lower ratings when you find subtle but impactful issues):

1) Safety
   Assess potential harm and misuse given what is described.
   Signals for Good:
   - Avoids destructive actions by default; includes safety checks/confirmations; mentions scope limits.
   - Does not encourage credential exfiltration, system damage, bypassing security, or unsafe automation.
   Signals for Average:
   - Benign domain, but no mention of safeguards for operations that could be risky (e.g., deployments, deletions).
   Signals for Poor:
   - Mentions or implies dangerous actions without safeguards (e.g., "delete/reset/disable security/steal/exploit").
   - Encourages unsafe tool usage or bypassing best practices.
   Additional guidance for Safety:
   - If allowed_tools grants broader permissions than what the Skill clearly needs (e.g., allows "bash" or other powerful tools but the described workflow and examples do not require them), reduce safety by at least one level compared to what it would otherwise be.
   - For health/medical-related Skills that provide advice or recommendations without an explicit disclaimer that it is NOT medical advice and NOT a substitute for professional diagnosis or treatment, safety MUST NOT be "Good" (its maximum allowed level is "Average").

2) Completeness
   Assess whether the description covers the essential steps/constraints to achieve its stated goal.
   Signals for Good:
   - Clear goal + clear steps/inputs/outputs; mentions prerequisites (env, packages, permissions) when relevant.
   - Mentions failure modes or edge cases at least briefly when they matter.
   Signals for Average:
   - Goal is clear, but steps/prereqs/outputs are underspecified; assumes context the user may not have.
   Signals for Poor:
   - Too vague to act on; missing core steps; unclear what "done" looks like.
   Additional guidance for Completeness:
   - If the core workflow lacks basic input validation that can obviously lead to crashes or meaningless outputs (e.g., division by zero for height <= 0, missing sanity checks on critical parameters), set completeness to at most "Average"; set it to "Poor" if this is likely to occur in realistic usage.
   - If you detect a CRITICAL CORRECTNESS ERROR in a core formula, algorithm, or code snippet (e.g., steps and code that contradict in a way that would cause wrong results), set completeness to at most "Average" and usually "Poor" if the error is central to the stated goal.
   - If the SKILL.md promises significant capabilities (e.g., multiple types of conversions, edits, or analyses) but the provided scripts and references only implement trivial placeholders (e.g., echoing input or “pretend success” messages) with no real logic for those capabilities, completeness MUST NOT be "Good" and is usually "Poor" because the implementation does not actually cover the described behavior.

3) Executability
   Assess whether an agent could realistically execute the described workflow with typical tools.
   Signals for Good:
   - Concrete actions and artifacts (commands, files, parameters); minimal ambiguity.
   - Avoids "hand-wavy" steps like "just configure X" without specifying how/where.
   - If script execution results are provided, successful runs support a higher rating.
   - **Instruction-only skills**: When the skill is designed to be executed purely through text instructions (e.g., guidelines, policies, brainstorming, design workflows) and does NOT require code execution, the absence of runnable scripts is acceptable. If SKILL.md provides clear, actionable guidance that an agent can follow using typical LLM tools (read files, apply guidelines, reason about content), rate executability as Good.
   Signals for Average:
   - Generally executable, but contains ambiguous steps or missing tool/environment assumptions.
   Signals for Poor:
   - Non-actionable ("optimize it", "make it work") with no operational detail; depends on unspecified systems.
   - If script execution results show failures/timeouts/missing dependencies, treat them as evidence about executability but do NOT automatically set executability to Poor. First classify whether the failure is due to unmet prerequisites in the evaluation/runtime environment (e.g., missing dependencies, missing input files/arguments, placeholders) versus a genuine defect or contradiction in the Skill's workflow/scripts; then adjust the rating accordingly.
   - If script execution was skipped due to missing required inputs, reflect missing prerequisites in the rating (usually Average).
   Additional guidance for Executability:
   - **Do NOT rate Poor solely because "No runnable python scripts found"**. Many skills (security guidelines, ideation, policies, design workflows) are instruction-only: the agent reads SKILL.md and follows the guidance with typical tools. For such skills, if the instructions are clear and actionable, executability should be Good.
   - If script execution fails due to an obvious documentation placeholder in an example command (e.g., tokens like "[options]", "<file>", "<pattern>", "{{path}}") or an argument parsing error caused by such placeholders, do NOT automatically set executability to Poor. Prefer Average and explain that the script likely needs real inputs or a concrete runnable example; only use Poor if there is additional evidence the workflow is not realistically executable.
   - If you detect any CRITICAL CORRECTNESS ERROR in a core formula, algorithm, or code snippet (e.g., Python using "^" for exponentiation or other language-level mistakes that would produce wrong results or runtime failures), executability MUST be "Poor".
   - If allowed_tools grants broader permissions than what the Skill clearly needs (e.g., allows "bash" or other powerful tools but the described workflow and examples do not require them), reduce executability by at least one level due to environment/permission ambiguity.
   - When reading formulas and code snippets, audit them line-by-line in the context of their target language and typical runtime environment; if you find subtle traps or inconsistencies that would mislead an implementer or cause incorrect behavior, choose a lower (more conservative) executability rating.
   - Do not treat a trivially successful script (e.g., one that only prints or echoes input without implementing the promised behavior) as strong evidence of executability; if the artifacts do not actually implement the key capabilities claimed in SKILL.md, executability should be at most "Average" and often "Poor".

4) Maintainability
   Assess how easy it would be to adjust/reuse/compose this Skill as described.
   Signals for Good:
   - Narrow, modular scope; clearly defined inputs/outputs; low coupling; safe to combine with other Skills.
   - Mentions configuration points or parameters rather than hard-coding assumptions.
   Signals for Average:
   - Some reusable parts, but unclear boundaries or assumptions; moderate coupling to a specific repo/tooling.
   Signals for Poor:
   - Overly broad or tightly coupled; unclear how to adapt; likely to conflict with other workflows.
   Additional guidance for Maintainability:
   - If the described capabilities are broad but the provided implementation is only a thin or trivial placeholder with no clear structure for where real logic should go, do not rate maintainability as "Good"; prefer "Average" because significant work is required to build the promised behavior safely and predictably.

5) Cost-awareness
   Assess whether the described approach is mindful of time/compute/money and operational overhead, given its domain.
   For clearly lightweight domains (e.g., documentation, brainstorming, simple text-only workflows) with no heavy data/infra hints:
   - Good: The task is inherently low-cost and the description does not suggest heavy loops, huge datasets, or expensive external services.
   For potentially heavy domains (e.g., data processing, infra, large-scale agents, external APIs, long-running jobs):
   - Good: Explicitly mentions batching/limits/caching/scope control or otherwise shows cost awareness.
   - Average: No explicit cost control is mentioned, but nothing suggests obviously wasteful behavior.
   - Poor: Encourages wasteful or unrealistic workflows without acknowledging cost/limits (e.g., "run huge jobs repeatedly", "scan all repos constantly").
   Examples:
   - Good: A batch processing Skill that explicitly limits file sizes or page counts and suggests sampling or pagination to control cost.
   - Average: A simple text summarizer that does not mention limits, but whose described usage clearly targets small inputs and occasional calls.
   - Poor: A monitoring Skill that recommends continuously re-scanning all repositories or documents at high frequency without any bounds or caching.

=== CONCRETE EVALUATION EXAMPLES ===

Example 1: BMI calculator Skill (health-related, wrong formula, no disclaimer)
- Observations:
  - SKILL.md provides a BMI formula using `weight / (height ^ 2)` in Python, which is a language-level error because `^` is bitwise XOR, not exponentiation.
  - It provides health-related recommendations (e.g., suggesting lifestyle or exercise changes) but does NOT include any disclaimer that this is not medical advice and not a substitute for a doctor.
  - There is no input validation for invalid heights (e.g., height <= 0) or obviously unrealistic values.
  - There are no runnable scripts that implement the calculation; only a faulty example snippet in SKILL.md.
- Expected ratings:
  - safety: "Average"
    - Reason: The domain is benign, but the Skill gives health advice without an explicit medical disclaimer or scope limits, creating a risk of over-reliance.
  - completeness: "Poor"
    - Reason: The core formula is incorrect in the target language and there is no input validation or handling of special cases, so critical detail is missing for reliable use.
  - executability: "Poor"
    - Reason: Following the formula as written in Python would not produce correct results, and there are no real scripts or commands to execute successfully.
  - maintainability: "Average"
    - Reason: Inputs and outputs (height, weight, BMI category) are conceptually clear, but the incorrect example and lack of validation make safe modification non-trivial.
  - cost_awareness: "Good"
    - Reason: The task is a simple numeric calculation with no heavy data or external services, so it is inherently low-cost.

Example 2: Quick task helper Skill (broad promise, placeholder implementation)
- Observations:
  - SKILL.md claims multiple capabilities (format conversion, simple file edits, brief summaries) but only lists high-level steps like "apply a minimal transformation" without concrete rules.
  - The only script (scripts/do_anything.py) merely echoes input or prints a success message; it does not implement any real conversion, editing, or summarization logic.
  - The domain is benign and there is no mention of dangerous tools or destructive actions.
- Expected ratings:
  - safety: "Good"
    - Reason: The operations are benign and the script does not perform destructive or risky actions.
  - completeness: "Poor"
    - Reason: The Skill promises a wide range of behaviors but does not specify formats, transformation rules, or error handling, and the implementation does not cover the described capabilities.
  - executability: "Poor"
    - Reason: Although the script technically runs, it is only a trivial placeholder; an agent following this Skill would not achieve the advertised conversions or edits.
  - maintainability: "Average"
    - Reason: The script is small and easy to edit, but there is no structure or guidance on where to implement the promised behaviors, so substantial work is needed to make it truly useful.
  - cost_awareness: "Good"
    - Reason: The intended tasks are quick, lightweight transformations with no indication of heavy computation or large-scale processing.

Example 3: Well-scoped document summarizer Skill (mostly solid)
- Observations:
  - SKILL.md describes a Skill that summarizes user-provided documents up to a clear size limit (e.g., "up to 10 pages or 5,000 words") and specifies that it will not access external systems.
  - It outlines concrete steps: load the document, chunk by paragraphs, generate summaries per chunk, then combine them, and mentions basic handling for unsupported file types.
  - There is no script, but the steps are specific and actionable with typical LLM tools.
- Expected ratings:
  - safety: "Good"
    - Reason: The Skill operates on user-provided content, does not touch external systems, and has no destructive actions.
  - completeness: "Good"
    - Reason: Inputs, steps, and limits are clearly specified, including handling for unsupported types and size bounds.
  - executability: "Good"
    - Reason: The workflow is concrete and can be followed using standard tools (e.g., text reading and summarization) without ambiguity.
  - maintainability: "Good"
    - Reason: The scope is narrow and modular, with clear points where chunking strategy or summary length can be adjusted.
  - cost_awareness: "Good"
    - Reason: The Skill explicitly caps document size and describes a strategy (chunking) that avoids unbounded compute.

Example 4: Instruction-only guideline Skill (e.g., security standards)
- Observations:
  - SKILL.md provides guidance on how to handle global security when working on code. It points to an external standards document for details.
  - There are no runnable Python scripts; script execution shows "No runnable python scripts found".
  - The workflow is: agent reads SKILL.md, loads the referenced document, and applies the guidelines when editing code.
- Expected ratings:
  - executability: "Good"
    - Reason: This is an instruction-only skill. The agent can execute the workflow by reading SKILL.md and the referenced file, then applying the guidelines with typical LLM tools. The absence of runnable scripts is acceptable because the skill does not require code execution.

Example 5: Overpowered deployment cleaner Skill (risky but technically executable)
- Observations:
  - SKILL.md describes a deployment cleanup tool that can delete old resources and restart services in production environments.
  - It grants broad permissions via allowed_tools (e.g., unrestricted shell access) and includes commands that can stop or remove services without confirmation.
  - Scripts implement the described behavior and script_execution results show successful runs on sample environments.
- Expected ratings:
  - safety: "Poor"
    - Reason: The Skill can perform destructive actions (deleting resources, stopping services) without explicit safeguards, confirmations, or guardrails.
  - completeness: "Average"
    - Reason: The main steps are described, but it does not clearly document rollback procedures, scoping rules, or safe usage patterns.
  - executability: "Good"
    - Reason: The scripts and commands are concrete and executable; script_execution results demonstrate that they run and perform real work.
  - maintainability: "Average"
    - Reason: While the scripts can be edited, the tight coupling to specific infrastructure and lack of configuration points make safe adaptation non-trivial.
  - cost_awareness: "Average"
    - Reason: The Skill does not appear to be compute-heavy, but it also does not explicitly address operational risk or cost; it neither optimizes nor clearly wastes resources.

Output requirements:
- Return STRICT JSON only (no prose, no markdown).
- Use exactly these keys: safety, completeness, executability, maintainability, cost_awareness.
- Each key must contain: level (Good/Average/Poor) and reason (1-2 sentences).
- The reason must cite concrete evidence from the provided content (metadata/SKILL.md/scripts), not imagined details.

Return the evaluation results in JSON format exactly like this:
{{
  "safety": {{
    "level": "Good/Average/Poor",
    "reason": "Reason for the rating (1-2 sentences)"
  }},
  "completeness": {{
    "level": "Good/Average/Poor",
    "reason": "Reason for the rating (1-2 sentences)"
  }},
  "executability": {{
    "level": "Good/Average/Poor",
    "reason": "Reason for the rating (1-2 sentences)"
  }},
  "maintainability": {{
    "level": "Good/Average/Poor",
    "reason": "Reason for the rating (1-2 sentences)"
  }},
  "cost_awareness": {{
    "level": "Good/Average/Poor",
    "reason": "Reason for the rating (1-2 sentences)"
  }}
}}

Remember: STRICT JSON only. """



# GitHub Repository to Skill Prompts

GITHUB_SKILL_SYSTEM_PROMPT = """You are an expert Technical Writer specializing in creating Skills for AI agents.
Your task is to analyze a GitHub repository and generate a comprehensive skill package that captures the repository's functionality and usage patterns.

CRITICAL REQUIREMENTS:
1. Generate COMPLETE content - do not truncate or abbreviate sections
2. Include ALL installation steps with actual commands from README
3. Extract CONCRETE code examples from README - copy them exactly, don't invent new ones
4. List specific models, APIs, or tools mentioned in the repository
5. For scripts/: Generate REAL, RUNNABLE Python code that demonstrates library usage
6. For references/: Generate DETAILED API documentation with actual function signatures
7. Follow the SkillNet skill structure standard exactly
8. Output files in parseable format with ## FILE: markers

SCRIPT QUALITY REQUIREMENTS:
- Scripts must be self-contained and runnable (no os.system('conda activate'))
- Scripts should demonstrate actual library API usage, not shell command wrappers
- Include proper imports, error handling, and docstrings
- If the library requires specific data, use placeholder paths with clear comments

REFERENCE QUALITY REQUIREMENTS:
- API references must include actual function signatures from code analysis
- Include parameter types, return types, and brief descriptions
- Organize by module/class hierarchy
- Reference the source file locations

Your output will be parsed by a script, so maintain strict formatting."""

GITHUB_SKILL_USER_PROMPT_TEMPLATE = """
Your task is to generate a complete skill package from the provided GitHub repository information.
This includes the main `SKILL.md` orchestration file and any necessary bundled resources.

# Input Data: GitHub Repository

## Repository Info
- **Name:** {repo_name}
- **URL:** {repo_url}
- **Description:** {repo_description}
- **Primary Language:** {language}
- **Languages Breakdown:** {languages_breakdown}
- **Stars:** {stars}
- **Topics:** {topics}

## README Content
{readme_content}

## File Structure
{file_tree}

## Code Analysis Summary
{code_summary}

# Skill Structure Standard
You must output the skill using the following directory structure:

```text
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter metadata (required)
│   │   ├── name: (required)
│   │   └── description: (required)
│   └── Markdown instructions (required)
└── Bundled Resources (required)
    ├── scripts/          - Executable Python code demonstrating library usage
    └── references/       - API documentation with function signatures
```

# SKILL.md Content Requirements (MUST INCLUDE ALL)

## 1. YAML Frontmatter (REQUIRED)
```yaml
---
name: skill-name-in-kebab-case
description: A when-to-use trigger statement explaining when this skill should be activated
---
```

## 2. When to Use Section (REQUIRED)
Clear description of scenarios where this skill should be activated. Include:
- Primary use cases
- Types of tasks it handles
- Keywords that should trigger this skill

## 3. Quick Reference Section (REQUIRED)
- Official documentation links
- Demo/playground URLs if available
- Key resources and references

## 4. Installation/Setup Section (REQUIRED - WITH ACTUAL COMMANDS)
Include complete installation commands exactly as shown in README:
- Prerequisites (Python version, system requirements)
- pip install commands
- Docker commands if available
- Environment setup steps

## 5. Core Features Section (REQUIRED)
List the main features/capabilities:
- Feature 1: Description
- Feature 2: Description
- Include any sub-modules or specialized tools

## 6. Usage Examples Section (REQUIRED - EXTRACT FROM README)
Include ACTUAL code examples from the README:
- Quick start code
- Common usage patterns
- Command-line examples

## 7. Key APIs/Models Section (REQUIRED)
List specific models, classes, or APIs mentioned:
- Model names (e.g., specific neural network architectures)
- API endpoints or function signatures
- Configuration options

## 8. Common Patterns & Best Practices (OPTIONAL)
Tips for effective usage

# scripts/ File Requirements (CRITICAL - HIGH QUALITY)

Generate Python scripts that ACTUALLY demonstrate how to use the library's API.

GOOD SCRIPT EXAMPLE (demonstrates actual API usage):
```python
#!/usr/bin/env python3
\"\"\"
Usage Example: Interacting with OpenAI API to Generate Text Responses

This script demonstrates how to use the OpenAI Python library to interact with
OpenAI's language models for text generation tasks.
Requires: pip install openai
\"\"\"

import os
from openai import OpenAI

def setup_api_key():
    \"\"\"
    Configure the environment with the OpenAI API key.
    \"\"\"
    os.environ["OPENAI_API_KEY"] = "YOUR_OPENAI_API_KEY"  # Replace with your actual API key

def generate_response(prompt: str, model: str = "gpt-4") -> str:
    \"\"\"
    Generate a text response using OpenAI's model with a given prompt.
    
    Args:
        prompt: The text input to pass to the model.
        model: The model identifier (e.g., "gpt-4", "gpt-3.5-turbo").
    
    Returns:
        The generated text from the model.
    \"\"\"
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=model,
            messages=[
                {{"role": "system", "content": "You are a helpful assistant."}},
                {{"role": "user", "content": prompt}}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"An error occurred while generating a response: {{e}}")
        return ""

if __name__ == "__main__":
    setup_api_key()
    response_text = generate_response("Explain quantum computing in simple terms.")
    print(f"Model Response: {{response_text}}")
```

# references/ File Requirements (CRITICAL - HIGH QUALITY)

Generate detailed API documentation based on the code analysis provided.

GOOD API REFERENCE EXAMPLE:
```markdown
# OpenAI Python Client API Reference

## Module: openai

### Class: OpenAI

Handles synchronous communications with OpenAI API for text generation, chat, and more.

**Constructor:**
```python
OpenAI(
    api_key: str = None,
    base_url: str = None,
    **kwargs
)
```

**Parameters:**
- `api_key` (str, optional): The API key for authenticating requests. Defaults to OPENAI_API_KEY environment variable.
- `base_url` (str, optional): Override the default API base URL.
- `kwargs`: Additional configuration options.

**Methods:**

#### chat.completions.create(model: str, messages: List[dict], **kwargs) -> ChatCompletion
Create a chat completion using the specified model.

**Parameters:**
- `model` (str): Model identifier (e.g., "gpt-4", "gpt-3.5-turbo").
- `messages` (List[dict]): List of message dictionaries with 'role' and 'content'.
- `temperature` (float, optional): Sampling temperature (0-2).
- `max_tokens` (int, optional): Maximum tokens to generate.

**Returns:**
- `ChatCompletion`: Response object containing generated text and metadata.

**Example:**
```python
from openai import OpenAI

client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {{"role": "system", "content": "You are a helpful assistant."}},
        {{"role": "user", "content": "Hello!"}}
    ]
)
print(response.choices[0].message.content)
```

---

### Class: AsyncOpenAI

Handles asynchronous interactions with OpenAI's API for efficient concurrent operations.

**Constructor:**
```python
AsyncOpenAI(
    api_key: str = None,
    **kwargs
)
```

**Parameters:**
- `api_key` (str, optional): The API key for authenticating requests.
- `kwargs`: Additional configuration options including HTTP client setups.

**Methods:**
- Same as `OpenAI` but returns awaitable objects.

**Example:**
```python
import asyncio
from openai import AsyncOpenAI

async def main():
    client = AsyncOpenAI()
    response = await client.chat.completions.create(
        model="gpt-4",
        messages=[{{"role": "user", "content": "Hello!"}}]
    )
    print(response.choices[0].message.content)

asyncio.run(main())
```
```

# Output Format (STRICT)
You must output the files using the following strict format so that a script can parse and save them.
For every file, use this exact pattern:

## FILE: {{actual-skill-name}}/{{path_to_file}}
```{{language_tag}}
{{file_content_here}}
```

**CRITICAL PATH RULES:**
- Replace `{{actual-skill-name}}` with the ACTUAL kebab-case skill name derived from the repository (e.g., "openai-python", "pandas", "requests")
- DO NOT use placeholder text like "skill-name" literally
- For repository "openai/openai-python" → use "openai-python"
- For repository "psf/requests" → use "requests"

**Example Output Pattern:**
```
## FILE: openai-python/SKILL.md
```markdown
---
name: openai-python
description: ...
---

# When to Use
...

## Installation
...
```

## FILE: openai-python/scripts/usage_example.py
```python
...
```

## FILE: openai-python/references/api_reference.md
```markdown
...
```
```

**IMPORTANT:**
- SKILL.md MUST use ```markdown as language tag and include ALL content (frontmatter + full body) inside ONE code block
- Generate COMPLETE files, do not use "..." or "[content continues]"
- SKILL.md should be comprehensive (at least 100+ lines)
- scripts/: At least one RUNNABLE Python script with actual library API usage
- references/: At least one DETAILED API reference with function signatures

Now, generate the complete skill package based on the provided GitHub repository information.
Focus on creating a practical, comprehensive skill that an AI agent can use to work with this repository.
DO NOT truncate content - include all relevant information from the README.
SCRIPTS must demonstrate actual Python API usage, not shell command wrappers.
REFERENCES must include actual function signatures and parameters."""


# ==========================================================================
# Office Document to Skill Prompts (PDF/PPT/Word)
# ==========================================================================

OFFICE_SKILL_SYSTEM_PROMPT = """You are an expert Technical Writer specializing in creating Skills for AI agents.
Your task is to analyze text content extracted from an office document (PDF, PPT, or Word) and convert it into a structured skill package.

CRITICAL REQUIREMENTS:
1. Identify the core knowledge, procedures, or guidelines from the document
2. Structure the content as a reusable AI skill
3. Extract actionable instructions that an AI agent can follow
4. Preserve key information while organizing it into the skill format
5. Generate appropriate scripts if the document describes code procedures
6. Create reference files for supplementary information

Output files in parseable format with ## FILE: markers."""

OFFICE_SKILL_USER_PROMPT_TEMPLATE = """
Your task is to convert the following document content into a structured skill package.

# Input: Document Content

**Source File:** {filename}
**File Type:** {file_type}

## Extracted Text Content:
{document_content}

# Skill Structure Standard
You must output the skill using the following directory structure:

```text
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter metadata (required)
│   │   ├── name: (required)
│   │   └── description: (required)
│   └── Markdown instructions (required)
└── Bundled Resources (optional but recommended)
    ├── scripts/          - Executable code if applicable
    └── references/       - Additional documentation or data
```

# Content Analysis Guidelines

1. **Identify the Skill Name**: Derive from document title or main topic
2. **Create Description**: Write a "when-to-use" trigger statement
3. **Extract Procedures**: Convert step-by-step instructions into actionable format
4. **Identify Code/Commands**: If the document contains code, create scripts/
5. **Supplementary Info**: Move detailed references to references/

# SKILL.md Requirements

## YAML Frontmatter (REQUIRED)
```yaml
---
name: skill-name-in-kebab-case
description: When-to-use trigger statement explaining when this skill should be activated
---
```

## Content Sections to Include:
- **Overview**: Brief summary of what this skill covers
- **When to Use**: Clear triggers for skill activation
- **Prerequisites**: Any required knowledge, tools, or setup
- **Instructions/Procedures**: Main actionable content from document
- **Examples**: Practical examples if available in source
- **References**: Links to additional resources mentioned

# Output Format (STRICT)
For every file, use this exact pattern:

## FILE: <skill-name>/<path_to_file>
```<language_tag>
<file_content_here>
```

Generate a complete, practical skill package from this document content.
Focus on making the knowledge actionable for an AI agent."""


# ==========================================================================
# Prompt-based Skill Generation (Direct User Description)
# ==========================================================================

PROMPT_SKILL_SYSTEM_PROMPT = """You are an expert Technical Writer specializing in creating Skills for AI agents.
Your task is to generate a complete skill package based on the user's description and requirements.

CRITICAL REQUIREMENTS:
1. Generate a comprehensive skill based on user's input
2. Create practical, actionable instructions
3. Include example scripts if the skill involves code
4. Add reference documentation where helpful
5. Make the skill reusable and well-structured

Think creatively about what resources would make this skill most useful.
Output files in parseable format with ## FILE: markers."""

PROMPT_SKILL_USER_PROMPT_TEMPLATE = """
Your task is to generate a complete skill package based on the following user description.

# User's Skill Request:
{user_input}

# Skill Structure Standard
You must output the skill using the following directory structure:

```text
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter metadata (required)
│   │   ├── name: (required)
│   │   └── description: (required)
│   └── Markdown instructions (required)
└── Bundled Resources (optional but recommended)
    ├── scripts/          - Executable code demonstrating the skill
    └── references/       - API docs, templates, or reference material
```

# Generation Guidelines

Based on the user's description, you should:

1. **Determine Skill Name**: Create a kebab-case name reflecting the skill's purpose
2. **Write Description**: Create a "when-to-use" trigger statement
3. **Design Instructions**: Write clear, step-by-step procedures
4. **Add Scripts**: If applicable, create Python scripts demonstrating the skill
5. **Include References**: Add any helpful reference documentation

# SKILL.md Requirements

## YAML Frontmatter (REQUIRED)
```yaml
---
name: skill-name-in-kebab-case
description: When-to-use trigger statement explaining when this skill should be activated
---
```

## Recommended Sections:
- **Overview**: What this skill does
- **When to Use**: Clear triggers for skill activation
- **Prerequisites**: Required tools, libraries, or knowledge
- **Quick Start**: Fastest way to use this skill
- **Detailed Instructions**: Comprehensive step-by-step guide
- **Examples**: Practical usage examples
- **Tips & Best Practices**: Common pitfalls and recommendations
- **Troubleshooting**: Common issues and solutions

# Output Format (STRICT)
For every file, use this exact pattern:

## FILE: <skill-name>/<path_to_file>
```<language_tag>
<file_content_here>
```

Now, generate a complete, high-quality skill package based on the user's request.
Be comprehensive and practical - create a skill that an AI agent would find genuinely useful."""


RELATIONSHIP_ANALYSIS_SYSTEM_PROMPT = """
You are the SkillNet Architect.
"""

RELATIONSHIP_ANALYSIS_USER_PROMPT_TEMPLATE = """
Your task is to map logical relationships between the provided skills based on their names and descriptions.

You must strictly identify ONLY the following 4 types of relationships:

1. similar_to
   - A and B perform functionally equivalent tasks (e.g., "Google Search" and "Bing Search").
   - Users can replace A with B.

2. belong_to
   - A is a sub-component or specific step within B.
   - B represents a larger workflow or agent, and A is just one part of it.
   - Direction: Child -> belong_to -> Parent.

3. compose_with
   - A and B are independent but often used together in a workflow.
   - One usually produces data that the other consumes, or they are logically paired.
   - Example: "PDF Parser" compose_with "Text Summarizer".

4. depend_on
   - A CANNOT execute without B.
   - B is a hard dependency (e.g., Environment setup, API Key loader, or a core library skill).
   - Direction: Dependent -> depend_on -> Prerequisite.

Here is the list of Skills in the user's local environment. Please analyze them and generate the relationships.

Skills List:
{skills_list}

Remember:
- Be conservative. Only create a relationship if there is a logical connection based on the name and description.
- Do not hallucinate skills not in the list.

Output Format:
Return a JSON array where each element represents a relationship with the following keys:
- source: (string) The name of the source skill (the one initiating the relationship)
- target: (string) The name of the target skill (the one receiving the relationship)
- type: (string) One of the 4 relationship types: "similar_to", "belong_to", "compose_with", "depend_on"
- reason: (string) A brief explanation of why this relationship exists based on the skill descriptions.

Output Example:
[
    {{
      "source": "google_search_tool",
      "target": "bing_search_tool",
      "type": "similar_to",
      "reason": "Both provide web search capabilities and are interchangeable."
    }},
    ...
]

Keep your output in the format below:
<Skill_Relationships>
your generated JSON array here
</Skill_Relationships>
"""
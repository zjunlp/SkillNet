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

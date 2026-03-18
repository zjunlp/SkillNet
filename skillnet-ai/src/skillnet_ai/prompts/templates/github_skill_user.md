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
"""
Usage Example: Interacting with OpenAI API to Generate Text Responses

This script demonstrates how to use the OpenAI Python library to interact with
OpenAI's language models for text generation tasks.
Requires: pip install openai
"""

import os
from openai import OpenAI

def setup_api_key():
    """
    Configure the environment with the OpenAI API key.
    """
    os.environ["OPENAI_API_KEY"] = "YOUR_OPENAI_API_KEY"  # Replace with your actual API key

def generate_response(prompt: str, model: str = "gpt-4") -> str:
    """
    Generate a text response using OpenAI's model with a given prompt.
    
    Args:
        prompt: The text input to pass to the model.
        model: The model identifier (e.g., "gpt-4", "gpt-3.5-turbo").
    
    Returns:
        The generated text from the model.
    """
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
REFERENCES must include actual function signatures and parameters.
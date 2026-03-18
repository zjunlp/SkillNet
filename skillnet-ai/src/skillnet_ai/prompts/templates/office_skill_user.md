
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
Focus on making the knowledge actionable for an AI agent.
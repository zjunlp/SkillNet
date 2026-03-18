
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
Be comprehensive and practical - create a skill that an AI agent would find genuinely useful.
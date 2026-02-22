---
description: Create a new Notion page with content from the current project or a custom prompt
argument-hint: "[page title] [optional: parent page ID or database ID]"
allowed-tools: ["Read", "Glob", "Grep", "Task", "TodoWrite"]
---

# Notion: Create Page

Create a new Notion page populated with relevant project content.

## Arguments

Parse `$ARGUMENTS` to extract:
- **Title**: The page title (first argument, or ask the user if not provided)
- **Parent ID**: Optional Notion parent page or database ID (second argument)

## Your Task

### Step 1: Gather Information

If `$ARGUMENTS` is empty or missing a title, ask the user:
- What should the page be titled?
- Where should it be created (parent page ID, database ID, or root workspace)?
- What content should it include?

### Step 2: Prepare Content

If the user wants to document the current project:
1. Use Glob to find key files: `README.md`, `package.json`, `pyproject.toml`, main source files
2. Read project documentation and extract relevant information
3. Identify the project's purpose, tech stack, and key components

If the user provides custom content, use that directly.

### Step 3: Launch the notion-page-creator Agent

Use the Task tool to launch the `notion-page-creator` agent:

```
{
  "subagent_type": "general-purpose",
  "description": "Create Notion page",
  "prompt": "You are creating a Notion page. Use the available Notion MCP tools to create a page with the following details:\n\nTitle: [TITLE]\nParent ID: [PARENT_ID or 'workspace root']\nContent: [CONTENT]\n\nUse the Notion MCP server tools to:\n1. If a parent ID was provided, verify it exists\n2. Create the page with well-structured content using appropriate Notion blocks (headings, paragraphs, code blocks, bullet lists)\n3. Return the created page URL and ID\n\nIMPORTANT: Format content using proper Notion block types for readability."
}
```

### Step 4: Report Results

After the agent completes:
- Display the created page URL to the user
- Confirm the page title and location
- Suggest next steps (e.g., adding more content, sharing the page)

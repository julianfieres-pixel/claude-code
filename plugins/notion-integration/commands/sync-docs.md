---
description: Sync project documentation (README, changelogs, API docs) to a Notion page
argument-hint: "[notion page ID or URL] [optional: --files <glob pattern>]"
allowed-tools: ["Read", "Glob", "Grep", "Task", "TodoWrite", "AskUserQuestion"]
---

# Notion: Sync Documentation

Sync your project's documentation files to a Notion page, keeping it up to date with your codebase.

## Arguments

Parse `$ARGUMENTS`:
- **Page ID / URL**: The target Notion page to sync content into (required)
- **--files**: Optional glob pattern to select specific files (default: `README.md`, `CHANGELOG.md`, docs/)

## Your Task

### Step 1: Parse Arguments

Extract:
- Target Notion page ID or URL from `$ARGUMENTS`
- Optional file pattern (after `--files` flag)

If no page ID is provided, ask the user:
- "Which Notion page should the documentation be synced to? Please provide the page ID or URL."
- "Would you like to create a new page instead?"

### Step 2: Discover Documentation Files

Use Glob to find documentation files in the project:
1. Always include: `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`
2. Include docs directories: `docs/**/*.md`, `documentation/**/*.md`
3. If `--files` was provided, use that glob pattern instead
4. Skip files matching: `node_modules/`, `.git/`, `vendor/`

Report to the user which files were found.

### Step 3: Read and Process Documentation

For each discovered file:
1. Read the file content
2. Extract headings and key sections
3. Prepare content for Notion format

### Step 4: Launch notion-content-formatter Agent

Use the Task tool to format and sync content:

```
{
  "subagent_type": "general-purpose",
  "description": "Format and sync docs to Notion",
  "prompt": "You are syncing project documentation to Notion. Use the Notion MCP tools to:\n\n1. Retrieve the current content of page ID: [PAGE_ID]\n2. Clear existing content (archive old blocks)\n3. Create well-structured Notion blocks from the following documentation:\n\n[FORMATTED_CONTENT]\n\nFormatting guidelines:\n- Use heading_1 for file names/major sections\n- Use heading_2 for H2 markdown headings\n- Use heading_3 for H3 markdown headings\n- Convert markdown code blocks to Notion code blocks with language\n- Convert bullet lists to bulleted_list_item blocks\n- Convert numbered lists to numbered_list_item blocks\n- Preserve links where possible\n- Add a 'Last synced' timestamp at the top\n\nReturn the page URL after syncing."
}
```

### Step 5: Confirm Sync

After the agent completes:
- Show the synced page URL
- List which files were synced
- Suggest setting up a git hook or CI step to auto-sync on changes

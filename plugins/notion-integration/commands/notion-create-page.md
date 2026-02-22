---
description: Create a new Notion page, optionally pre-populated from the current file or git diff
argument-hint: [page title]
---

Create a new page in the user's Notion workspace. The page title can be provided as an argument or collected interactively.

## Context

Requested title (may be empty): `$ARGUMENTS`

## Instructions

### 1. Check setup

If no Notion MCP tools are available, tell the user:

> The Notion integration isn't configured yet. Run `/notion:setup` to get started.

Stop here if MCP is not available.

### 2. Collect required information

Ask the following questions **one at a time**, skipping any already answered by `$ARGUMENTS` or clear from context:

**a) Page title**
If `$ARGUMENTS` is empty, ask: "What would you like to title the new page?"

**b) Parent location**
Ask: "Where should the page be created? Options:
- Top-level (workspace root)
- Inside an existing page (I'll search for it)
- Inside a database (I'll search for it)"

If they choose an existing page or database, use the Notion search MCP tool to find it. Show the top 5 matches and let them confirm.

**c) Initial content**
Ask: "What content should the page start with? Options:
- Empty page
- Content from the current file (`[filename]` if one is open)
- A summary of recent git changes
- Custom content (you describe it)"

Wait for each answer before asking the next.

### 3. Prepare content

Based on the user's choice:

**Empty page**: Proceed with no body content.

**Current file**: Read the file that is currently open or most recently referenced in the conversation. Format it as Notion-compatible rich text blocks (headings, paragraphs, code blocks as appropriate).

**Git changes**: Run `git log --oneline -10` and `git diff HEAD~1 --stat` to summarize recent changes. Create a brief changelog-style summary.

**Custom content**: Use the description the user provides.

### 4. Create the page

Call the Notion MCP create-page tool with:
- `parent`: the page ID or database ID selected in step 2 (or workspace root)
- `properties`: `{ "title": [{ "text": { "content": "<title>" } }] }`
- `children`: the content blocks prepared in step 3 (if any)

### 5. Confirm creation

Report success:

> Page created successfully!
>
> **Title**: <page title>
> **Location**: <parent page/database name or "Workspace root">
> **URL**: <notion.so/...>
>
> Open it in Notion: <URL>

If creation fails, show the error and suggest:
- Verify the integration has "Insert content" capability enabled
- Ensure the integration is connected to the parent page/database

### 6. Offer follow-up

> What would you like to do next?
> - Add more content to this page
> - Create another page
> - Search Notion (`/notion:search`)

## Notes

- Keep page titles concise — Notion titles have a practical limit around 2000 characters
- When converting file content to Notion blocks: map markdown headings to heading blocks, code fences to code blocks, and prose to paragraph blocks
- Do not include raw HTML in Notion blocks — convert to plain text or supported block types
- If creating inside a database, the `title` property name may differ (e.g., "Name") — use the database's actual title property key

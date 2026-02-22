---
description: Sync content between the local project and Notion (export files → Notion or import pages → local markdown)
---

Sync content between the current project and the user's Notion workspace. Supports two directions: **export** (local → Notion) and **import** (Notion → local).

## Instructions

### 1. Check setup

If no Notion MCP tools are available, tell the user:

> The Notion integration isn't configured yet. Run `/notion:setup` to get started.

Stop here if MCP is not available.

### 2. Choose sync direction

Ask the user:

> Which direction would you like to sync?
>
> **Export** — push local content to Notion
> - Sync a file or directory summary to an existing Notion page
> - Create a new Notion page from a local file
>
> **Import** — pull Notion content to a local file
> - Download a Notion page as a markdown file
> - Pull a Notion database table into a local CSV or markdown table

Wait for their choice.

---

## Export: Local → Notion

### E1. Select source content

Ask: "What would you like to export?
- A specific file (provide path or I'll use the currently open file)
- A directory README / summary
- The current git diff / changelog
- Something else"

### E2. Select target Notion page

Ask: "Where should the content go in Notion?
- An existing page (I'll search for it)
- A new page (I'll create it)"

If existing: use the Notion search tool to find the page. Show the top 5 matches and ask the user to confirm the destination.

If new: ask for a title and parent location, then create the page first.

### E3. Prepare the content

Read the selected file(s) using the Read tool. Convert the content:

- Markdown headings (`#`, `##`, `###`) → Notion heading_1, heading_2, heading_3 blocks
- Code fences (``` ``` ```) → Notion code blocks with language
- Bullet/numbered lists → Notion bulleted/numbered list item blocks
- Plain paragraphs → Notion paragraph blocks
- Bold/italic/inline code → Notion rich text annotations

Limit total content to 100 blocks (Notion API limit per request). If the file is larger, summarize or paginate and inform the user.

### E4. Write to Notion

Use the Notion MCP append-block-children (or update-page) tool to push the content to the target page.

**Conflict handling**: If the target page already has content, ask:
- Replace existing content
- Append to the end
- Cancel

### E5. Confirm

Report:
> Export complete!
>
> **Source**: `<file path>`
> **Destination**: <Notion page title>
> **URL**: <notion.so/...>
> **Blocks written**: <count>

---

## Import: Notion → Local

### I1. Find the Notion page

Ask: "Which Notion page would you like to import?" Accept:
- A search query (use the Notion search tool)
- A direct Notion page URL or ID

Show matching pages and ask the user to confirm.

### I2. Read the Notion page

Use the Notion MCP retrieve-page and retrieve-block-children tools to fetch the page content.

Recursively fetch child blocks as needed (up to 3 levels deep to avoid excessive API calls).

### I3. Convert to markdown

Convert Notion blocks to standard markdown:
- heading_1/2/3 → `#`/`##`/`###`
- paragraph → plain text
- code → fenced code block with language
- bulleted_list_item → `- `
- numbered_list_item → `1. `
- toggle → `> ` blockquote
- divider → `---`
- callout → `> **Note**: ...`

### I4. Select destination

Ask: "Where should the markdown file be saved?
- Provide a file path
- Use the page title as filename in the current directory (e.g., `<page-title>.md`)"

Check if the file already exists. If it does, ask:
- Overwrite
- Append
- Save to a new filename

### I5. Write the file

Write the converted markdown using the Write tool.

Report:
> Import complete!
>
> **Source**: <Notion page title>
> **Destination**: `<local file path>`
> **Content**: <word count> words, <block count> blocks converted

---

## Notes

- Notion API rate limit: 3 requests/second. For large operations, add small delays between requests.
- The Notion MCP server handles authentication automatically — no need to pass tokens manually in tool calls.
- Database rows are not supported in basic sync — use the `notion-assistant` agent for complex database operations.
- Always confirm before overwriting existing content (local files or Notion pages).

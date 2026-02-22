---
description: Guidance for working with Notion through Claude Code. Auto-invoked when the user asks about saving to Notion, creating Notion pages, or documenting projects in Notion.
triggers:
  - "notion"
  - "save to notion"
  - "create notion page"
  - "notion page"
  - "notion database"
  - "sync to notion"
  - "document in notion"
---

# Notion Integration Skill

You have access to Notion integration capabilities through the Notion MCP server.

## Available Commands

Use these slash commands for common Notion tasks:

- **`/notion:create-page`** - Create a new page in Notion
  - Provide a title and optional parent page ID
  - Can auto-populate with project documentation

- **`/notion:search`** - Search your Notion workspace
  - Finds pages, databases, and content

- **`/notion:sync-docs`** - Sync project documentation to Notion
  - Syncs README.md, CHANGELOG.md, and docs/ directory
  - Keeps a Notion page up-to-date with your codebase

## Direct MCP Usage

If you have the Notion MCP server connected, you can also use Notion tools directly for:

### Reading Content
- Retrieve page content by ID
- List databases
- Query database entries

### Creating Content
- Create new pages with blocks
- Append content to existing pages
- Create database entries

### Searching
- Search across the entire workspace
- Filter by page type, last edited date

## Setup Requirements

The Notion integration requires:

1. **Notion API Key**: Create an integration at https://www.notion.so/my-integrations
   ```bash
   export NOTION_API_KEY=secret_your_key_here
   ```

2. **Page Permissions**: Share target pages/databases with your integration in Notion

3. **MCP Server**: The `@notionhq/notion-mcp-server` package (auto-installed via npx)

## Best Practices

- **Page IDs**: Extract from Notion URLs (the 32-character hex string)
- **Content Structure**: Use headings and lists for better readability in Notion
- **Sync Strategy**: Use `/notion:sync-docs` for ongoing documentation sync; use `/notion:create-page` for one-time page creation
- **Databases**: For structured data (tasks, issues), prefer Notion databases over pages

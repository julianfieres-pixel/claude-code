# Notion Integration Plugin

Integrate Claude Code with [Notion](https://www.notion.so) to create pages, search your workspace, and sync project documentation directly from your terminal.

## Features

- **Create Pages**: Generate Notion pages from project files or custom content
- **Search Workspace**: Find pages, databases, and content across your Notion workspace
- **Sync Documentation**: Keep Notion pages in sync with your project's README and docs
- **Auto-formatting**: Converts markdown to Notion-native block structure
- **MCP Integration**: Uses the official Notion MCP server for reliable API access

## Setup

### 1. Create a Notion Integration

1. Go to [https://www.notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **"New integration"**
3. Give it a name (e.g., "Claude Code")
4. Select the workspace you want to connect
5. Copy the **Internal Integration Token** (starts with `secret_`)

### 2. Set Your API Key

```bash
export NOTION_API_KEY=secret_your_token_here
```

Add this to your shell profile (`~/.bashrc`, `~/.zshrc`) to persist across sessions.

### 3. Share Notion Pages with Your Integration

For any Notion page you want to access:
1. Open the page in Notion
2. Click **"..."** menu → **"Add connections"**
3. Select your integration

### 4. Install the Plugin

```bash
claude --plugin-dir /path/to/plugins/notion-integration
```

Or configure in your project's `.claude/settings.json`:

```json
{
  "plugins": [
    {
      "source": "./plugins/notion-integration"
    }
  ]
}
```

## Commands

### `/notion:create-page [title] [parent-id]`

Create a new Notion page with content from your project or custom input.

```bash
# Create a page at workspace root
/notion:create-page "My Project Documentation"

# Create a page under a specific parent
/notion:create-page "API Reference" abc123def456...
```

**What it does:**
- Reads project files (README, package.json, etc.) if requested
- Formats content using appropriate Notion block types
- Creates the page via the Notion API
- Returns the page URL

### `/notion:search <query>`

Search your Notion workspace for pages and databases.

```bash
/notion:search "project roadmap"
/notion:search "authentication"
```

**What it does:**
- Searches across all connected Notion pages
- Returns titles, URLs, and last-edited dates
- Offers follow-up actions (open, create new, sync)

### `/notion:sync-docs [page-id] [--files <pattern>]`

Sync your project documentation to an existing Notion page.

```bash
# Sync README and CHANGELOG to a Notion page
/notion:sync-docs abc123def456...

# Sync specific files
/notion:sync-docs abc123def456... --files "docs/**/*.md"
```

**What it does:**
- Discovers documentation files in your project
- Converts markdown to Notion blocks
- Updates the target page with fresh content
- Adds a "last synced" timestamp

## Agents

### `notion-page-creator`

Specialized agent for creating Notion pages. Handles API interactions, content structuring, and error recovery.

### `notion-content-formatter`

Specialized agent for converting markdown and project documentation into Notion-native block format with proper formatting.

## MCP Server

This plugin uses the official `@notionhq/notion-mcp-server` package. It's automatically installed via `npx` when needed—no manual installation required.

The MCP server provides direct access to Notion API endpoints:
- `GET /pages/:id` - Retrieve a page
- `POST /pages` - Create a page
- `GET /search` - Search the workspace
- `PATCH /blocks/:id/children` - Append blocks to a page

## Troubleshooting

### "NOTION_API_KEY is not set"
Set the environment variable: `export NOTION_API_KEY=secret_...`

### "Object not found" errors
Ensure the target page has been shared with your Notion integration. Open the page → "..." → "Add connections" → select your integration.

### MCP server not starting
Ensure `npx` is available: `npm install -g npx`

### Content not syncing correctly
Large documents may need to be split. The Notion API accepts up to 100 blocks per request and 2000 characters per block.

## Privacy

This plugin sends your content to the Notion API. Review Notion's [privacy policy](https://www.notion.so/privacy) before syncing sensitive information.

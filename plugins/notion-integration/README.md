# Notion Integration Plugin

Connect Claude Code to your Notion workspace. Search pages, create content, manage databases, and sync documentation — all from your terminal.

## Overview

The Notion Integration Plugin bridges Claude Code with the [Notion API](https://developers.notion.com/) via the official [Notion MCP server](https://github.com/makenotion/notion-mcp-server). It lets you read and write to Notion without leaving your editor, so you can keep documentation, project specs, and task lists in sync with your codebase.

## Prerequisites

- A Notion account with an **integration** (API key)
- `npx` available (comes with Node.js)

## Setup

Run the setup command once to configure your integration token and wire up the MCP server:

```
/notion:setup
```

This will:
1. Guide you through creating a Notion integration at <https://www.notion.so/profile/integrations>
2. Ask for your **Internal Integration Secret** (`ntn_...`)
3. Write the MCP server config to `.claude/settings.local.json`
4. Verify the connection by listing your accessible pages

> **Security note**: Your token is stored in `.claude/settings.local.json`, which is excluded from git by default. Never commit API keys.

## Commands

### `/notion:setup`

Interactive one-time setup. Configures the Notion MCP server with your API token and verifies connectivity.

```
/notion:setup
```

### `/notion:search [query]`

Search your Notion workspace for pages, databases, or blocks matching the query.

```
/notion:search API design decisions
/notion:search project roadmap
```

### `/notion:create-page [title]`

Create a new Notion page. Optionally pre-populate it from context (open file, git diff, selected text).

```
/notion:create-page
/notion:create-page "Sprint 42 Retrospective"
```

### `/notion:sync`

Sync content between the current project and Notion. Supports two modes:

- **Export**: Push a file or directory summary into a Notion page
- **Import**: Pull a Notion page's content into a local markdown file

```
/notion:sync
```

## Agent: `notion-assistant`

A persistent Notion assistant that can handle multi-step operations — building complex database queries, bulk-updating pages, or turning a Notion page into a structured spec document.

Trigger it by asking naturally:

```
Turn the ARCHITECTURE.md file into a Notion page in my Engineering wiki
Find all Notion pages tagged "bug" and summarize them
Add a row to my Tasks database for the current PR
```

## Architecture

```
plugins/notion-integration/
├── README.md
├── commands/
│   ├── notion-setup.md        # /notion:setup
│   ├── notion-search.md       # /notion:search
│   ├── notion-create-page.md  # /notion:create-page
│   └── notion-sync.md         # /notion:sync
└── agents/
    └── notion-assistant.md    # notion-assistant agent
```

The plugin uses the `@notionhq/notion-mcp-server` MCP server which exposes Notion API operations as tools that Claude can call directly.

## Troubleshooting

**"Could not connect to Notion"**
- Check your token starts with `ntn_` (Internal Integration Secret)
- Ensure the integration has been added to the pages/databases you want to access (open the page → ··· → Connections → add your integration)

**"Page not found"**
- The integration can only see pages it has been explicitly connected to
- Go to the target page in Notion and connect your integration

**MCP server not starting**
- Run `npx @notionhq/notion-mcp-server` manually to check for errors
- Ensure Node.js ≥ 18 is installed: `node --version`

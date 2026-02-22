---
description: Set up the Notion MCP integration — configure your API token and verify connectivity
---

You are helping the user connect Claude Code to their Notion workspace. Walk through the setup interactively, one step at a time.

## Step 1 — Check for an existing configuration

Read `.claude/settings.local.json` (if it exists) and check whether a Notion MCP server entry is already present under `mcpServers.notionApi`. If it exists, ask the user whether they want to reconfigure it or just verify the existing connection.

## Step 2 — Explain what's needed

Tell the user:

> To connect to Notion, you need a **Notion Internal Integration Secret**. Here's how to get one:
>
> 1. Go to <https://www.notion.so/profile/integrations>
> 2. Click **"New integration"**
> 3. Give it a name (e.g., "Claude Code") and select your workspace
> 4. Under **Capabilities**, enable: Read content, Update content, Insert content
> 5. Click **Save**, then copy the **Internal Integration Secret** — it starts with `ntn_`
>
> After creating the integration you'll also need to **connect it to your pages**:
> - Open any Notion page you want Claude to access
> - Click **···** (top right) → **Connections** → find and add your integration

Ask: "Do you have your Internal Integration Secret ready? (It starts with `ntn_`)"

Wait for the user to confirm before continuing.

## Step 3 — Collect the token

Ask the user to paste their token. Remind them it will be stored only in `.claude/settings.local.json` (gitignored) and never logged.

Validate that the provided value:
- Starts with `ntn_` OR is a valid `secret_` prefixed token (older format)
- Is at least 40 characters long

If validation fails, explain the issue and ask them to try again.

## Step 4 — Write the MCP server configuration

Read the existing `.claude/settings.local.json` if it exists (create an empty `{}` structure if not). Merge in the Notion MCP server configuration:

```json
{
  "mcpServers": {
    "notionApi": {
      "command": "npx",
      "args": ["-y", "@notionhq/notion-mcp-server"],
      "env": {
        "OPENAPI_MCP_HEADERS": "{\"Authorization\": \"Bearer <TOKEN>\", \"Notion-Version\": \"2022-06-28\"}"
      }
    }
  }
}
```

Replace `<TOKEN>` with the actual token the user provided.

Write the updated JSON back to `.claude/settings.local.json`, preserving any existing keys.

Tell the user:
> Configuration written to `.claude/settings.local.json`. This file is excluded from git by default — your token stays local.

## Step 5 — Verify connectivity

Inform the user that Claude Code needs to be restarted to load the new MCP server. Tell them:

> The Notion MCP server will be active after you restart Claude Code. Once restarted, you can verify the connection by running `/notion:search test` or asking me to list your Notion pages.

If the user is running in a session where MCP tools are already available, attempt to call `API-search-notion` or equivalent Notion MCP tool with the query `""` (empty search to list recent pages). Report the result:

- **Success**: List the first few page titles returned and confirm connectivity.
- **Failure**: Show the error message and provide troubleshooting steps:
  - Confirm the token is correct
  - Ensure `npx` is available (`npx --version`)
  - Check the integration is connected to at least one Notion page

## Step 6 — Next steps

Once setup is complete, tell the user what they can do next:

> **You're connected to Notion!** Try these commands:
>
> - `/notion:search <query>` — search pages and databases
> - `/notion:create-page` — create a new page
> - `/notion:sync` — sync a file or directory to/from Notion
>
> Or ask me naturally: "Find the API design doc in Notion" or "Add a task to my Notion board."

## Important notes

- Never print the full token in plain text after the user provides it — use `ntn_****` when referencing it
- If `.claude/settings.local.json` has other keys (e.g., existing MCP servers), preserve them — only add/update the `mcpServers.notionApi` entry
- If the user declines to provide a token, explain they can run `/notion:setup` again whenever they're ready

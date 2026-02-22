#!/usr/bin/env bash

# Notion Integration Plugin - SessionStart Hook
# Checks for Notion API key and provides context to Claude

NOTION_KEY_SET=false
CONTEXT_MSG=""

if [ -n "$NOTION_API_KEY" ]; then
  NOTION_KEY_SET=true
fi

if [ "$NOTION_KEY_SET" = true ]; then
  CONTEXT_MSG="The Notion integration plugin is active and configured. The NOTION_API_KEY environment variable is set. You have access to Notion MCP tools for reading and writing Notion pages and databases.\n\nAvailable Notion commands:\n- /notion:create-page - Create a new Notion page\n- /notion:search - Search the Notion workspace\n- /notion:sync-docs - Sync project documentation to Notion\n\nWhen the user asks about Notion or asks you to save/document something in Notion, proactively suggest using these commands."
else
  CONTEXT_MSG="The Notion integration plugin is installed but NOTION_API_KEY is not set. If the user wants to use Notion features, remind them to:\n1. Create a Notion integration at https://www.notion.so/my-integrations\n2. Set the API key: export NOTION_API_KEY=secret_...\n3. Share the relevant Notion pages with their integration\n\nAvailable Notion commands (require API key):\n- /notion:create-page - Create a new Notion page\n- /notion:search - Search the Notion workspace\n- /notion:sync-docs - Sync project documentation to Notion"
fi

cat << EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "$CONTEXT_MSG"
  }
}
EOF

exit 0

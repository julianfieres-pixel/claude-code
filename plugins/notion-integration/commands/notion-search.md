---
description: Search your Notion workspace for pages, databases, or blocks
argument-hint: [search query]
---

Search the connected Notion workspace for content matching the provided query.

## Context

The user wants to search Notion. Their query is: `$ARGUMENTS`

If `$ARGUMENTS` is empty, ask the user what they want to search for before proceeding.

## Instructions

### 1. Check setup

If no Notion MCP tools are available (the `notionApi` MCP server is not connected), tell the user:

> It looks like the Notion integration isn't configured yet. Run `/notion:setup` to get started.

Stop here if MCP is not available.

### 2. Execute the search

Use the Notion MCP search tool to search for `$ARGUMENTS`. The tool is typically named `API-search-notion` or similar — use whatever Notion search tool is available.

Pass the query string from `$ARGUMENTS`.

### 3. Display results

Format the results in a clear, readable list:

```
Found X results for "<query>":

1. [Page Title]
   Type: Page | Database | Database row
   Last edited: <date>
   URL: <notion.so/...>

2. [Page Title]
   ...
```

If no results are found:
> No results found for "<query>". Make sure your Notion integration is connected to the pages you want to search. (Page → ··· → Connections → add your integration)

### 4. Follow-up actions

After displaying results, offer helpful follow-up options based on context:

- If results look like documentation: "Would you like me to read the content of any of these pages?"
- If results look like task databases: "Want me to show the items in one of these databases?"
- If the user might want to create content: "Didn't find what you need? I can create a new page with `/notion:create-page`."

## Notes

- Limit display to the top 10 results to avoid overwhelming output
- Show the full Notion URL so the user can open the page directly in their browser
- If the query contains special characters, pass it as-is — the MCP server handles encoding

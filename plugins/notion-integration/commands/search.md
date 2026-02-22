---
description: Search your Notion workspace for pages, databases, or content
argument-hint: "<search query>"
allowed-tools: ["Task", "TodoWrite"]
---

# Notion: Search

Search your Notion workspace and display results in a readable format.

## Arguments

`$ARGUMENTS` contains the search query. If empty, ask the user what they want to search for.

## Your Task

### Step 1: Get Search Query

If `$ARGUMENTS` is provided, use it as the search query.
If empty, ask: "What would you like to search for in Notion?"

### Step 2: Perform Search

Use the Notion MCP tools directly to:
1. Call the Notion search API with the query from `$ARGUMENTS`
2. Filter results to show the most relevant pages and databases
3. Retrieve titles, URLs, and last-edited dates for top results (limit to 10)

### Step 3: Display Results

Present results in a clear, scannable format:

```
Found X results for "[query]":

1. [Page Title]
   URL: [notion URL]
   Last edited: [date]
   Type: [Page / Database]

2. [Page Title]
   ...
```

If no results are found, suggest:
- Checking spelling
- Using broader search terms
- Using `/notion:create-page` to create a new page on this topic

### Step 4: Offer Follow-up Actions

After showing results, ask if the user wants to:
- Open one of the results
- Create a new page based on search results
- Sync project documentation to a found page

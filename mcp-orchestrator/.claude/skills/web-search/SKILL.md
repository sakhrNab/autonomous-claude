---
name: web-search
description: "Search the web for information. Use for finding latest news, documentation, answers."
allowed-tools: Bash
---

# Web Search Skill

## Quick Start

Search the web for any information.

## Providers

1. **Brave Search** (Recommended)
   - Requires `BRAVE_API_KEY`
   - Best results, structured data

2. **DuckDuckGo** (Fallback)
   - May be blocked (CAPTCHA)
   - No API key needed

## Usage Examples

```
Search for latest AI news
Find React documentation 2025
Look up Python best practices
```

## Query Optimization

- Be specific: "React hooks tutorial" > "React"
- Add year for recent info: "Python 3.12 features 2024"
- Use quotes for exact phrases

## Output Format

```json
{
  "query": "...",
  "results": [
    {
      "title": "Result title",
      "url": "https://...",
      "snippet": "Description..."
    }
  ],
  "source": "brave-search"
}
```

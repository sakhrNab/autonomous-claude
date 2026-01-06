---
name: web-scrape
description: "Extract content from any website intelligently. Use for headlines, articles, data extraction."
allowed-tools: Read, Bash
---

# Web Scraping Skill

## Quick Start

Scrape any website and extract structured content.

## Usage Examples

```
Scrape headlines from bbc.com
Extract product info from amazon.com/product/123
Get article content from medium.com/article
```

## Extraction Patterns

### Headlines/News
- Look for `<h1>`, `<h2>`, `<h3>` tags
- Check for `article`, `news`, `headline` classes
- Extract JSON-LD structured data

### Products
- Find price patterns: `$XX.XX`, `USD`, etc.
- Look for product name, description, images
- Check meta tags for product info

### Articles
- Main content in `<article>` or `<main>` tags
- Author in `<meta name="author">` or byline classes
- Published date in `<time>` or meta tags

## Fallback Chain

1. Firecrawl (if available)
2. httpx + Claude extraction
3. Direct HTTP fetch

## Output Format

```json
{
  "success": true,
  "url": "https://...",
  "content": [
    {"title": "Headline 1"},
    {"title": "Headline 2"}
  ],
  "method": "universal_scraper"
}
```

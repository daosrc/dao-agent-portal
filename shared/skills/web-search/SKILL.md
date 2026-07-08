# Skill: web-search

# Web Search - Multiple Methods

Use multiple free search methods to get real-time information, news, and answers from the web.

This skill provides several approaches to web search, from fully free APIs to user-provided API keys.

---

## When to Use

Use this skill when you need to:

- **Search the web** for real-time information
- **Find news articles** and current events
- **Get answers** to factual questions
- **Discover content** across multiple sources
- **Research topics** with or without API keys

---

## Available Search Methods

### Method 1: SearXNG (Free, No API Key)
Open-source metasearch engine aggregating results from multiple search engines.

**Status:** May require finding working public instances

**Recommended Public Instances:**
- `https://search.sapti.me`
- `https://searx.be`
- `https://paulgo.io`
- `https://searx.tiekoetter.com`

Full list: https://searx.space

### Method 2: User-Provided API Keys (Recommended)
For reliable, production-grade search, use APIs with user-provided keys:

- **Brave Search API** - Free 2000 queries/month
- **Serper API** - Free 2500 queries/month (Google results)
- **Tavily API** - AI-optimized search
- **SerpAPI** - Multi-engine support

### Method 3: Specialized Free APIs (Verified Working)
- **Hacker News Algolia API** - Tech news search, fully free, no auth needed ✓
- **GitHub Search API** - Repository/code search, no auth (60 req/hr unauthed) ✓
- **Wikipedia API** - Knowledge base search
- **Reddit API** - Community discussions

---

## How to Use

### 1. Basic Web Search

Search the web and get JSON results:

```bash
curl -s "https://search.sapti.me/search?q=YOUR_QUERY&format=json" | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
for r in data.get('results', [])[:10]:
    print(f\"Title: {r.get('title', 'N/A')}\"[:100])
    print(f\"URL: {r.get('url', 'N/A')}\")
    print(f\"Content: {r.get('content', 'N/A')}\"[:200])
    print('---')
"
```

### 2. Search with Category Filter

Filter by category (general, news, images, videos, etc.):

```bash
# News search
curl -s "https://search.sapti.me/search?q=AI+news&categories=news&format=json"

# Images
curl -s "https://search.sapti.me/search?q=sunset&categories=images&format=json"

# Videos
curl -s "https://search.sapti.me/search?q=tutorial&categories=videos&format=json"
```

### 3. Search Specific Engines

Search using specific search engines:

```bash
# Google only
curl -s "https://search.sapti.me/search?q=climate+change&engines=google&format=json"

# DuckDuckGo only  
curl -s "https://search.sapti.me/search?q=climate+change&engines=duckduckgo&format=json"

# Wikipedia
curl -s "https://search.sapti.me/search?q=artificial+intelligence&engines=wikipedia&format=json"

# Multiple engines
curl -s "https://search.sapti.me/search?q=news&engines=google,bing,duckduckgo&format=json"
```

### 4. Time Range Filter

Get recent results only:

```bash
# Last day
curl -s "https://search.sapti.me/search?q=breaking+news&time_range=day&format=json"

# Last week
curl -s "https://search.sapti.me/search?q=tech+news&time_range=week&format=json"

# Last month
curl -s "https://search.sapti.me/search?q=events&time_range=month&format=json"

# Last year
curl -s "https://search.sapti.me/search?q=research&time_range=year&format=json"
```

### 5. Language Filter

Search in specific languages:

```bash
# English
curl -s "https://search.sapti.me/search?q=news&language=en&format=json"

# Chinese
curl -s "https://search.sapti.me/search?q=新闻&language=zh&format=json"

# Auto-detect
curl -s "https://search.sapti.me/search?q=YOUR_QUERY&language=auto&format=json"
```

### 6. Paginated Results

Get more results with pagination:

```bash
# Page 1 (default)
curl -s "https://search.sapti.me/search?q=python&format=json"

# Page 2
curl -s "https://search.sapti.me/search?q=python&pageno=2&format=json"

# Page 3
curl -s "https://search.sapti.me/search?q=python&pageno=3&format=json"
```

---

## Response Format

SearXNG returns JSON with this structure:

```json
{
  "query": "your search query",
  "number_of_results": 42,
  "results": [
    {
      "title": "Page Title",
      "url": "https://example.com",
      "content": "Page description or snippet",
      "engine": "google",
      "parsed_url": ["https", "example.com", "/path", "", "", ""],
      "engines": ["google", "bing"],
      "positions": [1],
      "score": 1.0,
      "category": "general"
    }
  ],
  "answers": [],
  "corrections": [],
  "infoboxes": [],
  "suggestions": [],
  "unresponsive_engines": []
}
```

**Key Fields:**

| Field | Description |
|-------|-------------|
| `results` | Array of search results |
| `title` | Page title |
| `url` | Page URL |
| `content` | Description/snippet |
| `engine` | Source engine (google, bing, etc.) |
| `engines` | All engines that returned this result |
| `score` | Relevance score |
| `answers` | Direct answers (like Wikipedia summaries) |
| `infoboxes` | Rich info boxes |
| `suggestions` | Search suggestions |

---

## Practical Examples

### Example 1: Get Latest AI News

```bash
curl -s "https://search.sapti.me/search?q=artificial+intelligence+news&categories=news&time_range=week&format=json" | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f\"Found {len(data.get('results', []))} results\n\")
for i, r in enumerate(data.get('results', [])[:5], 1):
    print(f\"{i}. {r.get('title', 'N/A')}\")
    print(f\"   {r.get('url', 'N/A')}\")
    print(f\"   {r.get('content', 'N/A')[:150]}...\n\")
"
```

### Example 2: Quick Answer Search

```bash
# Search with direct answers (like "What is Python?")
curl -s "https://search.sapti.me/search?q=what+is+quantum+computing&format=json" | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
answers = data.get('answers', [])
if answers:
    print('ANSWER:', answers[0])
else:
    print('Top result:', data['results'][0].get('content', 'N/A')[:300])
"
```

### Example 3: Search with Fallback

```bash
# Try primary instance, fallback to secondary
curl -s "https://search.sapti.me/search?q=YOUR_QUERY&format=json" || \
  curl -s "https://searx.be/search?q=YOUR_QUERY&format=json"
```

### Example 4: Multi-Engine Aggregation

```bash
# Search across Google, Bing, DuckDuckGo, Wikipedia
curl -s "https://search.sapti.me/search?q=climate+change&engines=google,bing,duckduckgo,wikipedia&format=json" | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
results = data.get('results', [])[:10]
for r in results:
    engines = ', '.join(r.get('engines', []))
    print(f\"{r.get('title')}\")
    print(f\"  Sources: {engines}\")
    print(f\"  URL: {r.get('url')}\n\")
"
```

---

## API Parameters Reference

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `q` | string | Search query (required) | `q=artificial intelligence` |
| `format` | string | Response format | `format=json` (or `html`, `csv`) |
| `categories` | string | Filter by category | `categories=general`, `news`, `images`, `videos`, `music`, `files`, `it`, `science` |
| `engines` | string | Comma-separated engines | `engines=google,bing,duckduckgo` |
| `language` | string | Search language | `language=en`, `zh`, `auto` |
| `pageno` | int | Page number | `pageno=1` (default), `pageno=2` |
| `time_range` | string | Time filter | `day`, `week`, `month`, `year` |
| `safesearch` | int | Safe search level | `0` (off), `1` (moderate), `2` (strict) |

---

## Available Search Engines

Common engines you can use with `engines=` parameter:

**General:**
- `google`, `bing`, `duckduckgo`, `yahoo`, `qwant`, `brave`

**News:**
- `google news`, `bing news`, `yahoo news`, `reddit`

**Academic:**
- `google scholar`, `arxiv`, `pubmed`, `semantic scholar`

**Tech:**
- `github`, `stackoverflow`, `gitlab`, `dockerhub`

**Media:**
- `youtube`, `vimeo`, `soundcloud`, `bandcamp`

**Reference:**
- `wikipedia`, `wiktionary`, `wikiquote`

---

## Available Categories

Use with `categories=` parameter:

- `general` - General web search (default)
- `news` - News articles
- `images` - Image search
- `videos` - Video search
- `music` - Music and audio
- `files` - File downloads
- `it` - IT/programming resources
- `science` - Scientific papers
- `social media` - Social networks

---

## Best Practices

1. **URL encode queries**: Replace spaces with `+` or `%20`
2. **Handle timeouts**: Some instances may be slow, add timeout or fallback
3. **Parse carefully**: Not all results have all fields
4. **Respect instances**: Don't spam requests, add delays for bulk searches
5. **Use fallbacks**: Keep 2-3 instances ready in case one is down
6. **Filter results**: Use categories and engines to get relevant results
7. **Check `unresponsive_engines`**: Some engines may fail

---

## Error Handling

```bash
# Search with error handling
QUERY="YOUR_QUERY"
INSTANCE="https://search.sapti.me"

response=$(curl -s -w "\n%{http_code}" "$INSTANCE/search?q=$QUERY&format=json")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | head -n-1)

if [ "$http_code" = "200" ]; then
    echo "$body" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin), indent=2))"
else
    echo "Error: HTTP $http_code"
    # Try fallback instance
    curl -s "https://searx.be/search?q=$QUERY&format=json"
fi
```

---

## Quick Start Example

```bash
# Simple news search
curl -s "https://search.sapti.me/search?q=OpenAI+GPT-5&categories=news&time_range=week&format=json" | \
  python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(f\"Query: {data.get('query')}\")
    print(f\"Results: {data.get('number_of_results', 0)}\n\")
    
    for i, result in enumerate(data.get('results', [])[:5], 1):
        print(f\"{i}. {result.get('title', 'No title')}\")
        print(f\"   {result.get('url', '')}\")
        snippet = result.get('content', '')[:200]
        if snippet:
            print(f\"   {snippet}...\")
        print()
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
"
```

---

## Troubleshooting

**Issue: Empty results**
- Try different instance (some may be down)
- Check query encoding
- Try broader search terms

**Issue: Slow response**
- Use faster instance (check https://searx.space for uptime stats)
- Reduce number of engines
- Add curl timeout: `curl --max-time 10`

**Issue: JSON parse error**
- Instance may be down, try fallback
- Check response is actually JSON: `curl -i` to see headers

---

## Instance Health Check

Test if an instance is working:

```bash
# Quick health check
curl -s "https://search.sapti.me/search?q=test&format=json" | python3 -c "import json,sys; print('OK' if json.load(sys.stdin).get('results') else 'FAIL')"
```

---

## Alternative: Use Multiple Instances for Reliability

```bash
# Try instances in order until one works
INSTANCES=(
    "https://search.sapti.me"
    "https://searx.be"
    "https://search.bus-hit.me"
    "https://priv.au"
)

QUERY="$1"

for instance in "${INSTANCES[@]}"; do
    echo "Trying $instance..."
    response=$(curl -s --max-time 5 "$instance/search?q=$QUERY&format=json")
    if [ $? -eq 0 ] && echo "$response" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
        echo "Success with $instance"
        echo "$response" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin)['results'][:3], indent=2))"
        break
    fi
done
```

---

## Using WebFetch as a Search Fallback

When other APIs are unavailable, use the `WebFetch` tool to directly access web pages.

### Best Search Alternatives via WebFetch

```
# Use these URLs in WebFetch tool:
# Google News RSS
https://news.google.com/rss/search?q=YOUR_QUERY&hl=en

# Wikipedia
https://en.wikipedia.org/w/api.php?action=opensearch&search=YOUR_QUERY&limit=5&format=json

# Hacker News search (via Algolia)
https://hn.algolia.com/api/v1/search?query=YOUR_QUERY&tags=story

# GitHub search (repos)
https://api.github.com/search/repositories?q=YOUR_QUERY&sort=stars
```

### Example: Hacker News Search (Always Free, No Auth)

```bash
curl -s "https://hn.algolia.com/api/v1/search?query=AI+news&tags=story&numericFilters=created_at_i>$(date -v -7d +%s)" | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
hits = data.get('hits', [])
print(f'Found {len(hits)} results\n')
for i, hit in enumerate(hits[:5], 1):
    print(f'{i}. {hit.get(\"title\", \"N/A\")}')
    print(f'   Points: {hit.get(\"points\", 0)}  Comments: {hit.get(\"num_comments\", 0)}')
    url = hit.get('url', f'https://news.ycombinator.com/item?id={hit.get(\"objectID\")}')
    print(f'   {url}')
    print()
"
```

### Example: GitHub Repository Search

```bash
curl -s "https://api.github.com/search/repositories?q=YOUR_QUERY&sort=stars&per_page=5" | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f'Total: {data.get(\"total_count\", 0)} repos\n')
for r in data.get('items', []):
    print(f'{r[\"full_name\"]} - ★{r[\"stargazers_count\"]}')
    print(f'  {r.get(\"description\", \"no description\")}')
    print(f'  {r[\"html_url\"]}')
    print()
"
```

---

## Recommended Setup for API Key Search

If you want reliable Google/Bing search results, set an API key as an environment variable:

```bash
# In ~/.zshrc or ~/.bashrc, add one of:
export BRAVE_API_KEY="your_key_here"        # https://brave.com/search/api/
export SERPER_API_KEY="your_key_here"       # https://serper.dev
export TAVILY_API_KEY="your_key_here"       # https://tavily.com
```

Then search:

```bash
# Brave Search (Free tier: 2000/month)
curl -s -H "X-Subscription-Token: $BRAVE_API_KEY" \
  "https://api.search.brave.com/res/v1/web/search?q=YOUR_QUERY&count=10" | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
for r in data.get('web', {}).get('results', [])[:5]:
    print(f'{r[\"title\"]}')
    print(f'  {r[\"url\"]}')
    print(f'  {r.get(\"description\", \"\")}')
    print()
"

# Serper (Free tier: 2500/month)
curl -s -X POST 'https://google.serper.dev/search' \
  -H "X-API-KEY: $SERPER_API_KEY" \
  -H 'Content-Type: application/json' \
  -d "{\"q\": \"YOUR_QUERY\"}" | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
for r in data.get('organic', [])[:5]:
    print(f'{r[\"title\"]}')
    print(f'  {r[\"link\"]}')
    print(f'  {r.get(\"snippet\", \"\")}')
    print()
"
```

---

Base directory for this skill: file:///Users/mihuashi-rd/.agents/skills/web-search

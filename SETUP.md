# Setup Guide - E-Commerce Scraper

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your API key:
```bash
cp .env.example .env
# Edit .env with your GROQ_API_KEY
```

Get your API key from [Groq Console](https://console.groq.com)

### 3. Run the Scraper
```bash
python main.py "https://example.com/products" [max_pages]

# Examples:
python main.py "https://www.peaksports.tn/collections/chaussures" 1
python main.py "https://www.mytek.tn/informatique/ordinateur-de-bureau/pc-de-bureau.html" 3
```

## Configuration

All settings are centralized in `config.py` and can be customized via environment variables in `.env`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `GROQ_API_KEY` | (required) | Groq API key for LLM-based selector detection |
| `GROQ_MODEL` | llama-3.1-70b-versatile | LLM model to use |
| `REQUEST_TIMEOUT` | 15 | HTTP request timeout in seconds |
| `BROWSER_HEADLESS` | true | Run browser in headless mode |
| `MAX_PAGES_DEFAULT` | 10 | Default max pages to scrape |
| `MAX_SCROLLS` | 6 | Max scroll attempts to load lazy-loaded content |
| `BROWSER_WINDOW_WIDTH` | 1920 | Browser window width |
| `BROWSER_WINDOW_HEIGHT` | 1080 | Browser window height |

## Architecture

The scraper uses a **platform-detection routing pattern**:

1. **Platform Detection** → Identifies e-commerce platform (Shopify, WooCommerce, etc.)
2. **Smart Routing** → Routes to specialized scraper:
   - ✅ **Shopify** → Fast API scraper (no browser)
   - ✅ **WooCommerce** → REST API with Selenium fallback
   - 🤖 **React/Vue SPA** → XHR/Fetch intercept with DOM fallback
   - 🤖 **Other** → Selenium + LLM/CSS selectors

## Modules

- **`main.py`** - Entry point, coordinates scraping
- **`detector.py`** - Platform detection
- **`api_scrapers.py`** - Fast API-based scrapers (Shopify, WooCommerce)
- **`selenium_scraper.py`** - Browser automation + LLM selector detection
- **`spa_scraper.py`** - Network request interception for SPAs
- **`config.py`** - Centralized configuration

## Logging

The scraper uses Python's standard logging module. Control verbosity via environment:

```python
import logging
logging.basicConfig(level=logging.DEBUG)  # For verbose output
```

## Error Handling

All modules use specific exception catching instead of bare `except` clauses:

- `requests.Timeout` - Request timeouts
- `requests.HTTPError` - HTTP errors
- `json.JSONDecodeError` - Invalid JSON responses
- `Exception` - Other unexpected errors logged with full context

## Output

Products are saved to `products.json` by default (configurable via `OUTPUT_FILENAME`):

```json
[
  {
    "name": "Product Name",
    "price": "99.99",
    "url": "https://..."
  },
  ...
]
```

## Files Structure

```
scraper/
├── config.py                 # Configuration management
├── .env                      # Environment variables (git-ignored)
├── .env.example              # Template for .env
├── requirements.txt          # Python dependencies
├── .gitignore               # Git ignore rules
├── main.py                  # Entry point
├── detector.py              # Platform detection
├── api_scrapers.py          # Shopify & WooCommerce APIs
├── selenium_scraper.py      # Selenium + LLM selectors
├── spa_scraper.py           # SPA/XHR scraping
├── products.json            # Output (git-ignored)
└── SETUP.md                 # This file
```

## Improvements Made

### High Priority ✅
- **Config Management**: Centralized `config.py` with environment variables
- **Logging**: Replaced all `print()` with Python logging module
- **Error Handling**: Specific exception catching instead of bare `except`
- **Dependencies**: Created `requirements.txt` with pinned versions
- **Environment Setup**: Added `.env.example` template
- **Git Hygiene**: Added comprehensive `.gitignore`

### What's Next
- [ ] Add unit tests for core functions
- [ ] Implement data validation/schema
- [ ] Add request caching layer
- [ ] Implement rate limiting
- [ ] Add scheduled scraping (scheduler.py)
- [ ] Add data storage options (storage.py)
- [ ] Add price tracking/history (tracker.py)
- [ ] Add data cleaning utilities (cleaner.py)

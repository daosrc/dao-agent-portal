#!/usr/bin/env python3
"""
Qiniu AI Token Usage Query Tool
Query token usage for the Qiniu AI API (api.qnaigc.com) with cost calculation.

Usage:
    python3 qiniu_usage.py [OPTIONS]

Options:
    --granularity   day | hour   (default: day)
    --start         Start date, e.g. 2026-02-01 or 2026-02-01T00:00:00+08:00
    --end           End date,   e.g. 2026-02-25 or 2026-02-25T23:59:59+08:00
    --days          Shortcut: query last N days (default: 7)
    --today         Shortcut: query today only
    --month         Shortcut: query current month
    --json          Output raw JSON instead of formatted table
    --cost          Show cost calculation (USD + CNY)
    --update-prices Fetch latest prices from sufy.com
    --update-rate   Fetch latest USD/CNY exchange rate
    --api-key       Override API key (default: reads QINIU_AI_API_KEY env)
    --list-prices   List all cached model prices
"""

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta, timezone
from typing import Optional

# ── Constants ────────────────────────────────────────────────────────────────

BASE_URL = "https://api.qnaigc.com"
USAGE_PATH = "/v2/stat/usage"
PRICING_URL = "https://sufy.com/zh-CN/services/ai-inference/models"

# Modelink 模型广场（Qiniu 模型定价的权威来源）— 页面内嵌 pricingRules JSON
MODELINK_MODELS_URL = "https://modelink.ai/zh-CN/models"
MODELINK_HISTORICAL_URL = "https://modelink.ai/historical-pricing.json"
PRICES_CACHE_FILE = os.path.expanduser("~/.cache/qiniu_prices.json")
CST = timezone(timedelta(hours=8))  # China Standard Time (UTC+8)

# Exchange rate API (free, no key required)
EXCHANGE_RATE_API = "https://api.exchangerate-api.com/v4/latest/USD"

# Default USD to CNY exchange rate (fallback when API unavailable)
DEFAULT_USD_TO_CNY = 7.25

# Default pricing (USD per 1M tokens) - fallback when cache unavailable
# Source: https://sufy.com/zh-CN/services/ai-inference/models
# NOTE: input = standard (non-cached) input price; sufy.com renders some prices via JS,
#       so web scraping may only capture the cached-input price ($0.30). These defaults
#       reflect the correct non-cached input prices.
DEFAULT_PRICING = {
    # Claude 4 Series
    "claude-4.6-sonnet": {"input": 3.0, "output": 15.0},
    "anthropic/claude-sonnet-5": {"input": 3.0, "output": 15.0},
    "claude-4.6-opus": {"input": 15.0, "output": 75.0},
    "claude-4.5-sonnet": {"input": 3.0, "output": 15.0},
    "claude-4.5-haiku": {"input": 1.0, "output": 5.0},
    "claude-4.5-opus": {"input": 15.0, "output": 75.0},
    "claude-4.0-sonnet": {"input": 3.0, "output": 15.0},
    "claude-4.0-opus": {"input": 15.0, "output": 75.0},
    "claude-4.1-opus": {"input": 15.0, "output": 75.0},
    # Claude 3 Series
    "claude-3.5-sonnet": {"input": 3.0, "output": 15.0},
    "claude-3.5-haiku": {"input": 0.8, "output": 4.0},
    "claude-3.7-sonnet": {"input": 3.0, "output": 15.0},
    # OpenAI GPT Series
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
    "gpt-5": {"input": 1.25, "output": 10.0},
    "gpt-5.2": {"input": 1.75, "output": 14.0},
    # Gemini
    "gemini-3.5-flash": {"input": 0.50, "output": 9.0},
    "gemini-3.1-pro-image": {"input": 2.0, "output": 12.0},
    "gemini-3.1-flash-image": {"input": 0.50, "output": 1.50},
    "gemini-3.1-flash-lite-image": {"input": 0.25, "output": 1.50},
    "gemini-3.1-flash-lite": {"input": 0.15, "output": 1.50},
    "google/gemini-3.1-flash-lite-image": {"input": 0.25, "output": 1.50},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.0},
    "gemini-2.5-flash": {"input": 0.15, "output": 2.5},
    "gemini-2.0-flash": {"input": 0.15, "output": 0.6},
    # DeepSeek
    "deepseek-v3": {"input": 0.278, "output": 1.11},
    "deepseek-v3.1": {"input": 0.556, "output": 1.67},
    "deepseek-r1": {"input": 0.556, "output": 2.22},
    "deepseek/deepseek-v4-pro-202606": {"input": 0.4348, "output": 0.8696},
    "deepseek/deepseek-v4-flash-20260731": {"input": 0.1449, "output": 0.2899},
    # Doubao
    "doubao-1.5-pro-32k": {"input": 0.111, "output": 0.278},
    "doubao-seed-1.6": {"input": 0.111, "output": 0.278},
    # Qwen
    "qwen-turbo": {"input": 0.042, "output": 0.417},
    "qwen3-max": {"input": 0.833, "output": 3.33},
    # GLM
    "glm-4.5": {"input": 0.556, "output": 2.22},
    "glm-4.6": {"input": 1.0, "output": 1.75},
    # Kimi
    "kimi-k2": {"input": 0.556, "output": 2.22},
    # Video Generation (Kling) — priced per second, not per token
    "kling-video/kling-3.0-turbo": {"input": 0.111, "output": 0.139},
    # Video Generation (Vidu) — priced per second, not per token
    "vidu/viduq3": {"input": 0.030, "output": 0.052},
    "viduq3-pro": {"input": 0.061, "output": 0.130},
    # Z-AI Text Models
    "z-ai/glm-5.2": {"input": 0.97, "output": 3.89},
    "anthropic/claude-fable-5": {"input": 10.0, "output": 50.0},
}

# Manual price overrides — authoritative source: anthropic.com/pricing + sufy.com
# sufy.com static HTML only exposes cached-input prices for Claude models;
# these entries ensure the correct non-cached standard input price is always used.
# Last updated: 2026-06-15
PRICE_OVERRIDES = {
    # Claude 4 current models (source: anthropic.com/pricing)
    "claude-4.6-sonnet":          {"input": 3.0,  "output": 15.0},
    # Anthropic Claude Sonnet 5 (source: qiniu pricing) — 非缓存输入 $3.00/M, 缓存输入 $0.30/M, 输出 $15.00/M
    "anthropic/claude-sonnet-5":  {"input": 3.0,  "output": 15.0},
    "claude-4.8-opus":            {"input": 5.0,  "output": 25.0},
    "claude-4.7-opus":            {"input": 5.0,  "output": 25.0},
    "claude-4.5-sonnet":          {"input": 3.0,  "output": 15.0},
    "claude-4.5-haiku":           {"input": 1.0,  "output": 5.0},
    "claude-4.5-opus":            {"input": 5.0,  "output": 25.0},
    "claude-4.0-sonnet":          {"input": 3.0,  "output": 15.0},
    "claude-4.0-opus":            {"input": 15.0, "output": 75.0},
    "claude-4.1-opus":            {"input": 15.0, "output": 75.0},
    "claude-4.6-opus":            {"input": 5.0,  "output": 25.0},
    # Gemini Image models (source: sufy.com)
    "google/gemini-3.1-flash-lite-image": {"input": 0.25, "output": 1.50},
    "gemini-3.1-flash-lite-image":       {"input": 0.25, "output": 1.50},
    "gemini-3.1-flash-lite":             {"input": 0.15, "output": 1.50},
    "gemini-3.1-flash-image":            {"input": 0.50, "output": 1.50},
    "gemini-3.1-pro-image":              {"input": 2.00, "output": 12.0},
    "gemini-3.5-flash":                  {"input": 0.50, "output": 9.0},
    # DeepSeek V4 (source: sufy.com, confirmed from screenshot)
    "deepseek/deepseek-v4-pro-202606": {"input": 0.4348, "output": 0.8696},
    "deepseek/deepseek-v4-pro":   {"input": 1.67, "output": 3.33},
    "deepseek-v4-pro":            {"input": 1.67, "output": 3.33},
    "deepseek/deepseek-v4-flash": {"input": 0.14, "output": 0.28},
    "deepseek-v4-flash":          {"input": 0.14, "output": 0.28},
    # Z-AI/GLM-5.2 non-cached input (sufy.com only exposes cached input via static HTML)
    "z-ai/glm-5.2":              {"input": 0.97, "output": 3.89},
    # Anthropic Claude Fable 5 (source: qiniu pricing screenshot)
    #   非缓存输入 $10.00/M | 缓存输入 $1.00/M | 缓存创建 $12.50/M | 1h缓存创建 $20.00/M
    #   输出 $50.00/M | 联网搜索 $0.01/次
    "anthropic/claude-fable-5": {"input": 10.0, "output": 50.0},
    # Anthropic Claude Opus 5 (source: qiniu pricing)
    #   非缓存输入 $5.00/M | 缓存输入 $0.50/M | 缓存创建 $6.25/M | 1h缓存创建 $10.00/M
    #   输出 $25.00/M | 联网搜索 $0.01/次
    "anthropic/claude-opus-5": {"input": 5.0, "output": 25.0},
    # OpenAI GPT-5.6 Luna (source: qiniu pricing)
    #   非缓存输入 $0.20/M | 缓存输入 $0.02/M | 缓存创建 $0.25/M
    #   输出 $1.20/M (≤272k) / $1.80/M (>272k)；长输入档 非缓存输入 $0.40/M
    "openai/gpt-5.6-luna": {"input": 0.20, "output": 1.20},
    # OpenAI GPT-5.6 Sol (source: qiniu pricing)
    #   非缓存输入 $5.00/M | 缓存输入 $0.50/M | 缓存创建 $6.25/M
    #   输出 $30.00/M (≤272k) / $45.00/M (>272k)；长输入档 非缓存输入 $10.00/M
    "openai/gpt-5.6-sol": {"input": 5.0, "output": 30.0},
    # Moonshot Kimi K3 (source: qiniu pricing)
    #   非缓存输入 $2.8986/M | 缓存输入 $0.2899/M | 输出 $14.4928/M
    "moonshotai/kimi-k3": {"input": 2.8986, "output": 14.4928},
    # DeepSeek V4 Flash 20260731 (source: qiniu pricing)
    #   非缓存输入 $0.1449/M | 缓存输入 $0.0029/M | 输出 $0.2899/M
    "deepseek/deepseek-v4-flash-20260731": {"input": 0.1449, "output": 0.2899},
    # OpenAI GPT-6 Astra (source: modelink.ai / qiniu pricing)
    #   非缓存输入 $10.00/M | 缓存输入 $1.00/M | 缓存创建 $12.50/M
    #   输出 $50.00/M (≤272k) / $75.00/M (>272k)；长输入档 非缓存输入 $20.00/M
    "openai/gpt-6-astra": {"input": 10.0, "output": 50.0},
    # Video Generation models — priced per second, included for reference
    "kling-video/kling-3.0-turbo": {"input": 0.111, "output": 0.139},
    "vidu/viduq3":                {"input": 0.030, "output": 0.052},
    "viduq3-pro":                 {"input": 0.061, "output": 0.130},
}


# ── Price Management ────────────────────────────────────────────────────────


def get_exchange_rate() -> float:
    """Fetch current USD to CNY exchange rate."""
    try:
        req = urllib.request.Request(
            EXCHANGE_RATE_API,
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            rate = data.get("rates", {}).get("CNY", DEFAULT_USD_TO_CNY)
            print(f"Fetched exchange rate: 1 USD = ¥{rate:.4f} CNY", file=sys.stderr)
            return rate
    except Exception as e:
        print(f"Failed to fetch exchange rate: {e}", file=sys.stderr)
        return DEFAULT_USD_TO_CNY


def _migrate_prices(prices: dict) -> dict:
    """Migrate old price format (input_price_per_m) to new format (input)."""
    migrated = {}
    for model, p in prices.items():
        if "input_price_per_m" in p or "output_price_per_m" in p:
            migrated[model] = {
                "input": p.get("input_price_per_m", 0.0),
                "output": p.get("output_price_per_m", 0.0),
            }
        else:
            migrated[model] = p
    return migrated


def load_prices() -> tuple[dict, float]:
    """Load prices and exchange rate from cache or return defaults.

    Cached prices (sourced from the modelink.ai pricing API via
    `--update-prices`) are authoritative; the hardcoded PRICE_OVERRIDES only
    fill in models the cache does not cover.
    """
    if os.path.exists(PRICES_CACHE_FILE):
        try:
            with open(PRICES_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                prices = _migrate_prices(data.get("prices", DEFAULT_PRICING))
                for name, pricing in PRICE_OVERRIDES.items():
                    prices.setdefault(name, pricing)
                return prices, data.get("exchange_rate", data.get("rate", DEFAULT_USD_TO_CNY))
        except (json.JSONDecodeError, IOError):
            pass
    return {**DEFAULT_PRICING, **PRICE_OVERRIDES}, DEFAULT_USD_TO_CNY


def save_prices(prices: dict, exchange_rate: float, source: str = MODELINK_MODELS_URL) -> None:
    """Save prices and exchange rate to cache file."""
    os.makedirs(os.path.dirname(PRICES_CACHE_FILE), exist_ok=True)
    data = {
        "updated": datetime.now(CST).isoformat(),
        "source": source,
        "exchange_rate": exchange_rate,
        "prices": prices,
    }
    with open(PRICES_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_model_name(name: str) -> str:
    """Normalize model name for consistent matching."""
    name = name.strip().lower()
    # Replace spaces and slashes with dashes
    name = re.sub(r"[\s/]+", "-", name)
    # Remove multiple consecutive dashes
    name = re.sub(r"-+", "-", name)
    # Remove common prefixes/suffixes
    name = name.strip("-")
    return name


def parse_html_prices(html: str) -> dict:
    """Parse model prices from sufy.com HTML."""
    prices = {}

    # Model names are in <h3> tags
    h3_pattern = re.compile(r'<h3[^>]*>([^<]+)</h3>', re.IGNORECASE)

    # Price pattern: <span...text-gray-500...>非缓存输入</span><span...text-blue-400...>$X.XX /M tokens</span>
    price_pattern = re.compile(
        r'<span[^>]*text-gray-500[^>]*>(输入|输出|非缓存输入|缓存输入|批量输入|思考输入|思考输出)</span>'
        r'.*?'
        r'<span[^>]*text-blue-400[^>]*>\$([\d.]+)\s*/M\s*tokens</span>',
        re.DOTALL | re.IGNORECASE
    )

    # Find all h3 positions
    h3_matches = list(h3_pattern.finditer(html))

    # For each h3, find the prices that follow until the next h3
    for i, h3_match in enumerate(h3_matches):
        model_name = h3_match.group(1).strip()
        start_pos = h3_match.end()

        # Find the end of this card (next h3 or end of content)
        if i + 1 < len(h3_matches):
            end_pos = h3_matches[i + 1].start()
        else:
            end_pos = len(html)

        card_content = html[start_pos:end_pos]

        # Find prices in this card
        # Priority for input: 非缓存输入 > 输入 > 批量输入 > 思考输入 > 缓存输入
        # "非缓存输入" is the standard input price; "缓存输入" is the discounted cache-hit price
        input_prices = {}  # price_type -> value
        output_price = None

        for price_match in price_pattern.finditer(card_content):
            price_type = price_match.group(1)
            price_value = float(price_match.group(2))

            if price_type in ['输入', '非缓存输入', '缓存输入', '批量输入', '思考输入']:
                if price_type not in input_prices:
                    input_prices[price_type] = price_value
            elif price_type in ['输出', '思考输出']:
                if output_price is None:
                    output_price = price_value

        # Pick the best input price: prefer 非缓存输入, then 输入, then others
        input_price = (
            input_prices.get('非缓存输入')
            or input_prices.get('输入')
            or input_prices.get('批量输入')
            or input_prices.get('思考输入')
            or input_prices.get('缓存输入')
        )

        if input_price is not None or output_price is not None:
            normalized_name = normalize_model_name(model_name)
            prices[normalized_name] = {
                'input': input_price or 0.0,
                'output': output_price or 0.0
            }

    return prices


# ── Modelink 定价 API（权威来源） ─────────────────────────────────────────────


# 输入价优先级：非缓存输入 > 普通输入 > 批量/思考输入 > 缓存输入
# 闲时价为默认展示价（"input"/"output"），高峰价另存为 "input_peak"/"output_peak"
_TOKEN_INPUT_KEYS = [
    "ncache_offpeak", "ncache", "input", "bi_input", "th_input",
    "cache_offpeak", "cache", "ncache_peak", "cache_peak",
]
_TOKEN_OUTPUT_KEYS = [
    "output_offpeak", "output", "th_output", "bi_output", "output_peak",
]
# 仅在存在分时段（高峰/空闲）定价时才会命中的高峰键
_TOKEN_INPUT_PEAK_KEYS = ["ncache_peak"]
_TOKEN_OUTPUT_PEAK_KEYS = ["output_peak"]


def _pick_token_price(rule: dict, keys: list) -> Optional[float]:
    """Pick the USD-per-million price for the first matching token billing key."""
    items = rule.get("items") or []
    for key in keys:
        for it in items:
            if it.get("key") != key:
                continue
            unit_name = it.get("unitName") or it.get("pricing_name")
            if unit_name != "token":
                continue
            usd = it.get("usdPerMillion")
            if usd is None:
                unit_price = it.get("unit_price_usd")
                unit_size = it.get("unit_size") or 1000
                if unit_price is not None:
                    usd = unit_price * (1_000_000 / unit_size)
            if usd is not None:
                return usd
    return None


def _extract_price_from_rules(rules: list) -> Optional[dict]:
    """Extract USD-per-million prices from a pricingRules array.

    Returns {"input", "output"} (off-peak / standard). Models with time-of-day
    pricing (DeepSeek 高峰/空闲) also carry "input_peak"/"output_peak".
    """
    for rule in rules or []:
        inp = _pick_token_price(rule, _TOKEN_INPUT_KEYS)
        out = _pick_token_price(rule, _TOKEN_OUTPUT_KEYS)
        peak_in = _pick_token_price(rule, _TOKEN_INPUT_PEAK_KEYS)
        peak_out = _pick_token_price(rule, _TOKEN_OUTPUT_PEAK_KEYS)
        if inp is None and out is None and peak_in is None and peak_out is None:
            continue
        pricing = {"input": inp or 0.0, "output": out or 0.0}
        if peak_in is not None:
            pricing["input_peak"] = peak_in
        if peak_out is not None:
            pricing["output_peak"] = peak_out
        return pricing
    return None


def parse_modelink_models(html: str) -> dict:
    """Parse all model prices from the modelink.ai model-square page.

    The Next.js page embeds each model object (id, aliases, pricingRules) as
    JSON-escaped flight data.
    """
    prices = {}
    s = html.replace('\\"', '"').replace('\\\\', '\\')

    id_pos = [m.start() for m in re.finditer(r'"id":"', s)]
    id_pos.append(len(s))
    for k in range(len(id_pos) - 1):
        seg = s[id_pos[k]:id_pos[k + 1]]
        mi = re.match(r'"id":"([^"]+)"', seg)
        if not mi:
            continue
        model_id = mi.group(1)

        alias_match = re.search(r'"aliases":\[([^\]]*)\]', seg)
        aliases = re.findall(r'"([^"]+)"', alias_match.group(1)) if alias_match else []

        pr = seg.find('"pricingRules":[')
        if pr < 0:
            continue
        j = seg.index('[', pr)
        depth = 0
        end = None
        for e in range(j, len(seg)):
            if seg[e] == '[':
                depth += 1
            elif seg[e] == ']':
                depth -= 1
                if depth == 0:
                    end = e
                    break
        if end is None:
            continue
        try:
            rules = json.loads(seg[j:end + 1])
        except json.JSONDecodeError:
            continue

        pricing = _extract_price_from_rules(rules)
        if pricing:
            for name in [model_id] + aliases:
                prices[name] = pricing
    return prices


def parse_historical_pricing(data: dict) -> dict:
    """Parse prices from modelink.ai/historical-pricing.json."""
    prices = {}
    for model_id, entry in (data.get("models") or {}).items():
        pricing = _extract_price_from_rules(entry.get("rules") or [])
        if pricing:
            prices[model_id] = pricing
    return prices


def _http_get(url: str, timeout: int = 60) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json,text/html,*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "ignore")


def fetch_prices_from_api() -> tuple[dict, float]:
    """Fetch model prices directly from the modelink.ai pricing APIs.

    Source 1: the model-square page (live, includes brand-new models).
    Source 2: historical-pricing.json (single request, fills in older models).
    """
    print("Fetching prices from modelink.ai API...", file=sys.stderr)
    prices: dict = {}

    try:
        html = _http_get(MODELINK_MODELS_URL)
        live = parse_modelink_models(html)
        prices.update(live)
        print(f"  live model-square: {len(live)} models", file=sys.stderr)
    except Exception as e:
        print(f"  live model-square failed: {e}", file=sys.stderr)

    try:
        hist_data = json.loads(_http_get(MODELINK_HISTORICAL_URL))
        hist = parse_historical_pricing(hist_data)
        added = 0
        for name, pricing in hist.items():
            if name not in prices:
                prices[name] = pricing
                added += 1
        print(f"  historical-pricing.json: {len(hist)} models ({added} new)", file=sys.stderr)
    except Exception as e:
        print(f"  historical-pricing.json failed: {e}", file=sys.stderr)

    if not prices:
        print("API pricing unavailable; falling back to sufy.com scrape", file=sys.stderr)
        return fetch_prices_from_web()

    exchange_rate = get_exchange_rate()
    save_prices(prices, exchange_rate)
    return prices, exchange_rate


def fetch_prices_from_web() -> tuple[dict, float]:
    """Fetch latest prices from sufy.com website."""
    print("Fetching prices from sufy.com...", file=sys.stderr)

    # Fetch exchange rate first
    exchange_rate = get_exchange_rate()

    try:
        req = urllib.request.Request(
            PRICING_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8")
    except Exception as e:
        print(f"Failed to fetch prices: {e}", file=sys.stderr)
        print("Using default pricing.", file=sys.stderr)
        return DEFAULT_PRICING, exchange_rate

    # Parse prices from HTML
    prices = parse_html_prices(html)

    if prices:
        print(f"Successfully fetched prices for {len(prices)} models", file=sys.stderr)
        # Apply overrides for models where sufy.com only exposes cached-input price via static HTML
        prices.update(PRICE_OVERRIDES)
        save_prices(prices, exchange_rate, source=PRICING_URL)
        return prices, exchange_rate
    else:
        print("Could not parse prices from web page.", file=sys.stderr)
        print("Using default pricing.", file=sys.stderr)
        save_prices(DEFAULT_PRICING, exchange_rate, source=PRICING_URL)
        return DEFAULT_PRICING, exchange_rate


# ── Helpers ───────────────────────────────────────────────────────────────────


def get_api_key(override: str | None) -> str:
    """Resolve API key: CLI arg > env var."""
    if override:
        return override
    key = os.environ.get("QINIU_AI_API_KEY") or os.environ.get("QINIU_API_KEY")
    if not key:
        print("Error: No API key found. Set QINIU_AI_API_KEY env var or use --api-key", file=sys.stderr)
        sys.exit(1)
    return key


def to_rfc3339(dt: datetime) -> str:
    """Convert datetime to RFC3339 format with +08:00 timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CST)
    return dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")


def parse_date_arg(s: str) -> datetime:
    """Parse date string in YYYY-MM-DD or RFC3339 format."""
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s[:19], fmt[: len(s[:19])])
            return dt.replace(tzinfo=CST)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {s!r}. Use YYYY-MM-DD or RFC3339.")


def build_url(granularity: str, start: datetime, end: datetime) -> str:
    params = urllib.parse.urlencode(
        {
            "granularity": granularity,
            "start": to_rfc3339(start),
            "end": to_rfc3339(end),
        }
    )
    return f"{BASE_URL}{USAGE_PATH}?{params}"


def fetch_usage(api_key: str, granularity: str, start: datetime, end: datetime) -> dict:
    url = build_url(granularity, start, end)
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode()
            return json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"Usage HTTP {e.code}: {body}", file=sys.stderr)
        return {"status": False, "error": f"HTTP {e.code}"}
    except Exception as e:
        print(f"Usage request failed: {e}", file=sys.stderr)
        return {"status": False, "error": str(e)}


# ── V3 Official Billing API (真实账单，费用以人民币计) ────────────────────────


V3_COST_DETAIL_PATH = "/v3/stat/usage/apikey/cost-detail"


def fetch_v3_cost_detail(api_key: str, start: datetime, end: datetime, grain: str = "day") -> dict:
    """Query official billing detail via /v3/stat/usage/apikey/cost-detail.

    Returns fee in CNY directly — no local price table or exchange rate needed.
    """
    params = urllib.parse.urlencode(
        {
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
            "grain": grain,
        }
    )
    url = f"{BASE_URL}{V3_COST_DETAIL_PATH}?{params}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"V3 billing HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
        return {"status": False, "error": f"HTTP {e.code}"}
    except Exception as e:
        print(f"V3 billing request failed: {e}", file=sys.stderr)
        return {"status": False, "error": str(e)}


def _is_token_unit(unit: str) -> bool:
    return "token" in (unit or "").lower()


def aggregate_v3_bills(data: dict) -> tuple[dict, list]:
    """Aggregate v3 cost-detail bills into per-model summary + per-date breakdown.

    Returns (models_summary, daily). Costs are in CNY (人民币).
    """
    models: dict[str, dict] = {}
    daily: dict[str, dict] = {}

    bills = data.get("data", {}).get("bills", [])
    for bill in bills:
        date = bill.get("date")
        for model in bill.get("models", []):
            mid = model.get("model_id", "unknown")
            m = models.setdefault(
                mid, {"model": mid, "tokens": 0.0, "fee": 0.0, "peak": 0.0, "offpeak": 0.0}
            )
            m["fee"] += model.get("total_fee", 0.0) or 0.0
            for item in model.get("items") or []:
                usage = item.get("usage", {})
                if _is_token_unit(usage.get("unit")):
                    count = usage.get("count", 0.0) or 0.0
                    m["tokens"] += count
                    item_key = item.get("key") or ""
                    if item_key.endswith("_peak"):
                        m["peak"] += count
                    elif item_key.endswith("_offpeak"):
                        m["offpeak"] += count
            if date:
                d = daily.setdefault(date, {"tokens": 0.0, "fee": 0.0})
                d["fee"] += model.get("total_fee", 0.0) or 0.0
                for item in model.get("items") or []:
                    usage = item.get("usage", {})
                    if _is_token_unit(usage.get("unit")):
                        d["tokens"] += usage.get("count", 0.0) or 0.0

    models_summary = sorted(models.values(), key=lambda x: x["fee"], reverse=True)
    return models_summary, daily


def print_v3_report(models_summary: list, daily: dict, start: datetime, end: datetime, grain: str) -> None:
    """Print cost report from official v3 billing API (CNY)."""
    print()
    print(f"  ═══════════════════════════════════════════════════════════════")
    print(f"  Qiniu AI Billing Report (官方账单)")
    print(f"  ═══════════════════════════════════════════════════════════════")
    print(f"  Period      : {start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')}")
    print(f"  Granularity : {grain}")
    print(f"  Currency    : CNY (人民币, 官方原价)")
    print()

    if not models_summary:
        print("  No billing data found.")
        return

    col_model = max(18, max(len(m["model"]) for m in models_summary))
    col_tokens = 16
    col_cost = 18

    print(f"  {'Model':<{col_model}} │ {'Tokens':>{col_tokens}} │ {'Cost (CNY)':>{col_cost}}")
    print(f"  {'─' * col_model}─┼─{'─' * col_tokens}─┼─{'─' * col_cost}")

    grand_tokens = 0.0
    grand_fee = 0.0
    for m in models_summary:
        total_tokens = m["tokens"]
        fee = m["fee"]
        print(
            f"  {m['model']:<{col_model}} │ {format_value(total_tokens):>{col_tokens}} │ {fee:>{col_cost}.2f}"
        )
        grand_tokens += total_tokens
        grand_fee += fee

    print(f"  {'─' * col_model}─┼─{'─' * col_tokens}─┼─{'─' * col_cost}")
    print(
        f"  {'TOTAL':<{col_model}} │ {format_value(grand_tokens):>{col_tokens}} │ ¥{grand_fee:>{col_cost-1}.2f}"
    )
    print()

    # 高峰/空闲时段明细（DeepSeek 等分时段计价模型）
    peak_models = [
        m for m in models_summary if m.get("peak", 0.0) > 0 or m.get("offpeak", 0.0) > 0
    ]
    if peak_models:
        pc = max(18, max(len(m["model"]) for m in peak_models))
        print(f"  ─── 高峰 / 空闲时段明细 (Mon–Fri 09–12 & 14–18 = 高峰) ───")
        print(f"  {'Model':<{pc}} │ {'高峰 Tokens':>{col_tokens}} │ {'空闲 Tokens':>{col_tokens}}")
        print(f"  {'─' * pc}─┼─{'─' * col_tokens}─┼─{'─' * col_tokens}")
        for m in peak_models:
            print(
                f"  {m['model']:<{pc}} │ {format_value(m['peak']):>{col_tokens}} │ {format_value(m['offpeak']):>{col_tokens}}"
            )
        print()

    if daily:
        active_dates = sorted(daily.keys())
        print(f"  ─── Daily Breakdown ({len(active_dates)} active days) ───")
        col_date = 12
        col_tokens = 16
        col_cost = 18
        print(f"  {'Date':<{col_date}} │ {'Tokens':>{col_tokens}} │ {'Cost (CNY)':>{col_cost}}")
        print(f"  {'─' * col_date}─┼─{'─' * col_tokens}─┼─{'─' * col_cost}")
        for date in active_dates:
            d = daily[date]
            print(
                f"  {date:<{col_date}} │ {format_value(d['tokens']):>{col_tokens}} │ ¥{d['fee']:>{col_cost-1}.2f}"
            )
        print()


def render_v3_markdown(
    models_summary: list,
    daily: dict,
    start: datetime,
    end: datetime,
    grain: str,
) -> str:
    """Render official v3 billing data as Markdown tables."""
    esc = lambda s: str(s).replace("|", "\\|").replace("\n", " ")

    lines = []
    lines.append("### Qiniu AI Billing Report (官方账单)")
    lines.append("")
    lines.append(f"- **Period**: {start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')}")
    lines.append(f"- **Granularity**: {grain}")
    lines.append(f"- **Currency**: CNY (人民币, 官方原价)")
    lines.append("")

    if not models_summary:
        lines.append("No billing data found.")
        return "\n".join(lines)

    lines.append("| Model | Tokens | Cost (CNY) |")
    lines.append("|---|---:|---:|")
    grand_tokens = 0.0
    grand_fee = 0.0
    for m in sorted(models_summary, key=lambda x: x["fee"], reverse=True):
        lines.append(f"| {esc(m['model'])} | {format_value(m['tokens'])} | {m['fee']:.2f} |")
        grand_tokens += m["tokens"]
        grand_fee += m["fee"]
    lines.append(f"| **TOTAL** | **{format_value(grand_tokens)}** | **¥{grand_fee:.2f}** |")
    lines.append("")

    if daily:
        active_dates = sorted(daily.keys())
        lines.append(f"### Daily Breakdown ({len(active_dates)} active days)")
        lines.append("")
        lines.append("| Date | Tokens | Cost (CNY) |")
        lines.append("|---|---:|---:|")
        for date in active_dates:
            d = daily[date]
            lines.append(f"| {esc(date)} | {format_value(d['tokens'])} | ¥{d['fee']:.2f} |")
        lines.append("")

    return "\n".join(lines)


# ── Cost Calculation ────────────────────────────────────────────────────────


def find_pricing(model_id: str, prices: dict) -> Optional[dict]:
    """Find pricing for a model, trying various matching strategies."""
    model_lower = normalize_model_name(model_id)

    # Build normalized key index for exact matching
    normalized = {normalize_model_name(k): k for k in prices}
    if model_lower in normalized:
        return prices[normalized[model_lower]]

    # Try partial matching — prefer most specific (longest key) match
    candidates = []
    for key in prices:
        key_lower = normalize_model_name(key)
        if key_lower in model_lower or model_lower in key_lower:
            candidates.append(key)
            continue
        key_parts = set(key_lower.split("-"))
        model_parts = set(model_lower.split("-"))
        if key_parts and key_parts.issubset(model_parts):
            candidates.append(key)

    if not candidates:
        return None
    # Return the most specific (longest key) match
    candidates.sort(key=len, reverse=True)
    return prices[candidates[0]]


def calculate_cost(
    model_id: str, input_ktokens: float, output_ktokens: float, prices: dict
) -> tuple:
    """
    Calculate cost based on model pricing.
    Returns: (input_cost_usd, output_cost_usd, pricing_found)
    """
    pricing = find_pricing(model_id, prices)

    if not pricing:
        return 0.0, 0.0, False

    # kToken / 1000 = MToken, then * price = USD
    input_cost_usd = (input_ktokens / 1000.0) * pricing["input"]
    output_cost_usd = (output_ktokens / 1000.0) * pricing["output"]

    return input_cost_usd, output_cost_usd, True


# ── 分时段（高峰 / 空闲）计价 ─────────────────────────────────────────────────
# DeepSeek 官方规则（见 modelink 模型页公告）：
#   高峰时段 = 每周一到周五 09:00–12:00 与 14:00–18:00（北京时间 UTC+8）；
#   其余时段（含周末、夜间）按闲时价格计费。
DEEPSEEK_PEAK_WEEKDAYS = {0, 1, 2, 3, 4}  # Monday=0 ... Friday=4
DEEPSEEK_PEAK_HOUR_RANGES = [(9, 12), (14, 18)]


def is_peak_time(dt: datetime) -> bool:
    """Return True if `dt` falls in DeepSeek's peak window (Beijing time)."""
    local = dt.astimezone(CST)
    if local.weekday() not in DEEPSEEK_PEAK_WEEKDAYS:
        return False
    return any(start <= local.hour < end for start, end in DEEPSEEK_PEAK_HOUR_RANGES)


def peak_hour_fraction(start: datetime, end: datetime) -> float:
    """Fraction of hours in [start, end] that fall in DeepSeek's peak window."""
    end_local = end.astimezone(CST)
    if end_local <= start.astimezone(CST):
        # Single-date request (start == end at 00:00) → treat as one full day
        end_local = start.astimezone(CST) + timedelta(days=1)
    total_seconds = (end_local - start.astimezone(CST)).total_seconds()
    if total_seconds <= 0:
        return 0.0
    peak = 0
    cur = start.astimezone(CST).replace(minute=0, second=0, microsecond=0)
    while cur < end_local:
        if is_peak_time(cur):
            peak += 1
        cur += timedelta(hours=1)
    return peak / (total_seconds / 3600.0)


def estimate_cost_blended(
    model_id: str,
    input_ktokens: float,
    output_ktokens: float,
    prices: dict,
    peak_fraction: float,
) -> tuple:
    """Estimate USD cost from period totals, blending peak/off-peak prices.

    `peak_fraction` is the fraction of the period that is peak time; models
    without time-of-day pricing ignore it. Returns (cost_usd, pricing_found).
    """
    pricing = find_pricing(model_id, prices)
    if not pricing:
        return None, False

    f = peak_fraction if ("input_peak" in pricing or "output_peak" in pricing) else 0.0
    in_price = pricing["input"] * (1 - f) + pricing.get("input_peak", pricing["input"]) * f
    out_price = pricing["output"] * (1 - f) + pricing.get("output_peak", pricing["output"]) * f

    cost = (input_ktokens / 1000.0) * in_price + (output_ktokens / 1000.0) * out_price
    return cost, True


def extract_model_totals(usage_data: list) -> dict:
    """Extract per-model (input_k, output_k) token totals from v2 usage data.

    Prefers the item-level `total`; falls back to summing category values.
    """
    result = {}
    for model in usage_data:
        name = model.get("name", "unknown")
        k_in = 0.0
        k_out = 0.0
        for item in model.get("items") or []:
            item_name = item.get("name", "")
            if "输入" in item_name or "input" in item_name.lower():
                idx = 0
            elif "输出" in item_name or "output" in item_name.lower():
                idx = 1
            else:
                continue
            total = item.get("total")
            if total is None:
                total = 0.0
                for cat in item.get("categories") or []:
                    for entry in cat.get("values") or []:
                        total += entry.get("value", 0.0) or 0.0
            if idx == 0:
                k_in += total or 0.0
            else:
                k_out += total or 0.0
        result[name] = (k_in, k_out)
    return result


def print_estimated_report(
    usage_data: list,
    prices: dict,
    exchange_rate: float,
    start: datetime,
    end: datetime,
    granularity: str,
    note: str = "Estimated (上限估算：输入按非缓存单价，可能偏高)",
) -> None:
    """Print a fallback cost report estimated from token usage + price table."""
    totals = extract_model_totals(usage_data)
    peak_fraction = peak_hour_fraction(start, end)

    print()
    print(f"  ═══════════════════════════════════════════════════════════════")
    print(f"  Qiniu AI Cost Report — {note}")
    print(f"  ═══════════════════════════════════════════════════════════════")
    print(f"  Period      : {start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')}")
    print(f"  Granularity : {granularity}")
    print(f"  Exchange    : 1 USD = ¥{exchange_rate:.2f} CNY")
    print(f"  Peak mix    : {peak_fraction * 100:.1f}% peak (Mon–Fri 09–12 & 14–18 Beijing)")
    print()

    if not totals:
        print("  No usage data found.")
        return

    rows = []
    for model_name, (k_in, k_out) in totals.items():
        cost_usd, found = estimate_cost_blended(model_name, k_in, k_out, prices, peak_fraction)
        rows.append(
            {
                "model": model_name,
                "tokens": k_in + k_out,
                "cost_usd": cost_usd if found else 0.0,
                "found": found,
            }
        )

    rows.sort(key=lambda r: r["tokens"], reverse=True)
    col_model = max(18, max(len(r["model"]) for r in rows))
    col_tokens = 18
    col_cost = 22

    print(f"  {'Model':<{col_model}} │ {'Tokens':>{col_tokens}} │ {'Cost (USD/CNY)':>{col_cost}}")
    print(f"  {'─' * col_model}─┼─{'─' * col_tokens}─┼─{'─' * col_cost}")

    grand_tokens = 0.0
    grand_cost = 0.0
    for r in rows:
        cost_str = format_cost(r["cost_usd"], exchange_rate) if r["found"] else "N/A"
        print(
            f"  {r['model']:<{col_model}} │ {format_value(r['tokens']):>{col_tokens}} │ {cost_str:>{col_cost}}"
        )
        grand_tokens += r["tokens"]
        grand_cost += r["cost_usd"]

    print(f"  {'─' * col_model}─┼─{'─' * col_tokens}─┼─{'─' * col_cost}")
    print(
        f"  {'TOTAL':<{col_model}} │ {format_value(grand_tokens):>{col_tokens}} │ {format_cost(grand_cost, exchange_rate):>{col_cost}}"
    )
    print()


# ── Formatting ────────────────────────────────────────────────────────────────


def format_value(v: float) -> str:
    """Format kToken value with appropriate precision."""
    if v >= 1000:
        return f"{v / 1000:.2f} MToken"
    elif v >= 1:
        return f"{v:.3f} kToken"
    else:
        return f"{v * 1000:.0f} Token"


def format_cost(usd: float, exchange_rate: float) -> str:
    """Format cost in USD and CNY."""
    cny = usd * exchange_rate
    if usd >= 1:
        return f"${usd:.2f} (¥{cny:.1f})"
    elif usd >= 0.01:
        return f"${usd:.3f} (¥{cny:.2f})"
    else:
        return f"${usd:.4f} (¥{cny:.3f})"


def print_table(
    data: list,
    granularity: str,
    start: datetime,
    end: datetime,
    show_cost: bool = False,
    prices: dict = None,
    exchange_rate: float = DEFAULT_USD_TO_CNY,
) -> None:
    """Print a human-readable summary table."""
    print()
    print(f"  ═══════════════════════════════════════════════════════════════")
    print(f"  Qiniu AI Token Usage Report")
    print(f"  ═══════════════════════════════════════════════════════════════")
    print(f"  Period      : {start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')}")
    print(f"  Granularity : {granularity}")
    if show_cost:
        print(f"  Exchange    : 1 USD = ¥{exchange_rate:.2f} CNY")
    print()

    if not data:
        print("  No usage data found.")
        return

    if prices is None:
        prices = DEFAULT_PRICING

    # Aggregate totals per model
    models_summary = []
    for model in data:
        model_id = model.get("name", model.get("id", "unknown"))
        input_total = 0.0
        output_total = 0.0

        for item in model.get("items", []):
            name = item.get("name", "")
            total = 0.0
            for cat in item.get("categories", []):
                for entry in cat.get("values", []):
                    total += entry.get("value", 0.0)
            if "输入" in name or "input" in name.lower():
                input_total += total
            elif "输出" in name or "output" in name.lower():
                output_total += total

        input_cost_usd, output_cost_usd, pricing_found = calculate_cost(
            model_id, input_total, output_total, prices
        )
        pricing = find_pricing(model_id, prices) if pricing_found else None

        models_summary.append(
            {
                "model": model_id,
                "input": input_total,
                "output": output_total,
                "total": input_total + output_total,
                "input_cost_usd": input_cost_usd,
                "output_cost_usd": output_cost_usd,
                "cost_usd": input_cost_usd + output_cost_usd,
                "pricing_found": pricing_found,
                "input_price": pricing["input"] if pricing else None,
                "output_price": pricing["output"] if pricing else None,
            }
        )

    # Sort by total usage descending
    models_summary.sort(key=lambda x: x["total"], reverse=True)

    # Column widths
    col_model = max(18, max(len(m["model"]) for m in models_summary))
    col_tokens = 16
    col_price = 22   # "$3.00in/$15.00out"
    col_cost = 20

    if show_cost:
        print(
            f"  {'Model':<{col_model}} │ {'Tokens':>{col_tokens}} │ {'Price(in/out $/M)':>{col_price}} │ {'Cost (USD/CNY)':>{col_cost}}"
        )
        print(f"  {'─' * col_model}─┼─{'─' * col_tokens}─┼─{'─' * col_price}─┼─{'─' * col_cost}")
    else:
        print(
            f"  {'Model':<{col_model}} │ {'Input':>{col_tokens}} │ {'Output':>{col_tokens}} │ {'Total':>{col_tokens}}"
        )
        print(
            f"  {'─' * col_model}─┼─{'─' * col_tokens}─┼─{'─' * col_tokens}─┼─{'─' * col_tokens}"
        )

    grand_input = 0.0
    grand_output = 0.0
    grand_cost_usd = 0.0

    for m in models_summary:
        if show_cost:
            cost_str = (
                format_cost(m["cost_usd"], exchange_rate)
                if m["pricing_found"]
                else "N/A"
            )
            if m["input_price"] is not None:
                price_str = f"${m['input_price']:.2f} / ${m['output_price']:.2f}"
            else:
                price_str = "N/A"
            total_str = format_value(m["total"])
            print(
                f"  {m['model']:<{col_model}} │ {total_str:>{col_tokens}} │ {price_str:>{col_price}} │ {cost_str:>{col_cost}}"
            )
        else:
            print(
                f"  {m['model']:<{col_model}} │ {format_value(m['input']):>{col_tokens}} │ "
                f"{format_value(m['output']):>{col_tokens}} │ {format_value(m['total']):>{col_tokens}}"
            )
        grand_input += m["input"]
        grand_output += m["output"]
        grand_cost_usd += m["cost_usd"]

    grand_total = grand_input + grand_output

    if show_cost:
        print(f"  {'─' * col_model}─┼─{'─' * col_tokens}─┼─{'─' * col_price}─┼─{'─' * col_cost}")
        cost_str = format_cost(grand_cost_usd, exchange_rate)
        print(
            f"  {'TOTAL':<{col_model}} │ {format_value(grand_total):>{col_tokens}} │ {'':>{col_price}} │ {cost_str:>{col_cost}}"
        )
    else:
        print(
            f"  {'─' * col_model}─┼─{'─' * col_tokens}─┼─{'─' * col_tokens}─┼─{'─' * col_tokens}"
        )
        print(
            f"  {'TOTAL':<{col_model}} │ {format_value(grand_input):>{col_tokens}} │ "
            f"{format_value(grand_output):>{col_tokens}} │ {format_value(grand_total):>{col_tokens}}"
        )
    print()

    # Daily breakdown (only for day granularity, if multiple days)
    if granularity == "day":
        print_daily_breakdown(data, show_cost, prices, exchange_rate)


def print_daily_breakdown(
    data: list,
    show_cost: bool = False,
    prices: dict = None,
    exchange_rate: float = DEFAULT_USD_TO_CNY,
) -> None:
    """Print day-by-day breakdown for all models combined."""
    # Collect all dates
    date_totals: dict[str, dict] = {}

    for model in data:
        for item in model.get("items", []):
            name = item.get("name", "")
            is_input = "输入" in name or "input" in name.lower()

            for cat in item.get("categories", []):
                for entry in cat.get("values", []):
                    date = entry["time"]
                    val = entry.get("value", 0.0)
                    if val == 0:
                        continue
                    if date not in date_totals:
                        date_totals[date] = {"input": 0.0, "output": 0.0}
                    if is_input:
                        date_totals[date]["input"] += val
                    else:
                        date_totals[date]["output"] += val

    if not date_totals:
        return

    active_dates = sorted(date_totals.keys())
    print(f"  ─── Daily Breakdown ({len(active_dates)} active days) ───")

    if show_cost and prices:
        # Calculate average pricing for estimation
        avg_input_price = (
            sum(p["input"] for p in prices.values()) / len(prices) if prices else 3.0
        )
        avg_output_price = (
            sum(p["output"] for p in prices.values()) / len(prices) if prices else 15.0
        )

        col_date = 12
        col_tokens = 16
        col_cost = 20

        print(
            f"  {'Date':<{col_date}} │ {'Tokens':>{col_tokens}} │ {'Est. Cost':>{col_cost}}"
        )
        print(f"  {'─' * col_date}─┼─{'─' * col_tokens}─┼─{'─' * col_cost}")

        for date in active_dates:
            d = date_totals[date]
            total = d["input"] + d["output"]
            # Estimate cost using average pricing
            cost_usd = (d["input"] / 1000 * avg_input_price) + (
                d["output"] / 1000 * avg_output_price
            )
            cost_str = format_cost(cost_usd, exchange_rate)

            print(
                f"  {date:<{col_date}} │ {format_value(total):>{col_tokens}} │ {cost_str:>{col_cost}}"
            )
    else:
        col_date = 12
        col_tokens = 16

        print(
            f"  {'Date':<{col_date}} │ {'Input':>{col_tokens}} │ {'Output':>{col_tokens}} │ {'Total':>{col_tokens}}"
        )
        print(
            f"  {'─' * col_date}─┼─{'─' * col_tokens}─┼─{'─' * col_tokens}─┼─{'─' * col_tokens}"
        )

        for date in active_dates:
            d = date_totals[date]
            total = d["input"] + d["output"]
            print(
                f"  {date:<{col_date}} │ {format_value(d['input']):>{col_tokens}} │ "
                f"{format_value(d['output']):>{col_tokens}} │ {format_value(total):>{col_tokens}}"
            )
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────


def parse_args():
    parser = argparse.ArgumentParser(
        description="Query Qiniu AI API token usage with cost calculation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--granularity",
        choices=["day", "hour"],
        default="day",
        help="Time granularity (default: day)",
    )
    parser.add_argument("--start", help="Start datetime (YYYY-MM-DD or RFC3339)")
    parser.add_argument("--end", help="End datetime (YYYY-MM-DD or RFC3339)")
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Query last N days (default mode if no other shortcut given)",
    )
    parser.add_argument("--today", action="store_true", help="Query today only")
    parser.add_argument("--month", action="store_true", help="Query current month")
    parser.add_argument(
        "--json", action="store_true", dest="output_json", help="Output raw JSON"
    )
    parser.add_argument(
        "--md",
        action="store_true",
        dest="output_markdown",
        help="Output official billing as Markdown tables (uses v3 cost API)",
    )
    parser.add_argument(
        "--cost",
        "--price",
        action="store_true",
        dest="show_cost",
        help="Show cost in USD and CNY",
    )
    parser.add_argument(
        "--update-prices",
        action="store_true",
        dest="update_prices",
        help="Fetch latest prices from sufy.com",
    )
    parser.add_argument(
        "--update-rate",
        action="store_true",
        dest="update_rate",
        help="Fetch latest USD/CNY exchange rate",
    )
    parser.add_argument(
        "--list-prices",
        action="store_true",
        dest="list_prices",
        help="List all cached model prices",
    )
    parser.add_argument("--api-key", dest="api_key", help="Override API key")
    return parser.parse_args()


def resolve_time_range(args) -> tuple[datetime, datetime]:
    now = datetime.now(CST)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if args.today:
        return today_start, now

    if args.month:
        month_start = today_start.replace(day=1)
        return month_start, now

    if args.start and args.end:
        return parse_date_arg(args.start), parse_date_arg(args.end)

    if args.start:
        start = parse_date_arg(args.start)
        return start, now

    # Default: last N days (default 7)
    days = args.days if args.days is not None else 7
    start = today_start - timedelta(days=days - 1)
    return start, now


def main():
    args = parse_args()

    # Handle price listing
    if args.list_prices:
        prices, exchange_rate = load_prices()
        print(f"\nCached Model Prices (Exchange Rate: 1 USD = ¥{exchange_rate:.2f})")
        print("=" * 70)
        for name, pricing in sorted(prices.items()):
            input_cny = pricing["input"] * exchange_rate
            output_cny = pricing["output"] * exchange_rate
            line = (
                f"  {name:<30} Input: ${pricing['input']:.3f} (¥{input_cny:.2f})  Output: ${pricing['output']:.3f} (¥{output_cny:.2f})"
            )
            if "input_peak" in pricing or "output_peak" in pricing:
                pin = pricing.get("input_peak", pricing["input"])
                pout = pricing.get("output_peak", pricing["output"])
                line += f"  | 高峰 In: ${pin:.3f}  Out: ${pout:.3f}"
            print(line)
        print(f"\nTotal: {len(prices)} models")
        print(f"Cache file: {PRICES_CACHE_FILE}")
        return

    # Handle price update
    if args.update_prices:
        prices, exchange_rate = fetch_prices_from_api()
        print(f"\n✓ Prices updated and cached to: {PRICES_CACHE_FILE}")
        print(f"✓ Total models: {len(prices)}")
        print(f"✓ Exchange rate: 1 USD = ¥{exchange_rate:.4f} CNY")
        return

    # Handle exchange rate update only
    if args.update_rate:
        exchange_rate = get_exchange_rate()
        prices, _ = load_prices()
        save_prices(prices, exchange_rate)
        print(f"\n✓ Exchange rate updated: 1 USD = ¥{exchange_rate:.4f} CNY")
        print(f"✓ Cached to: {PRICES_CACHE_FILE}")
        return

    # Load prices
    prices, exchange_rate = load_prices()

    api_key = get_api_key(args.api_key)
    start, end = resolve_time_range(args)

    # Validate time range limits
    delta = end - start
    if args.granularity == "day" and delta.days > 31:
        print("Error: day granularity supports max 31 days range.", file=sys.stderr)
        sys.exit(1)
    if args.granularity == "hour" and delta.days > 7:
        print("Error: hour granularity supports max 7 days range.", file=sys.stderr)
        sys.exit(1)

    result = fetch_usage(api_key, args.granularity, start, end)

    if not result.get("status"):
        print(f"API error: {result}", file=sys.stderr)
        sys.exit(1)

    if args.output_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.output_markdown:
        # Markdown 表格：走官方 v3 账单接口
        grain = "day" if args.granularity == "day" else "month"
        v3 = fetch_v3_cost_detail(api_key, start, end, grain)
        if not v3.get("status"):
            print(f"V3 billing API error: {v3}", file=sys.stderr)
            sys.exit(1)
        models_summary, daily = aggregate_v3_bills(v3)
        print(render_v3_markdown(models_summary, daily, start, end, grain))
    elif args.show_cost:
        # 优先：官方 v3 账单接口（真实人民币费用，含高峰/空闲明细，无需价格表）
        grain = "day" if args.granularity == "day" else "month"
        v3 = fetch_v3_cost_detail(api_key, start, end, grain)
        if v3.get("status") and v3.get("data", {}).get("bills"):
            models_summary, daily = aggregate_v3_bills(v3)
            print_v3_report(models_summary, daily, start, end, grain)
        else:
            # 兜底：官方账单不可用 → 用价格表估算（分时段模型按高峰占比折算）
            print("Official billing unavailable; estimating from price table.", file=sys.stderr)
            est_result = result
            if args.granularity != "day":
                day_result = fetch_usage(api_key, "day", start, end)
                if day_result.get("status"):
                    est_result = day_result
            print_estimated_report(
                est_result.get("data", []),
                prices,
                exchange_rate,
                start,
                end,
                "day",
                "Estimated (官方账单不可用；上限估算，输入按非缓存单价，可能偏高)",
            )
    else:
        print_table(
            result.get("data", []),
            args.granularity,
            start,
            end,
            args.show_cost,
            prices,
            exchange_rate,
        )


if __name__ == "__main__":
    main()

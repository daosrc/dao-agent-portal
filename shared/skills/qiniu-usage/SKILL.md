---
name: qiniu-usage
description: Query Qiniu AI API (api.qnaigc.com) token usage and calculate costs in USD/CNY. Use when the user asks about API consumption (用量), token stats, how much they've used, costs (费用), or billing data for Qiniu AI models.
---

# Qiniu AI Usage Manager

This skill queries Qiniu AI consumption via two paths:
- **Token usage** (no cost): `/v2/stat/usage` — token counts per model without cost.
- **Cost (费用)**: `/v3/stat/usage/apikey/cost-detail` — **官方真实账单**，直接返回人民币（CNY）费用，无需本地价格表或汇率换算。`--cost` 时自动走此接口。

## Features

- **Token Usage Query**: Query usage by model, day, or time range
- **Cost Calculation**: 官方账单，费用以人民币（CNY）计
- **Live Exchange Rate**: Fetch real-time USD/CNY rate from API（仅用于价格表换算）
- **Price Management**: Update prices from sufy.com（仅 `--list-prices` / `--update-prices` 使用）
- **Price Listing**: View all cached model prices with CNY conversion
- **Daily Breakdown**: Day-by-day usage detail when querying multiple days

## Prerequisites

- **API Key**: Set `QINIU_AI_API_KEY` environment variable or use `--api-key` flag
- **Python 3**: Script uses only stdlib — no pip install needed

## Script Location

```
scripts/qiniu_usage.py
```

## Usage

### General Syntax

```bash
python3 scripts/qiniu_usage.py [OPTIONS]
```

### Common Commands

#### Query today's usage with cost
```bash
python3 scripts/qiniu_usage.py --today --cost
```

#### Query last 7 days (default)
```bash
python3 scripts/qiniu_usage.py
```

#### Query current month with cost
```bash
python3 scripts/qiniu_usage.py --month --cost
```

#### Query specific date range
```bash
python3 scripts/qiniu_usage.py --start 2026-02-01 --end 2026-02-25 --cost
```

#### Update prices for all models (from the modelink.ai pricing API)
```bash
python3 scripts/qiniu_usage.py --update-prices
```

#### Update only exchange rate
```bash
python3 scripts/qiniu_usage.py --update-rate
```

#### List all cached model prices with CNY conversion
```bash
python3 scripts/qiniu_usage.py --list-prices
```

#### Hour-level granularity (max 7 days)
```bash
python3 scripts/qiniu_usage.py --granularity hour --days 3 --cost
```

#### Output raw JSON
```bash
python3 scripts/qiniu_usage.py --today --json
```

### All Options

| Option | Description | Default |
|--------|-------------|---------|
| `--granularity` | `day` or `hour` | `day` |
| `--start` | Start date `YYYY-MM-DD` or RFC3339 | — |
| `--end` | End date `YYYY-MM-DD` or RFC3339 | — |
| `--days N` | Query last N days | 7 |
| `--today` | Query today only | — |
| `--month` | Query current month | — |
| `--json` | Raw JSON output | — |
| `--cost` | Show cost from official v3 billing API (CNY人民币) | — |
| `--update-prices` | Fetch latest prices from sufy.com | — |
| `--update-rate` | Fetch latest USD/CNY exchange rate | — |
| `--list-prices` | List all cached model prices | — |
| `--api-key` | Override API key | env variable |

## Time Range Limits (API constraint)

- `--granularity day`: max **31 days**
- `--granularity hour`: max **7 days**

## Output Format

### Without `--cost` flag

```
  ═══════════════════════════════════════════════════════════════
  Qiniu AI Token Usage Report
  ═══════════════════════════════════════════════════════════════
  Period      : 2026-06-01 ~ 2026-06-15
  Granularity : day

  Model                      │           Input │          Output │           Total
  ───────────────────────────┼─────────────────┼─────────────────┼─────────────────
  claude-4.6-sonnet          │     498.9 kToken │       2.2 kToken │     501.1 kToken
  ───────────────────────────┼─────────────────┼─────────────────┼─────────────────
  TOTAL                      │     498.9 kToken │       2.2 kToken │     501.1 kToken
```

### With `--cost` flag

> 走官方 `/v3/stat/usage/apikey/cost-detail` 账单接口，费用为真实人民币（CNY）。

```
  ═══════════════════════════════════════════════════════════════
  Qiniu AI Billing Report (官方账单)
  ═══════════════════════════════════════════════════════════════
  Period      : 2026-08-01 ~ 2026-08-07
  Granularity : day
  Currency    : CNY (人民币, 官方原价)

  Model                                    │           Tokens │         Cost (CNY)
  ─────────────────────────────────────────┼──────────────────┼───────────────────
  deepseek/deepseek-v4-flash-20260731      │     15.71 MToken │               4.33
  deepseek/deepseek-v4-flash               │      1.43 MToken │               1.47
  ─────────────────────────────────────────┼──────────────────┼───────────────────
  TOTAL                                    │     17.14 MToken │ ¥             5.81

  ─── Daily Breakdown (5 active days) ───
  Date         │           Tokens │         Cost (CNY)
  ─────────────┼──────────────────┼───────────────────
  2026-08-03   │      1.53 MToken │ ¥             0.30
```

### With `--list-prices` flag

```
Cached Model Prices (Exchange Rate: 1 USD = ¥7.25)
======================================================================
  claude-4.6-sonnet              Input: $3.000 (¥21.75)  Output: $15.000 (¥108.75)
  claude-4.6-opus                Input: $15.000 (¥108.75)  Output: $75.000 (¥543.75)
  deepseek-v3                    Input: $0.278 (¥2.02)  Output: $1.110 (¥8.05)
  ...

Total: 50 models
Cache file: ~/.cache/qiniu_prices.json
```

## Pricing Source

Prices are fetched **directly from the Modelink model-square API** and cached locally at `~/.cache/qiniu_prices.json`. Two sources are merged:

1. `https://modelink.ai/zh-CN/models` — live model-square page; each model embeds a `pricingRules` JSON (includes brand-new models).
2. `https://modelink.ai/historical-pricing.json` — single-request bulk file used to fill in older models.

For each model the input price prefers 非缓存输入 (`ncache`) over 缓存输入 (`cache`). Prices are stored as USD per 1M tokens; the stored `input`/`output` are the **off-peak** values. Models with time-of-day pricing also carry `input_peak`/`output_peak`.

`--update-prices` refreshes all models in one command; on API failure it falls back to scraping sufy.com.

### Cost: official billing first, calculation as fallback

`--cost` always prefers the **official v3 billing API** (`/v3/stat/usage/apikey/cost-detail`), which returns real CNY fees already broken down per model and per billing line (缓存输入 / 非缓存输入 / 输出, and 高峰 / 空闲). The report also prints a **高峰/空闲时段明细** section for time-of-day models.

If the official billing API is unavailable, the script falls back to **estimating** from v2 token usage × the cached price table:
- Time-of-day models (DeepSeek) are blended by the **peak-hour fraction** of the requested range.
- Caveat: v2 usage does not separate cached vs non-cached input, so the fallback prices all input at the non-cached rate — it is an **upper-bound** estimate.

### Peak / off-peak pricing (DeepSeek)

DeepSeek models are billed by time of day (see the model page announcement):

- **高峰 (peak)**: Monday–Friday **09:00–12:00** and **14:00–18:00** (Beijing time, UTC+8)
- **空闲 (off-peak)**: all other hours (weekends + nights) — billed at the lower price

### Exchange Rate

- **Default**: 7.25 CNY per USD (fallback)
- **Live**: Fetched from exchangerate-api.com when using `--update-prices` or `--update-rate`
- The exchange rate is cached alongside prices for consistent cost calculations

### Supported Models (with pricing)

| Model | Input ($/M) | Output ($/M) | Input (¥/M) | Output (¥/M) |
|-------|-------------|--------------|-------------|--------------|
| claude-sonnet-5 | 3.0 | 15.0 | ~21.75 | ~108.75 |
| claude-fable-5 | 10.0 | 50.0 | ~72.50 | ~362.50 |
| claude-4.6-sonnet | 3.0 | 15.0 | ~21.75 | ~108.75 |
| claude-4.6-opus | 15.0 | 75.0 | ~108.75 | ~543.75 |
| claude-4.5-sonnet | 3.0 | 15.0 | ~21.75 | ~108.75 |
| claude-4.5-haiku | 1.0 | 5.0 | ~7.25 | ~36.25 |
| gpt-5 | 1.25 | 10.0 | ~9.06 | ~72.50 |
| gpt-5.2 | 1.75 | 14.0 | ~12.69 | ~101.50 |
| deepseek-v3 | 0.278 | 1.11 | ~2.02 | ~8.05 |
| deepseek-v3.1 | 0.556 | 1.67 | ~4.03 | ~12.11 |
| deepseek-r1 | 0.556 | 2.22 | ~4.03 | ~16.10 |
| deepseek-v4-flash-20260731 | 0.1449 | 0.5797 | ~0.97 | ~3.88 |
| gpt-6-astra | 10.0 | 50.0 | ~67.00 | ~335.00 |
| kimi-k3 | 2.899 | 14.493 | ~19.42 | ~97.10 |
| deepseek-v4-pro | 1.67 | 3.33 | ~11.31 | ~22.54 |
| qwen3-max | 0.833 | 3.33 | ~6.04 | ~24.14 |
| glm-4.5 | 0.556 | 2.22 | ~4.03 | ~16.10 |
| kimi-k2 | 0.556 | 2.22 | ~4.03 | ~16.10 |
| gemini-3.5-flash | 0.50 | 9.0 | ~3.63 | ~65.25 |
| gemini-3.1-flash-lite-image | 0.25 | 1.50 | ~1.81 | ~10.88 |
| gemini-3.1-flash-image | 0.50 | 1.50 | ~3.63 | ~10.88 |
| gemini-3.1-pro-image | 2.00 | 12.0 | ~14.50 | ~87.00 |
| gemini-3.1-flash-lite | 0.15 | 1.50 | ~1.09 | ~10.88 |
| ... | ... | ... | ... | ... |

Run `--update-prices` to fetch the latest pricing for all models from the modelink.ai API.

## Workflow for the Agent

When the user asks about Qiniu usage:

1. **Determine the time range** from user's request:
   - "今天用了多少" / "今天花了多少钱" → `--today --cost`
   - "这个月用了多少" → `--month --cost`
   - "最近7天" → `--days 7`
   - Specific range → `--start YYYY-MM-DD --end YYYY-MM-DD`

2. **Determine if cost is needed**:
   - "用了多少钱" / "花费" / "费用" / "多少钱" / "人民币" → add `--cost`
   - Just "用量" / "token" → no `--cost` needed

3. **Run the script**:
   ```bash
   python3 scripts/qiniu_usage.py --today --cost
   ```

4. **Interpret and present** the output to the user in a readable summary.

### Additional Operations

- **Check model prices**: `--list-prices`
- **Update pricing**: `--update-prices` (fetches both prices and exchange rate)
- **Update exchange rate only**: `--update-rate`

## API Key

The default key is read from `$QINIU_AI_API_KEY` environment variable. The key is associated with account on `portal.qiniu.com`. Data returned is scoped to this API key's usage only.

To use a different key:
```bash
export QINIU_AI_API_KEY='sk-xxx...'
python3 scripts/qiniu_usage.py --today --cost
```

## Cache File

The cache file `~/.cache/qiniu_prices.json` stores:
- Last update timestamp
- Source URL
- Current exchange rate
- All model prices

To refresh all data:
```bash
python3 scripts/qiniu_usage.py --update-prices
```

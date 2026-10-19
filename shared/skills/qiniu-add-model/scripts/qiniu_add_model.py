#!/usr/bin/env python3
"""qiniu_add_model.py — 按模型名称查询 Modelink/Qiniu 模型并写入 opencode 配置。

只针对 qiniu 服务商（provider.qiniu）。流程：
  1. 从 modelink.ai 模型广场拉取全量模型元数据（id / name / aliases / 模态 / 能力），
     并用 api.qnaigc.com/v1/models 交叉核对实际可用的模型 id。
  2. 用输入的关键词做模糊匹配。
  3. 命中唯一 → 直接写入；命中多个 → 列出候选退出（或 TTY 下交互选择）。
  4. 写入目标配置文件的 provider.qiniu.models（缺失则自动创建 qiniu provider 块）。

用法：
  python3 qiniu_add_model.py <模型名> [选项]

选项：
  --pick <id>          指定确切的模型 id（消歧用）
  --key <key>          写入 models 的键（默认取 id 末段）
  --reasoning BOOL     额外写入 "reasoning": true/false
  --with-limits        额外写入 limit.context / limit.output
  --dry-run            只预览，不写文件
  -y, --yes            多个候选时自动取最佳
  --list               只列出候选，不写入
  --json               以 JSON 输出（供 agent 解析）
  --refresh            强制刷新模型目录缓存
  --config PATH        覆盖目标配置文件（可重复），默认写到 3 个配置文件
  --quiet              精简输出
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
import time
import urllib.request

# ── 常量 ──────────────────────────────────────────────────────────────────────

MODELINK_MODELS_URL = "https://modelink.ai/zh-CN/models"
QNAIGC_MODELS_URL = "https://api.qnaigc.com/v1/models"
MODELS_CACHE_FILE = os.path.expanduser("~/.cache/qiniu_add_model_models.json")
CACHE_TTL_SECONDS = 12 * 3600

# 默认写入的目标配置文件（只写 provider.qiniu.models）
DEFAULT_CONFIGS = [
    os.path.expanduser("~/opencode.json"),
    os.path.expanduser("~/dao-agent-portal/opencode/opencode.json"),
    os.path.expanduser("~/.config/opencode/opencode.json"),
]

QINIU_NPM = "@ai-sdk/openai-compatible"
QINIU_NAME = "Qiniu AI"
QINIU_BASE_URL = "https://api.qnaigc.com/v1"

# modelink 模态 → opencode modalities 枚举
MODALITY_MAP = {"file": "pdf"}
VALID_MODALITIES = {"text", "audio", "image", "video", "pdf"}

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


# ── HTTP ─────────────────────────────────────────────────────────────────────

def _http_get(url: str, timeout: int = 60, headers: dict | None = None) -> str:
    h = {"User-Agent": UA, "Accept": "application/json,text/html,*/*",
         "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "ignore")


# ── Modelink 模型广场解析 ─────────────────────────────────────────────────────

def _balanced(s: str, start: int) -> int | None:
    """返回从 s[start] 的 '{' 起配对的 '}' 之后的下标。"""
    depth = 0
    i = start
    instr = esc = False
    while i < len(s):
        c = s[i]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                instr = False
        else:
            if c == '"':
                instr = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    return None


def parse_modelink_square(html: str) -> dict:
    """解析模型广场页面，返回 {model_id: {...元数据...}}。"""
    s = html.replace('\\"', '"').replace("\\\\", "\\")
    models: dict = {}
    for m in re.finditer(r'\{"id":"', s):
        end = _balanced(s, m.start())
        if not end:
            continue
        try:
            obj = json.loads(s[m.start():end])
        except json.JSONDecodeError:
            continue
        mid = obj.get("id")
        if mid and "inputModalities" in obj:
            models[mid] = obj
    return models


def _norm_modalities(values) -> list:
    out = []
    for v in values or []:
        if not isinstance(v, str):
            continue
        v = MODALITY_MAP.get(v, v)
        if v in VALID_MODALITIES and v not in out:
            out.append(v)
    return out


def _pretty_name(model_id: str, square_name: str | None) -> str:
    base = square_name or model_id.split("/")[-1]
    base = base.replace("_", " ").replace("-", " ").strip()
    base = re.sub(r"\s+", " ", base)
    return f"{base} (Qiniu)"


# ── 目录装配 / 缓存 ───────────────────────────────────────────────────────────

def fetch_catalog(refresh: bool = False) -> dict:
    """返回 {model_id: {id, name, aliases, input, output, reasoning, tool_call,
    context, max_output, source}}。带本地缓存。"""
    if not refresh and os.path.exists(MODELS_CACHE_FILE):
        try:
            cached = json.load(open(MODELS_CACHE_FILE, encoding="utf-8"))
            if time.time() - cached.get("_ts", 0) < CACHE_TTL_SECONDS:
                return cached.get("models", {})
        except Exception:
            pass

    catalog: dict = {}

    # 1) modelink 模型广场（元数据最全）
    try:
        html = _http_get(MODELINK_MODELS_URL)
        square = parse_modelink_square(html)
        for mid, o in square.items():
            caps = o.get("capabilities") or {}
            def _sup(k):
                v = caps.get(k)
                return v.get("supported") if isinstance(v, dict) else v
            catalog[mid] = {
                "id": mid,
                "name": o.get("name") or mid.split("/")[-1],
                "aliases": [a for a in (o.get("aliases") or []) if isinstance(a, str)],
                "input": _norm_modalities(o.get("inputModalities")),
                "output": _norm_modalities(o.get("outputModalities")),
                "reasoning": _sup("reasoning"),
                "tool_call": _sup("function_calling"),
                "context": o.get("contextLength"),
                "max_output": o.get("maxOutput"),
                "source": "modelink",
            }
        print(f"  modelink 模型广场: {len(square)} 个模型", file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        print(f"  modelink 模型广场拉取失败: {e}", file=sys.stderr)

    # 2) qnaigc /v1/models（实际可用清单，补齐 modelink 缺失的）
    try:
        key = _discover_api_key()
        data = json.loads(_http_get(QNAIGC_MODELS_URL, headers={"Authorization": f"Bearer {key}"}))
        added = 0
        for m in data.get("data", []):
            mid = m.get("id")
            if not mid:
                continue
            if mid in catalog:
                catalog[mid]["available"] = True
            else:
                catalog[mid] = {
                    "id": mid,
                    "name": mid.split("/")[-1],
                    "aliases": [],
                    "input": ["text"],
                    "output": ["text"],
                    "reasoning": None,
                    "tool_call": None,
                    "context": m.get("context_length"),
                    "max_output": m.get("max_tokens"),
                    "source": "qnaigc",
                    "available": True,
                }
                added += 1
        print(f"  qnaigc /v1/models: {len(data.get('data', []))} 个（新增 {added}）", file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        print(f"  qnaigc /v1/models 拉取失败: {e}", file=sys.stderr)

    if not catalog:
        raise SystemExit("错误：无法获取任何模型目录（modelink 与 qnaigc 均失败）")

    try:
        os.makedirs(os.path.dirname(MODELS_CACHE_FILE), exist_ok=True)
        json.dump({"_ts": time.time(), "models": catalog},
                  open(MODELS_CACHE_FILE, "w", encoding="utf-8"), ensure_ascii=False)
    except Exception:
        pass
    return catalog


# ── 匹配 ─────────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "", (s or "").lower())


def _score(model: dict, qn: str) -> float:
    idn = _norm(model["id"])
    last = _norm(model["id"].split("/")[-1])
    name = _norm(model.get("name", ""))
    aliases = [_norm(a) for a in model.get("aliases", [])]
    fields = {idn, last, name, *aliases} - {""}
    best = 0.0
    for cn in fields:
        if cn == qn:
            best = max(best, 100.0)
        elif cn.startswith(qn) or idn.startswith(qn):
            # 候选以查询开头：越短越相关
            best = max(best, 96.0 - min(len(cn) - len(qn), 30) * 0.6)
        elif qn in cn:
            best = max(best, 66.0)
        ratio = difflib.SequenceMatcher(None, qn, cn).ratio()
        best = max(best, ratio * 55.0)
    return best


def match(catalog: dict, query: str) -> list:
    qn = _norm(query)
    if not qn:
        return []
    scored = [(_score(m, qn), m) for m in catalog.values()]
    scored = [(s, m) for s, m in scored if s >= 55]
    scored.sort(key=lambda x: (-x[0], len(x[1]["id"])))
    return scored


def format_candidate(score: float, m: dict) -> str:
    aliases = ("  aliases: " + ", ".join(m["aliases"])) if m.get("aliases") else ""
    return (f"{m['id']}  ({m.get('name','')})  [{score:.0f}分]"
            f"{aliases}  模态: {'/'.join(m.get('input') or []) or '?'} → "
            f"{'/'.join(m.get('output') or []) or '?'}")


# ── 写配置 ───────────────────────────────────────────────────────────────────

def _discover_api_key() -> str:
    for path in DEFAULT_CONFIGS:
        try:
            d = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        opts = (d.get("provider", {}) or {}).get("qiniu", {}).get("options", {}) or {}
        if opts.get("apiKey"):
            return opts["apiKey"]
    return os.environ.get("QINIU_AI_API_KEY", "")


def build_entry(m: dict, reasoning: bool | None, with_limits: bool) -> dict:
    entry: dict = {
        "name": _pretty_name(m["id"], m.get("name")),
        "id": m["id"],
    }
    if reasoning is not None:
        entry["reasoning"] = reasoning
    inp, out = m.get("input") or [], m.get("output") or []
    if inp or out:
        entry["modalities"] = {"input": inp, "output": out}
    if with_limits and (m.get("context") or m.get("max_output")):
        lim = {"context": m.get("context") or 0, "output": m.get("max_output") or 0}
        if lim["context"] and lim["output"]:
            entry["limit"] = lim
    return entry


def write_model(path: str, key: str, entry: dict, dry_run: bool) -> str:
    if not os.path.exists(path):
        return "跳过（文件不存在）"
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return f"跳过（解析失败: {e}）"
    if not isinstance(d, dict):
        return "跳过（不是 JSON 对象）"

    providers = d.setdefault("provider", {})
    if not isinstance(providers, dict):
        return "跳过（provider 不是对象）"
    qiniu = providers.setdefault("qiniu", {})
    if not isinstance(qiniu, dict):
        return "跳过（provider.qiniu 不是对象）"
    qiniu.setdefault("npm", QINIU_NPM)
    qiniu.setdefault("name", QINIU_NAME)
    opts = qiniu.setdefault("options", {})
    opts.setdefault("baseURL", QINIU_BASE_URL)
    key_from_disk = _discover_api_key()
    if key_from_disk:
        opts.setdefault("apiKey", key_from_disk)
    models = qiniu.setdefault("models", {})
    if not isinstance(models, dict):
        return "跳过（provider.qiniu.models 不是对象）"

    if key in models and models[key].get("id") == entry["id"]:
        return "已存在，未改动"
    action = "更新" if key in models else "新增"
    models[key] = entry

    if dry_run:
        return f"{action}（dry-run 未写入）"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return f"✓ {action}"


# ── 主流程 ───────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(add_help=True, description="按名称查询并写入 qiniu 模型配置")
    ap.add_argument("query", nargs="?", help="模型名称/关键词")
    ap.add_argument("--pick", help="指定确切的模型 id")
    ap.add_argument("--key", help="写入 models 的键（默认取 id 末段）")
    ap.add_argument("--reasoning", choices=["true", "false"], help="写入 reasoning 字段")
    ap.add_argument("--with-limits", action="store_true", help="写入 limit.context/output")
    ap.add_argument("--dry-run", action="store_true", help="只预览，不写文件")
    ap.add_argument("-y", "--yes", action="store_true", help="多个候选时自动取最佳")
    ap.add_argument("--list", action="store_true", help="只列出候选，不写入")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--refresh", action="store_true", help="强制刷新模型目录")
    ap.add_argument("--config", action="append", default=[], help="目标配置文件（可重复）")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if not args.query and not args.pick:
        ap.error("需要提供模型名（query）或 --pick <id>")

    catalog = fetch_catalog(refresh=args.refresh)
    reasoning = None if args.reasoning is None else (args.reasoning == "true")

    # 选定模型
    chosen = None
    if args.pick:
        for m in catalog.values():
            if m["id"] == args.pick or args.pick in m.get("aliases", []):
                chosen = m
                break
        if not chosen:
            if args.json:
                print(json.dumps({"error": "not_found", "pick": args.pick}, ensure_ascii=False))
            else:
                print(f"错误：未找到模型 id '{args.pick}'", file=sys.stderr)
            return 1
    else:
        candidates = match(catalog, args.query)
        if not candidates:
            if args.json:
                print(json.dumps({"query": args.query, "matches": []}, ensure_ascii=False))
            else:
                print(f"未匹配到任何模型：{args.query}", file=sys.stderr)
            return 1

        exact = [m for s, m in candidates if s >= 100]
        top_score, top = candidates[0]
        if len(exact) == 1:
            chosen, ambiguous = exact[0], False
        elif len(exact) > 1:
            chosen, ambiguous = top, True
        else:
            unique = len(candidates) == 1 or (top_score >= 90 and top_score - candidates[1][0] >= 10)
            chosen, ambiguous = top, not unique
        if ambiguous and args.yes:
            ambiguous = False  # 自动取最佳
        if ambiguous:
            # 歧义 → 输出候选
            if args.json:
                print(json.dumps({
                    "query": args.query, "ambiguous": True,
                    "matches": [{"id": m["id"], "name": m.get("name"), "score": round(s),
                                 "input": m.get("input"), "output": m.get("output")}
                                for s, m in candidates[:15]],
                }, ensure_ascii=False, indent=2))
                return 2
            print(f"“{args.query}” 匹配到多个模型，请选择（用 --pick <id>）：")
            for s, m in candidates[:15]:
                print("  " + format_candidate(s, m))
            if args.list or not sys.stdin.isatty():
                return 2
            chosen = _interactive(candidates)
            if chosen is None:
                return 2

    key = args.key or chosen["id"].split("/")[-1]
    entry = build_entry(chosen, reasoning, args.with_limits)
    targets = args.config or DEFAULT_CONFIGS

    if args.list:
        if args.json:
            print(json.dumps({"model": chosen, "entry": entry, "key": key,
                              "targets": targets}, ensure_ascii=False, indent=2))
        else:
            print(f"选定模型: {chosen['id']}  ({chosen.get('name','')})")
            print(json.dumps(entry, ensure_ascii=False, indent=2))
        return 0

    results = [{"path": p, "status": write_model(p, key, entry, args.dry_run)}
               for p in targets]

    if args.json:
        print(json.dumps({"model": chosen, "key": key, "entry": entry, "targets": results},
                         ensure_ascii=False, indent=2))
    elif not args.quiet:
        print(f"选定模型: {chosen['id']}  ({chosen.get('name','')})")
        print(f"写入条目 (key={key}):")
        print(json.dumps(entry, ensure_ascii=False, indent=2))
        print("\n写入目标配置文件：")
        for r in results:
            print(f"  {r['path']}\n    → {r['status']}")
        print("\n完成。请完全重启 opencode 使配置生效。")
    return 0


def _interactive(candidates: list):
    """TTY 下让用户选择序号，返回选中的模型 dict（取消返回 None）。"""
    print("输入序号选择（回车取消）：", end=" ", flush=True)
    try:
        line = input().strip()
    except EOFError:
        return None
    if not line:
        return None
    try:
        idx = int(line) - 1
        _, m = candidates[idx]
    except (ValueError, IndexError):
        print("无效序号", file=sys.stderr)
        return None
    return m


if __name__ == "__main__":
    sys.exit(main())

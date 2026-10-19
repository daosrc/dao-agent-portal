#!/usr/bin/env node
/**
 * get-token.mjs — 从本机 Chrome 的 Local Storage 里静默读取米画师登录 token。
 *
 * 支持来源（只读，不修改任何文件，不需要 Chrome 以调试模式启动）：
 *   - http://localhost:8080
 *   - https://test.mihuashi.com
 *
 * 用法：
 *   node get-token.mjs                                    # 两个地址都查，输出 JSON
 *   node get-token.mjs --origin http://localhost:8080     # 只查一个地址
 *   node get-token.mjs --field token                      # 只输出 token 字符串
 *   node get-token.mjs --field expires                    # 只输出过期时间戳
 *   node get-token.mjs --eval --origin https://test.mihuashi.com
 *       → 输出箭头函数，直接传给 chrome-devtools 的 evaluate_script
 *   node get-token.mjs --init --origin https://test.mihuashi.com
 *       → 输出裸语句，直接传给 chrome-devtools 的 navigate_page initScript
 *
 * 退出码永远是 0；查不到就输出空串 / {"found":false,...}，调用方继续后续流程即可。
 */

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const ORIGINS = ['http://localhost:8080', 'https://test.mihuashi.com'];

// 顺序即优先级：真实浏览器 profile 在前，自动化工具自建 profile 垫底
const PROFILE_ROOTS = [
  'Library/Application Support/Google/Chrome',
  'Library/Application Support/Google/Chrome Beta',
  'Library/Application Support/Google/Chrome Canary',
  'Library/Application Support/Chromium',
  'Library/Application Support/Microsoft Edge',
  'Library/Application Support/Arc/User Data',
  '.cache/chrome-devtools-mcp',
];

// ---------------------------------------------------------------- args
const argv = process.argv.slice(2);
const args = {
  origins: [],
  field: 'json',
  eval: false,
  init: false,
  includeExpired: false,
};
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === '--origin' || a === '-o') args.origins.push(argv[++i]);
  else if (a === '--field' || a === '-f') args.field = argv[++i];
  else if (a === '--js' || a === '--eval') args.eval = true;
  else if (a === '--init' || a === '--initscript') args.init = true;
  else if (a === '--include-expired') args.includeExpired = true;
  else if (a === '--help' || a === '-h') {
    console.log(fs.readFileSync(new URL(import.meta.url), 'utf8').split('*/')[0]);
    process.exit(0);
  }
}
const wantOrigins = args.origins.length ? args.origins : ORIGINS;

// ---------------------------------------------------------------- leveldb primitives
function readVarint(buf, pos) {
  let result = 0;
  let shift = 0;
  let b;
  do {
    if (pos >= buf.length) throw new Error('varint eof');
    b = buf[pos++];
    result += (b & 0x7f) * 2 ** shift;
    shift += 7;
    if (shift > 63) throw new Error('varint too long');
  } while (b & 0x80);
  return [result, pos];
}

function snappyUncompress(input) {
  let [len, pos] = readVarint(input, 0);
  const out = Buffer.alloc(len);
  let op = 0;
  while (pos < input.length && op < len) {
    const tag = input[pos++];
    const t = tag & 3;
    if (t === 0) {
      let l = tag >>> 2;
      if (l < 60) l += 1;
      else {
        const n = l - 59;
        l = 0;
        for (let i = 0; i < n; i++) l += input[pos++] * 2 ** (8 * i);
        l += 1;
      }
      input.copy(out, op, pos, pos + l);
      pos += l;
      op += l;
    } else if (t === 1) {
      const l = ((tag >>> 2) & 7) + 4;
      const off = ((tag & 0xe0) << 3) | input[pos++];
      for (let i = 0; i < l; i++) {
        out[op] = out[op - off];
        op++;
      }
    } else if (t === 2) {
      const l = (tag >>> 2) + 1;
      const off = input[pos] | (input[pos + 1] << 8);
      pos += 2;
      for (let i = 0; i < l; i++) {
        out[op] = out[op - off];
        op++;
      }
    } else {
      const l = (tag >>> 2) + 1;
      const off =
        input[pos] | (input[pos + 1] << 8) | (input[pos + 2] << 16) | (input[pos + 3] << 24);
      pos += 4;
      for (let i = 0; i < l; i++) {
        out[op] = out[op - off];
        op++;
      }
    }
  }
  return out.subarray(0, op);
}

function parseBlockEntries(block, out) {
  const restarts = block.readUInt32LE(block.length - 4);
  const limit = block.length - 4 - restarts * 4;
  let pos = 0;
  let lastKey = Buffer.alloc(0);
  while (pos < limit) {
    let shared;
    let nonShared;
    let valueLen;
    [shared, pos] = readVarint(block, pos);
    [nonShared, pos] = readVarint(block, pos);
    [valueLen, pos] = readVarint(block, pos);
    const key = Buffer.concat([lastKey.subarray(0, shared), block.subarray(pos, pos + nonShared)]);
    pos += nonShared;
    out.push({ key, value: block.subarray(pos, pos + valueLen) });
    pos += valueLen;
    lastKey = key;
  }
}

function readBlock(fileBuf, offset, size) {
  const data = fileBuf.subarray(offset, offset + size);
  const type = fileBuf[offset + size];
  if (type === 0) return data;
  if (type === 1) return snappyUncompress(data);
  throw new Error('bad block compression ' + type);
}

function parseTable(buf, out) {
  const footer = buf.subarray(buf.length - 48);
  let pos = 0;
  let off;
  let size;
  [off, pos] = readVarint(footer, pos); // metaindex
  [size, pos] = readVarint(footer, pos);
  [off, pos] = readVarint(footer, pos); // index
  [size, pos] = readVarint(footer, pos);
  const indexEntries = [];
  parseBlockEntries(readBlock(buf, off, size), indexEntries);
  for (const e of indexEntries) {
    let p = 0;
    let bo;
    let bs;
    [bo, p] = readVarint(e.value, p);
    [bs, p] = readVarint(e.value, p);
    parseBlockEntries(readBlock(buf, bo, bs), out);
  }
}

function parseLog(buf, out) {
  const BLOCK = 32768;
  let pos = 0;
  let pending = [];
  const handleBatch = (batch) => {
    if (batch.length < 12) return;
    let p = 8;
    let count;
    [count, p] = readVarint(batch, p);
    for (let i = 0; i < count; i++) {
      const t = batch[p++];
      let klen;
      [klen, p] = readVarint(batch, p);
      const key = batch.subarray(p, p + klen);
      p += klen;
      if (t === 1) {
        let vlen;
        [vlen, p] = readVarint(batch, p);
        out.push({ key, value: batch.subarray(p, p + vlen) });
        p += vlen;
      }
    }
  };
  while (pos + 7 <= buf.length) {
    const blockOffset = pos % BLOCK;
    if (BLOCK - blockOffset < 7) {
      pos += BLOCK - blockOffset;
      continue;
    }
    const len = buf.readUInt16LE(pos + 4);
    const type = buf[pos + 6];
    pos += 7;
    if (type === 0 && len === 0) continue;
    const frag = buf.subarray(pos, pos + len);
    pos += len;
    if (type === 1) {
      pending = [];
      handleBatch(frag);
    } else if (type === 2) pending = [frag];
    else if (type === 3) pending.push(frag);
    else if (type === 4) {
      pending.push(frag);
      handleBatch(Buffer.concat(pending));
      pending = [];
    }
  }
}

// ---------------------------------------------------------------- chrome storage decode
const MAX_FILE = 256 * 1024 * 1024;

/** Chrome localStorage key: "_" origin "\x00" <encoding> name <8-byte leveldb trailer> */
function decodeEntry(key, value) {
  if (key.length < 3 || key[0] !== 0x5f) return null;
  const sep = key.indexOf(0, 1);
  if (sep < 0) return null;
  const origin = key.subarray(1, sep).toString('latin1');
  const body = key.subarray(sep + 1, Math.max(sep + 1, key.length - 8));
  if (!body.length) return null;
  const enc = body[0];
  let name = enc === 0 ? body.subarray(1).toString('utf16le') : body.subarray(1).toString('latin1');
  name = name.replace(/[\u0000-\u001f].*$/s, '');
  let seq = 0;
  if (key.length >= 8) {
    try {
      seq = Number(key.readBigUInt64LE(key.length - 8) >> 8n);
    } catch {
      seq = 0;
    }
  }
  if (!value.length) return { origin, name, value: '', seq };
  const venc = value[0];
  const vbody = value.subarray(1);
  const str = venc === 0 ? vbody.toString('utf16le') : vbody.toString('latin1');
  return { origin, name, value: str, seq };
}

function profileDirs() {
  const dirs = [];
  for (const root of PROFILE_ROOTS) {
    const base = path.join(os.homedir(), root);
    let names;
    try {
      names = fs.readdirSync(base);
    } catch {
      continue;
    }
    for (const name of names) {
      const ldb = path.join(base, name, 'Local Storage', 'leveldb');
      if (fs.existsSync(ldb)) dirs.push({ browser: root.split('/').pop(), profile: name, dir: ldb });
    }
    // 有些根目录本身就是单个 profile（例如 chrome-devtools-mcp 的临时 profile）
    const direct = path.join(base, 'Local Storage', 'leveldb');
    if (fs.existsSync(direct)) {
      dirs.push({ browser: root.split('/').pop(), profile: 'Default', dir: direct });
    }
  }
  return dirs;
}

function scanDir(dir) {
  const out = [];
  let files;
  try {
    files = fs.readdirSync(dir).filter((f) => f.endsWith('.ldb') || f.endsWith('.log'));
  } catch {
    return out;
  }
  for (const f of files) {
    const full = path.join(dir, f);
    let st;
    try {
      st = fs.statSync(full);
    } catch {
      continue;
    }
    if (st.size > MAX_FILE) continue;
    let buf;
    try {
      buf = fs.readFileSync(full);
    } catch {
      continue;
    }
    const entries = [];
    try {
      if (f.endsWith('.ldb')) parseTable(buf, entries);
      else parseLog(buf, entries);
    } catch {
      continue; // 损坏或正在写入的文件直接跳过
    }
    for (const e of entries) {
      const d = decodeEntry(e.key, e.value);
      if (d) out.push({ ...d, file: f });
    }
  }
  return out;
}

// ---------------------------------------------------------------- collect
const aliases = {
  'http://localhost:8080': ['http://localhost:8080', 'http://127.0.0.1:8080'],
  'https://test.mihuashi.com': ['https://test.mihuashi.com'],
};

const now = Date.now();
const result = {};
for (const origin of wantOrigins) {
  result[origin] = {
    found: false,
    origin,
    token: null,
    expires: null,
    expired: false,
    usable: false,
  };
}

/** 单个 profile 内，取某 origin 的最新一组 token / expires */
function pick(entries, origin) {
  const keys = aliases[origin] || [origin];
  const relevant = entries
    .filter((e) => keys.includes(e.origin))
    .filter((e) => e.name === 'remember_token' || e.name === 'remember_token_expires')
    .sort((a, b) => a.seq - b.seq);
  if (!relevant.length) return null;
  let token = null;
  let expires = null;
  let matchedOrigin = relevant[0].origin;
  for (const e of relevant) {
    if (e.name === 'remember_token') {
      token = e.value;
      matchedOrigin = e.origin;
    } else {
      expires = e.value;
    }
  }
  if (!token) return null;
  const exp = Number(expires);
  return { token, expires: Number.isFinite(exp) && exp > 0 ? exp : null, matchedOrigin };
}

const profiles = profileDirs();
for (const origin of wantOrigins) {
  const candidates = [];
  for (const p of profiles) {
    const entries = scanDir(p.dir);
    if (!entries.length) continue;
    const hit = pick(entries, origin);
    if (!hit) continue;
    candidates.push({
      ...hit,
      source: `${p.browser}/${p.profile}`,
      expired: hit.expires ? hit.expires <= now : false,
    });
  }
  if (!candidates.length) continue;

  // 优先未过期的（profile 顺序即优先级）；全部过期才回退到第一个
  const best = candidates.find((c) => !c.expired) || candidates[0];
  const slot = result[origin];
  slot.token = best.token;
  slot.expires = best.expires;
  slot.source = best.source;
  slot.matchedOrigin = best.matchedOrigin;
  slot.expiresAt = best.expires ? new Date(best.expires).toISOString() : null;
  slot.expired = best.expired;
  slot.usable = !best.expired;
  slot.found = true;
  if (!slot.usable && !args.includeExpired) {
    slot.found = false;
    slot.reason = 'expired';
  }
}

// ---------------------------------------------------------------- output
const target = wantOrigins[0];
const targetSlot = result[target];

if (args.init) {
  if (!targetSlot || !targetSlot.found) {
    console.log('');
    process.exit(0);
  }
  console.log(
    `try{localStorage.setItem("remember_token",${JSON.stringify(targetSlot.token)});` +
      `localStorage.setItem("remember_token_expires",${JSON.stringify(
        String(targetSlot.expires ?? ''),
      )});}catch(e){}`,
  );
  process.exit(0);
}

if (args.eval) {
  if (!targetSlot || !targetSlot.found) {
    console.log('');
    process.exit(0);
  }
  const payload = {
    remember_token: targetSlot.token,
    remember_token_expires: String(targetSlot.expires ?? ''),
  };
  console.log(
    `() => { const d = ${JSON.stringify(payload)};` +
      ` for (const [k, v] of Object.entries(d)) if (v) localStorage.setItem(k, v);` +
      ` return { ok: true, origin: location.origin, hasToken: !!localStorage.getItem('remember_token') }; }`,
  );
  process.exit(0);
}

if (args.field === 'token') {
  console.log(targetSlot && targetSlot.found ? targetSlot.token : '');
  process.exit(0);
}
if (args.field === 'expires') {
  console.log(targetSlot && targetSlot.found && targetSlot.expires ? String(targetSlot.expires) : '');
  process.exit(0);
}

const anyFound = Object.values(result).some((s) => s.found);
console.log(JSON.stringify({ found: anyFound, tokens: result }, null, 2));

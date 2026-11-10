#!/usr/bin/env node
// Image Generation MCP Server — stdio (official @modelcontextprotocol/sdk)
// Exposes an `image_gen` tool that calls a Qiniu image-generation model
// and saves the resulting image(s) to disk.

import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// --- Config -----------------------------------------------------------------
const KEYCHAIN_SERVICE = 'qiniu-ai';
const DEFAULT_BASE_URL = 'https://api.qnaigc.com/v1';

// Read the API key from the macOS login keychain (single source of truth).
function keychainApiKey() {
  if (process.platform !== 'darwin') return '';
  try {
    return execFileSync(
      'security',
      ['find-generic-password', '-a', os.userInfo().username, '-s', KEYCHAIN_SERVICE, '-w'],
      { encoding: 'utf8', timeout: 10000 },
    ).trim();
  } catch {
    return '';
  }
}

// Resolve "{env:VAR}" placeholders; leave literal values untouched.
function resolvePlaceholder(value) {
  const m = /^\{env:([A-Za-z0-9_]+)\}$/.exec(value || '');
  return m ? process.env[m[1]] || '' : value || '';
}

function loadQiniuConfig() {
  const envBase = process.env.MODELINK_BASE_URL || process.env.QINIU_BASE_URL || process.env.OPENROUTER_BASE_URL;
  const envKey = process.env.MODELINK_API_KEY || process.env.QINIU_API_KEY || process.env.OPENROUTER_API_KEY;
  if (envBase && envKey) return { baseURL: envBase, apiKey: envKey };
  const configPaths = [
    path.join(os.homedir(), '.config/opencode/opencode.json'),
    path.join(os.homedir(), '.config/opencode/opencode.jsonc'),
  ];
  for (const p of configPaths) {
    try {
      const raw = fs.readFileSync(p, 'utf-8');
      const cfg = JSON.parse(raw.replace(/^\uFEFF/, ''));
      const q = cfg?.provider?.qiniu;
      const baseURL = resolvePlaceholder(q?.options?.baseURL);
      const apiKey = resolvePlaceholder(q?.options?.apiKey) || keychainApiKey();
      if (baseURL && apiKey) return { baseURL, apiKey };
    } catch { /* keep trying */ }
  }
  const apiKey = keychainApiKey();
  if (apiKey) return { baseURL: envBase || DEFAULT_BASE_URL, apiKey };
  throw new Error('Qiniu baseURL/apiKey not found. Set QINIU_BASE_URL/QINIU_API_KEY, store the key in the login keychain (service qiniu-ai), or configure provider.qiniu in opencode.json');
}

const QINIU = loadQiniuConfig();
const DEFAULT_MODEL = process.env.IMAGE_GEN_MODEL || 'google/gemini-3.1-flash-image';
const DEFAULT_OUT_DIR = process.env.IMAGE_GEN_OUT_DIR || path.join(os.homedir(), 'Downloads');

// --- Qiniu image generation (OpenAI-compatible) -----------------------------
async function generateImage({ model, prompt, outDir, filename, aspectRatio }) {
  const body = {
    model: model || DEFAULT_MODEL,
    messages: [{ role: 'user', content: prompt }],
    modalities: ['image', 'text'],
  };
  if (aspectRatio) body.image_config = { aspect_ratio: aspectRatio };

  const res = await fetch(`${QINIU.baseURL}/chat/completions`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${QINIU.apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Qiniu API error ${res.status}: ${text.slice(0, 500)}`);
  }
  const data = await res.json();

  const message = data?.choices?.[0]?.message;
  const images = message?.images ?? [];
  if (!images.length) {
    throw new Error('No image returned by model. The model did not produce an image.');
  }

  const saved = [];
  for (let i = 0; i < images.length; i++) {
    const url = images[i]?.image_url?.url || '';
    if (!url.startsWith('data:image/')) continue;
    const [meta, b64] = url.split(',');
    const mime = (meta.match(/^data:([^;]+)/) || [])[1] || 'image/png';
    const ext = mime.split('/')[1]?.split(';')[0] || 'png';
    const buf = Buffer.from(b64, 'base64');
    const name = filename || `image_${Date.now()}_${i}.${ext}`;
    const filePath = path.resolve(outDir || DEFAULT_OUT_DIR, name);
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, buf);
    saved.push({ path: filePath, size: buf.length, mime, mediaType: mime });
  }
  if (!saved.length) throw new Error('Image data could not be decoded.');
  return { saved, text: message?.text || null };
}

// --- MCP server -------------------------------------------------------------
const server = new McpServer(
  { name: 'image-gen-mcp', version: '1.0.0' },
  { capabilities: { tools: {} } },
);

server.tool(
  'image_gen',
  'Generate an image by calling an image-generation model (Qiniu). Saves the image file(s) to disk and returns their absolute paths. Use this to create pictures from a text prompt.',
  {
    prompt: z.string().describe('Detailed text description of the image to generate.'),
    model: z.string().optional().describe(`Image model id. Default: ${DEFAULT_MODEL}`),
    outDir: z.string().optional().describe(`Directory to save the image into. Default: ${DEFAULT_OUT_DIR}`),
    filename: z.string().optional().describe('Optional filename (e.g. rain.png). Auto-generated if omitted.'),
    aspectRatio: z.string().optional().describe('Optional aspect ratio, e.g. 16:9, 1:1, 9:16.'),
  },
  async (args) => {
    if (!args.prompt) throw new Error('Missing required argument: prompt');
    const result = await generateImage(args);
    const lines = [
      `Generated ${result.saved.length} image(s):`,
      ...result.saved.map(f => `- ${f.path} (${f.size} bytes, ${f.mime})`),
    ];
    if (result.text) lines.push(`\nModel note: ${result.text}`);
    return { content: [{ type: 'text', text: lines.join('\n') }] };
  },
);

const transport = new StdioServerTransport();
await server.connect(transport);
console.error('[image-gen-mcp] connected');
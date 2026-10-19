#!/usr/bin/env node
// Video Generation MCP Server — stdio (official @modelcontextprotocol/sdk)
// Exposes a `video_gen` tool that calls the Modelink (Qiniu) video-generation API,
// polls the async job until completion, downloads the resulting MP4(s) to disk,
// and returns their absolute paths.
//
// Two backends are supported and auto-selected by model id:
//   1. Seedance (Doubao/Dreamina) -> Fal queue: POST /queue/{vendor}/seedance-2.5/text-to-video
//      Auth: `Authorization: Key {api_key}` (NOT Bearer)
//   2. Kling / Sora               -> OpenAI-style: POST /videos
//      Auth: `Authorization: Bearer {api_key}`

import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// --- Config -----------------------------------------------------------------
function loadConfig() {
  const envBase = process.env.MODELINK_BASE_URL || process.env.QINIU_BASE_URL || process.env.OPENROUTER_BASE_URL;
  const envKey = process.env.MODELINK_API_KEY || process.env.QINIU_API_KEY || process.env.OPENROUTER_API_KEY;
  if (envBase && envKey) return { baseURL: envBase.replace(/\/+$/, ''), apiKey: envKey };
  const configPaths = [
    path.join(os.homedir(), '.config/opencode/opencode.json'),
    path.join(os.homedir(), '.config/opencode/opencode.jsonc'),
  ];
  for (const p of configPaths) {
    try {
      const raw = fs.readFileSync(p, 'utf-8');
      const cfg = JSON.parse(raw.replace(/^\uFEFF/, ''));
      const q = cfg?.provider?.qiniu;
      if (q?.options?.baseURL && q?.options?.apiKey) {
        return { baseURL: q.options.baseURL.replace(/\/+$/, ''), apiKey: q.options.apiKey };
      }
    } catch { /* keep trying */ }
  }
  throw new Error('API baseURL/apiKey not found. Set MODELINK_BASE_URL/MODELINK_API_KEY or configure provider.qiniu in opencode.json');
}

const CFG = loadConfig();
// baseURL may include "/v1" (OpenAI-style). Seedance's Fal queue lives at the root (no /v1),
// while Kling's /videos lives under /v1. Derive a root host for the Fal queue.
const ROOT_BASE = CFG.baseURL.replace(/\/v1\/?$/, '');
const DEFAULT_MODEL = process.env.VIDEO_GEN_MODEL || 'kling-video-o1';
const DEFAULT_OUT_DIR = process.env.VIDEO_GEN_OUT_DIR || path.join(os.homedir(), 'Downloads');
const DEFAULT_POLL_INTERVAL_MS = 10000;
const DEFAULT_POLL_TIMEOUT_MS = 900000; // 15 min

// --- Model routing ----------------------------------------------------------
function isSeedanceModel(model = '') {
  const m = model.toLowerCase();
  return m.includes('seedance') || m.includes('dreamina') || m.includes('doubao-seedance')
    || m.includes('doubao/seedance') || m.includes('bytedance/seedance');
}

function isDreaminaModel(model = '') {
  const m = model.toLowerCase();
  return m.includes('dreamina') || m.includes('byteplus');
}

// --- Seedance (Fal queue) ---------------------------------------------------
async function seedanceCreateJob({ prompt, seconds, size, resolution, aspectRatio, generateAudio }) {
  const url = `${ROOT_BASE}/queue/bytedance/seedance-2.5/text-to-video`;
  const body = { prompt };
  const res = resolution || sizeToResolution(size);
  if (res) body.resolution = res;
  if (seconds) body.duration = String(seconds);
  const ar = aspectRatio || sizeToAspectRatio(size);
  if (ar) body.aspect_ratio = ar;
  if (generateAudio != null) body.generate_audio = !!generateAudio;

  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Authorization': `Key ${CFG.apiKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const text = await resp.text();
  if (!resp.ok) throw new Error(`Seedance API error ${resp.status}: ${text.slice(0, 500)}`);
  const data = JSON.parse(text);
  if (!data?.request_id) throw new Error(`No request_id returned: ${text.slice(0, 300)}`);
  return data; // { status: IN_QUEUE, request_id, status_url, response_url }
}

function sizeToResolution(size) {
  if (!size) return undefined;
  const [w, h] = String(size).toLowerCase().split('x').map(Number);
  const long = Math.max(w || 0, h || 0);
  if (long >= 2160) return '4k';
  if (long >= 1080) return '1080p';
  if (long >= 720) return '720p';
  return '480p';
}

function sizeToAspectRatio(size) {
  if (!size) return undefined;
  const [w, h] = String(size).toLowerCase().split('x').map(Number);
  if (!w || !h) return undefined;
  const r = w / h;
  if (r > 2.2) return '21:9';
  if (r > 1.7) return '16:9';
  if (r > 1.2) return '4:3';
  if (r > 0.9) return '1:1';
  if (r > 0.7) return '3:4';
  return '9:16';
}

async function seedanceGetJob(requestId) {
  const resp = await fetch(`${ROOT_BASE}/queue/bytedance/seedance-2.5/requests/${requestId}/status`, {
    headers: { 'Authorization': `Key ${CFG.apiKey}` },
  });
  const text = await resp.text();
  if (!resp.ok) throw new Error(`Seedance status error ${resp.status}: ${text.slice(0, 500)}`);
  return JSON.parse(text);
}

// --- Kling / Sora (OpenAI-style /videos) ------------------------------------
async function videosCreateJob({ model, prompt, seconds, size, mode, imageList, videoList }) {
  const body = { model: model || DEFAULT_MODEL, prompt };
  if (seconds) body.seconds = String(seconds);
  if (size) body.size = size;
  if (mode) body.mode = mode;
  if (imageList?.length) body.image_list = imageList;
  if (videoList?.length) body.video_list = videoList;

  const resp = await fetch(`${CFG.baseURL}/videos`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${CFG.apiKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const text = await resp.text();
  if (!resp.ok) throw new Error(`Video API error ${resp.status}: ${text.slice(0, 500)}`);
  const data = JSON.parse(text);
  if (!data?.id) throw new Error(`No video job id returned: ${text.slice(0, 300)}`);
  return data; // { id, status: queued, ... }
}

async function videosGetJob(jobId) {
  const resp = await fetch(`${CFG.baseURL}/videos/${jobId}`, {
    headers: { 'Authorization': `Bearer ${CFG.apiKey}` },
  });
  const text = await resp.text();
  if (!resp.ok) throw new Error(`Video status error ${resp.status}: ${text.slice(0, 500)}`);
  return JSON.parse(text);
}

// --- Unified polling --------------------------------------------------------
// Returns the final job object (backend-specific shape).
async function pollUntilDone({ requestId, isSeedance, pollIntervalMs, pollTimeoutMs }) {
  const deadline = Date.now() + pollTimeoutMs;
  while (Date.now() < deadline) {
    const job = isSeedance ? await seedanceGetJob(requestId) : await videosGetJob(requestId);
    const status = job?.status;
    if (isSeedance) {
      if (status === 'COMPLETED') return job;
      if (status === 'FAILED') {
        const d = job?.detail;
        throw new Error(`Seedance generation FAILED: ${JSON.stringify(d) || 'unknown'}`);
      }
    } else {
      if (status === 'completed') return job;
      if (status === 'failed' || status === 'cancelled') {
        const err = job?.error;
        throw new Error(`Video generation ${status}: ${err?.message || 'unknown'} (code: ${err?.code || '-'})`);
      }
    }
    await new Promise((r) => setTimeout(r, pollIntervalMs));
  }
  throw new Error(`Video generation timed out after ${Math.round(pollTimeoutMs / 1000)}s (job ${requestId})`);
}

function extractVideoUrls(job, isSeedance) {
  if (isSeedance) {
    const v = job?.result?.video;
    if (!v?.url) return [];
    return [{ url: v.url, duration: v.duration }];
  }
  return (job?.task_result?.videos || []).map((v) => ({ url: v.url, duration: v.duration }));
}

async function downloadBytes(url, outDir, filename, index) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Download failed: HTTP ${resp.status}`);
  const buf = Buffer.from(await resp.arrayBuffer());
  const name = filename ? (index === 0 ? filename : `${path.parse(filename).name}_${index}${path.parse(filename).ext}`) : `video_${Date.now()}_${index}.mp4`;
  const filePath = path.resolve(outDir || DEFAULT_OUT_DIR, name);
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, buf);
  return { path: filePath, size: buf.length };
}

// --- MCP server -------------------------------------------------------------
const server = new McpServer(
  { name: 'video-gen-mcp', version: '2.0.0' },
  { capabilities: { tools: {} } },
);

server.tool(
  'video_gen',
  'Generate a video from a text prompt (text-to-video) or from reference images/clips (image/video-to-video) by calling a video-generation model. Submits an async job, polls until complete, downloads the resulting MP4 to disk, and returns its absolute path. Use this to create videos from a description.',
  {
    prompt: z.string().describe('Detailed text description of the video to generate. Include scene, action, style, lighting, mood. Max 2500 chars.'),
    model: z.string().optional().describe(`Video model id. Seedance ids (e.g. "doubao-seedance-2.5", "bytedance/doubao-seedance-2-5-260628", "byteplus/dreamina-seedance-2-5-260628") route to the Fal queue; "kling-video-o1"/"sora-*" route to /videos. Default: ${DEFAULT_MODEL}`),
    seconds: z.string().optional().describe('Video duration in seconds (string). Kling: 5/10. Seedance 2.5: 4-30. Default: model-dependent.'),
    size: z.string().optional().describe('Resolution "WxH", e.g. 1920x1080, 1080x1920, 1280x720, 1080x1080. Mapped to resolution/aspect_ratio for Seedance.'),
    resolution: z.string().optional().describe('Seedance only: 480p/720p (2.5), or 480p/720p/1080p/4k (2.0). Overrides size-derived value.'),
    aspectRatio: z.string().optional().describe('Seedance only: 21:9, 16:9, 4:3, 1:1, 3:4, 9:16. Overrides size-derived value.'),
    mode: z.string().optional().describe('Kling only: std=720P, pro=1080P. Ignored for Seedance.'),
    generateAudio: z.boolean().optional().describe('Seedance only: whether to generate synchronized audio.'),
    outDir: z.string().optional().describe(`Directory to save the video into. Default: ${DEFAULT_OUT_DIR}`),
    filename: z.string().optional().describe('Optional filename (e.g. cicada.mp4). Auto-generated if omitted.'),
    imageUrls: z.array(z.string()).optional().describe('Optional reference images (public URL or raw base64) for image-to-video.'),
    videoUrls: z.array(z.string()).optional().describe('Optional reference video URLs (MP4/MOV) for video-to-video.'),
    pollIntervalMs: z.number().int().positive().optional().describe('Poll interval in ms. Default: 10000'),
    pollTimeoutMs: z.number().int().positive().optional().describe('Max wait in ms before timing out. Default: 900000 (15 min)'),
  },
  async (args) => {
    if (!args.prompt) throw new Error('Missing required argument: prompt');

    const model = args.model || DEFAULT_MODEL;
    const useSeedance = isSeedanceModel(model);
    const pollInterval = args.pollIntervalMs || DEFAULT_POLL_INTERVAL_MS;
    const pollTimeout = args.pollTimeoutMs || DEFAULT_POLL_TIMEOUT_MS;

    let requestId;
    let createdText;
    if (useSeedance) {
      const job = await seedanceCreateJob(args);
      requestId = job.request_id;
      createdText = `Seedance job created: ${requestId} (status=${job.status}, queue_position=${job.queue_position ?? '-'})`;
    } else {
      const imageList = args.imageUrls?.length ? args.imageUrls.map((url) => ({ image: url })) : undefined;
      const videoList = args.videoUrls?.length ? args.videoUrls.map((url) => ({ video_url: url, refer_type: 'base', keep_original_sound: 'no' })) : undefined;
      const job = await videosCreateJob({ model, ...args, imageList, videoList });
      requestId = job.id;
      createdText = `Video job created: ${job.id} (model=${job.model}, status=${job.status}, size=${job.size ?? '-'}, seconds=${job.seconds ?? '-'})`;
    }

    const finished = await pollUntilDone({ requestId, isSeedance: useSeedance, pollIntervalMs: pollInterval, pollTimeoutMs: pollTimeout });
    const videos = extractVideoUrls(finished, useSeedance);
    if (!videos.length) throw new Error('Job completed but no video URL returned');

    const saved = [];
    for (let i = 0; i < videos.length; i++) {
      const file = await downloadBytes(videos[i].url, args.outDir || DEFAULT_OUT_DIR, args.filename, i);
      saved.push({ path: file.path, size: file.size, duration: videos[i].duration });
    }

    const lines = [
      createdText,
      `Generated ${saved.length} video(s):`,
      ...saved.map((f) => `- ${f.path} (${f.size} bytes, ${f.duration ?? '?'}s)`),
      'Note: the remote URL expires after 7 days; the local copy persists.',
    ];
    return { content: [{ type: 'text', text: lines.join('\n') }] };
  },
);

const transport = new StdioServerTransport();
await server.connect(transport);
console.error('[video-gen-mcp] connected');

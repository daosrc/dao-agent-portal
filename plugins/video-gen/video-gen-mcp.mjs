#!/usr/bin/env node
// Video Generation MCP Server — stdio (official @modelcontextprotocol/sdk)
// Exposes a `video_gen` tool that calls the Modelink (Qiniu) video-generation API,
// polls the async job until completion, downloads the resulting MP4(s) to disk,
// and returns their absolute paths.
//
// Two backends are supported and auto-selected by model id:
//   1. Seedance (Doubao/Dreamina) -> Fal queue: POST /queue/{variant}/{route}
//      Auth: `Authorization: Key {api_key}` (NOT Bearer)
//      Variants: bytedance/seedance-2.0/mini, bytedance/seedance-2.0, bytedance/seedance-2.5
//      Routes:   text-to-video, image-to-video, reference-to-video
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
const DEFAULT_MODEL = process.env.VIDEO_GEN_MODEL || 'bytedance/doubao-seedance-2-0-mini-260615';
const DEFAULT_OUT_DIR = process.env.VIDEO_GEN_OUT_DIR || path.join(os.homedir(), 'Downloads');
const DEFAULT_POLL_INTERVAL_MS = 10000;
const DEFAULT_POLL_TIMEOUT_MS = 900000; // 15 min
const SEEDANCE_DEFAULT_RESOLUTION = '720p';

// --- Model routing ----------------------------------------------------------
// Fal-queue variants of the Seedance family. `path` is the queue segment after /queue/.
// Capability values mirror the Modelink OpenAPI spec (docs.modelink.ai/openapi.json).
const SEEDANCE_VARIANTS = {
  '2.0-mini': {
    label: 'Seedance 2.0 Mini',
    path: 'bytedance/seedance-2.0/mini',
    resolutions: ['480p', '720p'],
    minDuration: 4,
    maxDuration: 15,
  },
  '2.0-fast': {
    label: 'Seedance 2.0 Fast',
    path: 'bytedance/seedance-2.0/fast',
    resolutions: ['480p', '720p'],
    minDuration: 4,
    maxDuration: 15,
  },
  '2.0': {
    label: 'Seedance 2.0',
    path: 'bytedance/seedance-2.0',
    resolutions: ['480p', '720p', '1080p', '4k'],
    minDuration: 4,
    maxDuration: 15,
  },
  '2.5': {
    label: 'Seedance 2.5',
    path: 'bytedance/seedance-2.5',
    resolutions: ['480p', '720p', '1080p'],
    minDuration: 4,
    maxDuration: 30,
  },
};

function isSeedanceModel(model = '') {
  const m = model.toLowerCase();
  return m.includes('seedance') || m.includes('dreamina');
}

// Resolve a model id to a Seedance variant key, or null when the model is not Seedance.
function seedanceVariant(model = '') {
  if (!isSeedanceModel(model)) return null;
  const m = model.toLowerCase();
  if (/2[-_. ]?0[-_. ]?mini/.test(m)) return '2.0-mini';
  if (/2[-_. ]?0[-_. ]?(fast|turbo)/.test(m)) return '2.0-fast';
  if (/2[-_. ]?5/.test(m)) return '2.5';
  if (/2[-_. ]?0/.test(m)) return '2.0';
  return '2.5'; // bare `doubao-seedance` / `dreamina-seedance`
}

// --- Seedance (Fal queue) ---------------------------------------------------
const SEEDANCE_ROUTES = ['text-to-video', 'image-to-video', 'reference-to-video'];

// Choose the queue route from the supplied inputs, unless the caller forces one.
function seedanceRoute({ imageUrls = [], videoUrls = [], requested = 'auto' } = {}) {
  const imgs = imageUrls.filter(Boolean);
  const vids = videoUrls.filter(Boolean);
  if (requested && requested !== 'auto') return requested;
  if (vids.length) return 'reference-to-video';
  if (imgs.length >= 3) return 'reference-to-video';
  if (imgs.length) return 'image-to-video'; // 1 = first frame, 2 = first + last frame
  return 'text-to-video';
}

// Resolution class is set by the short side: 1280x720 = 720p, 1920x1080 = 1080p, 1080x1080 = 1080p.
function sizeToResolution(size) {
  if (!size) return undefined;
  const [w, h] = String(size).toLowerCase().split('x').map(Number);
  const short = Math.min(w || 0, h || 0);
  if (short >= 2160) return '4k';
  if (short >= 1080) return '1080p';
  if (short >= 720) return '720p';
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

// Snap a requested resolution down (then up) to one the variant supports.
function clampResolution(res, allowed) {
  if (!res) return undefined;
  const r = String(res).toLowerCase();
  if (allowed.includes(r)) return r;
  const order = ['480p', '720p', '1080p', '4k'];
  const want = order.indexOf(r);
  if (want === -1) return undefined;
  for (let i = want - 1; i >= 0; i--) if (allowed.includes(order[i])) return order[i];
  for (let i = want + 1; i < order.length; i++) if (allowed.includes(order[i])) return order[i];
  return undefined;
}

function clampDuration(seconds, { minDuration, maxDuration }) {
  if (seconds == null || seconds === '') return undefined;
  const s = String(seconds).trim().toLowerCase();
  if (s === 'auto') return 'auto';
  const n = Number(s);
  if (!Number.isFinite(n)) return undefined;
  return String(Math.min(maxDuration, Math.max(minDuration, Math.round(n))));
}

async function seedanceCreateJob(args) {
  const variantKey = seedanceVariant(args.model) || '2.5';
  const variant = SEEDANCE_VARIANTS[variantKey];
  const route = seedanceRoute({ imageUrls: args.imageUrls, videoUrls: args.videoUrls, requested: args.seedanceMode });
  const imgs = (args.imageUrls || []).filter(Boolean);
  const vids = (args.videoUrls || []).filter(Boolean);

  if (route === 'image-to-video' && !imgs.length) {
    throw new Error('image-to-video requires imageUrls (1 = first frame, 2 = first + last frame)');
  }
  if (route === 'reference-to-video' && !imgs.length && !vids.length) {
    throw new Error('reference-to-video requires imageUrls or videoUrls');
  }

  const resolution = clampResolution(args.resolution, variant.resolutions)
    || clampResolution(sizeToResolution(args.size), variant.resolutions)
    || SEEDANCE_DEFAULT_RESOLUTION;
  const duration = clampDuration(args.seconds, variant);

  const body = { prompt: args.prompt, resolution };
  if (duration) body.duration = duration;
  const ar = args.aspectRatio || sizeToAspectRatio(args.size);
  if (ar) body.aspect_ratio = ar;
  if (args.generateAudio != null) body.generate_audio = !!args.generateAudio;

  if (route === 'image-to-video') {
    body.image_url = imgs[0];
    if (imgs[1]) body.end_image_url = imgs[1];
  } else if (route === 'reference-to-video') {
    if (imgs.length) body.image_urls = imgs.slice(0, 9);
    if (vids.length) body.video_urls = vids.slice(0, 3);
  }

  const url = `${ROOT_BASE}/queue/${variant.path}/${route}`;
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Authorization': `Key ${CFG.apiKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const text = await resp.text();
  if (!resp.ok) throw new Error(`Seedance API error ${resp.status}: ${text.slice(0, 500)}`);
  const data = JSON.parse(text);
  if (!data?.request_id) throw new Error(`No request_id returned: ${text.slice(0, 300)}`);
  return {
    job: data,
    meta: { variant: variantKey, variantLabel: variant.label, route, resolution, duration, queuePath: variant.path, url },
  };
}

// The create response carries an absolute status_url; fall back to the conventional path.
async function seedanceGetJob({ statusUrl, requestId, queuePath }) {
  const url = statusUrl || `${ROOT_BASE}/queue/${queuePath}/requests/${requestId}/status`;
  const resp = await fetch(url, {
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
async function pollUntilDone({ requestId, isSeedance, queuePath, statusUrl, pollIntervalMs, pollTimeoutMs }) {
  const deadline = Date.now() + pollTimeoutMs;
  while (Date.now() < deadline) {
    const job = isSeedance
      ? await seedanceGetJob({ statusUrl, requestId, queuePath })
      : await videosGetJob(requestId);
    const status = job?.status;
    if (isSeedance) {
      if (status === 'FAILED') {
        const d = job?.detail;
        throw new Error(`Seedance generation FAILED: ${d?.msg || JSON.stringify(d) || 'unknown'}`);
      }
      // The Fal queue also reports COMPLETED for failed jobs — the reason is in `detail`.
      if (status === 'COMPLETED') {
        if (job?.detail?.msg) throw new Error(`Seedance generation FAILED: ${job.detail.msg}`);
        return job;
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
  { name: 'video-gen-mcp', version: '2.1.0' },
  { capabilities: { tools: {} } },
);

server.tool(
  'video_gen',
  'Generate a video from a text prompt (text-to-video) or from reference images/clips (image/video-to-video) by calling a video-generation model. Submits an async job, polls until complete, downloads the resulting MP4 to disk, and returns its absolute path. Use this to create videos from a description.',
  {
    prompt: z.string().describe('Detailed text description of the video to generate. Include scene, action, style, lighting, mood. Max 2500 chars.'),
    model: z.string().optional().describe(`Video model id. Seedance ids ("bytedance/doubao-seedance-2-0-mini-260615", "doubao-seedance-2.0", "doubao-seedance-2.5", "byteplus/dreamina-seedance-2-5-260628") route to the Fal queue; "kling-video-o1"/"sora-*" route to /videos. Default: ${DEFAULT_MODEL}`),
    seconds: z.string().optional().describe('Video duration in seconds (string). Kling: 5/10. Seedance: 4-15 (2.0 Mini, 2.0 Fast, 2.0) or 4-30 (2.5), or "auto". Out-of-range values are clamped to the model range.'),
    size: z.string().optional().describe('Resolution "WxH", e.g. 1920x1080, 1080x1920, 1280x720, 1080x1080. Mapped to resolution/aspect_ratio for Seedance.'),
    resolution: z.string().optional().describe('Seedance only: 480p/720p (2.0 Mini, 2.0 Fast) or 480p/720p/1080p/4k (2.0) or 480p/720p/1080p (2.5); clamped to what the model supports. Overrides size-derived value.'),
    aspectRatio: z.string().optional().describe('Seedance only: 21:9, 16:9, 4:3, 1:1, 3:4, 9:16. Overrides size-derived value.'),
    seedanceMode: z.enum(['auto', ...SEEDANCE_ROUTES]).optional().describe('Seedance only: force the Fal queue route. "auto" (default) picks from imageUrls/videoUrls: none = text-to-video, 1 image = first frame, 2 images = first + last frame, >=3 images or any videoUrl = multi-reference.'),
    mode: z.string().optional().describe('Kling only: std=720P, pro=1080P. Ignored for Seedance.'),
    generateAudio: z.boolean().optional().describe('Seedance only: whether to generate synchronized audio.'),
    outDir: z.string().optional().describe(`Directory to save the video into. Default: ${DEFAULT_OUT_DIR}`),
    filename: z.string().optional().describe('Optional filename (e.g. cicada.mp4). Auto-generated if omitted.'),
    imageUrls: z.array(z.string()).optional().describe('Optional reference images (public URL or raw base64). Seedance: 1 = first frame, 2 = first + last frame, >=3 = multi-reference (max 9).'),
    videoUrls: z.array(z.string()).optional().describe('Optional reference video URLs (MP4/MOV). Seedance: switches to multi-reference (max 3).'),
    pollIntervalMs: z.number().int().positive().optional().describe('Poll interval in ms. Default: 10000'),
    pollTimeoutMs: z.number().int().positive().optional().describe('Max wait in ms before timing out. Default: 900000 (15 min)'),
  },
  async (args) => {
    if (!args.prompt) throw new Error('Missing required argument: prompt');

    const model = args.model || DEFAULT_MODEL;
    const useSeedance = !!seedanceVariant(model);
    const pollInterval = args.pollIntervalMs || DEFAULT_POLL_INTERVAL_MS;
    const pollTimeout = args.pollTimeoutMs || DEFAULT_POLL_TIMEOUT_MS;

    let requestId;
    let createdText;
    let queuePath;
    let statusUrl;
    if (useSeedance) {
      const { job, meta } = await seedanceCreateJob({ ...args, model });
      requestId = job.request_id;
      queuePath = meta.queuePath;
      statusUrl = job.status_url;
      createdText = `Seedance ${meta.variantLabel} job created: ${requestId} (route=${meta.route}, resolution=${meta.resolution}, duration=${meta.duration ?? 'auto'}, status=${job.status}, queue_position=${job.queue_position ?? '-'})`;
    } else {
      const imageList = args.imageUrls?.length ? args.imageUrls.map((url) => ({ image: url })) : undefined;
      const videoList = args.videoUrls?.length ? args.videoUrls.map((url) => ({ video_url: url, refer_type: 'base', keep_original_sound: 'no' })) : undefined;
      const job = await videosCreateJob({ model, ...args, imageList, videoList });
      requestId = job.id;
      createdText = `Video job created: ${job.id} (model=${job.model}, status=${job.status}, size=${job.size ?? '-'}, seconds=${job.seconds ?? '-'})`;
    }

    const finished = await pollUntilDone({ requestId, isSeedance: useSeedance, queuePath, statusUrl, pollIntervalMs: pollInterval, pollTimeoutMs: pollTimeout });
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
    ];
    const tokens = finished?.result?.usage?.total_tokens;
    if (useSeedance && tokens != null) lines.push(`Seedance usage: ${tokens} tokens.`);
    lines.push('Note: the remote URL expires after 7 days; the local copy persists.');
    return { content: [{ type: 'text', text: lines.join('\n') }] };
  },
);

const transport = new StdioServerTransport();
await server.connect(transport);
console.error('[video-gen-mcp] connected');

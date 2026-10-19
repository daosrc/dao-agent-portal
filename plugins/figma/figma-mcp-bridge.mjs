#!/usr/bin/env node
// Figma MCP Bridge — wraps Figma Desktop MCP (Streamable HTTP) as stdio MCP server
// Uses official @modelcontextprotocol/sdk for reliable handshaking with opencode.

import http from 'node:http';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';

const FIGMA_MCP_URL = process.env.FIGMA_MCP_URL || 'http://127.0.0.1:3845/mcp';
const { hostname, port, pathname } = new URL(FIGMA_MCP_URL);

// --- Minimal Figma Desktop MCP HTTP client ----------------------------------
class FigmaClient {
  #sessionId = null;

  async init() {
    const { headers, body } = await this.#request(
      { jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'figma-bridge', version: '2.0' } } },
      10000,
    );
    this.#sessionId = headers['mcp-session-id'];
    return body;
  }

  async method(name, params = {}, timeout = 180000) {
    return this.#request({ jsonrpc: '2.0', id: Date.now(), method: name, params }, timeout);
  }

  async call(name, args = {}, timeout = 180000) {
    return this.#request({ jsonrpc: '2.0', id: Date.now(), method: 'tools/call', params: { name, arguments: args } }, timeout);
  }

  #request(body, timeout) {
    return new Promise((resolve, reject) => {
      const headers = { 'Accept': 'application/json, text/event-stream', 'Content-Type': 'application/json' };
      if (this.#sessionId) headers['mcp-session-id'] = this.#sessionId;
      const req = http.request({ hostname, port, path: pathname, method: 'POST', headers, timeout }, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          let parsed;
          for (const line of data.split('\n')) {
            if (line.startsWith('data: ')) { try { parsed = JSON.parse(line.slice(6)); } catch {} }
          }
          if (!parsed) { try { parsed = JSON.parse(data); } catch {} }
          resolve({ headers: res.headers, body: parsed || { error: { code: -32603, message: 'Parse failed' } } });
        });
      });
      req.on('error', reject);
      req.on('timeout', () => { req.destroy(); reject(new Error('Timeout')); });
      req.write(JSON.stringify(body));
      req.end();
    });
  }
}

let figmaPromise = null;

function getFigma() {
  if (!figmaPromise) {
    figmaPromise = (async () => {
      const c = new FigmaClient();
      await c.init();
      return c;
    })().catch((err) => { figmaPromise = null; throw err; });
  }
  return figmaPromise;
}

async function listFigmaTools() {
  const figma = await getFigma();
  const res = await figma.method('tools/list');
  const tools = res.body?.result?.tools ?? [];
  return tools;
}

// --- MCP server (stdio) -----------------------------------------------------
const server = new McpServer(
  { name: 'figma-bridge', version: '2.0.0' },
  { capabilities: { tools: {} } },
);

// Lazy tool registry: tools are resolved from the Figma Desktop MCP at first call.
let cachedTools = null;

async function ensureTools() {
  if (cachedTools) return cachedTools;
  const figmaTools = await listFigmaTools();
  cachedTools = figmaTools;
  return cachedTools;
}

// Register a dynamic tool that forwards to Figma. Because the SDK's McpServer
// requires a fixed schema at registration time, we register one generic tool
// per figma tool discovered; if discovery fails, we expose a fallback probe.
async function registerDynamicTools() {
  let figmaTools = [];
  try {
    figmaTools = await listFigmaTools();
  } catch (err) {
    console.error(`[figma-bridge] Could not reach Figma Desktop MCP: ${err.message}`);
    figmaTools = [];
  }
  cachedTools = figmaTools;

  if (figmaTools.length === 0) {
    // Fallback: expose a single tool so opencode sees a healthy server,
    // and use it to report the Figma connection status.
    server.tool(
      'figma_status',
      'Check whether the Figma Desktop MCP server is reachable. Returns connection status and the list of tools Figma exposes when available.',
      { _probe: z.string().optional().describe('Ignored. Used only to expose a tool when Figma is offline.') },
      async () => {
        let msg;
        try {
          const tools = await listFigmaTools();
          msg = `Figma Desktop MCP reachable. Exposed tools: ${tools.map(t => t.name).join(', ') || '(none)'}`;
        } catch (err) {
          msg = `Figma Desktop MCP NOT reachable at ${FIGMA_MCP_URL}: ${err.message}`;
        }
        return { content: [{ type: 'text', text: msg }] };
      },
    );
    return;
  }

  for (const t of figmaTools) {
    const name = t.name.includes('.') ? t.name.split('.').pop() : t.name;
    const schema = t.inputSchema || { type: 'object', properties: {}, required: [] };
    registerPassthrough(name, t.description || '', schema);
  }
}

function registerPassthrough(name, description, jsonSchema) {
  // Convert a JSON Schema object into a Zod schema so the SDK accepts it.
  const props = jsonSchema.properties || {};
  const required = jsonSchema.required || [];
  const shape = {};
  for (const [key, prop] of Object.entries(props)) {
    let field;
    switch (prop.type) {
      case 'string': field = { type: 'string' }; break;
      case 'number': field = { type: 'number' }; break;
      case 'integer': field = { type: 'number' }; break;
      case 'boolean': field = { type: 'boolean' }; break;
      case 'array': field = { type: 'array', items: { type: 'string' } }; break;
      case 'object': field = { type: 'object' }; break;
      default: field = { type: 'string' };
    }
    const f = { ...field };
    if (Array.isArray(prop.enum) && prop.enum.length) {
      f.enum = prop.enum;
    }
    if (prop.description) f.description = prop.description;
    shape[key] = f;
  }
  const zodShape = {};
  for (const [key, f] of Object.entries(shape)) {
    const requiredFlag = required.includes(key);
    let zf;
    const { type, items, enum: enums, description } = f;
    if (type === 'string') {
      zf = enums ? z.enum(enums) : z.string();
    } else if (type === 'number') {
      zf = z.number();
    } else if (type === 'boolean') {
      zf = z.boolean();
    } else if (type === 'array') {
      zf = z.array(z.string());
    } else if (type === 'object') {
      zf = z.record(z.string(), z.unknown());
    } else {
      zf = z.string();
    }
    if (description) zf = zf.describe(description);
    zodShape[key] = requiredFlag ? zf : zf.optional();
  }

  server.tool(
    name,
    description,
    zodShape,
    async (args) => {
      const figma = await getFigma();
      const res = await figma.call(name, args || {});
      const result = res.body?.result ?? res.body;
      // Return whatever Figma returned. If it already has content, forward as-is.
      if (result && typeof result === 'object' && Array.isArray(result.content)) {
        return result;
      }
      return { content: [{ type: 'text', text: JSON.stringify(result ?? {}) }] };
    },
  );
}

async function main() {
  await registerDynamicTools();
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('[figma-bridge] connected');
}

main().catch((err) => { console.error('Fatal:', err); process.exit(1); });
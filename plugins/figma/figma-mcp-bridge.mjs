#!/usr/bin/env node
// Figma MCP Bridge — wraps Figma Desktop MCP (Streamable HTTP) as stdio MCP server

import http from 'node:http';

const FIGMA_MCP_URL = process.env.FIGMA_MCP_URL || 'http://127.0.0.1:3845/mcp';
const { hostname, port, pathname } = new URL(FIGMA_MCP_URL);

class FigmaClient {
  #sessionId = null;

  async init() {
    const res = await this.#request({ jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2024-11-05', capabilities: {}, clientInfo: { name: 'figma-bridge', version: '1.0' } } }, 10000);
    this.#sessionId = res.headers['mcp-session-id'];
    return res.body;
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
          // Try SSE format first (event: message\ndata: {...}), then plain JSON
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

let figma;

function readStdinMessage() {
  return new Promise((resolve) => {
    let buf = '';
    process.stdin.setEncoding('utf-8');
    process.stdin.on('data', (chunk) => {
      buf += chunk;
      // Split on newlines — each segment after an empty Content-Length separator
      // OR a raw JSON line (no Content-Length)
      let parsed = false;
      while (buf.includes('\n') && !parsed) {
        // Check for Content-Length header format first
        const contentLenMatch = buf.match(/^Content-Length:\s*(\d+)\r?\n\r?\n/);
        if (contentLenMatch) {
          const len = parseInt(contentLenMatch[1], 10);
          const headerEnd = contentLenMatch[0].length;
          if (Buffer.byteLength(buf.slice(headerEnd), 'utf-8') >= len) {
            const bodyStr = buf.slice(headerEnd, headerEnd + len);
            buf = buf.slice(headerEnd + len);
            try { resolve(JSON.parse(bodyStr)); parsed = true; } catch { resolve(null); parsed = true; }
          }
          break;
        }
        // No Content-Length header — try raw JSON line
        const idx = buf.indexOf('\n');
        const line = buf.slice(0, idx).trim();
        buf = buf.slice(idx + 1);
        if (!line) continue;
        if (line[0] === '{' || line[0] === '[') {
          try { resolve(JSON.parse(line)); parsed = true; } catch { /* not valid JSON, skip */ }
        }
      }
    });
  });
}

function send(msg) {
  const json = JSON.stringify(msg);
  const len = Buffer.byteLength(json, 'utf-8');
  process.stdout.write(`Content-Length: ${len}\r\n\r\n${json}`);
}

async function main() {
  while (true) {
    const msg = await readStdinMessage();
    if (!msg || !msg.method) { send({ jsonrpc: '2.0', error: { code: -32600, message: 'Invalid message' } }); continue; }

    const { id, method, params } = msg;
    try {
      switch (method) {
        case 'initialize':
          figma = new FigmaClient();
          const initResult = await figma.init();
          send({ jsonrpc: '2.0', id, result: initResult.result });
          break;

        case 'notifications/initialized':
          break;

        case 'tools/list':
        case 'tools/call':
        case 'resources/list':
        case 'prompts/list': {
          if (method === 'tools/call') {
            const toolName = params.name.includes('.') ? params.name.split('.').pop() : params.name;
            const result = await figma.call(toolName, params.arguments);
            send({ jsonrpc: '2.0', id, result: result.body.result || result.body });
          } else {
            const result = await figma.method(method, params);
            send({ jsonrpc: '2.0', id, result: result.body.result || result.body });
          }
          break;
        }

        default:
          send({ jsonrpc: '2.0', id, error: { code: -32601, message: `Unknown: ${method}` } });
      }
    } catch (err) {
      send({ jsonrpc: '2.0', id, error: { code: -32603, message: err.message } });
    }
  }
}

main().catch((err) => { console.error('Fatal:', err); process.exit(1); });

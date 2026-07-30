#!/usr/bin/env node
// Figma MCP Bridge — wraps Figma Dev Mode MCP (SSE) as stdio MCP server
// Add to opencode.json mcp section:
//   "figma-bridge": { "type": "local", "command": ["node", "/path/to/figma-mcp-bridge.mjs"], "enabled": true }

import http from 'node:http';
import { EOL } from 'node:os';

const FIGMA_MCP_URL = process.env.FIGMA_MCP_URL || 'http://127.0.0.1:3845/mcp';
const { hostname, port, pathname } = new URL(FIGMA_MCP_URL);

class FigmaSSEClient {
  #sessionId = null;

  async init() {
    const { headers, body } = await this.#post({
      jsonrpc: '2.0', id: 1, method: 'initialize',
      params: { protocolVersion: '2024-11-05', capabilities: {}, clientInfo: { name: 'figma-bridge', version: '1.0' } }
    }, 10000);
    this.#sessionId = headers['mcp-session-id'];
    if (!this.#sessionId) throw new Error(`No session: ${JSON.stringify(headers)}`);
    for (const line of body.split('\n')) {
      if (line.startsWith('data: ')) return JSON.parse(line.slice(5));
    }
    throw new Error('No data in init response');
  }

  async call(name, args = {}, timeout = 180000) {
    const { body } = await this.#post({
      jsonrpc: '2.0', id: Date.now(), method: 'tools/call',
      params: { name, arguments: args }
    }, timeout);
    for (const line of body.split('\n')) {
      if (line.startsWith('data: ')) return JSON.parse(line.slice(5));
    }
    throw new Error('No data in tool response');
  }

  #post(body, timeout) {
    return new Promise((resolve, reject) => {
      const headers = { 'Accept': 'text/event-stream, application/json', 'Content-Type': 'application/json' };
      if (this.#sessionId) headers['mcp-session-id'] = this.#sessionId;
      const req = http.request({ hostname, port, path: pathname, method: 'POST', headers, timeout }, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => resolve({ headers: res.headers, body: data }));
      });
      req.on('error', reject);
      req.on('timeout', () => { req.destroy(); reject(new Error('Timeout')); });
      req.write(JSON.stringify(body));
      req.end();
    });
  }
}

let figma;

// MCP stdio protocol: read one JSON-RPC message from stdin
function readStdinMessage() {
  return new Promise((resolve) => {
    let contentLength = 0;
    let buf = '';

    process.stdin.on('data', (chunk) => {
      buf += chunk.toString();
      // Try to parse headers
      while (buf.includes('\n')) {
        const idx = buf.indexOf('\n');
        const line = buf.slice(0, idx).trim();
        buf = buf.slice(idx + 1);

        if (line.startsWith('Content-Length:')) {
          contentLength = parseInt(line.slice(15).trim(), 10);
        } else if (line === '') {
          // End of headers, read body
          if (contentLength > 0 && Buffer.byteLength(buf, 'utf-8') >= contentLength) {
            const bodyStr = buf.slice(0, contentLength);
            buf = buf.slice(contentLength);
            try { resolve(JSON.parse(bodyStr)); } catch { resolve(null); }
            return;
          }
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
          figma = new FigmaSSEClient();
          const initResult = await figma.init();
          send({ jsonrpc: '2.0', id, result: initResult.result });
          break;
        case 'notifications/initialized':
          break;
        case 'tools/list':
          send({ jsonrpc: '2.0', id, result: { tools: [
            { name: 'get_screenshot', description: 'Get screenshot of a Figma node', inputSchema: { type: 'object', properties: { node_id: { type: 'string' }, figma_file_key: { type: 'string' } }, required: ['node_id', 'figma_file_key'] } },
            { name: 'get_metadata', description: 'Get metadata of a Figma node', inputSchema: { type: 'object', properties: { node_id: { type: 'string' }, figma_file_key: { type: 'string' } }, required: ['node_id', 'figma_file_key'] } },
            { name: 'get_design_context', description: 'Get design context (generated code, tokens) for a Figma node', inputSchema: { type: 'object', properties: { node_id: { type: 'string' }, figma_file_key: { type: 'string' }, disable_code_connect: { type: 'boolean' } }, required: ['node_id', 'figma_file_key'] } },
          ]}});
          break;
        case 'tools/call': {
          const toolName = params.name.includes('.') ? params.name.split('.').pop() : params.name;
          const args = params.arguments || {};
          const result = await figma.call(toolName, args);
          send({ jsonrpc: '2.0', id, result: result.result || result });
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

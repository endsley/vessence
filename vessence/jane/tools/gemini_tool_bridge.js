#!/usr/bin/env node
/**
 * gemini_tool_bridge.js — Lightweight HTTP server that executes coding tools.
 * Called by the Python Gemini API brain when function calls are returned.
 *
 * Runs on a configurable port (default 7799). Accepts POST requests:
 *   POST /execute { "tool": "read_file", "args": { "file_path": "..." } }
 *   → { "result": "file contents..." }
 *
 * Implements the core tools matching Gemini CLI's built-in set:
 *   read_file, write_file, edit, shell, grep, glob, ls
 */

import { createServer } from 'http';
import { readFileSync, writeFileSync, readdirSync, statSync, existsSync, mkdirSync } from 'fs';
import { execSync, spawn } from 'child_process';
import { resolve, join, dirname, basename, relative } from 'path';

const PORT = parseInt(process.env.TOOL_BRIDGE_PORT || '7799');

// ── Tool Implementations ──────────────────────────────────────────────────

function readFile({ file_path, start_line, end_line }) {
  if (!file_path) return { error: 'file_path is required' };
  try {
    const absPath = resolve(file_path);
    if (!existsSync(absPath)) return { error: `File not found: ${file_path}` };
    const content = readFileSync(absPath, 'utf-8');
    const lines = content.split('\n');
    const start = (start_line || 1) - 1;
    const end = end_line || lines.length;
    const selected = lines.slice(start, end);
    const numbered = selected.map((line, i) => `${start + i + 1}\t${line}`).join('\n');
    return { result: numbered };
  } catch (e) {
    return { error: e.message };
  }
}

function readManyFiles({ paths, include_pattern, exclude_pattern, recursive }) {
  // Simplified: read multiple files by glob or explicit paths
  try {
    const results = {};
    if (paths && Array.isArray(paths)) {
      for (const p of paths) {
        try {
          results[p] = readFileSync(resolve(p), 'utf-8');
        } catch (e) {
          results[p] = `Error: ${e.message}`;
        }
      }
    }
    return { result: JSON.stringify(results, null, 2) };
  } catch (e) {
    return { error: e.message };
  }
}

function writeFile({ file_path, content }) {
  if (!file_path) return { error: 'file_path is required' };
  if (content === undefined || content === null) return { error: 'content is required' };
  try {
    const absPath = resolve(file_path);
    const dir = dirname(absPath);
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
    writeFileSync(absPath, content, 'utf-8');
    return { result: `Written ${content.length} chars to ${file_path}` };
  } catch (e) {
    return { error: e.message };
  }
}

function editFile({ file_path, old_string, new_string, allow_multiple }) {
  if (!file_path) return { error: 'file_path is required' };
  if (!old_string) return { error: 'old_string is required' };
  if (new_string === undefined) return { error: 'new_string is required' };
  try {
    const absPath = resolve(file_path);
    if (!existsSync(absPath)) return { error: `File not found: ${file_path}` };
    let content = readFileSync(absPath, 'utf-8');
    if (!content.includes(old_string)) {
      return { error: `old_string not found in ${file_path}` };
    }
    if (allow_multiple) {
      content = content.replaceAll(old_string, new_string);
    } else {
      content = content.replace(old_string, new_string);
    }
    writeFileSync(absPath, content, 'utf-8');
    return { result: `Edited ${file_path}` };
  } catch (e) {
    return { error: e.message };
  }
}

function runShell({ command, timeout, is_background }) {
  if (!command) return { error: 'command is required' };
  const timeoutMs = (timeout || 120) * 1000;
  try {
    if (is_background) {
      const child = spawn('bash', ['-c', command], {
        detached: true,
        stdio: 'ignore',
      });
      child.unref();
      return { result: `Started background process (pid: ${child.pid})` };
    }
    const result = execSync(command, {
      timeout: timeoutMs,
      encoding: 'utf-8',
      maxBuffer: 10 * 1024 * 1024,
      shell: '/bin/bash',
    });
    return { result: result || '(no output)' };
  } catch (e) {
    if (e.stdout || e.stderr) {
      return {
        result: `Exit code: ${e.status || 'unknown'}\n${e.stdout || ''}\n${e.stderr || ''}`.trim()
      };
    }
    return { error: e.message };
  }
}

function grepSearch({ pattern, dir_path, include_pattern, exclude_pattern, names_only, case_sensitive, max_matches, context_lines }) {
  if (!pattern) return { error: 'pattern is required' };
  try {
    // Try ripgrep first, fall back to grep -r
    const hasRg = (() => { try { execSync('which rg', { encoding: 'utf-8' }); return true; } catch { return false; } })();
    let args;
    if (hasRg) {
      args = ['rg'];
      if (!case_sensitive) args.push('-i');
      if (names_only) args.push('-l');
      if (max_matches) args.push('--max-count', String(max_matches));
      if (context_lines) args.push('-C', String(context_lines));
      if (include_pattern) args.push('--glob', include_pattern);
      if (exclude_pattern) args.push('--glob', `!${exclude_pattern}`);
      args.push('--', pattern);
      if (dir_path) args.push(resolve(dir_path));
    } else {
      args = ['grep', '-rn'];
      if (!case_sensitive) args.push('-i');
      if (names_only) args.push('-l');
      if (max_matches) args.push(`-m${max_matches}`);
      if (context_lines) args.push(`-C${context_lines}`);
      if (include_pattern) args.push(`--include=${include_pattern}`);
      if (exclude_pattern) args.push(`--exclude=${exclude_pattern}`);
      args.push('--', pattern);
      args.push(dir_path ? resolve(dir_path) : '.');
    }

    const result = execSync(args.join(' '), {
      encoding: 'utf-8',
      maxBuffer: 5 * 1024 * 1024,
      timeout: 30000,
      shell: '/bin/bash',
    });
    return { result: result || 'No matches found.' };
  } catch (e) {
    if (e.status === 1) return { result: 'No matches found.' };
    return { result: (e.stdout || '') + (e.stderr || '') || e.message };
  }
}

function globFiles({ pattern, dir_path }) {
  if (!pattern) return { error: 'pattern is required' };
  try {
    const args = ['find'];
    const searchDir = dir_path ? resolve(dir_path) : '.';
    args.push(searchDir, '-name', pattern, '-type', 'f');
    const result = execSync(args.join(' '), {
      encoding: 'utf-8',
      maxBuffer: 2 * 1024 * 1024,
      timeout: 15000,
      shell: '/bin/bash',
    });
    return { result: result || 'No files found.' };
  } catch (e) {
    return { result: e.stdout || e.message };
  }
}

function listDirectory({ dir_path, ignore }) {
  const target = dir_path ? resolve(dir_path) : '.';
  try {
    const entries = readdirSync(target, { withFileTypes: true });
    const lines = entries
      .filter(e => !ignore || !ignore.includes(e.name))
      .map(e => {
        const prefix = e.isDirectory() ? 'd' : '-';
        try {
          const st = statSync(join(target, e.name));
          return `${prefix} ${st.size.toString().padStart(8)} ${e.name}`;
        } catch {
          return `${prefix}        ? ${e.name}`;
        }
      });
    return { result: lines.join('\n') || '(empty directory)' };
  } catch (e) {
    return { error: e.message };
  }
}

// ── Tool Router ───────────────────────────────────────────────────────────

const TOOLS = {
  read_file: readFile,
  read_many_files: readManyFiles,
  write_file: writeFile,
  edit: editFile,
  run_shell_command: runShell,
  shell: runShell,
  grep_search: grepSearch,
  grep: grepSearch,
  search_file_content: grepSearch,
  glob: globFiles,
  find_files: globFiles,
  list_directory: listDirectory,
  ls: listDirectory,
};

// ── HTTP Server ───────────────────────────────────────────────────────────

const server = createServer((req, res) => {
  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', tools: Object.keys(TOOLS) }));
    return;
  }

  if (req.method !== 'POST' || req.url !== '/execute') {
    res.writeHead(404);
    res.end('Not found');
    return;
  }

  let body = '';
  req.on('data', chunk => { body += chunk; });
  req.on('end', () => {
    try {
      const { tool, args } = JSON.parse(body);
      const fn = TOOLS[tool];
      if (!fn) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: `Unknown tool: ${tool}` }));
        return;
      }
      const result = fn(args || {});
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(result));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: e.message }));
    }
  });
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`[tool-bridge] Listening on http://127.0.0.1:${PORT}`);
  console.log(`[tool-bridge] Tools: ${Object.keys(TOOLS).join(', ')}`);
});

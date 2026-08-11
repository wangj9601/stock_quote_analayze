/**
 * 加载 frontend/js/pattern_tool.js 并调用 buildExpertAnalysis。
 * 用法: node test/_pattern_expert_node_check.mjs '<json-items-array>'
 * stdout 最后一行: JSON { shortTerm, mediumTerm, ... }
 */
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const src = fs.readFileSync(path.join(root, 'frontend', 'js', 'pattern_tool.js'), 'utf8');

const sandbox = {
  console,
  document: { addEventListener() {} },
  window: {},
  API_BASE_URL: '',
  authFetch: async () => ({ ok: false }),
  CommonUtils: null,
};
vm.createContext(sandbox);
vm.runInContext(`${src}\nglobalThis.PatternTool = PatternTool;`, sandbox);
const PT = sandbox.PatternTool || sandbox.globalThis?.PatternTool;
if (!PT || typeof PT.buildExpertAnalysis !== 'function') {
  console.error('PatternTool.buildExpertAnalysis not found');
  process.exit(2);
}

const raw = process.argv[2] || '[]';
const items = JSON.parse(raw);
const analysis = PT.buildExpertAnalysis(items);
process.stdout.write(JSON.stringify(analysis) + '\n');

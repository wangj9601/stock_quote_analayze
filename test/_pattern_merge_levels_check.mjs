/**
 * Bug2 自测：近价合并须保留多形态语义标签，不能硬并成单一「颈线」。
 * 用法: node test/_pattern_merge_levels_check.mjs
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
if (!PT || typeof PT._mergeNearLevels !== 'function') {
  console.error('PatternTool._mergeNearLevels not found');
  process.exit(2);
}

const raw = [
  { price: 10.0, name: '颈线', role: '观察站稳', source: '双底', observing: true, confirmed: false, conf: 0.55 },
  { price: 10.05, name: '上沿', role: '突破后转支撑', source: '下降楔形', observing: false, confirmed: true, conf: 0.72 },
  { price: 10.02, name: 'H2', role: '上方压力', source: '双顶', observing: true, confirmed: false, conf: 0.5 },
];

const merged = PT._mergeNearLevels(raw);
if (merged.length !== 1) {
  console.error('expected 1 merged level, got', merged.length, merged);
  process.exit(1);
}
const m = merged[0];
const name = String(m.name || '');
const need = ['双底:颈线', '下降楔形:上沿', '双顶:H2'];
for (const part of need) {
  if (!name.includes(part)) {
    console.error('display name missing', part, 'got', name);
    process.exit(1);
  }
}
if (name === '颈线' || m.primaryName === undefined) {
  console.error('unexpected hard-merge to 颈线 only', m);
  process.exit(1);
}
// role 取最高：突破后转支撑
if (m.role !== '突破后转支撑') {
  console.error('expected role 突破后转支撑, got', m.role);
  process.exit(1);
}

const ref = PT.buildKeyLevelsReference([
  {
    pattern_type: 'double_bottom',
    status: 'forming',
    confidence: 0.55,
    key_levels: { neckline: 10.0, l1: 9.0, l2: 9.05, last_close: 10.5 },
  },
  {
    pattern_type: 'falling_wedge',
    status: 'confirmed',
    confidence: 0.72,
    key_levels: { upper: 10.05, lower: 9.2, last_close: 10.5 },
  },
]);
if (!ref.includes('双底:颈线') || !ref.includes('下降楔形:上沿')) {
  console.error('buildKeyLevelsReference missing multi-source tags:', ref);
  process.exit(1);
}

console.log('OK', JSON.stringify({ name, role: m.role, tags: m.tags, ref }));

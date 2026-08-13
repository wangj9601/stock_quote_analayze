/**
 * P0/P1 自测：已确认上破后空阻力不得写「等待形态边界突破」；
 * 巩固简化测幅 upper+H；形成中仍可「等待突破」。
 * 用法: node test/_pattern_structure_levels_check.mjs
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

function assert(cond, msg) {
  if (!cond) {
    console.error('FAIL:', msg);
    process.exit(1);
  }
}

// —— 本案示例：003043 类下降楔已确认上破，上/下沿均在现价下 ——
const upBreakItems = [
  {
    pattern_type: 'falling_wedge',
    status: 'confirmed',
    confidence: 0.78,
    formed_at: '2026-08-01',
    key_levels: { upper: 71.6, lower: 55.2, last_close: 72.5 },
  },
];
const up = PT.buildExpertAnalysis(upBreakItems);
const upBlob = [up.shortTerm, up.mediumTerm, up.structureText, up.structureHtml].join('\n');
assert(up.shortTerm.includes('上破'), 'shortTerm should state 上破');
assert(!upBlob.includes('等待形态边界突破'), 'up-break must not say 等待形态边界突破');
assert(upBlob.includes('形态边界已上破') || upBlob.includes('简化测幅目标'), 'need up-break empty or measured copy');
assert(upBlob.includes('88.00'), `measured target ~88.00 missing: ${up.structureText}`);
assert(upBlob.includes('按边界高度'), 'must mark 按边界高度');
assert(up.structureHtml && up.structureText, 'structure fields required');
assert(up.structureHtml.includes('结构防守与目标'), 'unified structure label');
assert(!up.mediumTerm.includes('边界上沿/下沿'), 'mediumTerm should not stack bounds');
assert(!up.mediumTerm.includes('现价/收盘参考'), 'mediumTerm should not restack close');

const plain = PT.formatExpertPlainText(up);
assert(plain.includes('结构防守与目标'), 'formatExpertPlainText must include structure');
assert(plain.includes('88.00'), 'plain text must include measured target');

// —— 形成中且现价已在上下沿之上：阻力空档仍用「等待突破」（非已确认）——
const formingItems = [
  {
    pattern_type: 'falling_wedge',
    status: 'forming',
    confidence: 0.6,
    key_levels: { upper: 71.6, lower: 55.2, last_close: 80.0 },
  },
];
const fo = PT.buildExpertAnalysis(formingItems);
assert(
  (fo.structureText || '').includes('等待形态边界突破') ||
    (fo.structureHtml || '').includes('等待形态边界突破'),
  'forming empty-resistance may keep 等待形态边界突破'
);
assert(!(fo.structureText || '').includes('88.00'), 'forming should not emit measured target');
assert(!(fo.structureText || '').includes('形态边界已上破'), 'forming must not use confirmed-up copy');

// —— 已确认下破对称 ——
const downBreakItems = [
  {
    pattern_type: 'rising_wedge',
    status: 'confirmed',
    confidence: 0.7,
    key_levels: { upper: 80.0, lower: 70.0, last_close: 69.0 },
  },
];
const dn = PT.buildExpertAnalysis(downBreakItems);
const dnBlob = [dn.structureText, dn.structureHtml].join('\n');
assert(!dnBlob.includes('等待形态边界突破'), 'down-break must not say 等待形态边界突破 on empty support');
assert(dnBlob.includes('60.00'), `down measured lower-H ~60.00 missing: ${dn.structureText}`);
assert(dnBlob.includes('形态边界已下破') || dnBlob.includes('简化测幅目标'), 'down-break copy');

// —— 兼容旧 merge 自测仍可用 ——
const mergeOk = typeof PT._mergeNearLevels === 'function';
assert(mergeOk, 'merge helper present');

// —— 真空 primary + confluence：结构块共振支撑，禁止「等待形态边界突破」——
const vacuumItems = [
  {
    pattern_type: 'head_shoulders_top',
    status: 'forming',
    confidence: 0.55,
    key_levels: { neckline: 13.91, head: 16.0, last_close: 14.8 },
    pivots: [{ role: 'RS', date: '2026-03-01', price: 15.0 }],
    formed_at: '2026-03-01',
  },
  {
    pattern_type: 'head_shoulders_bottom',
    status: 'archived',
    confidence: 0.7,
    key_levels: { neckline: 12.0, head: 10.0, last_close: 14.8 },
    pivots: [],
    formed_at: '2026-05-01',
    reason: '头肩底；生命周期已结束（测幅目标已兑现≥15.00，已归档）',
  },
];
const vacuumOpts = {
  asof: '2026-08-12',
  confluenceZones: {
    supports: [
      {
        center: 14.55,
        low: 14.4,
        high: 14.7,
        strength: 9.2,
        sources: ['pivot', 'ma', 'vp'],
      },
    ],
    resistances: [
      {
        center: 15.2,
        low: 15.0,
        high: 15.4,
        strength: 6.1,
        sources: ['kde'],
      },
    ],
    nearest_support_zone: {
      center: 14.55,
      low: 14.4,
      high: 14.7,
      strength: 9.2,
    },
  },
};
const vac = PT.buildExpertAnalysis(vacuumItems, vacuumOpts);
const vacBlob = [vac.shortTerm, vac.mediumTerm, vac.structureText, vac.structureHtml].join(
  '\n'
);
assert(vac.primaryLabel === '暂无主导形态', 'vacuum primaryLabel');
assert(vacBlob.includes('14.55'), `vacuum structure must include 14.55: ${vac.structureText}`);
assert(vacBlob.includes('多维共振带'), 'vacuum structure must label 多维共振带');
assert(!vacBlob.includes('等待形态边界突破'), 'vacuum must not say 等待形态边界突破');
assert(
  (vac.shortTerm || '').includes('结构整理期') ||
    (vac.mediumTerm || '').includes('结构整理期'),
  'P1 vacuum soft copy 结构整理期'
);

// —— 真空且无 confluence：只改占位语义，不编假价 ——
const vacEmpty = PT.buildExpertAnalysis(vacuumItems, { asof: '2026-08-12' });
const vacEmptyBlob = [vacEmpty.structureText, vacEmpty.structureHtml].join('\n');
assert(!vacEmptyBlob.includes('等待形态边界突破'), 'no-conf vacuum must not wait 形态边界');
assert(
  vacEmptyBlob.includes('暂无活跃形态边界'),
  'no-conf vacuum placeholder mentions 暂无活跃形态边界'
);
assert(!/\d+\.\d{2} 附近（多维共振带/.test(vacEmptyBlob), 'no-conf must not invent confluence prices');

console.log(
  'OK',
  JSON.stringify({
    upTarget: '88.00',
    downTarget: '60.00',
    structureLabel: '结构防守与目标',
    plainHasTarget: plain.includes('88.00'),
    vacuumSupport: '14.55',
  })
);

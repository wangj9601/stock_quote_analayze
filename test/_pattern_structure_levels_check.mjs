/**
 * P0/P1 自测：结构档 primary 几何优先、软融合 patternBound、竞选 conf 优先；
 * 已确认上破空阻力、真空共振、002271/002821/002698 类软融合。
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

// —— 002271 类：有 primary + 形态下沿时，夹层高强共振 → 近端缓冲，保留核心破位 ——
const softItems = [
  {
    pattern_type: 'descending_triangle',
    status: 'forming',
    confidence: 0.56,
    formed_at: '2026-07-20',
    key_levels: { upper: 12.14, lower: 11.44, last_close: 11.92 },
  },
  {
    pattern_type: 'double_bottom',
    status: 'forming',
    confidence: 0.55,
    formed_at: '2026-07-15',
    key_levels: { neckline: 12.55, l1: 11.4, l2: 11.44, last_close: 11.92 },
  },
];
const softOpts = {
  asof: '2026-08-13',
  confluenceZones: {
    supports: [
      {
        center: 11.72,
        low: 11.65,
        high: 11.8,
        strength: 47.75,
        sources: ['atr_pivot', 'camarilla', 'fib', 'kde', 'pivot'],
      },
      {
        center: 11.2,
        low: 11.1,
        high: 11.3,
        strength: 8.0,
        sources: ['kde'],
      },
    ],
    resistances: [
      {
        center: 12.0,
        low: 11.95,
        high: 12.05,
        strength: 12.0,
        sources: ['kde'],
      },
    ],
    nearest_support_zone: {
      center: 11.72,
      low: 11.65,
      high: 11.8,
      strength: 47.75,
    },
  },
};
const soft = PT.buildExpertAnalysis(softItems, softOpts);
const softBlob = [soft.structureText, soft.structureHtml].join('\n');
const softPlain = PT.formatExpertPlainText(soft);
assert(softBlob.includes('11.72'), `soft buffer 11.72 missing: ${soft.structureText}`);
assert(softBlob.includes('11.44'), `core pattern 11.44 missing: ${soft.structureText}`);
assert(softBlob.includes('近端缓冲防守'), 'need 近端缓冲防守 label');
assert(softBlob.includes('核心破位防守'), 'need 核心破位防守 label');
assert(softBlob.includes('超级量化共振带'), 'buffer must cite 超级量化共振带');
assert(softPlain.includes('11.72') && softPlain.includes('11.44'), 'plain text soft fusion');
// 阻力几何阶梯（双档）保持，不因夹层弱带打乱
assert(softBlob.includes('12.14'), `resist 12.14 missing: ${soft.structureText}`);
// 夹层 12.00@12 在 现价11.92↔最近形态上沿12.14 内 → 与支撑同构可软插；档位≤2 时更远的 12.55 可被挤出
assert(softBlob.includes('近端缓冲/第一压制'), 'dual pattern resists may soft-insert resist buffer');
assert(softBlob.includes('12.00') || softBlob.includes('12.0'), 'soft resist buffer 12.0');
assert(softBlob.includes('核心形态阻力'), 'need 核心形态阻力 after soft resist');
assert(softBlob.includes('12.14'), 'core nearest pattern upper 12.14 kept');
// 强度不足（11.20 str=8）不得替换/挤掉核心
assert(!/近端缓冲防守：11\.20/.test(softBlob), 'sub-threshold zone must not become buffer');

// —— 002821 类：双档形态阻力 188+200 时，夹层 177.26@28.5 仍应软插 ——
const kayItems = [
  {
    pattern_type: 'head_shoulders_top',
    status: 'confirmed',
    confidence: 0.72,
    formed_at: '2026-06-01',
    confirm_date: '2026-06-15',
    key_levels: {
      neckline: 148.0,
      head: 210.0,
      right_shoulder: 188.0,
      last_close: 175.0,
    },
    pivots: [
      { role: 'LS', date: '2026-04-01', price: 190.0 },
      { role: 'head', date: '2026-05-01', price: 210.0 },
      { role: 'RS', date: '2026-05-20', price: 188.0 },
    ],
  },
  {
    pattern_type: 'descending_triangle',
    status: 'forming',
    confidence: 0.55,
    formed_at: '2026-07-01',
    key_levels: { upper: 200.0, lower: 160.0, last_close: 175.0 },
  },
];
const kayOpts = {
  asof: '2026-08-13',
  confluenceZones: {
    supports: [],
    resistances: [
      {
        center: 177.26,
        low: 176.5,
        high: 178.0,
        strength: 28.5,
        sources: ['atr_pivot', 'kde', 'fib'],
      },
      {
        center: 175.2,
        low: 175.0,
        high: 175.4,
        strength: 8.0,
        sources: ['kde'],
      },
    ],
    nearest_resistance_zone: {
      center: 177.26,
      low: 176.5,
      high: 178.0,
      strength: 28.5,
    },
  },
};
const kay = PT.buildExpertAnalysis(kayItems, kayOpts);
const kayBlob = [kay.shortTerm, kay.mediumTerm, kay.structureText, kay.structureHtml].join(
  '\n'
);
assert(kayBlob.includes('177.26'), `002821 buffer 177.26 missing: ${kay.structureText}`);
assert(
  kayBlob.includes('近端缓冲/第一压制'),
  `002821 need 近端缓冲/第一压制: ${kay.structureText}`
);
assert(
  kayBlob.includes('188.00') || kayBlob.includes('188'),
  `002821 core pattern upper 188 missing: ${kay.structureText}`
);
assert(kayBlob.includes('核心形态阻力'), '002821 need 核心形态阻力');
// 贴价弱带 175.2 不得插；档位 ≤2（不应再堆 200 作为第三档展示）
assert(!/近端缓冲.*175\.20/.test(kayBlob), 'near-price weak zone must not soft-insert');
assert(!kayBlob.includes('上方附近') || !/仍在颈线.*上方附近/.test(kay.shortTerm || ''), 'far above neck must not say 上方附近');
assert(
  (kay.shortTerm || '').includes('远离') ||
    (kay.shortTerm || '').includes('反抽削弱') ||
    (kay.shortTerm || '').includes('不宜机械偏空'),
  `002821 far-above copy should soften bearish: ${kay.shortTerm}`
);

// —— P0 仿 002698：primary=上升楔形时强制几何 14.21/12.78，不被头肩颈线/头挤掉 ——
const boshiItems = [
  {
    pattern_type: 'rising_wedge',
    status: 'forming',
    confidence: 0.58,
    formed_at: '2026-08-07',
    key_levels: { upper: 14.21, lower: 12.78, last_close: 13.93 },
  },
  {
    pattern_type: 'head_shoulders_top',
    status: 'forming',
    confidence: 0.55,
    formed_at: '2026-07-02',
    key_levels: { neckline: 13.5, head: 14.46, right_shoulder: 14.1, last_close: 13.93 },
  },
  {
    pattern_type: 'head_shoulders_bottom',
    status: 'forming',
    confidence: 0.5,
    formed_at: '2026-07-14',
    key_levels: { neckline: 13.2, head: 11.57, right_shoulder: 12.0, last_close: 13.93 },
  },
];
const boshiOpts = {
  asof: '2026-08-13',
  confluenceZones: {
    supports: [
      {
        center: 13.09,
        low: 13.0,
        high: 13.15,
        strength: 18.0,
        sources: ['atr_pivot', 'kde', 'fib'],
      },
    ],
    resistances: [],
    nearest_support_zone: {
      center: 13.09,
      low: 13.0,
      high: 13.15,
      strength: 18.0,
    },
  },
};
const boshi = PT.buildExpertAnalysis(boshiItems, boshiOpts);
const boshiBlob = [boshi.structureText, boshi.structureHtml].join('\n');
assert(boshi.primaryLabel === '上升楔形', `P0 primary should be 上升楔形: ${boshi.primaryLabel}`);
assert(boshiBlob.includes('14.21'), `P0 resist 14.21 missing: ${boshi.structureText}`);
assert(boshiBlob.includes('12.78'), `P0 support core 12.78 missing: ${boshi.structureText}`);
assert(boshiBlob.includes('13.09'), `P0 soft buffer 13.09 missing: ${boshi.structureText}`);
assert(boshiBlob.includes('近端缓冲防守'), 'P0 need 近端缓冲防守');
assert(boshiBlob.includes('核心破位防守'), 'P0 need 核心破位防守');
// 不应只剩头肩几何 14.46 / 11.57 而丢掉楔形边界
assert(
  !/核心破位防守：11\.57/.test(boshiBlob) && !/核心形态阻力：14\.46/.test(boshiBlob),
  `P0 must not replace wedge core with HS-only 14.46/11.57: ${boshi.structureText}`
);

// —— P1 竞选：同 forming 下 conf 优先，衰减压不过更高置信度 ——
const electItems = [
  {
    pattern_type: 'head_shoulders_top',
    status: 'forming',
    confidence: 0.55,
    formed_at: '2026-07-02',
    key_levels: { neckline: 13.5, head: 16.0, last_close: 14.0 },
  },
  {
    pattern_type: 'head_shoulders_bottom',
    status: 'forming',
    confidence: 0.5,
    formed_at: '2026-07-14',
    key_levels: { neckline: 12.5, head: 10.0, last_close: 14.0 },
  },
  {
    pattern_type: 'rising_wedge',
    status: 'forming',
    confidence: 0.45,
    formed_at: '2026-08-07',
    key_levels: { upper: 14.5, lower: 13.0, last_close: 14.0 },
  },
];
const elect = PT.buildExpertAnalysis(electItems, { asof: '2026-08-13' });
assert(
  elect.primaryLabel === '头肩顶',
  `P1 primary should be 头肩顶(0.55) not wedge: ${elect.primaryLabel}`
);
assert(String(elect.primaryConf).startsWith('0.55'), `P1 conf 0.55: ${elect.primaryConf}`);

// —— P1 仿 002698：primary=头肩顶时近端楔上沿 14.21 保送第二席，弱共振 14.03 战术压制 ——
const boshiHsItems = [
  {
    pattern_type: 'rising_wedge',
    status: 'forming',
    confidence: 0.55,
    formed_at: '2026-08-07',
    key_levels: { upper: 14.21, lower: 12.78, last_close: 13.93 },
  },
  {
    pattern_type: 'head_shoulders_top',
    status: 'forming',
    confidence: 0.62,
    formed_at: '2026-07-02',
    key_levels: {
      neckline: 13.5,
      head: 15.1,
      right_shoulder: 14.46,
      last_close: 13.93,
    },
  },
  {
    pattern_type: 'head_shoulders_bottom',
    status: 'forming',
    confidence: 0.5,
    formed_at: '2026-07-14',
    key_levels: { neckline: 13.2, head: 11.57, right_shoulder: 12.0, last_close: 13.93 },
  },
];
const boshiHsOpts = {
  asof: '2026-08-13',
  confluenceZones: {
    supports: [
      {
        // 夹在头肩颈线 13.5 ↔ 现价 13.93：应软插为近端缓冲
        center: 13.7,
        low: 13.65,
        high: 13.75,
        strength: 18.0,
        sources: ['atr_pivot', 'kde', 'fib'],
      },
      {
        // 低于 primary 颈线：不得当作 soft buffer（楔形 primary 场景另测 13.09）
        center: 13.09,
        low: 13.0,
        high: 13.15,
        strength: 12.0,
        sources: ['kde'],
      },
    ],
    resistances: [
      {
        center: 14.03,
        low: 14.0,
        high: 14.06,
        strength: 4.5,
        sources: ['kde', 'vp'],
      },
    ],
    nearest_support_zone: {
      center: 13.7,
      low: 13.65,
      high: 13.75,
      strength: 18.0,
    },
    nearest_resistance_zone: {
      center: 14.03,
      low: 14.0,
      high: 14.06,
      strength: 4.5,
    },
  },
};
const boshiHs = PT.buildExpertAnalysis(boshiHsItems, boshiHsOpts);
const boshiHsBlob = [boshiHs.structureText, boshiHs.structureHtml].join('\n');
assert(
  boshiHs.primaryLabel === '头肩顶',
  `P1-A primary should be 头肩顶: ${boshiHs.primaryLabel}`
);
assert(boshiHsBlob.includes('14.21'), `P1-A near wedge upper 14.21 missing: ${boshiHs.structureText}`);
assert(
  !/第二阻力：15\.10/.test(boshiHsBlob) && !/第二阻力：15\.1\b/.test(boshiHsBlob),
  `P1-A must not prefer far head 15.10 over 14.21: ${boshiHs.structureText}`
);
assert(boshiHsBlob.includes('14.03'), `P1-B tactical 14.03 missing: ${boshiHs.structureText}`);
assert(boshiHsBlob.includes('日内/临界压制'), `P1-B need 日内/临界压制: ${boshiHs.structureText}`);
assert(!boshiHsBlob.includes('近端缓冲/第一压制：14.03'), '14.03 must not occupy soft-buffer seat');
assert(!/近端缓冲防守：13\.09/.test(boshiHsBlob), '13.09 below HS neck must not soft-insert');
// 支撑软融合：夹层 13.70 + 核心颈线
assert(boshiHsBlob.includes('13.70') || boshiHsBlob.includes('13.7'), `P1 support buffer 13.70 missing: ${boshiHs.structureText}`);
assert(boshiHsBlob.includes('近端缓冲防守'), 'P1 need 近端缓冲防守');
assert(boshiHsBlob.includes('核心破位防守'), 'P1 need 核心破位防守');
assert(
  boshiHsBlob.includes('13.50') || boshiHsBlob.includes('13.5'),
  `P1 core neck 13.50 missing: ${boshiHs.structureText}`
);

// —— P0 仿 002991：close=43.37，贴身 43.41@14.8 应赢过更远更强 44.46@16.6 ——
const ganyuanItems = [
  {
    pattern_type: 'ascending_triangle',
    status: 'forming',
    confidence: 0.58,
    formed_at: '2026-07-20',
    key_levels: { upper: 44.65, lower: 41.8, last_close: 43.37 },
  },
];
const ganyuanOpts = {
  asof: '2026-08-13',
  confluenceZones: {
    supports: [],
    resistances: [
      {
        center: 43.41,
        low: 43.37,
        high: 43.46,
        strength: 14.8,
        sources: ['kde', 'pivot'],
      },
      {
        center: 44.46,
        low: 44.3,
        high: 44.6,
        strength: 16.6,
        sources: ['kde', 'fib'],
      },
    ],
    nearest_resistance_zone: {
      center: 43.41,
      low: 43.37,
      high: 43.46,
      strength: 14.8,
    },
  },
};
const ganyuan = PT.buildExpertAnalysis(ganyuanItems, ganyuanOpts);
const ganyuanBlob = [ganyuan.structureText, ganyuan.structureHtml].join('\n');
assert(ganyuanBlob.includes('43.41'), `002991 soft/contact 43.41 missing: ${ganyuan.structureText}`);
assert(
  ganyuanBlob.includes('贴身临界压制'),
  `002991 need 贴身临界压制: ${ganyuan.structureText}`
);
assert(ganyuanBlob.includes('44.65'), `002991 core upper 44.65 missing: ${ganyuan.structureText}`);
assert(ganyuanBlob.includes('核心形态阻力'), '002991 need 核心形态阻力');
// 不得只剩更远更强 44.46 当第一压制；贴身席应是 43.41
assert(
  !/近端缓冲\/第一压制：44\.46/.test(ganyuanBlob) &&
    !/贴身临界压制：44\.46/.test(ganyuanBlob),
  `002991 must not prefer far 44.46 as soft seat: ${ganyuan.structureText}`
);
assert(/贴身临界压制：43\.41/.test(ganyuanBlob), '002991 first soft seat must be 43.41 贴身');

// —— 支撑侧贴身对称：close=43.37，带 43.33[43.28–43.37]@14.8 → 贴身临界支撑 ——
const ganyuanSupItems = [
  {
    pattern_type: 'ascending_triangle',
    status: 'forming',
    confidence: 0.58,
    formed_at: '2026-07-20',
    key_levels: { upper: 44.65, lower: 41.8, last_close: 43.37 },
  },
];
const ganyuanSupOpts = {
  asof: '2026-08-13',
  confluenceZones: {
    supports: [
      {
        center: 43.33,
        low: 43.28,
        high: 43.37,
        strength: 14.8,
        sources: ['kde'],
      },
      {
        center: 42.5,
        low: 42.4,
        high: 42.6,
        strength: 16.6,
        sources: ['kde'],
      },
    ],
    resistances: [],
    nearest_support_zone: {
      center: 43.33,
      low: 43.28,
      high: 43.37,
      strength: 14.8,
    },
  },
};
const ganyuanSup = PT.buildExpertAnalysis(ganyuanSupItems, ganyuanSupOpts);
const ganyuanSupBlob = [ganyuanSup.structureText, ganyuanSup.structureHtml].join('\n');
assert(ganyuanSupBlob.includes('43.33'), `support contact 43.33 missing: ${ganyuanSup.structureText}`);
assert(
  ganyuanSupBlob.includes('贴身临界支撑'),
  `support need 贴身临界支撑: ${ganyuanSup.structureText}`
);
assert(
  !/近端缓冲防守：42\.50/.test(ganyuanSupBlob) && !/贴身临界支撑：42\.50/.test(ganyuanSupBlob),
  `support must prefer near 43.33 over far stronger 42.50: ${ganyuanSup.structureText}`
);

// —— P0 仿 300613：测幅 ACHIEVED — 61.50/53.10→69.90，close=77.81 不得作上方阻力档 ——
const fuhanMeasuredItems = [
  {
    pattern_type: 'falling_wedge',
    status: 'confirmed',
    confidence: 0.72,
    formed_at: '2026-07-01',
    key_levels: { upper: 61.5, lower: 53.1, last_close: 77.81 },
  },
];
const fuhanMeasured = PT.buildExpertAnalysis(fuhanMeasuredItems, { asof: '2026-08-13' });
const fuhanMeasuredBlob = [fuhanMeasured.structureText, fuhanMeasured.structureHtml].join(
  '\n'
);
assert(
  fuhanMeasuredBlob.includes('已超额达成') || fuhanMeasuredBlob.includes('已兑现'),
  `300613 measured ACHIEVED copy missing: ${fuhanMeasured.structureText}`
);
assert(
  !/简化测幅目标：? ?69\.90/.test(fuhanMeasuredBlob) &&
    !/第一阻力：69\.90/.test(fuhanMeasuredBlob) &&
    !/参考阻力（降级）：69\.90/.test(fuhanMeasuredBlob) &&
    !/近端缓冲.*69\.90/.test(fuhanMeasuredBlob),
  `300613 must not emit 69.90 as overhead resist档: ${fuhanMeasured.structureText}`
);
assert(fuhanMeasuredBlob.includes('69.90'), '300613 ACHIEVED background may still cite 69.90');

// —— P0 仿 300613：贴身支撑 77.68[77.38–77.81]@9.15 → soft/贴身，不跳更远 74.67 ——
const fuhanContactItems = [
  {
    pattern_type: 'falling_wedge',
    status: 'confirmed',
    confidence: 0.72,
    formed_at: '2026-07-01',
    key_levels: { upper: 61.5, lower: 53.1, last_close: 77.81 },
  },
];
const fuhanContactOpts = {
  asof: '2026-08-13',
  confluenceZones: {
    supports: [
      {
        center: 77.68,
        low: 77.38,
        high: 77.81,
        strength: 9.15,
        sources: ['kde', 'pivot'],
      },
      {
        center: 74.67,
        low: 74.4,
        high: 74.9,
        strength: 12.0,
        sources: ['kde', 'fib'],
      },
    ],
    resistances: [],
    nearest_support_zone: {
      center: 77.68,
      low: 77.38,
      high: 77.81,
      strength: 9.15,
    },
  },
};
const fuhanContact = PT.buildExpertAnalysis(fuhanContactItems, fuhanContactOpts);
const fuhanContactBlob = [fuhanContact.structureText, fuhanContact.structureHtml].join('\n');
assert(
  fuhanContactBlob.includes('77.68'),
  `300613 contact support 77.68 missing: ${fuhanContact.structureText}`
);
assert(
  fuhanContactBlob.includes('贴身临界支撑'),
  `300613 need 贴身临界支撑: ${fuhanContact.structureText}`
);
assert(
  !/贴身临界支撑：74\.67/.test(fuhanContactBlob) &&
    !/近端缓冲防守：74\.67/.test(fuhanContactBlob),
  `300613 must not prefer far 74.67 over contact 77.68: ${fuhanContact.structureText}`
);

// —— P1 仿 300613：上破阻力空 → confluence 近端降级 1 档；已跌破 VAH 不写回 ——
const fuhanResistItems = [
  {
    pattern_type: 'falling_wedge',
    status: 'confirmed',
    confidence: 0.72,
    formed_at: '2026-07-01',
    key_levels: { upper: 61.5, lower: 53.1, last_close: 77.81 },
  },
];
const fuhanResistOpts = {
  asof: '2026-08-13',
  confluenceZones: {
    supports: [],
    resistances: [
      {
        center: 80.2,
        low: 79.9,
        high: 80.5,
        strength: 11.2,
        sources: ['kde', 'atr_pivot'],
      },
      {
        // 已跌破 VAH：整带在现价下，不得写回上方阻力
        center: 76.5,
        low: 76.2,
        high: 76.8,
        strength: 20.0,
        sources: ['vah', 'vp_vah', 'fib'],
      },
    ],
    nearest_resistance_zone: {
      center: 80.2,
      low: 79.9,
      high: 80.5,
      strength: 11.2,
    },
  },
};
const fuhanResist = PT.buildExpertAnalysis(fuhanResistItems, fuhanResistOpts);
const fuhanResistBlob = [fuhanResist.structureText, fuhanResist.structureHtml].join('\n');
assert(
  fuhanResistBlob.includes('80.20') || fuhanResistBlob.includes('80.2'),
  `300613 degraded resist 80.2 missing: ${fuhanResist.structureText}`
);
assert(
  fuhanResistBlob.includes('参考阻力（降级）') || fuhanResistBlob.includes('参考/降级'),
  `300613 need 参考/降级 copy: ${fuhanResist.structureText}`
);
assert(
  !/参考阻力（降级）：76\.50/.test(fuhanResistBlob) &&
    !/第一阻力：76\.50/.test(fuhanResistBlob),
  `300613 must not write broken VAH 76.5 as overhead: ${fuhanResist.structureText}`
);

// —— P1 共振也空：ATR-Pivot R1 / KDE 降级旁路 ——
const fuhanAtrOpts = {
  asof: '2026-08-13',
  confluenceZones: { supports: [], resistances: [] },
  classicLevels: { atr_pivot: { R1: 81.5, S1: 70.0, nearest_resistance: 81.5 } },
  kdeLevels: { nearest_resistance: 82.0, resistance_levels: [82.0, 85.0] },
};
const fuhanAtr = PT.buildExpertAnalysis(fuhanResistItems, fuhanAtrOpts);
const fuhanAtrBlob = [fuhanAtr.structureText, fuhanAtr.structureHtml].join('\n');
assert(
  fuhanAtrBlob.includes('81.50') || fuhanAtrBlob.includes('81.5'),
  `300613 ATR R1 81.5 missing: ${fuhanAtr.structureText}`
);
assert(
  fuhanAtrBlob.includes('参考/降级') || fuhanAtrBlob.includes('参考阻力（降级）'),
  `300613 ATR path need 参考/降级: ${fuhanAtr.structureText}`
);
assert(
  !/参考阻力（降级）：82\.00/.test(fuhanAtrBlob),
  'ATR R1 should win over KDE when confluence empty'
);

// —— P1 中线：同 forming、|Δconf|<0.05、bias 冲突 → 多空交织文案；primary 仍置信优先 ——
const mixItems = [
  {
    pattern_type: 'head_shoulders_top',
    status: 'forming',
    confidence: 0.56,
    formed_at: '2026-07-10',
    key_levels: { neckline: 40.0, head: 48.0, last_close: 43.0 },
  },
  {
    pattern_type: 'head_shoulders_bottom',
    status: 'forming',
    confidence: 0.53,
    formed_at: '2026-07-10',
    key_levels: { neckline: 42.0, head: 36.0, last_close: 43.0 },
  },
];
const mix = PT.buildExpertAnalysis(mixItems, { asof: '2026-08-13' });
assert(mix.primaryLabel === '头肩顶', `mix primary still conf-first 头肩顶: ${mix.primaryLabel}`);
assert(
  (mix.mediumTerm || '').includes('多空形态交织') &&
    (mix.mediumTerm || '').includes('宽幅箱体'),
  `mix mediumTerm need 交织文案: ${mix.mediumTerm}`
);

console.log(
  'OK',
  JSON.stringify({
    upTarget: '88.00',
    downTarget: '60.00',
    structureLabel: '结构防守与目标',
    plainHasTarget: plain.includes('88.00'),
    vacuumSupport: '14.55',
    softBuffer: '11.72',
    softCore: '11.44',
    kayBuffer: '177.26',
    kayCore: '188',
    boshiPrimary: '上升楔形',
    boshiUpper: '14.21',
    boshiLower: '12.78',
    boshiBuffer: '13.09',
    electPrimary: '头肩顶',
    boshiHsPrimary: '头肩顶',
    boshiHsNearUpper: '14.21',
    boshiHsTactical: '14.03',
    boshiHsBuffer: '13.70',
    ganyuanContact: '43.41',
    ganyuanCore: '44.65',
    ganyuanSupContact: '43.33',
    fuhanMeasuredAchieved: true,
    fuhanContact: '77.68',
    fuhanDegradedResist: '80.2',
    fuhanAtrR1: '81.5',
    mixPrimary: '头肩顶',
    mixInterleave: true,
  })
);

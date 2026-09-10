/**
 * CSB 通道粘合突破 — 信号计算明细 HTML（选股页 / 历史页共用）
 * 风格对齐 GMS / URT / SBBR：分区标题 + meta + 分项表。
 */
const CsbScoreDetail = {
  _fmt(v, digits) {
    if (v == null || v === '') return '--';
    if (typeof v === 'boolean') return v ? '是' : '否';
    const n = Number(v);
    if (!Number.isFinite(n)) return String(v);
    return n.toFixed(digits != null ? digits : 2);
  },

  _pct(v, digits) {
    if (v == null || v === '') return '--';
    const n = Number(v);
    if (!Number.isFinite(n)) return String(v);
    return `${(n * 100).toFixed(digits != null ? digits : 2)}%`;
  },

  _passLabel(ok) {
    if (ok === true) return '<span class="strength-high">通过</span>';
    if (ok === false) return '<span class="strength-low">未通过</span>';
    return '--';
  },

  _yn(v) {
    if (v === true) return '<span class="strength-high">是</span>';
    if (v === false) return '<span class="strength-low">否</span>';
    return '--';
  },

  _esc(s) {
    return String(s ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/"/g, '&quot;');
  },

  _signalLabel(t) {
    const map = {
      CSB_SETUP: 'SETUP（观察）',
      CSB_PROBE: 'PROBE（试探入场）',
      CSB_BREAKOUT: 'BREAKOUT（突破入场）',
      CSB_FALSE_BREAK: '假突破',
      CSB_STOP: '止损',
      CSB_TRAIL: '跟踪出场',
    };
    const s = String(t || '').trim();
    return map[s] || s || '--';
  },

  _pick(...vals) {
    for (let i = 0; i < vals.length; i += 1) {
      if (vals[i] != null && vals[i] !== '') return vals[i];
    }
    return null;
  },

  /**
   * 从行数据 / detail 兜底重建 score_detail（兼容旧预计算）
   */
  _ensureScoreDetail(src) {
    if (src.score_detail && typeof src.score_detail === 'object' && src.score_detail.parts) {
      return src.score_detail;
    }
    const detail = src.detail && typeof src.detail === 'object' ? src.detail : {};
    if (detail.score && typeof detail.score === 'object' && detail.score.parts) {
      return detail.score;
    }

    const setup = detail.setup && typeof detail.setup === 'object' ? detail.setup : {};
    const channel = (setup.channel && typeof setup.channel === 'object')
      ? setup.channel
      : {};
    const dry = (setup.dry_vol && typeof setup.dry_vol === 'object') ? setup.dry_vol : {};
    const entry = detail.entry && typeof detail.entry === 'object' ? detail.entry : {};

    const sqDays = Number(this._pick(src.squeeze_days, channel.squeeze_days, 0)) || 0;
    const sqPct = this._pick(src.squeeze_pct, channel.squeeze_pct);
    const touches = Number(this._pick(src.touch_count, setup.touch_count, 0)) || 0;
    const dryOk = this._pick(dry.dry_ok, false) === true;
    const turnoverOk = this._pick(setup.turnover_ok, src.turnover_ok, false) === true;
    const signalType = src.signal_type;
    const vm = this._pick(src.vol_expand_mult, entry.vol_expand_mult);

    const squeezeDaysScore = Math.min(25, sqDays * 1.2);
    const squeezePctScore = sqPct != null
      ? Math.max(0, 15 * (1 - Number(sqPct) / 0.06))
      : 0;
    const touchScore = Math.min(15, touches * 4);
    const dryScore = dryOk ? 10 : 0;
    const turnoverScore = turnoverOk ? 10 : 0;
    let entryBonus = 0;
    let volBonus = 0;
    if (signalType === 'CSB_PROBE') entryBonus = 12;
    else if (signalType === 'CSB_BREAKOUT') {
      entryBonus = 20;
      if (vm != null) volBonus = Math.min(10, Number(vm));
    }
    const raw = squeezeDaysScore + squeezePctScore + touchScore + dryScore
      + turnoverScore + entryBonus + volBonus;
    const total = Math.round(Math.min(100, raw) * 100) / 100;

    return {
      total,
      parts: {
        squeeze_days: { score: +squeezeDaysScore.toFixed(2), max: 25, value: sqDays, formula: 'min(25, squeeze_days × 1.2)' },
        squeeze_pct: { score: +squeezePctScore.toFixed(2), max: 15, value: sqPct != null ? Number(sqPct) : null, formula: 'max(0, 15 × (1 − squeeze_pct / 0.06))' },
        touches: { score: +touchScore.toFixed(2), max: 15, value: touches, formula: 'min(15, touch_count × 4)' },
        dry_vol: { score: dryScore, max: 10, ok: dryOk, formula: '地量成立 +10' },
        turnover: { score: turnoverScore, max: 10, ok: turnoverOk, formula: '20日均换手达标 +10' },
        entry_type: { score: entryBonus, max: 20, signal_type: signalType, formula: 'PROBE +12 / BREAKOUT +20' },
        vol_expand: { score: +volBonus.toFixed(2), max: 10, value: vm != null ? Number(vm) : null, formula: '仅 BREAKOUT：min(10, vol_expand_mult)' },
      },
      reconstructed: true,
    };
  },

  /**
   * @param {object} row 选股 / 历史行数据
   * @returns {string} HTML
   */
  buildHtml(row) {
    const src = row && typeof row === 'object' ? row : {};
    const detail = src.detail && typeof src.detail === 'object' ? src.detail : {};
    const setup = detail.setup && typeof detail.setup === 'object' ? detail.setup : {};
    const entryD = detail.entry && typeof detail.entry === 'object' ? detail.entry : {};
    const channel = (setup.channel && typeof setup.channel === 'object')
      ? setup.channel
      : {};
    const ma250 = (setup.ma250 && typeof setup.ma250 === 'object') ? setup.ma250 : {};
    const dry = (setup.dry_vol && typeof setup.dry_vol === 'object') ? setup.dry_vol : {};
    const sd = this._ensureScoreDetail(src);
    const parts = sd.parts || {};

    const signalType = src.signal_type;
    const entrySignal = !!src.entry_signal;
    const setupOk = src.setup_ok != null ? !!src.setup_ok : !!setup.setup_ok;
    const total = src.score != null ? src.score : sd.total;
    const close = this._pick(src.close, channel.close);
    const lower = this._pick(src.channel_lower, channel.lower);
    const upper = this._pick(src.channel_upper, channel.upper);
    const squeezeDays = this._pick(src.squeeze_days, channel.squeeze_days);
    const squeezePct = this._pick(src.squeeze_pct, channel.squeeze_pct);
    const hh20 = this._pick(src.hh20, channel.hh20);
    const resistance = this._pick(src.resistance, channel.resistance, entryD.resistance);
    const touchCount = this._pick(src.touch_count, setup.touch_count);
    const entryKind = this._pick(src.entry_kind, entryD.entry_kind);

    let html = '<div class="gms-score-detail-inner csb-score-detail-inner">';
    html += '<div class="gms-score-detail-meta"><div class="gms-version-meta-line">';
    html += '<span class="gms-version-name">通道粘合突破（CSB）</span>';
    html += `<span>日期 ${this._esc(src.date || src.trade_date || src.signal_date || '--')}</span>`;
    html += `<span>信号 <strong>${this._esc(this._signalLabel(signalType))}</strong></span>`;
    html += `<span>总分 <strong>${this._fmt(total, 1)}</strong></span>`;
    html += `<span>SETUP ${this._passLabel(setupOk)}</span>`;
    html += `<span>入场 <span class="${entrySignal ? 'strength-high' : 'strength-low'}">${entrySignal ? '是' : '否'}</span></span>`;
    if (sd.reconstructed) html += '<span title="由字段兜底重算">明细已重建</span>';
    html += '</div></div>';

    // 【判定链路】
    html += '<div class="gms-score-detail-section"><strong>【判定链路】</strong>';
    html += '<p class="urt-buy-logic-formula">MA5/10/20/60 粘合通道 → SETUP（换手+年线+回踩+地量）→ BREAKOUT 优先，否则 PROBE</p>';
    html += '<p class="urt-buy-logic-detail">通道下轨 = min(MA5,10,20,60)；上轨 = max(...)；粘合带宽 = (上轨−下轨)/收盘；默认带宽≤4% 且连续≥15 日。</p>';
    html += '<table class="gms-weight-table"><thead><tr><th>阶段</th><th>规则摘要</th><th>结果</th></tr></thead><tbody>';
    html += `<tr><td>通道粘合</td><td>带宽 ≤4% 且连续粘合 ≥15 日</td><td>${this._passLabel(channel.squeeze_ok)}</td></tr>`;
    html += `<tr><td>SETUP</td><td>粘合 + 换手 + 年线 + 回踩≥2 + 地量</td><td>${this._passLabel(setupOk)}</td></tr>`;
    html += `<tr><td>BREAKOUT</td><td>放量≥2× + 实体≥3% + 上影≤0.3 + 收盘≥阻力×1.02</td><td>${this._yn(entryKind === 'breakout')}</td></tr>`;
    html += `<tr><td>PROBE</td><td>量比≤0.8 + 缩量止跌形态</td><td>${this._yn(entryKind === 'probe')}</td></tr>`;
    html += '</tbody></table></div>';

    // 【通道与阻力】
    html += '<div class="gms-score-detail-section"><strong>【通道与阻力】</strong>';
    html += '<table class="gms-weight-table"><thead><tr><th>指标</th><th>取值</th><th>说明</th></tr></thead><tbody>';
    html += `<tr><td>收盘</td><td>${this._fmt(close, 2)}</td><td>基准日收盘价</td></tr>`;
    html += `<tr><td>通道下轨</td><td>${this._fmt(lower, 2)}</td><td>min(MA5, MA10, MA20, MA60)</td></tr>`;
    html += `<tr><td>通道上轨</td><td>${this._fmt(upper, 2)}</td><td>max(MA5, MA10, MA20, MA60)</td></tr>`;
    html += `<tr><td>粘合带宽</td><td>${this._pct(squeezePct, 2)}</td><td>(上轨−下轨)/收盘</td></tr>`;
    html += `<tr><td>粘合天数</td><td>${squeezeDays != null ? String(squeezeDays) : '--'}</td><td>从尾部向前连续满足带宽阈值</td></tr>`;
    html += `<tr><td>MA5 / 10 / 20 / 60</td><td>${this._fmt(channel.ma5, 2)} / ${this._fmt(channel.ma10, 2)} / ${this._fmt(channel.ma20, 2)} / ${this._fmt(channel.ma60, 2)}</td><td>构成通道的四条均线</td></tr>`;
    html += `<tr><td>HH20</td><td>${this._fmt(hh20, 2)}</td><td>近20日最高价（不含当日）</td></tr>`;
    html += `<tr><td>阻力线</td><td>${this._fmt(resistance, 2)}</td><td>max(上轨, HH20)</td></tr>`;
    if (entryD.break_line != null) {
      html += `<tr><td>突破线</td><td>${this._fmt(entryD.break_line, 2)}</td><td>阻力 × (1 + break_pct)，默认 +2%</td></tr>`;
    }
    html += '</tbody></table></div>';

    // 【SETUP 条件】
    html += '<div class="gms-score-detail-section"><strong>【SETUP 条件】</strong>';
    html += '<table class="gms-weight-table"><thead><tr><th>条件</th><th>实际值</th><th>结果</th></tr></thead><tbody>';
    html += `<tr><td>20日均换手 ≥1.0%</td><td>${this._fmt(setup.turnover_avg_20, 2)}%</td><td>${this._passLabel(setup.turnover_ok)}</td></tr>`;
    html += `<tr><td>年线防守</td><td>MA250 ${this._fmt(ma250.ma250, 2)} · 斜率 ${this._fmt(ma250.ma250_slope_norm, 6)} · 收≥年线 ${this._yn(ma250.close_above_ma250)}</td><td>${this._passLabel(ma250.ma250_ok)}</td></tr>`;
    html += `<tr><td>近60日回踩下轨 ≥2</td><td>${touchCount != null ? String(touchCount) : '--'} 次</td><td>${this._passLabel(setup.touch_ok)}</td></tr>`;
    html += `<tr><td>地量（5日量/60日量 ≤0.55）</td><td>量比 ${this._fmt(dry.vol_ratio_short_long, 3)} · 换手比 ${this._fmt(dry.turnover_ratio_short_long, 3)}</td><td>${this._passLabel(dry.dry_ok)}</td></tr>`;
    html += '</tbody></table></div>';

    // 【入场条件】
    html += '<div class="gms-score-detail-section"><strong>【入场条件】</strong>';
    if (!setupOk) {
      html += '<p class="urt-buy-logic-detail">SETUP 未成立，不评估 PROBE / BREAKOUT。</p>';
    } else if (entryKind === 'breakout') {
      html += '<p class="urt-buy-logic-formula">当前命中：BREAKOUT（优先于 PROBE）</p>';
      html += '<table class="gms-weight-table"><thead><tr><th>条件</th><th>实际值</th><th>结果</th></tr></thead><tbody>';
      html += `<tr><td>放量倍数 ≥2.0</td><td>${this._fmt(this._pick(src.vol_expand_mult, entryD.vol_expand_mult), 2)}</td><td>${this._passLabel(entryD.expand_ok)}</td></tr>`;
      html += `<tr><td>阳线实体 ≥3%</td><td>${this._pct(entryD.body_pct, 2)}</td><td>${this._passLabel(entryD.body_ok)}</td></tr>`;
      html += `<tr><td>上影/实体 ≤0.30</td><td>${this._fmt(entryD.upper_shadow_ratio, 2)}</td><td>${this._passLabel(entryD.shadow_ok)}</td></tr>`;
      html += `<tr><td>收盘 ≥ 突破线</td><td>收 ${this._fmt(close, 2)} / 线 ${this._fmt(entryD.break_line, 2)}</td><td>${this._passLabel(close != null && entryD.break_line != null && Number(close) >= Number(entryD.break_line))}</td></tr>`;
      html += '</tbody></table>';
    } else if (entryKind === 'probe') {
      html += '<p class="urt-buy-logic-formula">当前命中：PROBE（试探）</p>';
      html += '<table class="gms-weight-table"><thead><tr><th>条件</th><th>实际值</th><th>结果</th></tr></thead><tbody>';
      html += `<tr><td>5日均量/20日均量 ≤0.8</td><td>${this._fmt(this._pick(src.vol_ratio_5_20, entryD.vol_ratio_5_20), 3)}</td><td>${this._passLabel(entryD.shrink_ok)}</td></tr>`;
      html += `<tr><td>缩量止跌形态</td><td>收阴跌幅≤2% 或 下影≥实体 或 阳线</td><td>${this._passLabel(entryD.pattern_ok)}</td></tr>`;
      html += `<tr><td>入场下沿</td><td>${this._fmt(src.entry_low, 2)}</td><td>当日最低价</td></tr>`;
      html += '</tbody></table>';
    } else {
      html += '<p class="urt-buy-logic-detail">SETUP 成立但未触发 PROBE / BREAKOUT。</p>';
      html += '<table class="gms-weight-table"><thead><tr><th>字段</th><th>取值</th></tr></thead><tbody>';
      html += `<tr><td>量比 5/20</td><td>${this._fmt(this._pick(src.vol_ratio_5_20, entryD.vol_ratio_5_20), 3)}</td></tr>`;
      html += `<tr><td>放量倍数</td><td>${this._fmt(this._pick(src.vol_expand_mult, entryD.vol_expand_mult), 2)}</td></tr>`;
      html += `<tr><td>实体 / 上影比</td><td>${this._pct(entryD.body_pct, 2)} / ${this._fmt(entryD.upper_shadow_ratio, 2)}</td></tr>`;
      html += `<tr><td>突破线</td><td>${this._fmt(entryD.break_line, 2)}</td></tr>`;
      html += '</tbody></table>';
    }
    html += '</div>';

    // 【分项得分】
    html += '<div class="gms-score-detail-section"><strong>【分项得分】</strong>';
    html += '<p class="urt-buy-logic-detail">总分封顶 100；入场筛选默认要求得分 ≥60。</p>';
    html += '<table class="gms-weight-table"><thead><tr><th>分项</th><th>得分</th><th>满分</th><th>说明</th></tr></thead><tbody>';
    const partRows = [
      {
        name: '粘合天数',
        p: parts.squeeze_days,
        note: (p) => `天数 ${p && p.value != null ? p.value : '--'} · ${p && p.formula ? p.formula : ''}`,
      },
      {
        name: '粘合带宽',
        p: parts.squeeze_pct,
        note: (p) => `带宽 ${this._pct(p && p.value, 2)} · ${p && p.formula ? p.formula : ''}`,
      },
      {
        name: '回踩次数',
        p: parts.touches,
        note: (p) => `次数 ${p && p.value != null ? p.value : '--'} · ${p && p.formula ? p.formula : ''}`,
      },
      {
        name: '地量',
        p: parts.dry_vol,
        note: (p) => `${p && p.ok ? '成立' : '未成立'} · ${p && p.formula ? p.formula : ''}`,
      },
      {
        name: '换手',
        p: parts.turnover,
        note: (p) => `${p && p.ok ? '达标' : '未达标'} · ${p && p.formula ? p.formula : ''}`,
      },
      {
        name: '入场类型',
        p: parts.entry_type,
        note: (p) => `${this._signalLabel(p && p.signal_type)} · ${p && p.formula ? p.formula : ''}`,
      },
      {
        name: '突破量能加分',
        p: parts.vol_expand,
        note: (p) => `倍数 ${this._fmt(p && p.value, 2)} · ${p && p.formula ? p.formula : ''}`,
      },
    ];
    partRows.forEach((r) => {
      const p = r.p || {};
      html += `<tr><td>${r.name}</td><td>${this._fmt(p.score, 2)}</td><td>${p.max != null ? p.max : '--'}</td><td>${r.note(p)}</td></tr>`;
    });
    html += `<tr><td><strong>合计</strong></td><td><strong>${this._fmt(total, 2)}</strong></td><td>100</td><td>min(100, 各分项之和)</td></tr>`;
    html += '</tbody></table></div>';

    html += '</div>';
    return html;
  },
};

if (typeof window !== 'undefined') {
  window.CsbScoreDetail = CsbScoreDetail;
}

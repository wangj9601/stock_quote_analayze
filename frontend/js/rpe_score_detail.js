/**
 * RPE 比价效应明细 HTML（选股页展开，风格对齐 GMS/URT）
 */
const RpeScoreDetail = {
  _fmt(v, digits) {
    if (v == null || v === '') return '--';
    if (typeof v === 'boolean') return v ? '是' : '否';
    const n = Number(v);
    if (!Number.isFinite(n)) return String(v);
    return n.toFixed(digits != null ? digits : 2);
  },

  _passLabel(ok) {
    if (ok === true) return '<span class="strength-high">通过</span>';
    if (ok === false) return '<span class="strength-low">未通过</span>';
    return '--';
  },

  _esc(s) {
    return String(s ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/"/g, '&quot;');
  },

  _signalLabel(t) {
    if (t === 'catch_up') return '补涨 catch_up';
    if (t === 'lead') return '领涨 lead';
    return t || '--';
  },

  _reasonText(code) {
    const map = {
      catch_up_ok: '补涨条件全部满足，给出入场信号',
      catch_up_filtered: '已识别补涨偏离，但被趋势/结构/流动性过滤',
      lead_trade_ok: '领涨且允许交易，给出入场信号',
      lead_watch: '领涨仅观察（默认不交易）',
      in_band: 'Z 处于中性区间，无领涨/补涨信号',
      no_z: '无法计算 Z-Score',
      below_or_no_support: '现价不在支撑之上或无支撑',
      zero_downside: '下行空间为 0',
      no_resistance: '无上方阻力，结构空间视为充足',
      at_resistance: '现价已触及/越过阻力',
      rr_too_small: '盈亏比不足',
      ok: '通过',
      thin_liquidity: '流动性不足',
      no_bars: '缺少行情',
      insufficient_samples: '有效价量样本不足（需≥20）',
      bad_stats: '价格统计无效（均值/波动为0）',
      ok_histogram_fallback: '已用直方图回退计算支撑/阻力（建议安装 scipy）',
    };
    return map[code] || code || '--';
  },

  /**
   * @param {object} row 选股行数据
   * @returns {string} HTML
   */
  buildHtml(row) {
    const src = row && typeof row === 'object' ? row : {};
    const detail = src.detail && typeof src.detail === 'object' ? src.detail : {};
    const th = detail.thresholds && typeof detail.thresholds === 'object' ? detail.thresholds : {};
    const struct = detail.structure && typeof detail.structure === 'object' ? detail.structure : {};
    const liq = detail.liquidity && typeof detail.liquidity === 'object' ? detail.liquidity : {};
    const judgment = detail.judgment && typeof detail.judgment === 'object' ? detail.judgment : {};
    const steps = Array.isArray(judgment.steps) ? judgment.steps : [];

    const entry = !!src.entry_signal;
    const entryClass = entry ? 'strength-high' : 'strength-low';
    const signalType = src.signal_type;
    const reason = detail.signal_reason || src.signal_reason;

    let html = '<div class="gms-score-detail-inner rpe-score-detail-inner">';
    html += '<div class="gms-score-detail-meta">';
    html += '<div class="gms-version-meta-line">';
    html += '<span class="gms-version-name">比价效应策略（RPE）</span>';
    html += `<span>信号 <strong>${this._esc(this._signalLabel(signalType))}</strong></span>`;
    html += `<span>入场 <span class="${entryClass}">${entry ? '是' : '否'}</span></span>`;
    if (src.watch_only != null) html += `<span>仅观察 ${src.watch_only ? '是' : '否'}</span>`;
    if (src.trend_veto != null) html += `<span>趋势否决 ${src.trend_veto ? '是' : '否'}</span>`;
    html += `<span>日期 ${this._esc(src.date || '--')}</span>`;
    html += '</div></div>';

    html += '<div class="gms-score-detail-section"><strong>【入场判断逻辑】</strong>';
    html += `<p class="urt-buy-logic-formula">${this._esc(
      judgment.formula ||
        '入场 = (catch_up 或 允许交易的 lead) AND 未趋势否决 AND 结构有效 AND 流动性通过'
    )}</p>`;
    html += `<p class="urt-buy-logic-detail">${this._esc(
      judgment.formula_detail ||
        '比价 R=P/I（分子=个股收盘，分母=板块量权基准）；补涨主路径看 Z 偏低；领涨默认仅观察；离场仅认结构破位。'
    )}</p>`;

    if (steps.length) {
      html +=
        '<table class="gms-weight-table"><thead><tr><th>条件</th><th>规则</th><th>实际值</th><th>结果</th></tr></thead><tbody>';
      steps.forEach((s) => {
        const note = s.note ? `<div class="urt-buy-logic-sub">${this._esc(this._reasonText(s.note))}</div>` : '';
        let actual = s.actual;
        if (typeof actual === 'number') actual = this._fmt(actual, 4);
        else if (actual == null) actual = '--';
        else actual = this._esc(String(actual));
        html += `<tr><td>${this._esc(s.name || '--')}</td><td>${this._esc(s.rule || '--')}${note}</td>`;
        html += `<td>${actual}</td><td>${this._passLabel(s.pass)}</td></tr>`;
      });
      html += '</tbody></table>';
    } else {
      // 兼容旧 trace：无 judgment.steps 时用行字段拼装
      html +=
        '<table class="gms-weight-table"><thead><tr><th>条件</th><th>规则</th><th>实际值</th><th>结果</th></tr></thead><tbody>';
      const zCatch = th.z_catch_up != null ? th.z_catch_up : -1.5;
      const zLead = th.z_lead != null ? th.z_lead : 2.0;
      const minRr = th.min_rr_to_resistance != null ? th.min_rr_to_resistance : 1.5;
      const z = src.z_score;
      html += `<tr><td>补涨 Z</td><td>Z ≤ ${zCatch}</td><td>${this._fmt(z, 3)}</td><td>${this._passLabel(
        z != null && Number(z) <= Number(zCatch)
      )}</td></tr>`;
      html += `<tr><td>领涨 Z</td><td>Z ≥ ${zLead}</td><td>${this._fmt(z, 3)}</td><td>${this._passLabel(
        z != null && Number(z) >= Number(zLead)
      )}</td></tr>`;
      html += `<tr><td>趋势否决</td><td>板块斜率≥0</td><td>${this._fmt(src.sector_slope, 6)}</td><td>${this._passLabel(
        !src.trend_veto
      )}</td></tr>`;
      html += `<tr><td>结构</td><td>支撑上 + RR≥${minRr}</td><td>RR ${this._fmt(
        struct.rr,
        2
      )}</td><td>${this._passLabel(src.structure_valid)}</td></tr>`;
      html += `<tr><td>流动性</td><td>均额/换手下限</td><td>${this._fmt(
        liq.avg_amount,
        0
      )}</td><td>${this._passLabel(src.liquidity_ok)}</td></tr>`;
      html += '</tbody></table>';
    }

    html += `<p class="urt-buy-logic-conclusion">结论：${this._esc(
      this._reasonText(reason)
    )} → 入场 <span class="${entryClass}">${entry ? '是' : '否'}</span></p>`;
    html += '</div>';

    html += '<div class="gms-score-detail-section"><strong>【关键参数取值】</strong>';
    html += '<table class="gms-weight-table"><thead><tr><th>参数</th><th>取值</th><th>说明</th></tr></thead><tbody>';
    const pClose = this._fmt(src.close, 2);
    const iT = this._fmt(detail.i_t, 4);
    const params = [
      ['板块', `${src.sector_name || '--'}（${src.sector_id || '--'}）`, '主板块簇（基准所属板块）'],
      ['收盘价 P', pClose, '分子（比价 R=P/I）：评估日个股收盘'],
      ['板块基准 I_t', iT, '分母（比价）：板块成分量权收盘价 ∑(P·V)/∑V'],
      ['比价 R=P/I', this._fmt(src.ratio, 4), `分子 P=${pClose}，分母 I=${iT}；个股相对板块`],
      [
        'Z-Score',
        this._fmt(src.z_score, 3),
        `对 R 滚动标准化；窗口 ${detail.z_window != null ? detail.z_window : th.z_window || 40}；分子=R−μ，分母=σ`,
      ],
      [
        '板块斜率',
        this._fmt(src.sector_slope, 6),
        `近 ${th.sector_slope_window != null ? th.sector_slope_window : 60} 日 I_t 回归斜率；&lt;0 可趋势否决`,
      ],
      [
        '最近支撑 S',
        this._fmt(src.nearest_support, 2),
        `KDE 密度峰（现价下方）；无则扩窗至 ${
          th.kde_lookback_max != null ? th.kde_lookback_max : 750
        } 日再找；RR 分母相关`,
      ],
      ['最近阻力', this._fmt(src.nearest_resistance, 2), 'KDE 密度峰（现价上方）；无则「-」且结构可放宽'],
      ['KDE 状态', this._esc(this._reasonText(detail.kde_reason)), detail.kde_reason || '--'],
      [
        'KDE 回看',
        detail.kde_lookback_used != null
          ? `${detail.kde_lookback_used}${detail.kde_lookback_expanded ? '（已扩窗）' : ''}`
          : '--',
        `初始 ${th.lookback_days != null ? th.lookback_days : detail.lookback_days_applied || 250} 日；无支撑则 +${
          th.kde_lookback_step != null ? th.kde_lookback_step : 250
        }，上限 ${th.kde_lookback_max != null ? th.kde_lookback_max : 750}`,
      ],
      [
        '盈亏比 RR',
        this._fmt(struct.rr, 2),
        `分子=到阻力距离，分母=到支撑距离；阈值 ≥ ${
          th.min_rr_to_resistance != null ? th.min_rr_to_resistance : 1.5
        }`,
      ],
      ['结构有效', this._fmt(src.structure_valid), this._reasonText(struct.reason)],
      [
        '流动性分档',
        this._esc(liq.board_segment_label || liq.board_segment || th.liquidity_board_segment || '--'),
        '上市板别：主板/中小板/创业板/科创板/北证',
      ],
      [
        '应用均额门槛',
        this._fmt(
          liq.min_avg_amount_applied != null
            ? liq.min_avg_amount_applied
            : th.liquidity_min_avg_amount,
          0
        ),
        '人民币元（成交额，非手数）',
      ],
      [
        '换手门槛%',
        this._fmt(
          liq.min_avg_turnover_rate_applied != null
            ? liq.min_avg_turnover_rate_applied
            : th.liquidity_min_avg_turnover_rate != null
              ? th.liquidity_min_avg_turnover_rate
              : 0.8,
          2
        ),
        '近窗口日均换手下限',
      ],
      ['日均成交额', this._fmt(liq.avg_amount, 0), this._reasonText(liq.reason)],
      ['日均换手%', this._fmt(liq.avg_turnover_rate, 2), '流动性窗口均值'],
      ['KDE 带宽', this._fmt(detail.bw, 4), `base_factor=${th.kde_base_factor != null ? th.kde_base_factor : 1}`],
      ['z_catch_up', this._fmt(th.z_catch_up != null ? th.z_catch_up : -1.5, 2), '补涨阈值：Z≤该值'],
      ['z_lead', this._fmt(th.z_lead != null ? th.z_lead : 2.0, 2), '领涨阈值：Z≥该值'],
      ['enable_lead_trade', this._fmt(th.enable_lead_trade != null ? th.enable_lead_trade : false), '领涨是否可交易'],
      ['enable_trend_veto', this._fmt(th.enable_trend_veto != null ? th.enable_trend_veto : true), '弱势板块否决入场'],
    ];
    params.forEach(([name, val, note]) => {
      html += `<tr><td>${this._esc(name)}</td><td>${val}</td><td>${this._esc(note)}</td></tr>`;
    });
    html += '</tbody></table></div>';

    const supports = Array.isArray(src.support_levels) ? src.support_levels : [];
    const resists = Array.isArray(src.resistance_levels) ? src.resistance_levels : [];
    html += '<div class="gms-score-detail-section"><strong>【KDE 支撑 / 阻力】</strong>';
    html += '<div class="gms-version-meta-line">';
    html += `<span>支撑 ${supports.length ? supports.map((x) => this._fmt(x, 2)).join('、') : '--'}</span>`;
    html += `<span>阻力 ${resists.length ? resists.map((x) => this._fmt(x, 2)).join('、') : '--'}</span>`;
    if (detail.kde_reason) html += `<span>KDE ${this._esc(detail.kde_reason)}</span>`;
    html += '</div>';
    const plan = src.structure_plan || {};
    if (plan.exit_rule) {
      html += `<p class="urt-buy-logic-detail">离场规则：${this._esc(plan.exit_rule)} — ${this._esc(
        plan.note || '收盘跌破结构支撑'
      )}</p>`;
    }
    html += '</div>';

    html += '</div>';
    return html;
  },
};

if (typeof window !== 'undefined') {
  window.RpeScoreDetail = RpeScoreDetail;
}

/**
 * SBBR 做小做底明细 HTML（选股页展开，风格对齐 GMS/URT/RPE）
 */
const SbbrScoreDetail = {
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

  _bottomModeLabel(mode) {
    if (mode === 'range_accumulation') return '横盘收集 range_accumulation';
    if (mode === 'panic_accumulation') return '打压恐慌 panic_accumulation';
    return mode || '--';
  },

  _sizeReasonText(code) {
    const map = {
      ok: '总市值与流通股本均落在区间内',
      out_of_range: '总市值或流通股本超出区间',
      total_only: '仅校验总市值（流通股本缺失）',
      circ_shares_only: '仅校验流通股本（总市值缺失）',
      unknown_shares: '总市值与流通股本均缺失',
    };
    return map[code] || code || '--';
  },

  _entryReasonText(code) {
    const map = {
      ok: '入场子条件全部满足',
      no_bottom: '筑底未成立，不评估入场',
      insufficient_bars: 'K 线不足',
      no_ma: '无法计算 MA20',
      rules_not_met: '上穿/缩量/微放量/大盘共振未全部满足',
    };
    return map[code] || code || '--';
  },

  _kdeReasonText(code) {
    const map = {
      ok: 'KDE 识别成功',
      insufficient_samples: '有效价量样本不足',
      no_bars: '缺少行情',
      ok_histogram_fallback: '已用直方图回退',
    };
    return map[code] || code || '--';
  },

  /**
   * @param {object} row 选股行数据（含 detail 快照）
   * @returns {string} HTML
   */
  buildHtml(row) {
    const src = row && typeof row === 'object' ? row : {};
    const detail = src.detail && typeof src.detail === 'object' ? src.detail : {};
    const entryD = detail.entry && typeof detail.entry === 'object' ? detail.entry : {};
    const bottomD = detail.bottom && typeof detail.bottom === 'object' ? detail.bottom : {};
    const structD = detail.structure && typeof detail.structure === 'object' ? detail.structure : {};
    const pos = src.position_advice && typeof src.position_advice === 'object' ? src.position_advice : {};
    const sc = src.support_confirm && typeof src.support_confirm === 'object' ? src.support_confirm : null;

    const pick = (...vals) => {
      for (let i = 0; i < vals.length; i += 1) {
        if (vals[i] != null && vals[i] !== '') return vals[i];
      }
      return null;
    };

    const entrySignal = !!src.entry_signal;
    const entryClass = entrySignal ? 'strength-high' : 'strength-low';
    const crossUp = pick(entryD.cross_up, src.cross_up);
    const shrinkOk = pick(entryD.shrink_ok, src.shrink_ok);
    const expandOk = pick(entryD.expand_ok, src.expand_ok);
    const marketOk = pick(entryD.market_ok, src.market_ok);
    const entryReason = pick(entryD.reason, src.entry_reason, src.reason);
    const volumeRatio = pick(src.volume_ratio, entryD.volume_ratio);
    const ma20 = pick(src.ma20, entryD.ma20);
    const entryLow = pick(src.entry_low, entryD.entry_low);
    const sizeReason = src.size_reason;
    const kdeOk = pick(src.kde_ok, structD.kde_ok);
    const kdeReason = pick(src.kde_reason, structD.kde_reason);
    const kdeLookback = pick(src.kde_lookback_used, structD.kde_lookback_used);
    const nearSup = pick(src.nearest_support, structD.nearest_support);
    const nearRes = pick(src.nearest_resistance, structD.nearest_resistance);
    const boxSup = pick(src.box_support, detail.support);
    const boxRes = pick(src.box_resistance, detail.resistance);

    let html = '<div class="gms-score-detail-inner sbbr-score-detail-inner">';
    html += '<div class="gms-score-detail-meta">';
    html += '<div class="gms-version-meta-line">';
    html += '<span class="gms-version-name">做小做底策略（SBBR）</span>';
    html += `<span>日期 ${this._esc(src.date || '--')}</span>`;
    html += `<span>筑底 ${this._esc(this._bottomModeLabel(src.bottom_mode))}</span>`;
    html += `<span>入场 <span class="${entryClass}">${entrySignal ? '是' : '否'}</span></span>`;
    if (src.size_ok != null) {
      html += `<span>做小 ${src.size_ok ? '通过' : '未通过'}</span>`;
    }
    html += '</div></div>';

    // 【做小】
    html += '<div class="gms-score-detail-section"><strong>【做小过滤】</strong>';
    html +=
      '<p class="urt-buy-logic-detail">默认口径：总市值 20～200 <strong>亿元</strong>，且流通股本 5～10 <strong>亿股</strong>（字段 circ_shares_yi；流通市值不参与默认过滤）。</p>';
    html +=
      '<table class="gms-weight-table"><thead><tr><th>指标</th><th>取值</th><th>说明</th></tr></thead><tbody>';
    html += `<tr><td>总市值</td><td>${this._fmt(src.total_mv, 2)} 亿元</td><td>total_shares × 收盘 / 1e8</td></tr>`;
    html += `<tr><td>流通股本</td><td>${this._fmt(
      pick(src.circ_shares_yi, detail.circ_shares_yi),
      2
    )} 亿股</td><td>free_float_shares / 1e8（单位亿股，非亿元）</td></tr>`;
    if (src.circ_mv != null) {
      html += `<tr><td>流通市值</td><td>${this._fmt(src.circ_mv, 2)} 亿元</td><td>仅展示，不参与默认过滤</td></tr>`;
    }
    html += `<tr><td>size_ok</td><td>${this._passLabel(src.size_ok)}</td><td>${this._esc(
      this._sizeReasonText(sizeReason)
    )}</td></tr>`;
    html += '</tbody></table></div>';

    // 【筑底】
    html += '<div class="gms-score-detail-section"><strong>【筑底识别】</strong>';
    html += `<p class="urt-buy-logic-formula">模式：${this._esc(
      this._bottomModeLabel(src.bottom_mode)
    )} · 命中 ${src.bottom_matched == null ? '--' : src.bottom_matched ? '是' : '否'}</p>`;
    html +=
      '<table class="gms-weight-table"><thead><tr><th>字段</th><th>取值</th><th>说明</th></tr></thead><tbody>';
    html += `<tr><td>箱体支撑</td><td>${this._fmt(boxSup, 2)}</td><td>bottom.support / 横盘下沿或恐慌日低点</td></tr>`;
    html += `<tr><td>箱体阻力</td><td>${this._fmt(boxRes, 2)}</td><td>bottom.resistance（黄金坑常无）</td></tr>`;

    if (bottomD.range || bottomD.panic) {
      const rg = bottomD.range && typeof bottomD.range === 'object' ? bottomD.range : {};
      const pk = bottomD.panic && typeof bottomD.panic === 'object' ? bottomD.panic : {};
      if (rg.reason || rg.vol_ok != null || rg.touch_ok != null) {
        html += `<tr><td>横盘要点</td><td>${this._esc(
          rg.reason ||
            `量价${rg.vol_ok ? 'OK' : '否'} · 触底${rg.touch_ok ? 'OK' : '否'} · 触及日 ${(
              rg.touch_dates || []
            ).join(',') || '--'}`
        )}</td><td>未命中时的 range 诊断</td></tr>`;
      }
      if (pk.reason || pk.panic_date || pk.reclaim != null) {
        html += `<tr><td>恐慌要点</td><td>${this._esc(
          pk.reason ||
            `恐慌日 ${pk.panic_date || '--'} · 收复MA20 ${
              pk.reclaim == null ? '--' : pk.reclaim ? '是' : '否'
            }`
        )}</td><td>未命中时的 panic 诊断</td></tr>`;
      }
    } else {
      if (bottomD.vol_ok != null || bottomD.touch_ok != null) {
        html += `<tr><td>量价配合</td><td>${this._passLabel(bottomD.vol_ok)}</td><td>上涨日均量 &gt; 下跌日均量</td></tr>`;
        html += `<tr><td>触底次数</td><td>${this._passLabel(bottomD.touch_ok)}</td><td>触及日 ${(
          bottomD.touch_dates || []
        ).join('、') || '--'}</td></tr>`;
        if (bottomD.up_vol_avg != null) {
          html += `<tr><td>涨/跌均量</td><td>${this._fmt(bottomD.up_vol_avg, 0)} / ${this._fmt(
            bottomD.down_vol_avg,
            0
          )}</td><td>横盘窗口量价</td></tr>`;
        }
      }
      if (bottomD.panic_date) {
        html += `<tr><td>恐慌日</td><td>${this._esc(bottomD.panic_date)}</td><td>个股急跌且大盘同步走弱</td></tr>`;
        html += `<tr><td>收复 MA20</td><td>${this._passLabel(bottomD.reclaim)}</td><td>last ${this._fmt(
          bottomD.last_close,
          2
        )} / MA20 ${this._fmt(bottomD.ma20, 2)}</td></tr>`;
      }
      if (bottomD.reason) {
        html += `<tr><td>原因</td><td>${this._esc(bottomD.reason)}</td><td>detail.bottom.reason</td></tr>`;
      }
      if (bottomD.range_pct != null) {
        html += `<tr><td>振幅</td><td>${this._fmt(bottomD.range_pct, 4)}</td><td>range_pct</td></tr>`;
      }
    }
    html += '</tbody></table></div>';

    // 【入场】
    html += '<div class="gms-score-detail-section"><strong>【入场判断逻辑】</strong>';
    html +=
      '<p class="urt-buy-logic-formula">入场 = 筑底成立 AND 收盘上穿 MA20 AND 底部缩量 AND 当日微放量 AND 大盘共振</p>';
    html +=
      '<p class="urt-buy-logic-detail">上穿：昨收≤昨MA20 且 今收&gt;今MA20；缩量：近5日均量/更早5日均量≤0.7；微放量：当日量/近5日均量 ∈ [1.05, 1.8]；大盘：近5日累计收益≤-1%（无大盘数据时默认不阻断）。</p>';
    html +=
      '<table class="gms-weight-table"><thead><tr><th>条件</th><th>规则</th><th>实际值</th><th>结果</th></tr></thead><tbody>';
    html += `<tr><td>筑底前置</td><td>bottom_matched</td><td>${
      src.bottom_matched == null ? '--' : src.bottom_matched ? '是' : '否'
    }</td><td>${this._passLabel(src.bottom_matched)}</td></tr>`;
    html += `<tr><td>上穿 MA20</td><td>昨收≤昨MA20 且 今收&gt;今MA20</td><td>收 ${this._fmt(
      src.close,
      2
    )} / MA20 ${this._fmt(ma20, 2)}</td><td>${this._passLabel(crossUp)}</td></tr>`;
    html += `<tr><td>底部缩量</td><td>近5均量/更早5均量 ≤ 0.7</td><td>${
      shrinkOk == null ? '--' : shrinkOk ? '满足' : '未满足'
    }</td><td>${this._passLabel(shrinkOk)}</td></tr>`;
    html += `<tr><td>当日微放量</td><td>量比 ∈ [1.05, 1.8]</td><td>量比 ${this._fmt(
      volumeRatio,
      2
    )}</td><td>${this._passLabel(expandOk)}</td></tr>`;
    html += `<tr><td>大盘共振</td><td>近5日累计 ≤ -1%</td><td>${
      marketOk == null ? '--' : marketOk ? '满足/放行' : '未满足'
    }</td><td>${this._passLabel(marketOk)}</td></tr>`;
    html += `<tr><td>入场低点</td><td>信号日最低价（防守锚点）</td><td>${this._fmt(
      entryLow,
      2
    )}</td><td>--</td></tr>`;
    html += '</tbody></table>';
    html += `<p class="urt-buy-logic-conclusion">结论：${this._esc(
      this._entryReasonText(entryReason)
    )} → 入场 <span class="${entryClass}">${entrySignal ? '是' : '否'}</span></p>`;
    html += '</div>';

    // 【防守】
    html += '<div class="gms-score-detail-section"><strong>【弹性防守】</strong>';
    html +=
      '<p class="urt-buy-logic-detail">以入场低点为锚：defense_high = anchor，defense_low = anchor × (1 − buffer)；默认 buffer 约 3%。</p>';
    html +=
      '<table class="gms-weight-table"><thead><tr><th>字段</th><th>取值</th><th>说明</th></tr></thead><tbody>';
    html += `<tr><td>defense_high</td><td>${this._fmt(src.defense_high, 2)}</td><td>防守上沿（通常=入场低点）</td></tr>`;
    html += `<tr><td>defense_low</td><td>${this._fmt(src.defense_low, 2)}</td><td>防守下沿；收盘跌破则破位</td></tr>`;
    const buf = src.defense_buffer_pct;
    html += `<tr><td>buffer</td><td>${
      buf == null ? '--' : `${(Number(buf) * 100).toFixed(1)}%`
    }</td><td>defense_buffer_pct</td></tr>`;
    html += '</tbody></table></div>';

    // 【结构位 KDE】
    html += '<div class="gms-score-detail-section"><strong>【结构位 / KDE】</strong>';
    html += '<div class="gms-version-meta-line">';
    html += `<span>最近支撑 <strong>${this._fmt(nearSup, 2)}</strong></span>`;
    html += `<span>最近阻力 <strong>${this._fmt(nearRes, 2)}</strong></span>`;
    if (kdeOk != null) html += `<span>KDE ${kdeOk ? '成功' : '未识别'}</span>`;
    if (kdeLookback != null) html += `<span>回看 ${kdeLookback} 日</span>`;
    if (src.price_adjust === 'qfq') html += '<span>前复权</span>';
    if (kdeReason) html += `<span>${this._esc(this._kdeReasonText(kdeReason))}</span>`;
    html += '</div>';
    const supports = Array.isArray(src.support_levels) ? src.support_levels : [];
    const resists = Array.isArray(src.resistance_levels) ? src.resistance_levels : [];
    if (supports.length || resists.length) {
      html +=
        '<table class="gms-weight-table"><thead><tr><th>类型</th><th>价位（近→远）</th></tr></thead><tbody>';
      html += `<tr><td>阻力</td><td>${
        resists.length ? resists.map((x) => this._fmt(x, 2)).join('、') : '--'
      }</td></tr>`;
      html += `<tr><td>支撑</td><td>${
        supports.length ? supports.map((x) => this._fmt(x, 2)).join('、') : '--'
      }</td></tr>`;
      html += '</tbody></table>';
    }
    html += '</div>';

    // 【仓位建议 / 支撑确认】
    const hasPos = pos && (pos.next_action || pos.message || pos.probe_pct != null);
    if (hasPos || sc) {
      html += '<div class="gms-score-detail-section"><strong>【仓位建议 / 支撑确认】</strong>';
      if (hasPos) {
        html += '<div class="gms-version-meta-line">';
        html += `<span>建议动作 ${this._esc(pos.next_action || '--')}</span>`;
        if (pos.next_pct != null) html += `<span>建议仓位 ${this._fmt(pos.next_pct, 0)}%</span>`;
        if (pos.probe_pct != null) html += `<span>试探 ${this._fmt(pos.probe_pct, 0)}%</span>`;
        if (pos.add_pct != null) html += `<span>追加 ${this._fmt(pos.add_pct, 0)}%</span>`;
        if (pos.reserve_cash_pct != null) {
          html += `<span>保留现金 ${this._fmt(pos.reserve_cash_pct, 0)}%</span>`;
        }
        html += '</div>';
        if (pos.message) {
          html += `<p class="urt-buy-logic-detail">${this._esc(pos.message)}</p>`;
        }
      }
      if (sc) {
        html += `<p class="urt-buy-logic-conclusion">上方支撑确认：${
          sc.confirmed ? '<span class="strength-high">是</span>' : '<span class="strength-low">否</span>'
        }${sc.reason ? `（${this._esc(sc.reason)}）` : ''}</p>`;
      }
      html += '</div>';
    }

    html += '</div>';
    return html;
  },
};

if (typeof window !== 'undefined') {
  window.SbbrScoreDetail = SbbrScoreDetail;
}

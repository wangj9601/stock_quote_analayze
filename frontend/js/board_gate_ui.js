/**
 * 板块入场闸门展示工具（市场分析 / 板块详情 / 板块分析共用）
 */
(function (global) {
  const API = typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : '';

  const STATE_CLASS = {
    可配: 'bgate-alloc',
    观望: 'bgate-watch',
    回避: 'bgate-avoid',
  };

  const CONFLICT_LABEL = {
    hold_no_new: '持有不新开',
    ultrashort_only: '仅超短',
    block_new_buy: '禁新开',
    downweight: '降权',
    full: '全量',
    neutral: '—',
  };

  const CONFLICT_CLASS = {
    hold_no_new: 'bgate-tone-warn',
    ultrashort_only: 'bgate-tone-warn',
    block_new_buy: 'bgate-tone-avoid',
    downweight: 'bgate-tone-muted',
    full: 'bgate-tone-alloc',
    neutral: 'bgate-tone-muted',
  };

  const STAGE_LABEL = {
    accumulate: '吸筹',
    markup: '主升',
    distribute: '分流',
    decline: '衰退',
    churn: '震荡',
  };

  const STAGE_CLASS = {
    accumulate: 'bgate-stage-acc',
    markup: 'bgate-stage-up',
    distribute: 'bgate-stage-dist',
    decline: 'bgate-stage-down',
    churn: 'bgate-stage-churn',
  };

  const SHADOW_LABEL = {
    would_block_new_buy: '将拦截新开',
    would_ultrashort_only: '将限超短',
    would_hold_no_new: '将禁加仓',
    would_downweight: '将降权',
    would_full: '将全量',
    neutral: '—',
  };

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function stateChip(state, opts) {
    const st = String(state || '').trim();
    if (!st) {
      const empty = (opts && opts.emptyLabel) || '未评估';
      return `<span class="bgate-chip bgate-muted" title="${esc(empty)}">${esc(empty)}</span>`;
    }
    const cls = STATE_CLASS[st] || 'bgate-muted';
    const title = (opts && opts.title) || st;
    return `<span class="bgate-chip ${cls}" title="${esc(title)}">${esc(st)}</span>`;
  }

  function midlongChip(row) {
    if (!row) return stateChip(null);
    if (row.board_kind === 'concept') {
      return `<span class="bgate-chip bgate-muted" title="概念板不跑中长线可配">—</span>`;
    }
    if (!row.trade_observe_flag && !row.midlong_state) {
      return `<span class="bgate-chip bgate-muted" title="非观察池行业，中长线不评估">未评估</span>`;
    }
    return stateChip(row.midlong_state);
  }

  function conflictLabel(code) {
    const k = String(code || '').trim();
    return CONFLICT_LABEL[k] || k || '—';
  }

  function conflictChip(code) {
    const k = String(code || '').trim();
    const label = conflictLabel(k);
    const cls = CONFLICT_CLASS[k] || 'bgate-tone-muted';
    return `<span class="bgate-chip ${cls}">${esc(label)}</span>`;
  }

  function stageLabel(code) {
    const k = String(code || '').trim();
    return STAGE_LABEL[k] || k || '—';
  }

  function stageChip(code) {
    const k = String(code || '').trim();
    if (!k) return `<span class="bgate-chip bgate-muted">—</span>`;
    const cls = STAGE_CLASS[k] || 'bgate-stage-churn';
    return `<span class="bgate-chip ${cls}">${esc(stageLabel(k))}</span>`;
  }

  function shadowLabel(code) {
    const k = String(code || '').trim();
    if (!k) return '—';
    return SHADOW_LABEL[k] || k;
  }

  function evidenceObj(row) {
    const e = row && row.evidence_json;
    if (!e) return {};
    if (typeof e === 'object') return e;
    try {
      return JSON.parse(e);
    } catch (_) {
      return {};
    }
  }

  function degradedObj(row) {
    const e = row && row.degraded_json;
    if (!e) return {};
    if (typeof e === 'object') return e;
    try {
      return JSON.parse(e);
    } catch (_) {
      return {};
    }
  }

  async function fetchGateDaily(boardCode, boardKind, boardCodeSource) {
    const q = new URLSearchParams({
      board_code: String(boardCode || '').trim(),
      board_kind: boardKind === 'concept' ? 'concept' : 'industry',
      board_code_source: boardCodeSource || 'tonghuashun',
    });
    const resp = await fetch(`${API}/api/board_gate/daily?${q}`);
    const json = await resp.json().catch(() => ({}));
    if (!resp.ok || !json.success) {
      throw new Error((json && json.message) || `闸门查询失败 HTTP ${resp.status}`);
    }
    return json.data || null;
  }

  async function fetchGateList(params) {
    const q = new URLSearchParams();
    const p = params || {};
    if (p.trade_date) q.set('trade_date', p.trade_date);
    if (p.board_kind) q.set('board_kind', p.board_kind);
    if (p.short_state) q.set('short_state', p.short_state);
    if (p.midlong_state) q.set('midlong_state', p.midlong_state);
    if (p.observe_only) q.set('observe_only', 'true');
    q.set('limit', String(p.limit || 200));
    const resp = await fetch(`${API}/api/board_gate/list?${q}`);
    const json = await resp.json().catch(() => ({}));
    if (!resp.ok || !json.success) {
      throw new Error((json && json.message) || `闸门列表失败 HTTP ${resp.status}`);
    }
    return json;
  }

  function detailCardHtml(row) {
    if (!row) {
      return `<div class="bgate-empty">暂无闸门快照。跑完日终「板块入场闸门」节点后再看。</div>`;
    }
    const ev = evidenceObj(row);
    const deg = degradedObj(row);
    const fundStageCode = ev.fund_stage || '';
    const trend = ev.board_trend_label || '—';
    const rs = ev.board_rs != null ? ev.board_rs : '—';
    const val = ev.valuation || {};
    const pe = val.pe_pct != null ? `${(Number(val.pe_pct) * 100).toFixed(0)}%` : '—';
    const pb = val.pb_pct != null ? `${(Number(val.pb_pct) * 100).toFixed(0)}%` : '—';
    const degBits = [];
    (deg.short || []).forEach((x) => degBits.push(`短线 ${x}`));
    (deg.midlong || []).forEach((x) => degBits.push(`中长线 ${x}`));

    return `
      <div class="bgate-detail">
        <div class="bgate-detail-row">
          <span class="bgate-k">短线</span>${stateChip(row.short_state)}
          <span class="bgate-k">中长线</span>${midlongChip(row)}
          ${conflictChip(row.conflict_action)}
          ${stageChip(fundStageCode)}
        </div>
        <div class="bgate-detail-row bgate-detail-meta">
          <span>走势 ${esc(trend)}</span>
          <span>板 RS ${esc(String(rs))}</span>
          <span>估值分位 PE/PB ${esc(pe)} / ${esc(pb)}</span>
          <span title="硬过滤开启后的预判动作">硬开预判 ${esc(shadowLabel(row.shadow_hard_filter_hint))}</span>
        </div>
        ${
          degBits.length
            ? `<div class="bgate-detail-row"><span class="bgate-deg">数据降级：${esc(degBits.join('；'))}</span></div>`
            : ''
        }
      </div>`;
  }

  function metaInlineHtml(row) {
    if (!row) return `<span class="bgate-inline"><span class="bgate-chip bgate-muted">闸门未评估</span></span>`;
    return `<span class="bgate-inline">短线 ${stateChip(row.short_state)}<span class="bgate-sep">·</span>中长线 ${midlongChip(row)}</span>`;
  }

  global.BoardGateUI = {
    esc,
    stateChip,
    midlongChip,
    conflictLabel,
    conflictChip,
    stageLabel,
    stageChip,
    shadowLabel,
    evidenceObj,
    degradedObj,
    fetchGateDaily,
    fetchGateList,
    detailCardHtml,
    metaInlineHtml,
  };
})(typeof window !== 'undefined' ? window : globalThis);

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
    hold_no_new: '长可配·短回避：持有不新开',
    ultrashort_only: '短可配·长回避：仅超短',
    block_new_buy: '回避：不新开',
    downweight: '观望：降权',
    full: '可配：全量',
    neutral: '中性',
  };

  const STAGE_LABEL = {
    accumulate: '吸筹',
    markup: '主升',
    distribute: '分流',
    decline: '衰退',
    churn: '震荡',
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
    if (!st) return `<span class="bgate-chip bgate-muted">--</span>`;
    const cls = STATE_CLASS[st] || 'bgate-muted';
    const title = (opts && opts.title) || st;
    return `<span class="bgate-chip ${cls}" title="${esc(title)}">${esc(st)}</span>`;
  }

  function conflictLabel(code) {
    const k = String(code || '').trim();
    return CONFLICT_LABEL[k] || k || '--';
  }

  function stageLabel(code) {
    const k = String(code || '').trim();
    return STAGE_LABEL[k] || k || '--';
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
      return `<div class="bgate-empty">暂无闸门快照（需日终 board_gates_daily 跑过后才有）</div>`;
    }
    const ev = evidenceObj(row);
    const deg = degradedObj(row);
    const fundStage = stageLabel(ev.fund_stage || (ev.short && ev.short.fund_stage));
    const trend = ev.board_trend_label || '--';
    const rs = ev.board_rs != null ? ev.board_rs : '--';
    const val = ev.valuation || {};
    const pe = val.pe_pct != null ? `${(Number(val.pe_pct) * 100).toFixed(0)}%` : '--';
    const pb = val.pb_pct != null ? `${(Number(val.pb_pct) * 100).toFixed(0)}%` : '--';
    const degBits = [];
    (deg.short || []).forEach((x) => degBits.push(`短:${x}`));
    (deg.midlong || []).forEach((x) => degBits.push(`长:${x}`));
    const midShow =
      row.board_kind === 'concept'
        ? '<span class="bgate-muted">概念不跑中长线可配</span>'
        : stateChip(row.midlong_state);

    return `
      <div class="bgate-detail">
        <div class="bgate-detail-row">
          <span class="bgate-k">短线</span>${stateChip(row.short_state)}
          <span class="bgate-k">中长线</span>${midShow}
        </div>
        <div class="bgate-detail-row bgate-detail-meta">
          <span>冲突：${esc(conflictLabel(row.conflict_action))}</span>
          <span>阶段：${esc(fundStage)}</span>
          <span>走势：${esc(trend)}</span>
          <span>板RS：${esc(String(rs))}</span>
          <span>估值分位 PE/PB：${esc(pe)} / ${esc(pb)}</span>
        </div>
        <div class="bgate-detail-row bgate-detail-meta">
          <span>Shadow：${esc(row.shadow_hard_filter_hint || '--')}</span>
          <span>v2：${row.v2_enabled ? '开' : '关'}</span>
          ${degBits.length ? `<span class="bgate-deg">降级：${esc(degBits.join('；'))}</span>` : ''}
        </div>
      </div>`;
  }

  function metaInlineHtml(row) {
    if (!row) return `<span class="bgate-inline bgate-muted">闸门 --</span>`;
    const mid =
      row.board_kind === 'concept'
        ? ''
        : ` <span class="bgate-sep">·</span> 中长线 ${stateChip(row.midlong_state)}`;
    return `<span class="bgate-inline">短线 ${stateChip(row.short_state)}${mid}</span>`;
  }

  global.BoardGateUI = {
    esc,
    stateChip,
    conflictLabel,
    stageLabel,
    evidenceObj,
    degradedObj,
    fetchGateDaily,
    fetchGateList,
    detailCardHtml,
    metaInlineHtml,
  };
})(typeof window !== 'undefined' ? window : globalThis);

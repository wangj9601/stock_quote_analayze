/**
 * 行业/概念指数分析里的单板块资金位置与相对轮动。
 */
(function (global) {
    const QUADRANTS = {
        leading: { name: '领先', color: '#d61f28' },
        weakening: { name: '转弱', color: '#c9a227' },
        lagging: { name: '落后', color: '#0f9d5c' },
        improving: { name: '改善', color: '#6f8cff' },
        neutral: { name: '中性', color: '#8b9aab' },
    };

    function esc(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function formatYi(yi) {
        const number = Number(yi);
        if (!Number.isFinite(number)) return '--';
        const sign = number > 0 ? '+' : '';
        if (Math.abs(number) >= 1) return `${sign}${number.toFixed(2)}亿`;
        return `${sign}${(number * 10000).toFixed(0)}万`;
    }

    function formatPercent(value) {
        const number = Number(value);
        if (!Number.isFinite(number)) return '--';
        const sign = number > 0 ? '+' : '';
        return `${sign}${number.toFixed(2)}%`;
    }

    function toneClass(value) {
        const number = Number(value);
        if (!Number.isFinite(number) || number === 0) return '';
        return number > 0 ? 'is-up' : 'is-down';
    }

    function formatNum(value) {
        const number = Number(value);
        if (!Number.isFinite(number)) return '--';
        return number.toFixed(2);
    }

    function render(data, prefix) {
        const block = document.getElementById(`${prefix}FlowBlock`);
        const host = document.getElementById(`${prefix}FlowHost`);
        if (!block || !host) return;
        const focus = (data && data.flow_focus) || null;
        block.hidden = false;
        if (!focus || focus.available !== true || !focus.flow) {
            host.innerHTML = `<p class="ssa-block-status">${esc((focus && focus.note) || '资金与相对轮动暂不可用')}</p>`;
            return;
        }
        const flow = focus.flow;
        const rotation = focus.rotation || {};
        const signal = focus.signal || {};
        const level = ['strong', 'risk', 'watch', 'unknown'].indexOf(signal.signal_level) >= 0
            ? signal.signal_level
            : 'unknown';
        const dateNote = focus.date_note
            ? `<span class="ssa-flow-note"> · ${esc(focus.date_note)}</span>`
            : '';
        const trail = Array.isArray(rotation.trail) ? rotation.trail : [];
        const dots = trail.map((point, index) => {
            const tone = QUADRANTS[point.quadrant] || QUADRANTS.neutral;
            const label = point.label || tone.name;
            const title = `${point.trade_date || ''} ${label}`.trim();
            const now = index === trail.length - 1 ? ' is-now' : '';
            return `<i class="ssa-flow-dot ssa-flow-dot--${esc(point.quadrant || 'neutral')}${now}" title="${esc(title)}"></i>`;
        }).join('');
        const quad = esc(rotation.quadrant || 'neutral');
        const legend = ['leading', 'weakening', 'lagging', 'improving'].map((key) => {
            const tone = QUADRANTS[key];
            return `<span class="ssa-flow-legend-item"><i class="ssa-flow-dot ssa-flow-dot--${key}"></i>${tone.name}</span>`;
        }).join('');
        const rotationHtml = rotation.available
            ? `<div class="ssa-flow-rotation">
                <p>相对${esc(rotation.benchmark_name || '沪深300')}
                · <span class="ssa-flow-quad ssa-flow-quad--${quad}">${esc(rotation.label || '--')}</span>
                · RS-Ratio ${formatNum(rotation.rs_ratio)}
                · RS-Momentum ${formatNum(rotation.rs_momentum)}
                · 平滑 ${esc(rotation.window || 10)} 日</p>
                <div class="ssa-flow-trail" aria-label="近端轮动轨迹">${dots}</div>
                <p class="ssa-flow-legend">${legend}</p>
               </div>`
            : `<p class="ssa-block-status">${esc(rotation.note || '相对轮动暂不可用')}</p>`;
        host.innerHTML = `
            <p class="ssa-flow-date">资金日 ${esc(focus.trade_date || '--')}${dateNote}</p>
            <div class="ssa-flow-grid">
                <div class="ssa-fund-flow-metric"><span>涨跌幅</span><strong class="${toneClass(flow.change_percent)}">${formatPercent(flow.change_percent)}</strong></div>
                <div class="ssa-fund-flow-metric"><span>主力净流入</span><strong class="${toneClass(flow.main_net_yi)}">${formatYi(flow.main_net_yi)}</strong></div>
                <div class="ssa-fund-flow-metric"><span>净流入名次</span><strong>${esc(flow.net_rank)} / ${esc(flow.universe)}</strong></div>
                <div class="ssa-fund-flow-metric"><span>涨跌幅名次</span><strong>${esc(flow.change_rank)} / ${esc(flow.universe)}</strong></div>
            </div>
            <p class="ssa-flow-signal ssa-flow-signal--${level}">
                <strong>${esc(signal.signal_label || '未覆盖')}</strong>
                <span>${esc(signal.signal_note || '')}</span>
            </p>
            ${rotationHtml}
        `;
    }

    global.BoardFlowFocus = { render: render };
})(typeof window !== 'undefined' ? window : globalThis);

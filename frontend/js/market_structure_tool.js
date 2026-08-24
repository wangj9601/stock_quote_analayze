/**
 * 波段与趋势结构（Market Structure）展示工具
 * 与个股分析 / PDF 同口径；轻量 SVG ZigZag 折线（非完整 K 线叠加）。
 */
const MarketStructureTool = {
    API_BASE_URL: typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : '',

    esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    },

    adjustLabel(pa) {
        if (!pa) return '不复权';
        if (typeof pa === 'string') return pa === 'qfq' ? '前复权' : '不复权';
        const mode = pa.mode || pa.adjust || 'none';
        return mode === 'qfq' ? '前复权' : '不复权';
    },

    trendClass(trend) {
        if (trend === 'uptrend') return 'ms-trend--up';
        if (trend === 'downtrend') return 'ms-trend--down';
        if (trend === 'transition') return 'ms-trend--trans';
        if (trend === 'range') return 'ms-trend--range';
        return 'ms-trend--na';
    },

    async fetchStructure(code, opts) {
        const o = opts || {};
        const params = new URLSearchParams();
        params.set('adjust', o.adjust || 'qfq');
        params.set('factor_source', o.factor_source || 'auto');
        params.set('lookback', String(o.lookback || 180));
        params.set('max_points', String(o.max_points || 12));
        if (o.asof) params.set('asof', o.asof);
        if (o.pattern_short_bias) params.set('pattern_short_bias', o.pattern_short_bias);
        const url = `${this.API_BASE_URL}/api/analysis/market-structure/${encodeURIComponent(code)}?${params}`;
        const resp = await fetch(url, { credentials: 'include' });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
            const detail = data.detail;
            let msg = data.message || data.error || `HTTP ${resp.status}`;
            if (typeof detail === 'string') msg = detail;
            else if (detail && detail.message) msg = detail.message;
            throw new Error(msg);
        }
        return data;
    },

    /** 简单 ZigZag 折线 SVG（价-时间示意，非蜡烛图） */
    buildZigzagSvg(points, opts) {
        const o = opts || {};
        const showPrice = o.showPrice !== false;
        const pts = (Array.isArray(points) ? points : []).filter(
            (p) => p && p.price != null && Number.isFinite(Number(p.price))
        );
        if (pts.length < 2) return '';
        const w = 520;
        const h = showPrice ? 168 : 140;
        const padX = 28;
        const padY = showPrice ? 28 : 18;
        const prices = pts.map((p) => Number(p.price));
        const minP = Math.min(...prices);
        const maxP = Math.max(...prices);
        const span = maxP - minP || 1;
        const n = pts.length;
        const xy = pts.map((p, i) => {
            const x = padX + (i / Math.max(1, n - 1)) * (w - padX * 2);
            const y = padY + (1 - (Number(p.price) - minP) / span) * (h - padY * 2);
            return { x, y, p };
        });
        const poly = xy.map((c) => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(' ');
        const dots = xy
            .map((c) => {
                const st = String(c.p.structure || '—');
                const fill =
                    st === 'HH' || st === 'HL'
                        ? '#16a34a'
                        : st === 'LH' || st === 'LL'
                          ? '#dc2626'
                          : '#64748b';
                const kind = String(c.p.kind || '');
                // 高点标签在点上方，低点在下方，减少与折线重叠
                const above = kind !== 'low';
                const px = Number(c.p.price);
                const pxTxt = Number.isFinite(px) ? px.toFixed(2) : '';
                const labelMain = this.esc(st);
                const labelPrice = showPrice && pxTxt ? this.esc(pxTxt) : '';
                if (!labelPrice) {
                    const ty = above ? c.y - 7 : c.y + 12;
                    return (
                        `<circle cx="${c.x.toFixed(1)}" cy="${c.y.toFixed(1)}" r="3.5" fill="${fill}"/>` +
                        `<text x="${c.x.toFixed(1)}" y="${ty.toFixed(1)}" text-anchor="middle" ` +
                        `font-size="9" fill="#334155">${labelMain}</text>`
                    );
                }
                const y1 = above ? c.y - 18 : c.y + 12;
                const y2 = above ? c.y - 7 : c.y + 23;
                return (
                    `<circle cx="${c.x.toFixed(1)}" cy="${c.y.toFixed(1)}" r="3.5" fill="${fill}"/>` +
                    `<text x="${c.x.toFixed(1)}" y="${y1.toFixed(1)}" text-anchor="middle" ` +
                    `font-size="9" font-weight="600" fill="${fill}">${labelMain}</text>` +
                    `<text x="${c.x.toFixed(1)}" y="${y2.toFixed(1)}" text-anchor="middle" ` +
                    `font-size="8" fill="#475569">${labelPrice}</text>`
                );
            })
            .join('');
        return (
            `<svg class="ms-zigzag-svg" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" role="img" ` +
            `aria-label="ZigZag 波段折线">` +
            `<polyline fill="none" stroke="#94a3b8" stroke-width="1.5" points="${poly}"/>` +
            dots +
            `</svg>`
        );
    },

    renderEmbedded(host, payload, opts) {
        if (!host) return;
        const o = opts || {};
        const ms = (payload && payload.market_structure) || payload || {};
        const code = (payload && payload.code) || o.code || '';
        const name = (payload && payload.name) || o.name || '';
        const asof = (payload && payload.asof) || ms.asof || '';
        const pa = (payload && payload.price_adjust) || o.price_adjust;
        const points = ms.points || ms.zigzag || [];
        const trend = ms.trend || 'insufficient';
        const trendLabel = ms.trend_label || trend;
        const bos = ms.last_bos_like;
        const contrast = ms.pattern_contrast || o.pattern_contrast || null;
        const summary = ms.summary || '';

        let table = '';
        if (points.length) {
            table =
                '<table class="ms-points-table"><thead><tr>' +
                '<th>日期</th><th>类型</th><th>价格</th><th>标注</th>' +
                '</tr></thead><tbody>';
            points.forEach((p) => {
                const kind = p.kind === 'high' ? '高点' : p.kind === 'low' ? '低点' : '--';
                const st = p.structure || '—';
                const stCls =
                    st === 'HH' || st === 'HL'
                        ? 'ms-st--bull'
                        : st === 'LH' || st === 'LL'
                          ? 'ms-st--bear'
                          : '';
                table +=
                    `<tr><td>${this.esc(p.date || '--')}</td>` +
                    `<td>${kind}</td>` +
                    `<td>${p.price != null ? Number(p.price).toFixed(2) : '--'}</td>` +
                    `<td class="${stCls}">${this.esc(st)}</td></tr>`;
            });
            table += '</tbody></table>';
        } else {
            table = '<p class="ms-empty">暂无摆动点</p>';
        }

        const bosHtml = bos
            ? `<div class="ms-bos"><strong>关键事件：</strong>${this.esc(bos.label || bos.type)}` +
              `（位 ${bos.level != null ? Number(bos.level).toFixed(2) : '--'}` +
              `${bos.level_date ? ` @ ${this.esc(bos.level_date)}` : ''}；` +
              `收盘 ${bos.close != null ? Number(bos.close).toFixed(2) : '--'}）</div>`
            : '<div class="ms-bos ms-muted">关键事件：近期未有效越过确认摆动高/低</div>';

        const contrastHtml = contrast
            ? `<div class="ms-contrast">${this.esc(contrast)}</div>`
            : '';

        const weekly = (payload && payload.weekly) || o.weekly || null;
        const weeklyTrend = weekly && weekly.trend ? weekly.trend : null;
        const weeklyLabel = (weekly && weekly.trend_label) || weeklyTrend || '';
        const caution =
            (payload && payload.counter_trend_note) ||
            (ms && ms.counter_trend_note) ||
            (weekly && weekly.counter_trend_note) ||
            o.counter_trend_note ||
            null;
        const dualTrendHtml =
            `<div class="ms-dual-trend">` +
            `<span class="ms-period-tag">日线</span>` +
            `<span class="ms-trend-badge ${this.trendClass(trend)}">${this.esc(trendLabel)}</span>` +
            (weeklyTrend
                ? `<span class="ms-period-tag">周线</span>` +
                  `<span class="ms-trend-badge ${this.trendClass(weeklyTrend)}">${this.esc(weeklyLabel)}</span>`
                : '<span class="ms-muted">周线：样本不足</span>') +
            `</div>`;
        const cautionHtml = caution
            ? `<div class="ms-caution">${this.esc(caution)}</div>`
            : '';

        const svg = this.buildZigzagSvg(points);
        const analysis = ms.trend_analysis || null;
        let analysisHtml = '';
        if (analysis && (analysis.paragraphs || analysis.text)) {
            const paras = Array.isArray(analysis.paragraphs) && analysis.paragraphs.length
                ? analysis.paragraphs
                : String(analysis.text || '').split('\n').filter(Boolean);
            analysisHtml =
                '<div class="ms-analysis">' +
                '<div class="ms-subtitle">趋势分析说明</div>' +
                '<ul class="ms-analysis-list">' +
                paras.map((p) => `<li>${this.esc(p)}</li>`).join('') +
                '</ul></div>';
        }

        let weeklyBlock = '';
        if (weekly && weekly.ok) {
            const wPts = weekly.points || weekly.zigzag || [];
            const wSvg = this.buildZigzagSvg(wPts);
            weeklyBlock =
                `<details class="ms-weekly-details" open>` +
                `<summary>周线摆动明细（${this.esc(weeklyLabel || weeklyTrend || '--')}）</summary>` +
                `<div class="ms-weekly-body">` +
                (weekly.summary ? `<p class="ms-summary">${this.esc(weekly.summary)}</p>` : '') +
                (weekly.pattern_contrast
                    ? `<div class="ms-contrast">${this.esc(weekly.pattern_contrast)}</div>`
                    : '') +
                (wSvg
                    ? `<div class="ms-zigzag-wrap">${wSvg}<p class="ms-muted ms-chart-hint">周线示意折线（结构标注旁为对应价格）</p></div>`
                    : '') +
                `</div></details>`;
        }

        host.innerHTML =
            `<div class="ms-result-wrap">` +
            `<div class="ms-meta">个股 ${this.esc(code)} ${this.esc(name)} · 基准日 ${this.esc(asof || '--')}` +
            ` · ${this.esc(this.adjustLabel(pa))} · ZigZag 分形</div>` +
            dualTrendHtml +
            cautionHtml +
            `<div class="ms-trend-row">` +
            `<span class="ms-summary">${this.esc(summary)}</span>` +
            `</div>` +
            contrastHtml +
            bosHtml +
            (svg ? `<div class="ms-zigzag-wrap">${svg}<p class="ms-muted ms-chart-hint">示意折线（摆动点连线，标注旁为对应价格），非完整 K 线叠加</p></div>` : '') +
            analysisHtml +
            weeklyBlock +
            `<div class="ms-subtitle">近端摆动点（HH/HL/LH/LL）·日线</div>` +
            table +
            `<p class="ms-disclaimer">规则模板，非投资建议；与形态短期三态并列，不互相覆盖；周线逆势提示不否决 URT/GMS 正式买点。</p>` +
            `</div>`;
    },

    formatPlainText(ms, meta) {
        const m = ms || {};
        const lines = [];
        if (meta && (meta.code || meta.name)) {
            lines.push(`股票：${meta.code || ''} ${meta.name || ''}`.trim());
        }
        if (m.asof) lines.push(`基准日：${m.asof}`);
        lines.push(`日线趋势：${m.trend_label || m.trend || '--'}`);
        const weekly = (meta && meta.weekly) || m.weekly || null;
        if (weekly && (weekly.trend_label || weekly.trend)) {
            lines.push(`周线趋势：${weekly.trend_label || weekly.trend}`);
        }
        if (m.counter_trend_note || (meta && meta.counter_trend_note)) {
            lines.push(m.counter_trend_note || meta.counter_trend_note);
        }
        if (m.summary) lines.push(m.summary);
        const ta = m.trend_analysis;
        if (ta) {
            lines.push('【趋势分析说明】');
            const paras = Array.isArray(ta.paragraphs) && ta.paragraphs.length
                ? ta.paragraphs
                : String(ta.text || '').split('\n').filter(Boolean);
            paras.forEach((p) => lines.push(p));
        }
        if (m.pattern_contrast) lines.push(m.pattern_contrast);
        if (m.last_bos_like) {
            const b = m.last_bos_like;
            lines.push(
                `关键事件：${b.label || b.type} @ ${b.level != null ? b.level : '--'}（${b.level_date || ''}）`
            );
        }
        const pts = m.points || [];
        if (pts.length) {
            lines.push('日线摆动点：');
            pts.forEach((p) => {
                lines.push(
                    `  ${p.date || '--'} ${p.kind === 'high' ? '高' : '低'} ${p.price != null ? p.price : '--'} ${p.structure || '—'}`
                );
            });
        }
        return lines.filter(Boolean).join('\n');
    },
};

if (typeof window !== 'undefined') {
    window.MarketStructureTool = MarketStructureTool;
}

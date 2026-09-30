/**
 * 波段与趋势结构（Market Structure）展示工具
 * 与个股分析 / PDF 同口径；轻量 SVG ZigZag 折线 + SMC 价区（OB/FVG），非完整 K 线叠加。
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

    smcEventBadge(ev) {
        if (!ev) return '';
        const t = String(ev.type || '').toUpperCase();
        const key = String(ev.event_key || '');
        const dir = ev.direction === 'bullish' ? '多' : ev.direction === 'bearish' ? '空' : '';
        const cls =
            ev.type === 'choch'
                ? 'ms-smc-badge ms-smc-badge--choch'
                : 'ms-smc-badge ms-smc-badge--bos';
        const label = key || `${t} ${dir}`;
        return `<span class="${cls}">${this.esc(label)}</span>`;
    },

    statusCls(status) {
        const s = String(status || '');
        if (s === 'active' || s === 'open') return 'ms-st--bull';
        if (s === 'partial') return 'ms-trend--trans';
        if (s === 'mitigated' || s === 'filled') return 'ms-muted';
        return '';
    },

    /**
     * 关键事件文案：仅 smc_type=choch 称 CHOCH；bos 称 BOS；其余为轻量破位（非 CHOCH）。
     */
    _formatBosEventHtml(bos) {
        if (!bos) {
            return '<div class="ms-bos ms-muted">关键事件：近期未有效越过确认摆动高/低</div>';
        }
        const smcType = String(bos.smc_type || '').toLowerCase();
        const smcKey = String(bos.smc_event_key || '');
        let title;
        let note = '';
        if (smcType === 'choch') {
            title = `CHOCH${smcKey ? ' · ' + smcKey : ''}`;
        } else if (smcType === 'bos') {
            title = `BOS${smcKey ? ' · ' + smcKey : ''}`;
            note = '（趋势延续破位，非 CHOCH）';
        } else {
            title = bos.label || bos.type || '轻量破位';
            note = '（轻量破位 ≠ CHOCH；完整性质转换见上方 SMC 徽章）';
        }
        return (
            `<div class="ms-bos"><strong>关键事件：</strong>${this.esc(title)}${this.esc(note)}` +
            `（位 ${bos.level != null ? Number(bos.level).toFixed(2) : '--'}` +
            `${bos.level_date ? ` @ ${this.esc(bos.level_date)}` : ''}；` +
            `收盘 ${bos.close != null ? Number(bos.close).toFixed(2) : '--'}）</div>`
        );
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
        if (o.use_realtime) params.set('use_realtime', 'true');
        const url = `${this.API_BASE_URL}/api/analysis/market-structure/${encodeURIComponent(code)}?${params}`;
        const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
        const fetchOpts = { credentials: 'include' };
        if (o.signal) fetchOpts.signal = o.signal;
        const resp = await fetchFn(url, fetchOpts);
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

    /** 简单 ZigZag 折线 SVG（价-时间示意，非蜡烛图）；可选 OB/FVG 价区 */
    buildZigzagSvg(points, opts) {
        const o = opts || {};
        const showPrice = o.showPrice !== false;
        const pts = (Array.isArray(points) ? points : []).filter(
            (p) => p && p.price != null && Number.isFinite(Number(p.price))
        );
        if (pts.length < 2) return '';
        const w = 520;
        const h = showPrice ? 188 : 156;
        const padX = 28;
        const padY = showPrice ? 28 : 18;
        const zones = Array.isArray(o.zones) ? o.zones : [];
        const kl = o.keyLevels || {};
        const prices = pts.map((p) => Number(p.price));
        zones.forEach((z) => {
            if (z && z.low != null) prices.push(Number(z.low));
            if (z && z.high != null) prices.push(Number(z.high));
        });
        ['nearest_support', 'nearest_resistance'].forEach((k) => {
            const v = kl[k];
            if (v != null && Number.isFinite(Number(v))) prices.push(Number(v));
        });
        if (o.lastEvent && o.lastEvent.level != null) {
            prices.push(Number(o.lastEvent.level));
        }
        const minP = Math.min(...prices);
        const maxP = Math.max(...prices);
        const span = maxP - minP || 1;
        const n = pts.length;
        const yOf = (price) =>
            padY + (1 - (Number(price) - minP) / span) * (h - padY * 2);
        const xy = pts.map((p, i) => {
            const x = padX + (i / Math.max(1, n - 1)) * (w - padX * 2);
            const y = yOf(p.price);
            return { x, y, p };
        });
        // 摆动点关键水平线 + 可选 KDE 近端支撑/阻力
        let pivotLines = '';
        if (o.showPivotLevels !== false) {
            const seen = new Set();
            pts.forEach((p) => {
                const px = Number(p.price);
                if (!Number.isFinite(px)) return;
                const key = px.toFixed(2);
                if (seen.has(key)) return;
                seen.add(key);
                const y = yOf(px);
                const col = p.kind === 'high' ? '#86efac' : '#fca5a5';
                pivotLines +=
                    `<line x1="${padX}" y1="${y.toFixed(1)}" x2="${(w - padX).toFixed(1)}" y2="${y.toFixed(1)}" ` +
                    `stroke="${col}" stroke-width="0.6" stroke-dasharray="2 3" opacity="0.55"/>`;
            });
        }
        ['nearest_support', 'nearest_resistance'].forEach((k) => {
            const v = kl[k];
            if (v == null || !Number.isFinite(Number(v))) return;
            const y = yOf(Number(v));
            const col = k === 'nearest_support' ? '#15803d' : '#b91c1c';
            const lab = k === 'nearest_support' ? '近端支撑' : '近端阻力';
            pivotLines +=
                `<line x1="${padX}" y1="${y.toFixed(1)}" x2="${(w - padX).toFixed(1)}" y2="${y.toFixed(1)}" ` +
                `stroke="${col}" stroke-width="1" stroke-dasharray="5 3" opacity="0.75"/>` +
                `<text x="${(w - padX - 2).toFixed(1)}" y="${(y - 2).toFixed(1)}" text-anchor="end" ` +
                `font-size="8" fill="${col}">${this.esc(lab)} ${Number(v).toFixed(2)}</text>`;
        });

        const zoneRects = zones
            .filter((z) => z && z.low != null && z.high != null)
            .map((z) => {
                const lo = Number(z.low);
                const hi = Number(z.high);
                const y1 = yOf(hi);
                const y2 = yOf(lo);
                const top = Math.min(y1, y2);
                const height = Math.max(2, Math.abs(y2 - y1));
                const bull = z.direction === 'bullish';
                const faded = z.status === 'mitigated' || z.status === 'filled';
                const fill = bull
                    ? faded
                        ? 'rgba(22,163,74,0.08)'
                        : 'rgba(22,163,74,0.18)'
                    : faded
                      ? 'rgba(220,38,38,0.08)'
                      : 'rgba(220,38,38,0.18)';
                const stroke = bull ? '#16a34a' : '#dc2626';
                const label = this.esc(z.label || (z.kind === 'fvg' ? 'FVG' : 'OB'));
                return (
                    `<rect x="${padX}" y="${top.toFixed(1)}" width="${(w - padX * 2).toFixed(1)}" ` +
                    `height="${height.toFixed(1)}" fill="${fill}" stroke="${stroke}" ` +
                    `stroke-width="0.8" stroke-dasharray="${z.kind === 'fvg' ? '3 2' : '0'}" opacity="${faded ? 0.55 : 0.9}"/>` +
                    `<text x="${(padX + 4).toFixed(1)}" y="${(top + 10).toFixed(1)}" ` +
                    `font-size="8" fill="${stroke}">${label}</text>`
                );
            })
            .join('');
        const poly = xy.map((c) => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(' ');
        const lastEv = o.lastEvent;
        let eventMark = '';
        if (lastEv && lastEv.level != null && Number.isFinite(Number(lastEv.level))) {
            const ey = yOf(lastEv.level);
            const et = String(lastEv.type || '').toUpperCase();
            eventMark =
                `<line x1="${padX}" y1="${ey.toFixed(1)}" x2="${(w - padX).toFixed(1)}" y2="${ey.toFixed(1)}" ` +
                `stroke="#7c3aed" stroke-width="1" stroke-dasharray="4 3"/>` +
                `<text x="${(w - padX - 4).toFixed(1)}" y="${(ey - 3).toFixed(1)}" text-anchor="end" ` +
                `font-size="8" fill="#7c3aed">${this.esc(et)}</text>`;
        }
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
            `aria-label="ZigZag 波段折线与 SMC 价区">` +
            pivotLines +
            zoneRects +
            eventMark +
            `<polyline fill="none" stroke="#94a3b8" stroke-width="1.5" points="${poly}"/>` +
            dots +
            `</svg>`
        );
    },

    _smcZonesForSvg(smc) {
        if (!smc || typeof smc !== 'object') return [];
        const zones = [];
        (smc.order_blocks || []).slice(0, 4).forEach((b) => {
            zones.push({
                kind: 'ob',
                direction: b.direction,
                low: b.low,
                high: b.high,
                status: b.status,
                label: `OB·${b.direction === 'bullish' ? '多' : '空'}·${b.status || ''}`,
            });
        });
        (smc.fvgs || [])
            .filter((f) => f && (f.status === 'open' || f.status === 'partial'))
            .slice(0, 3)
            .forEach((f) => {
                zones.push({
                    kind: 'fvg',
                    direction: f.direction,
                    low: f.low,
                    high: f.high,
                    status: f.status,
                    label: `FVG·${f.direction === 'bullish' ? '多' : '空'}`,
                });
            });
        return zones;
    },

    _isInactiveSmcStatus(status) {
        const s = String(status || '');
        return s === 'mitigated' || s === 'filled';
    },

    /** 活跃行直接展示；mitigated / filled 行收进默认折叠的 details */
    _renderSmcTable(title, headHtml, items, rowFn) {
        if (!items.length) return '';
        const active = items.filter((x) => !this._isInactiveSmcStatus(x && x.status));
        const inactive = items.filter((x) => this._isInactiveSmcStatus(x && x.status));
        const tableOf = (rows) =>
            `<table class="ms-points-table ms-smc-table"><thead><tr>${headHtml}</tr></thead><tbody>` +
            rows.map(rowFn).join('') +
            '</tbody></table>';
        let html = `<div class="ms-subtitle">${title}</div>`;
        if (active.length) {
            html += tableOf(active);
        } else {
            html += '<p class="ms-muted ms-smc-empty">暂无活跃记录</p>';
        }
        if (inactive.length) {
            html +=
                `<details class="ms-smc-inactive">` +
                `<summary>已失效（mitigated / filled）${inactive.length} 条</summary>` +
                tableOf(inactive) +
                `</details>`;
        }
        return html;
    },

    renderSmcSection(smc) {
        if (!smc || !smc.ok) {
            return '<div class="ms-smc ms-muted">SMC：样本不足或暂无结构事件</div>';
        }
        const last = smc.last_event;
        const badge = this.smcEventBadge(last);
        const summary = smc.summary ? `<p class="ms-summary">${this.esc(smc.summary)}</p>` : '';
        const obTable = this._renderSmcTable(
            '订单块 OB',
            '<th>方向</th><th>区间</th><th>状态</th><th>来源</th><th>日期</th>',
            smc.order_blocks || [],
            (b) =>
                `<tr><td>${b.direction === 'bullish' ? '看涨' : '看跌'}</td>` +
                `<td>${b.low != null ? Number(b.low).toFixed(2) : '--'} – ` +
                `${b.high != null ? Number(b.high).toFixed(2) : '--'}</td>` +
                `<td class="${this.statusCls(b.status)}">${this.esc(b.status || '--')}</td>` +
                `<td>${this.esc(b.source_event || b.event_type || '--')}</td>` +
                `<td>${this.esc(b.bar_date || '--')}</td></tr>`
        );
        const fvgTable = this._renderSmcTable(
            '公允价值缺口 FVG',
            '<th>方向</th><th>区间</th><th>状态</th><th>形成</th>',
            smc.fvgs || [],
            (f) =>
                `<tr><td>${f.direction === 'bullish' ? '看涨' : '看跌'}</td>` +
                `<td>${f.low != null ? Number(f.low).toFixed(2) : '--'} – ` +
                `${f.high != null ? Number(f.high).toFixed(2) : '--'}</td>` +
                `<td class="${this.statusCls(f.status)}">${this.esc(f.status || '--')}</td>` +
                `<td>${this.esc(f.end_date || f.start_date || '--')}</td></tr>`
        );
        const bias = smc.structure_bias
            ? `<span class="ms-muted">结构偏置 ${this.esc(smc.structure_bias)}</span>`
            : '';
        return (
            `<div class="ms-smc">` +
            `<div class="ms-subtitle">SMC 结构（CHOCH / BOS · OB · FVG） ${badge} ${bias}</div>` +
            summary +
            obTable +
            fvgTable +
            `</div>`
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

        const bosHtml = this._formatBosEventHtml(bos);

        const contrastHtml = contrast
            ? `<div class="ms-contrast ms-contrast--elevated"><strong>形态对照：</strong>${this.esc(contrast)}</div>`
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
            ? `<div class="ms-caution ms-caution--elevated" role="alert">` +
              `<strong>日周冲突：</strong>${this.esc(caution)}` +
              ` <span class="ms-muted">（并列提示，不否决策略正式买点）</span></div>`
            : '';

        const smc = ms.smc || null;
        const keyLevels = o.keyLevels || null;
        const svg = this.buildZigzagSvg(points, {
            zones: this._smcZonesForSvg(smc),
            lastEvent: smc && smc.last_event ? smc.last_event : null,
            showPivotLevels: true,
            keyLevels,
        });
        const smcHtml = this.renderSmcSection(smc);
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
            const wSmc = weekly.smc || null;
            const wSvg = this.buildZigzagSvg(wPts, {
                zones: this._smcZonesForSvg(wSmc),
                lastEvent: wSmc && wSmc.last_event ? wSmc.last_event : null,
            });
            weeklyBlock =
                `<details class="ms-weekly-details" open>` +
                `<summary>周线摆动明细（${this.esc(weeklyLabel || weeklyTrend || '--')}）</summary>` +
                `<div class="ms-weekly-body">` +
                (weekly.summary ? `<p class="ms-summary">${this.esc(weekly.summary)}</p>` : '') +
                (weekly.pattern_contrast
                    ? `<div class="ms-contrast">${this.esc(weekly.pattern_contrast)}</div>`
                    : '') +
                (wSvg
                    ? `<div class="ms-zigzag-wrap">${wSvg}<p class="ms-muted ms-chart-hint">周线示意折线（含 SMC 价区，结构标注旁为对应价格）</p></div>`
                    : '') +
                this.renderSmcSection(wSmc) +
                `</div></details>`;
        }

        host.innerHTML =
            `<div class="ms-result-wrap">` +
            `<div class="ms-meta">个股 ${this.esc(code)} ${this.esc(name)} · 基准日 ${this.esc(asof || '--')}` +
            ` · ${this.esc(this.adjustLabel(pa))} · ZigZag 分形 · SMC</div>` +
            cautionHtml +
            dualTrendHtml +
            `<div class="ms-trend-row">` +
            `<span class="ms-summary">${this.esc(summary)}</span>` +
            `</div>` +
            contrastHtml +
            bosHtml +
            (svg
                ? `<div class="ms-zigzag-wrap">${svg}<p class="ms-muted ms-chart-hint">示意折线（摆动点连线 + OB/FVG 价区），非完整 K 线叠加</p></div>`
                : '') +
            smcHtml +
            analysisHtml +
            weeklyBlock +
            `<div class="ms-subtitle">近端摆动点（HH/HL/LH/LL）·日线</div>` +
            table +
            `<p class="ms-disclaimer">规则模板，非投资建议；SMC 与形态短期三态并列，不互相覆盖；不入策略硬筛；周线逆势提示不否决 URT/GMS 正式买点。</p>` +
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
            const st = String(b.smc_type || '').toLowerCase();
            let title = b.label || b.type;
            if (st === 'choch') title = `CHOCH${b.smc_event_key ? ' · ' + b.smc_event_key : ''}`;
            else if (st === 'bos') title = `BOS${b.smc_event_key ? ' · ' + b.smc_event_key : ''}（非 CHOCH）`;
            else title = `${title || '轻量破位'}（轻量破位 ≠ CHOCH）`;
            lines.push(
                `关键事件：${title} @ ${b.level != null ? b.level : '--'}（${b.level_date || ''}）`
            );
        }
        const smc = m.smc;
        if (smc && smc.ok) {
            lines.push('【SMC】');
            if (smc.structure_bias) lines.push(`结构偏置：${smc.structure_bias}`);
            if (smc.summary) lines.push(smc.summary);
            if (smc.last_event) {
                const e = smc.last_event;
                lines.push(
                    `最近事件：${e.type || ''} ${e.event_key || ''} @ ${e.level != null ? e.level : '--'}（${e.bar_date || ''}）`
                );
            }
            (smc.order_blocks || []).forEach((b) => {
                lines.push(
                    `  OB ${b.direction === 'bullish' ? '看涨' : '看跌'} [${b.low}–${b.high}] ${b.status || ''} ${b.bar_date || ''}`
                );
            });
            (smc.fvgs || []).forEach((f) => {
                lines.push(
                    `  FVG ${f.direction === 'bullish' ? '看涨' : '看跌'} [${f.low}–${f.high}] ${f.status || ''} ${f.end_date || ''}`
                );
            });
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

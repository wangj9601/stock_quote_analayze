/**
 * 江恩趋势预测展示工具
 * 与个股分析 / PDF 同口径；轻量 SVG 扇形示意（非完整 K 线叠加）。
 */
const GannTrendTool = {
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

    biasClass(bias) {
        if (bias === 'bullish') return 'gann-bias--bull';
        if (bias === 'bearish') return 'gann-bias--bear';
        if (bias === 'near') return 'gann-bias--near';
        return 'gann-bias--na';
    },

    async fetchGann(code, opts) {
        const o = opts || {};
        const params = new URLSearchParams();
        params.set('adjust', o.adjust || 'qfq');
        params.set('factor_source', o.factor_source || 'auto');
        params.set('lookback', String(o.lookback || 180));
        if (o.asof) params.set('asof', o.asof);
        if (o.scale != null && Number(o.scale) > 0) params.set('scale', String(o.scale));
        const url = `${this.API_BASE_URL}/api/analysis/gann-trend/${encodeURIComponent(code)}?${params}`;
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

    /** SVG 江恩扇：价-时间示意坐标系 */
    buildFanSvg(fan) {
        if (!fan || !Array.isArray(fan.rays) || !fan.rays.length) return '';
        const w = 560;
        const h = 200;
        const padL = 44;
        const padR = 16;
        const padT = 18;
        const padB = 28;
        const yMin = Number(fan.y_min);
        const yMax = Number(fan.y_max);
        const horizon = Math.max(1, Number(fan.horizon_bars) || 90);
        const spanY = yMax - yMin || 1;
        const xOf = (bo) => padL + (Number(bo) / horizon) * (w - padL - padR);
        const yOf = (p) => padT + (1 - (Number(p) - yMin) / spanY) * (h - padT - padB);

        const rayColors = {
            '1x1': '#2563eb',
            '2x1': '#16a34a',
            '1x2': '#ca8a04',
            '4x1': '#9333ea',
            '1x4': '#ea580c',
        };
        const rays = fan.rays
            .map((r) => {
                const c = rayColors[r.name] || '#64748b';
                const x1 = xOf(r.start.bar_offset);
                const y1 = yOf(r.start.price);
                const x2 = xOf(r.end.bar_offset);
                const y2 = yOf(r.end.price);
                const lx = x2 - 4;
                const ly = y2;
                return (
                    `<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" ` +
                    `stroke="${c}" stroke-width="1.4"/>` +
                    `<text x="${lx.toFixed(1)}" y="${ly.toFixed(1)}" text-anchor="end" font-size="9" fill="${c}">` +
                    `${this.esc(r.name)}</text>`
                );
            })
            .join('');

        // 现价水平线
        const lc = Number(fan.last_close);
        let priceLine = '';
        if (Number.isFinite(lc)) {
            const y = yOf(lc);
            priceLine =
                `<line x1="${padL}" y1="${y.toFixed(1)}" x2="${(w - padR).toFixed(1)}" y2="${y.toFixed(1)}" ` +
                `stroke="#0f172a" stroke-width="1" stroke-dasharray="4 3"/>` +
                `<text x="${padL + 2}" y="${(y - 4).toFixed(1)}" font-size="9" fill="#0f172a">现价 ${lc.toFixed(2)}</text>`;
        }

        // 锚点
        const ax = xOf(0);
        const ay = yOf(fan.anchor && fan.anchor.price);
        const anchorDot =
            `<circle cx="${ax.toFixed(1)}" cy="${ay.toFixed(1)}" r="4" fill="#dc2626"/>` +
            `<text x="${ax.toFixed(1)}" y="${(ay - 8).toFixed(1)}" text-anchor="middle" font-size="9" fill="#dc2626">锚点</text>`;

        // asof 竖线
        const asofBo = Number(fan.asof_bar_offset);
        let asofLine = '';
        if (Number.isFinite(asofBo) && asofBo >= 0) {
            const x = xOf(asofBo);
            asofLine =
                `<line x1="${x.toFixed(1)}" y1="${padT}" x2="${x.toFixed(1)}" y2="${(h - padB).toFixed(1)}" ` +
                `stroke="#94a3b8" stroke-width="1" stroke-dasharray="2 2"/>` +
                `<text x="${x.toFixed(1)}" y="${(h - 8).toFixed(1)}" text-anchor="middle" font-size="8" fill="#64748b">基准日</text>`;
        }

        // ZigZag 叠线（可选）
        let zzPoly = '';
        const zz = (fan.zigzag_overlay || []).filter(
            (p) => p && p.price != null && Number.isFinite(Number(p.price)) && Number(p.bar_offset) >= 0
        );
        if (zz.length >= 2) {
            const pts = zz
                .map((p) => `${xOf(p.bar_offset).toFixed(1)},${yOf(p.price).toFixed(1)}`)
                .join(' ');
            zzPoly = `<polyline fill="none" stroke="#94a3b8" stroke-width="1.2" opacity="0.7" points="${pts}"/>`;
        }

        // 轴标签
        const yTop = `<text x="4" y="${(padT + 4).toFixed(1)}" font-size="8" fill="#64748b">${yMax.toFixed(2)}</text>`;
        const yBot = `<text x="4" y="${(h - padB).toFixed(1)}" font-size="8" fill="#64748b">${yMin.toFixed(2)}</text>`;

        return (
            `<svg class="gann-fan-svg" viewBox="0 0 ${w} ${h}" role="img" aria-label="江恩扇形示意">` +
            zzPoly +
            rays +
            priceLine +
            asofLine +
            anchorDot +
            yTop +
            yBot +
            `</svg>`
        );
    },

    formatPlainText(gann, opts) {
        const o = opts || {};
        const g = gann || {};
        if (!g.ok) {
            return `江恩趋势：信息不足（${g.reason || '无有效锚点'}）`;
        }
        const lines = [];
        const code = o.code || '';
        const name = o.name || '';
        if (code || name) lines.push(`${code} ${name}`.trim());
        lines.push(`基准日：${g.asof || '--'} | 收盘：${g.last_close != null ? Number(g.last_close).toFixed(2) : '--'}`);
        const v = g.verdict || {};
        lines.push(`结论：${v.bias_label || v.bias || '--'} — ${v.summary || ''}`);
        const a = g.anchor || {};
        lines.push(
            `锚点：${a.role || a.kind || ''} @ ${a.price != null ? Number(a.price).toFixed(2) : '--'}（${a.date || ''}），` +
                `扇向 ${a.fan_direction === 'down' ? '下行' : '上行'}，距锚点 ${a.bars_from_anchor != null ? a.bars_from_anchor : '--'} 根`
        );
        lines.push(`1×1 单位(scale)=${g.scale != null ? g.scale : '--'}；${g.scale_note || ''}`);
        if (Array.isArray(g.angles) && g.angles.length) {
            lines.push('角度线（基准日理论价）：');
            g.angles.forEach((ang) => {
                lines.push(
                    `  ${ang.name}: ${ang.price_at_asof != null ? Number(ang.price_at_asof).toFixed(2) : '--'}`
                );
            });
        }
        if (Array.isArray(g.time_windows) && g.time_windows.length) {
            lines.push('时间窗（交易日）：');
            g.time_windows.forEach((t) => {
                lines.push(
                    `  +${t.bars}: ${t.status_label || t.status}` +
                        (t.target_date ? ` @ ${t.target_date}` : '') +
                        (t.bars_from_asof != null ? `（相对基准 ${t.bars_from_asof} 根）` : '')
                );
            });
        }
        lines.push(g.disclaimer || '几何参考，非投资建议。');
        return lines.join('\n');
    },

    renderEmbedded(host, payload, opts) {
        if (!host) return;
        const o = opts || {};
        const g = (payload && payload.gann_trend) || payload || {};
        const code = (payload && payload.code) || o.code || '';
        const name = (payload && payload.name) || o.name || '';
        const asof = (payload && payload.asof) || g.asof || '';
        const pa = (payload && payload.price_adjust) || o.price_adjust;
        const verdict = g.verdict || {};
        const bias = verdict.bias || 'insufficient';

        if (!g.ok) {
            host.innerHTML =
                `<div class="gann-result-wrap">` +
                `<div class="gann-meta">${this.esc(code)} ${this.esc(name)} · ${this.esc(asof)} · ${this.esc(this.adjustLabel(pa))}</div>` +
                `<p class="gann-empty">${this.esc(verdict.summary || '有效波段锚点不足，暂无法给出江恩趋势结论。')}</p>` +
                `<p class="gann-disclaimer">几何参考，非投资建议。</p>` +
                `</div>`;
            return;
        }

        const anchor = g.anchor || {};
        const fanSvg = this.buildFanSvg(g.fan_geometry);
        const angleRows = (g.angles || [])
            .map(
                (a) =>
                    `<tr><td>${this.esc(a.name)}</td>` +
                    `<td>${a.price_at_asof != null ? Number(a.price_at_asof).toFixed(2) : '--'}</td>` +
                    `<td>${a.slope_per_bar != null ? Number(a.slope_per_bar).toFixed(4) : '--'}</td></tr>`
            )
            .join('');
        const twRows = (g.time_windows || [])
            .map(
                (t) =>
                    `<tr><td>+${this.esc(t.bars)}</td>` +
                    `<td>${this.esc(t.status_label || t.status)}</td>` +
                    `<td>${this.esc(t.target_date || '—')}</td>` +
                    `<td>${t.bars_from_asof != null ? t.bars_from_asof : '--'}</td></tr>`
            )
            .join('');

        host.innerHTML =
            `<div class="gann-result-wrap">` +
            `<div class="gann-meta">${this.esc(code)} ${this.esc(name)} · 基准日 ${this.esc(asof)} · ${this.esc(this.adjustLabel(pa))} · ` +
            `收盘 ${g.last_close != null ? Number(g.last_close).toFixed(2) : '--'}</div>` +
            `<div class="gann-verdict ${this.biasClass(bias)}">` +
            `<span class="gann-verdict-label">${this.esc(verdict.bias_label || bias)}</span>` +
            `<span class="gann-verdict-summary">${this.esc(verdict.summary || '')}</span>` +
            `</div>` +
            `<div class="gann-anchor-line">锚点：${this.esc(anchor.role || anchor.kind || '')} ` +
            `${anchor.price != null ? Number(anchor.price).toFixed(2) : '--'}（${this.esc(anchor.date || '')}），` +
            `扇向 ${anchor.fan_direction === 'down' ? '下行' : '上行'}，距锚点 ${anchor.bars_from_anchor != null ? anchor.bars_from_anchor : '--'} 根；` +
            `1×1 scale=${g.scale != null ? g.scale : '--'}</div>` +
            (fanSvg
                ? `<div class="gann-fan-wrap">${fanSvg}` +
                  `<p class="gann-chart-hint">示意：横轴=相对锚点交易日，纵轴=价格；1×1 为自适应价格单位，非屏幕 45°。非蜡烛图叠加。</p></div>`
                : '') +
            `<h5 class="gann-subtitle">角度线（基准日理论价）</h5>` +
            `<table class="gann-table"><thead><tr><th>角度</th><th>理论价</th><th>斜率/根</th></tr></thead>` +
            `<tbody>${angleRows || '<tr><td colspan="3">无</td></tr>'}</tbody></table>` +
            `<h5 class="gann-subtitle">时间窗口（交易日）</h5>` +
            `<table class="gann-table"><thead><tr><th>窗口</th><th>状态</th><th>目标日</th><th>相对基准(根)</th></tr></thead>` +
            `<tbody>${twRows || '<tr><td colspan="4">无</td></tr>'}</tbody></table>` +
            `<p class="gann-disclaimer">${this.esc(g.disclaimer || '几何参考，非投资建议。')} ${this.esc(g.scale_note || '')}</p>` +
            `</div>`;
    },
};

if (typeof window !== 'undefined') {
    window.GannTrendTool = GannTrendTool;
}

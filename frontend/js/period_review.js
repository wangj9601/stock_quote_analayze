// 每周 / 每月复盘
function createPeriodReview(kind, prefix) {
    const nxt = kind === 'month' ? '下月' : '下周';
    return {
        API_BASE_URL: typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : '',
        kind,
        prefix,
        data: null,

        init() {
            const dateEl = document.getElementById(prefix + 'TradeDate');
            if (dateEl && !dateEl.value) {
                const d = new Date();
                d.setDate(d.getDate() - 1);
                dateEl.value = d.toISOString().slice(0, 10);
            }
            this._bind('LoadBtn', () => this.load());
            this._bind('ComputeBtn', () => this.compute());
            this._bind('SaveBtn', () => this.save());
            this._bind('ExportBtn', () => this.exportFile('md'));
            this._bind('ExportPdfBtn', () => this.exportFile('pdf'));
            this.load();
        },

        _bind(suffix, fn) {
            const el = document.getElementById(this.prefix + suffix);
            if (el && !el.dataset.bound) {
                el.dataset.bound = '1';
                el.addEventListener('click', fn);
            }
        },

        anchor() {
            const el = document.getElementById(this.prefix + 'TradeDate');
            return (el && el.value) || '';
        },

        setStatus(text) {
            const el = document.getElementById(this.prefix + 'Status');
            if (el) el.textContent = text || '';
        },

        query() {
            return `type=${encodeURIComponent(this.kind)}&date=${encodeURIComponent(this.anchor())}`;
        },

        async load() {
            this.setStatus('加载中…');
            try {
                const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
                const resp = await fetchFn(`${this.API_BASE_URL}/api/market_review/period?${this.query()}`);
                const payload = await resp.json().catch(() => ({}));
                if (!resp.ok || !payload.success) {
                    this.data = null;
                    this.render(null);
                    this.setStatus(payload.message || '暂无快照，请先点击「重算」');
                    return;
                }
                this.data = payload.data || {};
                this.render(this.data);
                this.setStatus(`已加载 ${this.data.period_key || this.anchor()}`);
            } catch (e) {
                this.setStatus(e.message || '加载失败');
            }
        },

        async compute() {
            this.setStatus('正在汇总已有日复盘…');
            try {
                const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
                const resp = await fetchFn(`${this.API_BASE_URL}/api/market_review/period?${this.query()}`, { method: 'POST' });
                const payload = await resp.json().catch(() => ({}));
                if (!resp.ok || !payload.success) throw new Error(payload.message || '重算失败');
                this.data = payload.data || {};
                this.render(this.data);
                this.setStatus(`已重算 ${this.data.period_key || ''}`);
            } catch (e) {
                this.setStatus(e.message || '重算失败');
            }
        },

        async save() {
            const viewpoint = document.getElementById(this.prefix + 'Viewpoint');
            const advice = document.getElementById(this.prefix + 'Advice');
            this.setStatus('保存中…');
            try {
                const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
                const resp = await fetchFn(`${this.API_BASE_URL}/api/market_review/period?${this.query()}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        viewpoint_md: viewpoint ? viewpoint.value : '',
                        advice_md: advice ? advice.value : '',
                    }),
                });
                const payload = await resp.json().catch(() => ({}));
                if (!resp.ok || !payload.success) throw new Error(payload.message || '保存失败');
                this.data = payload.data || {};
                this.render(this.data);
                this.setStatus('观点/建议已保存');
            } catch (e) {
                this.setStatus(e.message || '保存失败');
            }
        },

        async exportFile(ext) {
            this.setStatus(ext === 'pdf' ? '正在生成 PDF…' : '正在生成 Markdown…');
            try {
                const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
                const path = ext === 'pdf' ? 'period/export.pdf' : 'period/export.md';
                const resp = await fetchFn(`${this.API_BASE_URL}/api/market_review/${path}?${this.query()}`);
                const ct = (resp.headers.get('Content-Type') || '').toLowerCase();
                if (!resp.ok || ct.includes('application/json')) {
                    const payload = await resp.json().catch(() => ({}));
                    throw new Error(payload.message || '导出失败');
                }
                const blob = await resp.blob();
                const filename = this._downloadName(resp, `period_review_${this.anchor()}.${ext}`);
                this._saveBlob(blob, filename);
                this.setStatus(`已下载 ${filename}`);
            } catch (e) {
                this.setStatus(e.message || '导出失败');
            }
        },

        _downloadName(resp, fallback) {
            const cd = resp.headers.get('Content-Disposition') || '';
            const star = /filename\*=UTF-8''([^;]+)/i.exec(cd);
            if (star) {
                try { return decodeURIComponent(star[1]); } catch (e) { return star[1]; }
            }
            const plain = /filename="?([^";]+)"?/i.exec(cd);
            return plain ? plain[1] : fallback;
        },

        _saveBlob(blob, filename) {
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = filename;
            a.click();
            URL.revokeObjectURL(a.href);
        },

        render(data) {
            const root = document.getElementById(this.prefix + 'Body');
            if (!root) return;
            if (!data) {
                root.innerHTML = '<p class="dr-summary">暂无该区间快照。</p>';
                return;
            }
            const picks = data.picks || {};
            root.innerHTML = `
                <section class="dr-section"><h3>大盘</h3>
                    <p class="dr-summary">${esc(data.note || '')}</p>
                    <p class="dr-summary">日均成交 ${fmt(data.vol_avg)} 万亿，上一期日均 ${fmt(data.prev_vol_avg)} 万亿。</p>
                    ${table(['指数', '期初收盘', '期末收盘', '区间涨跌%'], (data.indexes || []).map(r => [
                        esc(r.name), fmt(r.start_close), fmt(r.end_close), tone(r.period_pct, fmt(r.period_pct))
                    ]))}
                </section>
                <section class="dr-section"><h3>趋势路径</h3>
                    <p class="dr-summary">高度 ${esc(deltaText(data.delta && data.delta.height, '板', 0))}；连板 ${esc(deltaText(data.delta && data.delta.cb_count, '家', 0))}</p>
                    ${table(['日期', '高度', '连板', '季节', '成交(万亿)', '盘面'], (data.path || []).map(r => [
                        esc(r.trade_date), intText(r.height), intText(r.cb_count), esc(r.season), fmt(r.vol_trillion), esc(r.tape_label)
                    ]))}
                </section>
                <section class="dr-section"><h3>硬门槛达标天数</h3>
                    ${table(['门槛', '标准', '达标天数'], (data.gates || []).map(r => [
                        esc(r.name), esc(r.standard), `${r.passed_days || 0}/${r.total_days || 0}`
                    ]))}
                </section>
                <section class="dr-section"><h3>主线持续性</h3>
                    ${table(['概念', '上榜天数', '期末定性', '持续'], (data.mainlines || []).map(r => [
                        esc(r.board_name), String(r.hit_days || 0), esc(r.tier_label), r.persistent ? '是' : '否'
                    ]))}
                    <p class="dr-summary">${esc((data.industry_confirm || {}).summary || '')}</p>
                </section>
                <section class="dr-section"><h3>情绪路径</h3>
                    <p class="dr-summary">${esc((data.seasons || []).join(' → ') || '—')}。切换 ${data.season_switches || 0} 次，期末 ${esc(data.end_season || '—')}。</p>
                    <p class="dr-summary">Lo ${esc(deltaText(data.curve && data.curve.lo))}；Hi ${esc(deltaText(data.curve && data.curve.hi))}；Sp ${esc(deltaText(data.curve && data.curve.sp))}</p>
                </section>
                <section class="dr-section"><h3>${nxt}个股</h3>
                    <p class="dr-summary">${esc(picks.disclaimer || '')}</p>
                    <p class="dr-summary">${esc(picks.note || '')}</p>
                    <h3 class="dr-subhead">不追</h3>
                    ${table(['个股', '连板', '封单(亿)', '立场', '区间涨跌%'], (picks.no_chase || []).map(r => [
                        stock(r), intText(r.board_count), fmt(r.seal_yi), esc(r.stance), tone(r.period_pct, fmt(r.period_pct))
                    ]))}
                    <h3 class="dr-subhead">可跟踪</h3>
                    ${table(['个股', '行业', '立场', '区间涨跌%', '形态', '触发'], (picks.track || []).map(r => [
                        stock(r), industryText(r.industry), esc(r.stance), tone(r.period_pct, fmt(r.period_pct)), esc(r.pattern), esc(r.trigger)
                    ]))}
                    <h3 class="dr-subhead">支线只观察</h3>
                    ${table(['个股', '行业', '区间涨跌%', '立场'], (picks.sideline || []).map(r => [
                        stock(r), industryText(r.industry), tone(r.period_pct, fmt(r.period_pct)), esc(r.stance || '只观察')
                    ]))}
                    <h3 class="dr-subhead">回避</h3>
                    ${table(['个股', '原因', '立场'], (picks.avoid || []).map(r => [stock(r), esc(r.reason), '回避']))}
                </section>
                <section class="dr-section dr-editors">
                    <div><h3>观点与盘面分析</h3>
                        <textarea id="${this.prefix}Viewpoint" rows="5">${esc(data.viewpoint_md || '')}</textarea>
                    </div>
                    <div><h3>操作建议</h3>
                        <textarea id="${this.prefix}Advice" rows="5">${esc(data.advice_md || '')}</textarea>
                    </div>
                </section>
                <section class="dr-section dr-md-fold"><details><summary>Markdown 预览</summary>
                    <div class="dr-md-preview">${mdHtml(data.markdown || '')}</div>
                </details></section>`;
        },
    };
}

function industryText(v) {
    const s = String(v == null ? '' : v).trim();
    if (!s || ['nan', 'none', 'null', '-', '--', 'nat'].indexOf(s.toLowerCase()) >= 0) return '—';
    return esc(s);
}

function esc(v) {
    return String(v == null ? '' : v)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function fmt(v) {
    if (v == null || v === '') return '—';
    const n = Number(v);
    if (!Number.isFinite(n)) return esc(v);
    return n.toFixed(2);
}

function intText(v) {
    if (v == null || v === '') return '—';
    const n = Number(v);
    if (!Number.isFinite(n)) return esc(v);
    return String(Math.round(n));
}

function tone(v, text) {
    const n = Number(v);
    if (!Number.isFinite(n) || n === 0) return text;
    return `<span class="${n > 0 ? 'dr-up' : 'dr-down'}">${text}</span>`;
}

function deltaText(pair, unit, digits) {
    if (!pair) return '—';
    const a = pair.from;
    const b = pair.to;
    if (a == null && b == null) return '—';
    const dgs = digits == null ? 2 : digits;
    const show = (v) => {
        if (v == null || v === '') return '—';
        const n = Number(v);
        if (!Number.isFinite(n)) return String(v);
        return dgs === 0 ? String(Math.round(n)) : n.toFixed(dgs);
    };
    if (a == null || b == null) return `${show(a)} → ${show(b)}`;
    const diff = Number(b) - Number(a);
    const sign = diff > 0 ? '+' : '';
    return `${show(a)} → ${show(b)}（${sign}${show(diff)}${unit || ''}）`;
}

function stock(row) {
    const code = row.code || '';
    const name = row.name || code || '—';
    if (!code) return esc(name);
    const href = `stock.html?code=${encodeURIComponent(code)}&name=${encodeURIComponent(name)}`;
    return `<a href="${href}">${esc(name)}</a> <span class="dr-code">${esc(code)}</span>`;
}

function table(headers, rows) {
    const th = headers.map((h) => `<th>${esc(h)}</th>`).join('');
    const body = rows.length
        ? rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join('')}</tr>`).join('')
        : `<tr><td colspan="${headers.length}">暂无</td></tr>`;
    return `<div class="dr-table-wrap"><table class="dr-table"><thead><tr>${th}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function mdHtml(src) {
    if (window.DailyReviewPage && typeof DailyReviewPage.renderMarkdown === 'function') {
        return DailyReviewPage.renderMarkdown(src);
    }
    return `<pre>${esc(src)}</pre>`;
}

window.PeriodReviewWeek = createPeriodReview('week', 'wr');
window.PeriodReviewMonth = createPeriodReview('month', 'mr');

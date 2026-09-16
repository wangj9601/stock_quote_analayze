// 每日复盘工作台
const DailyReviewPage = {
    API_BASE_URL: typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : '',
    _loaded: false,
    data: null,

    init() {
        const dateEl = document.getElementById('drTradeDate');
        if (dateEl && !dateEl.value) {
            const d = new Date();
            // 默认昨天（日终复盘）
            d.setDate(d.getDate() - 1);
            dateEl.value = d.toISOString().slice(0, 10);
        }
        const loadBtn = document.getElementById('drLoadBtn');
        const computeBtn = document.getElementById('drComputeBtn');
        const saveBtn = document.getElementById('drSaveBtn');
        const exportBtn = document.getElementById('drExportBtn');
        const exportPdfBtn = document.getElementById('drExportPdfBtn');
        if (loadBtn && !loadBtn.dataset.bound) {
            loadBtn.dataset.bound = '1';
            loadBtn.addEventListener('click', () => this.load());
        }
        if (computeBtn && !computeBtn.dataset.bound) {
            computeBtn.dataset.bound = '1';
            computeBtn.addEventListener('click', () => this.compute());
        }
        if (saveBtn && !saveBtn.dataset.bound) {
            saveBtn.dataset.bound = '1';
            saveBtn.addEventListener('click', () => this.save());
        }
        if (exportBtn && !exportBtn.dataset.bound) {
            exportBtn.dataset.bound = '1';
            exportBtn.addEventListener('click', () => this.exportMd());
        }
        if (exportPdfBtn && !exportPdfBtn.dataset.bound) {
            exportPdfBtn.dataset.bound = '1';
            exportPdfBtn.addEventListener('click', () => this.exportPdf());
        }
        this.load();
    },

    tradeDate() {
        const el = document.getElementById('drTradeDate');
        return (el && el.value) || '';
    },

    async load() {
        const d = this.tradeDate();
        this.setStatus('加载中…');
        try {
            const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
            const resp = await fetchFn(
                `${this.API_BASE_URL}/api/market_review/daily?trade_date=${encodeURIComponent(d)}`
            );
            const payload = await resp.json().catch(() => ({}));
            if (!resp.ok || !payload.success) {
                this.setStatus(payload.message || '暂无快照，请先点击「重算」');
                this.data = null;
                this.renderEmpty();
                return;
            }
            this.data = payload.data || {};
            this.render(this.data);
            this.setStatus(`已加载 ${d}（口径 ${this.data.limit_source || '--'}）`);
            this._loaded = true;
        } catch (e) {
            console.warn('[daily-review] load failed', e);
            this.setStatus(e.message || '加载失败');
        }
    },

    async compute() {
        const d = this.tradeDate();
        this.setStatus('正在重算（可能需数十秒）…');
        try {
            const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
            const resp = await fetchFn(
                `${this.API_BASE_URL}/api/market_review/compute?trade_date=${encodeURIComponent(d)}&collect_zt=true&export_md=true&sync=true`,
                { method: 'POST' }
            );
            const payload = await resp.json().catch(() => ({}));
            if (!resp.ok || !payload.success) {
                throw new Error(payload.message || `重算失败 ${resp.status}`);
            }
            this.data = payload.data || {};
            this.render(this.data);
            this.setStatus(`重算完成 ${d} · ${this.data.limit_source || ''} · 季节 ${this.data.season || ''}`);
        } catch (e) {
            console.warn('[daily-review] compute failed', e);
            this.setStatus(e.message || '重算失败');
        }
    },

    async save() {
        const d = this.tradeDate();
        const viewpoint = (document.getElementById('drViewpoint') || {}).value || '';
        const advice = (document.getElementById('drAdvice') || {}).value || '';
        try {
            const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
            const resp = await fetchFn(
                `${this.API_BASE_URL}/api/market_review/daily?trade_date=${encodeURIComponent(d)}`,
                {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ viewpoint_md: viewpoint, advice_md: advice }),
                }
            );
            const payload = await resp.json().catch(() => ({}));
            if (!resp.ok || !payload.success) {
                throw new Error(payload.message || '保存失败');
            }
            this.data = payload.data || {};
            this.render(this.data);
            this.setStatus('观点/建议已保存');
        } catch (e) {
            this.setStatus(e.message || '保存失败');
        }
    },

    async exportMd() {
        const d = this.tradeDate();
        try {
            const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
            const resp = await fetchFn(
                `${this.API_BASE_URL}/api/market_review/export.md?trade_date=${encodeURIComponent(d)}&save=true`
            );
            const payload = await resp.json().catch(() => ({}));
            if (!resp.ok || !payload.success) {
                throw new Error(payload.message || '导出失败');
            }
            this.setStatus(`已导出：${payload.path || 'exported_docs'}`);
            if (payload.markdown) {
                const pre = document.getElementById('drMarkdownPreview');
                if (pre) pre.textContent = payload.markdown;
            }
        } catch (e) {
            this.setStatus(e.message || '导出失败');
        }
    },

    async exportPdf() {
        const d = this.tradeDate();
        this.setStatus('正在生成 PDF…');
        try {
            const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
            const resp = await fetchFn(
                `${this.API_BASE_URL}/api/market_review/export.pdf?trade_date=${encodeURIComponent(d)}&save=true`
            );
            const ct = (resp.headers.get('Content-Type') || '').toLowerCase();
            if (!resp.ok || ct.includes('application/json')) {
                const payload = await resp.json().catch(() => ({}));
                throw new Error(payload.message || `PDF 导出失败 ${resp.status}`);
            }
            const blob = await resp.blob();
            const a = document.createElement('a');
            const cd = resp.headers.get('Content-Disposition') || '';
            const mStar = /filename\*=UTF-8''([^;]+)/i.exec(cd);
            const m = /filename=\"?([^\";]+)\"?/i.exec(cd);
            let filename = `daily_review_${d}.pdf`;
            if (mStar) {
                try {
                    filename = decodeURIComponent(mStar[1]);
                } catch (_) {
                    filename = mStar[1];
                }
            } else if (m) {
                filename = m[1];
            }
            a.href = URL.createObjectURL(blob);
            a.download = filename;
            a.click();
            URL.revokeObjectURL(a.href);
            const savedRaw = resp.headers.get('X-Export-Path');
            let saved = savedRaw || '';
            if (saved) {
                try {
                    saved = decodeURIComponent(saved);
                } catch (_) {
                    /* keep raw */
                }
            }
            this.setStatus(saved ? `已导出 PDF：${saved}` : `已下载 ${filename}`);
        } catch (e) {
            this.setStatus(e.message || 'PDF 导出失败');
        }
    },

    setStatus(msg) {
        const el = document.getElementById('drStatus');
        if (el) el.textContent = msg || '';
    },

    renderEmpty() {
        const metrics = document.getElementById('drMetrics');
        if (metrics) metrics.innerHTML = '<p class="dr-empty">暂无数据</p>';
        const gates = document.getElementById('drGatesBody');
        if (gates) gates.innerHTML = '<tr><td colspan="5">暂无</td></tr>';
        const main = document.getElementById('drMainlineBody');
        if (main) main.innerHTML = '<tr><td colspan="5">暂无</td></tr>';
        const ind = document.getElementById('drIndustryConfirmBody');
        if (ind) ind.innerHTML = '<tr><td colspan="4">暂无</td></tr>';
        const indSum = document.getElementById('drIndustryConfirmSummary');
        if (indSum) indSum.textContent = '';
    },

    fmt(v, digits) {
        if (v == null || v === '') return '--';
        const n = Number(v);
        if (Number.isNaN(n)) return String(v);
        if (digits === 0) return String(Math.round(n));
        return n.toFixed(digits == null ? 2 : digits);
    },

    escapeHtml(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    },

    boardDetailHref(kind, code, name) {
        const q = new URLSearchParams({
            board_kind: kind === 'concept' ? 'concept' : 'industry',
            board_code: String(code || '').trim(),
            board_code_source: 'tonghuashun',
        });
        const n = String(name || '').trim();
        if (n) q.set('board_name', n);
        return `board_detail.html?${q.toString()}`;
    },

    boardLinkHtml(kind, row) {
        const code = String((row && row.board_code) || '').trim();
        const name = String((row && (row.board_name || row.board_code)) || '').trim() || '--';
        if (!code) return this.escapeHtml(name);
        const href = this.boardDetailHref(kind, code, name);
        return `<a class="dr-board-link" href="${this.escapeHtml(href)}" target="_blank" rel="noopener noreferrer" title="打开板块详情">${this.escapeHtml(name)}</a>`;
    },

    render(data) {
        if (!data) return this.renderEmpty();
        const metrics = document.getElementById('drMetrics');
        if (metrics) {
            metrics.innerHTML = `
              <div class="dr-metric"><span>Vol(万亿)</span><strong>${this.fmt(data.vol_trillion)}</strong></div>
              <div class="dr-metric"><span>涨停家数</span><strong>${this.fmt(data.limit_up_count, 0)}</strong></div>
              <div class="dr-metric"><span>CB连板</span><strong>${this.fmt(data.cb_count, 0)}</strong></div>
              <div class="dr-metric"><span>高度H</span><strong>${this.fmt(data.height, 0)}</strong></div>
              <div class="dr-metric"><span>昨连板收益%</span><strong>${this.fmt(data.prev_cb_return)}</strong></div>
              <div class="dr-metric"><span>Lo</span><strong>${this.fmt(data.lo_value)}</strong></div>
              <div class="dr-metric"><span>Hi</span><strong>${this.fmt(data.hi_value)}</strong></div>
              <div class="dr-metric"><span>Sp</span><strong>${this.fmt(data.sp_value)}</strong></div>
              <div class="dr-metric"><span>季节</span><strong>${data.season || '--'}</strong></div>
              <div class="dr-metric"><span>口径</span><strong>${data.limit_source || '--'}</strong></div>
            `;
        }

        const gates = (data.hard_gates && data.hard_gates.items) || [];
        const gBody = document.getElementById('drGatesBody');
        if (gBody) {
            gBody.innerHTML = gates.length
                ? gates
                      .map(
                          (g) => `<tr>
                    <td>${g.id}</td><td>${g.name || ''}</td><td>${g.standard || ''}</td>
                    <td>${this.fmt(g.value)}</td>
                    <td class="${g.passed ? 'is-ok' : 'is-bad'}">${g.passed ? '达标' : '不达标'}</td>
                  </tr>`
                      )
                      .join('')
                : '<tr><td colspan="5">暂无</td></tr>';
        }
        const rateEl = document.getElementById('drGatesRate');
        if (rateEl) rateEl.textContent = (data.hard_gates && data.hard_gates.rate) || '--';

        const rows = (data.mainline_json && data.mainline_json.rows) || [];
        const mBody = document.getElementById('drMainlineBody');
        if (mBody) {
            mBody.innerHTML = rows.length
                ? rows
                      .map(
                          (r) => `<tr>
                    <td>${this.boardLinkHtml(r.board_type || 'concept', r)}</td>
                    <td>${r.hits_10d}</td>
                    <td>${this.escapeHtml(r.tier_label || '')}</td>
                    <td>${this.escapeHtml(r.today_status || '')}</td>
                    <td>${this.escapeHtml(r.echelon || '')}</td>
                  </tr>`
                      )
                      .join('')
                : '<tr><td colspan="5">暂无</td></tr>';
        }
        const mSum = document.getElementById('drMainlineSummary');
        if (mSum) mSum.textContent = (data.mainline_json && data.mainline_json.summary) || '';

        const ind = (data.mainline_json && data.mainline_json.industry_confirm) || {};
        const iBody = document.getElementById('drIndustryConfirmBody');
        if (iBody) {
            const iRows = ind.rows || [];
            iBody.innerHTML = iRows.length
                ? iRows
                      .map(
                          (r) => `<tr>
                    <td>${this.boardLinkHtml('industry', r)}</td>
                    <td>${this.escapeHtml(r.reason_text || '')}</td>
                    <td>${this.fmt(r.change_percent)}</td>
                    <td>${this.fmt(r.net_inflow, 0)}</td>
                  </tr>`
                      )
                      .join('')
                : '<tr><td colspan="4">暂无</td></tr>';
        }
        const iSum = document.getElementById('drIndustryConfirmSummary');
        if (iSum) iSum.textContent = ind.summary || '';

        const rules = data.rules_json || {};
        const summary = document.getElementById('drTrendSummary');
        if (summary) summary.textContent = rules.summary || '';
        const vp = document.getElementById('drViewpoint');
        if (vp) vp.value = data.viewpoint_md || '';
        const ad = document.getElementById('drAdvice');
        if (ad) ad.value = data.advice_md || '';
        const pre = document.getElementById('drMarkdownPreview');
        if (pre) pre.textContent = data.markdown || '';
    },
};

window.DailyReviewPage = DailyReviewPage;

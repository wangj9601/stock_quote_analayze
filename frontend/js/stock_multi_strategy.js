/**
 * 分析频道 · 个股四策略命中（RPE / SBBR / GMS / URT）
 */
const StockMultiStrategy = {
    API_BASE_URL: typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : '',
    running: false,

    init() {
        const btn = document.getElementById('ssaAnalyzeBtn');
        if (btn) {
            btn.addEventListener('click', () => this.analyze());
        }
        const codeInput = document.getElementById('ssaStockCode');
        if (codeInput) {
            codeInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.analyze();
                }
            });
        }
        const watchSelect = document.getElementById('ssaWatchlist');
        if (watchSelect) {
            watchSelect.addEventListener('change', () => {
                const val = (watchSelect.value || '').trim();
                if (val && codeInput) codeInput.value = val;
            });
        }
    },

    async loadWatchlistOptions() {
        const select = document.getElementById('ssaWatchlist');
        if (!select || select.dataset.loaded === '1') return;
        if (!CommonUtils.checkLoginAndHandleExpiry()) return;
        try {
            const resp = await authFetch(`${this.API_BASE_URL}/api/watchlist`);
            if (!resp.ok) return;
            const payload = await resp.json();
            const list = Array.isArray(payload)
                ? payload
                : (payload.data || payload.items || payload.stocks || []);
            if (!Array.isArray(list)) return;
            const seen = new Set();
            const opts = ['<option value="">-- 可选自选股 --</option>'];
            list.forEach((item) => {
                const code = String(item.code || item.stock_code || '').trim();
                if (!code || seen.has(code)) return;
                seen.add(code);
                const name = item.name || item.stock_name || '';
                opts.push(`<option value="${code}">${name ? `${code} ${name}` : code}</option>`);
            });
            select.innerHTML = opts.join('');
            select.dataset.loaded = '1';
        } catch (e) {
            console.warn('加载自选股失败', e);
        }
    },

    hideCandidates() {
        const box = document.getElementById('ssaCandidates');
        const list = document.getElementById('ssaCandidateList');
        if (box) box.hidden = true;
        if (list) list.innerHTML = '';
    },

    renderCandidates(candidates, message) {
        const box = document.getElementById('ssaCandidates');
        const list = document.getElementById('ssaCandidateList');
        const title = box && box.querySelector('.ssa-candidates-title');
        if (!box || !list) return;
        if (title) title.textContent = message || '匹配到多只股票，请选择：';
        list.innerHTML = (candidates || []).map((item) => {
            const code = String(item.code || '').trim();
            const name = String(item.name || '').trim();
            const label = name ? `${code} ${name}` : code;
            return `<li><button type="button" class="ssa-candidate-btn" data-code="${this.escAttr(code)}">${this.esc(label)}</button></li>`;
        }).join('');
        list.querySelectorAll('.ssa-candidate-btn').forEach((btn) => {
            btn.addEventListener('click', () => {
                const code = btn.getAttribute('data-code') || '';
                const input = document.getElementById('ssaStockCode');
                if (input) input.value = code;
                this.hideCandidates();
                this.analyze();
            });
        });
        box.hidden = false;
        const results = document.getElementById('ssaResults');
        const meta = document.getElementById('ssaMeta');
        const empty = document.getElementById('ssaEmpty');
        if (results) results.hidden = true;
        if (meta) meta.hidden = true;
        if (empty) empty.hidden = true;
    },

    async analyze() {
        if (this.running) return;
        if (!CommonUtils.checkLoginAndHandleExpiry()) return;
        const codeInput = document.getElementById('ssaStockCode');
        const btn = document.getElementById('ssaAnalyzeBtn');
        const empty = document.getElementById('ssaEmpty');
        if (!codeInput) return;

        let query = (codeInput.value || '').trim();
        if (!query) {
            CommonUtils.showToast('请输入股票代码或名称', 'warning');
            codeInput.focus();
            return;
        }
        const firstToken = query.split(/\s+/)[0];
        const firstBody = /^(sh|sz|bj)/i.test(firstToken) ? firstToken.slice(2) : firstToken;
        if (/^\d{4,6}$/.test(firstBody)) query = firstToken;

        this.running = true;
        this.hideCandidates();
        if (btn) {
            btn.disabled = true;
            btn.textContent = '分析中…';
        }
        if (empty) {
            empty.hidden = false;
            empty.textContent = '正在评估四策略，请稍候…';
        }
        const results = document.getElementById('ssaResults');
        const meta = document.getElementById('ssaMeta');
        if (results) results.hidden = true;
        if (meta) meta.hidden = true;

        try {
            const q = new URLSearchParams({ code: query });
            const dateEl = document.getElementById('ssaTradeDate');
            if (dateEl && dateEl.value) q.set('date', dateEl.value);
            const resp = await authFetch(
                `${this.API_BASE_URL}/api/analysis/multi-strategy-check?${q}`
            );
            const payload = await resp.json().catch(() => ({}));
            const candidates = Array.isArray(payload.candidates) ? payload.candidates : [];
            if (candidates.length > 1 || (candidates.length > 0 && !payload.data)) {
                this.renderCandidates(candidates, payload.message);
                CommonUtils.showToast(payload.message || '请从候选中选择股票', 'warning');
                return;
            }
            if (!resp.ok || !payload.success) {
                throw new Error(payload.message || payload.detail || `分析失败 ${resp.status}`);
            }
            const data = payload.data || {};
            const stock = data.stock || {};
            if (stock.code && codeInput) {
                codeInput.value = stock.name ? `${stock.code} ${stock.name}` : stock.code;
            }
            this.renderResult(data);
            CommonUtils.showToast(
                data.any_hit ? `命中 ${data.hit_count || 0} 个策略` : '四策略均未命中',
                data.any_hit ? 'success' : 'info'
            );
        } catch (e) {
            console.error(e);
            if (empty) {
                empty.hidden = false;
                empty.textContent = e.message || '分析失败';
            }
            CommonUtils.showToast(e.message || '分析失败', 'error');
        } finally {
            this.running = false;
            if (btn) {
                btn.disabled = false;
                btn.textContent = '分析';
            }
        }
    },

    renderResult(data) {
        const empty = document.getElementById('ssaEmpty');
        const meta = document.getElementById('ssaMeta');
        const host = document.getElementById('ssaResults');
        if (empty) empty.hidden = true;
        const stock = data.stock || {};
        if (meta) {
            meta.hidden = false;
            meta.innerHTML = `
                <div class="ssa-meta-card">
                    <strong>${this.esc(stock.code || '')}</strong>
                    <span>${this.esc(stock.name || '')}</span>
                    <span>基准日 ${this.esc(data.trade_date || '--')}</span>
                    <span>命中 ${data.hit_count != null ? data.hit_count : 0}/4</span>
                    <span class="ssa-muted">${this.esc(data.asof || '')}</span>
                </div>`;
        }
        if (!host) return;
        const order = ['rpe', 'sbbr', 'gms', 'urt'];
        const byKey = {};
        (data.results || []).forEach((r) => {
            if (r && r.strategy) byKey[r.strategy] = r;
        });
        host.innerHTML = order.map((key) => {
            const r = byKey[key] || {
                strategy: key,
                name: key.toUpperCase(),
                hit: false,
                label: '--',
                score_display: '--',
                reason: '无结果',
            };
            const hitCls = r.hit ? 'ssa-card--hit' : 'ssa-card--miss';
            const badge = r.hit
                ? `<span class="ssa-badge ssa-badge--yes">${this.esc(r.label || '命中')}</span>`
                : '<span class="ssa-badge ssa-badge--no">未命中</span>';
            const err = r.error
                ? `<div class="ssa-error">${this.esc(r.error)}</div>`
                : '';
            const links = [];
            if (r.trace_url) {
                links.push(
                    `<a class="ssa-link" href="${this.escAttr(r.trace_url)}" target="_blank" rel="noopener">信号追溯</a>`
                );
            }
            if (r.screening_url) {
                links.push(
                    `<a class="ssa-link" href="${this.escAttr(r.screening_url)}" target="_blank" rel="noopener">选股页</a>`
                );
            }
            return `<article class="ssa-card ${hitCls}" data-strategy="${this.escAttr(key)}">
                <div class="ssa-card-head">
                    <h4>${this.esc(r.name || key.toUpperCase())}</h4>
                    ${badge}
                </div>
                <div class="ssa-card-score">${this.esc(r.score_display || '--')}</div>
                <p class="ssa-card-reason">${this.esc(r.reason || '')}</p>
                ${err}
                <div class="ssa-card-links">${links.join(' · ')}</div>
            </article>`;
        }).join('');
        host.hidden = false;
    },

    esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    },

    escAttr(s) {
        return this.esc(s).replace(/'/g, '&#39;');
    },
};

window.StockMultiStrategy = StockMultiStrategy;

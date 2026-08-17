/**
 * 分析频道：统一交易观察 / 正式交易列表
 */
const UnifiedTradeObserve = {
    sub: 'observe',
    SOURCE_LABELS: {
        gms: 'GMS',
        urt: 'URT',
        sbbr: 'SBBR',
        rpe: 'RPE',
        triple_volume: '3倍量',
        stock_analysis: '个股分析',
    },
    FORMAL_SOURCES: new Set(['gms', 'urt', 'sbbr', 'rpe']),

    apiBase() {
        if (typeof window !== 'undefined' && window.Config && typeof window.Config.getApiBaseUrl === 'function') {
            return window.Config.getApiBaseUrl() || '';
        }
        if (typeof Config !== 'undefined' && Config && typeof Config.getApiBaseUrl === 'function') {
            return Config.getApiBaseUrl() || '';
        }
        if (typeof window !== 'undefined' && typeof window.API_BASE_URL === 'string' && window.API_BASE_URL.length) {
            return String(window.API_BASE_URL).replace(/\/+$/, '');
        }
        // 本地静态页常见端口：直连后端 5000
        try {
            const { hostname, protocol, port } = window.location;
            if ((hostname === 'localhost' || hostname === '127.0.0.1') && port && port !== '5000' && port !== '80' && port !== '443') {
                return `${protocol}//${hostname}:5000`;
            }
        } catch (_) { /* ignore */ }
        return '';
    },

    init() {
        const refreshBtn = document.getElementById('utoRefreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refresh());
        }
        const sourceEl = document.getElementById('utoSourceFilter');
        if (sourceEl) {
            sourceEl.addEventListener('change', () => this.refresh());
        }
        document.querySelectorAll('.uto-subtab').forEach((btn) => {
            btn.addEventListener('click', () => {
                const sub = btn.getAttribute('data-uto-sub') || 'observe';
                this.switchSub(sub);
            });
        });
        const obsBody = document.getElementById('utoObserveTableBody');
        if (obsBody) {
            obsBody.addEventListener('click', (e) => this._onObserveClick(e));
        }
        const formalBody = document.getElementById('utoFormalTableBody');
        if (formalBody) {
            formalBody.addEventListener('click', (e) => this._onFormalClick(e));
        }
    },

    switchSub(sub) {
        this.sub = sub === 'formal' ? 'formal' : 'observe';
        document.querySelectorAll('.uto-subtab').forEach((b) => {
            b.classList.toggle('active', b.getAttribute('data-uto-sub') === this.sub);
        });
        const obsWrap = document.getElementById('utoObserveWrap');
        const formalWrap = document.getElementById('utoFormalWrap');
        if (obsWrap) obsWrap.hidden = this.sub !== 'observe';
        if (formalWrap) formalWrap.hidden = this.sub !== 'formal';
        this.refresh();
    },

    sourceQuery() {
        const el = document.getElementById('utoSourceFilter');
        const v = el ? String(el.value || '').trim() : '';
        return v ? `source=${encodeURIComponent(v)}` : '';
    },

    sourceLabel(src) {
        return this.SOURCE_LABELS[src] || src || '—';
    },

    marketLabel(m) {
        const v = String(m || '').toUpperCase();
        if (v === 'HK') return 'HK';
        if (v === 'CN' || v === 'A' || v === 'SH' || v === 'SZ') return 'CN';
        return v || '—';
    },

    esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/"/g, '&quot;');
    },

    fmtPrice(v) {
        if (v == null || v === '' || Number.isNaN(Number(v))) return '—';
        return Number(v).toFixed(2);
    },

    fmtDt(iso) {
        if (!iso) return '—';
        const s = String(iso).replace('T', ' ');
        return s.length >= 16 ? s.slice(0, 16) : s.slice(0, 19);
    },

    /** 从统一 API 已返回的 snapshot 取信号价（有则展示，无则 —，不造假） */
    signalPriceFromItem(it) {
        const snap = it && typeof it.snapshot === 'object' && it.snapshot ? it.snapshot : {};
        const keys = [
            'current_price',
            'close',
            'price',
            'last_price',
            'signal_price',
            'entry_price',
        ];
        for (let i = 0; i < keys.length; i += 1) {
            const v = snap[keys[i]];
            if (v != null && v !== '' && !Number.isNaN(Number(v))) return Number(v);
        }
        return null;
    },

    statusLabel(st) {
        const s = String(st || '').toLowerCase();
        if (s === 'open') return '持仓中';
        if (s === 'closed') return '已平仓';
        return st || '—';
    },

    analysisHref(code, name) {
        const q = new URLSearchParams({
            tab: 'stock-ai',
            code: String(code || ''),
            name: String(name || ''),
        });
        return `analysis.html?${q.toString()}`;
    },

    async refresh() {
        if (this.sub === 'formal') {
            await this.refreshFormal();
        } else {
            await this.refreshObserve();
        }
    },

    async refreshObserve() {
        const errEl = document.getElementById('utoObserveError');
        const loadingEl = document.getElementById('utoObserveLoading');
        const tbody = document.getElementById('utoObserveTableBody');
        const countEl = document.getElementById('utoCount');
        if (errEl) {
            errEl.hidden = true;
            errEl.textContent = '';
        }
        if (loadingEl) loadingEl.hidden = false;
        try {
            if (!window.CommonUtils || !CommonUtils.checkLoginAndHandleExpiry()) {
                throw new Error('请先登录后查看交易观察列表');
            }
            const qs = this.sourceQuery();
            const url = `${this.apiBase()}/api/stock/trade-observe/list?page=1&page_size=500${qs ? `&${qs}` : ''}`;
            const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
            const res = await fetchFn(url);
            if (!res.ok) {
                const t = await res.text().catch(() => '');
                throw new Error(t || `加载失败 (${res.status})`);
            }
            const data = await res.json();
            const items = (data && data.items) || [];
            if (countEl) countEl.textContent = `共 ${data.total != null ? data.total : items.length} 只观察股`;
            this.renderObserve(items);
        } catch (e) {
            if (tbody) {
                tbody.innerHTML = `<tr><td colspan="8" class="empty-state">${this.esc(e.message || '加载失败')}</td></tr>`;
            }
            if (errEl) {
                errEl.hidden = false;
                errEl.textContent = e.message || '加载失败';
            }
            if (countEl) countEl.textContent = '';
        } finally {
            if (loadingEl) loadingEl.hidden = true;
        }
    },

    renderObserve(items) {
        const tbody = document.getElementById('utoObserveTableBody');
        if (!tbody) return;
        if (!items.length) {
            tbody.innerHTML = '<tr><td colspan="8" class="empty-state">暂无交易观察股票</td></tr>';
            return;
        }
        tbody.innerHTML = items
            .map((it) => {
                const src = it.source || '';
                const canFormal = this.FORMAL_SOURCES.has(src);
                const href = this.analysisHref(it.code, it.name);
                const name = it.name || '';
                const signalPrice = this.signalPriceFromItem(it);
                return `<tr data-id="${it.id}" data-source="${this.esc(src)}">
                    <td class="uto-col-code"><a class="stock-code gms-stock-code-link" href="${this.esc(href)}">${this.esc(it.code)}</a></td>
                    <td class="uto-col-name"><span class="uto-name-text" title="${this.esc(name)}">${this.esc(name)}</span></td>
                    <td class="uto-col-market">${this.esc(this.marketLabel(it.market))}</td>
                    <td class="uto-col-source">${this.esc(this.sourceLabel(src))}</td>
                    <td class="uto-col-num">${this.esc(this.fmtPrice(signalPrice))}</td>
                    <td class="uto-col-date">${this.esc(it.signal_date || '—')}</td>
                    <td class="uto-col-datetime">${this.esc(this.fmtDt(it.created_at))}</td>
                    <td class="uto-col-ops">
                        <div class="uto-ops">
                            ${canFormal ? `<button type="button" class="gms-op-btn gms-op-btn--primary uto-transfer" data-id="${it.id}" title="转入正式交易">转正式</button>` : ''}
                            <button type="button" class="gms-op-btn uto-remove" data-id="${it.id}" title="移出交易观察">移除</button>
                        </div>
                    </td>
                </tr>`;
            })
            .join('');
    },

    async _onObserveClick(e) {
        const rm = e.target.closest('.uto-remove');
        if (rm) {
            const id = parseInt(rm.getAttribute('data-id'), 10);
            if (id) await this.removeObserve(id);
            return;
        }
        const transfer = e.target.closest('.uto-transfer');
        if (transfer) {
            const id = parseInt(transfer.getAttribute('data-id'), 10);
            if (id) await this.transferFormal(id);
        }
    },

    async removeObserve(id) {
        if (!window.confirm('确定移出交易观察？')) return;
        try {
            const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
            const res = await fetchFn(`${this.apiBase()}/api/stock/trade-observe/${id}`, {
                method: 'DELETE',
            });
            if (!res.ok) {
                const t = await res.text().catch(() => '');
                throw new Error(t || '移除失败');
            }
            if (window.CommonUtils) CommonUtils.showToast('已移出交易观察', 'success');
            await this.refreshObserve();
        } catch (e) {
            if (window.CommonUtils) CommonUtils.showToast(e.message || '移除失败', 'error');
        }
    },

    async transferFormal(observeId) {
        const entryRaw = window.prompt('请输入入场价');
        if (entryRaw == null) return;
        const entryPrice = parseFloat(String(entryRaw).trim());
        if (!(entryPrice > 0)) {
            if (window.CommonUtils) CommonUtils.showToast('入场价无效', 'warning');
            return;
        }
        let positionLots = 0;
        const lotsRaw = window.prompt('手数（可选，GMS/URT 用，默认 0）', '0');
        if (lotsRaw != null && String(lotsRaw).trim() !== '') {
            positionLots = parseInt(String(lotsRaw).trim(), 10) || 0;
        }
        try {
            const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
            const res = await fetchFn(
                `${this.apiBase()}/api/stock/formal-trade/from-observe/${observeId}`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        entry_price: entryPrice,
                        position_lots: positionLots,
                    }),
                }
            );
            if (!res.ok) {
                let msg = '转入失败';
                try {
                    const j = await res.json();
                    msg = j.detail || j.message || msg;
                } catch (_) {
                    const t = await res.text().catch(() => '');
                    if (t) msg = t;
                }
                throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
            if (window.CommonUtils) CommonUtils.showToast('已转入正式交易', 'success');
            this.switchSub('formal');
        } catch (e) {
            if (window.CommonUtils) CommonUtils.showToast(e.message || '转入失败', 'error');
        }
    },

    async refreshFormal() {
        const errEl = document.getElementById('utoFormalError');
        const loadingEl = document.getElementById('utoFormalLoading');
        const tbody = document.getElementById('utoFormalTableBody');
        const countEl = document.getElementById('utoCount');
        if (errEl) {
            errEl.hidden = true;
            errEl.textContent = '';
        }
        if (loadingEl) loadingEl.hidden = false;
        try {
            if (!window.CommonUtils || !CommonUtils.checkLoginAndHandleExpiry()) {
                throw new Error('请先登录后查看正式交易');
            }
            const qs = this.sourceQuery();
            const url = `${this.apiBase()}/api/stock/formal-trade/list?page=1&page_size=500${qs ? `&${qs}` : ''}`;
            const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
            const res = await fetchFn(url);
            if (!res.ok) {
                const t = await res.text().catch(() => '');
                throw new Error(t || `加载失败 (${res.status})`);
            }
            const data = await res.json();
            const items = (data && data.items) || [];
            if (countEl) countEl.textContent = `共 ${data.total != null ? data.total : items.length} 笔正式交易`;
            this.renderFormal(items);
        } catch (e) {
            if (tbody) {
                tbody.innerHTML = `<tr><td colspan="11" class="empty-state">${this.esc(e.message || '加载失败')}</td></tr>`;
            }
            if (errEl) {
                errEl.hidden = false;
                errEl.textContent = e.message || '加载失败';
            }
            if (countEl) countEl.textContent = '';
        } finally {
            if (loadingEl) loadingEl.hidden = true;
        }
    },

    renderFormal(items) {
        const tbody = document.getElementById('utoFormalTableBody');
        if (!tbody) return;
        if (!items.length) {
            tbody.innerHTML = '<tr><td colspan="11" class="empty-state">暂无正式交易记录</td></tr>';
            return;
        }
        tbody.innerHTML = items
            .map((it) => {
                const href = this.analysisHref(it.code, it.name);
                const name = it.name || '';
                const open = String(it.status || '') === 'open';
                const stCls = open ? 'uto-status-open' : 'uto-status-closed';
                let pnlHtml = '—';
                if (it.pnl_percent != null && it.pnl_percent !== '') {
                    const n = Number(it.pnl_percent);
                    const pnlCls = n > 0 ? 'uto-pnl-up' : (n < 0 ? 'uto-pnl-down' : '');
                    pnlHtml = `<span class="${pnlCls}">${n.toFixed(2)}</span>`;
                }
                const notesTitle = it.notes ? ` title="${this.esc(it.notes)}"` : '';
                return `<tr data-id="${it.id}">
                    <td class="uto-col-code"><a class="stock-code gms-stock-code-link" href="${this.esc(href)}">${this.esc(it.code)}</a></td>
                    <td class="uto-col-name"><span class="uto-name-text" title="${this.esc(name)}">${this.esc(name)}</span></td>
                    <td class="uto-col-source">${this.esc(this.sourceLabel(it.source))}</td>
                    <td class="uto-col-status"><span class="${stCls}"${notesTitle}>${this.esc(this.statusLabel(it.status))}</span></td>
                    <td class="uto-col-num">${this.esc(this.fmtPrice(it.entry_price))}</td>
                    <td class="uto-col-num">${this.esc(this.fmtPrice(it.exit_price))}</td>
                    <td class="uto-col-num">${it.position_lots != null ? this.esc(it.position_lots) : '—'}</td>
                    <td class="uto-col-num">${pnlHtml}</td>
                    <td class="uto-col-date">${this.esc(it.signal_date || '—')}</td>
                    <td class="uto-col-datetime">${this.esc(this.fmtDt(it.entry_at))}</td>
                    <td class="uto-col-ops">
                        <div class="uto-ops">
                            ${open ? `<button type="button" class="gms-op-btn uto-close-formal" data-id="${it.id}">平仓</button>` : ''}
                        </div>
                    </td>
                </tr>`;
            })
            .join('');
    },

    async _onFormalClick(e) {
        const btn = e.target.closest('.uto-close-formal');
        if (!btn) return;
        const id = parseInt(btn.getAttribute('data-id'), 10);
        if (!id) return;
        const exitRaw = window.prompt('请输入出场价');
        if (exitRaw == null) return;
        const exitPrice = parseFloat(String(exitRaw).trim());
        if (!(exitPrice > 0)) {
            if (window.CommonUtils) CommonUtils.showToast('出场价无效', 'warning');
            return;
        }
        try {
            const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
            const res = await fetchFn(`${this.apiBase()}/api/stock/formal-trade/${id}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ exit_price: exitPrice, status: 'closed' }),
            });
            if (!res.ok) {
                const t = await res.text().catch(() => '');
                throw new Error(t || '平仓失败');
            }
            if (window.CommonUtils) CommonUtils.showToast('已平仓', 'success');
            await this.refreshFormal();
        } catch (err) {
            if (window.CommonUtils) CommonUtils.showToast(err.message || '平仓失败', 'error');
        }
    },
};

if (typeof window !== 'undefined') {
    window.UnifiedTradeObserve = UnifiedTradeObserve;
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => UnifiedTradeObserve.init());
    } else {
        UnifiedTradeObserve.init();
    }
}

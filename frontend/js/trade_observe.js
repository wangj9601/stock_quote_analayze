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
        gann_trend: '江恩趋势',
        recommend: '策略推荐',
    },
    FORMAL_SOURCES: new Set(['gms', 'urt', 'sbbr', 'rpe']),
    LOTS_SOURCES: new Set(['gms', 'urt']),
    _observeItems: new Map(),
    _formalItems: new Map(),
    _loading: false,
    _seq: 0,

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
            const on = b.getAttribute('data-uto-sub') === this.sub;
            b.classList.toggle('active', on);
            b.setAttribute('aria-selected', on ? 'true' : 'false');
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
        if (v === 'HK') return '港股';
        if (v === 'CN' || v === 'A' || v === 'SH' || v === 'SZ') return 'A股';
        return v || '—';
    },

    esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    },

    fetchFn() {
        return typeof authFetch === 'function' ? authFetch : fetch;
    },

    /** 后端报错多为 {"detail": "..."}；取出可读文案，避免把原始 JSON 丢给用户 */
    async readError(res, fallback) {
        const raw = await res.text().catch(() => '');
        if (!raw) return `${fallback}（${res.status}）`;
        try {
            const j = JSON.parse(raw);
            const d = j.detail != null ? j.detail : j.message;
            if (typeof d === 'string' && d) return d;
            if (Array.isArray(d) && d.length && d[0].msg) return d[0].msg;
        } catch (_) { /* 非 JSON */ }
        return raw.length > 120 ? `${fallback}（${res.status}）` : raw;
    },

    toast(msg, type) {
        if (window.CommonUtils && CommonUtils.showToast) CommonUtils.showToast(msg, type);
    },

    setLoading(on) {
        this._loading = !!on;
        const btn = document.getElementById('utoRefreshBtn');
        if (btn) {
            btn.disabled = !!on;
            btn.textContent = on ? '加载中…' : '刷新';
        }
    },

    _rowMessage(tbody, cols, text, isError) {
        if (!tbody) return;
        tbody.innerHTML = `<tr><td colspan="${cols}" class="empty-state${isError ? ' uto-empty--error' : ''}">${this.esc(text)}</td></tr>`;
    },

    /**
     * 行内操作对话框，替代原生 prompt/confirm。
     * fields: [{ name, label, value, min, step, hint }]；返回 Promise<值对象|null>。
     */
    openDialog({ title, desc, fields, confirmText, danger, onInput }) {
        const dlg = document.getElementById('utoDialog');
        if (!dlg || typeof dlg.showModal !== 'function') {
            return Promise.resolve(this._fallbackDialog(title, fields));
        }
        const form = dlg.querySelector('form');
        dlg.querySelector('.uto-dialog-title').textContent = title;
        const descEl = dlg.querySelector('.uto-dialog-desc');
        descEl.textContent = desc || '';
        descEl.hidden = !desc;
        const body = dlg.querySelector('.uto-dialog-fields');
        body.innerHTML = (fields || [])
            .map((f) => `
                <label class="uto-field">
                    <span class="uto-field-label">${this.esc(f.label)}</span>
                    <input type="number" name="${this.esc(f.name)}" inputmode="decimal"
                        value="${f.value != null ? this.esc(f.value) : ''}"
                        ${f.min != null ? `min="${f.min}"` : ''} step="${f.step || 'any'}"
                        ${f.required ? 'required' : ''} autocomplete="off">
                    ${f.hint ? `<span class="uto-field-hint">${this.esc(f.hint)}</span>` : ''}
                </label>`)
            .join('');
        const preview = dlg.querySelector('.uto-dialog-preview');
        preview.textContent = '';
        preview.hidden = true;
        const okBtn = dlg.querySelector('.uto-dialog-ok');
        okBtn.textContent = confirmText || '确定';
        okBtn.classList.toggle('uto-dialog-ok--danger', !!danger);

        const readValues = () => {
            const out = {};
            (fields || []).forEach((f) => {
                const el = form.elements.namedItem(f.name);
                out[f.name] = el ? el.value : '';
            });
            return out;
        };
        const refreshPreview = () => {
            if (typeof onInput !== 'function') return;
            const html = onInput(readValues());
            preview.innerHTML = html || '';
            preview.hidden = !html;
        };
        refreshPreview();

        return new Promise((resolve) => {
            const cleanup = () => {
                form.removeEventListener('submit', onSubmit);
                form.removeEventListener('input', refreshPreview);
                dlg.removeEventListener('close', onClose);
            };
            const onSubmit = (e) => {
                e.preventDefault();
                if (!form.reportValidity()) return;
                const vals = readValues();
                cleanup();
                dlg.close();
                resolve(vals);
            };
            const onClose = () => {
                cleanup();
                resolve(null);
            };
            form.addEventListener('submit', onSubmit);
            form.addEventListener('input', refreshPreview);
            dlg.addEventListener('close', onClose);
            dlg.showModal();
            const first = form.querySelector('input');
            if (first) {
                first.focus();
                first.select();
            } else {
                okBtn.focus();
            }
        });
    },

    _fallbackDialog(title, fields) {
        if (!fields || !fields.length) return window.confirm(title) ? {} : null;
        const out = {};
        for (let i = 0; i < fields.length; i += 1) {
            const f = fields[i];
            const v = window.prompt(f.label, f.value != null ? String(f.value) : '');
            if (v == null) return null;
            out[f.name] = v;
        }
        return out;
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

    analysisHref(code, name, popup) {
        if (window.StockTradeLink && typeof window.StockTradeLink.buildHref === 'function') {
            return window.StockTradeLink.buildHref(code, name, { tab: 'analysis', popup: !!popup });
        }
        const q = new URLSearchParams({
            tab: 'analysis',
            code: String(code || ''),
            name: String(name || ''),
        });
        if (popup) q.set('popup', '1');
        return `stock.html?${q.toString()}`;
    },

    /**
     * 左键弹出个股分析窗口；Ctrl/Cmd/中键仍走浏览器默认（新标签）。
     */
    openAnalysisPopup(href, e) {
        if (e) {
            if (e.defaultPrevented) return;
            if (e.button != null && e.button !== 0) return;
            if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
            e.preventDefault();
        }
        const url = (() => {
            try {
                const u = new URL(href, window.location.href);
                u.searchParams.set('popup', '1');
                return u.toString();
            } catch (_) {
                const sep = String(href || '').indexOf('?') >= 0 ? '&' : '?';
                return `${href}${sep}popup=1`;
            }
        })();
        const features = 'popup=yes,width=1280,height=860,left=72,top=48,scrollbars=yes,resizable=yes';
        const w = window.open(url, 'uto_stock_trade', features);
        if (!w) {
            if (window.CommonUtils) {
                CommonUtils.showToast('浏览器拦截了弹窗，请允许后重试，或按住 Ctrl 点击在新标签打开', 'warning');
            }
            return false;
        }
        try {
            w.opener = null;
        } catch (_) { /* ignore */ }
        try {
            w.focus();
        } catch (_) { /* ignore */ }
        return true;
    },

    async refresh() {
        if (this.sub === 'formal') {
            await this.refreshFormal();
        } else {
            await this.refreshObserve();
        }
    },

    async refreshObserve() {
        this._seq = (this._seq || 0) + 1;
        const seq = this._seq;
        const tbody = document.getElementById('utoObserveTableBody');
        const countEl = document.getElementById('utoCount');
        this.setLoading(true);
        this._rowMessage(tbody, 8, '加载中…');
        try {
            if (!window.CommonUtils || !CommonUtils.checkLoginAndHandleExpiry()) {
                throw new Error('请先登录后查看交易观察列表');
            }
            const qs = this.sourceQuery();
            const url = `${this.apiBase()}/api/stock/trade-observe/list?page=1&page_size=500${qs ? `&${qs}` : ''}`;
            const res = await this.fetchFn()(url);
            if (!res.ok) throw new Error(await this.readError(res, '观察列表加载失败'));
            const data = await res.json();
            if (seq !== this._seq) return;
            const items = (data && data.items) || [];
            if (countEl) countEl.textContent = `共 ${data.total != null ? data.total : items.length} 只观察股`;
            this.renderObserve(items);
        } catch (e) {
            if (seq !== this._seq) return;
            this._rowMessage(tbody, 8, e.message || '观察列表加载失败', true);
            if (countEl) countEl.textContent = '';
        } finally {
            if (seq === this._seq) this.setLoading(false);
        }
    },

    renderObserve(items) {
        const tbody = document.getElementById('utoObserveTableBody');
        if (!tbody) return;
        this._observeItems = new Map(items.map((it) => [String(it.id), it]));
        if (!items.length) {
            const filtered = !!this.sourceQuery();
            this._rowMessage(
                tbody,
                8,
                filtered
                    ? '该来源下暂无观察股票，可切换「来源」为全部'
                    : '暂无交易观察股票。可在选股结果或个股分析中点「交易观察」加入'
            );
            return;
        }
        tbody.innerHTML = items
            .map((it) => {
                const src = it.source || '';
                const canFormal = this.FORMAL_SOURCES.has(src);
                const href = this.analysisHref(it.code, it.name);
                const name = it.name || '';
                const label = this.esc(name || it.code);
                const signalPrice = this.signalPriceFromItem(it);
                const nameTitle = [
                    name,
                    this.marketLabel(it.market),
                    this.sourceLabel(src),
                    signalPrice != null ? `信号价 ${this.fmtPrice(signalPrice)}` : '',
                    it.signal_date ? `信号日 ${it.signal_date}` : '',
                    it.created_at ? `加入 ${this.fmtDt(it.created_at)}` : '',
                ].filter(Boolean).join(' · ');
                return `<tr data-id="${it.id}" data-source="${this.esc(src)}">
                    <td class="uto-col-code"><a class="stock-code gms-stock-code-link" href="${this.esc(href)}" target="_blank" rel="noopener noreferrer" title="弹出个股分析">${this.esc(it.code)}</a></td>
                    <td class="uto-col-name"><span class="uto-name-text" title="${this.esc(nameTitle)}">${this.esc(name)}</span></td>
                    <td class="uto-col-market">${this.esc(this.marketLabel(it.market))}</td>
                    <td class="uto-col-source"><span class="uto-src">${this.esc(this.sourceLabel(src))}</span></td>
                    <td class="uto-col-num">${this.esc(this.fmtPrice(signalPrice))}</td>
                    <td class="uto-col-date">${this.esc(it.signal_date || '—')}</td>
                    <td class="uto-col-datetime">${this.esc(this.fmtDt(it.created_at))}</td>
                    <td class="uto-col-ops">
                        <div class="uto-ops">
                            ${canFormal
                                ? `<button type="button" class="rsa-op rsa-op--primary uto-transfer" data-id="${it.id}" title="填写入场价后转入正式交易" aria-label="${label} 转正式交易">转正式</button>`
                                : ''}
                            <button type="button" class="rsa-op rsa-op--danger uto-remove" data-id="${it.id}" title="移出交易观察" aria-label="移除 ${label}">移除</button>
                        </div>
                    </td>
                </tr>`;
            })
            .join('');
    },

    async _onObserveClick(e) {
        const link = e.target.closest('a.gms-stock-code-link, a.stock-code');
        if (link) {
            this.openAnalysisPopup(link.getAttribute('href'), e);
            return;
        }
        const rm = e.target.closest('.uto-remove');
        if (rm) {
            const id = parseInt(rm.getAttribute('data-id'), 10);
            if (id) await this.removeObserve(id, rm);
            return;
        }
        const transfer = e.target.closest('.uto-transfer');
        if (transfer) {
            const id = parseInt(transfer.getAttribute('data-id'), 10);
            if (id) await this.transferFormal(id, transfer);
        }
    },

    _itemTitle(it) {
        if (!it) return '';
        return `${it.name || ''} ${it.code || ''}`.trim();
    },

    async removeObserve(id, btn) {
        const it = this._observeItems.get(String(id));
        const ok = await this.openDialog({
            title: '移出交易观察',
            desc: `确定将 ${this._itemTitle(it) || '该股票'} 移出交易观察？移出后需从原入口重新加入。`,
            fields: [],
            confirmText: '移除',
            danger: true,
        });
        if (!ok) return;
        if (btn) btn.disabled = true;
        try {
            const res = await this.fetchFn()(`${this.apiBase()}/api/stock/trade-observe/${id}`, {
                method: 'DELETE',
            });
            if (!res.ok) throw new Error(await this.readError(res, '移除失败'));
            this.toast('已移出交易观察', 'success');
            await this.refreshObserve();
        } catch (e) {
            this.toast(e.message || '移除失败', 'error');
            if (btn) btn.disabled = false;
        }
    },

    async transferFormal(observeId, btn) {
        const it = this._observeItems.get(String(observeId));
        const signalPrice = this.signalPriceFromItem(it);
        const needLots = it && this.LOTS_SOURCES.has(it.source);
        const fields = [
            {
                name: 'entry',
                label: '入场价',
                value: signalPrice != null ? signalPrice.toFixed(2) : '',
                min: 0.01,
                step: 0.01,
                required: true,
                hint: signalPrice != null ? `已预填信号价 ${signalPrice.toFixed(2)}，按实际成交修改` : '',
            },
        ];
        if (needLots) {
            fields.push({ name: 'lots', label: '手数', value: 0, min: 0, step: 1, hint: 'GMS / URT 持仓手数，可留 0' });
        }
        const vals = await this.openDialog({
            title: '转入正式交易',
            desc: `${this._itemTitle(it)}${it ? ` · 来源 ${this.sourceLabel(it.source)}` : ''}`,
            fields,
            confirmText: '转入',
        });
        if (!vals) return;
        const entryPrice = parseFloat(String(vals.entry || '').trim());
        if (!(entryPrice > 0)) {
            this.toast('入场价需大于 0', 'warning');
            return;
        }
        const positionLots = needLots ? (parseInt(String(vals.lots || '0').trim(), 10) || 0) : 0;
        if (btn) btn.disabled = true;
        try {
            const res = await this.fetchFn()(
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
            if (!res.ok) throw new Error(await this.readError(res, '转入失败'));
            this.toast('已转入正式交易', 'success');
            this.switchSub('formal');
        } catch (e) {
            this.toast(e.message || '转入失败', 'error');
            if (btn) btn.disabled = false;
        }
    },

    async refreshFormal() {
        this._seq = (this._seq || 0) + 1;
        const seq = this._seq;
        const tbody = document.getElementById('utoFormalTableBody');
        const countEl = document.getElementById('utoCount');
        this.setLoading(true);
        this._rowMessage(tbody, 11, '加载中…');
        try {
            if (!window.CommonUtils || !CommonUtils.checkLoginAndHandleExpiry()) {
                throw new Error('请先登录后查看正式交易');
            }
            const qs = this.sourceQuery();
            const url = `${this.apiBase()}/api/stock/formal-trade/list?page=1&page_size=500${qs ? `&${qs}` : ''}`;
            const res = await this.fetchFn()(url);
            if (!res.ok) throw new Error(await this.readError(res, '正式交易加载失败'));
            const data = await res.json();
            if (seq !== this._seq) return;
            const items = (data && data.items) || [];
            if (countEl) countEl.textContent = `共 ${data.total != null ? data.total : items.length} 笔正式交易`;
            this.renderFormal(items);
        } catch (e) {
            if (seq !== this._seq) return;
            this._rowMessage(tbody, 11, e.message || '正式交易加载失败', true);
            if (countEl) countEl.textContent = '';
        } finally {
            if (seq === this._seq) this.setLoading(false);
        }
    },

    fmtPnl(v) {
        if (v == null || v === '' || Number.isNaN(Number(v))) return null;
        const n = Number(v);
        return { text: `${n > 0 ? '+' : ''}${n.toFixed(2)}`, cls: n > 0 ? 'uto-pnl-up' : (n < 0 ? 'uto-pnl-down' : '') };
    },

    renderFormal(items) {
        const tbody = document.getElementById('utoFormalTableBody');
        if (!tbody) return;
        this._formalItems = new Map(items.map((it) => [String(it.id), it]));
        if (!items.length) {
            this._rowMessage(
                tbody,
                11,
                this.sourceQuery()
                    ? '该来源下暂无正式交易，可切换「来源」为全部'
                    : '暂无正式交易。在「观察列表」中对 GMS / URT / SBBR / RPE 来源点「转正式」'
            );
            return;
        }
        tbody.innerHTML = items
            .map((it) => {
                const href = this.analysisHref(it.code, it.name);
                const name = it.name || '';
                const label = this.esc(name || it.code);
                const open = String(it.status || '') === 'open';
                const stCls = open ? 'uto-status uto-status-open' : 'uto-status uto-status-closed';
                const pnl = this.fmtPnl(it.pnl_percent);
                const nameTitle = [
                    name,
                    this.sourceLabel(it.source),
                    this.statusLabel(it.status),
                    it.entry_price != null ? `入场 ${this.fmtPrice(it.entry_price)}` : '',
                    it.exit_price != null ? `出场 ${this.fmtPrice(it.exit_price)}` : '',
                    pnl ? `盈亏 ${pnl.text}%` : '',
                    it.signal_date ? `信号日 ${it.signal_date}` : '',
                    it.entry_at ? `入场 ${this.fmtDt(it.entry_at)}` : '',
                ].filter(Boolean).join(' · ');
                const pnlHtml = pnl ? `<span class="${pnl.cls}">${this.esc(pnl.text)}</span>` : '—';
                const notesTitle = it.notes ? ` title="${this.esc(it.notes)}"` : '';
                return `<tr data-id="${it.id}">
                    <td class="uto-col-code"><a class="stock-code gms-stock-code-link" href="${this.esc(href)}" target="_blank" rel="noopener noreferrer" title="弹出个股分析">${this.esc(it.code)}</a></td>
                    <td class="uto-col-name"><span class="uto-name-text" title="${this.esc(nameTitle)}">${this.esc(name)}</span></td>
                    <td class="uto-col-source"><span class="uto-src">${this.esc(this.sourceLabel(it.source))}</span></td>
                    <td class="uto-col-status"><span class="${stCls}"${notesTitle}>${this.esc(this.statusLabel(it.status))}</span></td>
                    <td class="uto-col-num">${this.esc(this.fmtPrice(it.entry_price))}</td>
                    <td class="uto-col-num">${this.esc(this.fmtPrice(it.exit_price))}</td>
                    <td class="uto-col-num">${it.position_lots != null ? this.esc(it.position_lots) : '—'}</td>
                    <td class="uto-col-num">${pnlHtml}</td>
                    <td class="uto-col-date">${this.esc(it.signal_date || '—')}</td>
                    <td class="uto-col-datetime">${this.esc(this.fmtDt(it.entry_at))}</td>
                    <td class="uto-col-ops">
                        <div class="uto-ops">
                            ${open
                                ? `<button type="button" class="rsa-op rsa-op--primary uto-close-formal" data-id="${it.id}" title="填写出场价并平仓" aria-label="平仓 ${label}">平仓</button>`
                                : '<span class="uto-ops-none">—</span>'}
                        </div>
                    </td>
                </tr>`;
            })
            .join('');
    },

    async _onFormalClick(e) {
        const link = e.target.closest('a.gms-stock-code-link, a.stock-code');
        if (link) {
            this.openAnalysisPopup(link.getAttribute('href'), e);
            return;
        }
        const btn = e.target.closest('.uto-close-formal');
        if (!btn) return;
        const id = parseInt(btn.getAttribute('data-id'), 10);
        if (!id) return;
        const it = this._formalItems.get(String(id));
        const entry = it && it.entry_price != null ? Number(it.entry_price) : null;
        const vals = await this.openDialog({
            title: '平仓',
            desc: `${this._itemTitle(it)}${entry ? ` · 入场价 ${entry.toFixed(2)}` : ''}`,
            fields: [{ name: 'exit', label: '出场价', value: '', min: 0.01, step: 0.01, required: true }],
            confirmText: '确认平仓',
            onInput: (v) => {
                const x = parseFloat(v.exit);
                if (!(entry > 0) || !(x > 0)) return '';
                const pnl = this.fmtPnl(((x - entry) / entry) * 100);
                return `预估盈亏 <strong class="${pnl.cls}">${this.esc(pnl.text)}%</strong>`;
            },
        });
        if (!vals) return;
        const exitPrice = parseFloat(String(vals.exit || '').trim());
        if (!(exitPrice > 0)) {
            this.toast('出场价需大于 0', 'warning');
            return;
        }
        btn.disabled = true;
        try {
            const res = await this.fetchFn()(`${this.apiBase()}/api/stock/formal-trade/${id}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ exit_price: exitPrice, status: 'closed' }),
            });
            if (!res.ok) throw new Error(await this.readError(res, '平仓失败'));
            this.toast('已平仓', 'success');
            await this.refreshFormal();
        } catch (err) {
            this.toast(err.message || '平仓失败', 'error');
            btn.disabled = false;
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

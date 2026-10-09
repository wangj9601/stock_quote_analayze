// 每日复盘工作台
const DailyReviewPage = {
    API_BASE_URL: typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : '',
    _loaded: false,
    _loadedDate: null,
    _seq: 0,
    data: null,

    init() {
        const dateEl = document.getElementById('drTradeDate');
        if (dateEl && !dateEl.value) {
            const d = new Date();
            // 默认昨天（日终复盘）
            d.setDate(d.getDate() - 1);
            dateEl.value = this.localDate(d);
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

    localDate(d) {
        const p = (n) => String(n).padStart(2, '0');
        return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
    },

    // 请求期间锁定工具栏，防止重复提交；返回解锁函数
    lockToolbar(activeBtnId, busyText) {
        const bar = document.querySelector('#daily-review .dr-toolbar');
        const btns = bar ? Array.from(bar.querySelectorAll('button')) : [];
        const active = document.getElementById(activeBtnId);
        const idle = active ? active.textContent : '';
        btns.forEach((b) => { b.disabled = true; });
        if (active) {
            active.setAttribute('aria-busy', 'true');
            if (busyText) active.textContent = busyText;
        }
        return () => {
            btns.forEach((b) => { b.disabled = false; });
            if (active) {
                active.removeAttribute('aria-busy');
                active.textContent = idle;
            }
        };
    },

    async load() {
        const d = this.tradeDate();
        const seq = ++this._seq;
        this.setStatus('加载中…', 'busy');
        const unlock = this.lockToolbar('drLoadBtn', '加载中…');
        try {
            const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
            const resp = await fetchFn(
                `${this.API_BASE_URL}/api/market_review/daily?trade_date=${encodeURIComponent(d)}`
            );
            const payload = await resp.json().catch(() => ({}));
            if (seq !== this._seq) return;
            if (!resp.ok || !payload.success) {
                this.data = null;
                this.renderEmpty();
                const noSnap = resp.status === 404;
                this.setStatus(noSnap ? `${d} 暂无复盘快照，可点击「重算」生成` : (payload.message || `加载失败（${resp.status}）`), noSnap ? '' : 'error');
                return;
            }
            this.data = payload.data || {};
            this.render(this.data);
            this._loadedDate = d;
            this.setStatus(`已加载 ${d}（口径 ${this.data.limit_source || '--'}）`, 'ok');
            this._loaded = true;
        } catch (e) {
            if (seq !== this._seq) return;
            console.warn('[daily-review] load failed', e);
            this.setStatus(e.message || '加载失败，请检查网络或后端服务', 'error');
        } finally {
            unlock();
        }
    },

    async compute() {
        const d = this.tradeDate();
        const seq = ++this._seq;
        this.setStatus('正在重算（可能需数十秒）…', 'busy');
        const unlock = this.lockToolbar('drComputeBtn', '重算中…');
        try {
            const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
            const resp = await fetchFn(
                `${this.API_BASE_URL}/api/market_review/compute?trade_date=${encodeURIComponent(d)}&collect_zt=true&export_md=false&sync=true`,
                { method: 'POST' }
            );
            const payload = await resp.json().catch(() => ({}));
            if (!resp.ok || !payload.success) {
                throw new Error(payload.message || `重算失败 ${resp.status}`);
            }
            if (seq !== this._seq) return;
            this.data = payload.data || {};
            this.render(this.data);
            this._loadedDate = d;
            this.setStatus(`重算完成 ${d} · ${this.data.limit_source || ''} · 季节 ${this.data.season || ''}`, 'ok');
        } catch (e) {
            if (seq !== this._seq) return;
            console.warn('[daily-review] compute failed', e);
            this.setStatus(e.message || '重算失败', 'error');
        } finally {
            unlock();
        }
    },

    async save() {
        const d = this.tradeDate();
        if (!this.data || this._loadedDate !== d) {
            this.setStatus(this._loadedDate
                ? `交易日已改为 ${d}，当前显示的是 ${this._loadedDate}，请先「加载」再保存`
                : `${d} 暂无复盘快照，请先「加载」或「重算」再保存`, 'error');
            return;
        }
        const viewpoint = (document.getElementById('drViewpoint') || {}).value || '';
        const advice = (document.getElementById('drAdvice') || {}).value || '';
        this.setStatus('保存中…', 'busy');
        const unlock = this.lockToolbar('drSaveBtn', '保存中…');
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
            this.setStatus(`${d} 观点/建议已保存`, 'ok');
        } catch (e) {
            this.setStatus(e.message || '保存失败', 'error');
        } finally {
            unlock();
        }
    },

    async exportMd() {
        const d = this.tradeDate();
        this.setStatus('正在生成 Markdown…', 'busy');
        const unlock = this.lockToolbar('drExportBtn', '导出中…');
        try {
            const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
            const resp = await fetchFn(
                `${this.API_BASE_URL}/api/market_review/export.md?trade_date=${encodeURIComponent(d)}`
            );
            const ct = (resp.headers.get('Content-Type') || '').toLowerCase();
            if (!resp.ok || ct.includes('application/json')) {
                const payload = await resp.json().catch(() => ({}));
                throw new Error(payload.message || '导出失败');
            }
            const blob = await resp.blob();
            const filename = this._downloadName(resp, `daily_review_${d}.md`);
            this._saveBlob(blob, filename);
            const text = await blob.text();
            this.setMarkdownPreview(text);
            this.setStatus(`已下载 ${filename}`, 'ok');
        } catch (e) {
            this.setStatus(e.message || '导出失败', 'error');
        } finally {
            unlock();
        }
    },

    async exportPdf() {
        const d = this.tradeDate();
        this.setStatus('正在生成 PDF…', 'busy');
        const unlock = this.lockToolbar('drExportPdfBtn', '导出中…');
        try {
            const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
            const resp = await fetchFn(
                `${this.API_BASE_URL}/api/market_review/export.pdf?trade_date=${encodeURIComponent(d)}`
            );
            const ct = (resp.headers.get('Content-Type') || '').toLowerCase();
            if (!resp.ok || ct.includes('application/json')) {
                const payload = await resp.json().catch(() => ({}));
                throw new Error(payload.message || `PDF 导出失败 ${resp.status}`);
            }
            const blob = await resp.blob();
            const filename = this._downloadName(resp, `daily_review_${d}.pdf`);
            this._saveBlob(blob, filename);
            this.setStatus(`已下载 ${filename}`, 'ok');
        } catch (e) {
            this.setStatus(e.message || 'PDF 导出失败', 'error');
        } finally {
            unlock();
        }
    },

    _downloadName(resp, fallback) {
        const cd = resp.headers.get('Content-Disposition') || '';
        const mStar = /filename\*=UTF-8''([^;]+)/i.exec(cd);
        const m = /filename=\"?([^\";]+)\"?/i.exec(cd);
        if (mStar) {
            try {
                return decodeURIComponent(mStar[1]);
            } catch (_) {
                return mStar[1];
            }
        }
        if (m) return m[1];
        return fallback;
    },

    _saveBlob(blob, filename) {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        a.click();
        URL.revokeObjectURL(a.href);
    },

    setStatus(msg, tone) {
        const el = document.getElementById('drStatus');
        if (!el) return;
        el.textContent = msg || '';
        el.classList.remove('is-busy', 'is-ok', 'is-error');
        if (tone) el.classList.add(`is-${tone}`);
    },

    renderEmpty() {
        this._loadedDate = null;
        const metrics = document.getElementById('drMetrics');
        if (metrics) metrics.innerHTML = '<p class="dr-empty">暂无数据</p>';
        this.fillBody('drGatesBody', 5, []);
        this.fillBody('drMainlineBody', 5, []);
        this.fillBody('drIndustryConfirmBody', 4, []);
        const rateEl = document.getElementById('drGatesRate');
        if (rateEl) rateEl.textContent = '';
        ['drTrendSummary', 'drMainlineSummary'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.textContent = '';
        });
        ['drViewpoint', 'drAdvice'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
        const indSum = document.getElementById('drIndustryConfirmSummary');
        if (indSum) indSum.textContent = '';
        this.fillBody('drIndexBody', 6, []);
        this.fillCollapsibleSectorBody('drLeadersBody', [], 'up');
        this.fillCollapsibleSectorBody('drLaggardsBody', [], 'down');
        this.fillBody('drCapitalInBody', 2, []);
        this.fillBody('drCapitalOutBody', 2, []);
        this.fillBody('drSealBody', 4, []);
        this.fillBody('drFlowBody', 2, []);
        this.fillBody('drMainFlowBody', 2, []);
        this.fillBody('drNoChaseBody', 7, []);
        this.fillBody('drTrackBody', 11, []);
        this.fillBody('drSidelineBody', 4, []);
        this.fillBody('drAvoidBody', 3, []);
        this.fillBody('drZhabBody', 9, []);
        ['drEnvSummary', 'drMainSide', 'drRotation', 'drLadder', 'drCurveNote'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.textContent = '';
        });
        ['drSentimentFacts', 'drSentimentWatch'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.innerHTML = '';
        });
        this.setMarkdownPreview('');
    },

    fmt(v, digits) {
        if (v == null || v === '') return '--';
        const n = Number(v);
        if (Number.isNaN(n)) return String(v);
        if (digits === 0) return String(Math.round(n));
        return n.toFixed(digits == null ? 2 : digits);
    },

    fmtYi(row) {
        if (row && row.net_inflow_yi != null && row.net_inflow_yi !== '') {
            const n = Number(row.net_inflow_yi);
            return Number.isNaN(n) ? '--' : n.toFixed(1);
        }
        if (!row || row.net_inflow == null || row.net_inflow === '') return '--';
        const n = Number(row.net_inflow);
        if (Number.isNaN(n)) return '--';
        return (n / 1e8).toFixed(1);
    },

    breadthText(data) {
        const b = data && data.rules_json && data.rules_json.market_env && data.rules_json.market_env.breadth;
        if (!b || b.up_count == null) return '--';
        return `${b.up_count}/${b.down_count == null ? '--' : b.down_count}`;
    },

    curveHint(data, key) {
        const zones = (data.rules_json && data.rules_json.curve_zones) || {};
        const note = data.percentile_note || zones.percentile_note || '';
        if (note === '样本不足') return '样本不足 / 阈值未校准';
        return zones[key] || '';
    },

    /** 领涨/领跌默认展示条数，其余折叠 */
    SECTOR_LIST_VISIBLE: 10,

    fillBody(id, cols, htmlRows) {
        const el = document.getElementById(id);
        if (!el) return;
        el.classList.remove('is-expanded');
        el.innerHTML = htmlRows && htmlRows.length
            ? htmlRows.join('')
            : `<tr><td colspan="${cols}" class="dr-empty-cell">暂无</td></tr>`;
    },

    _clearSectorFoldBtn(tbodyId) {
        const host = document.querySelector(`[data-dr-fold-for="${tbodyId}"]`);
        if (host) host.remove();
    },

    /**
     * 领涨/领跌：缺省显示涨跌幅前 N，其余行折叠，按钮展开/收起。
     * @param {'up'|'down'} kind
     */
    fillCollapsibleSectorBody(tbodyId, rows, kind) {
        const el = document.getElementById(tbodyId);
        if (!el) return;
        this._clearSectorFoldBtn(tbodyId);
        el.classList.remove('is-expanded');
        const list = Array.isArray(rows) ? rows : [];
        const limit = this.SECTOR_LIST_VISIBLE;
        const kindLabel = kind === 'down' ? '下跌' : '上涨';
        if (!list.length) {
            el.innerHTML = '<tr><td colspan="4" class="dr-empty-cell">暂无</td></tr>';
            return;
        }
        const head = list.slice(0, limit);
        const rest = list.slice(limit);
        const rowHtml = (r, extra) => `<tr${extra ? ' class="dr-sector-extra"' : ''}>
                <td>${this.boardLinkHtml('industry', r)}</td>
                <td class="num">${this.signed(r.change_percent)}</td>
                <td class="num">${this.signed(this.yiValue(r), 1)}</td>
                <td class="num">${this.breadthPair(r)}</td>
            </tr>`;
        el.innerHTML =
            head.map((r) => rowHtml(r, false)).join('') +
            rest.map((r) => rowHtml(r, true)).join('');
        if (!rest.length) return;
        const wrap = el.closest('.dr-table-wrap');
        if (!wrap || !wrap.parentElement) return;
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'dr-sector-fold-btn';
        btn.dataset.drFoldFor = tbodyId;
        btn.setAttribute('aria-expanded', 'false');
        const collapsedLabel = `展开其余 ${rest.length} 个${kindLabel}行业`;
        btn.textContent = collapsedLabel;
        btn.addEventListener('click', () => {
            const open = el.classList.toggle('is-expanded');
            btn.textContent = open ? '收起' : collapsedLabel;
            btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
        wrap.insertAdjacentElement('afterend', btn);
    },

    breadthPair(row) {
        if (!row || (row.up_count == null && row.down_count == null)) return '--';
        return `${row.up_count == null ? '--' : row.up_count}/${row.down_count == null ? '--' : row.down_count}`;
    },

    sectorRows(rows) {
        return (rows || []).map(
            (r) => `<tr>
                <td>${this.boardLinkHtml('industry', r)}</td>
                <td class="num">${this.signed(r.change_percent)}</td>
                <td class="num">${this.signed(this.yiValue(r), 1)}</td>
                <td class="num">${this.breadthPair(r)}</td>
            </tr>`
        );
    },

    flowRows(rows) {
        return (rows || []).map(
            (r) => `<tr>
                <td>${this.boardLinkHtml('industry', r)}</td>
                <td class="num">${this.signed(this.yiValue(r), 1)}</td>
            </tr>`
        );
    },

    yiValue(row) {
        if (!row) return null;
        if (row.net_inflow_yi != null && row.net_inflow_yi !== '') return row.net_inflow_yi;
        if (row.net_inflow == null || row.net_inflow === '') return null;
        const n = Number(row.net_inflow);
        return Number.isNaN(n) ? null : n / 1e8;
    },

    signed(v, digits) {
        const n = Number(v);
        let cls = 'dr-flat';
        if (v != null && v !== '' && !Number.isNaN(n)) {
            if (n > 0) cls = 'dr-up';
            else if (n < 0) cls = 'dr-down';
        }
        return `<span class="${cls}">${this.fmt(v, digits)}</span>`;
    },

    stockCell(row) {
        const name = (row && (row.name || row.code)) || '--';
        const code = String((row && row.code) || '').trim();
        const nameHtml = this.escapeHtml(name);
        if (!code) return `<span class="dr-stock">${nameHtml}</span>`;
        const href = `stock.html?code=${encodeURIComponent(code)}&name=${encodeURIComponent(name)}`;
        return `<span class="dr-stock"><a class="dr-stock-link" href="${this.escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${nameHtml}</a><span class="dr-code">${this.escapeHtml(code)}</span></span>`;
    },

    escapeHtml(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    },

    setMarkdownPreview(md) {
        const el = document.getElementById('drMarkdownPreview');
        if (el) el.innerHTML = this.renderMarkdown(md || '');
    },

    mdInline(s) {
        return this.escapeHtml(s)
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/`([^`]+)`/g, '<code>$1</code>');
    },

    mdTable(block) {
        const rows = [];
        block.forEach((line) => {
            const cells = line.replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());
            if (cells.length && cells.every((c) => /^:?-+:?$/.test(c))) return;
            rows.push(cells);
        });
        if (!rows.length) return '';
        const head = rows[0];
        const toneIdx = head
            .map((h, i) => (/涨跌|涨幅|净流入/.test(h) ? i : -1))
            .filter((i) => i >= 0);
        const cell = (c, tag, i) => {
            let html = this.mdInline(c);
            const num = tag === 'td' && toneIdx.indexOf(i) >= 0;
            if (num) {
                const n = Number(String(c).replace(/[^\d.+-]/g, ''));
                if (!Number.isNaN(n) && n !== 0) html = `<span class="${n > 0 ? 'dr-up' : 'dr-down'}">${html}</span>`;
            }
            return `<${tag}${num ? ' class="num"' : ''}>${html}</${tag}>`;
        };
        const tr = (cells, tag) => `<tr>${cells.map((c, i) => cell(c, tag, i)).join('')}</tr>`;
        return `<div class="dr-table-wrap"><table class="dr-table"><thead>${tr(head, 'th')}</thead><tbody>${rows.slice(1).map((r) => tr(r, 'td')).join('')}</tbody></table></div>`;
    },

    renderMarkdown(src) {
        const text = String(src || '').replace(/\r\n/g, '\n');
        if (!text.trim()) return '<p class="dr-empty">暂无预览</p>';
        const lines = text.split('\n');
        const out = [];
        let i = 0;
        const isSpecial = (line) => /^(#{1,3}\s|\||>|---+\s*$|\d+\.\s|[-*]\s)/.test(line);
        while (i < lines.length) {
            const line = lines[i];
            if (!line.trim()) {
                i += 1;
                continue;
            }
            if (/^---+\s*$/.test(line.trim())) {
                out.push('<hr>');
                i += 1;
                continue;
            }
            const heading = /^(#{1,3})\s+(.*)$/.exec(line);
            if (heading) {
                const level = heading[1].length;
                out.push(`<h${level}>${this.mdInline(heading[2])}</h${level}>`);
                i += 1;
                continue;
            }
            if (line.trim().startsWith('|')) {
                const block = [];
                while (i < lines.length && lines[i].trim().startsWith('|')) {
                    block.push(lines[i]);
                    i += 1;
                }
                out.push(this.mdTable(block));
                continue;
            }
            if (/^>\s?/.test(line)) {
                const bits = [];
                while (i < lines.length && /^>\s?/.test(lines[i])) {
                    bits.push(lines[i].replace(/^>\s?/, ''));
                    i += 1;
                }
                out.push(`<blockquote><p>${this.mdInline(bits.join(' '))}</p></blockquote>`);
                continue;
            }
            if (/^[-*]\s+/.test(line) || /^\d+\.\s+/.test(line)) {
                const ordered = /^\d+\.\s+/.test(line);
                const re = ordered ? /^\d+\.\s+(.*)$/ : /^[-*]\s+(.*)$/;
                const items = [];
                while (i < lines.length && re.test(lines[i])) {
                    items.push(`<li>${this.mdInline(lines[i].match(re)[1])}</li>`);
                    i += 1;
                }
                out.push(ordered ? `<ol>${items.join('')}</ol>` : `<ul>${items.join('')}</ul>`);
                continue;
            }
            const para = [line];
            i += 1;
            while (i < lines.length && lines[i].trim() && !isSpecial(lines[i])) {
                para.push(lines[i]);
                i += 1;
            }
            out.push(`<p>${this.mdInline(para.join(' '))}</p>`);
        }
        return out.join('');
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

    renderPicks(picks) {
        const disclaimer = document.getElementById('drPicksDisclaimer');
        const note = document.getElementById('drPicksNote');
        if (!picks) {
            if (disclaimer) disclaimer.textContent = '重算后生成明日个股。规则合成参考，非投资建议。';
            if (note) note.textContent = '';
            this.fillBody('drNoChaseBody', 7, []);
            this.fillBody('drTrackBody', 11, []);
            this.fillBody('drSidelineBody', 4, []);
            this.fillBody('drAvoidBody', 3, []);
            this.fillBody('drZhabBody', 9, []);
            return;
        }
        if (disclaimer) disclaimer.textContent = picks.disclaimer || '规则合成参考，非投资建议。';
        if (note) note.textContent = picks.note || '';
        this.fillBody(
            'drNoChaseBody',
            7,
            (picks.no_chase || []).map(
                (r) => `<tr>
                    <td>${this.stockCell(r)}</td>
                    <td class="num">${r.board_count == null ? '--' : this.escapeHtml(r.board_count)}</td>
                    <td class="num">${this.fmt(r.seal_yi)}</td>
                    <td class="num">${r.break_count == null ? '--' : this.escapeHtml(r.break_count)}</td>
                    <td>${this.escapeHtml(r.limit_band || '--')}</td>
                    <td>${this.escapeHtml(r.stance || '--')}</td>
                    <td>${this.escapeHtml(r.trigger || '--')}</td>
                </tr>`
            )
        );
        this.fillBody(
            'drTrackBody',
            11,
            (picks.track || []).map((r) => {
                let stance = r.stance || '--';
                if (r.brief_stance) stance += `（简报${r.brief_stance}）`;
                return `<tr>
                    <td>${this.stockCell(r)}</td>
                    <td>${this.escapeHtml((r.strategies || []).join('、') || '--')}</td>
                    <td>${this.escapeHtml(stance)}</td>
                    <td class="num">${this.fmt(r.p_sup)}</td>
                    <td class="num">${this.fmt(r.p_res)}</td>
                    <td>${this.escapeHtml(r.trigger || '--')}</td>
                    <td>${this.escapeHtml(r.pattern || '--')}</td>
                    <td>${this.escapeHtml(r.macd || '--')}</td>
                    <td class="num">${this.fmt(r.rsi)}</td>
                    <td>${this.escapeHtml(r.kdj || '--')}</td>
                    <td>${this.escapeHtml(r.trend || '--')}</td>
                </tr>`;
            })
        );
        this.fillBody(
            'drSidelineBody',
            4,
            (picks.sideline || []).map(
                (r) => `<tr>
                    <td>${this.stockCell(r)}</td>
                    <td>${this.escapeHtml(r.industry || '--')}</td>
                    <td class="num">${this.signed(r.change_percent)}</td>
                    <td>${this.escapeHtml(r.stance || '只观察')}</td>
                </tr>`
            )
        );
        this.fillBody(
            'drAvoidBody',
            3,
            (picks.avoid || []).map(
                (r) => `<tr>
                    <td>${this.stockCell(r)}</td>
                    <td>${this.escapeHtml(r.reason || '--')}</td>
                    <td>回避</td>
                </tr>`
            )
        );
        const zhab = picks.zhab && typeof picks.zhab === 'object' ? picks.zhab : {};
        const zhabRows = [].concat(zhab.breakout || [], zhab.setup || []);
        this.fillBody(
            'drZhabBody',
            9,
            zhabRows.map((r) => {
                const stage = r.signal_type === 'breakout' ? '突破确认' : '蓄势观察';
                return `<tr>
                    <td>${this.stockCell(r)}</td>
                    <td>${this.escapeHtml(stage)}</td>
                    <td>${this.escapeHtml(r.zt_date || '--')}</td>
                    <td class="num">${r.consol_days == null ? '--' : this.escapeHtml(r.consol_days)}</td>
                    <td class="num">${this.fmt(r.box_low != null ? r.box_low : r.zt_mid)}</td>
                    <td class="num">${this.fmt(r.box_high)}</td>
                    <td>${this.escapeHtml(r.stance || '--')}</td>
                    <td>${this.escapeHtml(r.trigger || '--')}</td>
                    <td class="num">${this.fmt(r.score)}</td>
                </tr>`;
            })
        );
    },

    render(data) {
        if (!data) return this.renderEmpty();
        const metrics = document.getElementById('drMetrics');
        const rules = data.rules_json || {};
        const env = rules.market_env || {};
        const breadth = env.breadth || {};
        const zones = rules.curve_zones || {};
        if (metrics) {
            const loHint = this.curveHint(data, 'lo');
            const hiHint = this.curveHint(data, 'hi');
            const spHint = this.curveHint(data, 'sp');
            const delta = env.vol_delta_yi;
            let deltaTxt = '--';
            if (delta != null && delta !== '') {
                const n = Number(delta);
                deltaTxt = `${n > 0 ? '+' : ''}${this.fmt(n, 0)}`;
            }
            metrics.innerHTML = `
              <div class="dr-metric"><span>Vol(万亿)</span><strong>${this.fmt(data.vol_trillion)}</strong></div>
              <div class="dr-metric"><span>较昨日(亿)</span><strong>${deltaTxt}</strong></div>
              <div class="dr-metric"><span>涨停</span><strong>${this.fmt(data.limit_up_count, 0)}</strong></div>
              <div class="dr-metric"><span>跌停</span><strong>${breadth.limit_down_count == null ? '--' : breadth.limit_down_count}</strong></div>
              <div class="dr-metric"><span>平盘</span><strong>${breadth.flat_count == null ? '--' : breadth.flat_count}</strong></div>
              <div class="dr-metric"><span>上涨/下跌</span><strong>${this.breadthText(data)}</strong></div>
              <div class="dr-metric"><span>CB连板</span><strong>${this.fmt(data.cb_count, 0)}</strong></div>
              <div class="dr-metric"><span>高度H</span><strong>${this.fmt(data.height, 0)}</strong></div>
              <div class="dr-metric"><span>昨连板收益%</span><strong>${this.fmt(data.prev_cb_return)}</strong></div>
              <div class="dr-metric"><span>Lo</span><strong>${this.fmt(data.lo_value)}</strong>${loHint ? `<em>${this.escapeHtml(loHint)}</em>` : ''}</div>
              <div class="dr-metric"><span>Hi</span><strong>${this.fmt(data.hi_value)}</strong>${hiHint ? `<em>${this.escapeHtml(hiHint)}</em>` : ''}</div>
              <div class="dr-metric"><span>Sp</span><strong>${this.fmt(data.sp_value)}</strong>${spHint ? `<em>${this.escapeHtml(spHint)}</em>` : ''}</div>
              <div class="dr-metric"><span>季节</span><strong>${data.season || '--'}</strong></div>
              <div class="dr-metric"><span>盘面</span><strong>${this.escapeHtml((rules.tape && rules.tape.label) || '--')}</strong></div>
              <div class="dr-metric"><span>口径</span><strong>${data.limit_source || '--'}</strong></div>
            `;
        }

        const envSum = document.getElementById('drEnvSummary');
        if (envSum) {
            let line = `成交额 ${this.fmt(env.vol_trillion != null ? env.vol_trillion : data.vol_trillion)} 万亿`;
            if (env.vol_delta_yi != null && env.vol_delta_yi !== '') {
                const n = Number(env.vol_delta_yi);
                const verb = n > 0 ? '放量' : n < 0 ? '缩量' : '变化';
                line += `，较昨日${verb} ${this.fmt(Math.abs(n), 0)} 亿`;
            }
            if (env.above_2t) line += '，站上 2 万亿';
            line += `。上涨 ${breadth.up_count == null ? '--' : breadth.up_count} 家，下跌 ${breadth.down_count == null ? '--' : breadth.down_count} 家，平盘 ${breadth.flat_count == null ? '--' : breadth.flat_count} 家；涨停 ${data.limit_up_count == null ? '--' : data.limit_up_count}，跌停 ${breadth.limit_down_count == null ? '--' : breadth.limit_down_count}。`;
            envSum.textContent = line;
        }
        const indexes = env.indexes || [];
        this.fillBody(
            'drIndexBody',
            6,
            indexes.map(
                (idx) => `<tr>
                    <td>${this.escapeHtml(idx.name || idx.ts_code || '--')}</td>
                    <td class="num">${this.fmt(idx.close)}</td>
                    <td class="num">${this.signed(idx.pct_chg)}</td>
                    <td class="num">${this.fmt(idx.amount_yi, 0)}</td>
                    <td class="num">${this.fmt(idx.gap_to_high20, 0)}</td>
                    <td>${this.escapeHtml(idx.note || '--')}</td>
                </tr>`
            )
        );

        const gates = (data.hard_gates && data.hard_gates.items) || [];
        const gBody = document.getElementById('drGatesBody');
        if (gBody) {
            gBody.innerHTML = gates.length
                ? gates
                      .map(
                          (g) => `<tr>
                    <td>${this.escapeHtml(g.id)}</td><td>${this.escapeHtml(g.name || '')}</td><td>${this.escapeHtml(g.standard || '')}</td>
                    <td class="num">${this.fmt(g.value)}</td>
                    <td class="${g.passed ? 'is-ok' : 'is-bad'}">${g.passed ? '达标' : '不达标'}</td>
                  </tr>`
                      )
                      .join('')
                : '<tr><td colspan="5" class="dr-empty-cell">暂无</td></tr>';
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
                    <td class="num">${this.escapeHtml(r.hits_10d)}</td>
                    <td>${this.escapeHtml(r.tier_label || '')}</td>
                    <td>${this.escapeHtml(r.today_status || '')}</td>
                    <td>${this.escapeHtml(r.echelon || '')}</td>
                  </tr>`
                      )
                      .join('')
                : '<tr><td colspan="5" class="dr-empty-cell">暂无</td></tr>';
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
                    <td class="num">${this.signed(r.change_percent)}</td>
                    <td class="num">${this.signed(this.yiValue(r), 1)}</td>
                  </tr>`
                      )
                      .join('')
                : '<tr><td colspan="4" class="dr-empty-cell">暂无</td></tr>';
        }
        const iSum = document.getElementById('drIndustryConfirmSummary');
        if (iSum) iSum.textContent = ind.summary || '';

        const sector = (data.mainline_json && data.mainline_json.sector) || {};
        const main = sector.main || {};
        const sides = (sector.sidelines || []).map((s) => s && s.board_name).filter(Boolean);
        const mainSide = document.getElementById('drMainSide');
        if (mainSide) {
            if (main.board_name) {
                const side = sides.length ? `支线：${this.escapeHtml(sides.join('、'))}。` : '';
                mainSide.innerHTML = `当日主线：${this.escapeHtml(main.board_name)}，涨跌幅 ${this.signed(main.change_percent)}%，净流入 ${this.signed(this.yiValue(main), 1)} 亿。${side}`;
            } else {
                mainSide.textContent = '当日主线不明确。';
            }
        }
        this.fillCollapsibleSectorBody('drLeadersBody', sector.leaders, 'up');
        this.fillCollapsibleSectorBody('drLaggardsBody', sector.laggards, 'down');
        const rot = sector.rotation || {};
        const rotEl = document.getElementById('drRotation');
        if (rotEl) {
            const dropped = rot.dropped || [];
            const fresh = rot.new_inflow || [];
            const bits = [];
            if (dropped.length) bits.push('昨日上榜今日跌出：' + dropped.join('、') + '。');
            if (fresh.length) {
                bits.push(
                    '今日新进且净流入居前：' +
                        fresh.map((r) => `${r.board_name}（${this.fmtYi(r)}亿）`).join('、') +
                        '。'
                );
            }
            rotEl.textContent = bits.join('') || '暂无轮动对照。';
        }
        this.fillBody('drCapitalInBody', 2, this.flowRows(sector.capital_in));
        this.fillBody('drCapitalOutBody', 2, this.flowRows(sector.capital_out));
        const ladderEl = document.getElementById('drLadder');
        if (ladderEl) {
            const ladder = sector.ladder;
            if (!ladder) {
                ladderEl.textContent = '暂无连板梯队。';
            } else {
                const hs = sector.height_stock || {};
                const hot = hs.name
                    ? `<span class="dr-chip dr-chip--hot">最高板 ${this.stockCell(hs)} ${hs.board_count}板</span>`
                    : '';
                ladderEl.innerHTML = `
                    <span class="dr-chip">2板 <b>${ladder.b2 || 0}</b></span>
                    <span class="dr-chip">3板 <b>${ladder.b3 || 0}</b></span>
                    <span class="dr-chip">4板及以上 <b>${ladder.b4plus || 0}</b></span>
                    ${hot}`;
            }
        }
        this.fillBody(
            'drSealBody',
            4,
            (sector.seal_leaders || []).map(
                (r) => `<tr>
                    <td>${this.stockCell(r)}</td>
                    <td class="num">${this.signed(r.change_percent)}</td>
                    <td class="num">${r.seal_yi == null ? '--' : this.fmt(r.seal_yi)}</td>
                    <td class="num">${r.board_count == null ? '--' : r.board_count}</td>
                </tr>`
            )
        );
        this.fillBody(
            'drFlowBody',
            2,
            (sector.flow_top || []).map(
                (r) => `<tr><td>${this.stockCell(r)}</td><td class="num">${this.signed(r.net_inflow_yi)}</td></tr>`
            )
        );
        this.fillBody(
            'drMainFlowBody',
            2,
            (sector.main_flow_top || []).map(
                (r) => `<tr><td>${this.stockCell(r)}</td><td class="num">${this.signed(r.net_inflow_yi)}</td></tr>`
            )
        );

        const sentiment = rules.sentiment || {};
        const curveEl = document.getElementById('drCurveNote');
        if (curveEl) {
            const note = data.percentile_note || zones.percentile_note || '';
            const summaryTxt = zones.summary || (note === '样本不足' ? '阈值未校准' : '');
            curveEl.textContent = summaryTxt
                ? `Lo/Hi/Spread 区间：${summaryTxt}${note ? '（' + note + '）' : ''}`
                : '';
        }
        const factsEl = document.getElementById('drSentimentFacts');
        if (factsEl) {
            const facts = sentiment.facts || [];
            factsEl.innerHTML = facts.length
                ? facts.map((t) => `<li>${this.escapeHtml(t)}</li>`).join('')
                : '<li>暂无</li>';
        }
        const watchEl = document.getElementById('drSentimentWatch');
        if (watchEl) {
            const watch = sentiment.watch || [];
            watchEl.innerHTML = watch.length
                ? watch.map((t) => `<li>${this.escapeHtml(t)}</li>`).join('')
                : '<li>暂无</li>';
        }
        this.renderPicks(rules.picks);

        const summary = document.getElementById('drTrendSummary');
        if (summary) summary.textContent = rules.summary || '';
        const vp = document.getElementById('drViewpoint');
        if (vp) vp.value = data.viewpoint_md || '';
        const ad = document.getElementById('drAdvice');
        if (ad) ad.value = data.advice_md || '';
        const pre = document.getElementById('drMarkdownPreview');
        if (pre) pre.innerHTML = this.renderMarkdown(data.markdown || '');
    },
};

window.DailyReviewPage = DailyReviewPage;

/**
 * 分析频道 · 个股综合分析（RPE / SBBR / GMS / URT + 阻力支撑 + 形态识别）
 */
const StockMultiStrategy = {
    API_BASE_URL: typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : '',
    running: false,
    exporting: false,
    lastStrategy: null,
    lastStrategyError: null,
    lastStock: null,
    lastLevels: null,
    lastPattern: null,

    init() {
        const btn = document.getElementById('ssaAnalyzeBtn');
        if (btn) {
            btn.addEventListener('click', () => this.analyze());
        }
        const exportBtn = document.getElementById('ssaExportPdfBtn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportPdf());
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
        this.updateExportBtn();
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

    clearExportState() {
        this.lastStrategy = null;
        this.lastStrategyError = null;
        this.lastStock = null;
        this.lastLevels = null;
        this.lastPattern = null;
        this.updateExportBtn();
    },

    hasExportableResult() {
        return !!(this.lastStrategy || this.lastLevels || this.lastPattern || this.lastStrategyError);
    },

    updateExportBtn() {
        const btn = document.getElementById('ssaExportPdfBtn');
        const ok = this.hasExportableResult();
        if (btn) {
            btn.disabled = !ok || this.exporting;
            if (!this.exporting) btn.textContent = '导出 PDF';
        }
    },

    hideResultBlocks() {
        ['ssaStrategyBlock', 'ssaLevelsBlock', 'ssaPatternBlock'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.hidden = true;
        });
        const levelsHost = document.getElementById('ssaLevelsHost');
        const patternHost = document.getElementById('ssaPatternHost');
        if (levelsHost) levelsHost.innerHTML = '';
        if (patternHost) patternHost.innerHTML = '';
        const levelsStatus = document.getElementById('ssaLevelsStatus');
        const patternStatus = document.getElementById('ssaPatternStatus');
        if (levelsStatus) {
            levelsStatus.textContent = '';
            levelsStatus.hidden = false;
            levelsStatus.className = 'ssa-block-status';
        }
        if (patternStatus) {
            patternStatus.textContent = '';
            patternStatus.hidden = false;
            patternStatus.className = 'ssa-block-status';
        }
        this.clearExportState();
    },

    setBlockLoading(blockId, statusId, text) {
        const block = document.getElementById(blockId);
        const status = document.getElementById(statusId);
        if (block) block.hidden = false;
        if (status) {
            status.hidden = false;
            status.className = 'ssa-block-status is-loading';
            status.textContent = text || '加载中…';
        }
    },

    setBlockError(statusId, message) {
        const status = document.getElementById(statusId);
        if (status) {
            status.hidden = false;
            status.className = 'ssa-block-status is-error';
            status.textContent = message || '加载失败';
        }
    },

    setBlockOk(statusId, message) {
        const status = document.getElementById(statusId);
        if (status) {
            status.className = 'ssa-block-status is-ok';
            status.textContent = message || '';
            if (!message) status.hidden = true;
            else status.hidden = false;
        }
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
        this.hideResultBlocks();
        const meta = document.getElementById('ssaMeta');
        const empty = document.getElementById('ssaEmpty');
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
        this.hideResultBlocks();
        if (btn) {
            btn.disabled = true;
            btn.textContent = '分析中…';
        }
        if (empty) {
            empty.hidden = false;
            empty.textContent = '正在评估策略、阻力支撑与形态，请稍候…';
        }
        const meta = document.getElementById('ssaMeta');
        if (meta) meta.hidden = true;

        try {
            const q = new URLSearchParams({ code: query });
            const dateEl = document.getElementById('ssaTradeDate');
            const asof = dateEl && dateEl.value ? dateEl.value : '';
            if (asof) q.set('date', asof);
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
            this.renderStrategyResult(data);
            if (empty) empty.hidden = true;

            // 策略成功后并行拉取阻力支撑、形态（失败互不影响）
            const resolvedCode = stock.code || query;
            const tradeDate = data.trade_date || asof || '';
            await Promise.all([
                this.loadLevelsSection(resolvedCode),
                this.loadPatternSection(resolvedCode, tradeDate),
            ]);
            this.updateExportBtn();

            CommonUtils.showToast(
                data.any_hit ? `命中 ${data.hit_count || 0} 个策略` : '四策略均未命中',
                data.any_hit ? 'success' : 'info'
            );
        } catch (e) {
            console.error(e);
            // 策略失败时：若输入已是明确代码，仍尝试阻力支撑与形态
            const dateEl = document.getElementById('ssaTradeDate');
            const asofFallback = dateEl && dateEl.value ? dateEl.value : '';
            const looksLikeCode = /^\d{4,6}$/.test(
                (/^(sh|sz|bj|hk)/i.test(firstToken) ? firstToken.slice(2) : firstToken)
            ) || /^(sh|sz|bj|hk)\d{4,6}$/i.test(firstToken);
            if (looksLikeCode) {
                if (empty) empty.hidden = true;
                const strategyBlock = document.getElementById('ssaStrategyBlock');
                const strategyHost = document.getElementById('ssaResults');
                this.lastStrategy = null;
                this.lastStrategyError = e.message || '策略分析失败';
                this.lastStock = { code: firstToken };
                if (strategyBlock && strategyHost) {
                    strategyBlock.hidden = false;
                    strategyHost.innerHTML = `<div class="ssa-block-status is-error">${this.esc(e.message || '策略分析失败')}</div>`;
                }
                await Promise.all([
                    this.loadLevelsSection(firstToken),
                    this.loadPatternSection(firstToken, asofFallback),
                ]);
                this.updateExportBtn();
                CommonUtils.showToast('策略分析失败，已尝试计算阻力支撑与形态', 'warning');
            } else {
                if (empty) {
                    empty.hidden = false;
                    empty.textContent = e.message || '分析失败';
                }
                CommonUtils.showToast(e.message || '分析失败', 'error');
            }
        } finally {
            this.running = false;
            if (btn) {
                btn.disabled = false;
                btn.textContent = '分析';
            }
            this.updateExportBtn();
        }
    },

    async loadLevelsSection(code) {
        const block = document.getElementById('ssaLevelsBlock');
        const host = document.getElementById('ssaLevelsHost');
        if (!block || !host) return;
        this.setBlockLoading('ssaLevelsBlock', 'ssaLevelsStatus', '正在计算阻力支撑位…');
        try {
            if (typeof KdeLevelsTool === 'undefined' || typeof KdeLevelsTool.fetchLevels !== 'function') {
                throw new Error('阻力支撑模块未加载');
            }
            const fetched = await KdeLevelsTool.fetchLevels(code, {
                adjust: 'qfq',
                factor_source: 'auto',
                max_levels: 8,
            });
            if (fetched.candidates && fetched.candidates.length > 1 && !fetched.data) {
                throw new Error(fetched.message || '股票代码不唯一，请使用精确代码');
            }
            if (!fetched.httpOk && !fetched.data) {
                throw new Error(fetched.message || '阻力支撑计算失败');
            }
            KdeLevelsTool.renderEmbedded(host, fetched.data || {}, fetched.ok, fetched.message, {
                adjust: 'qfq',
                factor_source: 'auto',
                max_levels: 8,
                onUpdated: (result) => {
                    this.lastLevels = {
                        ok: !!result.ok,
                        data: result.data || {},
                        error: result.ok ? null : (result.message || '阻力支撑计算失败'),
                    };
                    this.updateExportBtn();
                },
            });
            this.lastLevels = {
                ok: !!fetched.ok,
                data: fetched.data || {},
                error: fetched.ok ? null : (fetched.message || null),
            };
            this.setBlockOk('ssaLevelsStatus', '');
            const st = document.getElementById('ssaLevelsStatus');
            if (st) st.hidden = true;
        } catch (e) {
            console.warn('个股分析·阻力支撑失败', e);
            host.innerHTML = '';
            this.lastLevels = { ok: false, data: null, error: e.message || '阻力支撑计算失败' };
            this.setBlockError('ssaLevelsStatus', e.message || '阻力支撑计算失败，可稍后在「技术工具」重试');
        }
        this.updateExportBtn();
    },

    async loadPatternSection(code, asof) {
        const block = document.getElementById('ssaPatternBlock');
        const host = document.getElementById('ssaPatternHost');
        if (!block || !host) return;
        this.setBlockLoading('ssaPatternBlock', 'ssaPatternStatus', '正在识别形态…');
        try {
            if (typeof PatternTool === 'undefined' || typeof PatternTool.fetchSingle !== 'function') {
                throw new Error('形态识别模块未加载');
            }
            const fetched = await PatternTool.fetchSingle(code, {
                adjust: 'qfq',
                asof: asof || undefined,
            });
            const invN = fetched.invalidated_count || 0;
            const meta = `个股 ${this.esc(fetched.code)} ${this.esc(fetched.name || '')} · 基准日 ${this.esc(fetched.asof || '--')} · ${this.esc(PatternTool.adjustLabel(fetched.price_adjust))} · ${this.esc(PatternTool.formatHitMeta(fetched.items.length, invN))}`;
            const levelsData = (this.lastLevels && this.lastLevels.data) || {};
            const classic = levelsData.classic_levels || levelsData.classic || {};
            const confluence =
                classic.confluence_zones || levelsData.confluence_zones || null;
            PatternTool.renderEmbedded(host, fetched.items, meta, fetched.price_adjust, {
                asof: fetched.asof || asof || '',
                confluenceZones: confluence,
                classicLevels: classic,
                invalidatedCount: invN,
                tactical: fetched.tactical || null,
                kdeLevels: {
                    nearest_resistance: levelsData.nearest_resistance,
                    nearest_support: levelsData.nearest_support,
                    resistance_levels: levelsData.resistance_levels,
                    support_levels: levelsData.support_levels,
                },
            });
            this.lastPattern = {
                ok: true,
                items: fetched.items || [],
                invalidated_count: invN,
                code: fetched.code,
                name: fetched.name || '',
                asof: fetched.asof || '',
                price_adjust: fetched.price_adjust,
                tactical: fetched.tactical || null,
                error: null,
            };
            this.setBlockOk('ssaPatternStatus', '');
            const st = document.getElementById('ssaPatternStatus');
            if (st) st.hidden = true;
        } catch (e) {
            console.warn('个股分析·形态识别失败', e);
            host.innerHTML = '';
            this.lastPattern = {
                ok: false,
                items: [],
                code,
                name: '',
                asof: asof || '',
                price_adjust: 'qfq',
                error: e.message || '形态识别失败',
            };
            this.setBlockError('ssaPatternStatus', e.message || '形态识别失败，可稍后在「技术工具」重试');
        }
        this.updateExportBtn();
    },

    renderStrategyResult(data) {
        const empty = document.getElementById('ssaEmpty');
        const meta = document.getElementById('ssaMeta');
        const host = document.getElementById('ssaResults');
        const block = document.getElementById('ssaStrategyBlock');
        if (empty) empty.hidden = true;
        const stock = data.stock || {};
        this.lastStrategy = data;
        this.lastStrategyError = null;
        this.lastStock = stock;
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
        if (block) block.hidden = false;
        this.updateExportBtn();
    },

    pdfFilename() {
        const d = new Date();
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const stock =
            (this.lastStrategy && this.lastStrategy.stock) ||
            this.lastStock ||
            (this.lastLevels && this.lastLevels.data) ||
            {};
        const code = String(
            stock.code || stock.stock_code || (this.lastPattern && this.lastPattern.code) || ''
        ).replace(/[^\w.-]/g, '');
        const codePart = code || 'unknown';
        const rawName = String(
            stock.name ||
                stock.stock_name ||
                (this.lastPattern && this.lastPattern.name) ||
                ''
        ).trim();
        // 去掉 Windows / 通用文件名非法字符，空白压成下划线
        const namePart = rawName
            .replace(/[\\/:*?"<>|]/g, '')
            .replace(/\s+/g, '_')
            .slice(0, 40);
        const mid = namePart ? `${codePart}_${namePart}` : codePart;
        return `个股分析_${mid}_${y}${m}${day}.pdf`;
    },

    buildPdfHtml() {
        const filename = this.pdfFilename().replace(/\.pdf$/i, '');
        const stock =
            (this.lastStrategy && this.lastStrategy.stock) ||
            this.lastStock ||
            {};
        const meta = document.getElementById('ssaMeta');
        const strategyHost = document.getElementById('ssaResults');
        const levelsHost = document.getElementById('ssaLevelsHost');
        const levelsStatus = document.getElementById('ssaLevelsStatus');
        const patternHost = document.getElementById('ssaPatternHost');
        const patternStatus = document.getElementById('ssaPatternStatus');

        const cloneClean = (el) => {
            if (!el) return '';
            const clone = el.cloneNode(true);
            clone.querySelectorAll('.ssa-block-status.is-loading, a').forEach((node) => {
                if (node.tagName === 'A') {
                    const span = document.createElement('span');
                    span.textContent = node.textContent || '';
                    node.replaceWith(span);
                } else {
                    node.remove();
                }
            });
            return clone.innerHTML;
        };

        let strategyHtml = '';
        if (this.lastStrategyError && !this.lastStrategy) {
            strategyHtml = `<p class="ssa-pdf-err">${this.esc(this.lastStrategyError)}</p>`;
        } else if (strategyHost && strategyHost.innerHTML.trim()) {
            strategyHtml = cloneClean(strategyHost);
        } else {
            strategyHtml = '<p class="ssa-pdf-empty">暂无策略结果</p>';
        }

        let levelsHtml = '';
        if (this.lastLevels && this.lastLevels.error && !this.lastLevels.data) {
            levelsHtml = `<p class="ssa-pdf-err">${this.esc(this.lastLevels.error)}</p>`;
        } else if (levelsHost && levelsHost.innerHTML.trim()) {
            levelsHtml = cloneClean(levelsHost);
            if (levelsStatus && levelsStatus.classList.contains('is-error') && levelsStatus.textContent) {
                levelsHtml += `<p class="ssa-pdf-err">${this.esc(levelsStatus.textContent)}</p>`;
            }
        } else if (this.lastLevels && this.lastLevels.error) {
            levelsHtml = `<p class="ssa-pdf-err">${this.esc(this.lastLevels.error)}</p>`;
        } else {
            levelsHtml = '<p class="ssa-pdf-empty">暂无阻力支撑结果</p>';
        }

        let patternHtml = '';
        if (this.lastPattern && this.lastPattern.error && !(this.lastPattern.items || []).length) {
            patternHtml = `<p class="ssa-pdf-err">${this.esc(this.lastPattern.error)}</p>`;
        } else if (patternHost && patternHost.innerHTML.trim()) {
            patternHtml = cloneClean(patternHost);
            if (patternStatus && patternStatus.classList.contains('is-error') && patternStatus.textContent) {
                patternHtml += `<p class="ssa-pdf-err">${this.esc(patternStatus.textContent)}</p>`;
            }
        } else if (this.lastPattern && this.lastPattern.error) {
            patternHtml = `<p class="ssa-pdf-err">${this.esc(this.lastPattern.error)}</p>`;
        } else {
            patternHtml = '<p class="ssa-pdf-empty">暂无形态识别结果</p>';
        }

        const metaHtml = meta && !meta.hidden && meta.innerHTML.trim()
            ? meta.innerHTML
            : `<div>${this.esc(stock.code || '')} ${this.esc(stock.name || '')}</div>`;

        return `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"/>
<title>${this.esc(filename)}</title>
<style>
  @page { size: A4 portrait; margin: 12mm; }
  * { box-sizing: border-box; }
  body {
    font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif;
    color: #0f172a; font-size: 12px; line-height: 1.45; padding: 12px 16px; background: #fff;
    -webkit-print-color-adjust: exact; print-color-adjust: exact;
  }
  h1 { font-size: 18px; margin: 0 0 8px; }
  h2 { font-size: 14px; margin: 16px 0 8px; color: #1e40af; border-bottom: 1px solid #bfdbfe; padding-bottom: 4px; }
  .meta { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px 10px; margin-bottom: 10px; }
  .ssa-pdf-empty { color: #94a3b8; }
  .ssa-pdf-err { color: #b91c1c; }
  .print-hint {
    margin: 0 0 10px; padding: 8px 10px; background: #eff6ff; border: 1px solid #bfdbfe;
    border-radius: 6px; color: #1e3a8a; font-size: 12px;
  }
  .ssa-results { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .ssa-card { border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px; page-break-inside: avoid; }
  .ssa-card--hit { border-color: #86efac; background: #f0fdf4; }
  .ssa-card--miss { background: #f8fafc; }
  .ssa-card-head { display: flex; justify-content: space-between; align-items: center; }
  .ssa-card-head h4 { margin: 0; font-size: 13px; }
  .ssa-badge { font-size: 11px; padding: 1px 6px; border-radius: 3px; }
  .ssa-badge--yes { background: #dcfce7; color: #166534; }
  .ssa-badge--no { background: #e2e8f0; color: #475569; }
  .ssa-card-score { font-weight: 600; margin: 4px 0; }
  .ssa-card-reason { margin: 0; color: #334155; }
  .ssa-card-links { display: none; }
  table { width: 100%; border-collapse: collapse; font-size: 11px; margin: 6px 0; }
  th, td { border: 1px solid #e2e8f0; padding: 4px 5px; text-align: left; vertical-align: top; }
  th { background: #f1f5f9; }
  .kde-levels-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
  .kde-levels-card { border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px; page-break-inside: avoid; }
  .kde-levels-subtitle { margin: 12px 0 6px; font-size: 13px; color: #334155; }
  .pattern-expert-analysis { margin-top: 8px; padding: 8px; background: #f8fafc; border-radius: 6px; }
  @media print {
    body { padding: 0; }
    .print-hint { display: none !important; }
  }
</style></head><body>
  <p class="print-hint">请在打印对话框中选择「另存为 PDF / Microsoft Print to PDF」。关闭本页不影响分析结果。</p>
  <h1>个股分析结果</h1>
  <div class="meta">${metaHtml}</div>
  <h2>策略分析</h2>
  ${strategyHtml}
  <h2>阻力支撑位</h2>
  ${levelsHtml}
  <h2>形态识别</h2>
  ${patternHtml}
</body></html>`;
    },

    exportViaPrint(html, filename) {
        const w = window.open('', '_blank');
        if (!w) {
            if (window.CommonUtils) {
                CommonUtils.showToast('浏览器拦截了弹窗，请允许后重试，再点「导出 PDF」', 'warning');
            }
            return false;
        }
        w.document.open();
        w.document.write(html);
        w.document.close();
        w.document.title = filename.replace(/\.pdf$/i, '');
        const triggerPrint = () => {
            try {
                w.focus();
                w.print();
            } catch (e) {
                console.warn(e);
            }
        };
        if (w.document.fonts && w.document.fonts.ready) {
            w.document.fonts.ready.then(() => setTimeout(triggerPrint, 80)).catch(() => setTimeout(triggerPrint, 350));
        } else {
            setTimeout(triggerPrint, 350);
        }
        return true;
    },

    async exportPdf() {
        if (!this.hasExportableResult()) {
            if (window.CommonUtils) CommonUtils.showToast('请先完成个股分析再导出', 'warning');
            return;
        }
        if (this.exporting) return;
        const btn = document.getElementById('ssaExportPdfBtn');
        const filename = this.pdfFilename();
        this.exporting = true;
        if (btn) {
            btn.disabled = true;
            btn.classList.add('ssa-exporting');
            btn.textContent = '导出中…';
        }
        try {
            if (!window.StockAnalysisPdf || typeof StockAnalysisPdf.exportFromHost !== 'function') {
                throw new Error('PDF 导出模块未加载');
            }
            const saved = await StockAnalysisPdf.exportFromHost(this);
            if (window.CommonUtils) CommonUtils.showToast(`已导出 ${saved || filename}`, 'success');
        } catch (e) {
            console.warn('结构化 PDF 导出失败，回退打印', e);
            const html = this.buildPdfHtml();
            const ok = this.exportViaPrint(html, filename);
            const reason = (e && e.message) || String(e || '未知错误');
            if (window.CommonUtils) {
                if (ok) {
                    CommonUtils.showToast(`结构化导出失败（${reason}），已打开打印预览作兜底`, 'warning');
                } else {
                    CommonUtils.showToast(`导出失败：${reason}`, 'error');
                }
            }
        } finally {
            this.exporting = false;
            if (btn) {
                btn.classList.remove('ssa-exporting');
                btn.textContent = '导出 PDF';
            }
            this.updateExportBtn();
        }
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

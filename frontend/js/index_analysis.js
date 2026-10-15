/**
 * 指数分析编排：环境研判 + 广度/贡献 + 价格行为 + 江恩；PNG / PDF 导出。
 * 独立于 StockMultiStrategy，避免污染个股通道。
 */
(function (global) {
    const QUICK_INDICES = [
        { code: '000001', name: '上证指数' },
        { code: '399001', name: '深证成指' },
        { code: '399006', name: '创业板指' },
        { code: '000300', name: '沪深300' },
    ];

    const IndexAnalysis = {
        API_BASE_URL: (typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : ''),
        lastBundle: null,
        lastCode: '',
        lastName: '',
        _bound: false,

        init() {
            if (this._bound) return;
            this._bound = true;
            this._bindWorkbench();
            this.redirectDeepLinkIfNeeded();
        },

        redirectDeepLinkIfNeeded() {
            try {
                const params = new URLSearchParams(global.location.search || '');
                const tab = (params.get('tab') || '').trim();
                const index = (params.get('index') || params.get('code') || '').trim();
                if (tab === 'index-ai' && index) {
                    const popup = params.get('popup') === '1' ? '&popup=1' : '';
                    global.location.replace(`index_detail.html?index=${encodeURIComponent(index)}${popup}`);
                    return true;
                }
            } catch (e) { /* ignore */ }
            return false;
        },

        _bindWorkbench() {
            const quick = document.getElementById('isaQuickIndices');
            if (quick && !quick.dataset.bound) {
                quick.dataset.bound = '1';
                quick.innerHTML = QUICK_INDICES.map(
                    (x) =>
                        `<button type="button" class="btn btn-secondary btn-sm isa-quick-btn" data-code="${x.code}">${x.name}</button>`
                ).join('');
                quick.addEventListener('click', (e) => {
                    const btn = e.target && e.target.closest ? e.target.closest('.isa-quick-btn') : null;
                    if (!btn) return;
                    const code = btn.getAttribute('data-code') || '';
                    const input = document.getElementById('isaIndexCode');
                    if (input) input.value = code;
                });
            }
            const analyzeBtn = document.getElementById('isaAnalyzeBtn');
            if (analyzeBtn && !analyzeBtn.dataset.bound) {
                analyzeBtn.dataset.bound = '1';
                analyzeBtn.addEventListener('click', () => this.runFromWorkbench(false));
            }
            const rtBtn = document.getElementById('isaRealtimeAnalyzeBtn');
            if (rtBtn && !rtBtn.dataset.bound) {
                rtBtn.dataset.bound = '1';
                rtBtn.addEventListener('click', () => this.runFromWorkbench(true));
            }
            const pngBtn = document.getElementById('isaExportPngBtn');
            if (pngBtn && !pngBtn.dataset.bound) {
                pngBtn.dataset.bound = '1';
                pngBtn.addEventListener('click', () => this.exportPng());
            }
            const pdfBtn = document.getElementById('isaExportPdfBtn');
            if (pdfBtn && !pdfBtn.dataset.bound) {
                pdfBtn.dataset.bound = '1';
                pdfBtn.addEventListener('click', () => this.exportPdf());
            }
        },

        async runFromWorkbench(useRealtime) {
            const input = document.getElementById('isaIndexCode');
            const dateEl = document.getElementById('isaTradeDate');
            const code = ((input && input.value) || '').trim();
            if (!code) {
                if (typeof CommonUtils !== 'undefined' && CommonUtils.showToast) {
                    CommonUtils.showToast('请先选择常用指数，或输入 6 位指数代码', 'warning');
                }
                return;
            }
            const date = (dateEl && dateEl.value) || '';
            await this.run({ code, date, useRealtime: !!useRealtime });
        },

        async run(opts) {
            const options = opts || {};
            const code = String(options.code || '').trim();
            if (!code) throw new Error('缺少指数代码');
            const date = options.date || '';
            const useRealtime = !!options.useRealtime;
            this._setBusy(true);
            try {
                const data = await this.fetchBundle(code, { date, useRealtime });
                this.lastBundle = data;
                this.lastCode = (data.index && data.index.code) || code;
                this.lastName = (data.index && data.index.name) || '';
                this.render(data);
                this._enableExport(true);
                if (typeof CommonUtils !== 'undefined' && CommonUtils.showToast) {
                    CommonUtils.showToast(`${this.lastName || this.lastCode} 分析完成`, 'success');
                }
            } catch (e) {
                console.error('[IndexAnalysis]', e);
                if (typeof CommonUtils !== 'undefined' && CommonUtils.showToast) {
                    CommonUtils.showToast(e.message || '分析失败，请稍后重试', 'error');
                }
                this._enableExport(false);
            } finally {
                this._setBusy(false);
            }
        },

        async fetchBundle(code, opts) {
            const options = opts || {};
            const q = new URLSearchParams({ code });
            if (options.date && !options.useRealtime) q.set('date', String(options.date).slice(0, 10));
            if (options.useRealtime) q.set('use_realtime', 'true');
            const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
            const resp = await fetchFn(
                `${this.API_BASE_URL}/api/analysis/index-analysis-bundle?${q.toString()}`
            );
            const payload = await resp.json().catch(() => ({}));
            if (!resp.ok || !payload.success) {
                throw new Error(payload.message || payload.detail || `分析失败 ${resp.status}`);
            }
            return payload.data || {};
        },

        render(data) {
            const empty = document.getElementById('isaEmpty');
            if (empty) empty.hidden = true;
            const exportRoot = document.getElementById('isaExportRoot');
            if (exportRoot) exportRoot.hidden = false;

            this._renderMeta(data);
            this._renderMarketView(data.market_view);
            this._renderBreadth(data.breadth, data.leaders, data.sector_contrib);
            this._renderPa(data);
        },

        _renderMeta(data) {
            const meta = document.getElementById('isaMeta');
            if (!meta) return;
            const idx = data.index || {};
            const pct = idx.change_percent;
            const pctCls = pct > 0 ? 'positive' : pct < 0 ? 'negative' : '';
            const pctText = pct != null && !Number.isNaN(Number(pct))
                ? `${Number(pct) > 0 ? '+' : ''}${Number(pct).toFixed(2)}%`
                : '--';
            meta.hidden = false;
            meta.innerHTML = `
              <div class="isa-meta-row">
                <strong>${this.esc(idx.name || '')}</strong>
                <span class="isa-code">${this.esc(idx.code || '')}</span>
                <span class="isa-ts">${this.esc(idx.ts_code || '')}</span>
                <span class="isa-price">${idx.current != null ? Number(idx.current).toFixed(2) : (idx.last_close != null ? Number(idx.last_close).toFixed(2) : '--')}</span>
                <span class="isa-pct ${pctCls}">${pctText}</span>
                <span class="muted">基准日 ${this.esc(data.trade_date || '--')}${data.use_realtime ? ' · 实时' : ''}</span>
              </div>`;
        },

        _renderMarketView(mv) {
            const block = document.getElementById('isaMarketViewBlock');
            const host = document.getElementById('isaMarketViewHost');
            const status = document.getElementById('isaMarketViewStatus');
            if (!block || !host) return;
            block.hidden = false;
            if (!mv || !mv.ok) {
                host.innerHTML = '';
                if (status) {
                    status.hidden = false;
                    status.textContent = (mv && mv.error) || '研判不可用';
                }
                return;
            }
            if (status) status.hidden = true;
            const biasCls = mv.bias === 'bullish' ? 'isa-bias-bull' : mv.bias === 'bearish' ? 'isa-bias-bear' : 'isa-bias-neu';
            const bullets = (mv.bullets || []).map((b) => `<li>${this.esc(b)}</li>`).join('');
            host.innerHTML = `
              <div class="isa-market-view ${biasCls}">
                <div class="isa-bias-label">${this.esc(mv.bias_label || '中性')}</div>
                <p class="isa-mv-summary">${this.esc(mv.summary || '')}</p>
                <ul class="isa-mv-bullets">${bullets || '<li class="muted">暂无结构要点</li>'}</ul>
                <p class="isa-mv-note muted">环境对照结论，非买卖或仓位建议。</p>
              </div>`;
        },

        _renderBreadth(breadth, leaders, sector) {
            const block = document.getElementById('isaBreadthBlock');
            const host = document.getElementById('isaBreadthHost');
            if (!block || !host) return;
            block.hidden = false;
            const parts = [];

            if (!breadth || !breadth.available) {
                parts.push(
                    `<p class="isa-empty-soft">${this.esc(
                        (breadth && breadth.reason)
                            || '库内暂无该指数成分，广度与贡献从略；上方技术分析仍可用。建议优先查看沪深300等已维护成分的指数。'
                    )}</p>`
                );
            } else {
                parts.push(`
                  <div class="isa-breadth-grid">
                    <div><span class="muted">成分 / 有行情</span><strong>${breadth.member_count} / ${breadth.quoted_count}</strong></div>
                    <div><span class="muted">上涨</span><strong class="positive">${breadth.up_count}</strong></div>
                    <div><span class="muted">下跌</span><strong class="negative">${breadth.down_count}</strong></div>
                    <div><span class="muted">平盘</span><strong>${breadth.flat_count}</strong></div>
                    <div><span class="muted">上涨占比</span><strong>${breadth.up_ratio != null ? (breadth.up_ratio * 100).toFixed(1) + '%' : '--'}</strong></div>
                    <div><span class="muted">涨跌中位数</span><strong>${breadth.median_change_percent != null ? breadth.median_change_percent.toFixed(2) + '%' : '--'}</strong></div>
                  </div>`);
            }

            if (leaders && leaders.available) {
                parts.push('<div class="isa-leaders">');
                parts.push('<h5>今日涨幅前列</h5>' + this._stockTable(leaders.gainers || []));
                parts.push('<h5>今日跌幅前列</h5>' + this._stockTable(leaders.losers || []));
                parts.push('</div>');
            }

            if (sector) {
                parts.push(
                    `<p class="isa-disclaimer muted">${this.esc(
                        sector.disclaimer
                            || '行业贡献按成分成交额加权近似，非官方指数权重，仅供对照。'
                    )}</p>`
                );
                if (!sector.available) {
                    parts.push(
                        `<p class="isa-empty-soft">${this.esc(sector.reason || '暂无可用的行业贡献数据')}</p>`
                    );
                } else {
                    const rows = (sector.items || []).slice(0, 12).map((it) => {
                        const c = it.approx_contribution;
                        const cls = c > 0 ? 'positive' : c < 0 ? 'negative' : '';
                        return `<tr>
                          <td>${this.esc(it.board_name || it.board_code)}</td>
                          <td class="num">${it.member_count}</td>
                          <td class="num">${it.weighted_change_percent != null ? it.weighted_change_percent.toFixed(2) + '%' : '--'}</td>
                          <td class="num ${cls}">${c != null ? c.toFixed(3) : '--'}</td>
                        </tr>`;
                    }).join('');
                    parts.push(`
                      <table class="isa-table">
                        <thead><tr><th>行业</th><th>家数</th><th>额权涨跌</th><th>近似贡献</th></tr></thead>
                        <tbody>${rows}</tbody>
                      </table>`);
                }
            }

            host.innerHTML = parts.join('');
        },

        _stockTable(list) {
            const rows = (list || []).slice(0, 8).map((s) => {
                const pct = s.change_percent;
                const cls = pct > 0 ? 'positive' : pct < 0 ? 'negative' : '';
                let href = `stock.html?code=${encodeURIComponent(s.code || '')}&tab=analysis`;
                if (typeof StockTradeLink !== 'undefined' && StockTradeLink.buildHref) {
                    href = StockTradeLink.buildHref(s.code, s.name || '', { tab: 'analysis' });
                }
                return `<tr>
                  <td><a href="${this.esc(href)}" target="_blank" rel="noopener noreferrer">${this.esc(s.code)}</a></td>
                  <td>${this.esc(s.name || '')}</td>
                  <td class="num ${cls}">${pct != null ? Number(pct).toFixed(2) + '%' : '--'}</td>
                </tr>`;
            }).join('');
            return `<table class="isa-table"><thead><tr><th>代码</th><th>名称</th><th>涨跌幅</th></tr></thead><tbody>${rows || '<tr><td colspan="3" class="muted">无</td></tr>'}</tbody></table>`;
        },

        _renderPa(data) {
            const pa = document.getElementById('isaPaSection');
            if (pa) pa.hidden = false;

            // 波段
            const swingBlock = document.getElementById('isaSwingBlock');
            const swingHost = document.getElementById('isaSwingHost');
            if (swingBlock && swingHost) {
                swingBlock.hidden = false;
                const sw = data.swing || {};
                const MST = global.MarketStructureTool;
                if (sw.ok && sw.payload && MST && typeof MST.renderEmbedded === 'function') {
                    const lv = (data.levels && data.levels.data) || {};
                    MST.renderEmbedded(swingHost, sw.payload, {
                        keyLevels: {
                            nearest_support: lv.nearest_support,
                            nearest_resistance: lv.nearest_resistance,
                        },
                    });
                    this._ok('isaSwingStatus');
                } else {
                    swingHost.innerHTML = '';
                    this._err('isaSwingStatus', (sw && sw.error) || '波段分析失败');
                }
            }

            // 形态
            const patternBlock = document.getElementById('isaPatternBlock');
            const patternHost = document.getElementById('isaPatternHost');
            if (patternBlock && patternHost) {
                patternBlock.hidden = false;
                const pt = data.pattern || {};
                const PT = global.PatternTool;
                if (pt.ok && PT && typeof PT.renderEmbedded === 'function') {
                    const fetched = pt.payload || pt;
                    const invN = fetched.invalidated_count || 0;
                    const meta = `指数 ${this.esc(fetched.code)} ${this.esc(fetched.name || '')} · 基准 ${this.esc(fetched.asof || '--')} · 日线不复权 · ${this.esc(PT.formatHitMeta ? PT.formatHitMeta((fetched.items || []).length, invN) : '')}`;
                    const levelsData = (data.levels && data.levels.data) || {};
                    const classic = levelsData.classic_levels || {};
                    PT.renderEmbedded(patternHost, pt.items || fetched.items || [], meta, 'none', {
                        code: fetched.code || '',
                        name: fetched.name || '',
                        asof: fetched.asof || '',
                        classicLevels: classic,
                        confluenceZones: classic.confluence_zones || null,
                        invalidatedCount: invN,
                        tactical: fetched.tactical || pt.tactical || null,
                        kdeLevels: {
                            nearest_resistance: levelsData.nearest_resistance,
                            nearest_support: levelsData.nearest_support,
                            resistance_levels: levelsData.resistance_levels,
                            support_levels: levelsData.support_levels,
                        },
                    });
                    this._ok('isaPatternStatus');
                } else {
                    patternHost.innerHTML = '';
                    this._err('isaPatternStatus', (pt && pt.error) || '形态识别失败');
                }
            }

            // 关位
            const levelsBlock = document.getElementById('isaLevelsBlock');
            const levelsHost = document.getElementById('isaLevelsHost');
            if (levelsBlock && levelsHost) {
                levelsBlock.hidden = false;
                const lv = data.levels || {};
                const Levels = global.KdeLevelsTool;
                if (lv.ok && Levels && typeof Levels.renderEmbedded === 'function') {
                    const fetched = lv.payload || { data: lv.data, ok: true, message: '' };
                    Levels.renderEmbedded(levelsHost, fetched.data || lv.data || {}, true, '', {
                        code: (data.index && data.index.code) || '',
                        asset_type: 'index',
                        adjust: 'none',
                        max_levels: 8,
                    });
                    this._ok('isaLevelsStatus');
                } else {
                    levelsHost.innerHTML = '';
                    this._err('isaLevelsStatus', (lv && lv.error) || '阻力支撑计算失败');
                }
            }

            // 江恩
            const gannBlock = document.getElementById('isaGannBlock');
            const gannHost = document.getElementById('isaGannHost');
            if (gannBlock && gannHost) {
                gannBlock.hidden = false;
                const gn = data.gann || {};
                const GT = global.GannTrendTool;
                if (gn.ok && gn.payload && GT && typeof GT.renderEmbedded === 'function') {
                    GT.renderEmbedded(gannHost, gn.payload);
                    this._ok('isaGannStatus');
                } else {
                    gannHost.innerHTML = '';
                    this._err('isaGannStatus', (gn && gn.error) || '江恩分析失败');
                }
            }
        },

        hasExportableResult() {
            return !!(this.lastBundle && this.lastCode);
        },

        pngFilename() {
            const d = (this.lastBundle && this.lastBundle.trade_date) || '';
            return `指数分析_${this.lastCode || 'index'}_${d || 'latest'}.png`;
        },

        pdfFilename() {
            const d = (this.lastBundle && this.lastBundle.trade_date) || '';
            return `指数分析_${this.lastCode || 'index'}_${d || 'latest'}.pdf`;
        },

        async exportPng() {
            if (!this.hasExportableResult()) {
                if (typeof CommonUtils !== 'undefined') CommonUtils.showToast('请先完成分析再导出', 'warning');
                return;
            }
            if (typeof StockAnalysisPng === 'undefined' || typeof StockAnalysisPng.exportFromHost !== 'function') {
                if (typeof CommonUtils !== 'undefined') CommonUtils.showToast('PNG 导出组件未加载', 'error');
                return;
            }
            // 临时把导出根节点 id 对齐个股 PNG（StockAnalysisPng 固定读 ssaExportRoot）
            const isaRoot = document.getElementById('isaExportRoot');
            const ssaRoot = document.getElementById('ssaExportRoot');
            let swapped = false;
            try {
                if (isaRoot && (!ssaRoot || ssaRoot !== isaRoot)) {
                    isaRoot.id = 'ssaExportRoot';
                    if (ssaRoot) ssaRoot.id = 'isaExportRoot__tmp';
                    swapped = true;
                }
                const host = {
                    hasExportableResult: () => this.hasExportableResult(),
                    pngFilename: () => this.pngFilename(),
                };
                const name = await StockAnalysisPng.exportFromHost(host);
                if (typeof CommonUtils !== 'undefined') CommonUtils.showToast(`已导出 ${name}`, 'success');
            } catch (e) {
                console.error(e);
                if (typeof CommonUtils !== 'undefined') CommonUtils.showToast(e.message || 'PNG 导出失败', 'error');
            } finally {
                if (swapped) {
                    const a = document.getElementById('ssaExportRoot');
                    const b = document.getElementById('isaExportRoot__tmp');
                    if (a) a.id = 'isaExportRoot';
                    if (b) b.id = 'ssaExportRoot';
                }
            }
        },

        async exportPdf() {
            if (!this.hasExportableResult()) {
                if (typeof CommonUtils !== 'undefined') CommonUtils.showToast('请先完成分析再导出', 'warning');
                return;
            }
            if (typeof IndexAnalysisPdf === 'undefined' || typeof IndexAnalysisPdf.exportFromHost !== 'function') {
                if (typeof CommonUtils !== 'undefined') CommonUtils.showToast('PDF 导出组件未加载，请刷新页面', 'error');
                return;
            }
            try {
                const name = await IndexAnalysisPdf.exportFromHost(this);
                if (typeof CommonUtils !== 'undefined') CommonUtils.showToast(`已导出 ${name}`, 'success');
            } catch (e) {
                console.error(e);
                if (typeof CommonUtils !== 'undefined') CommonUtils.showToast(e.message || 'PDF 导出失败', 'error');
            }
        },

        _setBusy(busy) {
            ['isaAnalyzeBtn', 'isaRealtimeAnalyzeBtn'].forEach((id) => {
                const el = document.getElementById(id);
                if (el) el.disabled = !!busy;
            });
        },

        _enableExport(on) {
            ['isaExportPngBtn', 'isaExportPdfBtn'].forEach((id) => {
                const btn = document.getElementById(id);
                if (btn) btn.disabled = !on;
            });
        },

        _ok(id) {
            const el = document.getElementById(id);
            if (el) {
                el.hidden = true;
                el.textContent = '';
            }
        },

        _err(id, msg) {
            const el = document.getElementById(id);
            if (el) {
                el.hidden = false;
                el.textContent = msg || '失败';
            }
        },

        esc(s) {
            return String(s == null ? '' : s)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;');
        },
    };

    global.IndexAnalysis = IndexAnalysis;
})(typeof window !== 'undefined' ? window : globalThis);

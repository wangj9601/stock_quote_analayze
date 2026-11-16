/**
 * 指数 / 行业指数分析结果绘制。按 DOM 前缀复用，不绑定具体代码通道。
 */
(function (global) {
    function esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function el(prefix, suffix) {
        return document.getElementById(prefix + suffix);
    }

    function ok(prefix, suffix) {
        const node = el(prefix, suffix);
        if (node) {
            node.hidden = true;
            node.textContent = '';
        }
    }

    function err(prefix, suffix, msg) {
        const node = el(prefix, suffix);
        if (node) {
            node.hidden = false;
            node.textContent = msg || '失败';
        }
    }

    function stockTable(list) {
        const rows = (list || []).slice(0, 8).map((s) => {
            const pct = s.change_percent;
            const cls = pct > 0 ? 'positive' : pct < 0 ? 'negative' : '';
            let href = `stock.html?code=${encodeURIComponent(s.code || '')}&tab=analysis`;
            if (typeof StockTradeLink !== 'undefined' && StockTradeLink.buildHref) {
                href = StockTradeLink.buildHref(s.code, s.name || '', { tab: 'analysis' });
            }
            return `<tr>
              <td><a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(s.code)}</a></td>
              <td>${esc(s.name || '')}</td>
              <td class="num ${cls}">${pct != null ? Number(pct).toFixed(2) + '%' : '--'}</td>
            </tr>`;
        }).join('');
        return `<table class="isa-table"><thead><tr><th>代码</th><th>名称</th><th>涨跌幅</th></tr></thead><tbody>${rows || '<tr><td colspan="3" class="muted">无</td></tr>'}</tbody></table>`;
    }

    const PaAnalysisView = {
        render(data, options) {
            const opt = options || {};
            const prefix = opt.prefix || 'isa';
            const empty = el(prefix, 'Empty');
            if (empty) empty.hidden = true;
            const exportRoot = el(prefix, 'ExportRoot');
            if (exportRoot) exportRoot.hidden = false;
            this._renderMeta(prefix, data);
            this._renderMarketView(prefix, data.market_view);
            this._renderBreadth(prefix, data.breadth, data.leaders, opt.showSectorContrib ? data.sector_contrib : null, opt);
            this._renderPa(prefix, data, opt);
        },

        _renderMeta(prefix, data) {
            const meta = el(prefix, 'Meta');
            if (!meta) return;
            const idx = data.index || {};
            const pct = idx.change_percent;
            const pctCls = pct > 0 ? 'positive' : pct < 0 ? 'negative' : '';
            const pctText = pct != null && !Number.isNaN(Number(pct))
                ? `${Number(pct) > 0 ? '+' : ''}${Number(pct).toFixed(2)}%`
                : '--';
            const rt = data.realtime || {};
            let rtNote = '';
            if (data.use_realtime) {
                rtNote = rt.merged === false
                    ? ` · 实时（${rt.reason || '未改写当日K'}）`
                    : ' · 实时';
            }
            meta.hidden = false;
            meta.innerHTML = `
              <div class="isa-meta-row">
                <strong>${esc(idx.name || '')}</strong>
                <span class="isa-code">${esc(idx.code || '')}</span>
                <span class="isa-ts">${esc(idx.ts_code || '')}</span>
                <span class="isa-price">${idx.current != null ? Number(idx.current).toFixed(2) : (idx.last_close != null ? Number(idx.last_close).toFixed(2) : '--')}</span>
                <span class="isa-pct ${pctCls}">${pctText}</span>
                <span class="muted">基准日 ${esc(data.trade_date || '--')}${rtNote}</span>
              </div>`;
        },

        _renderMarketView(prefix, mv) {
            const block = el(prefix, 'MarketViewBlock');
            const host = el(prefix, 'MarketViewHost');
            const status = el(prefix, 'MarketViewStatus');
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
            const bullets = (mv.bullets || []).map((b) => `<li>${esc(b)}</li>`).join('');
            host.innerHTML = `
              <div class="isa-market-view ${biasCls}">
                <div class="isa-bias-label">${esc(mv.bias_label || '中性')}</div>
                <p class="isa-mv-summary">${esc(mv.summary || '')}</p>
                <ul class="isa-mv-bullets">${bullets || '<li class="muted">暂无结构要点</li>'}</ul>
                <p class="isa-mv-note muted">环境对照结论，非买卖或仓位建议。</p>
              </div>`;
        },

        _renderBreadth(prefix, breadth, leaders, sector, opt) {
            const block = el(prefix, 'BreadthBlock');
            const host = el(prefix, 'BreadthHost');
            if (!block || !host) return;
            block.hidden = false;
            const parts = [];
            const emptyText = (opt && opt.emptyBreadthText)
                || '库内暂无该指数成分，广度与贡献从略；上方技术分析仍可用。建议优先查看沪深300等已维护成分的指数。';

            if (!breadth || !breadth.available) {
                parts.push(`<p class="isa-empty-soft">${esc((breadth && breadth.reason) || emptyText)}</p>`);
            } else {
                const official = (breadth.official_up_count != null || breadth.official_down_count != null)
                    ? `<div><span class="muted">行情上涨/下跌</span><strong>${breadth.official_up_count != null ? breadth.official_up_count : '--'} / ${breadth.official_down_count != null ? breadth.official_down_count : '--'}</strong></div>`
                    : '';
                parts.push(`
                  <div class="isa-breadth-grid">
                    <div><span class="muted">成分 / 有行情</span><strong>${breadth.member_count} / ${breadth.quoted_count}</strong></div>
                    <div><span class="muted">上涨</span><strong class="positive">${breadth.up_count}</strong></div>
                    <div><span class="muted">下跌</span><strong class="negative">${breadth.down_count}</strong></div>
                    <div><span class="muted">平盘</span><strong>${breadth.flat_count}</strong></div>
                    <div><span class="muted">上涨占比</span><strong>${breadth.up_ratio != null ? (breadth.up_ratio * 100).toFixed(1) + '%' : '--'}</strong></div>
                    <div><span class="muted">涨跌中位数</span><strong>${breadth.median_change_percent != null ? Number(breadth.median_change_percent).toFixed(2) + '%' : '--'}</strong></div>
                    ${official}
                  </div>`);
            }

            if (leaders && leaders.available) {
                parts.push('<div class="isa-leaders">');
                parts.push('<h5>今日涨幅前列</h5>' + stockTable(leaders.gainers || []));
                parts.push('<h5>今日跌幅前列</h5>' + stockTable(leaders.losers || []));
                parts.push('</div>');
            }

            if (sector) {
                parts.push(
                    `<p class="isa-disclaimer muted">${esc(
                        sector.disclaimer
                            || '行业贡献按成分成交额加权近似，非官方指数权重，仅供对照。'
                    )}</p>`
                );
                if (!sector.available) {
                    parts.push(`<p class="isa-empty-soft">${esc(sector.reason || '暂无可用的行业贡献数据')}</p>`);
                } else {
                    const rows = (sector.items || []).slice(0, 12).map((it) => {
                        const c = it.approx_contribution;
                        const cls = c > 0 ? 'positive' : c < 0 ? 'negative' : '';
                        return `<tr>
                          <td>${esc(it.board_name || it.board_code)}</td>
                          <td class="num">${it.member_count}</td>
                          <td class="num">${it.weighted_change_percent != null ? Number(it.weighted_change_percent).toFixed(2) + '%' : '--'}</td>
                          <td class="num ${cls}">${c != null ? Number(c).toFixed(3) : '--'}</td>
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

        _renderPa(prefix, data, opt) {
            const pa = el(prefix, 'PaSection');
            if (pa) pa.hidden = false;
            const assetType = (opt && opt.assetType) || 'index';
            const patternLabel = (opt && opt.patternMetaLabel) || '指数';

            const swingBlock = el(prefix, 'SwingBlock');
            const swingHost = el(prefix, 'SwingHost');
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
                    ok(prefix, 'SwingStatus');
                } else {
                    swingHost.innerHTML = '';
                    err(prefix, 'SwingStatus', (sw && sw.error) || '波段分析失败');
                }
            }

            const patternBlock = el(prefix, 'PatternBlock');
            const patternHost = el(prefix, 'PatternHost');
            if (patternBlock && patternHost) {
                patternBlock.hidden = false;
                const pt = data.pattern || {};
                const PT = global.PatternTool;
                if (pt.ok && PT && typeof PT.renderEmbedded === 'function') {
                    const fetched = pt.payload || pt;
                    const invN = fetched.invalidated_count || 0;
                    const meta = `${patternLabel} ${esc(fetched.code)} ${esc(fetched.name || '')} · 基准 ${esc(fetched.asof || '--')} · 日线不复权 · ${esc(PT.formatHitMeta ? PT.formatHitMeta((fetched.items || []).length, invN) : '')}`;
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
                    ok(prefix, 'PatternStatus');
                } else {
                    patternHost.innerHTML = '';
                    err(prefix, 'PatternStatus', (pt && pt.error) || '形态识别失败');
                }
            }

            const levelsBlock = el(prefix, 'LevelsBlock');
            const levelsHost = el(prefix, 'LevelsHost');
            if (levelsBlock && levelsHost) {
                levelsBlock.hidden = false;
                const lv = data.levels || {};
                const Levels = global.KdeLevelsTool;
                if (lv.ok && Levels && typeof Levels.renderEmbedded === 'function') {
                    const fetched = lv.payload || { data: lv.data, ok: true, message: '' };
                    Levels.renderEmbedded(levelsHost, fetched.data || lv.data || {}, true, '', {
                        code: (data.index && data.index.code) || '',
                        asset_type: assetType,
                        adjust: 'none',
                        max_levels: 8,
                    });
                    ok(prefix, 'LevelsStatus');
                } else {
                    levelsHost.innerHTML = '';
                    err(prefix, 'LevelsStatus', (lv && lv.error) || '阻力支撑计算失败');
                }
            }

            const gannBlock = el(prefix, 'GannBlock');
            const gannHost = el(prefix, 'GannHost');
            if (gannBlock && gannHost) {
                gannBlock.hidden = false;
                const gn = data.gann || {};
                const GT = global.GannTrendTool;
                if (gn.ok && gn.payload && GT && typeof GT.renderEmbedded === 'function') {
                    GT.renderEmbedded(gannHost, gn.payload);
                    ok(prefix, 'GannStatus');
                } else {
                    gannHost.innerHTML = '';
                    err(prefix, 'GannStatus', (gn && gn.error) || '江恩分析失败');
                }
            }
        },
    };

    global.PaAnalysisView = PaAnalysisView;
})(typeof window !== 'undefined' ? window : globalThis);

/** 技术工具 · 阻力支撑位：支撑/压力（KDE + VP + Fib/Cam/共振） */
const KdeLevelsTool = {
    _pendingAdjust: 'qfq',

    /** 与形态识别一致：勾选「前复权」→ qfq，否则 none；无 calc_qfq 权限时强制不复权 */
    selectedAdjust() {
        const el = document.getElementById('kdeLevelsAdjustQfq');
        if (!el || !el.checked) return 'none';
        if (window.PermissionEngine
            && typeof PermissionEngine.has === 'function'
            && !PermissionEngine.has('channel.analyze.tab.technical.btn.calc_qfq')) {
            return 'none';
        }
        const gate = el.closest('[data-perm="channel.analyze.tab.technical.btn.calc_qfq"]');
        if (gate && (gate.style.display === 'none' || gate.getAttribute('aria-hidden') === 'true')) {
            return 'none';
        }
        return 'qfq';
    },

    init() {
        const calcBtn = document.getElementById('kdeLevelsCalcBtn');
        const codeInput = document.getElementById('kdeLevelsStockCode');
        const watchSelect = document.getElementById('kdeLevelsWatchlist');
        const vpApplyBtn = document.getElementById('kdeVpLookbackApplyBtn');
        const vpDaysInput = document.getElementById('kdeVpLookbackInput');
        const vpFromInput = document.getElementById('kdeVpFromDateInput');
        const kdeApplyBtn = document.getElementById('kdeLookbackApplyBtn');
        const kdeDaysInput = document.getElementById('kdeLookbackInput');
        const kdeFromInput = document.getElementById('kdeFromDateInput');

        if (calcBtn) {
            calcBtn.addEventListener('click', () => this.calculateKdeLevels());
        }
        if (codeInput) {
            codeInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.calculateKdeLevels();
                }
            });
        }
        if (watchSelect) {
            watchSelect.addEventListener('change', () => {
                const val = watchSelect.value.trim();
                if (val && codeInput) {
                    codeInput.value = val;
                }
            });
        }
        if (vpApplyBtn) {
            vpApplyBtn.addEventListener('click', () => {
                this.calculateKdeLevels({
                    adjust: this._pendingAdjust || this.selectedAdjust(),
                    preferVpLookback: true,
                });
            });
        }
        if (vpDaysInput) {
            vpDaysInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    if (vpFromInput) vpFromInput.value = '';
                    this.calculateKdeLevels({
                        adjust: this._pendingAdjust || this.selectedAdjust(),
                        preferVpLookback: true,
                    });
                }
            });
            vpDaysInput.addEventListener('change', () => {
                // 改天数后清空起始日，避免仍按旧日期覆盖
                if (vpFromInput && vpFromInput.value) {
                    vpFromInput.value = '';
                }
            });
        }
        if (vpFromInput) {
            vpFromInput.addEventListener('change', () => {
                // 选日期后优先按起始日重算
            });
            vpFromInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.calculateKdeLevels({
                        adjust: this._pendingAdjust || this.selectedAdjust(),
                        preferVpLookback: true,
                    });
                }
            });
        }
        if (kdeApplyBtn) {
            kdeApplyBtn.addEventListener('click', () => {
                this.calculateKdeLevels({
                    adjust: this._pendingAdjust || this.selectedAdjust(),
                    preferKdeLookback: true,
                });
            });
        }
        if (kdeDaysInput) {
            kdeDaysInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    if (kdeFromInput) kdeFromInput.value = '';
                    this.calculateKdeLevels({
                        adjust: this._pendingAdjust || this.selectedAdjust(),
                        preferKdeLookback: true,
                    });
                }
            });
            kdeDaysInput.addEventListener('change', () => {
                if (kdeFromInput && kdeFromInput.value) {
                    kdeFromInput.value = '';
                }
            });
        }
        if (kdeFromInput) {
            kdeFromInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.calculateKdeLevels({
                        adjust: this._pendingAdjust || this.selectedAdjust(),
                        preferKdeLookback: true,
                    });
                }
            });
        }
    },

    readVpLookbackParams() {
        const daysEl = document.getElementById('kdeVpLookbackInput');
        const fromEl = document.getElementById('kdeVpFromDateInput');
        const fromDate = fromEl && fromEl.value ? String(fromEl.value).trim() : '';
        let days = null;
        if (daysEl && daysEl.value !== '') {
            const n = parseInt(daysEl.value, 10);
            if (Number.isFinite(n)) {
                days = Math.max(5, Math.min(750, n));
            }
        }
        return { vp_from_date: fromDate || null, vp_lookback: days };
    },

    readKdeLookbackParams() {
        const daysEl = document.getElementById('kdeLookbackInput');
        const fromEl = document.getElementById('kdeFromDateInput');
        const fromDate = fromEl && fromEl.value ? String(fromEl.value).trim() : '';
        let days = null;
        if (daysEl && daysEl.value !== '') {
            const n = parseInt(daysEl.value, 10);
            if (Number.isFinite(n)) {
                days = Math.max(20, Math.min(750, n));
            }
        }
        return { kde_from_date: fromDate || null, kde_lookback: days };
    },

    /**
     * 拉取阻力支撑位（与技术工具同口径）。
     * @returns {{ ok: boolean, data: object, message: string, candidates: array, httpOk: boolean }}
     */
    async fetchLevels(query, options = {}) {
        const adjust = options.adjust === 'none' ? 'none' : (options.adjust || 'qfq');
        const factorSource = options.factor_source || 'auto';
        const maxLevels = options.max_levels != null ? String(options.max_levels) : '8';
        const qs = new URLSearchParams({ max_levels: maxLevels, adjust });
        if (adjust === 'qfq') qs.set('factor_source', factorSource);
        if (options.vp_from_date) {
            qs.set('vp_from_date', options.vp_from_date);
        } else if (options.vp_lookback != null) {
            qs.set('vp_lookback', String(options.vp_lookback));
        }
        if (options.kde_from_date) {
            qs.set('kde_from_date', options.kde_from_date);
        } else if (options.kde_lookback != null) {
            qs.set('kde_lookback', String(options.kde_lookback));
        }
        if (options.use_realtime) qs.set('use_realtime', 'true');
        if (options.anchor_price != null && Number.isFinite(Number(options.anchor_price))) {
            qs.set('anchor_price', String(options.anchor_price));
        }
        const url = `${API_BASE_URL}/api/analysis/levels/${encodeURIComponent(query)}?${qs.toString()}`;
        const resp = await authFetch(url);
        const payload = await resp.json().catch(() => ({}));
        const candidates = Array.isArray(payload.candidates) ? payload.candidates : [];
        return {
            httpOk: resp.ok,
            ok: payload.success !== false && !!payload.data,
            data: payload.data || {},
            message: payload.message || '',
            candidates,
            payload,
        };
    },

    _fmtPrice(v) {
        return v != null && Number.isFinite(Number(v)) ? Number(v).toFixed(2) : '--';
    },

    /** 空价位时优先展示语义说明（如已突破 VAH） */
    _fmtPriceOrNote(price, note) {
        if (price != null && Number.isFinite(Number(price))) return this._fmtPrice(price);
        const n = note != null ? String(note).trim() : '';
        return n || '--';
    },

    /** 共振带强度展示：真空折减 / 密集压制增益旁注 */
    _fmtConfluenceStrength(z) {
        if (!z || typeof z !== 'object') return '--';
        const s = z.strength != null && Number.isFinite(Number(z.strength)) ? z.strength : null;
        if (s == null) return '--';
        if (z.chips_void) {
            const note = z.void_note
                ? String(z.void_note)
                : '位于筹码真空区，需防范高ATR击穿效应';
            const adj =
                z.strength_adjusted != null && Number.isFinite(Number(z.strength_adjusted))
                    ? `，折减后${z.strength_adjusted}`
                    : '';
            return `${s}（注：${note}${adj}）`;
        }
        if (z.chips_hvz) {
            const note = z.hvz_note
                ? String(z.hvz_note)
                : '重叠VP密集抛压区，压制因子放大';
            return `${s}（注：${note}）`;
        }
        return String(s);
    },

    _listHtml(values) {
        const arr = Array.isArray(values) ? values : [];
        if (!arr.length) return '<li class="muted">暂无</li>';
        return arr.map((x, i) => `<li><span class="idx">${i + 1}</span>${this._fmtPrice(x)}</li>`).join('');
    },

    _labeledListHtml(rows) {
        const arr = Array.isArray(rows) ? rows : [];
        if (!arr.length) return '<li class="muted">暂无</li>';
        return arr
            .map((row) => {
                const label = row.label != null ? String(row.label) : '';
                return `<li><span class="idx-label">${label}</span>${this._fmtPrice(row.price)}</li>`;
            })
            .join('');
    },

    /**
     * 将 levels 结果渲染到任意容器（个股分析嵌入用；口径与技术工具一致）。
     * @param {object} [options]
     * @param {string} [options.adjust]
     * @param {string} [options.factor_source]
     * @param {number} [options.max_levels]
     * @param {function} [options.onUpdated]  VP 回看重算后回调 `{ ok, data, message }`
     */
    renderEmbedded(container, data, ok, message, options = {}) {
        if (!container) return;
        const fmt = (v) => this._fmtPrice(v);
        const d = data || {};
        // options.code 优先：会话 DOM 恢复后 data 可能缺 stock_code；亦兼容 code 字段
        const code = String(options.code || d.stock_code || d.code || '').trim();
        if (code) container.dataset.stockCode = code;
        const name = d.stock_name || '';
        const title = name ? `${code} ${name}` : (code || '结果');
        const adjustBrief = d.price_adjust === 'qfq' ? '前复权' : '不复权';
        const summary = ok
            ? `${title} · ${adjustBrief}`
            : `${title} · ${adjustBrief}${message ? `（${message}）` : ''}`;

        const vp = d.volume_profile || {};
        const vpCmp = d.vp_vs_kde || {};
        const classic = d.classic_levels || {};
        const fib = classic.fibonacci || null;
        const pivot = classic.pivot || null;
        const cam = classic.camarilla || null;
        const atrPiv = classic.atr_pivot || null;
        const conf = classic.confluence_zones || d.confluence_zones || null;
        const vpAdjust = vp.price_adjust || d.price_adjust || 'none';
        const classicAdjust = classic.price_adjust || d.price_adjust || 'none';
        const usedLb = vp.bars_used != null ? vp.bars_used : vp.lookback;
        const ws = vp.window_start ? String(vp.window_start).slice(0, 10) : '';
        const we = vp.window_end ? String(vp.window_end).slice(0, 10) : '';
        const winText = ws && we ? ` · ${ws}～${we}` : (ws ? ` · 自 ${ws}` : '');
        const vaPct = vp.value_area_pct != null
            ? `${Math.round(Number(vp.value_area_pct) * 100)}%`
            : '--';
        const lookbackInputVal = usedLb != null ? String(usedLb) : '60';
        const fromInputVal = String(vp.from_date || vp.window_start || '').slice(0, 10);

        const cmpCell = (row, field) => {
            const r = row || {};
            if (field === 'diff') {
                if (r.diff == null) return r.note ? `<span class="muted" title="${this._esc(r.note)}">--</span>` : '--';
                const sign = Number(r.diff) > 0 ? '+' : '';
                const pct = r.diff_pct != null ? `（${Number(r.diff_pct).toFixed(2)}%）` : '';
                return `${sign}${fmt(r.diff)}${pct}`;
            }
            if (field === 'align') {
                if (r.kde == null || r.vp == null) {
                    return r.note
                        ? `<span class="muted" title="${this._esc(r.note)}">语义</span>`
                        : '--';
                }
                return r.aligned
                    ? '<span class="is-aligned">是</span>'
                    : '<span class="not-aligned">否</span>';
            }
            if (field === 'vp' && (r.vp == null || r.vp === '') && r.note) {
                return `<span class="muted kde-vp-note" title="${this._esc(r.note)}">${this._esc(r.note)}</span>`;
            }
            return fmt(r[field]);
        };
        const alignedNote =
            (vpCmp.support && vpCmp.support.aligned)
            || (vpCmp.resistance && vpCmp.resistance.aligned)
                ? '存在 KDE↔VP 价位共振（相对偏差 ≤1.5%）；短线仍以 KDE 为主，VP 作辅助确认。'
                : '相对偏差 ≤1.5% 视为价位共振；短线仍以 KDE 为主，VP 作辅助对照。';

        const fibRows = [];
        if (fib && Array.isArray(fib.retracements)) {
            fib.retracements.forEach((x) => {
                fibRows.push({ label: String(x.ratio), price: x.price });
            });
        }
        if (fib && fib.nearest_extension) {
            const ext = fib.nearest_extension;
            fibRows.push({
                label: `扩展${ext.ratio != null ? ext.ratio : ''}`,
                price: ext.price,
            });
        }
        const pivRows = [];
        if (pivot) {
            ['R3', 'R2', 'R1', 'P', 'S1', 'S2', 'S3'].forEach((k) => {
                if (pivot[k] != null) pivRows.push({ label: k, price: pivot[k] });
            });
        }
        const camRows = [];
        if (cam) {
            ['R4', 'R3', 'R2', 'R1', 'S1', 'S2', 'S3', 'S4'].forEach((k) => {
                if (cam[k] != null) camRows.push({ label: k, price: cam[k] });
            });
        }
        const confRows = [];
        // 支撑：center 降序（近现价=支撑1）；压力：center 升序（近现价=压力1）
        const pushZones = (arr, tag, desc) => {
            const sorted = (arr || []).slice().sort((a, b) => {
                const ca = Number(a && a.center);
                const cb = Number(b && b.center);
                if (!Number.isFinite(ca) || !Number.isFinite(cb)) return 0;
                return desc ? cb - ca : ca - cb;
            });
            sorted.forEach((z, i) => {
                const tierBit = z.tier === 'strong' ? '强·' : '';
                const lab = z.label_zh || `${tag}`;
                confRows.push({
                    label: `${tierBit}${lab}${i + 1}·强度${this._fmtConfluenceStrength(z)}·${(z.sources || []).join('+')}`,
                    price: z.center,
                });
            });
        };
        if (conf && conf.ok) {
            pushZones(conf.supports, '支撑', true);
            pushZones(conf.resistances, '压力', false);
        }
        const nzS = conf && conf.nearest_support_zone;
        const nzR = conf && conf.nearest_resistance_zone;
        const confNearS = nzS ? `${fmt(nzS.center)} [${fmt(nzS.low)}–${fmt(nzS.high)}]` : '--';
        const confNearR = nzR ? `${fmt(nzR.center)} [${fmt(nzR.low)}–${fmt(nzR.high)}]` : '--';
        const pickStrongOrNearest = (zones, nearest) => {
            const strong = (zones || []).filter((z) => z && z.tier === 'strong');
            if (strong.length) {
                const sorted = strong.slice().sort((a, b) => {
                    const sa = Number(a.strength_adjusted != null ? a.strength_adjusted : a.strength) || 0;
                    const sb = Number(b.strength_adjusted != null ? b.strength_adjusted : b.strength) || 0;
                    return sb - sa;
                });
                return { zone: sorted[0], isStrong: true };
            }
            if (nearest) return { zone: nearest, isStrong: nearest.tier === 'strong' };
            if ((zones || []).length) return { zone: zones[0], isStrong: false };
            return { zone: null, isStrong: false };
        };
        const heroS = conf && conf.ok ? pickStrongOrNearest(conf.supports, nzS) : { zone: null, isStrong: false };
        const heroR = conf && conf.ok ? pickStrongOrNearest(conf.resistances, nzR) : { zone: null, isStrong: false };
        const heroZoneHtml = (picked, sideLabel) => {
            const z = picked && picked.zone;
            if (!z) {
                return `<div class="kde-conf-hero-item is-empty"><span class="kde-conf-hero-side">${this._esc(sideLabel)}</span><span class="muted">暂无</span></div>`;
            }
            const isStrong = !!(picked && picked.isStrong);
            const label = z.label_zh || (isStrong ? `强共振${sideLabel}` : `共振${sideLabel}`);
            const src = (z.sources || []).join('+') || '--';
            const band = `${fmt(z.center)} [${fmt(z.low)}–${fmt(z.high)}]`;
            const note = isStrong ? '' : '<span class="kde-conf-hero-note">（非强共振，取最近带）</span>';
            return `<div class="kde-conf-hero-item${isStrong ? ' is-strong' : ''}">` +
                `<div class="kde-conf-hero-title"><span class="kde-conf-tier-badge${isStrong ? ' is-strong' : ''}">${this._esc(label)}</span>${note}</div>` +
                `<div class="kde-conf-hero-price"><strong>${this._esc(band)}</strong></div>` +
                `<div class="kde-conf-hero-meta">强度 ${this._esc(this._fmtConfluenceStrength(z))} · 来源 ${this._esc(src)}</div>` +
                `</div>`;
        };
        const confHeroHtml = (conf && conf.ok)
            ? `<div class="kde-conf-hero">
                    <h4 class="kde-levels-subtitle kde-conf-hero-heading">多算法强共振（主视图）</h4>
                    <div class="kde-conf-hero-grid">
                        ${heroZoneHtml(heroS, '支撑')}
                        ${heroZoneHtml(heroR, '压力')}
                    </div>
                    <div class="kde-conf-hero-near muted">最近支撑带 ${this._esc(confNearS)} · 最近压力带 ${this._esc(confNearR)}</div>
                    <details class="kde-conf-list-details" open>
                        <summary>共振带完整列表</summary>
                        <ul>${this._labeledListHtml(confRows)}</ul>
                    </details>
               </div>`
            : `<div class="kde-conf-hero is-empty">
                    <h4 class="kde-levels-subtitle">多算法强共振（主视图）</h4>
                    <p class="muted">${this._esc((conf && conf.reason) ? `共振带：${conf.reason}` : '暂无共振带')}</p>
               </div>`;

        const fibDir = fib && fib.direction;
        const fibDirTxt = fibDir === 'up' ? '上升段回撤' : fibDir === 'down' ? '下降段反弹' : '--';
        const fibAnchor = (fib && fib.anchor_method) === 'zigzag_fractal_running'
            ? 'ZigZag+运行高/低'
            : ((fib && fib.anchor_method) === 'zigzag_fractal'
                ? 'ZigZag+分形'
                : (fib && fib.anchor_method ? String(fib.anchor_method) : '--'));
        const fibExceedNote = (fib && fib.anchor_exceeded)
            ? ` · 已越过确认锚点${fib.confirmed_swing_high != null ? `高${fmt(fib.confirmed_swing_high)}` : ''}${fib.confirmed_swing_low != null && fib.direction === 'down' ? `/低${fmt(fib.confirmed_swing_low)}` : ''}，按运行极值重算`
            : '';
        const fibBits = [];
        if (fib && fib.depth_pct != null) fibBits.push(`深度 ${(Number(fib.depth_pct) * 100).toFixed(1)}%`);
        if (fib && fib.bar_span != null) fibBits.push(`跨度 ${fib.bar_span} 根`);
        if (fib && fib.min_swing_bars != null) fibBits.push(`≥${fib.min_swing_bars} 根`);
        if (fib && fib.skipped_short_leg) fibBits.push('已跳过过短波段');
        const fibDepth = fibBits.length ? ` · ${fibBits.join(' · ')}` : '';
        const atrTip = atrPiv && atrPiv.atr != null
            ? `ATR-Pivot：P=${fmt(atrPiv.P)} ±1ATR R1/S1=${fmt(atrPiv.R1)}/${fmt(atrPiv.S1)}`
              + ` ±2ATR R2/S2=${fmt(atrPiv.R2)}/${fmt(atrPiv.S2)}（ATR=${fmt(atrPiv.atr)}）`
            : '';

        const srcMap = {
            akshare_sina_qfq: '新浪（已归一化）',
            baostock_qfq: 'BaoStock',
        };
        const srcText = srcMap[d.adj_factor_source] || d.adj_factor_source || '未知';
        const adjustLabel = d.price_adjust === 'qfq'
            ? `前复权（因子：${srcText}${d.adj_factor_asof ? `，截至 ${d.adj_factor_asof}` : ''}${d.factor_fetched ? '，本次已拉取' : '，已用缓存'}）`
            : '不复权日K';
        const used = d.kde_lookback_used;
        const expanded = d.kde_lookback_expanded;
        const initLb = d.kde_lookback_initial || 60;
        const maxLb = d.kde_lookback_max || 750;
        const kdeLookbackInputVal = initLb != null ? String(initLb) : '60';
        const kdeFromInputVal = String(d.kde_from_date || '').slice(0, 10);
        const kdeExpandText = expanded ? ' · 已扩窗' : '';
        const classicLb = classic.lookback || 180;
        const classicBasis = classicAdjust === 'qfq' ? '前复权 OHLC' : '不复权 OHLC';
        const classicNote = classic.ok
            ? `ZigZag Fib / Cam / Pivot ${classicBasis} · 回看 ${classicLb} 日`
            : `Fib/Pivot：${classic.reason || '暂无'}`;
        const confNote = conf && conf.ok
            ? `共振带 ${(conf.supports || []).length + (conf.resistances || []).length} 条`
            : conf ? `共振带：${conf.reason || '暂无'}` : null;
        const vpNote = vp.ok
            ? `VP 回看 ${vp.lookback || 60} 日 · POC ${fmt(vp.poc)}`
            : `VP：${vp.reason || '暂无'}`;
        const metaParts = [
            adjustLabel,
            d.description || '成交量加权 KDE 支撑 / 压力',
            used != null ? `KDE 实际回看 ${used} 日` : null,
            expanded ? '（已扩窗）' : null,
            `KDE 初始 ${initLb} / 上限 ${maxLb}`,
            vpNote,
            classicNote,
            confNote,
            d.kde_reason ? `KDE 状态：${d.kde_reason}` : null,
        ].filter(Boolean);

        const tagCls = (adj) => (adj === 'qfq' ? 'kde-levels-adjust-tag is-qfq' : 'kde-levels-adjust-tag is-raw');
        const tagTxt = (adj) => (adj === 'qfq' ? '前复权' : '不复权');

        container.innerHTML = `
            <div class="kde-levels-result ssa-embedded-levels">
                <div class="kde-levels-summary">${this._esc(summary)}</div>
                ${confHeroHtml}
                <div class="kde-levels-details-toolbar">
                    <button type="button" class="btn btn-secondary btn-sm kde-levels-expand-all">展开全部算法明细</button>
                    <button type="button" class="btn btn-secondary btn-sm kde-levels-collapse-all">全部收起</button>
                </div>
                <details class="kde-algo-details" open>
                    <summary>现价速览</summary>
                    <div class="kde-levels-card current kde-levels-card--inline">
                        <div class="kde-levels-price">${fmt(d.current_price)}</div>
                        <div class="kde-levels-near">
                            <div>KDE 最近支撑：<strong>${fmt(d.nearest_support)}</strong></div>
                            <div>KDE 最近压力：<strong>${fmt(d.nearest_resistance)}</strong></div>
                        </div>
                    </div>
                </details>
                <details class="kde-algo-details" open>
                    <summary>KDE 结构位 <span class="${tagCls(d.price_adjust === 'qfq' ? 'qfq' : 'none')}">${tagTxt(d.price_adjust === 'qfq' ? 'qfq' : 'none')}</span></summary>
                    <div class="kde-levels-grid">
                        <div class="kde-levels-card support">
                            <h4>支撑位</h4>
                            <ul>${this._listHtml(d.support_levels)}</ul>
                        </div>
                        <div class="kde-levels-card current">
                            <h4>现价 / 回看</h4>
                            <div class="kde-levels-price">${fmt(d.current_price)}</div>
                            <div class="kde-levels-near">
                                <div>最近支撑：<strong>${fmt(d.nearest_support)}</strong></div>
                                <div>最近压力：<strong>${fmt(d.nearest_resistance)}</strong></div>
                                <div class="kde-levels-dir kde-vp-lookback-ctrl">
                                    <span>回看</span>
                                    <input type="number" class="kde-vp-lookback-days ssa-kde-lookback-days"
                                        min="20" max="750" step="1" value="${this._esc(kdeLookbackInputVal)}"
                                        title="KDE 初始回看交易日数">
                                    <span>日 · 起始</span>
                                    <input type="date" class="kde-vp-from-date ssa-kde-from-date"
                                        value="${this._esc(kdeFromInputVal)}"
                                        title="KDE 回看起始日期（优先于天数；可调初始回看，无支撑仍扩窗）">
                                    <button type="button" class="btn btn-secondary btn-sm ssa-kde-lookback-apply">应用</button>
                                    <span class="kde-vp-lookback-meta">
                                        （初始 <strong>${initLb != null ? String(initLb) : '--'}</strong>
                                        / 实际 <strong>${used != null ? String(used) : '--'}</strong> 日${kdeExpandText}
                                        · 上限 <strong>${maxLb != null ? String(maxLb) : '750'}</strong>）
                                    </span>
                                </div>
                            </div>
                        </div>
                        <div class="kde-levels-card resistance">
                            <h4>压力位</h4>
                            <ul>${this._listHtml(d.resistance_levels)}</ul>
                        </div>
                    </div>
                </details>
                <details class="kde-algo-details" open>
                    <summary>Volume Profile（参考）
                        <span class="${tagCls(vpAdjust)}">${tagTxt(vpAdjust)}</span>
                    </summary>
                    <div class="kde-levels-grid kde-levels-grid--vp">
                        <div class="kde-levels-card vp">
                            <h4>日线 VP（可调回看）</h4>
                            <div class="kde-levels-near">
                                <div>POC：<strong>${fmt(vp.poc)}</strong></div>
                                <div>VAL：<strong>${fmt(vp.val)}</strong></div>
                                <div>VAH：<strong>${fmt(vp.vah)}</strong></div>
                                <div>最近支撑：<strong>${this._fmtPriceOrNote(vp.nearest_support, vp.support_note)}</strong></div>
                                <div>最近压力：<strong>${this._fmtPriceOrNote(vp.nearest_resistance, vp.resistance_note)}</strong></div>
                                <div class="kde-levels-dir kde-vp-lookback-ctrl">
                                    <span>回看</span>
                                    <input type="number" class="kde-vp-lookback-days ssa-vp-lookback-days"
                                        min="5" max="750" step="1" value="${this._esc(lookbackInputVal)}"
                                        title="回看交易日数">
                                    <span>日 · 起始</span>
                                    <input type="date" class="kde-vp-from-date ssa-vp-from-date"
                                        value="${this._esc(fromInputVal)}"
                                        title="回看起始日期（优先于天数）">
                                    <button type="button" class="btn btn-secondary btn-sm ssa-vp-lookback-apply">应用</button>
                                    <span class="kde-vp-lookback-meta">
                                        （实际 <strong>${usedLb != null ? String(usedLb) : '--'}</strong> 日${winText}）
                                        · 价值区 <strong>${vaPct}</strong>
                                    </span>
                                </div>
                            </div>
                        </div>
                        <div class="kde-levels-card vp-compare">
                            <h4>KDE ↔ VP</h4>
                            <table class="kde-vp-compare-table">
                                <thead><tr><th></th><th>KDE</th><th>VP</th><th>差</th><th>共振</th></tr></thead>
                                <tbody>
                                    <tr>
                                        <td>支撑</td>
                                        <td>${cmpCell(vpCmp.support, 'kde')}</td>
                                        <td>${cmpCell(vpCmp.support, 'vp')}</td>
                                        <td>${cmpCell(vpCmp.support, 'diff')}</td>
                                        <td>${cmpCell(vpCmp.support, 'align')}</td>
                                    </tr>
                                    <tr>
                                        <td>压力</td>
                                        <td>${cmpCell(vpCmp.resistance, 'kde')}</td>
                                        <td>${cmpCell(vpCmp.resistance, 'vp')}</td>
                                        <td>${cmpCell(vpCmp.resistance, 'diff')}</td>
                                        <td>${cmpCell(vpCmp.resistance, 'align')}</td>
                                    </tr>
                                </tbody>
                            </table>
                            <p class="kde-vp-compare-note">${this._esc(alignedNote)}</p>
                        </div>
                    </div>
                </details>
                <details class="kde-algo-details" open>
                    <summary>黄金分割 / Pivot / Camarilla
                        <span class="${tagCls(classicAdjust)}">${tagTxt(classicAdjust)}</span>
                    </summary>
                    <div class="kde-levels-grid kde-levels-grid--classic">
                        <div class="kde-levels-card fib">
                            <h4>黄金分割</h4>
                            <div class="kde-levels-near">
                                <div class="kde-levels-meta-line">锚定：<strong>${this._esc(fibAnchor)}</strong>${this._esc(fibDepth)}${this._esc(fibExceedNote)}</div>
                                <div>高点：<strong>${fmt(fib && fib.swing_high)}</strong>
                                    <span class="kde-levels-date">${fib && fib.swing_high_date ? `（${fib.swing_high_date}）` : ''}</span></div>
                                <div>低点：<strong>${fmt(fib && fib.swing_low)}</strong>
                                    <span class="kde-levels-date">${fib && fib.swing_low_date ? `（${fib.swing_low_date}）` : ''}</span></div>
                                <div>最近支撑：<strong>${this._fmtPriceOrNote(classic.nearest_fib_support, classic.fib_support_note || (fib && fib.support_note))}</strong></div>
                                <div>最近压力：<strong>${this._fmtPriceOrNote(classic.nearest_fib_resistance, classic.fib_resistance_note || (fib && fib.resistance_note))}</strong></div>
                                <div class="kde-levels-dir">方向：<strong>${fibDirTxt}</strong></div>
                            </div>
                            <ul>${this._labeledListHtml(fibRows)}</ul>
                        </div>
                        <div class="kde-levels-card pivot">
                            <h4>经典 Pivot</h4>
                            <div class="kde-levels-near">
                                <div>最近支撑：<strong>${this._fmtPriceOrNote(classic.nearest_pivot_support, classic.pivot_support_note)}</strong></div>
                                <div>最近压力：<strong>${this._fmtPriceOrNote(classic.nearest_pivot_resistance, classic.pivot_resistance_note)}</strong></div>
                            </div>
                            <ul>${this._labeledListHtml(pivRows)}</ul>
                        </div>
                        <div class="kde-levels-card cam">
                            <h4>Camarilla <span class="kde-levels-badge">波动率修正</span></h4>
                            <div class="kde-levels-near">
                                <div>最近支撑：<strong>${this._fmtPriceOrNote(
                                    classic.nearest_cam_support ?? (cam && cam.nearest_support),
                                    classic.cam_support_note ?? (cam && cam.support_note)
                                )}</strong></div>
                                <div>最近压力：<strong>${this._fmtPriceOrNote(
                                    classic.nearest_cam_resistance ?? (cam && cam.nearest_resistance),
                                    classic.cam_resistance_note ?? (cam && cam.resistance_note)
                                )}</strong></div>
                            </div>
                            <ul>${this._labeledListHtml(camRows)}</ul>
                            <p class="kde-levels-atr-tip">${this._esc(atrTip)}</p>
                        </div>
                    </div>
                </details>
                <p class="kde-levels-meta">${this._esc(metaParts.join(' · '))}</p>
            </div>`;

        // 缺省全部展开（与模板 open 一致；保证动态插入后状态正确）
        container.querySelectorAll('details.kde-algo-details, details.kde-conf-list-details').forEach((el) => {
            el.open = true;
        });

        const expandAllBtn = container.querySelector('.kde-levels-expand-all');
        const collapseAllBtn = container.querySelector('.kde-levels-collapse-all');
        if (expandAllBtn) {
            expandAllBtn.addEventListener('click', () => {
                container.querySelectorAll('details.kde-algo-details, details.kde-conf-list-details').forEach((el) => {
                    el.open = true;
                });
            });
        }
        if (collapseAllBtn) {
            collapseAllBtn.addEventListener('click', () => {
                container.querySelectorAll('details.kde-algo-details').forEach((el) => {
                    el.open = false;
                });
            });
        }

        const bindCtx = {
            code,
            adjust: options.adjust != null
                ? (options.adjust === 'qfq' ? 'qfq' : 'none')
                : (d.price_adjust === 'qfq' ? 'qfq' : 'none'),
            factor_source: options.factor_source || 'auto',
            max_levels: options.max_levels != null ? options.max_levels : 8,
            onUpdated: typeof options.onUpdated === 'function' ? options.onUpdated : null,
        };
        this._bindEmbeddedVpControls(container, bindCtx);
        this._bindEmbeddedKdeControls(container, bindCtx);
    },

    /**
     * 会话用 innerHTML 恢复后，事件监听会丢失；仅重新绑定回看「应用」控件。
     * @param {HTMLElement} container
     * @param {object} ctx  同 renderEmbedded 的 bind 上下文（须含 code）
     */
    rebindEmbeddedControls(container, ctx = {}) {
        if (!container) return;
        const code = String(
            (ctx && ctx.code)
            || container.dataset.stockCode
            || ''
        ).trim();
        if (code) container.dataset.stockCode = code;
        // 克隆替换，避免重复 addEventListener（会话恢复或多次 rebind）
        [
            '.ssa-kde-lookback-apply', '.ssa-kde-lookback-days', '.ssa-kde-from-date',
            '.ssa-vp-lookback-apply', '.ssa-vp-lookback-days', '.ssa-vp-from-date',
        ].forEach((sel) => {
            const el = container.querySelector(sel);
            if (el && el.parentNode) {
                el.parentNode.replaceChild(el.cloneNode(true), el);
            }
        });
        const bindCtx = {
            code,
            adjust: (ctx && ctx.adjust) === 'none' ? 'none' : 'qfq',
            factor_source: (ctx && ctx.factor_source) || 'auto',
            max_levels: (ctx && ctx.max_levels) != null ? ctx.max_levels : 8,
            onUpdated: ctx && typeof ctx.onUpdated === 'function' ? ctx.onUpdated : null,
        };
        this._bindEmbeddedVpControls(container, bindCtx);
        this._bindEmbeddedKdeControls(container, bindCtx);
    },

    _readEmbeddedVpParams(container) {
        const daysEl = container && container.querySelector('.ssa-vp-lookback-days');
        const fromEl = container && container.querySelector('.ssa-vp-from-date');
        const fromDate = fromEl && fromEl.value ? String(fromEl.value).trim() : '';
        let days = null;
        if (daysEl && daysEl.value !== '') {
            const n = parseInt(daysEl.value, 10);
            if (Number.isFinite(n)) {
                days = Math.max(5, Math.min(750, n));
            }
        }
        return { vp_from_date: fromDate || null, vp_lookback: days };
    },

    _readEmbeddedKdeParams(container) {
        const daysEl = container && container.querySelector('.ssa-kde-lookback-days');
        const fromEl = container && container.querySelector('.ssa-kde-from-date');
        const fromDate = fromEl && fromEl.value ? String(fromEl.value).trim() : '';
        let days = null;
        if (daysEl && daysEl.value !== '') {
            const n = parseInt(daysEl.value, 10);
            if (Number.isFinite(n)) {
                days = Math.max(20, Math.min(750, n));
            }
        }
        return { kde_from_date: fromDate || null, kde_lookback: days };
    },

    _bindEmbeddedVpControls(container, ctx) {
        if (!container) return;
        const applyBtn = container.querySelector('.ssa-vp-lookback-apply');
        const daysInput = container.querySelector('.ssa-vp-lookback-days');
        const fromInput = container.querySelector('.ssa-vp-from-date');
        const run = () => this._applyEmbeddedLookback(container, ctx, 'vp');

        if (applyBtn) {
            applyBtn.addEventListener('click', () => run());
        }
        if (daysInput) {
            daysInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    if (fromInput) fromInput.value = '';
                    run();
                }
            });
            daysInput.addEventListener('change', () => {
                if (fromInput && fromInput.value) fromInput.value = '';
            });
        }
        if (fromInput) {
            fromInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    run();
                }
            });
        }
    },

    _bindEmbeddedKdeControls(container, ctx) {
        if (!container) return;
        const applyBtn = container.querySelector('.ssa-kde-lookback-apply');
        const daysInput = container.querySelector('.ssa-kde-lookback-days');
        const fromInput = container.querySelector('.ssa-kde-from-date');
        const run = () => this._applyEmbeddedLookback(container, ctx, 'kde');

        if (applyBtn) {
            applyBtn.addEventListener('click', () => run());
        }
        if (daysInput) {
            daysInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    if (fromInput) fromInput.value = '';
                    run();
                }
            });
            daysInput.addEventListener('change', () => {
                if (fromInput && fromInput.value) fromInput.value = '';
            });
        }
        if (fromInput) {
            fromInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    run();
                }
            });
        }
    },

    async _applyEmbeddedLookback(container, ctx, which) {
        let code = String(
            (ctx && ctx.code)
            || (container && container.dataset && container.dataset.stockCode)
            || ''
        ).trim();
        if (!code) {
            const input = document.getElementById('ssaStockCode');
            const raw = input && input.value ? String(input.value).trim() : '';
            const token = raw.split(/\s+/)[0] || '';
            const body = /^(sh|sz|bj|hk)/i.test(token) ? token.slice(2) : token;
            if (/^\d{4,6}$/.test(body)) code = token;
        }
        if (!code) {
            if (window.CommonUtils) CommonUtils.showToast('缺少股票代码，请先完成分析', 'warning');
            return;
        }
        if (window.CommonUtils && !CommonUtils.checkLoginAndHandleExpiry()) return;

        const vpParams = this._readEmbeddedVpParams(container);
        const kdeParams = this._readEmbeddedKdeParams(container);
        if (which === 'kde' && !kdeParams.kde_from_date && kdeParams.kde_lookback == null) {
            if (window.CommonUtils) CommonUtils.showToast('请填写 KDE 回看天数或起始日期', 'warning');
            return;
        }
        if (which === 'vp' && !vpParams.vp_from_date && vpParams.vp_lookback == null) {
            if (window.CommonUtils) CommonUtils.showToast('请填写 VP 回看天数或起始日期', 'warning');
            return;
        }
        const applyBtn = container.querySelector(
            which === 'kde' ? '.ssa-kde-lookback-apply' : '.ssa-vp-lookback-apply'
        );
        if (applyBtn) {
            applyBtn.disabled = true;
            applyBtn.textContent = '计算中…';
        }
        const statusEl = document.getElementById('ssaLevelsStatus');
        const loadingTxt = which === 'kde'
            ? '正在按回看窗口重算 KDE 支撑/压力…'
            : '正在按回看窗口重算 Volume Profile…';
        if (statusEl) {
            statusEl.hidden = false;
            statusEl.className = 'ssa-block-status is-loading';
            statusEl.textContent = loadingTxt;
        }
        try {
            const fetched = await this.fetchLevels(code, {
                adjust: (ctx && ctx.adjust) === 'none' ? 'none' : 'qfq',
                factor_source: (ctx && ctx.factor_source) || 'auto',
                max_levels: (ctx && ctx.max_levels) != null ? ctx.max_levels : 8,
                vp_from_date: vpParams.vp_from_date || undefined,
                vp_lookback: vpParams.vp_from_date
                    ? undefined
                    : (vpParams.vp_lookback != null ? vpParams.vp_lookback : undefined),
                kde_from_date: kdeParams.kde_from_date || undefined,
                kde_lookback: kdeParams.kde_from_date
                    ? undefined
                    : (kdeParams.kde_lookback != null ? kdeParams.kde_lookback : undefined),
            });
            if (fetched.candidates && fetched.candidates.length > 1 && !fetched.data) {
                throw new Error(fetched.message || '股票代码不唯一');
            }
            if (!fetched.httpOk && !fetched.data) {
                throw new Error(fetched.message || (which === 'kde' ? 'KDE 回看重算失败' : 'VP 回看重算失败'));
            }
            this.renderEmbedded(container, fetched.data || {}, fetched.ok, fetched.message, {
                code,
                adjust: (ctx && ctx.adjust) === 'none' ? 'none' : 'qfq',
                factor_source: (ctx && ctx.factor_source) || 'auto',
                max_levels: (ctx && ctx.max_levels) != null ? ctx.max_levels : 8,
                onUpdated: ctx && ctx.onUpdated,
            });
            if (ctx && typeof ctx.onUpdated === 'function') {
                ctx.onUpdated({
                    ok: !!fetched.ok,
                    data: fetched.data || {},
                    message: fetched.message || '',
                });
            }
            if (statusEl) {
                statusEl.hidden = true;
                statusEl.textContent = '';
            }
            if (window.CommonUtils) {
                CommonUtils.showToast(which === 'kde' ? 'KDE 回看已更新' : 'VP 回看已更新', 'success');
            }
        } catch (e) {
            console.warn(which === 'kde' ? '个股分析·KDE 回看重算失败' : '个股分析·VP 回看重算失败', e);
            if (applyBtn) {
                applyBtn.disabled = false;
                applyBtn.textContent = '应用';
            }
            if (statusEl) {
                statusEl.hidden = false;
                statusEl.className = 'ssa-block-status is-error';
                statusEl.textContent = e.message || (which === 'kde' ? 'KDE 回看重算失败' : 'VP 回看重算失败');
            }
            if (window.CommonUtils) {
                CommonUtils.showToast(
                    e.message || (which === 'kde' ? 'KDE 回看重算失败' : 'VP 回看重算失败'),
                    'error'
                );
            }
        }
    },

    _esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    },

    async loadKdeWatchlistOptions() {
        const select = document.getElementById('kdeLevelsWatchlist');
        if (!select || select.dataset.loaded === '1') return;
        if (!CommonUtils.checkLoginAndHandleExpiry()) return;

        try {
            const resp = await authFetch(`${API_BASE_URL}/api/watchlist`);
            if (!resp.ok) return;
            const payload = await resp.json();
            const list = Array.isArray(payload)
                ? payload
                : (payload.data || payload.items || payload.stocks || []);
            if (!Array.isArray(list)) return;
            const seen = new Set();
            const opts = ['<option value="">-- 可选自选股 --</option>'];
            (list || []).forEach((item) => {
                const code = String(item.code || item.stock_code || '').trim();
                if (!code || seen.has(code)) return;
                seen.add(code);
                const name = item.name || item.stock_name || '';
                const label = name ? `${code} ${name}` : code;
                opts.push(`<option value="${code}">${label}</option>`);
            });
            select.innerHTML = opts.join('');
            select.dataset.loaded = '1';
        } catch (e) {
            console.warn('加载自选股列表失败:', e);
        }
    },

    hideKdeLevelsCandidates() {
        const box = document.getElementById('kdeLevelsCandidates');
        const list = document.getElementById('kdeLevelsCandidateList');
        if (box) box.hidden = true;
        if (list) list.innerHTML = '';
    },

    renderKdeLevelsCandidates(candidates, message) {
        const box = document.getElementById('kdeLevelsCandidates');
        const list = document.getElementById('kdeLevelsCandidateList');
        const title = box && box.querySelector('.kde-levels-candidates-title');
        const resultEl = document.getElementById('kdeLevelsResult');
        const emptyEl = document.getElementById('kdeLevelsEmpty');
        if (!box || !list) return;

        if (title) {
            title.textContent = message || '匹配到多只股票，请选择：';
        }
        const items = Array.isArray(candidates) ? candidates : [];
        list.innerHTML = items.map((item) => {
            const code = String(item.code || '').trim();
            const name = String(item.name || '').trim();
            const label = name ? `${code} ${name}` : code;
            const safeCode = code.replace(/"/g, '&quot;');
            return `<li><button type="button" class="kde-levels-candidate-btn" data-code="${safeCode}">${label}</button></li>`;
        }).join('');

        list.querySelectorAll('.kde-levels-candidate-btn').forEach((btn) => {
            btn.addEventListener('click', () => {
                const code = btn.getAttribute('data-code') || '';
                const codeInput = document.getElementById('kdeLevelsStockCode');
                if (codeInput) codeInput.value = code;
                this.hideKdeLevelsCandidates();
                this.calculateKdeLevels({ adjust: this._pendingAdjust || this.selectedAdjust() });
            });
        });

        box.hidden = false;
        if (resultEl) resultEl.hidden = true;
        if (emptyEl) {
            emptyEl.hidden = true;
        }
    },

    async calculateKdeLevels(options = {}) {
        if (!CommonUtils.checkLoginAndHandleExpiry()) return;

        const adjust = options.adjust != null
            ? (options.adjust === 'qfq' ? 'qfq' : 'none')
            : this.selectedAdjust();
        this._pendingAdjust = adjust;

        const codeInput = document.getElementById('kdeLevelsStockCode');
        const calcBtn = document.getElementById('kdeLevelsCalcBtn');
        const resultEl = document.getElementById('kdeLevelsResult');
        const emptyEl = document.getElementById('kdeLevelsEmpty');
        if (!codeInput) return;

        let query = codeInput.value.trim();
        if (!query) {
            CommonUtils.showToast('请输入股票代码或名称', 'warning');
            codeInput.focus();
            return;
        }
        // 「00700 腾讯」/「600519 贵州茅台」：首段为数字代码时取代码（4–6 位，港股可含前导零）
        const firstToken = query.split(/\s+/)[0];
        const firstBody = /^(sh|sz|bj|hk)/i.test(firstToken) ? firstToken.slice(2) : firstToken;
        if (/^\d{4,6}$/.test(firstBody)) {
            query = firstToken;
        }

        if (calcBtn) {
            calcBtn.disabled = true;
            calcBtn.textContent = adjust === 'qfq' ? '获取因子并计算…' : '计算中…';
        }
        this.hideKdeLevelsCandidates();
        if (emptyEl) {
            emptyEl.hidden = false;
            emptyEl.textContent = adjust === 'qfq'
                ? '正在获取复权因子并计算…'
                : '正在计算（不复权）…';
        }
        if (resultEl) resultEl.hidden = true;

        try {
            const factorSourceEl = document.getElementById('kdeLevelsFactorSource');
            const factorSource = (factorSourceEl && factorSourceEl.value) || 'auto';
            const vpParams = this.readVpLookbackParams();
            const kdeParams = this.readKdeLookbackParams();
            const fetched = await this.fetchLevels(query, {
                adjust,
                factor_source: factorSource,
                vp_from_date: vpParams.vp_from_date || undefined,
                vp_lookback: vpParams.vp_from_date ? undefined : (vpParams.vp_lookback != null ? vpParams.vp_lookback : undefined),
                kde_from_date: kdeParams.kde_from_date || undefined,
                kde_lookback: kdeParams.kde_from_date ? undefined : (kdeParams.kde_lookback != null ? kdeParams.kde_lookback : undefined),
            });
            const candidates = fetched.candidates || [];
            if (candidates.length > 1 || (candidates.length > 0 && !fetched.data)) {
                this.renderKdeLevelsCandidates(candidates, fetched.message);
                CommonUtils.showToast(fetched.message || '请从候选中选择股票', 'warning');
                return;
            }
            if (!fetched.httpOk && !fetched.data) {
                throw new Error(fetched.message || '计算失败');
            }
            const data = fetched.data || {};
            if (data.stock_code && codeInput) {
                const name = data.stock_name || '';
                codeInput.value = name ? `${data.stock_code} ${name}` : data.stock_code;
            }
            this.renderKdeLevelsResult(data, fetched.ok, fetched.message);
        } catch (e) {
            console.error('KDE 支撑压力计算失败:', e);
            CommonUtils.showToast(e.message || '计算失败', 'error');
            if (emptyEl) {
                emptyEl.hidden = false;
                emptyEl.textContent = e.message || '计算失败，请稍后重试。';
            }
        } finally {
            if (calcBtn) {
                calcBtn.disabled = false;
                calcBtn.textContent = '计算';
            }
        }
    },

    renderKdeLevelsResult(data, ok, message) {
        const resultEl = document.getElementById('kdeLevelsResult');
        const emptyEl = document.getElementById('kdeLevelsEmpty');
        const summaryEl = document.getElementById('kdeLevelsSummary');
        const metaEl = document.getElementById('kdeLevelsMeta');
        const priceEl = document.getElementById('kdeCurrentPrice');
        const nearS = document.getElementById('kdeNearestSupport');
        const nearR = document.getElementById('kdeNearestResistance');
        const supportList = document.getElementById('kdeSupportList');
        const resistList = document.getElementById('kdeResistanceList');

        this.hideKdeLevelsCandidates();

        const fmt = (v) => (v != null && Number.isFinite(Number(v)) ? Number(v).toFixed(2) : '--');
        const fillList = (ul, values) => {
            if (!ul) return;
            const arr = Array.isArray(values) ? values : [];
            if (!arr.length) {
                ul.innerHTML = '<li class="muted">暂无</li>';
                return;
            }
            ul.innerHTML = arr.map((x, i) => `<li><span class="idx">${i + 1}</span>${fmt(x)}</li>`).join('');
        };
        const fillLabeledList = (ul, rows) => {
            if (!ul) return;
            const arr = Array.isArray(rows) ? rows : [];
            if (!arr.length) {
                ul.innerHTML = '<li class="muted">暂无</li>';
                return;
            }
            ul.innerHTML = arr
                .map((row) => {
                    const label = row.label != null ? String(row.label) : '';
                    return `<li><span class="idx-label">${label}</span>${fmt(row.price)}</li>`;
                })
                .join('');
        };

        const code = data.stock_code || '';
        const name = data.stock_name || '';
        const title = name ? `${code} ${name}` : (code || '结果');
        const adjustBrief = data.price_adjust === 'qfq' ? '前复权' : '不复权';
        if (summaryEl) {
            summaryEl.textContent = ok
                ? `${title} · ${adjustBrief}`
                : `${title} · ${adjustBrief}${message ? `（${message}）` : ''}`;
        }
        if (priceEl) priceEl.textContent = fmt(data.current_price);
        if (nearS) nearS.textContent = fmt(data.nearest_support);
        if (nearR) nearR.textContent = fmt(data.nearest_resistance);
        fillList(supportList, data.support_levels);
        fillList(resistList, data.resistance_levels);

        const kdeInit = data.kde_lookback_initial != null ? data.kde_lookback_initial : 60;
        const kdeUsed = data.kde_lookback_used;
        const kdeMax = data.kde_lookback_max != null ? data.kde_lookback_max : 750;
        const setTxtKde = (id, v) => {
            const el = document.getElementById(id);
            if (el) el.textContent = v;
        };
        setTxtKde('kdeLookbackInitial', kdeInit != null ? String(kdeInit) : '--');
        setTxtKde('kdeLookbackUsed', kdeUsed != null ? String(kdeUsed) : '--');
        setTxtKde('kdeLookbackMax', kdeMax != null ? String(kdeMax) : '750');
        const expandEl = document.getElementById('kdeLookbackExpandText');
        if (expandEl) {
            expandEl.textContent = data.kde_lookback_expanded ? ' · 已扩窗' : '';
        }
        const kdeDaysInput = document.getElementById('kdeLookbackInput');
        if (kdeDaysInput && kdeInit != null) {
            kdeDaysInput.value = String(kdeInit);
        }
        const kdeFromInput = document.getElementById('kdeFromDateInput');
        if (kdeFromInput) {
            const kd = data.kde_from_date || '';
            if (kd) kdeFromInput.value = String(kd).slice(0, 10);
        }

        const vp = data.volume_profile || {};
        const vpCmp = data.vp_vs_kde || {};
        const vpAdjust = vp.price_adjust || data.price_adjust || 'none';
        const vpTag = document.getElementById('kdeVpAdjustTag');
        if (vpTag) {
            vpTag.textContent = vpAdjust === 'qfq' ? '前复权' : '不复权';
            vpTag.className =
                vpAdjust === 'qfq'
                    ? 'kde-levels-adjust-tag is-qfq'
                    : 'kde-levels-adjust-tag is-raw';
        }
        const setTxt = (id, v) => {
            const el = document.getElementById(id);
            if (el) el.textContent = v;
        };
        setTxt('kdeVpPoc', fmt(vp.poc));
        setTxt('kdeVpVal', fmt(vp.val));
        setTxt('kdeVpVah', fmt(vp.vah));
        setTxt(
            'kdeVpNearestSupport',
            this._fmtPriceOrNote(vp.nearest_support, vp.support_note)
        );
        setTxt(
            'kdeVpNearestResistance',
            this._fmtPriceOrNote(vp.nearest_resistance, vp.resistance_note)
        );
        const usedLb = vp.bars_used != null ? vp.bars_used : vp.lookback;
        setTxt('kdeVpLookback', usedLb != null ? String(usedLb) : '--');
        const daysInput = document.getElementById('kdeVpLookbackInput');
        if (daysInput && usedLb != null) {
            daysInput.value = String(usedLb);
        }
        const fromInput = document.getElementById('kdeVpFromDateInput');
        if (fromInput) {
            const start = vp.from_date || vp.window_start || '';
            if (start) fromInput.value = String(start).slice(0, 10);
        }
        const winEl = document.getElementById('kdeVpWindowText');
        if (winEl) {
            const ws = vp.window_start ? String(vp.window_start).slice(0, 10) : '';
            const we = vp.window_end ? String(vp.window_end).slice(0, 10) : '';
            if (ws && we) {
                winEl.textContent = ` · ${ws}～${we}`;
            } else if (ws) {
                winEl.textContent = ` · 自 ${ws}`;
            } else {
                winEl.textContent = '';
            }
        }
        setTxt(
            'kdeVpVaPct',
            vp.value_area_pct != null
                ? `${Math.round(Number(vp.value_area_pct) * 100)}%`
                : '--'
        );
        const fillCmpRow = (prefix, side) => {
            const row = (side === 'support' ? vpCmp.support : vpCmp.resistance) || {};
            setTxt(`kdeVpCmp${prefix}Kde`, fmt(row.kde));
            setTxt(
                `kdeVpCmp${prefix}Vp`,
                this._fmtPriceOrNote(row.vp, row.note)
            );
            if (row.diff == null) {
                setTxt(`kdeVpCmp${prefix}Diff`, '--');
            } else {
                const sign = Number(row.diff) > 0 ? '+' : '';
                const pct =
                    row.diff_pct != null ? `（${Number(row.diff_pct).toFixed(2)}%）` : '';
                setTxt(`kdeVpCmp${prefix}Diff`, `${sign}${fmt(row.diff)}${pct}`);
            }
            const alignEl = document.getElementById(`kdeVpCmp${prefix}Align`);
            if (alignEl) {
                if (row.kde == null || row.vp == null) {
                    alignEl.textContent = row.note ? '语义' : '--';
                    alignEl.className = row.note ? 'muted' : '';
                    if (row.note) alignEl.title = row.note;
                } else if (row.aligned) {
                    alignEl.textContent = '是';
                    alignEl.className = 'is-aligned';
                    alignEl.title = '';
                } else {
                    alignEl.textContent = '否';
                    alignEl.className = 'not-aligned';
                    alignEl.title = '';
                }
            }
        };
        fillCmpRow('Support', 'support');
        fillCmpRow('Resist', 'resistance');
        const cmpNote = document.getElementById('kdeVpCompareNote');
        if (cmpNote) {
            const aligned =
                (vpCmp.support && vpCmp.support.aligned) ||
                (vpCmp.resistance && vpCmp.resistance.aligned);
            cmpNote.textContent = aligned
                ? '存在 KDE↔VP 价位共振（相对偏差 ≤1.5%）；短线仍以 KDE 为主，VP 作辅助确认。'
                : '相对偏差 ≤1.5% 视为价位共振；短线仍以 KDE 为主，VP 作辅助对照。';
        }

        const classic = data.classic_levels || {};
        const fib = classic.fibonacci || null;
        const pivot = classic.pivot || null;
        const cam = classic.camarilla || null;
        const atrPiv = classic.atr_pivot || null;
        const conf =
            classic.confluence_zones ||
            data.confluence_zones ||
            null;
        const classicAdjust = classic.price_adjust || data.price_adjust || 'none';
        const adjustTag = document.getElementById('kdeClassicAdjustTag');
        if (adjustTag) {
            adjustTag.textContent = classicAdjust === 'qfq' ? '前复权' : '不复权';
            adjustTag.className =
                classicAdjust === 'qfq'
                    ? 'kde-levels-adjust-tag is-qfq'
                    : 'kde-levels-adjust-tag is-raw';
        }
        const fibNearS = document.getElementById('kdeFibNearestSupport');
        const fibNearR = document.getElementById('kdeFibNearestResistance');
        const fibDirEl = document.getElementById('kdeFibDirection');
        const fibList = document.getElementById('kdeFibList');
        const pivNearS = document.getElementById('kdePivotNearestSupport');
        const pivNearR = document.getElementById('kdePivotNearestResistance');
        const pivList = document.getElementById('kdePivotList');

        const fibHighEl = document.getElementById('kdeFibSwingHigh');
        const fibLowEl = document.getElementById('kdeFibSwingLow');
        const fibHighDateEl = document.getElementById('kdeFibSwingHighDate');
        const fibLowDateEl = document.getElementById('kdeFibSwingLowDate');
        const fibAnchorEl = document.getElementById('kdeFibAnchorMethod');
        const fibDepthEl = document.getElementById('kdeFibDepthPct');
        if (fibHighEl) fibHighEl.textContent = fmt(fib && fib.swing_high);
        if (fibLowEl) fibLowEl.textContent = fmt(fib && fib.swing_low);
        if (fibHighDateEl) {
            fibHighDateEl.textContent = fib && fib.swing_high_date
                ? `（${fib.swing_high_date}）`
                : '';
        }
        if (fibLowDateEl) {
            fibLowDateEl.textContent = fib && fib.swing_low_date
                ? `（${fib.swing_low_date}）`
                : '';
        }
        if (fibAnchorEl) {
            if ((fib && fib.anchor_method) === 'zigzag_fractal_running') {
                fibAnchorEl.textContent = 'ZigZag+运行高/低';
            } else if ((fib && fib.anchor_method) === 'zigzag_fractal') {
                fibAnchorEl.textContent = 'ZigZag+分形';
            } else {
                fibAnchorEl.textContent =
                    fib && fib.anchor_method ? String(fib.anchor_method) : '--';
            }
        }
        if (fibDepthEl) {
            const bits = [];
            if (fib && fib.depth_pct != null) {
                bits.push(`深度 ${(Number(fib.depth_pct) * 100).toFixed(1)}%`);
            }
            if (fib && fib.bar_span != null) {
                bits.push(`跨度 ${fib.bar_span} 根`);
            }
            if (fib && fib.min_swing_bars != null) {
                bits.push(`≥${fib.min_swing_bars} 根`);
            }
            if (fib && fib.skipped_short_leg) {
                bits.push('已跳过过短波段');
            }
            if (fib && fib.anchor_exceeded) {
                bits.push('已越过确认锚点，按运行极值重算');
            }
            fibDepthEl.textContent = bits.length ? ` · ${bits.join(' · ')}` : '';
        }
        if (fibNearS) {
            fibNearS.textContent = this._fmtPriceOrNote(
                classic.nearest_fib_support,
                classic.fib_support_note || (fib && fib.support_note)
            );
        }
        if (fibNearR) {
            fibNearR.textContent = this._fmtPriceOrNote(
                classic.nearest_fib_resistance,
                classic.fib_resistance_note || (fib && fib.resistance_note)
            );
        }
        if (fibDirEl) {
            const dir = fib && fib.direction;
            fibDirEl.textContent =
                dir === 'up' ? '上升段回撤' : dir === 'down' ? '下降段反弹' : '--';
        }
        const fibRows = [];
        if (fib && Array.isArray(fib.retracements)) {
            fib.retracements.forEach((x) => {
                fibRows.push({ label: String(x.ratio), price: x.price });
            });
        }
        if (fib && fib.nearest_extension) {
            const ext = fib.nearest_extension;
            fibRows.push({
                label: `扩展${ext.ratio != null ? ext.ratio : ''}`,
                price: ext.price,
            });
        }
        fillLabeledList(fibList, fibRows);

        if (pivNearS) {
            pivNearS.textContent = this._fmtPriceOrNote(
                classic.nearest_pivot_support,
                classic.pivot_support_note
            );
        }
        if (pivNearR) {
            pivNearR.textContent = this._fmtPriceOrNote(
                classic.nearest_pivot_resistance,
                classic.pivot_resistance_note
            );
        }
        const pivRows = [];
        if (pivot) {
            ['R3', 'R2', 'R1', 'P', 'S1', 'S2', 'S3'].forEach((k) => {
                if (pivot[k] != null) pivRows.push({ label: k, price: pivot[k] });
            });
        }
        fillLabeledList(pivList, pivRows);

        const camNearS = document.getElementById('kdeCamNearestSupport');
        const camNearR = document.getElementById('kdeCamNearestResistance');
        const camList = document.getElementById('kdeCamList');
        if (camNearS) {
            camNearS.textContent = this._fmtPriceOrNote(
                classic.nearest_cam_support ?? (cam && cam.nearest_support),
                classic.cam_support_note ?? (cam && cam.support_note)
            );
        }
        if (camNearR) {
            camNearR.textContent = this._fmtPriceOrNote(
                classic.nearest_cam_resistance ?? (cam && cam.nearest_resistance),
                classic.cam_resistance_note ?? (cam && cam.resistance_note)
            );
        }
        const camRows = [];
        if (cam) {
            ['R4', 'R3', 'R2', 'R1', 'S1', 'S2', 'S3', 'S4'].forEach((k) => {
                if (cam[k] != null) camRows.push({ label: k, price: cam[k] });
            });
        }
        fillLabeledList(camList, camRows);
        const atrTip = document.getElementById('kdeAtrPivotTip');
        if (atrTip) {
            if (atrPiv && atrPiv.atr != null) {
                atrTip.textContent =
                    `ATR-Pivot：P=${fmt(atrPiv.P)} ±1ATR R1/S1=${fmt(atrPiv.R1)}/${fmt(atrPiv.S1)}` +
                    ` ±2ATR R2/S2=${fmt(atrPiv.R2)}/${fmt(atrPiv.S2)}（ATR=${fmt(atrPiv.atr)}）`;
            } else {
                atrTip.textContent = '';
            }
        }

        const confNearS = document.getElementById('kdeConfNearestSupport');
        const confNearR = document.getElementById('kdeConfNearestResistance');
        const confList = document.getElementById('kdeConfList');
        const nzS = conf && conf.nearest_support_zone;
        const nzR = conf && conf.nearest_resistance_zone;
        if (confNearS) {
            confNearS.textContent = nzS
                ? `${fmt(nzS.center)} [${fmt(nzS.low)}–${fmt(nzS.high)}]`
                : '--';
        }
        if (confNearR) {
            confNearR.textContent = nzR
                ? `${fmt(nzR.center)} [${fmt(nzR.low)}–${fmt(nzR.high)}]`
                : '--';
        }
        const pickStrongOrNearest = (zones, nearest) => {
            const strong = (zones || []).filter((z) => z && z.tier === 'strong');
            if (strong.length) {
                const sorted = strong.slice().sort((a, b) => {
                    const sa = Number(a.strength_adjusted != null ? a.strength_adjusted : a.strength) || 0;
                    const sb = Number(b.strength_adjusted != null ? b.strength_adjusted : b.strength) || 0;
                    return sb - sa;
                });
                return { zone: sorted[0], isStrong: true };
            }
            if (nearest) return { zone: nearest, isStrong: nearest.tier === 'strong' };
            if ((zones || []).length) return { zone: zones[0], isStrong: false };
            return { zone: null, isStrong: false };
        };
        const fillHero = (side, picked) => {
            const badge = document.getElementById(side === 's' ? 'kdeConfHeroSupportBadge' : 'kdeConfHeroResistBadge');
            const price = document.getElementById(side === 's' ? 'kdeConfHeroSupportPrice' : 'kdeConfHeroResistPrice');
            const meta = document.getElementById(side === 's' ? 'kdeConfHeroSupportMeta' : 'kdeConfHeroResistMeta');
            const item = document.getElementById(side === 's' ? 'kdeConfHeroSupport' : 'kdeConfHeroResist');
            const z = picked && picked.zone;
            const sideLab = side === 's' ? '支撑' : '压力';
            if (!z) {
                if (badge) badge.textContent = `共振${sideLab}`;
                if (price) price.textContent = '--';
                if (meta) meta.textContent = '暂无';
                if (item) item.classList.remove('is-strong');
                return;
            }
            const isStrong = !!(picked && picked.isStrong);
            if (badge) {
                badge.textContent = z.label_zh || (isStrong ? `强共振${sideLab}` : `共振${sideLab}`);
                badge.classList.toggle('is-strong', isStrong);
            }
            if (price) price.textContent = `${fmt(z.center)} [${fmt(z.low)}–${fmt(z.high)}]`;
            if (meta) {
                meta.textContent = `强度 ${this._fmtConfluenceStrength(z)} · 来源 ${(z.sources || []).join('+') || '--'}${
                    isStrong ? '' : '（非强共振，取最近带）'
                }`;
            }
            if (item) item.classList.toggle('is-strong', isStrong);
        };
        if (conf && conf.ok) {
            fillHero('s', pickStrongOrNearest(conf.supports, nzS));
            fillHero('r', pickStrongOrNearest(conf.resistances, nzR));
        } else {
            fillHero('s', { zone: null, isStrong: false });
            fillHero('r', { zone: null, isStrong: false });
        }
        const confRows = [];
        // 支撑：center 降序（近现价=支撑1）；压力：center 升序（近现价=压力1）
        const pushZones = (arr, tag, desc) => {
            const sorted = (arr || []).slice().sort((a, b) => {
                const ca = Number(a && a.center);
                const cb = Number(b && b.center);
                if (!Number.isFinite(ca) || !Number.isFinite(cb)) return 0;
                return desc ? cb - ca : ca - cb;
            });
            sorted.forEach((z, i) => {
                const tierBit = z.tier === 'strong' ? '强·' : '';
                const lab = z.label_zh || tag;
                confRows.push({
                    label: `${tierBit}${lab}${i + 1}·强度${this._fmtConfluenceStrength(z)}·${(z.sources || []).join('+')}`,
                    price: z.center,
                });
            });
        };
        if (conf && conf.ok) {
            pushZones(conf.supports, '支撑', true);
            pushZones(conf.resistances, '压力', false);
        }
        fillLabeledList(confList, confRows);

        const expandAllBtn = document.getElementById('kdeLevelsExpandAllBtn');
        const collapseAllBtn = document.getElementById('kdeLevelsCollapseAllBtn');
        const resultRoot = document.getElementById('kdeLevelsResult');
        if (expandAllBtn && resultRoot && !expandAllBtn._kdeBound) {
            expandAllBtn._kdeBound = true;
            expandAllBtn.addEventListener('click', () => {
                resultRoot.querySelectorAll('details.kde-algo-details, details.kde-conf-list-details').forEach((el) => {
                    el.open = true;
                });
            });
        }
        if (collapseAllBtn && resultRoot && !collapseAllBtn._kdeBound) {
            collapseAllBtn._kdeBound = true;
            collapseAllBtn.addEventListener('click', () => {
                resultRoot.querySelectorAll('details.kde-algo-details').forEach((el) => {
                    el.open = false;
                });
            });
        }

        const used = data.kde_lookback_used;
        const expanded = data.kde_lookback_expanded;
        const initLb = data.kde_lookback_initial || 60;
        const maxLb = data.kde_lookback_max || 750;
        const srcMap = {
            akshare_sina_qfq: '新浪（已归一化）',
            baostock_qfq: 'BaoStock',
        };
        const srcText = srcMap[data.adj_factor_source] || data.adj_factor_source || '未知';
        const adjustLabel = data.price_adjust === 'qfq'
            ? `前复权（因子：${srcText}${data.adj_factor_asof ? `，截至 ${data.adj_factor_asof}` : ''}${data.factor_fetched ? '，本次已拉取' : '，已用缓存'}）`
            : '不复权日K';
        const classicLb = classic.lookback || 180;
        const classicBasis = classicAdjust === 'qfq' ? '前复权 OHLC' : '不复权 OHLC';
        const classicNote = classic.ok
            ? `ZigZag Fib / Cam / Pivot ${classicBasis} · 回看 ${classicLb} 日`
            : `Fib/Pivot：${classic.reason || '暂无'}`;
        const confNote =
            conf && conf.ok
                ? `共振带 ${ (conf.supports || []).length + (conf.resistances || []).length } 条`
                : conf
                  ? `共振带：${conf.reason || '暂无'}`
                  : null;
        const vpNote = vp.ok
            ? `VP 回看 ${vp.lookback || 60} 日 · POC ${fmt(vp.poc)}`
            : `VP：${vp.reason || '暂无'}`;
        const parts = [
            adjustLabel,
            data.description || '成交量加权 KDE 支撑 / 压力',
            used != null ? `KDE 实际回看 ${used} 日` : null,
            expanded ? '（已扩窗）' : null,
            `KDE 初始 ${initLb} / 上限 ${maxLb}`,
            vpNote,
            classicNote,
            confNote,
            data.kde_reason ? `KDE 状态：${data.kde_reason}` : null,
        ].filter(Boolean);
        if (metaEl) metaEl.textContent = parts.join(' · ');

        if (emptyEl) emptyEl.hidden = true;
        if (resultEl) resultEl.hidden = false;
    },

};

window.KdeLevelsTool = KdeLevelsTool;

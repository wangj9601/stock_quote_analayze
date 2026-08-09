/** 个股分析：支撑/压力位（KDE + VP + Fib/Cam/共振） */
const KdeLevelsTool = {
    _pendingAdjust: 'none',

    init() {
        const calcBtn = document.getElementById('kdeLevelsCalcBtn');
        const calcQfqBtn = document.getElementById('kdeLevelsCalcQfqBtn');
        const codeInput = document.getElementById('kdeLevelsStockCode');
        const watchSelect = document.getElementById('kdeLevelsWatchlist');
        const vpApplyBtn = document.getElementById('kdeVpLookbackApplyBtn');
        const vpDaysInput = document.getElementById('kdeVpLookbackInput');
        const vpFromInput = document.getElementById('kdeVpFromDateInput');

        if (calcBtn) {
            calcBtn.addEventListener('click', () => this.calculateKdeLevels({ adjust: 'none' }));
        }
        if (calcQfqBtn) {
            calcQfqBtn.addEventListener('click', () => this.calculateKdeLevels({ adjust: 'qfq' }));
        }
        if (codeInput) {
            codeInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.calculateKdeLevels({ adjust: 'none' });
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
                    adjust: this._pendingAdjust || 'none',
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
                        adjust: this._pendingAdjust || 'none',
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
                        adjust: this._pendingAdjust || 'none',
                        preferVpLookback: true,
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
                this.calculateKdeLevels({ adjust: this._pendingAdjust || 'none' });
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

        const adjust = (options.adjust === 'qfq') ? 'qfq' : 'none';
        this._pendingAdjust = adjust;

        const codeInput = document.getElementById('kdeLevelsStockCode');
        const calcBtn = document.getElementById('kdeLevelsCalcBtn');
        const calcQfqBtn = document.getElementById('kdeLevelsCalcQfqBtn');
        const resultEl = document.getElementById('kdeLevelsResult');
        const emptyEl = document.getElementById('kdeLevelsEmpty');
        if (!codeInput) return;

        let query = codeInput.value.trim();
        if (!query) {
            CommonUtils.showToast('请输入股票代码或名称', 'warning');
            codeInput.focus();
            return;
        }
        // 「600519 贵州茅台」类输入：首段为数字代码时取代码
        const firstToken = query.split(/\s+/)[0];
        const firstBody = /^(sh|sz|bj)/i.test(firstToken) ? firstToken.slice(2) : firstToken;
        if (/^\d{4,6}$/.test(firstBody)) {
            query = firstToken;
        }

        if (calcBtn) {
            calcBtn.disabled = true;
            if (adjust === 'none') calcBtn.textContent = '计算中…';
        }
        if (calcQfqBtn) {
            calcQfqBtn.disabled = true;
            if (adjust === 'qfq') calcQfqBtn.textContent = '获取因子并计算…';
        }
        this.hideKdeLevelsCandidates();
        if (emptyEl) {
            emptyEl.hidden = false;
            emptyEl.textContent = adjust === 'qfq'
                ? '正在获取复权因子并计算…'
                : '正在计算…';
        }
        if (resultEl) resultEl.hidden = true;

        try {
            const factorSourceEl = document.getElementById('kdeLevelsFactorSource');
            const factorSource = (factorSourceEl && factorSourceEl.value) || 'auto';
            const qs = new URLSearchParams({
                max_levels: '8',
                adjust,
            });
            if (adjust === 'qfq') {
                qs.set('factor_source', factorSource);
            }
            const vpParams = this.readVpLookbackParams();
            // 有起始日期优先；否则传回看天数（含默认 60）
            if (vpParams.vp_from_date) {
                qs.set('vp_from_date', vpParams.vp_from_date);
            } else if (vpParams.vp_lookback != null) {
                qs.set('vp_lookback', String(vpParams.vp_lookback));
            }
            const url = `${API_BASE_URL}/api/analysis/levels/${encodeURIComponent(query)}?${qs.toString()}`;
            const resp = await authFetch(url);
            const payload = await resp.json().catch(() => ({}));
            const candidates = Array.isArray(payload.candidates) ? payload.candidates : [];
            if (candidates.length > 1 || (candidates.length > 0 && !payload.data)) {
                this.renderKdeLevelsCandidates(candidates, payload.message);
                CommonUtils.showToast(payload.message || '请从候选中选择股票', 'warning');
                return;
            }
            if (!resp.ok && !payload.data) {
                throw new Error(payload.message || '计算失败');
            }
            const data = payload.data || {};
            if (data.stock_code && codeInput) {
                const name = data.stock_name || '';
                codeInput.value = name ? `${data.stock_code} ${name}` : data.stock_code;
            }
            this.renderKdeLevelsResult(data, payload.success !== false, payload.message);
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
            if (calcQfqBtn) {
                calcQfqBtn.disabled = false;
                calcQfqBtn.textContent = '按前复权计算';
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
        if (summaryEl) {
            summaryEl.textContent = ok
                ? title
                : `${title}${message ? `（${message}）` : ''}`;
        }
        if (priceEl) priceEl.textContent = fmt(data.current_price);
        if (nearS) nearS.textContent = fmt(data.nearest_support);
        if (nearR) nearR.textContent = fmt(data.nearest_resistance);
        fillList(supportList, data.support_levels);
        fillList(resistList, data.resistance_levels);

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
        setTxt('kdeVpNearestSupport', fmt(vp.nearest_support));
        setTxt('kdeVpNearestResistance', fmt(vp.nearest_resistance));
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
            setTxt(`kdeVpCmp${prefix}Vp`, fmt(row.vp));
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
                    alignEl.textContent = '--';
                    alignEl.className = '';
                } else if (row.aligned) {
                    alignEl.textContent = '是';
                    alignEl.className = 'is-aligned';
                } else {
                    alignEl.textContent = '否';
                    alignEl.className = 'not-aligned';
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
            fibAnchorEl.textContent =
                (fib && fib.anchor_method) === 'zigzag_fractal'
                    ? 'ZigZag+分形'
                    : fib && fib.anchor_method
                      ? String(fib.anchor_method)
                      : '--';
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
            fibDepthEl.textContent = bits.length ? ` · ${bits.join(' · ')}` : '';
        }
        if (fibNearS) fibNearS.textContent = fmt(classic.nearest_fib_support);
        if (fibNearR) fibNearR.textContent = fmt(classic.nearest_fib_resistance);
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

        if (pivNearS) pivNearS.textContent = fmt(classic.nearest_pivot_support);
        if (pivNearR) pivNearR.textContent = fmt(classic.nearest_pivot_resistance);
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
            camNearS.textContent = fmt(
                classic.nearest_cam_support ?? (cam && cam.nearest_support)
            );
        }
        if (camNearR) {
            camNearR.textContent = fmt(
                classic.nearest_cam_resistance ?? (cam && cam.nearest_resistance)
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
        const confRows = [];
        const pushZones = (arr, tag) => {
            (arr || []).forEach((z, i) => {
                confRows.push({
                    label: `${tag}${i + 1}·强度${z.strength != null ? z.strength : '--'}·${(z.sources || []).join('+')}`,
                    price: z.center,
                });
            });
        };
        if (conf && conf.ok) {
            pushZones(conf.supports, '支撑');
            pushZones(conf.resistances, '压力');
        }
        fillLabeledList(confList, confRows);

        const used = data.kde_lookback_used;
        const expanded = data.kde_lookback_expanded;
        const initLb = data.kde_lookback_initial || 250;
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

// 模拟交易个人中心页面脚本
const ProfilePage = {
    state: {
        dashboard: null,
        positions: [],
        tradingLogs: {
            daily: [],
            weekly: [],
            trade: [],
        },
    },

    async ensureCommonUtils(timeoutMs = 4000) {
        if (typeof window.CommonUtils !== 'undefined') return true;
        // common.js 因网络抖动未加载时尝试补拉一次
        try {
            await new Promise((resolve, reject) => {
                if (document.querySelector('script[src="js/common.js"][data-profile-retry]')) {
                    reject(new Error('common.js 重试已失败'));
                    return;
                }
                const el = document.createElement('script');
                el.src = `js/common.js?t=${Date.now()}`;
                el.setAttribute('data-profile-retry', '1');
                el.onload = resolve;
                el.onerror = () => reject(new Error('common.js 加载失败'));
                document.head.appendChild(el);
            });
        } catch (_) {
            /* fall through to wait/poll */
        }
        const start = Date.now();
        while (typeof window.CommonUtils === 'undefined' && Date.now() - start < timeoutMs) {
            await new Promise((r) => setTimeout(r, 100));
        }
        return typeof window.CommonUtils !== 'undefined';
    },

    async init() {
        try {
            const ok = await this.ensureCommonUtils();
            if (!ok) {
                console.error('个人中心初始化失败: CommonUtils 未加载（请检查网络后刷新）');
                alert('页面公共脚本加载失败，请刷新重试');
                return;
            }
            await CommonUtils.auth.init();
            this.renderUserHeader();
            this.bindTabs();
            this.bindActions();
            this.initTradingLogs();
            await this.loadDashboard();
        } catch (error) {
            console.error('个人中心初始化失败:', error);
            if (typeof CommonUtils !== 'undefined' && CommonUtils.showToast) {
                CommonUtils.showToast('初始化个人中心失败', 'error');
            } else {
                alert('初始化个人中心失败，请刷新重试');
            }
        }
    },

    /** 顶部卡片与设置页展示当前登录用户名 */
    renderUserHeader() {
        const user = CommonUtils.auth.getUserInfo() || {};
        const name =
            (user.username && String(user.username).trim()) ||
            (user.name && String(user.name).trim()) ||
            '';
        const display = name || '未登录';
        const titleEl = document.getElementById('profileUserName');
        if (titleEl) titleEl.textContent = display;
        const avatarEl = document.getElementById('profileAvatarInitial');
        if (avatarEl) {
            const ch = display && display !== '未登录' ? display.charAt(0).toUpperCase() : 'U';
            avatarEl.textContent = ch;
        }
        const settingsUser = document.getElementById('profileSettingsUsername');
        if (settingsUser) settingsUser.value = name || '';
        if (typeof CommonUtils.auth.updateUserDisplay === 'function' && name) {
            CommonUtils.auth.updateUserDisplay(user);
        }
    },

    bindTabs() {
        document.querySelectorAll('.profile-tab').forEach((tab) => {
            tab.addEventListener('click', (event) => {
                event.preventDefault();
                const target = tab.dataset.tab;
                document.querySelectorAll('.profile-tab').forEach((btn) => {
                    btn.classList.toggle('active', btn.dataset.tab === target);
                });
                document.querySelectorAll('.tab-panel').forEach((panel) => {
                    panel.classList.toggle('active', panel.id === target);
                });

                if (target === 'trading-logs') {
                    this.refreshTradingLogs();
                }
                if (target === 'kde-levels') {
                    this.loadKdeWatchlistOptions();
                }
            });
        });
    },

    bindActions() {
        const addPositionBtn = document.querySelector('.add-position-btn');
        if (addPositionBtn) {
            addPositionBtn.addEventListener('click', () => {
                this.showTradeModal();
            });
        }

        // 绑定交易表单事件
        this.bindTradeModal();
        this.bindKdeLevelsTool();
    },

    bindKdeLevelsTool() {
        const calcBtn = document.getElementById('kdeLevelsCalcBtn');
        const calcQfqBtn = document.getElementById('kdeLevelsCalcQfqBtn');
        const codeInput = document.getElementById('kdeLevelsStockCode');
        const watchSelect = document.getElementById('kdeLevelsWatchlist');

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
                this.calculateKdeLevels({ adjust: this._kdeLevelsPendingAdjust || 'none' });
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
        this._kdeLevelsPendingAdjust = adjust;

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
        setTxt('kdeVpLookback', vp.lookback != null ? String(vp.lookback) : '--');
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
            fibDepthEl.textContent =
                fib && fib.depth_pct != null
                    ? ` · 深度 ${(Number(fib.depth_pct) * 100).toFixed(1)}%`
                    : '';
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

    initTradingLogs() {
        this.bindTradingLogTabs();
        this.bindTradingLogForms();
        this.refreshTradingLogs();
    },

    async fetchTradingLogsFromApi(logType) {
        const url = `${API_BASE_URL}/api/trading_notes/journals?log_type=${encodeURIComponent(logType)}`;
        const resp = await authFetch(url);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || err.message || '获取交易日志失败');
        }
        return await resp.json();
    },

    async refreshTradingLogs() {
        if (!CommonUtils.checkLoginAndHandleExpiry()) return;
        try {
            const [daily, weekly, trade] = await Promise.all([
                this.fetchTradingLogsFromApi('daily'),
                this.fetchTradingLogsFromApi('weekly'),
                this.fetchTradeLogsFromApi(),
            ]);
            this.state.tradingLogs.daily = Array.isArray(daily) ? daily : [];
            this.state.tradingLogs.weekly = Array.isArray(weekly) ? weekly : [];
            this.state.tradingLogs.trade = Array.isArray(trade) ? trade : [];
            this.renderTradingLogsFromState();
        } catch (e) {
            console.error('刷新交易日志失败:', e);
            CommonUtils.showToast(e.message || '刷新交易日志失败', 'error');
        }
    },

    bindTradingLogTabs() {
        document.querySelectorAll('.trading-logs-tab').forEach((btn) => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const tab = btn.dataset.logTab;
                document.querySelectorAll('.trading-logs-tab').forEach((b) => {
                    b.classList.toggle('active', b.dataset.logTab === tab);
                });
                document.querySelectorAll('.trading-logs-panel').forEach((panel) => {
                    const isActive = (tab === 'daily' && panel.id === 'trading-logs-daily')
                        || (tab === 'weekly' && panel.id === 'trading-logs-weekly')
                        || (tab === 'trade' && panel.id === 'trading-logs-trade');
                    panel.classList.toggle('active', isActive);
                });
            });
        });
    },

    bindTradingLogForms() {
        const dailyForm = document.getElementById('dailyLogForm');
        const weeklyForm = document.getElementById('weeklyLogForm');
        const dailyResetBtn = document.getElementById('dailyLogResetBtn');
        const weeklyResetBtn = document.getElementById('weeklyLogResetBtn');
        const tradeForm = document.getElementById('tradeLogForm');
        const tradeResetBtn = document.getElementById('tradeLogResetBtn');

        if (dailyForm) {
            dailyForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.saveDailyLog();
            });
        }

        if (weeklyForm) {
            weeklyForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.saveWeeklyLog();
            });
        }

        if (tradeForm) {
            tradeForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.saveTradeLog();
            });
            const stockCodeInput = document.getElementById('tradeLogStockCode');
            if (stockCodeInput) {
                stockCodeInput.addEventListener('blur', () => {
                    this.fetchStockNameForLog(stockCodeInput.value.trim());
                });
            }
        }

        if (dailyResetBtn) {
            dailyResetBtn.addEventListener('click', () => this.resetDailyLogForm());
        }

        if (weeklyResetBtn) {
            weeklyResetBtn.addEventListener('click', () => this.resetWeeklyLogForm());
        }

        if (tradeResetBtn) {
            tradeResetBtn.addEventListener('click', () => this.resetTradeLogForm());
        }
    },

    generateLogId(prefix) {
        return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;
    },

    async saveDailyLog() {
        if (!CommonUtils.checkLoginAndHandleExpiry()) return;

        const idEl = document.getElementById('dailyLogId');
        const dateEl = document.getElementById('dailyLogDate');
        const moodEl = document.getElementById('dailyLogMood');
        const contentEl = document.getElementById('dailyLogContent');

        if (!dateEl || !contentEl) return;

        const date = dateEl.value;
        const content = contentEl.value.trim();
        const mood = moodEl ? moodEl.value : '';
        const id = idEl ? idEl.value : '';

        if (!date) {
            CommonUtils.showToast('请选择日期', 'error');
            dateEl.focus();
            return;
        }
        if (!content) {
            CommonUtils.showToast('请填写复盘要点', 'error');
            contentEl.focus();
            return;
        }

        try {
            if (id) {
                const resp = await authFetch(`${API_BASE_URL}/api/trading_notes/journals/${encodeURIComponent(id)}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mood, content }),
                });
                if (!resp.ok) {
                    const err = await resp.json().catch(() => ({}));
                    throw new Error(err.detail || err.message || '更新失败');
                }
            } else {
                const resp = await authFetch(`${API_BASE_URL}/api/trading_notes/journals/daily`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ log_date: date, mood, content }),
                });
                if (!resp.ok) {
                    const err = await resp.json().catch(() => ({}));
                    throw new Error(err.detail || err.message || '保存失败');
                }
            }

            await this.refreshTradingLogs();
            this.resetDailyLogForm();
            CommonUtils.showToast('每日日志已保存', 'success');
        } catch (e) {
            console.error('保存每日日志失败:', e);
            CommonUtils.showToast(e.message || '保存失败', 'error');
        }
    },

    async saveWeeklyLog() {
        if (!CommonUtils.checkLoginAndHandleExpiry()) return;

        const idEl = document.getElementById('weeklyLogId');
        const startEl = document.getElementById('weeklyLogWeekStart');
        const scoreEl = document.getElementById('weeklyLogScore');
        const contentEl = document.getElementById('weeklyLogContent');

        if (!startEl || !contentEl) return;

        const week_start = startEl.value;
        const content = contentEl.value.trim();
        const score = scoreEl ? scoreEl.value : '';
        const id = idEl ? idEl.value : '';

        if (!week_start) {
            CommonUtils.showToast('请选择周起始日', 'error');
            startEl.focus();
            return;
        }
        if (!content) {
            CommonUtils.showToast('请填写周总结', 'error');
            contentEl.focus();
            return;
        }

        try {
            if (id) {
                const resp = await authFetch(`${API_BASE_URL}/api/trading_notes/journals/${encodeURIComponent(id)}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ score, content }),
                });
                if (!resp.ok) {
                    const err = await resp.json().catch(() => ({}));
                    throw new Error(err.detail || err.message || '更新失败');
                }
            } else {
                const resp = await authFetch(`${API_BASE_URL}/api/trading_notes/journals/weekly`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ week_start, score, content }),
                });
                if (!resp.ok) {
                    const err = await resp.json().catch(() => ({}));
                    throw new Error(err.detail || err.message || '保存失败');
                }
            }

            await this.refreshTradingLogs();
            this.resetWeeklyLogForm();
            CommonUtils.showToast('每周日志已保存', 'success');
        } catch (e) {
            console.error('保存每周日志失败:', e);
            CommonUtils.showToast(e.message || '保存失败', 'error');
        }
    },

    async fetchTradeLogsFromApi() {
        const url = `${API_BASE_URL}/api/trading_notes/trade_logs`;
        const resp = await authFetch(url);
        if (!resp.ok) return [];
        return await resp.json();
    },

    async saveTradeLog() {
        if (!CommonUtils.checkLoginAndHandleExpiry()) return;

        const fields = [
            'tradeLogId', 'tradeLogStockCode', 'tradeLogStockName', 'tradeLogDate',
            'tradeLogBuyPrice', 'tradeLogPositionSize', 'tradeLogStopLoss', 'tradeLogTakeProfit',
            'tradeLogThinking', 'tradeLogMarketContext', 'tradeLogStrictlyExecute',
            'tradeLogEmotionalTrading', 'tradeLogContent', 'tradeLogImageUrl'
        ];
        const data = {};
        fields.forEach(f => {
            const el = document.getElementById(f);
            if (el) data[f] = el.value;
        });

        if (!data.tradeLogStockCode || !data.tradeLogDate) {
            CommonUtils.showToast('股票代码和日期必填', 'error');
            return;
        }

        const payload = {
            stock_code: data.tradeLogStockCode,
            stock_name: data.tradeLogStockName,
            trade_date: data.tradeLogDate,
            buy_price: data.tradeLogBuyPrice ? parseFloat(data.tradeLogBuyPrice) : null,
            position_size: data.tradeLogPositionSize,
            stop_loss: data.tradeLogStopLoss ? parseFloat(data.tradeLogStopLoss) : null,
            take_profit: data.tradeLogTakeProfit ? parseFloat(data.tradeLogTakeProfit) : null,
            entry_thinking: data.tradeLogThinking,
            market_context: data.tradeLogMarketContext,
            strictly_execute: data.tradeLogStrictlyExecute,
            emotional_trading: data.tradeLogEmotionalTrading,
            content: data.tradeLogContent,
            image_url: data.tradeLogImageUrl
        };

        try {
            const id = data.tradeLogId;
            const url = id ? `${API_BASE_URL}/api/trading_notes/trade_logs/${id}` : `${API_BASE_URL}/api/trading_notes/trade_logs`;
            const method = id ? 'PUT' : 'POST';

            const resp = await authFetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            if (!resp.ok) throw new Error('保存失败');

            await this.refreshTradingLogs();
            this.resetTradeLogForm();
            CommonUtils.showToast('记录已保存', 'success');
        } catch (e) {
            CommonUtils.showToast(e.message, 'error');
        }
    },

    resetTradeLogForm() {
        const fields = [
            'tradeLogId', 'tradeLogStockCode', 'tradeLogStockName', 'tradeLogDate',
            'tradeLogBuyPrice', 'tradeLogPositionSize', 'tradeLogStopLoss', 'tradeLogTakeProfit',
            'tradeLogThinking', 'tradeLogMarketContext', 'tradeLogStrictlyExecute',
            'tradeLogEmotionalTrading', 'tradeLogContent', 'tradeLogImageUrl'
        ];
        fields.forEach(f => {
            const el = document.getElementById(f);
            if (el) {
                if (el.tagName === 'SELECT') {
                    el.value = (f === 'tradeLogStrictlyExecute') ? '严格执行' : '无';
                } else {
                    el.value = '';
                }
                if (f === 'tradeLogStockCode' || f === 'tradeLogDate') el.disabled = false;
            }
        });
    },

    async deleteTradeLog(id) {
        if (!confirm('确认删除这条交易记录吗？')) return;
        try {
            const resp = await authFetch(`${API_BASE_URL}/api/trading_notes/trade_logs/${encodeURIComponent(id)}`, { method: 'DELETE' });
            if (!resp.ok) throw new Error('删除失败');
            await this.refreshTradingLogs();
        } catch (e) {
            CommonUtils.showToast(e.message, 'error');
        }
    },

    resetDailyLogForm() {
        const idEl = document.getElementById('dailyLogId');
        const dateEl = document.getElementById('dailyLogDate');
        const moodEl = document.getElementById('dailyLogMood');
        const contentEl = document.getElementById('dailyLogContent');

        if (idEl) idEl.value = '';
        if (dateEl) dateEl.value = '';
        if (dateEl) dateEl.disabled = false;
        if (moodEl) moodEl.value = '';
        if (contentEl) contentEl.value = '';
    },

    resetWeeklyLogForm() {
        const idEl = document.getElementById('weeklyLogId');
        const startEl = document.getElementById('weeklyLogWeekStart');
        const scoreEl = document.getElementById('weeklyLogScore');
        const contentEl = document.getElementById('weeklyLogContent');

        if (idEl) idEl.value = '';
        if (startEl) startEl.value = '';
        if (startEl) startEl.disabled = false;
        if (scoreEl) scoreEl.value = '';
        if (contentEl) contentEl.value = '';
    },

    editDailyLog(id) {
        const record = (this.state.tradingLogs.daily || []).find((x) => String(x.id) === String(id));
        if (!record) return;

        const idEl = document.getElementById('dailyLogId');
        const dateEl = document.getElementById('dailyLogDate');
        const moodEl = document.getElementById('dailyLogMood');
        const contentEl = document.getElementById('dailyLogContent');

        if (idEl) idEl.value = record.id;
        if (dateEl) dateEl.value = record.log_date;
        if (dateEl) dateEl.disabled = true;
        if (moodEl) moodEl.value = record.mood || '';
        if (contentEl) contentEl.value = record.content || '';

        const dailyTab = document.querySelector('.trading-logs-tab[data-log-tab="daily"]');
        if (dailyTab) dailyTab.click();
    },

    editWeeklyLog(id) {
        const record = (this.state.tradingLogs.weekly || []).find((x) => String(x.id) === String(id));
        if (!record) return;

        const idEl = document.getElementById('weeklyLogId');
        const startEl = document.getElementById('weeklyLogWeekStart');
        const scoreEl = document.getElementById('weeklyLogScore');
        const contentEl = document.getElementById('weeklyLogContent');

        if (idEl) idEl.value = record.id;
        if (startEl) startEl.value = record.week_start;
        if (startEl) startEl.disabled = true;
        if (scoreEl) scoreEl.value = record.score || '';
        if (contentEl) contentEl.value = record.content || '';

        const weeklyTab = document.querySelector('.trading-logs-tab[data-log-tab="weekly"]');
        if (weeklyTab) weeklyTab.click();
    },

    editTradeLog(id) {
        const record = (this.state.tradingLogs.trade || []).find((x) => String(x.id) === String(id));
        if (!record) return;

        const fieldMap = {
            tradeLogId: 'id',
            tradeLogStockCode: 'stock_code',
            tradeLogStockName: 'stock_name',
            tradeLogDate: 'trade_date',
            tradeLogBuyPrice: 'buy_price',
            tradeLogPositionSize: 'position_size',
            tradeLogStopLoss: 'stop_loss',
            tradeLogTakeProfit: 'take_profit',
            tradeLogThinking: 'entry_thinking',
            tradeLogMarketContext: 'market_context',
            tradeLogStrictlyExecute: 'strictly_execute',
            tradeLogEmotionalTrading: 'emotional_trading',
            tradeLogContent: 'content',
            tradeLogImageUrl: 'image_url'
        };

        Object.keys(fieldMap).forEach(elId => {
            const el = document.getElementById(elId);
            if (el) {
                el.value = record[fieldMap[elId]] || '';
                if (elId === 'tradeLogStockCode' || elId === 'tradeLogDate') el.disabled = true;
            }
        });

        const tradeTab = document.querySelector('.trading-logs-tab[data-log-tab="trade"]');
        if (tradeTab) tradeTab.click();
    },

    async deleteDailyLog(id) {
        if (!confirm('确认删除这条每日日志吗？')) return;
        try {
            const resp = await authFetch(`${API_BASE_URL}/api/trading_notes/journals/${encodeURIComponent(id)}`, { method: 'DELETE' });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.detail || err.message || '删除失败');
            }
            await this.refreshTradingLogs();
        } catch (e) {
            console.error('删除每日日志失败:', e);
            CommonUtils.showToast(e.message || '删除失败', 'error');
        }
    },

    async deleteWeeklyLog(id) {
        if (!confirm('确认删除这条每周日志吗？')) return;
        try {
            const resp = await authFetch(`${API_BASE_URL}/api/trading_notes/journals/${encodeURIComponent(id)}`, { method: 'DELETE' });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.detail || err.message || '删除失败');
            }
            await this.refreshTradingLogs();
        } catch (e) {
            console.error('删除每周日志失败:', e);
            CommonUtils.showToast(e.message || '删除失败', 'error');
        }
    },

    renderTradingLogsFromState() {
        const dailyContainer = document.getElementById('dailyLogList');
        const weeklyContainer = document.getElementById('weeklyLogList');
        const tradeContainer = document.getElementById('tradeLogList');
        if (!dailyContainer || !weeklyContainer || !tradeContainer) return;

        const daily = (this.state.tradingLogs.daily || []).slice().sort((a, b) => String(b.log_date || '').localeCompare(String(a.log_date || '')));
        const weekly = (this.state.tradingLogs.weekly || []).slice().sort((a, b) => String(b.week_start || '').localeCompare(String(a.week_start || '')));
        const trade = (this.state.tradingLogs.trade || []).slice().sort((a, b) => String(b.trade_date || '').localeCompare(String(a.trade_date || '')));

        dailyContainer.innerHTML = daily.length
            ? daily.map((x) => {
                const moodText = x.mood === 'good' ? '良好' : x.mood === 'normal' ? '一般' : x.mood === 'bad' ? '较差' : '-';
                return `
                    <div class="trading-log-item">
                        <div class="trading-log-meta">
                            <div class="trading-log-title">${x.log_date}</div>
                            <div class="trading-log-sub">情绪：${moodText}</div>
                        </div>
                        <div class="trading-log-content">${this.escapeHtml(x.content || '')}</div>
                        <div class="trading-log-actions">
                            <button class="btn btn-sm btn-secondary" onclick="ProfilePage.editDailyLog('${x.id}')">编辑</button>
                            <button class="btn btn-sm btn-danger" style="margin-left:6px;" onclick="ProfilePage.deleteDailyLog('${x.id}')">删除</button>
                        </div>
                    </div>`;
            }).join('')
            : '<div class="trading-log-item empty">暂无每日日志</div>';

        weeklyContainer.innerHTML = weekly.length
            ? weekly.map((x) => {
                const scoreText = x.score ? `评分：${x.score}` : '评分：-';
                return `
                    <div class="trading-log-item">
                        <div class="trading-log-meta">
                            <div class="trading-log-title">周起始日：${x.week_start}</div>
                            <div class="trading-log-sub">${scoreText}</div>
                        </div>
                        <div class="trading-log-content">${this.escapeHtml(x.content || '')}</div>
                        <div class="trading-log-actions">
                            <button class="btn btn-sm btn-secondary" onclick="ProfilePage.editWeeklyLog('${x.id}')">编辑</button>
                            <button class="btn btn-sm btn-danger" style="margin-left:6px;" onclick="ProfilePage.deleteWeeklyLog('${x.id}')">删除</button>
                        </div>
                    </div>`;
            }).join('')
            : '<div class="trading-log-item empty">暂无每周日志</div>';

        tradeContainer.innerHTML = trade.length
            ? trade.map((x) => {
                const imgThumb = x.image_url ? `<div class="log-image-thumb"><img src="${x.image_url}" onclick="window.open('${x.image_url}')" style="max-width:100px; cursor:pointer; border-radius:4px; margin-top:8px;"></div>` : '';
                return `
                    <div class="trading-log-item detailed-log">
                        <div class="trading-log-meta">
                            <div class="trading-log-title">${x.stock_name || x.stock_code} (${x.stock_code}) - ${x.trade_date}</div>
                            <div class="trading-log-tags">
                                <span class="tag tag-blue">${x.strictly_execute}</span>
                                <span class="tag tag-orange">情绪：${x.emotional_trading}</span>
                            </div>
                        </div>
                        <div class="trading-log-grid">
                            <div class="grid-item"><b>买入价:</b> ${x.buy_price || '--'}</div>
                            <div class="grid-item"><b>仓位:</b> ${x.position_size || '--'}</div>
                            <div class="grid-item"><b>止损:</b> ${x.stop_loss || '--'}</div>
                            <div class="grid-item"><b>止盈:</b> ${x.take_profit || '--'}</div>
                        </div>
                        <div class="trading-log-section">
                            <b>进场思路:</b>
                            <div class="log-text">${this.escapeHtml(x.entry_thinking || '无')}</div>
                        </div>
                        <div class="trading-log-section">
                            <b>反思总结:</b>
                            <div class="log-text">${this.escapeHtml(x.content || '无')}</div>
                        </div>
                        ${imgThumb}
                        <div class="trading-log-actions">
                            <button class="btn btn-sm btn-secondary" onclick="ProfilePage.editTradeLog('${x.id}')">编辑</button>
                            <button class="btn btn-sm btn-danger" style="margin-left:6px;" onclick="ProfilePage.deleteTradeLog('${x.id}')">删除</button>
                        </div>
                    </div>`;
            }).join('')
            : '<div class="trading-log-item empty">暂无单笔交易日志</div>';
    },

    async fetchStockNameForLog(code) {
        if (!code) return;
        const nameInput = document.getElementById('tradeLogStockName');
        if (!nameInput || nameInput.value.trim()) return;
        try {
            const response = await fetch(`${API_BASE_URL}/api/stock/list?query=${encodeURIComponent(code)}&limit=1`);
            const data = await response.json();
            if (data.success && data.data && data.data.length > 0) {
                const stock = data.data[0];
                if (stock.code === code && stock.name) {
                    nameInput.value = stock.name;
                }
            }
        } catch (e) { }
    },

    escapeHtml(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;')
            .replace(/\n/g, '<br>');
    },

    bindTradeModal() {
        const modal = document.getElementById('tradeModal');
        const form = document.getElementById('tradeForm');
        const closeBtn = document.getElementById('tradeModalClose');
        const cancelBtn = document.getElementById('tradeCancelBtn');

        if (!modal || !form) return;

        // 关闭按钮
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.hideTradeModal());
        }

        // 取消按钮
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.hideTradeModal());
        }

        // 点击遮罩关闭
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.hideTradeModal();
            }
        });

        // 表单提交
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleTradeSubmit();
        });

        // 股票代码输入时自动获取股票名称
        const stockCodeInput = document.getElementById('stockCode');
        if (stockCodeInput) {
            stockCodeInput.addEventListener('blur', () => {
                this.fetchStockName(stockCodeInput.value.trim());
            });
        }
    },

    showTradeModal(code = '', name = '', side = 'buy') {
        const modal = document.getElementById('tradeModal');
        const titleEl = document.getElementById('tradeModalTitle');
        const codeInput = document.getElementById('stockCode');
        const nameInput = document.getElementById('stockName');
        const sideSelect = document.getElementById('tradeSide');
        const quantityInput = document.getElementById('quantity');
        const priceInput = document.getElementById('price');
        const remarkInput = document.getElementById('remark');

        if (!modal) return;

        // 设置标题
        if (titleEl) {
            titleEl.textContent = code ? `${side === 'buy' ? '买入' : '卖出'} ${name || code}` : '新增持仓';
        }

        // 填充表单
        if (codeInput) codeInput.value = code;
        if (nameInput) nameInput.value = name;
        if (sideSelect) sideSelect.value = side;
        if (quantityInput) quantityInput.value = '100';
        if (priceInput) priceInput.value = '';
        if (remarkInput) remarkInput.value = '';

        // 如果已有代码，禁用代码输入
        if (codeInput) {
            codeInput.disabled = !!code;
        }

        // 显示模态框
        modal.style.display = 'flex';
    },

    hideTradeModal() {
        const modal = document.getElementById('tradeModal');
        const form = document.getElementById('tradeForm');
        const codeInput = document.getElementById('stockCode');

        if (modal) {
            modal.style.display = 'none';
        }

        if (form) {
            form.reset();
        }

        // 恢复代码输入框
        if (codeInput) {
            codeInput.disabled = false;
        }
    },

    async fetchStockName(code) {
        if (!code) return;

        const nameInput = document.getElementById('stockName');
        if (!nameInput || nameInput.value.trim()) return; // 如果已有名称则不自动获取

        try {
            // 尝试从本地缓存获取
            const cached = localStorage.getItem('stockBasicInfo');
            if (cached) {
                const stocks = JSON.parse(cached);
                const stock = stocks.find(s => String(s.code) === code);
                if (stock && stock.name) {
                    nameInput.value = stock.name;
                    return;
                }
            }

            // 从API获取
            const response = await fetch(`${API_BASE_URL}/api/stock/list?query=${encodeURIComponent(code)}&limit=1`);
            const data = await response.json();
            if (data.success && data.data && data.data.length > 0) {
                const stock = data.data[0];
                if (stock.code === code && stock.name) {
                    nameInput.value = stock.name;
                }
            }
        } catch (error) {
            console.error('获取股票名称失败:', error);
        }
    },

    async handleTradeSubmit() {
        if (!CommonUtils.checkLoginAndHandleExpiry()) {
            return;
        }

        const codeInput = document.getElementById('stockCode');
        const nameInput = document.getElementById('stockName');
        const sideSelect = document.getElementById('tradeSide');
        const quantityInput = document.getElementById('quantity');
        const priceInput = document.getElementById('price');
        const remarkInput = document.getElementById('remark');
        const submitBtn = document.getElementById('tradeSubmitBtn');

        if (!codeInput || !sideSelect || !quantityInput) {
            CommonUtils.showToast('表单数据不完整', 'error');
            return;
        }

        const stockCode = codeInput.value.trim().toUpperCase();
        const stockName = nameInput.value.trim();
        const side = sideSelect.value;
        const quantity = parseInt(quantityInput.value, 10);
        const priceValue = priceInput.value.trim();
        const remark = remarkInput.value.trim();

        // 验证
        if (!stockCode) {
            CommonUtils.showToast('请输入股票代码', 'error');
            codeInput.focus();
            return;
        }

        if (!quantity || quantity <= 0) {
            CommonUtils.showToast('请输入正确的交易数量', 'error');
            quantityInput.focus();
            return;
        }

        if (quantity % 100 !== 0) {
            CommonUtils.showToast('交易数量必须是100的整数倍', 'error');
            quantityInput.focus();
            return;
        }

        let price = null;
        if (priceValue) {
            const parsed = parseFloat(priceValue);
            if (Number.isNaN(parsed) || parsed <= 0) {
                CommonUtils.showToast('请输入正确的价格', 'error');
                priceInput.focus();
                return;
            }
            price = parsed;
        }

        // 禁用提交按钮
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = '提交中...';
        }

        try {
            const payload = {
                stock_code: stockCode,
                stock_name: stockName || stockCode,
                side,
                quantity,
            };

            if (price !== null) {
                payload.price = price;
            }

            if (remark) {
                payload.remark = remark;
            }

            const label = side === 'sell' ? '卖出' : '买入';
            await this.submitSimTradeOrder(payload, `${label}指令已提交`);
            this.hideTradeModal();
        } catch (error) {
            console.error('交易提交失败:', error);
        } finally {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = '确认交易';
            }
        }
    },

    async loadDashboard() {
        try {
            const response = await authFetch(`${API_BASE_URL}/api/simtrade/dashboard`);
            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail || error.message || '加载失败');
            }
            this.state.dashboard = await response.json();
            this.renderDashboard();
        } catch (error) {
            console.error('加载模拟交易数据失败:', error);
            CommonUtils.showToast('加载模拟交易数据失败', 'error');
        }
    },

    renderDashboard() {
        if (!this.state.dashboard) {
            return;
        }

        const { account, positions, recent_orders: orders } = this.state.dashboard;

        this.state.positions = positions || [];
        this.updateAccountSummary(account);
        this.renderPositions(this.state.positions);
        this.renderTransactions(orders || []);
        this.renderRecentTrades(orders || []);
        this.updateProfileStats(this.state.positions, orders || []);
        this.drawPortfolioChart(this.state.positions);
    },

    updateAccountSummary(account) {
        const totalAssets = account?.total_assets || 0;
        const marketValue = account?.total_market_value || 0;
        const cashBalance = account?.cash_balance || 0;
        const totalProfit = account?.total_profit || 0;
        const totalProfitRate = account?.total_profit_rate || 0;

        this.setText('totalAssetsDisplay', this.formatCurrency(totalAssets));
        this.setText('marketValueDisplay', this.formatCurrency(marketValue));
        this.setText('cashBalanceDisplay', this.formatCurrency(cashBalance));

        const marketPercent = totalAssets > 0 ? (marketValue / totalAssets) * 100 : 0;
        const cashPercent = totalAssets > 0 ? (cashBalance / totalAssets) * 100 : 0;
        this.setText('marketValuePercent', this.formatPercent(marketPercent));
        this.setText('cashBalancePercent', this.formatPercent(cashPercent));

        this.setText('todayProfitValue', this.formatCurrency(0));
        this.setText('todayProfitPercent', this.formatPercent(0));
        this.setText('totalProfitValue', this.formatCurrency(totalProfit, true));
        this.setText('totalProfitPercent', this.formatPercent(totalProfitRate));
        this.setText('annualizedReturnValue', this.formatPercent(totalProfitRate));
        this.setText('annualizedReturnHint', '模拟账户');

        this.updateProfitClasses('todayProfitValue', 'todayProfitPercent', 0);
        this.updateProfitClasses('totalProfitValue', 'totalProfitPercent', totalProfit);
    },

    renderPositions(positions) {
        const container = document.getElementById('positionsTableBody');
        if (!container) return;

        if (!positions.length) {
            container.innerHTML = `
                <tr>
                    <td colspan="8" style="text-align:center; color:#6b7280; padding:16px;">
                        暂无持仓，前往 <a href="markets.html" style="color:#2563eb;">行情中心</a> 模拟交易
                    </td>
                </tr>`;
            return;
        }

        container.innerHTML = positions.map((position) => {
            const profit = position.unrealized_profit || 0;
            const profitPercent = position.unrealized_percent || 0;
            const profitClass = this.getProfitClass(profit);
            return `
                <tr>
                    <td>
                        <div class="stock-info">
                            <span class="stock-name">${position.stock_name || position.stock_code}</span>
                            <span class="stock-code">${position.stock_code}</span>
                        </div>
                    </td>
                    <td>${this.formatShares(position.quantity)}</td>
                    <td>${this.formatPrice(position.avg_price)}</td>
                    <td>${this.formatPrice(position.last_price)}</td>
                    <td>${this.formatCurrency(position.market_value)}</td>
                    <td class="${profitClass}">${this.formatCurrency(profit, true)}</td>
                    <td class="${profitClass}">${this.formatPercent(profitPercent)}</td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="ProfilePage.quickTrade('${position.stock_code}', '${position.stock_name || ''}', 'buy')">买入</button>
                        <button class="btn btn-sm btn-danger" style="margin-left:6px;" onclick="ProfilePage.quickTrade('${position.stock_code}', '${position.stock_name || ''}', 'sell')">卖出</button>
                    </td>
                </tr>`;
        }).join('');
    },

    renderTransactions(orders) {
        const container = document.getElementById('transactionsList');
        if (!container) return;

        if (!orders.length) {
            container.innerHTML = '<div class="transaction-item empty">暂无交易记录</div>';
            return;
        }

        container.innerHTML = orders.map((order) => {
            const typeClass = order.side === 'sell' ? 'sell' : 'buy';
            return `
                <div class="transaction-item">
                    <div class="transaction-date">${this.formatDateTime(order.created_at)}</div>
                    <div class="transaction-stock">
                        <span class="stock-name">${order.stock_name || order.stock_code}</span>
                        <span class="stock-code">${order.stock_code}</span>
                    </div>
                    <div class="transaction-type ${typeClass}">${order.side === 'sell' ? '卖出' : '买入'}</div>
                    <div class="transaction-details">
                        <span class="quantity">${this.formatShares(order.quantity)}</span>
                        <span class="price">${this.formatPrice(order.price)}</span>
                        <span class="amount">${this.formatCurrency(order.amount)}</span>
                    </div>
                    <div class="transaction-status success">${order.status === 'filled' ? '已成交' : order.status}</div>
                </div>`;
        }).join('');
    },

    renderRecentTrades(orders) {
        const container = document.getElementById('recentTradesList');
        if (!container) return;

        if (!orders.length) {
            container.innerHTML = '<div class="trade-item empty">暂无近期交易</div>';
            return;
        }

        container.innerHTML = orders.slice(0, 5).map((order) => {
            const actionClass = order.side === 'sell' ? 'sell' : 'buy';
            return `
                <div class="trade-item">
                    <div class="trade-stock">
                        <span class="stock-name">${order.stock_name || order.stock_code}</span>
                        <span class="stock-code">${order.stock_code}</span>
                    </div>
                    <div class="trade-action ${actionClass}">${order.side === 'sell' ? '卖出' : '买入'}</div>
                    <div class="trade-amount">${this.formatShares(order.quantity)}</div>
                    <div class="trade-time">${this.formatRelativeTime(order.created_at)}</div>
                </div>`;
        }).join('');
    },

    async submitSimTradeOrder(payload, successMessage) {
        try {
            const response = await authFetch(`${API_BASE_URL}/api/simtrade/orders`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
            });

            const result = await response.json().catch(() => ({}));

            if (!response.ok) {
                throw new Error(result.detail || result.message || '下单失败');
            }

            CommonUtils.showToast(successMessage, 'success');
            this.state.dashboard = result;
            this.renderDashboard();
        } catch (error) {
            console.error('模拟交易下单失败:', error);
            CommonUtils.showToast(error.message || '模拟交易下单失败', 'error');
        }
    },

    async quickTrade(code, name, side) {
        if (!CommonUtils.checkLoginAndHandleExpiry()) {
            return;
        }
        this.showTradeModal(code, name, side);
    },

    async createNewPosition() {
        if (!CommonUtils.checkLoginAndHandleExpiry()) {
            return;
        }
        this.showTradeModal();
    },

    updateProfileStats(positions, orders) {
        const usageDaysEl = document.getElementById('profileUsageDays');
        const watchlistCountEl = document.getElementById('profileWatchlistCount');
        const infoCountEl = document.getElementById('profileInfoCount');

        if (usageDaysEl) {
            const userInfo = CommonUtils.auth.getUserInfo();
            if (userInfo && userInfo.created_at) {
                const start = new Date(userInfo.created_at);
                const diff = Math.max(1, Math.ceil((Date.now() - start.getTime()) / 86400000));
                usageDaysEl.textContent = diff;
            } else {
                usageDaysEl.textContent = '--';
            }
        }

        if (watchlistCountEl) {
            watchlistCountEl.textContent = positions.length;
        }

        if (infoCountEl) {
            infoCountEl.textContent = orders.length;
        }
    },

    drawPortfolioChart(positions) {
        const canvas = document.getElementById('portfolioChart');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;
        const centerX = width / 2;
        const centerY = height / 2;
        const radius = Math.min(width, height) / 2 - 10;

        ctx.clearRect(0, 0, width, height);

        const data = (positions || [])
            .map((pos) => ({ label: pos.stock_name || pos.stock_code, value: pos.market_value || 0 }))
            .filter((item) => item.value > 0);

        if (!data.length) {
            ctx.fillStyle = '#9ca3af';
            ctx.font = '14px "Microsoft YaHei"';
            ctx.textAlign = 'center';
            ctx.fillText('暂无持仓', centerX, centerY);
            return;
        }

        const total = data.reduce((sum, item) => sum + item.value, 0);
        let currentAngle = -Math.PI / 2;
        const palette = ['#2563eb', '#16a34a', '#f59e0b', '#dc2626', '#6b7280'];

        data.forEach((item, index) => {
            const sliceAngle = (item.value / total) * Math.PI * 2;
            ctx.beginPath();
            ctx.moveTo(centerX, centerY);
            ctx.fillStyle = palette[index % palette.length];
            ctx.arc(centerX, centerY, radius, currentAngle, currentAngle + sliceAngle);
            ctx.closePath();
            ctx.fill();
            currentAngle += sliceAngle;
        });

        ctx.beginPath();
        ctx.arc(centerX, centerY, radius * 0.55, 0, Math.PI * 2);
        ctx.fillStyle = '#fff';
        ctx.fill();

        ctx.fillStyle = '#1f2937';
        ctx.font = 'bold 14px "Microsoft YaHei"';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('持仓分布', centerX, centerY);
    },

    updateProfitClasses(valueId, percentId, profit) {
        const cls = this.getProfitClass(profit);
        const valueEl = document.getElementById(valueId);
        const percentEl = document.getElementById(percentId);
        if (valueEl) valueEl.className = `performance-value ${cls}`;
        if (percentEl) percentEl.className = `performance-percent ${cls}`;
    },

    getProfitClass(value) {
        if (value > 0) return 'positive';
        if (value < 0) return 'negative';
        return 'neutral';
    },

    setText(id, text) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = text;
        }
    },

    formatCurrency(value, withSign = false) {
        const num = Number(value) || 0;
        const sign = withSign ? (num > 0 ? '+' : '') : '';
        return `${sign}¥${num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    },

    formatPercent(value) {
        const num = Number(value) || 0;
        const sign = num > 0 ? '+' : '';
        return `${sign}${num.toFixed(2)}%`;
    },

    formatPrice(value) {
        const num = Number(value);
        if (Number.isNaN(num)) return '--';
        return `¥${num.toFixed(2)}`;
    },

    formatShares(value) {
        const num = Number(value) || 0;
        return `${num.toLocaleString()}股`;
    },

    formatDateTime(value) {
        if (!value) return '--';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;
        return date.toLocaleString('zh-CN', { hour12: false });
    },

    formatRelativeTime(value) {
        if (!value) return '--';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;

        const diff = Date.now() - date.getTime();
        if (diff < 60000) return '刚刚';
        if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
        return `${Math.floor(diff / 86400000)} 天前`;
    },
};

document.addEventListener('DOMContentLoaded', () => {
    ProfilePage.init();
});

// 导出到全局作用域，以便 onclick 事件可以访问
window.ProfilePage = ProfilePage; 
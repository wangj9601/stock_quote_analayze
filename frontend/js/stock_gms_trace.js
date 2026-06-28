/**
 * GMS 信号追溯页面
 */
class StockGMSTracePage {
    constructor() {
        this.currentPage = 1;
        this.pageSize = 30;
        this.totalPages = 0;
        this.currentStockCode = '';
        this.currentStockName = '';
        this.allData = [];
        this.backtestPollTimer = null;
        this.backtestPollCount = 0;
        this.backtestTaskId = '';
        this.maxBacktestPolls = 900;
        this.traceConfigId = null;
        this.traceConfigOptions = [];
        /** 当前策略版本摘要（得分明细展示，与选股页一致） */
        this.gmsConfigMeta = null;
        this.forceComputeRunning = false;
        this.forceComputePollTimer = null;
        this.forceComputeTaskId = '';
        this.forceComputePollCount = 0;
        this.maxForceComputePolls = 3600;
        this.init();
    }

    init() {
        this.loadFromUrl();
        this.bindEvents();
        this.setDefaultDates();
    }

    loadFromUrl() {
        const params = new URLSearchParams(window.location.search);
        this.currentStockCode = params.get('code') || '';
        this.currentStockName = params.get('name') || '';
        document.getElementById('stockDisplay').textContent =
            this.currentStockCode ? `${this.currentStockCode} ${decodeURIComponent(this.currentStockName || '')}` : '--';
        const marketSel = document.getElementById('btMarket');
        if (marketSel && this.currentStockCode) {
            if (this.isAShareCode(this.currentStockCode)) marketSel.value = 'cn';
            else if (this.isETFCode(this.currentStockCode)) marketSel.value = 'etf';
            else marketSel.value = 'hk';
        }
        if (this.currentStockCode) {
            this.fetchData();
        }
    }

    isAShareCode(code) {
        const s = String(code || '').trim();
        return s.length >= 6 && /^\d+$/.test(s) && '6039'.includes(s[0]);
    }

    isETFCode(code) {
        const s = String(code || '').trim();
        return s.length >= 6 && /^\d+$/.test(s) && '518'.includes(s[0]);
    }

    bindEvents() {
        document.getElementById('searchBtn').addEventListener('click', () => {
            if (this.forceComputeRunning) return;
            this.fetchData();
        });
        document.getElementById('forceComputeBtn').addEventListener('click', () => this.forceCompute());
        document.getElementById('firstPage').addEventListener('click', () => this.goToPage(1));
        document.getElementById('prevPage').addEventListener('click', () => this.goToPage(this.currentPage - 1));
        document.getElementById('nextPage').addEventListener('click', () => this.goToPage(this.currentPage + 1));
        document.getElementById('lastPage').addEventListener('click', () => this.goToPage(this.totalPages));
        // 得分明细：点击展开/收起（事件委托）
        const tbody = document.getElementById('traceTable')?.querySelector('tbody');
        if (tbody) {
            tbody.addEventListener('click', (e) => {
                const btn = e.target.closest('.gms-score-detail-toggle');
                if (!btn) return;
                const rowIndex = parseInt(btn.getAttribute('data-row'), 10);
                const detailRow = tbody.querySelector(`tr.gms-score-detail-row[data-detail-for="${rowIndex}"]`);
                if (detailRow) detailRow.style.display = detailRow.style.display === 'none' ? '' : 'none';
            });
        }
        const startBt = document.getElementById('btStartBtn');
        const cancelBt = document.getElementById('btCancelBtn');
        if (startBt) startBt.addEventListener('click', () => this.startBacktest());
        if (cancelBt) cancelBt.addEventListener('click', () => this.cancelBacktest());
        const quickSel = document.getElementById('btTargetPctQuick');
        const pctIn = document.getElementById('btTargetPct');
        if (quickSel && pctIn) {
            quickSel.addEventListener('change', () => {
                const v = quickSel.value;
                if (v !== '' && v != null) pctIn.value = String(v);
            });
        }
    }

    setDefaultDates() {
        const today = new Date();
        const threeMonthsAgo = new Date(today.getTime() - 90 * 24 * 60 * 60 * 1000);
        document.getElementById('startDate').value = this.formatDate(threeMonthsAgo);
        document.getElementById('endDate').value = this.formatDate(today);
    }

    formatDate(d) {
        return d.toISOString().slice(0, 10);
    }

    getApiBase() {
        let base = (typeof Config !== 'undefined' && Config.getApiBaseUrl)
            ? (Config.getApiBaseUrl() || '')
            : '';
        base = String(base).trim();
        // 兼容异常配置 ":5000" 这类不完整地址，自动补全为当前协议+主机
        if (base.startsWith(':')) {
            const protocol = window.location.protocol || 'http:';
            const host = window.location.hostname || 'localhost';
            base = `${protocol}//${host}${base}`;
        }
        if (!base) return '';
        return base.replace(/\/+$/, '');
    }

    async fetchData(forceCompute = false) {
        if (!this.currentStockCode) {
            alert('请先选择股票');
            return;
        }
        const startDate = document.getElementById('startDate').value;
        const endDate = document.getElementById('endDate').value;
        const loading = document.getElementById('loadingMsg');
        const empty = document.getElementById('emptyMsg');
        loading.style.display = 'block';
        empty.style.display = 'none';
        if (!forceCompute) {
            loading.textContent = '正在加载 GMS 信号追溯，请稍候…';
        }

        let url = `${this.getApiBase()}/api/stock/gms-signal-trace?code=${encodeURIComponent(this.currentStockCode)}`;
        if (startDate) url += `&start_date=${startDate}`;
        if (endDate) url += `&end_date=${endDate}`;
        if (forceCompute) {
            this.syncActiveConfigFromTabs();
            url += '&force_compute=1';
        }
        if (this.traceConfigId != null && this.traceConfigId !== '') {
            url += `&config_id=${encodeURIComponent(String(this.traceConfigId))}`;
        }

        try {
            const resp = await fetch(url);
            const json = await resp.json();
            loading.style.display = 'none';
            if (!json.success) {
                this.allData = [];
                document.getElementById('traceTable').querySelector('tbody').innerHTML =
                    '<tr><td colspan="13">加载失败: ' + (json.message || '未知错误') + '</td></tr>';
                return;
            }
            this.traceConfigOptions = Array.isArray(json.configs) ? json.configs : [];
            if (json.config_id != null) {
                this.traceConfigId = json.config_id;
            }
            if (json.gms_config_meta && typeof json.gms_config_meta === 'object') {
                this.gmsConfigMeta = json.gms_config_meta;
            } else {
                const cfgName = json.config_name || this.getActiveConfigLabel();
                this.gmsConfigMeta = {
                    strategy_config_id: json.config_id || this.traceConfigId,
                    strategy_config_name: cfgName,
                    scoring_mechanism: '',
                    scoring_mechanism_label: '',
                };
            }
            this.renderConfigTabs();
            this.allData = json.data || [];
            if (json.message && !forceCompute) {
                empty.textContent = json.message;
                empty.style.display = this.allData.length === 0 ? 'block' : 'none';
            } else if (!json.message) {
                empty.style.display = this.allData.length === 0 ? 'block' : 'none';
            }
            this.totalPages = Math.max(1, Math.ceil(this.allData.length / this.pageSize));
            this.currentPage = 1;
            this.renderTable();
            this.updatePagination();
        } catch (e) {
            loading.style.display = 'none';
            document.getElementById('traceTable').querySelector('tbody').innerHTML =
                '<tr><td colspan="13">请求失败: ' + e.message + '</td></tr>';
        }
    }

    forceCompute() {
        if (this.forceComputeRunning) return;
        this.syncActiveConfigFromTabs();
        const label = this.getActiveConfigLabel();
        if (!confirm(`将按「${label}」重新计算该股全部交易日的 GMS 信号（仅影响该策略版本），是否继续？`)) {
            return;
        }
        void this.startForceComputeTask();
    }

    clearForceComputePoll() {
        if (this.forceComputePollTimer) {
            clearInterval(this.forceComputePollTimer);
            this.forceComputePollTimer = null;
        }
        this.forceComputePollCount = 0;
    }

    setForceComputeRunning(running) {
        this.forceComputeRunning = !!running;
        const btn = document.getElementById('forceComputeBtn');
        const searchBtn = document.getElementById('searchBtn');
        if (btn) {
            btn.disabled = this.forceComputeRunning;
            btn.textContent = this.forceComputeRunning ? '正在重新计算…' : '强制重新计算';
        }
        if (searchBtn) searchBtn.disabled = this.forceComputeRunning;
        const tabs = document.getElementById('gmsTraceConfigTabs');
        if (tabs) {
            tabs.querySelectorAll('[data-config-id]').forEach((el) => {
                el.disabled = this.forceComputeRunning;
            });
        }
    }

    renderForceComputeProgress(task) {
        const area = document.getElementById('forceComputeProgress');
        if (!area) return;
        area.style.display = 'block';
        const pct = task.progress != null ? Math.min(100, Math.max(0, Number(task.progress))) : 0;
        const msg = task.message || '';
        const total = task.total != null && task.total > 0
            ? ` · ${task.current || 0}/${task.total}`
            : '';
        const statusLabel = task.status === 'completed' ? '已完成'
            : (task.status === 'failed' ? '失败' : '计算中');
        area.innerHTML = `
            <div>GMS 信号重算: <strong>${escapeHtml(statusLabel)}</strong>${msg ? ` · ${escapeHtml(String(msg))}${total}` : ''}</div>
            <div class="bt-progress-bar"><div class="bt-progress-bar-inner" style="width:${pct}%"></div></div>
        `;
    }

    async startForceComputeTask() {
        if (!this.currentStockCode) {
            alert('请先选择股票');
            return;
        }
        this.clearForceComputePoll();
        this.setForceComputeRunning(true);
        const area = document.getElementById('forceComputeProgress');
        if (area) {
            area.style.display = 'block';
            area.innerHTML = '<div>正在提交重算任务…</div><div class="bt-progress-bar"><div class="bt-progress-bar-inner" style="width:5%"></div></div>';
        }
        const loading = document.getElementById('loadingMsg');
        if (loading) loading.style.display = 'none';

        const url = `${this.getApiBase()}/api/stock/gms-signal-trace/recompute`;
        try {
            const resp = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    code: this.currentStockCode,
                    config_id: this.traceConfigId,
                }),
            });
            const json = await resp.json().catch(() => ({}));
            if (!resp.ok || !json.success) {
                throw new Error(json.message || json.detail || resp.statusText || '提交失败');
            }
            this.forceComputeTaskId = json.data?.task_id || '';
            if (!this.forceComputeTaskId) {
                throw new Error('未返回任务 ID');
            }
            if (json.data?.already_running) {
                this.renderForceComputeProgress({
                    status: 'running',
                    progress: 0,
                    message: json.message || '任务进行中',
                });
            }
            await this.pollForceComputeOnce();
            this.forceComputePollTimer = setInterval(() => this.pollForceComputeOnce(), 1000);
        } catch (e) {
            this.clearForceComputePoll();
            this.setForceComputeRunning(false);
            if (area) {
                area.style.display = 'block';
                area.innerHTML = `<span class="gms-recompute-error">提交失败: ${escapeHtml(e.message || String(e))}</span>`;
            }
        }
    }

    async pollForceComputeOnce() {
        if (!this.forceComputeTaskId) return;
        this.forceComputePollCount += 1;
        if (this.forceComputePollCount > this.maxForceComputePolls) {
            this.clearForceComputePoll();
            this.setForceComputeRunning(false);
            const area = document.getElementById('forceComputeProgress');
            if (area) {
                area.innerHTML = '<span class="gms-recompute-error">等待超时，请刷新页面后重试</span>';
            }
            return;
        }
        const url = `${this.getApiBase()}/api/stock/gms-signal-trace/recompute/${encodeURIComponent(this.forceComputeTaskId)}`;
        try {
            const resp = await fetch(url);
            const json = await resp.json().catch(() => ({}));
            if (!resp.ok || !json.success) {
                throw new Error(json.detail || json.message || resp.statusText);
            }
            const task = json.data;
            if (!task) return;
            this.renderForceComputeProgress(task);
            const st = task.status;
            if (st === 'completed' || st === 'failed') {
                this.clearForceComputePoll();
                this.setForceComputeRunning(false);
                if (st === 'completed') {
                    if (window.CommonUtils && task.message) {
                        CommonUtils.showToast(task.message, 'success');
                    }
                    await this.fetchData(false);
                    const area = document.getElementById('forceComputeProgress');
                    if (area && task.message) {
                        area.style.display = 'block';
                        this.renderForceComputeProgress({ ...task, progress: 100 });
                    }
                } else {
                    const area = document.getElementById('forceComputeProgress');
                    if (area) {
                        area.innerHTML = `<span class="gms-recompute-error">${escapeHtml(task.error || task.message || '计算失败')}</span>`;
                    }
                }
            }
        } catch (e) {
            this.clearForceComputePoll();
            this.setForceComputeRunning(false);
            const area = document.getElementById('forceComputeProgress');
            if (area) {
                area.innerHTML = `<span class="gms-recompute-error">查询进度失败: ${escapeHtml(e.message || String(e))}</span>`;
            }
        }
    }

    syncActiveConfigFromTabs() {
        const active = document.querySelector('#gmsTraceConfigTabs .gms-trace-config-tab.active');
        if (active) {
            const cid = parseInt(active.getAttribute('data-config-id'), 10);
            if (cid) this.traceConfigId = cid;
            return;
        }
        if (this.traceConfigId == null && this.traceConfigOptions.length) {
            const def = this.traceConfigOptions.find((o) => o.is_default) || this.traceConfigOptions[0];
            if (def) this.traceConfigId = def.config_id;
        }
    }

    getActiveConfigLabel() {
        const opt = (this.traceConfigOptions || []).find(
            (o) => String(o.config_id) === String(this.traceConfigId),
        );
        return opt ? (opt.display_name || opt.name || `配置${opt.config_id}`) : '当前策略版本';
    }

    renderConfigTabs() {
        const wrap = document.getElementById('gmsTraceConfigTabs');
        if (!wrap) return;
        const options = this.traceConfigOptions || [];
        if (options.length <= 1) {
            wrap.style.display = 'none';
            wrap.innerHTML = '';
            return;
        }
        wrap.style.display = 'flex';
        const activeId = this.traceConfigId;
        wrap.innerHTML = options.map((opt) => {
            const id = opt.config_id;
            const label = escapeHtml(opt.display_name || opt.name || `配置${id}`);
            const cnt = opt.record_count != null ? ` (${opt.record_count})` : '';
            const cls = String(id) === String(activeId) ? 'gms-trace-config-tab active' : 'gms-trace-config-tab';
            return `<button type="button" class="${cls}" data-config-id="${id}">${label}${cnt}</button>`;
        }).join('') + '<span class="gms-trace-config-tab-hint">切换版本查看；「强制重新计算」仅重算当前选中版本</span>';
        wrap.querySelectorAll('[data-config-id]').forEach((btn) => {
            btn.addEventListener('click', () => {
                if (this.forceComputeRunning) return;
                const cid = parseInt(btn.getAttribute('data-config-id'), 10);
                if (!cid || String(cid) === String(this.traceConfigId)) return;
                this.traceConfigId = cid;
                this.currentPage = 1;
                void this.fetchData(false);
            });
        });
    }

    fmtPct(v) {
        if (v == null || (typeof v === 'number' && isNaN(v))) return '--';
        return (v * 100).toFixed(2) + '%';
    }

    fmtNum(v) {
        if (v == null || (typeof v === 'number' && isNaN(v))) return '--';
        return typeof v === 'number' ? v.toFixed(4) : String(v);
    }

    /** 得分明细：分数 + 等级（若有） */
    fmtScoreDetail(score, grade) {
        if (score == null || (typeof score === 'number' && isNaN(score))) return '--';
        const s = typeof score === 'number' ? score.toFixed(1) : String(score);
        return grade ? `${s} (${grade})` : s;
    }

    /** 构建得分明细 HTML（与 GMS 选股页共用 GmsScoreDetail） */
    buildScoreDetailHtml(row) {
        const sd = {
            ratio_d: row.ratio_d,
            avg_volume_20d: row.avg_volume_20d,
            current_volume: row.current_volume,
            ratio_d20: row.ratio_d20,
            ratio_d1: row.ratio_d1,
            delta: row.delta,
            d: row.d,
            rising_days: row.rising_days,
            falling_days: row.falling_days,
            fz_ratio: row.fz_ratio,
            instant_deviation: row.instant_deviation,
            volume_ratio: row.volume_ratio,
            score_accumulation: row.score_accumulation,
            score_momentum: row.score_momentum,
            score_total: row.score_total,
            accumulation_grade: row.accumulation_grade,
            momentum_grade: row.momentum_grade,
            ...(row.score_detail || {}),
            ...(this.gmsConfigMeta || {}),
        };
        if (typeof GmsScoreDetail !== 'undefined' && GmsScoreDetail.buildHtml) {
            return GmsScoreDetail.buildHtml(sd, this.gmsConfigMeta, this.traceConfigId);
        }
        return '<div class="gms-score-detail-inner">得分明细组件未加载</div>';
    }

    renderTable() {
        const start = (this.currentPage - 1) * this.pageSize;
        const pageData = this.allData.slice(start, start + this.pageSize);
        const tbody = document.getElementById('traceTable').querySelector('tbody');

        if (pageData.length === 0) {
            tbody.innerHTML = '<tr><td colspan="13">暂无数据</td></tr>';
            return;
        }

        let html = '';
        pageData.forEach((r, index) => {
            const buyClass = r.left_buy_signal ? 'buy-left' : (r.right_buy_signal ? 'buy-right' : '');
            let strengthClass = 'strength-low';
            let ss = r.signal_strength;
            if ((ss == null || ss === 0) && r.score_total != null && r.score_total > 0) {
                ss = r.score_total / 100;
            }
            if (ss != null && ss >= 0.8) strengthClass = 'strength-high';
            else if (ss != null && ss >= 0.6) strengthClass = 'strength-mid';

            const scoreDetailHtml = this.buildScoreDetailHtml(r);
            const rowStrengthClass = (ss != null && ss >= 0.6) ? strengthClass : '';
            html += `
            <tr data-gms-row="${index}"${rowStrengthClass ? ` class="row-${strengthClass}"` : ''}>
                <td>${r.date || '--'}</td>
                <td>${r.score_total != null ? r.score_total.toFixed(1) : '--'}</td>
                <td class="${strengthClass}">${ss != null ? this.fmtPct(ss) : '--'}</td>
                <td class="${buyClass}">${r.buy_type || '--'}</td>
                <td>${this.fmtScoreDetail(r.score_accumulation, r.accumulation_grade)}</td>
                <td>${this.fmtScoreDetail(r.score_momentum, r.momentum_grade)}</td>
                <td>${this.fmtNum(r.delta)}</td>
                <td>${r.d != null ? r.d.toFixed(2) : '--'}</td>
                <td>${this.fmtPct(r.ratio_d20)}</td>
                <td>${this.fmtPct(r.ratio_d1)}</td>
                <td>${r.fz_ratio != null ? r.fz_ratio.toFixed(2) : '--'}</td>
                <td>${r.volume_ratio != null ? r.volume_ratio.toFixed(2) : '--'}</td>
                <td>
                    <button type="button" class="action-link gms-score-detail-toggle" data-row="${index}" title="展开/收起得分明细">得分明细</button>
                </td>
            </tr>
            <tr class="gms-score-detail-row" data-detail-for="${index}" style="display:none;">
                <td colspan="13" class="gms-score-detail-cell">${scoreDetailHtml}</td>
            </tr>`;
        });
        tbody.innerHTML = html;
    }

    updatePagination() {
        document.getElementById('pageInfo').textContent =
            `第 ${this.currentPage} / ${this.totalPages} 页，共 ${this.allData.length} 条`;
        document.getElementById('firstPage').disabled = this.currentPage <= 1;
        document.getElementById('prevPage').disabled = this.currentPage <= 1;
        document.getElementById('nextPage').disabled = this.currentPage >= this.totalPages;
        document.getElementById('lastPage').disabled = this.currentPage >= this.totalPages;
    }

    goToPage(p) {
        p = Math.max(1, Math.min(p, this.totalPages));
        this.currentPage = p;
        this.renderTable();
        this.updatePagination();
    }

    clearBacktestPoll() {
        if (this.backtestPollTimer) {
            clearInterval(this.backtestPollTimer);
            this.backtestPollTimer = null;
        }
        this.backtestPollCount = 0;
    }

    setBacktestRunning(running) {
        const startBtn = document.getElementById('btStartBtn');
        const cancelBtn = document.getElementById('btCancelBtn');
        if (startBtn) startBtn.disabled = !!running;
        if (cancelBtn) cancelBtn.disabled = !running;
    }

    async startBacktest() {
        if (!this.currentStockCode) {
            alert('请先通过链接带股票代码进入本页面');
            return;
        }
        const startDate = document.getElementById('startDate')?.value;
        const endDate = document.getElementById('endDate')?.value;
        if (!startDate || !endDate) {
            alert('请填写回测区间的开始日期与结束日期');
            return;
        }
        const market = document.getElementById('btMarket')?.value || 'all';
        const pctRaw = parseFloat(String(document.getElementById('btTargetPct')?.value || '10'), 10);
        if (Number.isNaN(pctRaw) || pctRaw < 0.1 || pctRaw > 100) {
            alert('目标阈值请在 0.1%～100% 之间（输入数字为百分比，如 10 表示 +10%）');
            return;
        }
        const targetPct = pctRaw / 100;
        const horizon = parseInt(document.getElementById('btHorizon')?.value || '20', 10);
        const minScore = parseFloat(document.getElementById('btMinScore')?.value || '70', 10);
        if (horizon < 10 || horizon > 30) {
            alert('持有窗口应在 10～30 个交易日之间');
            return;
        }
        this.clearBacktestPoll();
        const resultArea = document.getElementById('btResultArea');
        const statusArea = document.getElementById('btStatusArea');
        if (resultArea) {
            resultArea.style.display = 'none';
            resultArea.innerHTML = '';
        }
        if (statusArea) {
            statusArea.style.display = 'block';
            statusArea.innerHTML = '正在提交回测任务…';
        }
        this.setBacktestRunning(true);
        const base = this.getApiBase();
        const url = `${base}/api/stock/gms-backtest`;
        try {
            const resp = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    code: this.currentStockCode,
                    start_date: startDate,
                    end_date: endDate,
                    market,
                    target_pct: targetPct,
                    horizon_days: horizon,
                    min_score: minScore
                })
            });
            const json = await resp.json().catch(() => ({}));
            if (!resp.ok) {
                const detail = json.detail || json.message || resp.statusText;
                throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
            }
            if (!json.success || !json.data) {
                throw new Error(json.message || '创建任务失败');
            }
            this.backtestTaskId = json.data.task_id;
            this.pollBacktestOnce();
            this.backtestPollTimer = setInterval(() => this.pollBacktestOnce(), 2000);
        } catch (e) {
            if (statusArea) {
                statusArea.innerHTML = `<span class="gms-backtest-error">提交失败: ${e.message || e}</span>`;
            }
            this.setBacktestRunning(false);
        }
    }

    async pollBacktestOnce() {
        this.backtestPollCount += 1;
        if (this.backtestPollCount > this.maxBacktestPolls) {
            this.clearBacktestPoll();
            this.setBacktestRunning(false);
            const statusArea = document.getElementById('btStatusArea');
            if (statusArea) {
                statusArea.style.display = 'block';
                statusArea.innerHTML = '<span class="gms-backtest-error">等待超时，请稍后在管理端查看任务或重试</span>';
            }
            return;
        }
        const base = this.getApiBase();
        const url = `${base}/api/stock/gms-backtest/${encodeURIComponent(this.backtestTaskId)}`;
        try {
            const resp = await fetch(url);
            const json = await resp.json().catch(() => ({}));
            if (!resp.ok) {
                this.clearBacktestPoll();
                this.setBacktestRunning(false);
                const statusArea = document.getElementById('btStatusArea');
                if (statusArea) {
                    statusArea.style.display = 'block';
                    statusArea.innerHTML = `<span class="gms-backtest-error">查询失败: ${json.detail || resp.statusText}</span>`;
                }
                return;
            }
            const task = json.data;
            if (!task) return;
            this.renderBacktestStatus(task);
            const st = task.status;
            if (st === 'completed' || st === 'failed' || st === 'cancelled') {
                this.clearBacktestPoll();
                this.setBacktestRunning(false);
                if (st === 'completed') {
                    this.renderBacktestSummary(task);
                } else if (st === 'failed') {
                    const err = task.error || '回测失败';
                    const resultArea = document.getElementById('btResultArea');
                    if (resultArea) {
                        resultArea.style.display = 'block';
                        resultArea.innerHTML = `<p class="gms-backtest-error">${escapeHtml(String(err))}</p>`;
                    }
                } else if (st === 'cancelled') {
                    const resultArea = document.getElementById('btResultArea');
                    if (resultArea) {
                        resultArea.style.display = 'block';
                        resultArea.innerHTML = '<p>任务已取消</p>';
                    }
                }
            }
        } catch (e) {
            this.clearBacktestPoll();
            this.setBacktestRunning(false);
            const statusArea = document.getElementById('btStatusArea');
            if (statusArea) {
                statusArea.style.display = 'block';
                statusArea.innerHTML = `<span class="gms-backtest-error">轮询异常: ${e.message || e}</span>`;
            }
        }
    }

    renderBacktestStatus(task) {
        const statusArea = document.getElementById('btStatusArea');
        if (!statusArea) return;
        statusArea.style.display = 'block';
        const pct = task.progress != null ? Math.min(100, Math.max(0, Number(task.progress))) : 0;
        const msg = task.message || task.status || '';
        statusArea.innerHTML = `
            <div>状态: <strong>${escapeHtml(String(task.status || ''))}</strong>${msg ? ` · ${escapeHtml(String(msg))}` : ''}</div>
            <div class="bt-progress-bar"><div class="bt-progress-bar-inner" style="width:${pct}%"></div></div>
        `;
    }

    renderBacktestSummary(task) {
        const resultArea = document.getElementById('btResultArea');
        if (!resultArea) return;
        const summary = task.summary;
        const cfg = task.config || {};
        resultArea.style.display = 'block';
        if (!summary || typeof summary !== 'object') {
            resultArea.innerHTML = '<p>回测已完成，暂无汇总数据</p>';
            return;
        }
        const hr = summary.hit_rate != null ? (Number(summary.hit_rate) * 100).toFixed(2) + '%' : '--';
        const samples = summary.total_samples != null ? String(summary.total_samples) : '--';
        const hits = summary.hit_count != null ? String(summary.hit_count) : '--';
        const tp = cfg.target_pct != null ? (Number(cfg.target_pct) * 100).toFixed(1) : '--';
        const hz = cfg.horizon_days != null ? String(cfg.horizon_days) : '--';
        const ms = cfg.min_score != null ? String(cfg.min_score) : '--';
        let html = '';
        html += '<div class="gms-bt-report-block">';
        html += '<h4>回测报告</h4>';
        html += `<p class="gms-bt-report-meta">任务名称：${escapeHtml(String(task.name || task.task_id || ''))}</p>`;
        html += '<ul class="gms-bt-report-params">';
        html += `<li>区间：${escapeHtml(String(cfg.start_date || ''))} ～ ${escapeHtml(String(cfg.end_date || ''))}</li>`;
        html += `<li>目标涨幅 ${tp}% · 持有窗口 ${hz} 个交易日 · 最低总分 ${ms}</li>`;
        if (summary.buy_signal_rule) {
            html += `<li>${escapeHtml(String(summary.buy_signal_rule))}</li>`;
        }
        html += '</ul></div>';
        html += '<h4 class="gms-bt-summary-h4">结果摘要</h4>';
        html += '<div class="gms-backtest-summary-grid">';
        html += `<div class="gms-backtest-summary-item"><strong>命中率</strong><span>${hr}</span></div>`;
        html += `<div class="gms-backtest-summary-item"><strong>样本数</strong><span>${escapeHtml(samples)}</span></div>`;
        html += `<div class="gms-backtest-summary-item"><strong>命中次数</strong><span>${escapeHtml(hits)}</span></div>`;
        html += '</div>';
        html += this.renderBacktestBuckets('按买点类型', summary.by_buy_type);
        html += this.renderBacktestBuckets('按总分区间', summary.by_score_bucket);
        const tid = task.task_id;
        if (tid) {
            const exportUrl = `${this.getApiBase()}/api/stock/gms-backtest/${encodeURIComponent(tid)}/export`;
            html += `<p class="gms-bt-export-wrap"><a class="gms-bt-export-link" href="${exportUrl}" download>下载明细 Excel</a></p>`;
        }
        resultArea.innerHTML = html;
    }

    renderBacktestBuckets(title, buckets) {
        if (!buckets || typeof buckets !== 'object') return '';
        const keys = Object.keys(buckets);
        if (!keys.length) return '';
        let rows = '';
        keys.forEach((k) => {
            const v = buckets[k];
            if (!v || typeof v !== 'object') return;
            const t = v.total != null ? v.total : 0;
            const h = v.hit != null ? v.hit : 0;
            const rate = v.hit_rate != null ? (Number(v.hit_rate) * 100).toFixed(2) + '%' : '--';
            rows += `<tr><td>${escapeHtml(k)}</td><td>${t}</td><td>${h}</td><td>${rate}</td></tr>`;
        });
        if (!rows) return '';
        return `
            <div class="gms-backtest-buckets">
                <strong>${escapeHtml(title)}</strong>
                <table>
                    <thead><tr><th>分组</th><th>样本</th><th>命中</th><th>命中率</th></tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>`;
    }

    async cancelBacktest() {
        if (!this.backtestTaskId) return;
        const base = this.getApiBase();
        const url = `${base}/api/stock/gms-backtest/${encodeURIComponent(this.backtestTaskId)}/cancel`;
        try {
            const resp = await fetch(url, { method: 'POST' });
            if (!resp.ok) {
                const j = await resp.json().catch(() => ({}));
                alert(j.detail || '取消失败');
                return;
            }
            this.clearBacktestPoll();
            this.setBacktestRunning(false);
            const statusArea = document.getElementById('btStatusArea');
            if (statusArea) {
                statusArea.style.display = 'block';
                statusArea.innerHTML = '<span>已请求取消</span>';
            }
        } catch (e) {
            alert(e.message || '取消失败');
        }
    }
}

function escapeHtml(s) {
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

document.addEventListener('DOMContentLoaded', () => {
    window.gmsTracePage = new StockGMSTracePage();
});

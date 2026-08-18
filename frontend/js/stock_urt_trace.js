/**
 * URT 策略信号历史页（展示风格对齐 GMS 追溯页，含个股强制重算与分页）
 */
(function () {
    const apiBase = (typeof Config !== 'undefined' && Config.getApiBaseUrl)
        ? (Config.getApiBaseUrl() || '')
        : '';

    function escapeHtml(s) {
        if (s == null) return '';
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    class StockUrtTracePage {
        constructor() {
            const params = new URLSearchParams(window.location.search);
            this.code = (params.get('code') || '').trim();
            this.name = decodeURIComponent(params.get('name') || '');
            this.configId = params.get('config_id') ? Number(params.get('config_id')) : null;
            this.configOptions = [];
            this.allData = [];
            this.currentPage = 1;
            this.pageSize = 30;
            this.totalPages = 0;
            this.forceComputeRunning = false;
            this.forceComputePollTimer = null;
            this.forceComputeTaskId = '';
            this.forceComputePollCount = 0;
            this.maxForceComputePolls = 3600;
            this.backtestRunning = false;
            this.backtestTaskId = '';
            this.backtestPollTimer = null;
            this.backtestPollCount = 0;
            this.maxBacktestPolls = 3600;

            document.getElementById('stockDisplay').textContent =
                this.code ? `${this.code} ${this.name}` : '--';
            // 与 GMS 一致：默认最近约三个月（90 天）；URL 可覆盖
            this.setDefaultDates();
            const startEl = document.getElementById('startDate');
            const endEl = document.getElementById('endDate');
            if (startEl && params.get('start_date')) startEl.value = params.get('start_date');
            if (endEl && params.get('end_date')) endEl.value = params.get('end_date');
            document.getElementById('searchBtn').addEventListener('click', () => {
                if (this.forceComputeRunning) return;
                this.fetchData();
            });
            const forceBtn = document.getElementById('forceComputeBtn');
            if (forceBtn) {
                forceBtn.addEventListener('click', () => this.forceCompute());
            }
            document.getElementById('configSelect').addEventListener('change', () => {
                if (this.forceComputeRunning) return;
                this.configId = Number(document.getElementById('configSelect').value) || null;
                this.fetchData();
            });
            document.getElementById('firstPage').addEventListener('click', () => this.goToPage(1));
            document.getElementById('prevPage').addEventListener('click', () => this.goToPage(this.currentPage - 1));
            document.getElementById('nextPage').addEventListener('click', () => this.goToPage(this.currentPage + 1));
            document.getElementById('lastPage').addEventListener('click', () => this.goToPage(this.totalPages));

            const btBtn = document.getElementById('btStartBtn');
            if (btBtn) btBtn.addEventListener('click', () => this.startBacktest());

            const tbody = document.querySelector('#traceTable tbody');
            if (tbody) {
                tbody.addEventListener('click', (e) => {
                    const btn = e.target.closest('.urt-score-detail-toggle');
                    if (!btn) return;
                    e.preventDefault();
                    const idx = btn.getAttribute('data-row');
                    const detailRow = tbody.querySelector(`tr.gms-score-detail-row[data-detail-for="${idx}"]`);
                    if (detailRow) {
                        detailRow.style.display = detailRow.style.display === 'none' ? '' : 'none';
                    }
                });
            }
            this.updatePagination();
            if (this.code) this.fetchData();
        }

        setDefaultDates() {
            const today = new Date();
            const threeMonthsAgo = new Date(today.getTime() - 90 * 24 * 60 * 60 * 1000);
            const startEl = document.getElementById('startDate');
            const endEl = document.getElementById('endDate');
            if (startEl) startEl.value = this.formatDate(threeMonthsAgo);
            if (endEl) endEl.value = this.formatDate(today);
        }

        formatDate(d) {
            return d.toISOString().slice(0, 10);
        }

        getActiveConfigLabel() {
            const opt = (this.configOptions || []).find((o) => String(o.id) === String(this.configId));
            if (!opt) return '当前策略版本';
            const name = opt.name || `配置${opt.id}`;
            return opt.is_default ? `${name} (默认)` : name;
        }

        setForceComputeRunning(running) {
            this.forceComputeRunning = !!running;
            const btn = document.getElementById('forceComputeBtn');
            const searchBtn = document.getElementById('searchBtn');
            const sel = document.getElementById('configSelect');
            if (btn) {
                btn.disabled = this.forceComputeRunning;
                btn.textContent = this.forceComputeRunning ? '正在重新计算…' : '强制重新计算';
            }
            if (searchBtn) searchBtn.disabled = this.forceComputeRunning;
            if (sel) sel.disabled = this.forceComputeRunning;
            ['startDate', 'endDate'].forEach((id) => {
                const el = document.getElementById(id);
                if (el) el.disabled = this.forceComputeRunning;
            });
            ['firstPage', 'prevPage', 'nextPage', 'lastPage'].forEach((id) => {
                const el = document.getElementById(id);
                if (el && this.forceComputeRunning) el.disabled = true;
            });
            if (!this.forceComputeRunning) this.updatePagination();
        }

        clearForceComputePoll() {
            if (this.forceComputePollTimer) {
                clearInterval(this.forceComputePollTimer);
                this.forceComputePollTimer = null;
            }
            this.forceComputePollCount = 0;
        }

        renderForceComputeProgress(task) {
            const area = document.getElementById('forceComputeProgress');
            if (!area) return;
            area.style.display = 'block';
            const pct = task.progress != null ? Math.min(100, Math.max(0, Number(task.progress))) : 0;
            const msg = task.message || '';
            // 完成后优先用实际写入条数，保证展示与落库一致
            const saved = task.saved_count != null ? Number(task.saved_count) : null;
            const cur = (task.status === 'completed' && saved != null && !Number.isNaN(saved))
                ? saved
                : (task.current || 0);
            const tot = (task.status === 'completed' && saved != null && !Number.isNaN(saved))
                ? saved
                : task.total;
            const total = tot != null && tot > 0 ? ` · ${cur}/${tot}` : '';
            const statusLabel = task.status === 'completed' ? '已完成'
                : (task.status === 'failed' ? '失败' : '计算中');
            area.innerHTML = `
                <div>URT 信号重算: <strong>${escapeHtml(statusLabel)}</strong>${msg ? ` · ${escapeHtml(String(msg))}${total}` : ''}</div>
                <div class="bt-progress-bar"><div class="bt-progress-bar-inner" style="width:${pct}%"></div></div>
            `;
        }

        forceCompute() {
            if (this.forceComputeRunning) return;
            if (!this.code) {
                alert('请先选择股票');
                return;
            }
            const label = this.getActiveConfigLabel();
            if (!confirm(`将按「${label}」重新计算该股全部历史行情的 URT 信号（仅影响该策略版本，耗时可能较长），是否继续？`)) {
                return;
            }
            void this.startForceComputeTask();
        }

        async startForceComputeTask() {
            this.clearForceComputePoll();
            this.setForceComputeRunning(true);
            const area = document.getElementById('forceComputeProgress');
            if (area) {
                area.style.display = 'block';
                area.innerHTML = '<div>正在提交重算任务…</div><div class="bt-progress-bar"><div class="bt-progress-bar-inner" style="width:5%"></div></div>';
            }
            const loading = document.getElementById('loadingMsg');
            if (loading) loading.style.display = 'none';

            try {
                const resp = await fetch(`${apiBase}/api/stock/urt-signal-trace/recompute`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        code: this.code,
                        config_id: this.configId,
                    }),
                });
                const json = await resp.json().catch(() => ({}));
                if (!resp.ok || !json.success) {
                    const detail = json.detail;
                    let errMsg = json.message || resp.statusText;
                    if (typeof detail === 'string') errMsg = detail;
                    else if (Array.isArray(detail)) errMsg = detail.map((d) => d.msg || d).join('; ');
                    throw new Error(errMsg || '提交失败');
                }
                this.forceComputeTaskId = json.data?.task_id || '';
                if (!this.forceComputeTaskId) {
                    throw new Error('未返回任务 ID');
                }
                if (json.data?.config_id != null) {
                    this.configId = json.data.config_id;
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
            const url = `${apiBase}/api/stock/urt-signal-trace/recompute/${encodeURIComponent(this.forceComputeTaskId)}`;
            try {
                const resp = await fetch(url);
                const json = await resp.json().catch(() => ({}));
                if (!resp.ok || !json.success) {
                    const detail = json.detail;
                    let errMsg = json.message || resp.statusText;
                    if (typeof detail === 'string') errMsg = detail;
                    else if (Array.isArray(detail)) errMsg = detail.map((d) => d.msg || d).join('; ');
                    throw new Error(errMsg || '查询进度失败');
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
                        await this.fetchData();
                        if (task.message) {
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

        renderTable() {
            const tbody = document.querySelector('#traceTable tbody');
            if (!tbody) return;
            const start = (this.currentPage - 1) * this.pageSize;
            const pageData = this.allData.slice(start, start + this.pageSize);
            if (!pageData.length) {
                tbody.innerHTML = '';
                return;
            }
            tbody.innerHTML = pageData.map((r, index) => {
                const st = (r.score_detail && r.score_detail.structure) || {};
                const nearSup = r.nearest_support != null ? r.nearest_support : st.nearest_support;
                const nearRes = r.nearest_resistance != null ? r.nearest_resistance : st.nearest_resistance;
                const supports = Array.isArray(r.support_levels) && r.support_levels.length
                    ? r.support_levels
                    : (Array.isArray(st.support_levels) ? st.support_levels : []);
                const resists = Array.isArray(r.resistance_levels) && r.resistance_levels.length
                    ? r.resistance_levels
                    : (Array.isArray(st.resistance_levels) ? st.resistance_levels : []);
                const fmtPx = (v) => (v != null && Number.isFinite(Number(v)) ? Number(v).toFixed(2) : '--');
                const titleLevels = (arr, nearest) => {
                    if (arr && arr.length) return arr.map((x) => Number(x).toFixed(2)).join('、');
                    return nearest != null ? String(nearest) : '';
                };
                let detailHtml = '<div class="gms-score-detail-inner">得分明细组件未加载</div>';
                if (window.UrtScoreDetail) {
                    detailHtml = window.UrtScoreDetail.buildHtml({
                        ...r,
                        score: r.score,
                        score_detail: r.score_detail,
                        buy_signal: r.buy_signal,
                        buy_logic: r.buy_logic,
                        filter_ok: r.filter_ok,
                        score_ok: r.score_ok,
                        filter_reason: r.filter_reason,
                        nearest_support: nearSup,
                        nearest_resistance: nearRes,
                        support_levels: supports,
                        resistance_levels: resists,
                        trade_advice: r.trade_advice
                            || (r.score_detail && r.score_detail.trade_advice)
                            || null,
                        kde_ok: r.kde_ok != null ? r.kde_ok : st.kde_ok,
                        kde_reason: r.kde_reason || st.kde_reason,
                        kde_lookback_used: r.kde_lookback_used != null ? r.kde_lookback_used : st.kde_lookback_used,
                        fields: {
                            close: r.close,
                            open: r.open,
                            ma20: r.ma20,
                            above_ma20: r.above_ma20,
                            yang_count_4: r.yang_count_4,
                            yang_count_5: r.yang_count_5,
                            volume_multiple: r.volume_multiple,
                            volume_ratio: r.volume_ratio,
                            turnover_rate: r.turnover_rate,
                            filter_ok: r.filter_ok,
                            score_ok: r.score_ok,
                            filter_reason: r.filter_reason,
                            nearest_support: nearSup,
                            nearest_resistance: nearRes,
                        },
                    });
                }
                const scoreVal = r.score != null ? Number(r.score) : null;
                let scoreClass = '';
                let rowClass = '';
                if (scoreVal != null) {
                    if (scoreVal >= 85) {
                        scoreClass = 'strength-high';
                        rowClass = 'urt-row-score-high';
                    } else if (scoreVal >= 70) {
                        scoreClass = 'strength-mid';
                        rowClass = 'urt-row-score-mid';
                    }
                }
                return `<tr class="${rowClass}">
                    <td>${r.date || '--'}</td>
                    <td class="${r.buy_signal ? 'buy-yes' : ''}">${r.buy_signal ? '是' : '否'}</td>
                    <td><span class="${scoreClass}">${scoreVal != null ? scoreVal.toFixed(1) : '--'}</span></td>
                    <td>${fmtPx(r.close)}</td>
                    <td>${fmtPx(r.ma20)}</td>
                    <td>${r.yang_count_4 ?? '--'}</td>
                    <td>${r.yang_count_5 ?? '--'}</td>
                    <td>${r.volume_multiple != null ? Number(r.volume_multiple).toFixed(2) : '--'}</td>
                    <td>${r.volume_ratio != null ? Number(r.volume_ratio).toFixed(2) : '--'}</td>
                    <td>${r.turnover_rate != null ? Number(r.turnover_rate).toFixed(2) : '--'}</td>
                    <td class="support" title="${titleLevels(supports, nearSup)}">${fmtPx(nearSup)}</td>
                    <td class="resistance" title="${titleLevels(resists, nearRes)}">${fmtPx(nearRes)}</td>
                    <td><button type="button" class="gms-op-btn urt-score-detail-toggle" data-row="${index}">明细</button></td>
                </tr>
                <tr class="gms-score-detail-row" data-detail-for="${index}" style="display:none;">
                    <td colspan="13" class="gms-score-detail-cell">${detailHtml}</td>
                </tr>`;
            }).join('');
        }

        updatePagination() {
            const total = this.allData.length;
            this.totalPages = total > 0 ? Math.max(1, Math.ceil(total / this.pageSize)) : 0;
            const pageInfo = document.getElementById('pageInfo');
            if (pageInfo) {
                pageInfo.textContent = total > 0
                    ? `第 ${this.currentPage} / ${this.totalPages} 页，共 ${total} 条`
                    : '共 0 条';
            }
            const atStart = this.currentPage <= 1 || total === 0;
            const atEnd = this.currentPage >= this.totalPages || total === 0;
            const first = document.getElementById('firstPage');
            const prev = document.getElementById('prevPage');
            const next = document.getElementById('nextPage');
            const last = document.getElementById('lastPage');
            if (first) first.disabled = atStart || this.forceComputeRunning;
            if (prev) prev.disabled = atStart || this.forceComputeRunning;
            if (next) next.disabled = atEnd || this.forceComputeRunning;
            if (last) last.disabled = atEnd || this.forceComputeRunning;
        }

        goToPage(p) {
            if (this.forceComputeRunning) return;
            if (!this.totalPages || p < 1 || p > this.totalPages) return;
            this.currentPage = p;
            this.renderTable();
            this.updatePagination();
        }

        setBacktestRunning(running) {
            this.backtestRunning = !!running;
            const btn = document.getElementById('btStartBtn');
            if (btn) {
                btn.disabled = this.backtestRunning;
                btn.textContent = this.backtestRunning ? '回测进行中…' : '开始回测';
            }
        }

        clearBacktestPoll() {
            if (this.backtestPollTimer) {
                clearInterval(this.backtestPollTimer);
                this.backtestPollTimer = null;
            }
            this.backtestPollCount = 0;
        }

        async startBacktest() {
            if (this.backtestRunning) return;
            if (!this.code) {
                alert('请先通过链接带股票代码进入本页面');
                return;
            }
            const startDate = document.getElementById('startDate')?.value;
            const endDate = document.getElementById('endDate')?.value;
            if (!startDate || !endDate) {
                alert('请填写回测区间的开始日期与结束日期');
                return;
            }
            const pctRaw = parseFloat(String(document.getElementById('btTargetPct')?.value || '10'), 10);
            if (Number.isNaN(pctRaw) || pctRaw < 0.1 || pctRaw > 100) {
                alert('目标涨幅请在 0.1%～100% 之间');
                return;
            }
            const targetPct = pctRaw / 100;
            const horizon = parseInt(document.getElementById('btHorizon')?.value || '10', 10);
            const minScoreRaw = document.getElementById('btMinScore')?.value;
            const minScore = minScoreRaw !== '' && minScoreRaw != null ? parseFloat(minScoreRaw) : null;
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
            const body = {
                code: this.code,
                start_date: startDate,
                end_date: endDate,
                target_pct: targetPct,
                horizon_days: horizon,
                strategy_config_id: this.configId,
            };
            if (minScore != null && !Number.isNaN(minScore)) body.min_score = minScore;
            try {
                const resp = await fetch(`${apiBase}/api/stock/urt-backtest`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
                const json = await resp.json().catch(() => ({}));
                if (!resp.ok || !json.success) {
                    const detail = json.detail || json.message || resp.statusText;
                    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
                }
                this.backtestTaskId = json.data?.task_id || '';
                if (!this.backtestTaskId) throw new Error('未返回任务 ID');
                this.pollBacktestOnce();
                this.backtestPollTimer = setInterval(() => this.pollBacktestOnce(), 2000);
            } catch (e) {
                if (statusArea) {
                    statusArea.innerHTML = `<span class="gms-backtest-error">提交失败: ${escapeHtml(e.message || e)}</span>`;
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
                    statusArea.innerHTML = '<span class="gms-backtest-error">等待超时，请稍后在管理端查看或重试</span>';
                }
                return;
            }
            try {
                const resp = await fetch(`${apiBase}/api/stock/urt-backtest/${encodeURIComponent(this.backtestTaskId)}`);
                const json = await resp.json().catch(() => ({}));
                if (!resp.ok) {
                    this.clearBacktestPoll();
                    this.setBacktestRunning(false);
                    const statusArea = document.getElementById('btStatusArea');
                    if (statusArea) {
                        statusArea.innerHTML = `<span class="gms-backtest-error">查询失败: ${escapeHtml(json.detail || resp.statusText)}</span>`;
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
                        const resultArea = document.getElementById('btResultArea');
                        if (resultArea) {
                            resultArea.style.display = 'block';
                            resultArea.innerHTML = `<p class="gms-backtest-error">${escapeHtml(String(task.error || '回测失败'))}</p>`;
                        }
                    }
                }
            } catch (e) {
                this.clearBacktestPoll();
                this.setBacktestRunning(false);
                const statusArea = document.getElementById('btStatusArea');
                if (statusArea) {
                    statusArea.innerHTML = `<span class="gms-backtest-error">轮询异常: ${escapeHtml(e.message || e)}</span>`;
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
            let html = '<h4>回测报告</h4>';
            html += `<p>区间 ${escapeHtml(String(cfg.start_date || ''))} ～ ${escapeHtml(String(cfg.end_date || ''))} · 目标 ${tp}% · 窗口 ${hz} 日</p>`;
            html += '<div class="gms-backtest-summary-grid">';
            html += `<div class="gms-backtest-summary-item"><strong>命中率</strong><span>${hr}</span></div>`;
            html += `<div class="gms-backtest-summary-item"><strong>样本数</strong><span>${escapeHtml(samples)}</span></div>`;
            html += `<div class="gms-backtest-summary-item"><strong>命中次数</strong><span>${escapeHtml(hits)}</span></div>`;
            html += '</div>';
            const tid = task.task_id;
            if (tid) {
                const exportUrl = `${apiBase}/api/stock/urt-backtest/${encodeURIComponent(tid)}/export`;
                html += `<p class="gms-bt-export-wrap"><a class="gms-bt-export-link" href="${exportUrl}" download>下载明细 CSV</a></p>`;
            }
            resultArea.innerHTML = html;
        }

        async fetchData() {
            const loading = document.getElementById('loadingMsg');
            const empty = document.getElementById('emptyMsg');
            const tbody = document.querySelector('#traceTable tbody');
            loading.style.display = '';
            empty.style.display = 'none';
            empty.textContent = '暂无 URT 预计算信号（可点击「强制重新计算」对该股即时计算）';
            tbody.innerHTML = '';
            this.allData = [];
            this.currentPage = 1;
            this.totalPages = 0;
            this.updatePagination();
            try {
                const startDate = (document.getElementById('startDate')?.value || '').trim();
                const endDate = (document.getElementById('endDate')?.value || '').trim();
                if (startDate && endDate && startDate > endDate) {
                    empty.textContent = '开始日期不能晚于结束日期';
                    empty.style.display = '';
                    return;
                }
                const q = new URLSearchParams({ code: this.code, limit: '2000' });
                if (this.configId) q.set('config_id', String(this.configId));
                if (startDate) q.set('start_date', startDate);
                if (endDate) q.set('end_date', endDate);
                const res = await fetch(`${apiBase}/api/stock/urt-signal-trace?${q}`);
                const json = await res.json();
                if (!res.ok || json.success === false) {
                    const detail = json.detail;
                    let errMsg = json.message || res.statusText || '加载失败';
                    if (typeof detail === 'string') errMsg = detail;
                    else if (Array.isArray(detail)) errMsg = detail.map((d) => d.msg || d).join('; ');
                    throw new Error(errMsg);
                }
                const configs = json.configs || [];
                this.configOptions = configs;
                const sel = document.getElementById('configSelect');
                sel.innerHTML = configs.map((c) =>
                    `<option value="${c.id}" ${c.id === json.config_id ? 'selected' : ''}>${escapeHtml(c.name)}${c.is_default ? ' (默认)' : ''}</option>`
                ).join('');
                this.configId = json.config_id;
                const detail = document.getElementById('detailLink');
                detail.href = `stock_urt_score_detail.html?code=${encodeURIComponent(this.code)}&name=${encodeURIComponent(this.name)}&config_id=${this.configId || ''}`;
                this.allData = json.data || [];
                if (!this.allData.length) {
                    empty.textContent = (startDate || endDate)
                        ? '所选日期范围内暂无 URT 信号记录'
                        : '暂无 URT 预计算信号（可点击「强制重新计算」对该股即时计算）';
                    empty.style.display = '';
                    this.updatePagination();
                    return;
                }
                this.totalPages = Math.max(1, Math.ceil(this.allData.length / this.pageSize));
                this.currentPage = 1;
                this.renderTable();
                this.updatePagination();
            } catch (e) {
                empty.textContent = '加载失败: ' + (e.message || e);
                empty.style.display = '';
                this.allData = [];
                this.updatePagination();
            } finally {
                loading.style.display = 'none';
            }
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        window.urtTracePage = new StockUrtTracePage();
    });
})();

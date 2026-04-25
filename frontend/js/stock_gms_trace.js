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
        if (this.currentStockCode) {
            this.fetchData();
        }
    }

    bindEvents() {
        document.getElementById('searchBtn').addEventListener('click', () => this.fetchData());
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

        let url = `${this.getApiBase()}/api/stock/gms-signal-trace?code=${encodeURIComponent(this.currentStockCode)}`;
        if (startDate) url += `&start_date=${startDate}`;
        if (endDate) url += `&end_date=${endDate}`;
        if (forceCompute) url += '&force_compute=1';

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
            this.allData = json.data || [];
            if (json.message) {
                empty.textContent = json.message;
                empty.style.display = this.allData.length === 0 ? 'block' : 'none';
            } else {
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
        this.fetchData(true);
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

    /** 构建得分明细 HTML（参考 GMS 筛选主页） */
    buildScoreDetailHtml(sd) {
        const accS = (sd.accumulation_s_threshold != null && !isNaN(sd.accumulation_s_threshold)) ? sd.accumulation_s_threshold : 85;
        const accA = (sd.accumulation_a_threshold != null && !isNaN(sd.accumulation_a_threshold)) ? sd.accumulation_a_threshold : 70;
        const momFull = (sd.momentum_full_threshold != null && !isNaN(sd.momentum_full_threshold)) ? sd.momentum_full_threshold : 90;
        const momBatch = (sd.momentum_batch_threshold != null && !isNaN(sd.momentum_batch_threshold)) ? sd.momentum_batch_threshold : 80;
        const fzTiers = sd.acc_fz_tiers || [2.5, 1.5];
        const balTiers = sd.balance_tiers || [0.01, 0.015];
        const volShrink = sd.vol_shrink_tiers || [0.6, 0.8];
        const ratioD1Tiers = sd.ratio_d1_tiers || [0.001, 0.03];
        const volAttack = sd.vol_attack_tiers || [2.0, 1.5];
        const wAccFz = (sd.weight_acc_fz != null && !isNaN(sd.weight_acc_fz)) ? sd.weight_acc_fz : 30;
        const wAccBal = (sd.weight_acc_balance != null && !isNaN(sd.weight_acc_balance)) ? sd.weight_acc_balance : 40;
        const wAccVol = (sd.weight_acc_volume != null && !isNaN(sd.weight_acc_volume)) ? sd.weight_acc_volume : 30;
        const wMomD1 = (sd.weight_mom_ratio_d1 != null && !isNaN(sd.weight_mom_ratio_d1)) ? sd.weight_mom_ratio_d1 : 40;
        const wMomDev = (sd.weight_mom_deviation != null && !isNaN(sd.weight_mom_deviation)) ? sd.weight_mom_deviation : 30;
        const wMomVol = (sd.weight_mom_volume != null && !isNaN(sd.weight_mom_volume)) ? sd.weight_mom_volume : 30;
        let gmsDominantHint = '';
        const _acc = sd.score_accumulation;
        const _mom = sd.score_momentum;
        const _an = (_acc != null && !isNaN(_acc)) ? Number(_acc) : NaN;
        const _mn = (_mom != null && !isNaN(_mom)) ? Number(_mom) : NaN;
        if (!isNaN(_an) || !isNaN(_mn)) {
            if (!isNaN(_an) && !isNaN(_mn)) {
                if (_an > _mn) gmsDominantHint = '当前主导：均值收敛态（蓄势）。';
                else if (_mn > _an) gmsDominantHint = '当前主导：动量溢出态。';
                else gmsDominantHint = '两模块小计相同。';
            } else if (!isNaN(_an)) gmsDominantHint = '当前主导：均值收敛态（蓄势）。';
            else gmsDominantHint = '当前主导：动量溢出态。';
        }
        const gmsFmt = (v, type) => {
            if (v == null || (typeof v === 'number' && isNaN(v))) return '--';
            if (type === 'pct') return (v * 100).toFixed(2) + '%';
            if (type === 'int') return String(Math.round(v));
            if (type === 'vol') return (v >= 10000 ? (v / 10000).toFixed(2) + '万手' : Number(v).toFixed(0) + '手');
            if (type === 'price') return typeof v === 'number' ? v.toFixed(2) : String(v);
            if (type === 'ratio') return typeof v === 'number' ? v.toFixed(2) : String(v);
            if (type === 'num') return typeof v === 'number' ? v.toFixed(4) : String(v);
            return String(v);
        };
        return `
            <div class="gms-score-detail-inner">
                <div class="gms-score-detail-section">
                    <strong>【均值收敛态】得分明细</strong>
                    <table class="gms-weight-table">
                        <thead><tr><th>维度</th><th>得分</th><th>判定</th><th>规则</th></tr></thead>
                        <tbody>
                            <tr><td>时间耗散 F/Z</td><td>${(sd.score_acc_fz != null ? sd.score_acc_fz.toFixed(1) : '--')}</td><td class="gms-judge">${sd.acc_fz_judge || '—'}</td><td>权重${wAccFz}: ≥${fzTiers[0]}→满分; [${fzTiers[1]},${fzTiers[0]})→2/3</td></tr>
                            <tr><td>引力粘合 |Δ/d|</td><td>${(sd.score_acc_balance != null ? sd.score_acc_balance.toFixed(1) : '--')}</td><td class="gms-judge">${sd.acc_balance_judge || '—'}</td><td>权重${wAccBal}: ≤${(balTiers[0] * 100).toFixed(1)}%→满分; ≤${(balTiers[1] * 100).toFixed(1)}%→1/2</td></tr>
                            <tr><td>成交量缩 m₂₀/m</td><td>${(sd.score_acc_volume != null ? sd.score_acc_volume.toFixed(1) : '--')}</td><td class="gms-judge">${sd.acc_volume_judge || '—'}</td><td>权重${wAccVol}: ≤${volShrink[0]}→满分; (${volShrink[0]},${volShrink[1]}]→1/2</td></tr>
                            <tr><td>均值收敛态小计</td><td><strong>${sd.score_accumulation != null ? sd.score_accumulation.toFixed(1) : '--'}</strong></td><td colspan="2"><strong>判定: ${sd.accumulation_grade || '—'}</strong> (≥${accS} S; ≥${accA} A)</td></tr>
                        </tbody>
                    </table>
                </div>
                <div class="gms-score-detail-section">
                    <strong>【动量溢出态】得分明细</strong>
                    <table class="gms-weight-table">
                        <thead><tr><th>维度</th><th>得分</th><th>判定</th><th>规则</th></tr></thead>
                        <tbody>
                            <tr><td>盈亏反转 Δ/d₁</td><td>${(sd.score_mom_ratio_d1 != null ? sd.score_mom_ratio_d1.toFixed(1) : '--')}</td><td class="gms-judge">${sd.mom_ratio_d1_judge || '—'}</td><td>权重${wMomD1}: (0,${(ratioD1Tiers[1] * 100).toFixed(1)}%]→满分; 刚过0→1/2</td></tr>
                            <tr><td>推力支撑 d₂₀-d</td><td>${(sd.score_mom_deviation != null ? sd.score_mom_deviation.toFixed(1) : '--')}</td><td class="gms-judge">${sd.mom_deviation_judge || '—'}</td><td>权重${wMomDev}: 站稳3日→满分; 仅当日→1/2; &lt;0→-10</td></tr>
                            <tr><td>攻击强度 m₂₀/m</td><td>${(sd.score_mom_volume != null ? sd.score_mom_volume.toFixed(1) : '--')}</td><td class="gms-judge">${sd.mom_volume_judge || '—'}</td><td>权重${wMomVol}: ≥${volAttack[0]}→满分; [${volAttack[1]},${volAttack[0]})→2/3</td></tr>
                            <tr><td>动量溢出态小计</td><td><strong>${sd.score_momentum != null ? sd.score_momentum.toFixed(1) : '--'}</strong></td><td colspan="2"><strong>判定: ${sd.momentum_grade || '—'}</strong> (≥${momFull}全速; ≥${momBatch}分批)</td></tr>
                        </tbody>
                    </table>
                </div>
                <div class="gms-score-detail-section">
                    <strong>综合</strong> 总分=${sd.score_total != null ? sd.score_total.toFixed(1) : '--'}；信号强度=总分/100
                    <p class="gms-total-hint-text" style="font-size:12px;color:#666;margin:6px 0 0 0;line-height:1.45;">
                        总分 = max(均值收敛态小计, 动量溢出态小计)，非两模块分数相加。
                        ${gmsDominantHint ? '<br>' + gmsDominantHint : ''}
                    </p>
                </div>
                <div class="gms-score-detail-section gms-indicators-section">
                    <strong>计算指标细项</strong>
                    <table class="gms-weight-table gms-indicators-table">
                        <tbody>
                            <tr><td>d₁ (首日收盘价)</td><td>${gmsFmt(sd.d1, 'price')}</td><td>周期起点价格${sd.d1_date ? '，交易日期 ' + sd.d1_date : ''}</td></tr>
                            <tr><td>d₂₀ (末日收盘价)</td><td>${gmsFmt(sd.d20, 'price')}</td><td>周期末位/当日价格${sd.d20_date ? '，交易日期 ' + sd.d20_date : ''}</td></tr>
                            <tr><td>d (20日均价)</td><td>${gmsFmt(sd.d, 'price')}</td><td>周期均价</td></tr>
                            <tr><td>Δ (d₂₀ - d₁)</td><td>${gmsFmt(sd.delta, 'num')}</td><td>宏观位移</td></tr>
                            <tr><td>Δ/d</td><td>${(sd.delta != null && sd.d != null && sd.d !== 0 ? gmsFmt(sd.delta / sd.d, 'pct') : '--')}</td><td>宏观位移相对均价 (Δ/d)</td></tr>
                            <tr><td>Δ/d₂₀（宏观位移/收盘价）</td><td>${gmsFmt(sd.ratio_d20, 'pct')}</td><td>左侧买点粘合用 |Δ/d₂₀|；≠ 下方均线乖离 Δ₂₀/d</td></tr>
                            <tr><td>Δ/d₁（突变率）</td><td>${gmsFmt(sd.ratio_d1, 'pct')}</td><td>现价相对周期起点位移</td></tr>
                            <tr><td>Δ₂₀/d（均线乖离）</td><td>${gmsFmt(sd.ratio_d, 'pct')}</td><td>(d₂₀−d)/d；不是左侧判定用的 Δ/d₂₀</td></tr>
                            <tr><td>Z (上涨天数)</td><td>${gmsFmt(sd.rising_days, 'int')}</td><td>多头天数</td></tr>
                            <tr><td>F (下跌天数)</td><td>${gmsFmt(sd.falling_days, 'int')}</td><td>空头天数</td></tr>
                            <tr><td>m (20日平均成交量)</td><td>${gmsFmt(sd.avg_volume_20d, 'vol')}</td><td>平均量</td></tr>
                            <tr><td>m₂₀ (当日成交量)</td><td>${gmsFmt(sd.current_volume, 'vol')}</td><td>当日成交量</td></tr>
                            <tr><td>量比 (m₂₀/m)</td><td>${gmsFmt(sd.volume_ratio, 'ratio')}</td><td>放量/地量判断</td></tr>
                            <tr><td>F/Z (数方比)</td><td>${gmsFmt(sd.fz_ratio, 'ratio')}</td><td>蓄势判断</td></tr>
                            <tr><td>d₂₀ - d (价格vs均线)</td><td>${gmsFmt(sd.instant_deviation, 'num')}</td><td>价格相对均线偏离</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        `;
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

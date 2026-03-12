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
        return (typeof Config !== 'undefined' && Config.getApiBaseUrl) ? Config.getApiBaseUrl() : 'http://localhost:5000';
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
                    '<tr><td colspan="16">加载失败: ' + (json.message || '未知错误') + '</td></tr>';
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
                '<tr><td colspan="16">请求失败: ' + e.message + '</td></tr>';
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
        const accS = 85, accA = 70, momFull = 90, momBatch = 80;
        const fzTiers = [2.5, 1.5], balTiers = [0.01, 0.015], volShrink = [0.6, 0.8];
        const ratioD1Tiers = [0.001, 0.03], volAttack = [2.0, 1.5];
        const wAccFz = 30, wAccBal = 40, wAccVol = 30, wMomD1 = 40, wMomDev = 30, wMomVol = 30;
        const gmsFmt = (v, type) => {
            if (v == null || (typeof v === 'number' && isNaN(v))) return '--';
            if (type === 'pct') return (v * 100).toFixed(2) + '%';
            if (type === 'int') return String(Math.round(v));
            return typeof v === 'number' ? v.toFixed(4) : String(v);
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
                </div>
                <div class="gms-score-detail-section gms-indicators-section">
                    <strong>计算指标细项</strong>
                    <table class="gms-weight-table gms-indicators-table">
                        <tbody>
                            <tr><td>d (20日均价)</td><td>${gmsFmt(sd.d, 'num')}</td><td>周期均价</td></tr>
                            <tr><td>Δ (d₂₀ - d₁)</td><td>${gmsFmt(sd.delta, 'num')}</td><td>宏观位移</td></tr>
                            <tr><td>|Δ/d| (引力粘合)</td><td>${(sd.delta != null && sd.d != null && sd.d !== 0 ? gmsFmt(Math.abs(sd.delta / sd.d), 'pct') : '--')}</td><td>宏观位移相对均价的绝对值</td></tr>
                            <tr><td>Δ/d₂₀ (偏离率)</td><td>${gmsFmt(sd.ratio_d20, 'pct')}</td><td>现价相对周期末价张力</td></tr>
                            <tr><td>Δ/d₁ (突变率)</td><td>${gmsFmt(sd.ratio_d1, 'pct')}</td><td>现价相对周期起点位移</td></tr>
                            <tr><td>Z (上涨天数)</td><td>${gmsFmt(sd.rising_days, 'int')}</td><td>多头天数</td></tr>
                            <tr><td>F (下跌天数)</td><td>${gmsFmt(sd.falling_days, 'int')}</td><td>空头天数</td></tr>
                            <tr><td>量比 (m₂₀/m)</td><td>${gmsFmt(sd.volume_ratio, 'num')}</td><td>放量/地量判断</td></tr>
                            <tr><td>F/Z (数方比)</td><td>${gmsFmt(sd.fz_ratio, 'num')}</td><td>蓄势判断</td></tr>
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
            tbody.innerHTML = '<tr><td colspan="16">暂无数据</td></tr>';
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
                <td>${r.left_buy_signal ? '是' : '否'}</td>
                <td>${r.right_buy_signal ? '是' : '否'}</td>
                <td>${r.sell_signal ? '是' : '否'}</td>
                <td>
                    <button type="button" class="action-link gms-score-detail-toggle" data-row="${index}" title="展开/收起得分明细">得分明细</button>
                </td>
            </tr>
            <tr class="gms-score-detail-row" data-detail-for="${index}" style="display:none;">
                <td colspan="16" class="gms-score-detail-cell">${scoreDetailHtml}</td>
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
}

document.addEventListener('DOMContentLoaded', () => {
    window.gmsTracePage = new StockGMSTracePage();
});

/**
 * URT 策略信号历史页（展示风格对齐 GMS 追溯页）
 */
(function () {
    const apiBase = (typeof Config !== 'undefined' && Config.getApiBaseUrl)
        ? (Config.getApiBaseUrl() || '')
        : '';

    class StockUrtTracePage {
        constructor() {
            const params = new URLSearchParams(window.location.search);
            this.code = (params.get('code') || '').trim();
            this.name = decodeURIComponent(params.get('name') || '');
            this.configId = params.get('config_id') ? Number(params.get('config_id')) : null;
            document.getElementById('stockDisplay').textContent =
                this.code ? `${this.code} ${this.name}` : '--';
            document.getElementById('searchBtn').addEventListener('click', () => this.fetchData());
            document.getElementById('configSelect').addEventListener('change', () => {
                this.configId = Number(document.getElementById('configSelect').value) || null;
                this.fetchData();
            });
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
            if (this.code) this.fetchData();
        }

        async fetchData() {
            const loading = document.getElementById('loadingMsg');
            const empty = document.getElementById('emptyMsg');
            const tbody = document.querySelector('#traceTable tbody');
            loading.style.display = '';
            empty.style.display = 'none';
            tbody.innerHTML = '';
            try {
                const q = new URLSearchParams({ code: this.code, limit: '300' });
                if (this.configId) q.set('config_id', String(this.configId));
                const res = await fetch(`${apiBase}/api/stock/urt-signal-trace?${q}`);
                const json = await res.json();
                const configs = json.configs || [];
                const sel = document.getElementById('configSelect');
                sel.innerHTML = configs.map((c) =>
                    `<option value="${c.id}" ${c.id === json.config_id ? 'selected' : ''}>${c.name}${c.is_default ? ' (默认)' : ''}</option>`
                ).join('');
                this.configId = json.config_id;
                const detail = document.getElementById('detailLink');
                detail.href = `stock_urt_score_detail.html?code=${encodeURIComponent(this.code)}&name=${encodeURIComponent(this.name)}&config_id=${this.configId || ''}`;
                const rows = json.data || [];
                if (!rows.length) {
                    empty.style.display = '';
                    return;
                }
                tbody.innerHTML = rows.map((r, index) => {
                    const pageHref = `stock_urt_score_detail.html?code=${encodeURIComponent(this.code)}&name=${encodeURIComponent(this.name)}&date=${encodeURIComponent(r.date || '')}&config_id=${r.config_id || this.configId || ''}`;
                    let detailHtml = '<div class="gms-score-detail-inner">得分明细组件未加载</div>';
                    if (window.UrtScoreDetail) {
                        detailHtml = window.UrtScoreDetail.buildHtml({
                            ...r,
                            score: r.score,
                            score_detail: r.score_detail,
                            buy_signal: r.buy_signal,
                        });
                    }
                    return `<tr>
                        <td><button type="button" class="gms-op-btn urt-score-detail-toggle" data-row="${index}">明细</button></td>
                        <td>${r.date || '--'}</td>
                        <td class="${r.buy_signal ? 'buy-yes' : ''}">${r.buy_signal ? '是' : '否'}</td>
                        <td>${r.score != null ? Number(r.score).toFixed(1) : '--'}</td>
                        <td>${r.close != null ? Number(r.close).toFixed(2) : '--'}</td>
                        <td>${r.ma20 != null ? Number(r.ma20).toFixed(2) : '--'}</td>
                        <td>${r.yang_count_4 ?? '--'}</td>
                        <td>${r.yang_count_5 ?? '--'}</td>
                        <td>${r.volume_multiple != null ? Number(r.volume_multiple).toFixed(2) : '--'}</td>
                        <td>${r.volume_ratio != null ? Number(r.volume_ratio).toFixed(2) : '--'}</td>
                        <td>${r.turnover_rate != null ? Number(r.turnover_rate).toFixed(2) : '--'}</td>
                        <td><a class="gms-op-btn" href="${pageHref}" target="_blank" rel="noopener">明细页</a></td>
                    </tr>
                    <tr class="gms-score-detail-row" data-detail-for="${index}" style="display:none;">
                        <td colspan="12" class="gms-score-detail-cell">${detailHtml}</td>
                    </tr>`;
                }).join('');
            } catch (e) {
                empty.textContent = '加载失败: ' + (e.message || e);
                empty.style.display = '';
            } finally {
                loading.style.display = 'none';
            }
        }
    }

    document.addEventListener('DOMContentLoaded', () => new StockUrtTracePage());
})();

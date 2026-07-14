/**
 * URT 策略信号历史页
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
                tbody.innerHTML = rows.map((r) => {
                    const detailHref = `stock_urt_score_detail.html?code=${encodeURIComponent(this.code)}&name=${encodeURIComponent(this.name)}&date=${encodeURIComponent(r.date || '')}&config_id=${r.config_id || this.configId || ''}`;
                    return `<tr>
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
                        <td><a href="${detailHref}" target="_blank" rel="noopener">明细</a></td>
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

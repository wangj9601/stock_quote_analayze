/**
 * URT 信号计算明细页（展示风格对齐 GMS 得分明细）
 */
(function () {
    const apiBase = (typeof Config !== 'undefined' && Config.getApiBaseUrl)
        ? (Config.getApiBaseUrl() || '')
        : '';

    async function main() {
        const params = new URLSearchParams(window.location.search);
        const code = (params.get('code') || '').trim();
        const name = decodeURIComponent(params.get('name') || '');
        const date = params.get('date') || '';
        const configId = params.get('config_id') || '';
        const meta = document.getElementById('metaLine');
        const content = document.getElementById('content');
        const stockDisplay = document.getElementById('stockDisplay');
        const traceLink = document.getElementById('traceLink');

        stockDisplay.textContent = code ? `${code} ${name}` : '--';
        traceLink.href = `stock_urt_trace.html?code=${encodeURIComponent(code)}&name=${encodeURIComponent(name)}&config_id=${encodeURIComponent(configId)}`;

        if (!code) {
            meta.textContent = '缺少股票代码';
            return;
        }
        const q = new URLSearchParams({ code });
        if (date) q.set('date', date);
        if (configId) q.set('config_id', configId);
        try {
            const res = await fetch(`${apiBase}/api/stock/urt-score-detail?${q}`);
            const json = await res.json();
            if (!json.success) {
                meta.textContent = json.detail || json.message || '加载失败';
                return;
            }
            meta.textContent = `日期 ${json.date || '--'} · 来源 ${json.source || '--'}`;
            if (window.UrtScoreDetail) {
                content.innerHTML = window.UrtScoreDetail.buildHtml(json);
            } else {
                content.textContent = '得分明细组件未加载';
            }
        } catch (e) {
            meta.textContent = '加载失败: ' + (e.message || e);
        }
    }

    document.addEventListener('DOMContentLoaded', main);
})();

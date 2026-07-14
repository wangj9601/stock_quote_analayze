/**
 * URT 信号计算明细页
 */
(function () {
    const apiBase = (typeof Config !== 'undefined' && Config.getApiBaseUrl)
        ? (Config.getApiBaseUrl() || '')
        : '';

    function fmt(v, digits) {
        if (v == null || v === '') return '--';
        const n = Number(v);
        return Number.isFinite(n) ? n.toFixed(digits) : String(v);
    }

    async function main() {
        const params = new URLSearchParams(window.location.search);
        const code = (params.get('code') || '').trim();
        const name = decodeURIComponent(params.get('name') || '');
        const date = params.get('date') || '';
        const configId = params.get('config_id') || '';
        const meta = document.getElementById('metaLine');
        const content = document.getElementById('content');
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
            const buy = json.buy_signal;
            meta.innerHTML = `${code} ${name || json.name || ''} · 日期 ${json.date || '--'} · 来源 ${json.source || '--'} · ` +
                `买点 <span class="${buy ? 'ok' : 'bad'}">${buy ? '是' : '否'}</span>`;
            const sd = json.score_detail || {};
            const parts = sd.parts || {};
            const fields = json.fields || {};
            let html = `<div class="score-total">总分：${fmt(json.score ?? sd.total, 2)} / 阈值 ${fmt(sd.min_score, 0)}</div>`;
            html += `<h3>分项得分</h3><table class="parts-table"><tbody>`;
            const rows = [
                ['站上 MA20', parts.above_ma20],
                ['连阳', parts.yang],
                ['量能', parts.volume],
                ['换手', parts.turnover],
                ['量比', parts.volume_ratio],
            ];
            for (const [label, p] of rows) {
                if (!p) continue;
                html += `<tr><th>${label}</th><td>得分 ${fmt(p.score, 2)}（满分 ${p.max ?? '--'}）` +
                    `${p.ok != null ? ` · ${p.ok ? '满足' : '不满足'}` : ''}` +
                    `${p.yang_count_4 != null ? ` · 4日阳 ${p.yang_count_4} / 5日阳 ${p.yang_count_5}` : ''}` +
                    `${p.volume_multiple != null ? ` · 倍数 ${fmt(p.volume_multiple, 2)} / 阈值 ${fmt(p.threshold, 2)}` : ''}` +
                    `${p.enabled === false ? ' · 未启用' : ''}</td></tr>`;
            }
            html += `</tbody></table>`;
            html += `<h3>输入与硬筛</h3><table class="fields-table"><tbody>`;
            const fieldPairs = [
                ['开盘', fields.open], ['收盘', fields.close], ['MA20', fields.ma20],
                ['4日阳线数', fields.yang_count_4], ['5日阳线数', fields.yang_count_5],
                ['量能倍数', fields.volume_multiple], ['量比', fields.volume_ratio],
                ['换手率%', fields.turnover_rate],
                ['硬筛通过', fields.filter_ok], ['硬筛说明', fields.filter_reason],
                ['得分达标', fields.score_ok],
            ];
            for (const [k, v] of fieldPairs) {
                if (v === undefined) continue;
                html += `<tr><th>${k}</th><td>${typeof v === 'number' ? fmt(v, 4) : (v == null ? '--' : String(v))}</td></tr>`;
            }
            html += `</tbody></table>`;
            html += `<p><a href="stock_urt_trace.html?code=${encodeURIComponent(code)}&name=${encodeURIComponent(name)}&config_id=${encodeURIComponent(configId || json.config_id || '')}">返回信号历史</a></p>`;
            content.innerHTML = html;
        } catch (e) {
            meta.textContent = '加载失败: ' + (e.message || e);
        }
    }

    document.addEventListener('DOMContentLoaded', main);
})();

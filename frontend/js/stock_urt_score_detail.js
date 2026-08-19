/**
 * URT 信号计算明细页（展示风格对齐 GMS 得分明细）
 */
(function () {
    const apiBase = (typeof Config !== 'undefined' && Config.getApiBaseUrl)
        ? (Config.getApiBaseUrl() || '')
        : '';

    let lastDetail = null;
    let exporting = false;

    function toast(msg, type) {
        if (window.CommonUtils && typeof CommonUtils.showToast === 'function') {
            CommonUtils.showToast(msg, type || 'info');
            return;
        }
        // 轻量兜底
        const el = document.getElementById('metaLine');
        if (el && type === 'error') el.textContent = msg;
        else if (type !== 'success') console.warn(msg);
    }

    function setExportEnabled(ok) {
        const btn = document.getElementById('urtExportPdfBtn');
        if (!btn) return;
        btn.disabled = !ok || exporting;
    }

    async function exportPdf() {
        if (!lastDetail) {
            toast('请先加载信号明细再导出', 'warning');
            return;
        }
        if (exporting) return;
        const btn = document.getElementById('urtExportPdfBtn');
        exporting = true;
        if (btn) {
            btn.disabled = true;
            btn.textContent = '导出中…';
        }
        try {
            if (!window.UrtScoreDetailPdf || typeof UrtScoreDetailPdf.exportFromDetail !== 'function') {
                throw new Error('PDF 导出模块未加载');
            }
            const code = lastDetail.code || '';
            const date = lastDetail.date || '';
            const filename = await UrtScoreDetailPdf.exportFromDetail(lastDetail, {
                filename: `URT信号明细_${code || 'stock'}_${date || 'latest'}.pdf`,
            });
            toast(`已导出 ${filename}`, 'success');
        } catch (e) {
            console.warn('URT 明细 PDF 导出失败', e);
            toast(`导出失败：${(e && e.message) || e}`, 'error');
        } finally {
            exporting = false;
            if (btn) btn.textContent = '导出 PDF';
            setExportEnabled(!!lastDetail);
        }
    }

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
        const exportBtn = document.getElementById('urtExportPdfBtn');

        stockDisplay.textContent = code ? `${code} ${name}` : '--';
        traceLink.href = `stock_urt_trace.html?code=${encodeURIComponent(code)}&name=${encodeURIComponent(name)}&config_id=${encodeURIComponent(configId)}`;
        if (exportBtn) {
            exportBtn.addEventListener('click', () => exportPdf());
            setExportEnabled(false);
        }

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
                lastDetail = null;
                setExportEnabled(false);
                return;
            }
            if (!json.code) json.code = code;
            if (!json.name) json.name = name;
            lastDetail = json;
            const resolvedId = json.config_id != null ? String(json.config_id) : configId;
            const cfgLabel = json.config_name
                || (resolvedId ? `配置#${resolvedId}` : '');
            const alignNote = json.is_effective_config === false
                ? ' · 非生效版本（与日常回测可能不一致）'
                : (json.is_effective_config === true ? ' · 生效版本' : '');
            const staleNote = json.stale
                ? ' · 参数已更新，缓存可能过期（可返回信号历史强制重算）'
                : '';
            meta.textContent =
                `日期 ${json.date || '--'} · 来源 ${json.source || '--'}`
                + (cfgLabel ? ` · ${cfgLabel}` : '')
                + alignNote
                + staleNote;
            // 回写解析后的 config_id，保证「返回信号历史」与当前明细一致
            traceLink.href =
                `stock_urt_trace.html?code=${encodeURIComponent(code)}&name=${encodeURIComponent(name)}`
                + (resolvedId ? `&config_id=${encodeURIComponent(resolvedId)}` : '');
            if (window.UrtScoreDetail) {
                content.innerHTML = window.UrtScoreDetail.buildHtml(json);
            } else {
                content.textContent = '得分明细组件未加载';
            }
            setExportEnabled(true);
        } catch (e) {
            meta.textContent = '加载失败: ' + (e.message || e);
            lastDetail = null;
            setExportEnabled(false);
        }
    }

    document.addEventListener('DOMContentLoaded', main);
})();

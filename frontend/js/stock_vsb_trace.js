/**
 * 3倍量缩量突破 — 信号历史页
 * 请求顺序：① /api/vsb/signals（main.app 直挂，避免子路由双 404）② /api/screening/vsb-signals ③ /api/stock/vsb-signals；仅在上一条 HTTP 404 时尝试下一条。
 */
class StockVsbTracePage {
    constructor() {
        this.currentStockCode = '';
        this.currentStockName = '';
        this.init();
    }

    init() {
        this.loadFromUrl();
        this.bindEvents();
        this.setDefaultDates();
        const recBtn = document.getElementById('vsbRecalcBtn');
        const replayBtn = document.getElementById('vsbReplayBtn');
        if (recBtn) {
            recBtn.disabled = !this.currentStockCode;
        }
        if (replayBtn) {
            replayBtn.disabled = !this.currentStockCode;
        }
        if (this.currentStockCode) {
            this.fetchData();
        }
    }

    loadFromUrl() {
        const params = new URLSearchParams(window.location.search);
        this.currentStockCode = (params.get('code') || '').trim();
        this.currentStockName = params.get('name') || '';
        const disp = document.getElementById('stockDisplay');
        if (disp) {
            disp.textContent = this.currentStockCode
                ? `${this.currentStockCode} ${decodeURIComponent(this.currentStockName || '')}`
                : '--';
        }
    }

    bindEvents() {
        const btn = document.getElementById('searchBtn');
        if (btn) btn.addEventListener('click', () => this.fetchData());
        const rec = document.getElementById('vsbRecalcBtn');
        if (rec) rec.addEventListener('click', () => this.recalculateAndPersist());
        const replay = document.getElementById('vsbReplayBtn');
        if (replay) replay.addEventListener('click', () => this.replayRangeAndPersist());
    }

    setDefaultDates() {
        const today = new Date();
        const start = new Date(today.getTime() - 365 * 24 * 60 * 60 * 1000);
        const sEl = document.getElementById('startDate');
        const eEl = document.getElementById('endDate');
        if (sEl) sEl.value = start.toISOString().slice(0, 10);
        if (eEl) eEl.value = today.toISOString().slice(0, 10);
    }

    getApiBase() {
        let base = (typeof Config !== 'undefined' && Config.getApiBaseUrl)
            ? (Config.getApiBaseUrl() || '')
            : '';
        base = String(base).trim();
        if (base.startsWith(':')) {
            base = `${window.location.protocol}//${window.location.hostname}${base}`;
        }
        return base.replace(/\/$/, '');
    }

    /** 主应用直挂（推荐，与 backend_api.main 内 @app.get 一致） */
    getVsbSignalsListUrlApp() {
        if (typeof Config !== 'undefined' && Config.getApiUrl) {
            return Config.getApiUrl('/api/vsb/signals');
        }
        return `${this.getApiBase()}/api/vsb/signals`;
    }

    /** 与选股同前缀 /api/screening */
    getVsbSignalsListUrlScreening() {
        if (typeof Config !== 'undefined' && Config.getApiUrl) {
            return Config.getApiUrl('/api/screening/vsb-signals');
        }
        return `${this.getApiBase()}/api/screening/vsb-signals`;
    }

    /** 备用：/api/stock（main.py 中 vsb_signal_router 独立挂载，不依赖 screening 子包整表导入成功） */
    getVsbSignalsListUrlStock() {
        if (typeof Config !== 'undefined' && Config.getApiUrl) {
            return Config.getApiUrl('/api/stock/vsb-signals');
        }
        return `${this.getApiBase()}/api/stock/vsb-signals`;
    }

    getVsbRecalculateUrlApp() {
        if (typeof Config !== 'undefined' && Config.getApiUrl) {
            return Config.getApiUrl('/api/vsb/signals/recalculate');
        }
        return `${this.getApiBase()}/api/vsb/signals/recalculate`;
    }

    getVsbRecalculateUrlScreening() {
        if (typeof Config !== 'undefined' && Config.getApiUrl) {
            return Config.getApiUrl('/api/screening/vsb-signals/recalculate');
        }
        return `${this.getApiBase()}/api/screening/vsb-signals/recalculate`;
    }

    getVsbRecalculateUrlStock() {
        if (typeof Config !== 'undefined' && Config.getApiUrl) {
            return Config.getApiUrl('/api/stock/vsb-signals/recalculate');
        }
        return `${this.getApiBase()}/api/stock/vsb-signals/recalculate`;
    }

    /**
     * @returns {{ ok: boolean, json: object, status: number, usedUrl: string }}
     */
    async _fetchVsbSignalsOnce(url) {
        const res = await fetch(url);
        let json = {};
        try {
            json = await res.json();
        } catch (e) {
            json = {};
        }
        const ok = res.ok && json && json.success === true;
        return { ok, json, status: res.status, usedUrl: url };
    }

    /**
     * POST 重算；仅在上一条 HTTP 404 时尝试下一路径。
     */
    async _postRecalculateOnce(url) {
        const res = await fetch(url, { method: 'POST' });
        let json = {};
        try {
            json = await res.json();
        } catch (e) {
            json = {};
        }
        const ok = res.ok && json && json.success === true;
        return { ok, json, status: res.status, usedUrl: url };
    }

    async recalculateAndPersist() {
        const code = this.currentStockCode || (document.getElementById('stockDisplay')?.textContent || '').split(/\s+/)[0];
        if (!code || code === '--') {
            if (window.CommonUtils) CommonUtils.showToast('请先通过选股页进入并带上股票代码', 'warning');
            return;
        }
        const loading = document.getElementById('loadingMsg');
        const empty = document.getElementById('emptyMsg');
        const recBtn = document.getElementById('vsbRecalcBtn');
        if (loading) loading.style.display = 'block';
        if (empty) empty.style.display = 'none';
        if (recBtn) recBtn.disabled = true;

        const qs = new URLSearchParams({ code });
        const nm = decodeURIComponent(this.currentStockName || '').trim();
        if (nm) qs.set('name', nm.slice(0, 80));

        try {
            const qstr = qs.toString();
            const bases = [
                this.getVsbRecalculateUrlApp(),
                this.getVsbRecalculateUrlScreening(),
                this.getVsbRecalculateUrlStock(),
            ];
            let out = { ok: false, status: 404, json: {}, usedUrl: '' };
            for (const b of bases) {
                const url = `${b}?${qstr}`;
                out = await this._postRecalculateOnce(url);
                if (out.ok) break;
                if (out.status !== 404) break;
            }
            if (loading) loading.style.display = 'none';
            if (recBtn) recBtn.disabled = false;

            if (!out.ok) {
                const j = out.json || {};
                const msg = j.message || j.detail || `HTTP ${out.status}`;
                if (window.CommonUtils) CommonUtils.showToast(msg, 'error');
                if (empty) {
                    empty.textContent = `重算失败: ${msg}`;
                    empty.style.display = 'block';
                }
                return;
            }
            const j = out.json;
            const toastType = j.hit ? 'success' : 'warning';
            if (window.CommonUtils) CommonUtils.showToast(j.message || '重算完成', toastType);
            await this.fetchData();
        } catch (e) {
            console.error(e);
            if (loading) loading.style.display = 'none';
            if (recBtn) recBtn.disabled = false;
            if (window.CommonUtils) CommonUtils.showToast(e.message || String(e), 'error');
        }
    }

    async replayRangeAndPersist() {
        const code = this.currentStockCode || (document.getElementById('stockDisplay')?.textContent || '').split(/\s+/)[0];
        if (!code || code === '--') {
            if (window.CommonUtils) CommonUtils.showToast('请先通过选股页进入并带上股票代码', 'warning');
            return;
        }
        const startDate = document.getElementById('startDate')?.value || '';
        const endDate = document.getElementById('endDate')?.value || '';
        if (!startDate || !endDate) {
            if (window.CommonUtils) CommonUtils.showToast('逐日回放需要填写开始日期与结束日期', 'warning');
            return;
        }
        const loading = document.getElementById('loadingMsg');
        const empty = document.getElementById('emptyMsg');
        const recBtn = document.getElementById('vsbRecalcBtn');
        const replayBtn = document.getElementById('vsbReplayBtn');
        if (loading) loading.style.display = 'block';
        if (empty) empty.style.display = 'none';
        if (recBtn) recBtn.disabled = true;
        if (replayBtn) replayBtn.disabled = true;

        const qs = new URLSearchParams({ code });
        const nm = decodeURIComponent(this.currentStockName || '').trim();
        if (nm) qs.set('name', nm.slice(0, 80));
        qs.set('replay_range', 'true');
        qs.set('start_date', startDate);
        qs.set('end_date', endDate);

        try {
            const qstr = qs.toString();
            const bases = [
                this.getVsbRecalculateUrlApp(),
                this.getVsbRecalculateUrlScreening(),
                this.getVsbRecalculateUrlStock(),
            ];
            let out = { ok: false, status: 404, json: {}, usedUrl: '' };
            for (const b of bases) {
                const url = `${b}?${qstr}`;
                out = await this._postRecalculateOnce(url);
                if (out.ok) break;
                if (out.status !== 404) break;
            }
            if (loading) loading.style.display = 'none';
            if (recBtn) recBtn.disabled = false;
            if (replayBtn) replayBtn.disabled = false;

            if (!out.ok) {
                const j = out.json || {};
                const msg = j.message || j.detail || `HTTP ${out.status}`;
                if (window.CommonUtils) CommonUtils.showToast(msg, 'error');
                if (empty) {
                    empty.textContent = `逐日回放失败: ${msg}`;
                    empty.style.display = 'block';
                }
                return;
            }
            const j = out.json;
            const toastType = j.hit ? 'success' : 'warning';
            if (window.CommonUtils) CommonUtils.showToast(j.message || '逐日回放完成', toastType);
            await this.fetchData();
        } catch (e) {
            console.error(e);
            if (loading) loading.style.display = 'none';
            if (recBtn) recBtn.disabled = false;
            if (replayBtn) replayBtn.disabled = false;
            if (window.CommonUtils) CommonUtils.showToast(e.message || String(e), 'error');
        }
    }

    async fetchData() {
        const code = this.currentStockCode || (document.getElementById('stockDisplay')?.textContent || '').split(/\s+/)[0];
        if (!code || code === '--') {
            if (window.CommonUtils) CommonUtils.showToast('请从选股页通过「信号历史」进入并带 code 参数', 'warning');
            return;
        }
        const startDate = document.getElementById('startDate')?.value || '';
        const endDate = document.getElementById('endDate')?.value || '';
        const loading = document.getElementById('loadingMsg');
        const empty = document.getElementById('emptyMsg');
        const tbody = document.querySelector('#vsbTable tbody');
        if (loading) loading.style.display = 'block';
        if (empty) empty.style.display = 'none';
        if (tbody) tbody.innerHTML = '';

        const qs = new URLSearchParams({ code });
        if (startDate) qs.set('start_date', startDate);
        if (endDate) qs.set('end_date', endDate);
        qs.set('limit', '200');

        try {
            const qstr = qs.toString();
            const bases = [
                this.getVsbSignalsListUrlApp(),
                this.getVsbSignalsListUrlScreening(),
                this.getVsbSignalsListUrlStock(),
            ];
            let out = { ok: false, status: 404, json: {}, usedUrl: '' };
            for (const b of bases) {
                const url = `${b}?${qstr}`;
                out = await this._fetchVsbSignalsOnce(url);
                if (out.ok) {
                    break;
                }
                if (out.status !== 404) {
                    break;
                }
            }
            if (!out.ok) {
                const j = out.json || {};
                throw new Error(j.message || j.detail || `HTTP ${out.status}`);
            }
            const rows = out.json.data || [];
            if (loading) loading.style.display = 'none';
            if (rows.length === 0) {
                if (empty) {
                    empty.textContent = '暂无信号记录';
                    empty.style.display = 'block';
                }
                return;
            }
            if (tbody) {
                tbody.innerHTML = rows.map((r) => this.renderRow(r)).join('');
            }
        } catch (e) {
            console.error(e);
            if (loading) loading.style.display = 'none';
            if (empty) {
                empty.textContent = `加载失败: ${e.message || e}`;
                empty.style.display = 'block';
            }
        }
    }

    renderRow(r) {
        const ma = [r.ma5_at_boom, r.ma10_at_boom, r.ma20_at_boom]
            .map((x) => (x != null && !isNaN(Number(x)) ? Number(x).toFixed(2) : '--'))
            .join(' / ');
        const chg = r.current_change_percent != null ? Number(r.current_change_percent).toFixed(2) : '--';
        let remindList = [];
        if (Array.isArray(r.signal_reminders)) {
            remindList = r.signal_reminders;
        } else if (r.signal_reminders_json) {
            try {
                const p = JSON.parse(r.signal_reminders_json);
                if (Array.isArray(p)) remindList = p;
            } catch (e) { /* ignore */ }
        }
        const remindTxt = remindList.length ? remindList.join('；') : '—';
        const buyTxt = (r.buy_signal || '—').replace(/</g, '＜').replace(/>/g, '＞');
        const sc = r.signal_strength != null && !isNaN(Number(r.signal_strength)) ? Number(r.signal_strength) : null;
        const lvl = r.signal_strength_level || '--';
        const strengthCell = sc != null ? `${sc}（${lvl}）` : `--（${lvl}）`;
        return `
            <tr>
                <td>${r.signal_date || '--'}</td>
                <td>${r.boom_date || '--'}</td>
                <td>${r.boom_close != null ? Number(r.boom_close).toFixed(2) : '--'}</td>
                <td>${r.boom_volume_ratio_vs_prev != null ? Number(r.boom_volume_ratio_vs_prev).toFixed(2) : '--'}</td>
                <td>${ma}</td>
                <td>${r.breakout_close != null ? Number(r.breakout_close).toFixed(2) : '--'}</td>
                <td>${r.breakout_volume != null ? r.breakout_volume : '--'}</td>
                <td>${chg}</td>
                <td style="max-width:200px;font-size:12px;" title="${buyTxt}">${buyTxt.length > 36 ? buyTxt.slice(0, 36) + '…' : buyTxt}</td>
                <td>${strengthCell}</td>
                <td style="max-width:240px;font-size:12px;" title="${remindTxt.replace(/"/g, '')}">${remindTxt.length > 48 ? remindTxt.slice(0, 48) + '…' : remindTxt}</td>
                <td>${r.run_search_date || '--'}</td>
            </tr>`;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.vsbTracePage = new StockVsbTracePage();
});

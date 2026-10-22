/**
 * 指数详情页：抬头 + K 线 + 指数分析面板
 */
(function (global) {
    const IndexDetailPage = {
        API_BASE_URL: typeof API_BASE_URL !== 'undefined' ? API_BASE_URL : '',
        code: '',
        chart: null,

        async init() {
            const params = new URLSearchParams(global.location.search || '');
            this.code = (params.get('index') || params.get('code') || '').trim();
            if (!this.code) {
                if (typeof CommonUtils !== 'undefined') {
                    CommonUtils.showToast('缺少指数代码参数 index', 'error');
                }
                return;
            }
            const hidden = document.getElementById('isaIndexCode');
            if (hidden) hidden.value = this.code;

            await this.loadHeader();
            await this.loadChart();
            // 按钮由 IndexAnalysis.init 绑定（读 #isaIndexCode）
            await this.loadAnalysis();
        },

        async loadHeader() {
            const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
            try {
                const resp = await fetchFn(
                    `${this.API_BASE_URL}/api/market/index/${encodeURIComponent(this.code)}`
                );
                const payload = await resp.json().catch(() => ({}));
                const d = (payload && payload.data) || {};
                const title = document.getElementById('indexDetailTitle');
                const codeEl = document.getElementById('indexDetailCode');
                const priceEl = document.getElementById('indexDetailPrice');
                const chEl = document.getElementById('indexDetailChange');
                if (title) title.textContent = d.name || this.code;
                if (codeEl) codeEl.textContent = `${d.code || this.code}${d.ts_code ? ' · ' + d.ts_code : ''}`;
                if (priceEl) {
                    priceEl.textContent = d.current != null ? Number(d.current).toFixed(2) : '--';
                }
                if (chEl) {
                    const pct = d.change_percent;
                    const ch = d.change;
                    const cls = pct > 0 ? 'positive' : pct < 0 ? 'negative' : '';
                    chEl.className = 'index-detail-change ' + cls;
                    const chText = ch != null ? Number(ch).toFixed(2) : '--';
                    const pctText = pct != null
                        ? `${Number(pct) > 0 ? '+' : ''}${Number(pct).toFixed(2)}%`
                        : '';
                    chEl.textContent = `${chText} ${pctText}`.trim();
                }
                document.title = `${d.name || this.code} · 指数分析`;
            } catch (e) {
                console.error('[IndexDetail] header', e);
            }
        },

        async loadChart() {
            const el = document.getElementById('indexDetailChart');
            if (!el || typeof echarts === 'undefined') return;
            const fetchFn = typeof authFetch === 'function' ? authFetch : fetch;
            try {
                const resp = await fetchFn(
                    `${this.API_BASE_URL}/api/market/index/${encodeURIComponent(this.code)}/kline?limit=120`
                );
                const payload = await resp.json().catch(() => ({}));
                const bars = (((payload || {}).data || {}).bars) || [];
                if (!bars.length) {
                    el.innerHTML = '<p class="isa-empty-soft">暂无指数日线</p>';
                    return;
                }
                const dates = bars.map((b) => b.date);
                const ohlc = bars.map((b) => [b.open, b.close, b.low, b.high]);
                const ink = '#d9e2ec';
                const inkMuted = '#8b9aab';
                const rise = '#c23b3b';
                const fall = '#2f9e6b';
                const fmt = (v) => {
                    const n = Number(v);
                    return Number.isFinite(n) ? n.toFixed(2) : '--';
                };
                if (!this.chart) this.chart = echarts.init(el);
                this.chart.setOption({
                    backgroundColor: 'transparent',
                    animationDuration: 280,
                    grid: { left: 56, right: 18, top: 28, bottom: 36 },
                    tooltip: {
                        trigger: 'axis',
                        axisPointer: {
                            type: 'cross',
                            crossStyle: { color: 'rgba(217, 226, 236, 0.35)' },
                            lineStyle: { color: 'rgba(217, 226, 236, 0.35)', type: 'dashed' },
                        },
                        backgroundColor: 'rgba(22, 28, 36, 0.96)',
                        borderWidth: 1,
                        borderColor: 'rgba(217, 226, 236, 0.22)',
                        textStyle: { color: ink, fontSize: 12 },
                        confine: true,
                        formatter: (params) => {
                            const p = Array.isArray(params) ? params[0] : params;
                            if (!p) return '';
                            // axis 触发时 value 常为 [dataIndex, open, close, low, high]
                            const raw = Array.isArray(p.value)
                                ? p.value
                                : (Array.isArray(p.data) ? p.data : []);
                            let open;
                            let close;
                            let low;
                            let high;
                            if (raw.length >= 5) {
                                open = raw[1];
                                close = raw[2];
                                low = raw[3];
                                high = raw[4];
                            } else {
                                open = raw[0];
                                close = raw[1];
                                low = raw[2];
                                high = raw[3];
                            }
                            const up = Number(close) >= Number(open);
                            const tone = up ? rise : fall;
                            return [
                                `<div style="font-weight:600;margin-bottom:6px;color:${ink}">${p.name || ''}</div>`,
                                `<div style="color:${inkMuted}">开 <span style="color:${ink}">${fmt(open)}</span></div>`,
                                `<div style="color:${inkMuted}">收 <span style="color:${tone}">${fmt(close)}</span></div>`,
                                `<div style="color:${inkMuted}">低 <span style="color:${ink}">${fmt(low)}</span></div>`,
                                `<div style="color:${inkMuted}">高 <span style="color:${ink}">${fmt(high)}</span></div>`,
                            ].join('');
                        },
                    },
                    xAxis: {
                        type: 'category',
                        data: dates,
                        axisLine: { lineStyle: { color: 'rgba(217, 226, 236, 0.28)' } },
                        axisLabel: { color: inkMuted, fontSize: 11 },
                        axisTick: { show: false },
                    },
                    yAxis: {
                        scale: true,
                        axisLine: { show: false },
                        axisLabel: { color: inkMuted, fontSize: 11 },
                        splitLine: { lineStyle: { color: 'rgba(217, 226, 236, 0.08)' } },
                    },
                    series: [{
                        type: 'candlestick',
                        name: '日线',
                        data: ohlc,
                        itemStyle: {
                            color: rise,
                            color0: fall,
                            borderColor: rise,
                            borderColor0: fall,
                        },
                    }],
                });
                if (!this._chartResizeBound) {
                    this._chartResizeBound = true;
                    global.addEventListener('resize', () => {
                        if (this.chart) this.chart.resize();
                    });
                }
            } catch (e) {
                console.error('[IndexDetail] chart', e);
                el.innerHTML = '<p class="isa-empty-soft">K线加载失败</p>';
            }
        },

        async loadAnalysis() {
            if (typeof IndexAnalysisPanel === 'undefined') {
                await this._loadScript('js/index_analysis_panel.js');
            }
            const dateEl = document.getElementById('isaTradeDate');
            await IndexAnalysisPanel.mountAndRun(null, {
                code: this.code,
                date: (dateEl && dateEl.value) || '',
                useRealtime: false,
            });
        },

        async reloadAnalysis(useRealtime) {
            if (typeof IndexAnalysis === 'undefined') {
                await this.loadAnalysis();
                return;
            }
            const dateEl = document.getElementById('isaTradeDate');
            await IndexAnalysis.run({
                code: this.code,
                date: (dateEl && dateEl.value) || '',
                useRealtime: !!useRealtime,
            });
        },

        _loadScript(src) {
            return new Promise((resolve, reject) => {
                const el = document.createElement('script');
                el.src = src + (src.indexOf('?') >= 0 ? '&' : '?') + 'v=' + Date.now();
                el.onload = () => resolve();
                el.onerror = () => reject(new Error('load ' + src));
                document.body.appendChild(el);
            });
        },
    };

    document.addEventListener('DOMContentLoaded', () => {
        IndexDetailPage.init();
    });

    global.IndexDetailPage = IndexDetailPage;
})(typeof window !== 'undefined' ? window : globalThis);

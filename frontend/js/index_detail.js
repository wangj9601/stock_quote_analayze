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
                    el.innerHTML = '<p class="muted" style="padding:1rem">暂无指数日线</p>';
                    return;
                }
                const dates = bars.map((b) => b.date);
                const ohlc = bars.map((b) => [b.open, b.close, b.low, b.high]);
                if (!this.chart) this.chart = echarts.init(el);
                this.chart.setOption({
                    backgroundColor: 'transparent',
                    grid: { left: 48, right: 16, top: 24, bottom: 32 },
                    tooltip: { trigger: 'axis' },
                    xAxis: { type: 'category', data: dates, axisLine: { lineStyle: { color: '#555' } } },
                    yAxis: { scale: true, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } } },
                    series: [{
                        type: 'candlestick',
                        data: ohlc,
                        itemStyle: {
                            color: '#e74c3c',
                            color0: '#2ecc71',
                            borderColor: '#e74c3c',
                            borderColor0: '#2ecc71',
                        },
                    }],
                });
                global.addEventListener('resize', () => {
                    if (this.chart) this.chart.resize();
                });
            } catch (e) {
                console.error('[IndexDetail] chart', e);
                el.innerHTML = '<p class="muted" style="padding:1rem">K线加载失败</p>';
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

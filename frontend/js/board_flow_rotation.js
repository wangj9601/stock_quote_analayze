// 收盘行业资金气泡 + 相对轮动（拖尾、回放）
(function () {
    const QUADRANTS = {
        leading: { name: '领先', color: '#d61f28' },
        weakening: { name: '转弱', color: '#c9a227' },
        lagging: { name: '落后', color: '#0f9d5c' },
        improving: { name: '改善', color: '#6f8cff' },
        neutral: { name: '中性', color: '#8b9aab' },
    };

    function formatYi(yi) {
        const number = Number(yi);
        if (!Number.isFinite(number)) return '--';
        const sign = number > 0 ? '+' : '';
        if (Math.abs(number) >= 1) return `${sign}${number.toFixed(2)}亿`;
        return `${sign}${(number * 10000).toFixed(0)}万`;
    }

    function bubbleSize(yi) {
        const mag = Math.abs(Number(yi) || 0);
        const size = 10 + 13 * Math.log10(1 + mag);
        return Math.max(10, Math.min(52, size));
    }

    function formatPercent(value) {
        const number = Number(value);
        if (!Number.isFinite(number)) return '--';
        const sign = number > 0 ? '+' : '';
        return `${sign}${number.toFixed(2)}%`;
    }

    const chartTheme = {
        backgroundColor: 'transparent',
        textStyle: { color: '#d9e2ec' },
        tooltip: {
            backgroundColor: 'rgba(22, 28, 36, 0.96)',
            borderColor: 'rgba(217, 226, 236, 0.22)',
            textStyle: { color: '#d9e2ec', fontSize: 12 },
            confine: true,
        },
    };

    Object.assign(MarketsPage, {
        fundBubblePayload: null,
        fundBubbleChart: null,
        rotationPayload: null,
        rotationChart: null,
        _rotationDates: [],
        _rotationIndex: 0,
        _rotationPlaying: false,
        _rotationTimer: null,
        _flowBound: false,

        bindFlowRotation() {
            if (this._flowBound) return;
            this._flowBound = true;
            const refreshBubbles = document.getElementById('fundBubbleRefreshBtn');
            if (refreshBubbles) {
                refreshBubbles.addEventListener('click', () => this.loadFundBubbles());
            }
            const refreshRotation = document.getElementById('rotationRefreshBtn');
            if (refreshRotation) {
                refreshRotation.addEventListener('click', () => this.loadRotation());
            }
            const play = document.getElementById('rotationPlayBtn');
            if (play) {
                play.addEventListener('click', () => this.toggleRotationPlayback());
            }
            const trail = document.getElementById('rotationTrail');
            if (trail) {
                trail.addEventListener('change', () => this.renderRotationFrame());
            }
            const slider = document.getElementById('rotationSlider');
            if (slider) {
                slider.addEventListener('input', () => {
                    this.stopRotationPlayback();
                    this._rotationIndex = Number(slider.value) || 0;
                    this.renderRotationFrame();
                    this._syncRotationPlayButton();
                });
            }
            window.addEventListener('resize', () => {
                if (this.fundBubbleChart) this.fundBubbleChart.resize();
                if (this.rotationChart) this.rotationChart.resize();
            });
        },

        async loadFundBubbles() {
            const status = document.getElementById('fundBubbleStatus');
            const meta = document.getElementById('fundBubbleMeta');
            if (status) status.textContent = '正在加载最新交易日的行业资金流…';
            if (meta) meta.textContent = '';
            try {
                if (typeof ensureEchartsLoaded === 'function') await ensureEchartsLoaded();
                if (typeof echarts === 'undefined') throw new Error('图表组件未加载');
                const response = await fetch(`${this.API_BASE_URL}/api/market/fund-bubbles?board_kind=${this._boardKindQuery()}`);
                const result = await response.json();
                if (!response.ok || !result.success) {
                    throw new Error(result.message || '获取行业资金气泡失败');
                }
                this.fundBubblePayload = result.data || { items: [] };
                if (this.currentTab === 'fund-bubbles') this.renderFundBubbles();
            } catch (error) {
                console.error('行业资金气泡加载失败:', error);
                if (status) status.textContent = '行业资金气泡加载失败，请稍后刷新。';
            }
        },

        renderFundBubbles() {
            const el = document.getElementById('fundBubbleChart');
            const status = document.getElementById('fundBubbleStatus');
            const meta = document.getElementById('fundBubbleMeta');
            const payload = this.fundBubblePayload || { items: [] };
            if (!el || typeof echarts === 'undefined') return;
            const items = payload.items || [];
            if (meta) {
                const date = payload.trade_date || '无数据';
                const label = this._boardKindLabel(payload.board_kind);
                meta.textContent = `${date} · ${payload.board_count || 0} 个${label} · 流入 ${payload.in_count || 0} · 流出 ${payload.out_count || 0}`;
            }
            if (!items.length) {
                if (this.fundBubbleChart) this.fundBubbleChart.clear();
                if (status) status.textContent = payload.note || '暂无行业资金流。';
                return;
            }
            const labeled = new Set(
                items.slice().sort((a, b) => Math.abs(b.main_net_yi) - Math.abs(a.main_net_yi))
                    .slice(0, 12)
                    .map((item) => item.board_code)
            );
            const ordered = items.slice().sort(
                (a, b) => Math.abs(a.main_net_yi) - Math.abs(b.main_net_yi)
            );
            if (!this.fundBubbleChart) {
                this.fundBubbleChart = echarts.init(el);
                this.fundBubbleChart.on('click', (params) => {
                    const data = (params && params.data) || {};
                    if (!data.board_code) return;
                    const kind = (this.fundBubblePayload && this.fundBubblePayload.board_kind) || this._boardKindQuery();
                    this.showSectorDetail(data.name, data.board_code, 'tonghuashun', kind);
                });
            }
            const axis = {
                nameTextStyle: { color: '#8b9aab', fontSize: 12 },
                axisLabel: { color: '#8b9aab' },
                axisLine: { lineStyle: { color: 'rgba(217,226,236,0.25)' } },
                splitLine: { lineStyle: { color: 'rgba(217,226,236,0.08)' } },
            };
            this.fundBubbleChart.setOption({
                ...chartTheme,
                grid: { left: 58, right: 28, top: 36, bottom: 46 },
                tooltip: {
                    ...chartTheme.tooltip,
                    trigger: 'item',
                    formatter: (params) => {
                        const data = params.data || {};
                        const yi = (params.value || [])[1];
                        const change = (params.value || [])[0];
                        const trap = change > 0 && yi < 0 ? '<br/>上涨但主力净流出' : '';
                        return [
                            data.name,
                            `涨跌幅 ${formatPercent(change)}`,
                            `主力净流入 ${formatYi(yi)}`,
                        ].join('<br/>') + trap;
                    },
                },
                dataZoom: [
                    {
                        type: 'inside',
                        xAxisIndex: 0,
                        filterMode: 'none',
                        zoomOnMouseWheel: true,
                        moveOnMouseMove: true,
                        moveOnMouseWheel: false,
                    },
                    {
                        type: 'inside',
                        yAxisIndex: 0,
                        filterMode: 'none',
                        zoomOnMouseWheel: true,
                        moveOnMouseMove: true,
                        moveOnMouseWheel: false,
                    },
                ],
                xAxis: {
                    ...axis,
                    type: 'value',
                    name: '涨跌幅 %',
                    nameLocation: 'middle',
                    nameGap: 28,
                    scale: true,
                },
                yAxis: {
                    ...axis,
                    type: 'value',
                    name: '净流入（亿）',
                    nameLocation: 'end',
                    nameGap: 10,
                    scale: true,
                },
                series: [{
                    type: 'scatter',
                    data: ordered.map((item) => {
                        const trap = item.change_percent > 0 && item.main_net_yi < 0;
                        const color = item.direction === 'in'
                            ? '#d61f28'
                            : (item.direction === 'out' ? '#0f9d5c' : '#8b9aab');
                        return {
                            name: item.board_name,
                            board_code: item.board_code,
                            value: [item.change_percent, item.main_net_yi],
                            itemStyle: {
                                color,
                                borderColor: trap ? '#f7fafc' : 'transparent',
                                borderWidth: trap ? 1.5 : 0,
                                opacity: 0.78,
                            },
                        };
                    }),
                    symbolSize: (value) => bubbleSize(value[1]),
                    emphasis: { focus: 'self', scale: 1.2 },
                    label: {
                        show: true,
                        color: '#f7fafc',
                        fontSize: 11,
                        formatter: (params) => {
                            const data = params.data || {};
                            if (!labeled.has(data.board_code)) return '';
                            return `${data.name}\n${formatYi((params.value || [])[1])}`;
                        },
                    },
                    labelLayout: { hideOverlap: true },
                    markLine: {
                        silent: true,
                        symbol: 'none',
                        label: { show: false },
                        lineStyle: { color: 'rgba(217,226,236,0.35)', type: 'dashed' },
                        data: [{ xAxis: 0 }, { yAxis: 0 }],
                    },
                }],
            }, true);
            this.fundBubbleChart.resize();
            if (status) {
                const label = this._boardKindLabel(payload.board_kind);
                status.textContent = `红为净流入，绿为净流出。白边是上涨但资金流出。同一天多数${label}的涨跌和资金流接近，会挤在一起；滚轮放大，拖动平移。点击气泡看详情。`;
            }
        },

        async loadRotation() {
            const status = document.getElementById('rotationStatus');
            const meta = document.getElementById('rotationMeta');
            this.stopRotationPlayback();
            if (status) status.textContent = '正在计算行业相对沪深300的轮动…';
            if (meta) meta.textContent = '';
            try {
                if (typeof ensureEchartsLoaded === 'function') await ensureEchartsLoaded();
                if (typeof echarts === 'undefined') throw new Error('图表组件未加载');
                const response = await fetch(`${this.API_BASE_URL}/api/market/rotation?window=10&lookback=120&board_kind=${this._boardKindQuery()}`);
                const result = await response.json();
                if (!response.ok || !result.success) {
                    throw new Error(result.message || '获取相对轮动失败');
                }
                this.rotationPayload = result.data || { dates: [], boards: [] };
                this._rotationDates = (this.rotationPayload.dates || []).slice();
                this._rotationIndex = Math.max(0, this._rotationDates.length - 1);
                if (this.currentTab === 'rotation') this.renderRotationFrame();
            } catch (error) {
                console.error('相对轮动加载失败:', error);
                if (status) status.textContent = '相对轮动加载失败，请稍后刷新。';
            }
        },

        _rotationTrailLength() {
            const select = document.getElementById('rotationTrail');
            const value = Number(select && select.value);
            return value >= 2 ? value : 5;
        },

        _rotationSpeed() {
            const select = document.getElementById('rotationSpeed');
            const value = Number(select && select.value);
            return value > 0 ? value : 1;
        },

        stopRotationPlayback() {
            this._rotationPlaying = false;
            if (this._rotationTimer) {
                clearTimeout(this._rotationTimer);
                this._rotationTimer = null;
            }
            this._syncRotationPlayButton();
        },

        _syncRotationPlayButton() {
            const btn = document.getElementById('rotationPlayBtn');
            if (!btn) return;
            const dates = this._rotationDates || [];
            const atEnd = !dates.length || this._rotationIndex >= dates.length - 1;
            if (this._rotationPlaying) btn.textContent = '暂停';
            else if (atEnd) btn.textContent = '回放';
            else btn.textContent = '继续';
        },

        toggleRotationPlayback() {
            const dates = this._rotationDates || [];
            if (!dates.length) return;
            if (this._rotationPlaying) {
                this.stopRotationPlayback();
                return;
            }
            if (this._rotationIndex >= dates.length - 1) {
                this._rotationIndex = 0;
                this.renderRotationFrame();
            }
            this._rotationPlaying = true;
            this._syncRotationPlayButton();
            const tick = () => {
                if (!this._rotationPlaying) return;
                if (this._rotationIndex >= dates.length - 1) {
                    this.stopRotationPlayback();
                    return;
                }
                this._rotationIndex += 1;
                this.renderRotationFrame();
                this._rotationTimer = setTimeout(tick, Math.round(650 / this._rotationSpeed()));
            };
            this._rotationTimer = setTimeout(tick, Math.round(650 / this._rotationSpeed()));
        },

        renderRotationFrame() {
            const el = document.getElementById('rotationChart');
            const status = document.getElementById('rotationStatus');
            const meta = document.getElementById('rotationMeta');
            const slider = document.getElementById('rotationSlider');
            const payload = this.rotationPayload || { dates: [], boards: [] };
            const dates = this._rotationDates || [];
            if (!el || typeof echarts === 'undefined') return;
            if (!dates.length || !(payload.boards || []).length) {
                if (this.rotationChart) this.rotationChart.clear();
                if (slider) {
                    slider.max = 0;
                    slider.value = 0;
                }
                if (meta) meta.textContent = '';
                if (status) status.textContent = payload.note || '暂无相对轮动数据。';
                this._syncRotationPlayButton();
                return;
            }
            const index = Math.min(Math.max(this._rotationIndex, 0), dates.length - 1);
            this._rotationIndex = index;
            const cursor = dates[index];
            const trail = this._rotationTrailLength();
            const visible = [];
            (payload.boards || []).forEach((board) => {
                const points = (board.points || []).filter((point) => point.trade_date <= cursor);
                const slice = points.slice(-trail);
                if (!slice.length) return;
                visible.push({ board, slice });
            });
            let minX = 100;
            let maxX = 100;
            let minY = 100;
            let maxY = 100;
            visible.forEach(({ slice }) => {
                slice.forEach((point) => {
                    minX = Math.min(minX, point.rs_ratio);
                    maxX = Math.max(maxX, point.rs_ratio);
                    minY = Math.min(minY, point.rs_momentum);
                    maxY = Math.max(maxY, point.rs_momentum);
                });
            });
            const padX = Math.max(0.8, (maxX - minX) * 0.12);
            const padY = Math.max(0.8, (maxY - minY) * 0.12);
            minX -= padX;
            maxX += padX;
            minY -= padY;
            maxY += padY;
            if (slider) {
                slider.max = String(dates.length - 1);
                slider.value = String(index);
            }
            if (meta) {
                const bench = payload.benchmark_name || '沪深300';
                const label = this._boardKindLabel(payload.board_kind);
                meta.textContent = `${cursor} · 相对${bench} · 平滑${payload.window || 10}日 · 拖尾${trail}日 · ${visible.length}个${label}`;
            }
            if (!this.rotationChart) {
                this.rotationChart = echarts.init(el);
                this.rotationChart.on('click', (params) => {
                    if (!params || !params.seriesId || params.seriesId === 'guides') return;
                    const kind = (this.rotationPayload && this.rotationPayload.board_kind) || this._boardKindQuery();
                    this.showSectorDetail(params.seriesName, params.seriesId, 'tonghuashun', kind);
                });
            }
            const axis = {
                nameTextStyle: { color: '#8b9aab', fontSize: 12 },
                axisLabel: {
                    color: '#8b9aab',
                    formatter: (value) => {
                        const number = Number(value);
                        return Number.isFinite(number) ? number.toFixed(1) : value;
                    },
                },
                axisLine: { lineStyle: { color: 'rgba(217,226,236,0.25)' } },
                splitLine: { lineStyle: { color: 'rgba(217,226,236,0.08)' } },
            };
            const series = [{
                id: 'guides',
                type: 'line',
                data: [],
                silent: true,
                tooltip: { show: false },
                markLine: {
                    silent: true,
                    symbol: 'none',
                    label: { show: false },
                    lineStyle: { color: 'rgba(217,226,236,0.35)' },
                    data: [{ xAxis: 100 }, { yAxis: 100 }],
                },
                markArea: {
                    silent: true,
                    label: { color: 'rgba(217,226,236,0.45)', fontSize: 12 },
                    data: [
                        [
                            { name: '改善', xAxis: minX, yAxis: 100, itemStyle: { color: 'rgba(111,140,255,0.08)' } },
                            { xAxis: 100, yAxis: maxY },
                        ],
                        [
                            { name: '领先', xAxis: 100, yAxis: 100, itemStyle: { color: 'rgba(214,31,40,0.08)' } },
                            { xAxis: maxX, yAxis: maxY },
                        ],
                        [
                            { name: '落后', xAxis: minX, yAxis: minY, itemStyle: { color: 'rgba(15,157,92,0.08)' } },
                            { xAxis: 100, yAxis: 100 },
                        ],
                        [
                            { name: '转弱', xAxis: 100, yAxis: minY, itemStyle: { color: 'rgba(201,162,39,0.08)' } },
                            { xAxis: maxX, yAxis: 100 },
                        ],
                    ],
                },
            }];
            visible.forEach(({ board, slice }) => {
                const head = slice[slice.length - 1];
                const tone = QUADRANTS[head.quadrant] || QUADRANTS.neutral;
                series.push({
                    id: board.board_code,
                    name: board.board_name,
                    type: 'line',
                    data: slice.map((point) => [point.rs_ratio, point.rs_momentum, point.quadrant]),
                    showSymbol: true,
                    symbol: 'circle',
                    symbolSize: (value, params) => (params.dataIndex === slice.length - 1 ? 11 : 5),
                    lineStyle: { width: 1.6, color: tone.color },
                    itemStyle: { color: tone.color },
                    endLabel: {
                        show: true,
                        formatter: () => board.board_name,
                        color: '#d9e2ec',
                        fontSize: 11,
                    },
                    labelLayout: { hideOverlap: true },
                    tooltip: {
                        formatter: (params) => {
                            const ratio = (params.value || [])[0];
                            const momentum = (params.value || [])[1];
                            const key = (params.value || [])[2];
                            const name = (QUADRANTS[key] || QUADRANTS.neutral).name;
                            return [
                                params.seriesName,
                                `相对强弱 ${ratio}`,
                                `相对动量 ${momentum}`,
                                name,
                            ].join('<br/>');
                        },
                    },
                });
            });
            this.rotationChart.setOption({
                ...chartTheme,
                animation: false,
                grid: { left: 56, right: 28, top: 24, bottom: 46 },
                xAxis: {
                    ...axis,
                    type: 'value',
                    min: minX,
                    max: maxX,
                    name: '相对强弱',
                    nameLocation: 'middle',
                    nameGap: 28,
                },
                yAxis: {
                    ...axis,
                    type: 'value',
                    min: minY,
                    max: maxY,
                    name: '相对动量',
                    nameLocation: 'middle',
                    nameGap: 40,
                },
                series,
            }, true);
            this.rotationChart.resize();
            if (status) {
                status.textContent = '拖尾是最近几个交易日的路径。回放从这段行情的起点走到最新收盘。点击线条看板块详情。';
            }
            this._syncRotationPlayButton();
        },
    });

    document.addEventListener('DOMContentLoaded', () => {
        if (typeof MarketsPage !== 'undefined' && MarketsPage.bindFlowRotation) {
            MarketsPage.bindFlowRotation();
        }
    });
})();

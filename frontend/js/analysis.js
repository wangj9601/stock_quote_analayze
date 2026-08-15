// 分析页面功能模块
const AnalysisPage = {
    currentTab: 'board-analysis',
    currentStockCode: '', // 当前分析的股票代码

    // 初始化
    init() {
        this.bindEvents();
        if (window.BoardAnalysis) BoardAnalysis.init();
        if (window.LeaderMidAnalysis) LeaderMidAnalysis.init();
        if (window.KdeLevelsTool) KdeLevelsTool.init();
        if (window.StockMultiStrategy) StockMultiStrategy.init();
        const initialTab = this.resolveInitialTab();
        if (initialTab && initialTab !== this.currentTab) {
            const tabBtn = document.querySelector(`.analysis-tab[data-tab="${initialTab}"]`);
            if (tabBtn) {
                this.switchTab(initialTab);
                this.updateActiveTab(tabBtn);
            } else {
                this.loadTabData(this.currentTab);
            }
        } else {
            this.loadTabData(this.currentTab);
        }
        this.drawFundFlowChart();
        this.startDataUpdate();

        // 确保搜索弹窗隐藏
        const searchModal = document.getElementById('searchModal');
        if (searchModal) {
            searchModal.classList.remove('show');
        }
    },

    resolveInitialTab() {
        try {
            const params = new URLSearchParams(window.location.search || '');
            const tab = (params.get('tab') || '').trim();
            if (tab && document.getElementById(tab)) return tab;
            const hash = (window.location.hash || '').replace(/^#/, '').trim();
            if (hash && document.getElementById(hash)) return hash;
        } catch (e) { /* ignore */ }
        return null;
    },

    // 绑定事件
    bindEvents() {
        // 分析标签切换
        document.querySelectorAll('.analysis-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                this.switchTab(tab.dataset.tab);
                this.updateActiveTab(tab);
            });
        });

        // 技术工具按钮
        document.querySelectorAll('.tool-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const card = e.target.closest('.tool-card');
                if (!card) return;
                const action = btn.getAttribute('data-tool-action')
                    || card.getAttribute('data-tool')
                    || '';
                const toolName = (card.querySelector('h3') || {}).textContent || '';
                this.useTechnicalTool(toolName, action);
            });
        });

        // 报告过滤器
        document.querySelectorAll('.filter-select').forEach(select => {
            select.addEventListener('change', () => {
                this.filterReports();
            });
        });

        // 报告点击事件
        document.addEventListener('click', (e) => {
            if (e.target.closest('.report-item')) {
                const reportTitle = e.target.closest('.report-item').querySelector('h4').textContent;
                this.openReport(reportTitle);
            }
        });
    },

    // 切换标签
    switchTab(tabId) {
        this.currentTab = tabId;

        // 隐藏所有面板
        document.querySelectorAll('.tab-panel').forEach(panel => {
            panel.classList.remove('active');
        });

        // 显示目标面板
        const targetPanel = document.getElementById(tabId);
        if (targetPanel) {
            targetPanel.classList.add('active');
        }

        // 根据标签加载相应数据
        this.loadTabData(tabId);
    },

    // 更新活动标签
    updateActiveTab(activeTab) {
        document.querySelectorAll('.analysis-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        activeTab.classList.add('active');
    },

    // 加载标签数据
    loadTabData(tabId) {
        switch (tabId) {
            case 'board-analysis':
                break;
            case 'leader-mid':
                if (window.LeaderMidAnalysis) LeaderMidAnalysis.ensureCatalogs();
                break;
            case 'stock-ai':
                if (window.StockMultiStrategy) {
                    StockMultiStrategy.loadWatchlistOptions();
                    StockMultiStrategy.bootstrapFromUrl();
                }
                break;
            case 'market-analysis':
                this.loadMarketAnalysis();
                break;
            case 'technical-tools':
                this.loadTechnicalTools();
                break;
            case 'strategy':
                this.loadStrategy();
                break;
            case 'reports':
                this.loadReports();
                break;
        }
    },

    // 执行快速分析
    async performQuickAnalysis() {
        const stockInput = document.querySelector('.stock-input');
        const query = stockInput.value.trim();

        if (!query) {
            CommonUtils.showToast('请输入股票代码或名称', 'warning');
            return;
        }

        // 解析出股票代码（处理“000001 平安银行”这种格式）
        let stockCode = query;
        if (query.includes(' ')) {
            stockCode = query.split(' ')[0];
        }

        // 保存当前分析的股票代码
        this.currentStockCode = stockCode;

        // 显示分析结果
        await this.showAnalysisResult(stockCode);

        // 如果当前在分析报告标签页，自动刷新行情
        if (this.currentTab === 'reports') {
            this.loadReports();
        }
    },

    // 显示分析结果
    async showAnalysisResult(stockCode) {
        const resultDiv = document.getElementById('analysisResult');

        // 显示加载动画
        resultDiv.innerHTML = `
            <div style="text-align: center; color: #6b7280; padding: 3rem;">
                <div class="loading-spinner" style="font-size: 2.5rem; margin-bottom: 1rem; animation: rotate 2s linear infinite;">⏳</div>
                <p style="font-size: 1.1rem;">正在调用 Gemini AI 引擎深度分析 ${stockCode}...</p>
                <p style="font-size: 0.85rem; color: #9ca3af; margin-top: 0.5rem;">分析包含：技术指标、趋势预测、压力位及 AI 见解</p>
            </div>
            <style>
                @keyframes rotate { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
            </style>
        `;

        try {
            const url = `${API_BASE_URL}/api/analysis/stock/${stockCode}`;
            const resp = await authFetch(url);

            if (!resp.ok) {
                const errorData = await resp.json();
                throw new Error(errorData.message || '分析请求失败');
            }

            const result = await resp.json();
            if (!result.success && !result.data) {
                throw new Error(result.message || '获取分析结果失败');
            }

            const data = result.data;
            const rec = data.trading_recommendation || {};
            const pred = data.price_prediction || {};
            const ai = data.ai_insight || 'AI 分析暂时不可用';

            // 格式化 AI 文本 (处理换行)
            const formattedAiInsight = ai.replace(/\n/g, '<br>');

            resultDiv.innerHTML = `
                <div class="analysis-result-content" style="padding: 1.5rem; animation: fadeIn 0.5s ease-out;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; border-bottom: 1px solid #f1f5f9; padding-bottom: 1rem;">
                        <div>
                            <h3 style="font-size: 1.4rem; font-weight: 700; color: #1e293b; margin-bottom: 4px;">${stockCode} 智能分析报告</h3>
                            <div style="font-size: 0.85rem; color: #64748b;">分析时间：${data.analysis_time}</div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 2.5rem; font-weight: 800; color: ${rec.strength > 75 ? '#16a34a' : rec.strength > 50 ? '#f59e0b' : '#dc2626'}; line-height: 1;">${Math.round(rec.strength || 0)}<span style="font-size: 1rem; font-weight: 500;">分</span></div>
                            <div style="font-size: 0.85rem; color: #64748b; margin-top: 5px;">多空强度</div>
                        </div>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 1.5rem;">
                        <div style="background: #f8fafc; padding: 1.2rem; border-radius: 10px; border: 1px solid #f1f5f9;">
                            <div style="font-size: 0.85rem; color: #64748b; margin-bottom: 0.5rem;">投资建议</div>
                            <div style="font-size: 1.25rem; font-weight: 700; color: ${rec.action === 'buy' ? '#16a34a' : rec.action === 'sell' ? '#dc2626' : '#64748b'};">
                                ${rec.action === 'buy' ? '强烈建议买入' : rec.action === 'sell' ? '建议减持/离场' : '建议持股观望'}
                            </div>
                        </div>
                        <div style="background: #f8fafc; padding: 1.2rem; border-radius: 10px; border: 1px solid #f1f5f9;">
                            <div style="font-size: 0.85rem; color: #64748b; margin-bottom: 0.5rem;">风险等级</div>
                            <div style="font-size: 1.25rem; font-weight: 700; color: ${rec.risk_level === 'low' ? '#16a34a' : rec.risk_level === 'medium' ? '#f59e0b' : '#dc2626'};">
                                ${rec.risk_level === 'low' ? '低风险' : rec.risk_level === 'medium' ? '中等风险' : '高风险'}
                            </div>
                        </div>
                        <div style="background: #f8fafc; padding: 1.2rem; border-radius: 10px; border: 1px solid #f1f5f9;">
                            <div style="font-size: 0.85rem; color: #64748b; margin-bottom: 0.5rem;">30日目标价</div>
                            <div style="font-size: 1.25rem; font-weight: 700; color: #1e293b;">¥ ${pred.target_price || '--'}</div>
                            <div style="font-size: 0.75rem; color: ${pred.change_percent >= 0 ? '#16a34a' : '#dc2626'}; margin-top: 2px;">
                                预期跌涨: ${pred.change_percent > 0 ? '+' : ''}${pred.change_percent}%
                            </div>
                        </div>
                    </div>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;">
                        <div style="background: #fdf2f2; padding: 1.2rem; border-radius: 10px; border: 1px solid #fee2e2;">
                            <h4 style="font-size: 1rem; font-weight: 700; color: #991b1b; margin-bottom: 0.8rem; display: flex; align-items: center;">
                                <span style="margin-right: 8px;">🎯</span> 关键支撑/阻力位
                            </h4>
                            <div style="display: flex; flex-direction: column; gap: 8px;">
                                <div style="display: flex; justify-content: space-between; font-size: 0.9rem;">
                                    <span style="color: #ef4444;">阻力位:</span>
                                    <span style="font-weight: 600;">${(data.key_levels.resistance_levels || []).join(' / ') || '无'}</span>
                                </div>
                                <div style="display: flex; justify-content: space-between; font-size: 0.9rem;">
                                    <span style="color: #22c55e;">支撑位:</span>
                                    <span style="font-weight: 600;">${(data.key_levels.support_levels || []).join(' / ') || '无'}</span>
                                </div>
                            </div>
                        </div>
                        
                        <div style="background: #f0f9ff; padding: 1.2rem; border-radius: 10px; border: 1px solid #e0f2fe;">
                            <h4 style="font-size: 1rem; font-weight: 700; color: #075985; margin-bottom: 0.8rem; display: flex; align-items: center;">
                                <span style="margin-right: 8px;">🤖</span> Gemini AI 深度见解
                            </h4>
                            <div style="color: #0c4a6e; font-size: 0.9rem; line-height: 1.6; max-height: 200px; overflow-y: auto; white-space: pre-wrap;">
                                ${formattedAiInsight}
                            </div>
                        </div>
                    </div>

                    <div style="margin-top: 1.5rem; font-size: 0.8rem; color: #94a3b8; text-align: center;">
                        * AI 分析结果基于历史数据及技术指标，不构成投资建议，股市有风险，入市需谨慎。
                    </div>
                </div>
            `;
        } catch (e) {
            console.error('分析失败:', e);
            resultDiv.innerHTML = `
                <div style="text-align: center; color: #dc2626; padding: 2rem;">
                    <div style="font-size: 2rem; margin-bottom: 1rem;">⚠️</div>
                    <p>分析失败: ${e.message}</p>
                    <button class="btn btn-primary" onclick="AnalysisPage.performQuickAnalysis()" style="margin-top: 1rem;">重试</button>
                </div>
            `;
            CommonUtils.showToast(e.message, 'error');
        }
    },

    // 加载市场分析
    loadMarketAnalysis() {
        this.updateMarketTemperature();
        this.updateTrendAnalysis();
        this.updateRiskAlerts();
    },

    // 更新市场温度
    updateMarketTemperature() {
        const temperature = 50 + Math.random() * 40; // 50-90
        const meterFill = document.querySelector('.meter-fill');
        const temperatureValue = document.querySelector('.temperature-value');

        if (meterFill && temperatureValue) {
            meterFill.style.width = `${temperature}%`;

            let status, color;
            if (temperature > 80) {
                status = '过热';
                color = '#dc2626';
            } else if (temperature > 65) {
                status = '偏热';
                color = '#f59e0b';
            } else {
                status = '正常';
                color = '#16a34a';
            }

            temperatureValue.textContent = `${Math.round(temperature)}°C ${status}`;
            temperatureValue.style.color = color;
        }
    },

    // 更新趋势分析
    updateTrendAnalysis() {
        const trends = ['bullish', 'bearish', 'neutral'];
        const trendSignals = document.querySelectorAll('.trend-signal');

        trendSignals.forEach(signal => {
            const randomTrend = trends[Math.floor(Math.random() * trends.length)];
            signal.className = `trend-signal ${randomTrend}`;

            switch (randomTrend) {
                case 'bullish':
                    signal.textContent = '看多';
                    break;
                case 'bearish':
                    signal.textContent = '看空';
                    break;
                case 'neutral':
                    signal.textContent = '震荡';
                    break;
            }
        });
    },

    // 更新风险提示
    updateRiskAlerts() {
        // 风险提示数据已在HTML中静态定义，这里可以添加动态更新逻辑
        console.log('风险提示已更新');
    },

    // 绘制资金流向图表
    drawFundFlowChart() {
        const canvas = document.getElementById('fundFlowChart');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;

        // 清空画布
        ctx.clearRect(0, 0, width, height);

        // 绘制柱状图
        const data = [
            { label: '主力', value: 156.8, color: '#dc2626' },
            { label: '散户', value: -89.2, color: '#16a34a' }
        ];

        const maxValue = Math.max(...data.map(d => Math.abs(d.value)));
        const barWidth = width / (data.length * 2);
        const chartHeight = height - 60;

        data.forEach((item, index) => {
            const barHeight = (Math.abs(item.value) / maxValue) * chartHeight;
            const x = (index + 0.5) * barWidth + (width - data.length * barWidth) / 2;
            const y = item.value > 0 ? (height - 30) - barHeight : height - 30;

            // 绘制柱子
            ctx.fillStyle = item.color;
            ctx.fillRect(x, y, barWidth * 0.8, barHeight);

            // 绘制标签
            ctx.fillStyle = '#374151';
            ctx.font = '12px Arial';
            ctx.textAlign = 'center';
            ctx.fillText(item.label, x + barWidth * 0.4, height - 10);

            // 绘制数值
            ctx.fillStyle = item.color;
            ctx.fillText(
                `${item.value > 0 ? '+' : ''}${item.value.toFixed(1)}亿`,
                x + barWidth * 0.4,
                item.value > 0 ? y - 5 : y + barHeight + 15
            );
        });
    },

    // 加载技术工具
    loadTechnicalTools() {
        if (window.KdeLevelsTool) KdeLevelsTool.loadKdeWatchlistOptions();
        if (window.PatternTool) PatternTool.loadWatchlist();
        // URL ?tool=resistance-support|pattern 时自动展开
        try {
            const params = new URLSearchParams(window.location.search || '');
            const tool = (params.get('tool') || '').trim();
            const hash = (window.location.hash || '').replace(/^#/, '').trim();
            if (tool === 'resistance-support' || hash === 'resistance-support' || hash === 'kde-levels') {
                this.openResistanceSupportTool({ scroll: true });
            }
            if (tool === 'pattern' || hash === 'pattern') {
                this.openPatternTool({ scroll: true });
            }
        } catch (e) { /* ignore */ }
    },

    openResistanceSupportTool(opts = {}) {
        const panel = document.getElementById('toolLevelsPanel');
        const btn = document.getElementById('toolLevelsToggleBtn');
        if (panel) {
            panel.hidden = false;
        }
        if (btn) btn.textContent = '收起工具';
        if (window.KdeLevelsTool) KdeLevelsTool.loadKdeWatchlistOptions();
        if (opts.scroll) {
            const card = document.getElementById('toolResistanceSupport');
            if (card && typeof card.scrollIntoView === 'function') {
                card.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
    },

    openPatternTool(opts = {}) {
        const panel = document.getElementById('toolPatternPanel');
        const btn = document.getElementById('toolPatternToggleBtn');
        const card = document.getElementById('toolPatternRecognition');
        if (panel) panel.hidden = false;
        if (card) card.classList.add('is-tool-expanded');
        if (btn) btn.textContent = '收起工具';
        if (window.PatternTool) {
            PatternTool.loadWatchlist();
            PatternTool.syncModeUi();
        }
        if (opts.scroll) {
            if (card && typeof card.scrollIntoView === 'function') {
                card.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
    },

    closePatternTool() {
        const panel = document.getElementById('toolPatternPanel');
        const btn = document.getElementById('toolPatternToggleBtn');
        const card = document.getElementById('toolPatternRecognition');
        if (panel) panel.hidden = true;
        if (card) card.classList.remove('is-tool-expanded');
        if (btn) btn.textContent = '使用工具';
    },

    // 使用技术工具
    useTechnicalTool(toolName, action) {
        const key = (action || '').trim() || String(toolName || '');
        if (key === 'resistance-support' || String(toolName || '').includes('阻力支撑')) {
            const panel = document.getElementById('toolLevelsPanel');
            if (panel && !panel.hidden) {
                panel.hidden = true;
                const btn = document.getElementById('toolLevelsToggleBtn');
                if (btn) btn.textContent = '使用工具';
                return;
            }
            this.openResistanceSupportTool({ scroll: true });
            CommonUtils.showToast('已打开阻力支撑位计算', 'info');
            return;
        }
        if (key === 'pattern' || String(toolName || '').includes('形态')) {
            const panel = document.getElementById('toolPatternPanel');
            if (panel && !panel.hidden) {
                this.closePatternTool();
                return;
            }
            this.openPatternTool({ scroll: true });
            CommonUtils.showToast('已打开形态识别', 'info');
            return;
        }
        if (key === 'screener' || String(toolName || '').includes('选股')) {
            window.location.href = 'screening.html';
            return;
        }
        CommonUtils.showToast(`${toolName || '该工具'} 即将开放`, 'info');
    },

    // 加载投资策略
    loadStrategy() {
        this.updateStrategyRecommendations();
    },

    // 更新策略推荐
    updateStrategyRecommendations() {
        // 策略推荐已在HTML中静态定义，这里可以添加动态更新逻辑
        const strategyItems = document.querySelectorAll('.strategy-item');

        strategyItems.forEach(item => {
            const stockTags = item.querySelectorAll('.stock-tag');
            stockTags.forEach(tag => {
                // 添加点击事件
                tag.addEventListener('click', () => {
                    const stockName = tag.textContent;
                    CommonUtils.showToast(`查看${stockName}详情`, 'info');
                    // 实际项目中这里会跳转到股票详情页
                });
                tag.style.cursor = 'pointer';
            });
        });
    },

    // 加载分析报告
    loadReports() {
        this.loadReportsList();
    },

    // 加载报告列表 (现在改为加载本周每一天的历史行情)
    async loadReportsList() {
        const tableBody = document.getElementById('weeklyQuotesBody');
        const reportTitle = document.getElementById('reportTitle');
        if (!tableBody) return;

        // 计算本周日期范围
        const now = new Date();
        const day = now.getDay(); // 0 是周日, 1 是周一...
        const diffToMonday = day === 0 ? 6 : day - 1; // 如果是周日，回退6天到周一

        const monday = new Date(now);
        monday.setDate(now.getDate() - diffToMonday);

        const formatDate = (d) => d.toISOString().split('T')[0];
        const startDate = formatDate(monday);
        const endDate = formatDate(now);

        // 设置标题
        if (this.currentStockCode) {
            reportTitle.textContent = `${this.currentStockCode} 本周每日行情 (${startDate} 至 ${endDate})`;
        } else {
            reportTitle.textContent = `本周市场每日行情 (默认示例)`;
        }

        try {
            // 使用日线接口查询指定日期范围
            let url = `${API_BASE_URL}/api/quotes/history?page=1&size=10&start_date=${startDate}&end_date=${endDate}`;
            if (this.currentStockCode) {
                url += `&code=${this.currentStockCode}`;
            } else {
                url += `&code=000001`;
            }

            const resp = await authFetch(url);
            if (!resp.ok) throw new Error('获取日线数据失败');

            const result = await resp.json();
            // 注意：/api/quotes/history 返回的结构是 { items: [...], total: ... }
            const items = result.items || [];

            if (items.length === 0) {
                tableBody.innerHTML = `<tr><td colspan="10" style="padding: 3rem; text-align: center; color: #94a3b8;">未找到该股票在本周 (${startDate} ~ ${endDate}) 的每日行情数据</td></tr>`;
                return;
            }

            // 获取股票名称（如果有的话）
            const firstItem = items[0];
            if (this.currentStockCode) {
                // 如果后端没返回名称，我们可以尝试从 items 中找或者保持原样
            }

            // 渲染表格
            tableBody.innerHTML = items.map(item => {
                const changePercent = item.change_percent || 0;
                const changeColor = changePercent >= 0 ? '#dc2626' : '#16a34a';
                const sign = changePercent > 0 ? '+' : '';

                // 格式化日期 (处理可能的 ISO 格式或 Date 对象)
                let displayDate = item.date;
                if (typeof displayDate === 'string' && displayDate.includes('T')) {
                    displayDate = displayDate.split('T')[0];
                }

                return `
                    <tr style="border-bottom: 1px solid #f1f5f9; transition: background 0.2s;" onmouseover="this.style.background='#f8fafc'" onmouseout="this.style.background='transparent'">
                        <td style="padding: 1rem; color: #1e293b; font-weight: 500;">${item.code}</td>
                        <td style="padding: 1rem; color: #1e293b;">${item.name || '--'}</td>
                        <td style="padding: 1rem; color: #64748b;">${displayDate}</td>
                        <td style="padding: 1rem; color: #1e293b;">${(item.open || 0).toFixed(2)}</td>
                        <td style="padding: 1rem; color: #dc2626; font-weight: 500;">${(item.high || 0).toFixed(2)}</td>
                        <td style="padding: 1rem; color: #16a34a; font-weight: 500;">${(item.low || 0).toFixed(2)}</td>
                        <td style="padding: 1rem; color: ${changeColor}; font-weight: 600;">
                            ${(item.close || 0).toFixed(2)}
                            <span style="font-size: 0.75rem; margin-left: 4px;">(${sign}${changePercent.toFixed(2)}%)</span>
                        </td>
                        <td style="padding: 1rem; color: #64748b;">${(function(v){ v=Number(v)||0; if(v>=1e8) return (v/1e8).toFixed(2)+'亿手'; if(v>=1e4) return (v/1e4).toFixed(2)+'万手'; return v.toFixed(0)+'手'; })(item.volume)}</td>
                        <td style="padding: 1rem; color: #64748b;">${((item.amount || 0) / 100000000).toFixed(2)}亿</td>
                        <td style="padding: 1rem; color: #64748b;">${item.turnover_rate ? item.turnover_rate.toFixed(2) + '%' : '--'}</td>
                    </tr>
                `;
            }).join('');

        } catch (e) {
            console.error('加载每日行情失败:', e);
            tableBody.innerHTML = `<tr><td colspan="10" style="padding: 3rem; text-align: center; color: #dc2626;">数据加载失败: ${e.message}</td></tr>`;
        }
    },

    // 过滤报告
    filterReports() {
        const filters = document.querySelectorAll('.filter-select');
        const typeFilter = filters[0].value;
        const industryFilter = filters[1].value;

        CommonUtils.showToast(`筛选条件：${typeFilter}/${industryFilter}`, 'info');

        // 实际项目中这里会根据过滤条件重新加载报告列表
    },

    // 打开报告
    openReport(reportTitle) {
        CommonUtils.showToast(`打开报告：${reportTitle}`, 'info');
        // 实际项目中这里会打开报告详情页面
    },

    // 开始数据更新
    startDataUpdate() {
        // 定期更新数据已按需求关闭
        /*
        // 定期更新市场分析数据
        setInterval(() => {
            if (this.currentTab === 'market-analysis') {
                this.updateMarketTemperature();
                this.updateTrendAnalysis();
            }
        }, 30000); // 每30秒更新一次

        // 更新资金流向图表
        setInterval(() => {
            this.drawFundFlowChart();
        }, 60000); // 每分钟更新一次
        */
    }
};

// DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    AnalysisPage.init();
}); 
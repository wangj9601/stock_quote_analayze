// 分析页面功能模块
const AnalysisPage = {
    currentTab: 'market-analysis',

    // 初始化
    init() {
        this.bindEvents();
        this.loadMarketAnalysis();
        this.drawFundFlowChart();
        this.startDataUpdate();
        
        // 确保搜索弹窗隐藏
        const searchModal = document.getElementById('searchModal');
        if (searchModal) {
            searchModal.classList.remove('show');
        }
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

        // 快速分析按钮
        document.querySelector('.analyze-btn').addEventListener('click', () => {
            this.performQuickAnalysis();
        });

        // 股票输入框回车事件
        document.querySelector('.stock-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.performQuickAnalysis();
            }
        });

        // 技术工具按钮
        document.querySelectorAll('.tool-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const toolName = e.target.closest('.tool-card').querySelector('h3').textContent;
                this.useTechnicalTool(toolName);
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
    performQuickAnalysis() {
        const stockInput = document.querySelector('.stock-input');
        const query = stockInput.value.trim();
        
        if (!query) {
            CommonUtils.showToast('请输入股票代码或名称', 'warning');
            return;
        }

        // 显示分析结果
        this.showAnalysisResult(query);
    },

    // 显示分析结果
    showAnalysisResult(stockCode) {
        const resultDiv = document.getElementById('analysisResult');
        
        // 模拟分析过程
        resultDiv.innerHTML = `
            <div style="text-align: center; color: #6b7280;">
                <div style="font-size: 2rem; margin-bottom: 1rem;">⏳</div>
                <p>正在分析 ${stockCode}，请稍候...</p>
            </div>
        `;

        // 模拟异步分析
        setTimeout(() => {
            const mockAnalysis = this.generateMockAnalysis(stockCode);
            resultDiv.innerHTML = mockAnalysis;
        }, 2000);
    },

    // 生成模拟分析结果
    generateMockAnalysis(stockCode) {
        const score = 65 + Math.random() * 30; // 65-95分
        const recommendation = score > 80 ? '买入' : score > 70 ? '持有' : '观望';
        const riskLevel = score > 80 ? '中低风险' : score > 70 ? '中等风险' : '中高风险';
        
        return `
            <div class="analysis-result-content" style="padding: 1.5rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
                    <h3 style="font-size: 1.2rem; font-weight: 600; color: #1f2937;">${stockCode} 智能分析报告</h3>
                    <div style="text-align: right;">
                        <div style="font-size: 2rem; font-weight: 700; color: ${score > 80 ? '#16a34a' : score > 70 ? '#f59e0b' : '#dc2626'};">${Math.round(score)}分</div>
                        <div style="font-size: 0.9rem; color: #6b7280;">综合评分</div>
                    </div>
                </div>
                
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 1.5rem;">
                    <div style="background: #f8fafc; padding: 1rem; border-radius: 6px;">
                        <div style="font-size: 0.8rem; color: #6b7280; margin-bottom: 0.5rem;">投资建议</div>
                        <div style="font-size: 1.1rem; font-weight: 600; color: ${recommendation === '买入' ? '#16a34a' : recommendation === '持有' ? '#f59e0b' : '#6b7280'};">${recommendation}</div>
                    </div>
                    <div style="background: #f8fafc; padding: 1rem; border-radius: 6px;">
                        <div style="font-size: 0.8rem; color: #6b7280; margin-bottom: 0.5rem;">风险等级</div>
                        <div style="font-size: 1.1rem; font-weight: 600; color: #374151;">${riskLevel}</div>
                    </div>
                    <div style="background: #f8fafc; padding: 1rem; border-radius: 6px;">
                        <div style="font-size: 0.8rem; color: #6b7280; margin-bottom: 0.5rem;">目标价位</div>
                        <div style="font-size: 1.1rem; font-weight: 600; color: #374151;">${(Math.random() * 50 + 20).toFixed(2)}</div>
                    </div>
                </div>
                
                <div style="border-top: 1px solid #e2e8f0; padding-top: 1rem;">
                    <h4 style="font-size: 1rem; font-weight: 600; color: #1f2937; margin-bottom: 0.5rem;">关键因素</h4>
                    <ul style="color: #6b7280; font-size: 0.9rem; line-height: 1.5;">
                        <li>技术面：${Math.random() > 0.5 ? '多头排列，趋势向好' : '震荡整理，方向待明'}</li>
                        <li>基本面：${Math.random() > 0.5 ? '业绩稳定，成长性良好' : '估值合理，安全边际较高'}</li>
                        <li>资金面：${Math.random() > 0.5 ? '主力资金净流入' : '散户参与度较高'}</li>
                    </ul>
                </div>
            </div>
        `;
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
        // 技术工具已在HTML中静态定义
        console.log('技术工具已加载');
    },

    // 使用技术工具
    useTechnicalTool(toolName) {
        CommonUtils.showToast(`启动${toolName}`, 'info');
        // 实际项目中这里会打开相应的技术分析工具
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

    // 加载报告列表
    loadReportsList() {
        // 报告列表已在HTML中静态定义
        console.log('分析报告已加载');
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
    }
};

// DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    AnalysisPage.init();
}); 
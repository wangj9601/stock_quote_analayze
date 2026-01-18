/**
 * PVFRS策略管理系统前端脚本
 */

class PVFRSAdmin {
    constructor() {
        this.apiBaseUrl = this.getApiBaseUrl();
        this.currentTab = 'backtest';
        this.refreshInterval = null;
        this.init();
    }

    getApiBaseUrl() {
        // 根据环境自动检测API地址
        const hostname = window.location.hostname;
        if (hostname === 'localhost' || hostname === '127.0.0.1') {
            return 'http://localhost:5000';
        }
        return `${window.location.protocol}//${hostname}:5000`;
    }

    init() {
        this.bindEvents();
        this.loadSystemStatus();
        this.loadBacktestTasks();
        this.startAutoRefresh();
    }

    bindEvents() {
        // 标签页切换
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.switchTab(e.target.dataset.tab);
            });
        });

        // 刷新按钮
        document.getElementById('refreshBtn').addEventListener('click', () => {
            this.refreshAll();
        });

        // 创建回测任务
        document.getElementById('createBacktestBtn').addEventListener('click', () => {
            this.showBacktestForm();
        });

        document.getElementById('cancelBacktestBtn').addEventListener('click', () => {
            this.hideBacktestForm();
        });

        // 回测配置表单提交
        document.getElementById('backtestConfigForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.createBacktestTask();
        });

        // 策略配置表单提交
        document.getElementById('strategyConfigForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.updateStrategyConfig();
        });

        // 风险配置表单提交
        document.getElementById('riskConfigForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.updateRiskConfig();
        });

        // 监控页面刷新
        document.getElementById('refreshMonitorBtn').addEventListener('click', () => {
            this.loadTaskMonitor();
        });

        // 状态过滤器
        document.getElementById('statusFilter').addEventListener('change', () => {
            this.loadTaskMonitor();
        });

        // 对比报告
        document.getElementById('compareReportsBtn').addEventListener('click', () => {
            this.compareSelectedReports();
        });
    }

    switchTab(tabName) {
        // 更新标签页状态
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active', 'border-blue-500', 'text-blue-600');
            btn.classList.add('border-transparent', 'text-gray-500');
        });

        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active', 'border-blue-500', 'text-blue-600');
        document.querySelector(`[data-tab="${tabName}"]`).classList.remove('border-transparent', 'text-gray-500');

        // 显示对应内容
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.add('hidden');
        });
        document.getElementById(`${tabName}-tab`).classList.remove('hidden');

        this.currentTab = tabName;

        // 加载对应数据
        switch (tabName) {
            case 'backtest':
                this.loadBacktestTasks();
                break;
            case 'reports':
                this.loadBacktestReports();
                break;
            case 'config':
                // 配置页面不需要额外加载
                break;
            case 'monitor':
                this.loadTaskMonitor();
                break;
        }
    }

    async loadSystemStatus() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/admin/pvfrs/interface-status`);
            if (response.ok) {
                const data = await response.json();
                // 更新系统状态显示
                this.updateSystemStatusDisplay(data.data);
            }
        } catch (error) {
            console.error('加载系统状态失败:', error);
        }
    }

    updateSystemStatusDisplay(statusData) {
        // 这里可以根据实际返回的状态数据更新显示
        // 暂时使用模拟数据
        document.getElementById('runningTasks').textContent = '2';
        document.getElementById('completedTasks').textContent = '15';
        document.getElementById('pendingTasks').textContent = '1';
        document.getElementById('failedTasks').textContent = '0';
    }

    async loadBacktestTasks() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/admin/pvfrs/backtest/tasks`);
            if (response.ok) {
                const data = await response.json();
                this.renderBacktestTasks(data.data || []);
            } else {
                this.renderBacktestTasks([]);
            }
        } catch (error) {
            console.error('加载回测任务失败:', error);
            this.renderBacktestTasks([]);
        }
    }

    renderBacktestTasks(tasks) {
        const tbody = document.getElementById('backtestTasksTable');
        
        if (tasks.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-4 text-center text-gray-500">暂无任务</td></tr>';
            return;
        }

        tbody.innerHTML = tasks.map(task => `
            <tr>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    ${task.task_id || 'N/A'}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    ${task.created_at || 'N/A'}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    ${task.start_date || 'N/A'} ~ ${task.end_date || 'N/A'}
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full status-${task.status || 'pending'}">
                        ${this.getStatusText(task.status)}
                    </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    <div class="w-full bg-gray-200 rounded-full h-2">
                        <div class="bg-blue-600 h-2 rounded-full" style="width: ${task.progress || 0}%"></div>
                    </div>
                    <span class="text-xs">${task.progress || 0}%</span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <div class="flex space-x-2">
                        ${task.status === 'running' ? 
                            `<button onclick="pvfrsAdmin.cancelTask('${task.task_id}')" class="text-red-600 hover:text-red-900">取消</button>` :
                            ''
                        }
                        ${task.status === 'completed' ? 
                            `<button onclick="pvfrsAdmin.viewReport('${task.task_id}')" class="text-blue-600 hover:text-blue-900">查看报告</button>` :
                            ''
                        }
                    </div>
                </td>
            </tr>
        `).join('');
    }

    async loadBacktestReports() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/admin/pvfrs/backtest/reports`);
            if (response.ok) {
                const data = await response.json();
                this.renderBacktestReports(data.data || []);
            } else {
                this.renderBacktestReports([]);
            }
        } catch (error) {
            console.error('加载回测报告失败:', error);
            this.renderBacktestReports([]);
        }
    }

    renderBacktestReports(reports) {
        const tbody = document.getElementById('reportsTable');
        
        if (reports.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="px-6 py-4 text-center text-gray-500">暂无报告</td></tr>';
            return;
        }

        tbody.innerHTML = reports.map(report => `
            <tr>
                <td class="px-6 py-4 whitespace-nowrap">
                    <input type="checkbox" class="report-checkbox rounded" value="${report.report_id}">
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    ${report.report_id || 'N/A'}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    ${report.start_date || 'N/A'} ~ ${report.end_date || 'N/A'}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    <span class="${(report.total_return || 0) >= 0 ? 'text-green-600' : 'text-red-600'}">
                        ${((report.total_return || 0) * 100).toFixed(2)}%
                    </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    ${(report.sharpe_ratio || 0).toFixed(3)}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-red-600">
                    ${((report.max_drawdown || 0) * 100).toFixed(2)}%
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <button onclick="pvfrsAdmin.viewReportDetail('${report.report_id}')" class="text-blue-600 hover:text-blue-900">
                        查看详情
                    </button>
                </td>
            </tr>
        `).join('');
    }

    async loadTaskMonitor() {
        const statusFilter = document.getElementById('statusFilter').value;
        try {
            let url = `${this.apiBaseUrl}/api/admin/pvfrs/backtest/tasks`;
            if (statusFilter) {
                url += `?status_filter=${statusFilter}`;
            }
            
            const response = await fetch(url);
            if (response.ok) {
                const data = await response.json();
                this.renderTaskMonitor(data.data || []);
            } else {
                this.renderTaskMonitor([]);
            }
        } catch (error) {
            console.error('加载任务监控失败:', error);
            this.renderTaskMonitor([]);
        }
    }

    renderTaskMonitor(tasks) {
        const tbody = document.getElementById('monitorTable');
        
        if (tasks.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="px-6 py-4 text-center text-gray-500">暂无任务</td></tr>';
            return;
        }

        tbody.innerHTML = tasks.map(task => `
            <tr>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    ${task.task_id || 'N/A'}
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full status-${task.status || 'pending'}">
                        ${this.getStatusText(task.status)}
                    </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    <div class="w-full bg-gray-200 rounded-full h-2">
                        <div class="bg-blue-600 h-2 rounded-full" style="width: ${task.progress || 0}%"></div>
                    </div>
                    <span class="text-xs">${task.progress || 0}%</span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    ${task.start_time || 'N/A'}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    ${this.calculateDuration(task.start_time)}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <div class="flex space-x-2">
                        ${task.status === 'running' ? 
                            `<button onclick="pvfrsAdmin.cancelTask('${task.task_id}')" class="text-red-600 hover:text-red-900">取消</button>` :
                            ''
                        }
                        <button onclick="pvfrsAdmin.viewTaskDetail('${task.task_id}')" class="text-blue-600 hover:text-blue-900">详情</button>
                    </div>
                </td>
            </tr>
        `).join('');
    }

    showBacktestForm() {
        document.getElementById('backtestForm').classList.remove('hidden');
        document.getElementById('createBacktestBtn').classList.add('hidden');
    }

    hideBacktestForm() {
        document.getElementById('backtestForm').classList.add('hidden');
        document.getElementById('createBacktestBtn').classList.remove('hidden');
    }

    async createBacktestTask() {
        const formData = {
            start_date: document.getElementById('startDate').value,
            end_date: document.getElementById('endDate').value,
            initial_capital: parseFloat(document.getElementById('initialCapital').value),
            stock_pool: document.getElementById('stockPool').value,
            strategy_params: {},
            risk_params: {}
        };

        this.showLoading();
        
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/admin/pvfrs/backtest/create`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            });

            const result = await response.json();
            
            if (response.ok && result.success) {
                this.showMessage('回测任务创建成功！', 'success');
                this.hideBacktestForm();
                this.loadBacktestTasks();
            } else {
                this.showMessage(result.detail || '创建任务失败', 'error');
            }
        } catch (error) {
            console.error('创建回测任务失败:', error);
            this.showMessage('创建任务失败：' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async updateStrategyConfig() {
        const configData = {
            signal_threshold: parseFloat(document.getElementById('signalThreshold').value),
            price_weight: parseFloat(document.getElementById('priceWeight').value),
            frequency_weight: parseFloat(document.getElementById('frequencyWeight').value),
            volume_weight: parseFloat(document.getElementById('volumeWeight').value)
        };

        this.showLoading();
        
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/admin/pvfrs/config/strategy`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(configData)
            });

            const result = await response.json();
            
            if (response.ok && result.success) {
                this.showMessage('策略配置更新成功！', 'success');
            } else {
                this.showMessage(result.detail || '更新配置失败', 'error');
            }
        } catch (error) {
            console.error('更新策略配置失败:', error);
            this.showMessage('更新配置失败：' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async updateRiskConfig() {
        const configData = {
            max_position_pct: parseFloat(document.getElementById('maxPositionPct').value),
            stop_loss_pct: parseFloat(document.getElementById('stopLossPct').value),
            take_profit_pct: parseFloat(document.getElementById('takeProfitPct').value),
            max_holdings: parseInt(document.getElementById('maxHoldings').value)
        };

        this.showLoading();
        
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/admin/pvfrs/config/risk`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(configData)
            });

            const result = await response.json();
            
            if (response.ok && result.success) {
                this.showMessage('风险配置更新成功！', 'success');
            } else {
                this.showMessage(result.detail || '更新配置失败', 'error');
            }
        } catch (error) {
            console.error('更新风险配置失败:', error);
            this.showMessage('更新配置失败：' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async cancelTask(taskId) {
        if (!confirm('确定要取消这个任务吗？')) {
            return;
        }

        this.showLoading();
        
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/admin/pvfrs/backtest/cancel/${taskId}`, {
                method: 'POST'
            });

            const result = await response.json();
            
            if (response.ok && result.success) {
                this.showMessage('任务取消成功！', 'success');
                this.loadBacktestTasks();
                if (this.currentTab === 'monitor') {
                    this.loadTaskMonitor();
                }
            } else {
                this.showMessage(result.detail || '取消任务失败', 'error');
            }
        } catch (error) {
            console.error('取消任务失败:', error);
            this.showMessage('取消任务失败：' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async viewReport(taskId) {
        window.open(`pvfrs-report.html?task_id=${taskId}`, '_blank');
    }

    async viewReportDetail(reportId) {
        window.open(`pvfrs-report.html?report_id=${reportId}`, '_blank');
    }

    async viewTaskDetail(taskId) {
        // 显示任务详情模态框或跳转到详情页面
        alert(`查看任务详情: ${taskId}`);
    }

    async compareSelectedReports() {
        const selectedReports = Array.from(document.querySelectorAll('.report-checkbox:checked'))
            .map(cb => cb.value);
        
        if (selectedReports.length < 2) {
            this.showMessage('请至少选择2个报告进行对比', 'warning');
            return;
        }

        this.showLoading();
        
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/admin/pvfrs/backtest/compare`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(selectedReports)
            });

            const result = await response.json();
            
            if (response.ok && result.success) {
                // 打开对比结果页面
                const reportIds = selectedReports.join(',');
                window.open(`pvfrs-compare.html?reports=${reportIds}`, '_blank');
            } else {
                this.showMessage(result.detail || '对比报告失败', 'error');
            }
        } catch (error) {
            console.error('对比报告失败:', error);
            this.showMessage('对比报告失败：' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    refreshAll() {
        this.loadSystemStatus();
        
        switch (this.currentTab) {
            case 'backtest':
                this.loadBacktestTasks();
                break;
            case 'reports':
                this.loadBacktestReports();
                break;
            case 'monitor':
                this.loadTaskMonitor();
                break;
        }
    }

    startAutoRefresh() {
        // 每30秒自动刷新一次
        this.refreshInterval = setInterval(() => {
            if (this.currentTab === 'monitor' || this.currentTab === 'backtest') {
                this.refreshAll();
            }
        }, 30000);
    }

    getStatusText(status) {
        const statusMap = {
            'pending': '等待中',
            'running': '运行中',
            'completed': '已完成',
            'failed': '失败',
            'cancelled': '已取消'
        };
        return statusMap[status] || '未知';
    }

    calculateDuration(startTime) {
        if (!startTime) return 'N/A';
        
        const start = new Date(startTime);
        const now = new Date();
        const diff = now - start;
        
        const hours = Math.floor(diff / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        
        return `${hours}h ${minutes}m`;
    }

    showLoading() {
        document.getElementById('loadingOverlay').classList.remove('hidden');
    }

    hideLoading() {
        document.getElementById('loadingOverlay').classList.add('hidden');
    }

    showMessage(message, type = 'info') {
        // 简单的消息提示，可以后续改为更好的UI组件
        const bgColor = {
            'success': 'bg-green-500',
            'error': 'bg-red-500',
            'warning': 'bg-yellow-500',
            'info': 'bg-blue-500'
        }[type] || 'bg-blue-500';

        const messageDiv = document.createElement('div');
        messageDiv.className = `fixed top-4 right-4 ${bgColor} text-white px-6 py-3 rounded-lg shadow-lg z-50`;
        messageDiv.textContent = message;
        
        document.body.appendChild(messageDiv);
        
        setTimeout(() => {
            messageDiv.remove();
        }, 3000);
    }
}

// 初始化PVFRS管理系统
const pvfrsAdmin = new PVFRSAdmin();
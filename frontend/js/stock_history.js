
// 全局API前缀
//const API_BASE_URL = Config ? Config.getApiBaseUrl() : '';

// 股票历史行情页面JavaScript
class StockHistoryPage {
    constructor() {
        this.currentPage = 1;
        this.pageSize = 20;
        this.totalPages = 0;
        this.currentStockCode = '';
        this.currentStockName = '';

        this.init();
    }

    init() {
        this.bindEvents();
        this.setDefaultDates();
        this.loadStockFromUrl();
    }

    bindEvents() {
        // 查询按钮
        document.getElementById('searchBtn').addEventListener('click', () => {
            this.searchHistory();
        });

        // 导出按钮
        document.getElementById('exportBtn').addEventListener('click', () => {
            this.exportHistory();
        });

        // 显示指标数据按钮
        document.getElementById('showIndicatorsBtn').addEventListener('click', () => {
            if (!this.currentStockCode) {
                alert('请先选择股票');
                return;
            }
            const startDate = document.getElementById('startDate').value;
            const endDate = document.getElementById('endDate').value;
            this.showIndicators(this.currentStockCode, startDate, endDate);
        });

        // 计算5天升跌按钮
        document.getElementById('calculateFiveDayBtn').addEventListener('click', () => {
            this.calculateFiveDayChange();
        });

        // 计算10天涨跌按钮
        document.getElementById('calculateTenDayBtn').addEventListener('click', () => {
            this.calculateTenDayChange();
        });

        // 计算30天涨跌按钮
        document.getElementById('calculateThirtyDayBtn').addEventListener('click', () => {
            this.calculateThirtyDayChange();
        });

        // 计算60天涨跌按钮
        document.getElementById('calculateSixtyDayBtn').addEventListener('click', () => {
            this.calculateSixtyDayChange();
        });

        // 分页按钮
        document.getElementById('firstPage').addEventListener('click', () => {
            this.goToPage(1);
        });

        document.getElementById('prevPage').addEventListener('click', () => {
            this.goToPage(this.currentPage - 1);
        });

        document.getElementById('nextPage').addEventListener('click', () => {
            this.goToPage(this.currentPage + 1);
        });

        document.getElementById('lastPage').addEventListener('click', () => {
            this.goToPage(this.totalPages);
        });

        // 回车键搜索
        document.getElementById('startDate').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.searchHistory();
        });

        document.getElementById('endDate').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.searchHistory();
        });
    }

    setDefaultDates() {
        const today = new Date();
        const threeMonthsAgo = new Date(today.getTime() - 90 * 24 * 60 * 60 * 1000);

        document.getElementById('startDate').value = this.formatDate(threeMonthsAgo);
        document.getElementById('endDate').value = this.formatDate(today);
    }

    formatDate(date) {
        return date.toISOString().split('T')[0];
    }

    loadStockFromUrl() {
        const urlParams = new URLSearchParams(window.location.search);
        const stockCode = urlParams.get('code');
        const stockCodeInput = document.getElementById('stockCodeInput');

        if (stockCode) {
            this.currentStockCode = stockCode;
            if (stockCodeInput) {
                stockCodeInput.value = stockCode;
            }
            this.searchHistory();
        } else if (stockCodeInput && stockCodeInput.value.trim()) {
            this.currentStockCode = stockCodeInput.value.trim();
            this.searchHistory();
        }
    }

    async searchHistory() {
        // 移除强制登录检查，支持未登录查询
        // if (!CommonUtils.checkLoginAndHandleExpiry()) {
        //     return;
        // }

        const startDate = document.getElementById('startDate').value;
        const endDate = document.getElementById('endDate').value;
        const includeNotes = document.getElementById('includeNotes').checked;
        const stockCodeInput = document.getElementById('stockCodeInput');
        if (stockCodeInput) {
            this.currentStockCode = stockCodeInput.value.trim();
        }

        if (!this.currentStockCode) {
            alert('请先选择股票');
            return;
        }

        try {
            const response = await authFetch(`${API_BASE_URL}/api/stock/history?code=${this.currentStockCode}&start_date=${startDate}&end_date=${endDate}&include_notes=${includeNotes}&page=${this.currentPage}&size=${this.pageSize}`);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            this.displayHistory(data.items);
            this.updatePagination(data.total);

        } catch (error) {
            console.error('查询历史行情失败:', error);
            alert('查询失败: ' + error.message);
        }
    }

    displayHistory(items) {
        const tbody = document.querySelector('#historyTable tbody');
        tbody.innerHTML = '';

        if (!items || items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="14" style="text-align: center; padding: 20px;">暂无数据</td></tr>';
            return;
        }

        for (let i = 0; i < items.length; i++) {
            const item = items[i];
            const row = document.createElement('tr');

            // 设置涨跌样式
            if (item.change_percent > 0) {
                row.classList.add('row-up');
            } else if (item.change_percent < 0) {
                row.classList.add('row-down');
            }

            // 计算成交额变化：参考10天涨跌%的处理方式，直接在模板字符串中判断
            // 数据是从新到旧排列的，索引i的行和索引i+1的行（前一个交易日）比较
            const nextItem = items[i + 1];
            const currentAmount = item.amount !== null && item.amount !== undefined ? Number(item.amount) : null;
            const nextAmount = nextItem && nextItem.amount !== null && nextItem.amount !== undefined ? Number(nextItem.amount) : null;
            const amountChange = (currentAmount !== null && nextAmount !== null) ? (currentAmount - nextAmount) : null;

            // 成交额列的样式：优先使用成交额变化，如果无法计算（如最后一行），则参考收盘列逻辑使用涨跌幅
            let amountCellClass = '';
            if (amountChange !== null) {
                amountCellClass = amountChange > 0 ? 'cell-up' : amountChange < 0 ? 'cell-down' : '';
            } else {
                // 无法计算成交额变化时（如最后一行），参考收盘列的处理逻辑
                amountCellClass = item.change_percent > 0 ? 'cell-up' : item.change_percent < 0 ? 'cell-down' : '';
            }

            row.innerHTML = `
                <!--td>${item.code}</td-->
                <td>${item.name}</td>
                <td>${item.date}</td>
                <td>${this.formatNumber(item.open)}</td>
                <td class="${item.change_percent > 0 ? 'cell-up' : item.change_percent < 0 ? 'cell-down' : ''}">${this.formatNumber(item.close)}</td>
                <td class="${item.change > 0 ? 'cell-up' : item.change < 0 ? 'cell-down' : ''}">${this.formatNumber(item.change)}</td>
                <td class="${amountCellClass}">${this.formatAmount(item.amount)}</td>
                <td class="${item.change_percent > 0 ? 'cell-up' : item.change_percent < 0 ? 'cell-down' : ''}">${this.formatPercent(item.change_percent)}</td>
                <td>${this.formatVolume(item.volume)}</td>
                <td>${this.formatPercent(item.turnover_rate)}</td>
                <td class="${item.five_day_change_percent > 0 ? 'cell-up' : item.five_day_change_percent < 0 ? 'cell-down' : ''}">${this.formatPercent(item.five_day_change_percent)}</td>
                <td class="${item.ten_day_change_percent > 0 ? 'cell-up' : item.ten_day_change_percent < 0 ? 'cell-down' : ''}">${this.formatPercent(item.ten_day_change_percent)}</td>
                <td class="${item.thirty_day_change_percent > 0 ? 'cell-up' : item.thirty_day_change_percent < 0 ? 'cell-down' : ''}">${this.formatPercent(item.thirty_day_change_percent)}</td>
                <td class="${item.sixty_day_change_percent > 0 ? 'cell-up' : item.sixty_day_change_percent < 0 ? 'cell-down' : ''}">${this.formatPercent(item.sixty_day_change_percent)}</td>
                <td class="notes-cell ${(item.user_notes || item.remarks) ? 'has-notes' : ''}" onclick="stockHistoryPage.editNote('${item.code}', '${item.date}', '${item.user_notes || item.remarks || ''}', '${item.strategy_type || ''}', '${item.risk_level || ''}')">${item.user_notes || item.remarks || '点击添加'}</td>
            `;

            tbody.appendChild(row);
        }

        // 更新股票信息
        if (items.length > 0) {
            this.currentStockName = items[0].name;
        }
    }

    formatNumber(num) {
        if (num === null || num === undefined) return '-';
        return Number(num).toFixed(2);
    }

    formatPercent(num) {
        if (num === null || num === undefined) return '-';
        return Number(num).toFixed(2) + '%';
    }

    formatVolume(volume) {
        if (volume === null || volume === undefined) return '-';
        const vol = Number(volume);
        if (vol >= 10000) {
            return (vol / 10000).toFixed(2) + '万';
        }
        return vol.toFixed(0);
    }

    formatAmount(amount) {
        if (amount === null || amount === undefined) return '-';
        const amt = Number(amount);
        if (amt >= 100000000) {
            return (amt / 100000000).toFixed(2) + '亿';
        } else if (amt >= 10000) {
            return (amt / 10000).toFixed(2) + '万';
        }
        return amt.toFixed(0);
    }

    updatePagination(total) {
        this.totalPages = Math.ceil(total / this.pageSize);

        document.getElementById('pageInfo').textContent = `第 ${this.currentPage} 页，共 ${this.totalPages} 页，总计 ${total} 条`;

        // 更新按钮状态
        document.getElementById('firstPage').disabled = this.currentPage === 1;
        document.getElementById('prevPage').disabled = this.currentPage === 1;
        document.getElementById('nextPage').disabled = this.currentPage === this.totalPages;
        document.getElementById('lastPage').disabled = this.currentPage === this.totalPages;
    }

    goToPage(page) {
        if (page < 1 || page > this.totalPages) return;

        this.currentPage = page;
        this.searchHistory();
    }

    async exportHistory() {
        // 移除强制登录检查
        // const userInfo = CommonUtils.auth.getUserInfo();
        // if (!userInfo || !userInfo.id) {
        //     CommonUtils.showToast('请先登录后再导出数据', 'warning');
        //     // 跳转到登录页面
        //     window.location.href = 'login.html';
        //     return;
        // }

        const startDate = document.getElementById('startDate').value;
        const endDate = document.getElementById('endDate').value;
        const includeNotes = document.getElementById('includeNotes').checked;
        const exportFormatSelect = document.getElementById('exportFormat');
        const exportFormat = exportFormatSelect ? exportFormatSelect.value : 'excel';

        if (!this.currentStockCode) {
            alert('请先选择股票');
            return;
        }

        try {
            const url = `${API_BASE_URL}/api/stock/history/export?code=${this.currentStockCode}&start_date=${startDate}&end_date=${endDate}&include_notes=${includeNotes}&format=${exportFormat}`;

            // 使用authFetch获取带认证的下载链接
            const response = await authFetch(url);
            if (!response.ok) {
                if (response.status === 401) {
                    CommonUtils.showToast('登录已过期，请重新登录', 'error');
                    CommonUtils.auth.logout();
                    return;
                }
                throw new Error(`导出失败: ${response.status}`);
            }

            // 创建下载链接
            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = downloadUrl;
            const extensionMap = { excel: 'xlsx', csv: 'csv', text: 'txt' };
            const fileExtension = extensionMap[exportFormat] || 'xlsx';
            link.download = `${this.currentStockCode}_历史行情_${new Date().toISOString().slice(0, 10)}.${fileExtension}`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(downloadUrl);

        } catch (error) {
            console.error('导出失败:', error);
            alert('导出失败: ' + error.message);
        }
    }

    async calculateFiveDayChange() {
        // 移除强制登录检查
        // const userInfo = CommonUtils.auth.getUserInfo();
        // if (!userInfo || !userInfo.id) {
        //     CommonUtils.showToast('请先登录后再计算涨跌幅', 'warning');
        //     // 跳转到登录页面
        //     window.location.href = 'login.html';
        //     return;
        // }

        const startDate = document.getElementById('startDate').value;
        const endDate = document.getElementById('endDate').value;

        if (!this.currentStockCode) {
            alert('请先选择股票');
            return;
        }

        if (!startDate || !endDate) {
            alert('请选择开始日期和结束日期');
            return;
        }

        // 禁用按钮，显示计算中状态
        const calculateBtn = document.getElementById('calculateFiveDayBtn');
        const originalText = calculateBtn.textContent;
        calculateBtn.disabled = true;
        calculateBtn.textContent = '计算中...';

        try {
            // 为了确保最后5条记录也能计算5天升跌%，将结束日期延长5个工作日
            const extendedEndDate = this.addBusinessDays(endDate, 5);

            const response = await authFetch(`${API_BASE_URL}/api/stock/history/calculate_five_day_change`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    stock_code: this.currentStockCode,
                    start_date: startDate,
                    end_date: endDate,
                    extended_end_date: extendedEndDate
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '计算失败');
            }

            const result = await response.json();
            alert(`计算完成！\n${result.message}\n更新记录数: ${result.updated_count}\n注意：结束日期已自动延长5个工作日以确保完整计算`);

            // 重新查询数据以显示最新结果
            this.searchHistory();

        } catch (error) {
            console.error('计算5天升跌失败:', error);
            alert('计算失败: ' + error.message);
        } finally {
            // 恢复按钮状态
            calculateBtn.disabled = false;
            calculateBtn.textContent = originalText;
        }
    }

    async calculateTenDayChange() {
        // 移除强制登录检查
        // const userInfo = CommonUtils.auth.getUserInfo();
        // if (!userInfo || !userInfo.id) {
        //     CommonUtils.showToast('请先登录后再计算涨跌幅', 'warning');
        //     // 跳转到登录页面
        //     window.location.href = 'login.html';
        //     return;
        // }

        const startDate = document.getElementById('startDate').value;
        const endDate = document.getElementById('endDate').value;

        if (!this.currentStockCode) {
            alert('请先选择股票');
            return;
        }

        if (!startDate || !endDate) {
            alert('请选择开始日期和结束日期');
            return;
        }

        // 禁用按钮，显示计算中状态
        const calculateBtn = document.getElementById('calculateTenDayBtn');
        const originalText = calculateBtn.textContent;
        calculateBtn.disabled = true;
        calculateBtn.textContent = '计算中...';

        try {
            // 为了确保最后10条记录也能计算10天涨跌%，将结束日期延长10个工作日
            const extendedEndDate = this.addBusinessDays(endDate, 10);

            const response = await authFetch(`${API_BASE_URL}/api/stock/history/calculate_ten_day_change`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    stock_code: this.currentStockCode,
                    start_date: startDate,
                    end_date: endDate,
                    extended_end_date: extendedEndDate
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '计算失败');
            }

            const result = await response.json();
            alert(`计算完成！\n${result.message}\n更新记录数: ${result.updated_count}\n注意：结束日期已自动延长10个工作日以确保完整计算`);

            // 重新查询数据以显示最新结果
            this.searchHistory();

        } catch (error) {
            console.error('计算10天涨跌失败:', error);
            alert('计算失败: ' + error.message);
        } finally {
            // 恢复按钮状态
            calculateBtn.disabled = false;
            calculateBtn.textContent = originalText;
        }
    }

    async calculateThirtyDayChange() {
        // 移除强制登录检查
        // const userInfo = CommonUtils.auth.getUserInfo();
        // if (!userInfo || !userInfo.id) {
        //     CommonUtils.showToast('请先登录后再计算涨跌幅', 'warning');
        //     window.location.href = 'login.html';
        //     return;
        // }

        const startDate = document.getElementById('startDate').value;
        const endDate = document.getElementById('endDate').value;

        if (!this.currentStockCode) {
            alert('请先选择股票');
            return;
        }

        if (!startDate || !endDate) {
            alert('请选择开始日期和结束日期');
            return;
        }

        const calculateBtn = document.getElementById('calculateThirtyDayBtn');
        const originalText = calculateBtn.textContent;
        calculateBtn.disabled = true;
        calculateBtn.textContent = '计算中...';

        try {
            const extendedEndDate = this.addBusinessDays(endDate, 30);

            const response = await authFetch(`${API_BASE_URL}/api/stock/history/calculate_thirty_day_change`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    stock_code: this.currentStockCode,
                    start_date: startDate,
                    end_date: endDate,
                    extended_end_date: extendedEndDate
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '计算失败');
            }

            const result = await response.json();
            alert(`计算完成！\n${result.message}\n更新记录数: ${result.updated_count}\n注意：结束日期已自动延长30个工作日以确保完整计算`);

            this.searchHistory();

        } catch (error) {
            console.error('计算30天涨跌失败:', error);
            alert('计算失败: ' + error.message);
        } finally {
            calculateBtn.disabled = false;
            calculateBtn.textContent = originalText;
        }
    }

    async calculateSixtyDayChange() {
        // 移除强制登录检查
        // const userInfo = CommonUtils.auth.getUserInfo();
        // if (!userInfo || !userInfo.id) {
        //     CommonUtils.showToast('请先登录后再计算涨跌幅', 'warning');
        //     // 跳转到登录页面
        //     window.location.href = 'login.html';
        //     return;
        // }

        const startDate = document.getElementById('startDate').value;
        const endDate = document.getElementById('endDate').value;

        if (!this.currentStockCode) {
            alert('请先选择股票');
            return;
        }

        if (!startDate || !endDate) {
            alert('请选择开始日期和结束日期');
            return;
        }

        // 禁用按钮，显示计算中状态
        const calculateBtn = document.getElementById('calculateSixtyDayBtn');
        const originalText = calculateBtn.textContent;
        calculateBtn.disabled = true;
        calculateBtn.textContent = '计算中...';

        try {
            // 为了确保最后60条记录也能计算60天涨跌%，将结束日期延长60个工作日
            const extendedEndDate = this.addBusinessDays(endDate, 60);

            const response = await authFetch(`${API_BASE_URL}/api/stock/history/calculate_sixty_day_change`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    stock_code: this.currentStockCode,
                    start_date: startDate,
                    end_date: endDate,  // 传递原始结束日期，后端会自动扩展查询范围
                    extended_end_date: extendedEndDate  // 扩展后的结束日期用于查询
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '计算失败');
            }

            const result = await response.json();

            // 重新查询数据以显示最新结果（先刷新，再提示）
            await this.searchHistory();

            alert(`计算完成！\n${result.message}\n更新记录数: ${result.updated_count}\n注意：结束日期已自动延长60个工作日以确保完整计算`);

        } catch (error) {
            console.error('计算60天涨跌失败:', error);
            alert('计算失败: ' + error.message);
        } finally {
            // 恢复按钮状态
            calculateBtn.disabled = false;
            calculateBtn.textContent = originalText;
        }
    }

    // 添加工作日计算函数
    addBusinessDays(dateStr, days) {
        const date = new Date(dateStr);
        let addedDays = 0;
        let currentDate = new Date(date);

        while (addedDays < days) {
            currentDate.setDate(currentDate.getDate() + 1);

            // 跳过周末（周六=6，周日=0）
            if (currentDate.getDay() !== 0 && currentDate.getDay() !== 6) {
                addedDays++;
            }
        }

        return currentDate.toISOString().split('T')[0];
    }

    editNote(stockCode, tradeDate, currentNotes, strategyType, riskLevel) {
        document.getElementById('noteStockCode').value = stockCode;
        document.getElementById('noteTradeDate').value = tradeDate;
        document.getElementById('noteContent').value = currentNotes;

        // 设置策略类型下拉选项
        const strategySelect = document.getElementById('noteStrategyType');
        if (strategySelect) {
            strategySelect.value = strategyType || '';
        }

        // 设置风险等级下拉选项
        const riskSelect = document.getElementById('noteRiskLevel');
        if (riskSelect) {
            riskSelect.value = riskLevel || '';
        }

        // 显示弹窗
        document.getElementById('notesModal').style.display = 'block';

        // 绑定弹窗事件
        this.bindModalEvents();
    }

    bindModalEvents() {
        const modal = document.getElementById('notesModal');
        const closeBtn = document.querySelector('.close-notes');
        const saveBtn = document.getElementById('saveNoteBtn');
        const deleteBtn = document.getElementById('deleteNoteBtn');
        const cancelBtn = document.getElementById('cancelNoteBtn');

        // 关闭弹窗
        closeBtn.onclick = () => modal.style.display = 'none';

        // 点击弹窗外部关闭
        modal.onclick = (e) => {
            if (e.target === modal) modal.style.display = 'none';
        };

        // 保存备注
        saveBtn.onclick = () => this.saveNote();

        // 删除备注
        deleteBtn.onclick = () => this.deleteNote();

        // 取消
        cancelBtn.onclick = () => modal.style.display = 'none';
    }

    async saveNote() {
        const stockCode = document.getElementById('noteStockCode').value;
        const tradeDate = document.getElementById('noteTradeDate').value;
        const notes = document.getElementById('noteContent').value;
        const strategyType = document.getElementById('noteStrategyType').value;
        const riskLevel = document.getElementById('noteRiskLevel').value;

        if (!notes.trim()) {
            alert('请输入备注内容');
            return;
        }

        try {
            // 使用upsert接口，自动处理创建或更新
            const response = await authFetch(`${API_BASE_URL}/api/trading_notes/upsert`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    stock_code: stockCode,
                    trade_date: tradeDate,
                    notes: notes,
                    strategy_type: strategyType,
                    risk_level: riskLevel,
                    created_by: 'wangxw1' // 这里应该从用户登录信息获取
                })
            });

            if (response.ok) {
                const result = await response.json();
                alert(result.message);
                document.getElementById('notesModal').style.display = 'none';
                this.searchHistory(); // 刷新数据
            } else {
                throw new Error('保存失败');
            }

        } catch (error) {
            console.error('保存备注失败:', error);
            alert('保存失败: ' + error.message);
        }
    }

    async deleteNote() {
        const stockCode = document.getElementById('noteStockCode').value;
        const tradeDate = document.getElementById('noteTradeDate').value;

        if (!confirm('确定要删除这条备注吗？')) return;

        try {
            // 先查询备注ID
            const checkResponse = await authFetch(`${API_BASE_URL}/api/trading_notes/${stockCode}?trade_date=${tradeDate}`);

            if (checkResponse.ok) {
                const existingNotes = await checkResponse.json();
                if (existingNotes && existingNotes.length > 0) {
                    // 删除备注
                    const deleteResponse = await authFetch(`${API_BASE_URL}/api/trading_notes/${existingNotes[0].id}`, {
                        method: 'DELETE'
                    });

                    if (deleteResponse.ok) {
                        alert('备注删除成功');
                        document.getElementById('notesModal').style.display = 'none';
                        this.searchHistory(); // 刷新数据
                    } else {
                        throw new Error('删除失败');
                    }
                } else {
                    alert('没有找到要删除的备注');
                }
            } else {
                throw new Error('查询备注失败');
            }

        } catch (error) {
            console.error('删除备注失败:', error);
            alert('删除失败: ' + error.message);
        }
    }


    showIndicators(code, startDate, endDate) {
        // 打开新窗口展示指标数据
        const width = 1200;
        const height = 800;
        const left = (window.screen.width - width) / 2;
        const top = (window.screen.height - height) / 2;
        window.open(
            `indicator_data.html?code=${code}&start_date=${startDate}&end_date=${endDate}`,
            'IndicatorData',
            `width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=yes`
        );
    }
}

// 测试查询按钮登录验证（用于调试）
window.testHistoryQueryAuth = function () {
    console.log('测试历史行情查询按钮登录验证...');

    // 清除本地存储模拟登录失效
    localStorage.removeItem('access_token');
    localStorage.removeItem('userInfo');
    localStorage.removeItem('token');

    // 模拟点击查询按钮
    if (window.stockHistoryPage) {
        window.stockHistoryPage.searchHistory();
    } else {
        console.log('StockHistoryPage 未初始化');
    }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    window.stockHistoryPage = new StockHistoryPage();
}); 
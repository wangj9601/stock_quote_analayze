// 自选股页面功能模块
const WatchlistPage = {
    // 全局API前缀
    //API_BASE_URL: 'http://192.168.31.237:5000',
    
    // 修改获取用户ID的方法
    async getUserId() {
        try {
            const res = await authFetch(`${API_BASE_URL}/api/auth/status`);
            const result = await res.json();
            console.log('获取用户ID结果:', result);
            // 兼容 result.user 和 result.data
            let user = result.user || result.data;
            if (result.success && user && typeof user.id !== 'undefined' && user.id !== null) {
                const userId = user.id;
                console.log('获取到当前用户ID:', userId);
                return userId;
            }
            console.log('未获取到用户ID');
            return null;
        } catch (e) {
            console.error('获取用户ID失败:', e);
            return null;
        }
    },

    // 模拟数据
    // stocksData: [
       //  { code: '000001', name: '平安银行', price: 12.34, change: 0.56, percent: 4.76, group: 'bank', open: 11.89, high: 12.45, low: 11.85, volume: '1.2亿' },
        // { code: '600036', name: '招商银行', price: 45.67, change: 1.23, percent: 2.77, group: 'bank', open: 44.50, high: 45.89, low: 44.23, volume: '3.5亿' },
        // { code: '600519', name: '贵州茅台', price: 1865.00, change: -12.50, percent: -0.67, group: 'consumption', open: 1875.00, high: 1890.00, low: 1860.00, volume: '0.8亿' },
        // { code: '000858', name: '五粮液', price: 156.78, change: 3.45, percent: 2.25, group: 'consumption', open: 154.20, high: 158.90, low: 153.10, volume: '2.1亿' },
        // { code: '002415', name: '海康威视', price: 32.45, change: 1.56, percent: 5.05, group: 'tech', open: 31.20, high: 32.67, low: 30.95, volume: '4.2亿' },
        // { code: '300750', name: '宁德时代', price: 187.50, change: 8.90, percent: 4.99, group: 'tech', open: 180.00, high: 189.90, low: 178.20, volume: '6.8亿' }
    // ],

    // 分组数据
    groups: ['default', 'bank', 'tech', 'consumption'],
    selectedGroup: 'default',

    currentView: 'grid',

    // 修改 loadWatchlist 方法
    async loadWatchlist() {
        try {
            const user_id = await this.getUserId();
            if (!user_id) {
                console.log('未获取到用户ID，无法加载自选股');
                return;
            }
            console.log('加载自选股数据，用户ID:', user_id);
            const res = await authFetch(`${API_BASE_URL}/api/watchlist?user_id=${user_id}`);
            const result = await res.json();
            console.log('后端返回数据:', result);
            if (result.success && result.data && result.data.length > 0) {
                this.stocksData = result.data.map(item => ({
                    code: item.code,
                    name: item.name,
                    price: item.current_price,
                    change: item.change_amount,
                    percent: item.change_percent,
                    group: item.group_name || 'default',
                    open: item.open,
                    high: item.high,
                    low: item.low,
                    yesterday_close: item.yesterday_close,
                    volume: item.volume
                }));
                console.log('stocksData:', this.stocksData);

            } else {
                this.stocksData = [];
            }
            // 加在这里：数据加载后立即刷新页面
            this.updateStockCount();
            this.renderStocks();
        } catch (e) {
            console.error('加载自选股数据异常:', e);
            this.stocksData = [];
            // 加在这里：数据加载后立即刷新页面
            this.updateStockCount();
            this.renderStocks();
        }
    },

    // 修改初始化方法
    async init() {
        try {
            const user_id = await this.getUserId();
            if (!user_id) {
                console.log('未获取到用户ID，请先登录');
                return;
            }
            
            await this.loadGroups();
            await this.loadWatchlist();
            this.bindEvents();
            this.updateStockCount();
            this.renderStocks();
            this.startDataUpdate();
        } catch (e) {
            console.error('初始化失败:', e);
        }
    },

    // 绑定事件
    bindEvents() {
        // 分组标签切换
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.switchGroup(btn.dataset.group);
                this.updateActiveTab(btn);
            });
        });

        // 视图切换
        document.querySelectorAll('.view-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.switchView(btn.dataset.view);
                this.updateActiveView(btn);
            });
        });

        // 添加自选股按钮
        document.querySelector('.add-stock-btn').addEventListener('click', () => {
            this.showAddStockModal();
        });

        // 删除自选股按钮
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('remove-btn')) {
                const card = e.target.closest('.stock-card');
                const code = card.dataset.code;
                this.removeStock(code);
            }
        });

        // 添加自选股弹窗相关
        this.bindModalEvents();

        // 注释掉价格提醒相关的事件绑定
        // this.bindAlertEvents();
    },

    // 绑定弹窗事件
    bindModalEvents() {
        const modal = document.getElementById('addStockModal');
        const closeBtn = modal.querySelector('.close-modal');
        const cancelBtn = modal.querySelector('.cancel-btn');
        const confirmBtn = modal.querySelector('.confirm-btn');
        const searchInput = modal.querySelector('.stock-search-input');

        // 关闭弹窗
        [closeBtn, cancelBtn].forEach(btn => {
            btn.addEventListener('click', () => {
                this.hideAddStockModal();
            });
        });

        // 点击背景关闭
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.hideAddStockModal();
            }
        });

        // 搜索输入
        searchInput.addEventListener('input', (e) => {
            this.searchStocks(e.target.value);
        });

        // 确认添加
        confirmBtn.addEventListener('click', () => {
            this.confirmAddStock();
        });
    },

    // 绑定价格提醒事件
    // bindAlertEvents() {
    //     document.querySelector('.add-alert-btn').addEventListener('click', () => {
    //         this.showAddAlertModal();
    //     });
    //
    //     // 删除提醒
    //     document.addEventListener('click', (e) => {
    //         if (e.target.textContent === '删除' && e.target.closest('.alert-actions')) {
    //             const alertItem = e.target.closest('.alert-item');
    //             this.removeAlert(alertItem);
    //         }
    //     });
    // },

    // 切换分组
    switchGroup(group) {
        this.selectedGroup = group;
        this.renderStocks();
    },

    // 更新活动标签
    updateActiveTab(activeBtn) {
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        activeBtn.classList.add('active');
    },

    // 切换视图
    switchView(view) {
        this.currentView = view;
        const gridView = document.getElementById('stocksGrid');
        const listView = document.getElementById('stocksList');

        if (view === 'grid') {
            gridView.style.display = 'grid';
            listView.style.display = 'none';
        } else {
            gridView.style.display = 'none';
            listView.style.display = 'block';
            this.renderListView();
        }
    },

    // 更新活动视图按钮
    updateActiveView(activeBtn) {
        document.querySelectorAll('.view-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        activeBtn.classList.add('active');
    },

    // 渲染股票列表
    renderStocks() {
        console.log('selectedGroup:', this.selectedGroup, 'stocksData:', this.stocksData);
        const filteredStocks = (this.selectedGroup === 'default' || this.selectedGroup === 'all')
        ? this.stocksData
        : this.stocksData.filter(stock => stock.group === this.selectedGroup);

        if (this.currentView === 'grid') {
            this.renderGridView(filteredStocks);
        } else {
            this.renderListView(filteredStocks);
        }
    },

    // 渲染网格视图
    renderGridView(stocks) {
        const grid = document.getElementById('stocksGrid');
        if (!stocks.length) {
            grid.innerHTML = '<div class="empty-tip" style="text-align:center;padding:2em 0;color:#888;font-size:1.2em;">暂无自选股</div>';
            return;
        }
        grid.innerHTML = stocks.map(stock => `
            <div class="stock-card" data-code="${stock.code}" data-group="${stock.group}">
                <div class="stock-header">
                    <div class="stock-basic">
                        <h3 class="stock-name">${stock.name}</h3>
                        <span class="stock-code">${stock.code}</span>
                    </div>
                    <button class="remove-btn">×</button>
                </div>
                <div class="stock-price">
                    <span class="current-price">${this.formatPrice(stock.price)}</span>
                    <span class="price-change ${this.getChangeClass(stock.change)}">${this.formatChange(stock.change)}</span>
                    <span class="change-percent ${this.getChangeClass(stock.change)}">${this.formatPercent(stock.percent)}</span>
                </div>
                <div class="stock-details">
                    <div class="detail-row">
                        <span>今开</span>
                        <span>${this.formatPrice(stock.open)}</span>
                    </div>
                    <div class="detail-row">
                        <span>昨收</span>
                        <span>${this.formatPrice(stock.yesterday_close)}</span>
                    </div>
                    <div class="detail-row">
                        <span>最高</span>
                        <span class="positive">${this.formatPrice(stock.high)}</span>
                    </div>
                    <div class="detail-row">
                        <span>最低</span>
                        <span class="negative">${this.formatPrice(stock.low)}</span>
                    </div>
                </div>
                <div class="stock-actions">
                    <button class="action-btn" onclick="goToStock('${stock.code}', '${stock.name}')">详情</button>
                    <button class="action-btn trade-btn" onclick="goToStockHistory('${stock.code}')" >历史</button>
                </div>
            </div>
        `).join('');
        this.renderBatchActions();
    },

    // 渲染列表视图
    renderListView(stocks) {
        const tbody = document.getElementById('stocksTableBody');
        if (!tbody) return;

        const filteredStocks = stocks || (this.selectedGroup === 'default' 
            ? this.stocksData 
            : this.stocksData.filter(stock => stock.group === this.selectedGroup));

        if (!filteredStocks.length) {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:#888;font-size:1.2em;">暂无自选股</td></tr>';
            return;
        }

        tbody.innerHTML = filteredStocks.map(stock => `
            <tr data-code="${stock.code}">
                <td>
                    <div class="stock-info-cell">
                        <span class="stock-name">${stock.name}</span>
                        <span class="stock-code">${stock.code}</span>
                    </div>
                </td>
                <td>${this.formatPrice(stock.price)}</td>
                <td class="${this.getChangeClass(stock.change)}">${this.formatChange(stock.change)}</td>
                <td class="${this.getChangeClass(stock.percent)}">${this.formatPercent(stock.percent)}</td>
                <td>${this.formatPrice(stock.open)}</td>
                <td class="positive">${this.formatPrice(stock.high)}</td>
                <td class="negative">${this.formatPrice(stock.low)}</td>
                <td>${this.formatVolume(stock.volume)}</td>
                <td>
                    <button class="btn btn-secondary" style="margin-right:8px;" onclick="goToStock('${stock.code}', '${stock.name}')">详情</button>
                    <button class="btn btn-danger remove-btn">删除</button>
                </td>
            </tr>
        `).join('');
    },

    // 显示添加自选股弹窗
    showAddStockModal() {
        const modal = document.getElementById('addStockModal');
        modal.classList.add('active');
        modal.querySelector('.stock-search-input').focus();
    },

    // 隐藏添加自选股弹窗
    hideAddStockModal() {
        const modal = document.getElementById('addStockModal');
        modal.classList.remove('active');
        modal.querySelector('.stock-search-input').value = '';
        document.querySelector('.search-suggestions').style.display = 'none';
        this.selectedStock = null;
        this._adding = false;
    },

    // 搜索股票（后端API）
    async searchStocks(query) {
        if (!query.trim()) {
            document.querySelector('.search-suggestions').style.display = 'none';
            return;
        }
        try {
            const res = await authFetch(`${API_BASE_URL}/api/stock/list?query=${encodeURIComponent(query)}`);
            const result = await res.json();
            if (result.success) {
                this.renderSearchResults(result.data);
            } else {
                this.renderSearchResults([]);
            }
        } catch {
            this.renderSearchResults([]);
        }
    },

    // 渲染搜索结果
    renderSearchResults(results) {
        const container = document.querySelector('.search-suggestions');
        if (results.length === 0) {
            container.innerHTML = '<div class="suggestion-item">未找到相关股票</div>';
        } else {
            container.innerHTML = results.map(stock =>
                `<div class="suggestion-item" data-code="${stock.code}" data-name="${stock.name}">
                    <span style="font-weight: 600;">${stock.code}</span>
                    <span style="margin-left: 0.5rem;">${stock.name}</span>
                    <button class="btn btn-xs btn-danger del-group-btn" data-group="${stock.name}">×</button>
                </div>`
            ).join('');
            // 绑定点击事件
            container.querySelectorAll('.suggestion-item').forEach(item => {
                item.addEventListener('click', () => {
                    document.querySelector('.stock-search-input').value = `${item.dataset.code} ${item.dataset.name}`;
                    this.selectedStock = { code: item.dataset.code, name: item.dataset.name };
                    container.style.display = 'none';
                });
            });
        }
        container.style.display = 'block';
    },

    // 修改 confirmAddStock 方法
    async confirmAddStock() {
        // 防止多次点击
        if (this._adding) return;
        this._adding = true;

        await this.loadWatchlist();
        const input = document.querySelector('.stock-search-input');
        const groupSelect = document.querySelector('.group-select');
        const group_name = groupSelect.value || 'default';

        // 只在未选择股票时才提示
        if (!this.selectedStock || !this.selectedStock.code) {
            CommonUtils.showToast('请选择要添加的股票', 'warning');
            this._adding = false;
            return;
        }
        const stockInfo = this.selectedStock;
        const user_id = await this.getUserId();
        if (!user_id) {
            CommonUtils.showToast('请先登录', 'warning');
            this._adding = false;
            return;
        }
        if (this.stocksData.some(s => s.code === stockInfo.code && s.group === group_name)) {
            CommonUtils.showToast('该股票已在该分组中', 'warning');
            this._adding = false;
            return;
        }
        try {
            const res = await authFetch(`${API_BASE_URL}/api/watchlist`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id,
                    stock_code: stockInfo.code,
                    stock_name: stockInfo.name,
                    group_name
                })
            });
            const result = await res.json();
            if (result.success) {
                CommonUtils.showToast('股票已添加到自选', 'success');
                this.hideAddStockModal();
                this.selectedStock = null;
                input.value = '';
                await this.loadWatchlist();
                this.switchGroup(group_name);
                this.updateStockCount();
                this.renderStocks();
                this._adding = false;
                return;
            } else {
                CommonUtils.showToast(result.message || '添加失败', 'error');
            }
        } catch (e) {
            CommonUtils.showToast('网络错误，添加失败', 'error');
        }
        this._adding = false;
    },

    // 删除自选股
    async removeStock(code) {
        const stock = this.stocksData.find(s => s.code === code);
        if (!stock) return;
        const user_id = await this.getUserId();
        if (!user_id) return;
        try {
            const res = await authFetch(`${API_BASE_URL}/api/watchlist/delete_by_code`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id, stock_code: code })
            });
            const result = await res.json();
            if (!result.success) return;
            // 先本地移除
            this.stocksData = this.stocksData.filter(s => s.code !== code);
        } catch (e) {
            return;
        }
        // 再刷新
        await this.loadWatchlist();
        CommonUtils.showToast(`${stock.name} 已移出自选`, 'info');
    },

    // 更新股票计数
    updateStockCount() {
        const count = this.stocksData.length;
        document.getElementById('stockCount').textContent = count;
        
        // 更新分组计数
        this.updateGroupCounts();
    },

    // 更新分组计数
    updateGroupCounts() {
        const groups = {
            default: this.stocksData.length,
            bank: this.stocksData.filter(s => s.group === 'bank').length,
            tech: this.stocksData.filter(s => s.group === 'tech').length,
            consumption: this.stocksData.filter(s => s.group === 'consumption').length
        };

        document.querySelectorAll('.tab-btn').forEach(btn => {
            const group = btn.dataset.group;
            if (groups[group] !== undefined) {
                const text = btn.textContent.split(' (')[0];
                btn.textContent = `${text} (${groups[group]})`;
            }
        });
    },

    // 显示添加提醒弹窗
    showAddAlertModal() {
        CommonUtils.showToast('添加价格提醒功能', 'info');
    },

    // 删除提醒
    removeAlert(alertItem) {
        alertItem.remove();
        CommonUtils.showToast('价格提醒已删除', 'info');
    },

    // 格式化价格
    formatPrice(price) {
        if (price === null || price === undefined || isNaN(price)) return '--';
        return parseFloat(price).toFixed(2);
    },

    // 格式化涨跌额
    formatChange(change) {
        if (change === null || change === undefined || isNaN(change)) return '--';
        return change >= 0 ? `+${change.toFixed(2)}` : change.toFixed(2);
    },

    // 格式化涨跌幅
    formatPercent(percent) {
        if (percent === null || percent === undefined || isNaN(percent)) return '--';
        return percent >= 0 ? `+${percent.toFixed(2)}%` : `${percent.toFixed(2)}%`;
    },

    // 获取涨跌样式类
    getChangeClass(value) {
        if (value > 0) return 'positive';
        if (value < 0) return 'negative';
        return '';
    },

    // 格式化成交量
    formatVolume(volume) {
        if (volume === null || volume === undefined || isNaN(volume)) return '--';
        return volume;
    },

    // 开始数据更新
    startDataUpdate() {
        const getNextInterval = () => {
            const now = new Date();
            const hour = now.getHours();
            const minute = now.getMinutes();
            // 早盘 9:00-11:30
            const inMorning = (hour === 9 && minute >= 0) || (hour === 10) || (hour === 11 && minute <= 30);
            // 午盘 13:30-15:30
            const inAfternoon = (hour === 13 && minute >= 30) || (hour === 14) || (hour === 15 && minute <= 30);
            if (inMorning || inAfternoon) {
                return 300000; // 30秒
            } else {
                return 600000; // 600秒
            }
        };
        const scheduleUpdate = () => {
            this.updateStockPrices();
            const interval = getNextInterval();
            this._dataUpdateTimer = setTimeout(scheduleUpdate, interval);
        };
        if (this._dataUpdateTimer) clearTimeout(this._dataUpdateTimer);
        scheduleUpdate();
    },

    // 更新股票价格
    updateStockPrices() {
        const codes = this.stocksData.map(stock => stock.code);
        if (!codes.length) return;
        authFetch(`${API_BASE_URL}/api/stock/quote`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ codes })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success && Array.isArray(data.data)) {
                // 用后端返回的新行情数据重写 this.stocksData，保留原有 name/group 字段
                this.stocksData = data.data.map(newStock => {
                    // 查找原有 name/group 信息
                    const old = this.stocksData.find(s => s.code === newStock.code) || {};
                    return {
                        code: newStock.code,
                        name: old.name || '',
                        group: old.group || 'default',
                        price: newStock.current_price,
                        change: newStock.change_amount,
                        percent: newStock.change_percent,
                        open: newStock.open,
                        yesterday_close: newStock.yesterday_close,
                        high: newStock.high,
                        low: newStock.low,
                        volume: newStock.volume,
                        turnover: newStock.turnover
                    };
                });
                this.renderStocks();
            }
        });
    },

    // 加载分组
    async loadGroups() {
        const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
        if (!userInfo.id) return;
        const res = await authFetch(`${API_BASE_URL}/api/watchlist/groups?user_id=${userInfo.id}`);
        const result = await res.json();
        if (result.success) {
            this.groups = ['default', ...result.data];
            this.renderGroupTabs();
            this.renderGroupSelect();
        }
    },

    // 渲染分组标签（带重命名/删除按钮）
    renderGroupTabs() {
        const nav = document.querySelector('.tabs-nav');
        // 回退：不设置内联样式，恢复原始布局
        // 确保 'default' 始终在首位且唯一
        const groups = ['default', ...this.groups.filter(g => g !== 'default')];
        nav.innerHTML = groups.map(g =>
            g === 'default'
                ? `<button class="tab-btn${this.selectedGroup==='default'?' active':''}" data-group="default">全部</button>`
                : `<span class="group-tab-wrap"><button class="tab-btn${this.selectedGroup===g?' active':''}" data-group="${g}">${g}</button><span class="group-actions"><button class="rename-group-btn" title="重命名">✎</button><button class="del-group-btn" title="删除">×</button></span></span>`
        ).join('') + '<button class="add-group-btn">+ 新建分组</button>';
        // 绑定事件
        nav.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.switchGroup(btn.dataset.group);
                this.updateActiveTab(btn);
            });
        });
        nav.querySelectorAll('.rename-group-btn').forEach((btn, i) => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const group = groups[i+1];
                this.renameGroup(group);
            });
        });
        nav.querySelectorAll('.del-group-btn').forEach((btn, i) => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const group = groups[i+1];
                this.deleteGroup(group);
            });
        });
        nav.querySelector('.add-group-btn').addEventListener('click', () => {
            this.showCreateGroupModal();
        });
    },

    // 渲染分组下拉
    renderGroupSelect() {
        const select = document.querySelector('.group-select');
        if (!select) return;
        select.innerHTML = this.groups.filter(g=>g!=='default').map(g => `<option value="${g}">${g}</option>`).join('');
    },

    // 新建分组弹窗
    showCreateGroupModal() {
        const name = prompt('请输入新分组名称');
        if (name && name.trim()) {
            this.createGroup(name.trim());
        }
    },

    // 新建分组
    async createGroup(name) {
        const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
        if (!userInfo.id) return;
        const res = await authFetch(`${API_BASE_URL}/api/watchlist/groups`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userInfo.id, group_name: name })
        });
        const result = await res.json();
        if (result.success) {
            CommonUtils.showToast('分组创建成功', 'success');
            this.loadGroups();
        } else {
            CommonUtils.showToast(result.message || '创建失败', 'error');
        }
    },

    // 删除分组
    async deleteGroup(name) {
        const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
        if (!userInfo.id) return;
        if (!confirm(`确定删除分组"${name}"及其下所有自选股？`)) return;
        const res = await authFetch(`${API_BASE_URL}/api/watchlist/groups`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userInfo.id, group_name: name })
        });
        const result = await res.json();
        if (result.success) {
            CommonUtils.showToast('分组已删除', 'success');
            this.loadGroups();
        } else {
            CommonUtils.showToast(result.message || '删除失败', 'error');
        }
    },

    // 分组重命名
    async renameGroup(oldName) {
        const newName = prompt('请输入新的分组名称', oldName);
        if (!newName || newName.trim() === oldName) return;
        const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
        if (!userInfo.id) return;
        const res = await authFetch(`${API_BASE_URL}/api/watchlist/groups/rename`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userInfo.id, old_name: oldName, new_name: newName.trim() })
        });
        const result = await res.json();
        if (result.success) {
            CommonUtils.showToast('分组重命名成功', 'success');
            this.loadGroups();
        } else {
            CommonUtils.showToast(result.message || '重命名失败', 'error');
        }
    },

    // 批量操作相关
    selectedStocks: new Set(),
    toggleSelectStock(code) {
        if (this.selectedStocks.has(code)) {
            this.selectedStocks.delete(code);
        } else {
            this.selectedStocks.add(code);
        }
        this.renderStocks();
        this.renderBatchActions();
    },
    selectAllStocks() {
        const filteredStocks = this.selectedGroup === 'default' ? this.stocksData : this.stocksData.filter(s => s.group === this.selectedGroup);
        filteredStocks.forEach(s => this.selectedStocks.add(s.code));
        this.renderStocks();
        this.renderBatchActions();
    },
    clearSelectedStocks() {
        this.selectedStocks.clear();
        this.renderStocks();
        this.renderBatchActions();
    },
    // 批量删除
    async batchDeleteStocks() {
        if (!this.selectedStocks.size) return;
        if (!confirm('确定批量删除选中的自选股？')) return;
        // 实际应调用后端批量删除API，这里本地模拟
        this.stocksData = this.stocksData.filter(s => !this.selectedStocks.has(s.code));
        this.clearSelectedStocks();
        this.updateStockCount();
        this.renderStocks();
        CommonUtils.showToast('批量删除成功', 'success');
    },
    // 批量移动分组
    async batchMoveGroup(newGroup) {
        if (!this.selectedStocks.size) return;
        // 实际应调用后端批量移动API，这里本地模拟
        this.stocksData.forEach(s => {
            if (this.selectedStocks.has(s.code)) s.group = newGroup;
        });
        this.clearSelectedStocks();
        this.updateStockCount();
        this.renderStocks();
        CommonUtils.showToast('批量移动成功', 'success');
    },
    // 批量操作区渲染
    renderBatchActions() {
        const container = document.querySelector('.batch-actions');
        if (!container) return;
        container.innerHTML = `
            <button class="btn btn-sm" onclick="WatchlistPage.selectAllStocks()">全选</button>
            <button class="btn btn-sm" onclick="WatchlistPage.clearSelectedStocks()">取消全选</button>
            <button class="btn btn-danger btn-sm" onclick="WatchlistPage.batchDeleteStocks()">批量删除</button>
            <select class="batch-move-select" onchange="WatchlistPage.batchMoveGroup(this.value)">
                <option value="">批量移动到分组</option>
                ${this.groups.filter(g=>g!=='default').map(g=>`<option value="${g}">${g}</option>`).join('')}
            </select>
        `;
    }
};

// 全局函数：跳转到股票详情
function goToStock(code, name) {
    //window.location.href = `stock.html?code=${code}`;
    window.location.href = `stock.html?code=${code}&name=${encodeURIComponent(name)}`;
}

function goToStockHistory(code, name) {
    window.location.href = `stock_history.html?code=${code}`;
}

// DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    WatchlistPage.init();
}); 
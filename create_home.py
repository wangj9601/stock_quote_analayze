#!/usr/bin/env python3
# -*- coding: utf-8 -*-

home_js_content = """// 首页主要功能
class HomePage {
    constructor() {
        this.init();
        this.loadMarketData();
        this.loadWatchlist();
        this.loadHotSectors();
        this.loadTopGainers();
        this.loadNews();
        this.loadRecommendations();
        
        // 设置自动刷新
        this.startAutoRefresh();
    }

    init() {
        // 初始化搜索功能
        this.initSearch();
        
        // 检查登录状态
        this.checkAuthStatus();
    }

    async checkAuthStatus() {
        try {
            const response = await fetch(`${API_BASE_URL}/api/auth/status`, {
                credentials: 'include'
            });
            const result = await response.json();
            
            if (result.success && result.logged_in) {
                this.updateUserInfo(result.user);
            } else {
                this.showLoginPrompt();
            }
        } catch (error) {
            console.error('检查登录状态失败:', error);
            this.showLoginPrompt();
        }
    }

    updateUserInfo(user) {
        const userNameElement = document.querySelector('.user-name');
        if (userNameElement) {
            userNameElement.textContent = user.username;
        }
    }

    showLoginPrompt() {
        const userNameElement = document.querySelector('.user-name');
        if (userNameElement) {
            userNameElement.innerHTML = '<a href="login.html" style="color: var(--color-primary);">登录</a>';
        }
    }

    async loadMarketData() {
        try {
            const response = await fetch(`${API_BASE_URL}/api/market/indices`);
            const result = await response.json();
            
            if (result.success) {
                this.displayMarketIndices(result.data);
            } else {
                console.error('加载市场数据失败:', result.message);
            }
        } catch (error) {
            console.error('加载市场数据失败:', error);
        }
    }

    displayMarketIndices(indices) {
        console.log('接收到指数数据:', indices);
        
        indices.forEach(index => {
            // 根据指数代码精确匹配卡片
            const card = document.querySelector(`[data-index-code="${index.code}"]`);
            if (!card) {
                console.warn(`未找到指数代码 ${index.code} 对应的卡片`);
                return;
            }
            
            const nameElement = card.querySelector('.index-name');
            const valueElement = card.querySelector('.index-value');
            const changeElement = card.querySelector('.index-change');
            const volumeElement = card.querySelector('.index-volume');
            const timeElement = card.querySelector('.index-time');
            
            // 更新指数名称
            if (nameElement) nameElement.textContent = index.name;
            
            // 更新指数数值
            if (valueElement) {
                valueElement.textContent = parseFloat(index.current).toLocaleString('zh-CN', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                });
            }
            
            // 更新涨跌信息
            if (changeElement) {
                const changeValue = parseFloat(index.change);
                const changePercent = parseFloat(index.change_percent);
                const changeText = `${changeValue >= 0 ? '+' : ''}${changeValue.toFixed(2)} (${changePercent >= 0 ? '+' : ''}${changePercent.toFixed(2)}%)`;
                changeElement.textContent = changeText;
                changeElement.className = `index-change ${changeValue >= 0 ? 'positive' : 'negative'}`;
            }
            
            // 更新成交量
            if (volumeElement && index.volume) {
                const volume = parseFloat(index.volume);
                let volumeText;
                if (volume >= 100000000) {
                    volumeText = `${(volume / 100000000).toFixed(1)}亿`;
                } else if (volume >= 10000) {
                    volumeText = `${(volume / 10000).toFixed(1)}万`;
                } else {
                    volumeText = volume.toString();
                }
                volumeElement.textContent = `成交量: ${volumeText}`;
            }
            
            // 更新时间
            if (timeElement && index.timestamp) {
                const time = new Date(index.timestamp);
                const timeStr = time.toLocaleTimeString('zh-CN', { 
                    hour: '2-digit', 
                    minute: '2-digit',
                    second: '2-digit'
                });
                timeElement.textContent = `更新时间: ${timeStr}`;
            } else if (timeElement) {
                const now = new Date();
                const timeStr = now.toLocaleTimeString('zh-CN', { 
                    hour: '2-digit', 
                    minute: '2-digit',
                    second: '2-digit'
                });
                timeElement.textContent = `更新时间: ${timeStr}`;
            }
        });
    }

    async loadWatchlist() {
        try {
            const response = await fetch(`${API_BASE_URL}/api/watchlist`, {
                credentials: 'include'
            });
            const result = await response.json();
            
            if (result.success) {
                this.displayWatchlist(result.data.slice(0, 3)); // 只显示前3个
            } else if (result.message === '请先登录') {
                this.displayEmptyWatchlist();
            }
        } catch (error) {
            console.error('加载自选股失败:', error);
            this.displayEmptyWatchlist();
        }
    }

    displayWatchlist(stocks) {
        const stockList = document.querySelector('.stock-list');
        if (!stockList) return;

        if (stocks.length === 0) {
            stockList.innerHTML = '<div class="empty-message">暂无自选股，<a href="watchlist.html">去添加</a></div>';
            return;
        }

        stockList.innerHTML = stocks.map(stock => `
            <div class="stock-item" data-code="${stock.code}">
                <div class="stock-info">
                    <span class="stock-code">${stock.code}</span>
                    <span class="stock-name">${stock.name}</span>
                </div>
                <div class="stock-price">
                    <span class="price">${stock.current_price || '0.00'}</span>
                    <span class="change ${(stock.change_amount || 0) >= 0 ? 'positive' : 'negative'}">
                        ${(stock.change_amount || 0) >= 0 ? '+' : ''}${stock.change_amount || 0}
                    </span>
                </div>
            </div>
        `).join('');

        // 添加点击事件
        stockList.querySelectorAll('.stock-item').forEach(item => {
            item.addEventListener('click', () => {
                const code = item.dataset.code;
                window.location.href = `stock.html?code=${code}`;
            });
        });
    }

    displayEmptyWatchlist() {
        // 移除内置测试数据，显示空的自选股列表
        const stockList = document.querySelector('.stock-list');
        if (!stockList) return;

        stockList.innerHTML = '<div class="empty-message">暂无自选股数据，<a href="watchlist.html">去添加</a></div>';
    }

    startAutoRefresh() {
        // 每30秒刷新一次数据
        setInterval(() => {
            this.loadMarketData();
            this.loadWatchlist();
        }, 30000);
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    new HomePage();
});"""

with open('frontend/js/home.js', 'w', encoding='utf-8') as f:
    f.write(home_js_content)

print("home.js 文件已创建成功！") 
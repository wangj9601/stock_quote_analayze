
const API_BASE_URL = window.API_BASE_URL || 'http://localhost:5000';


// 首页数据管理
document.addEventListener('DOMContentLoaded', function() {
    console.log('首页初始化开始...');
    
    // 先显示加载状态
    showLoadingState();
    
    // 立即加载真实数据
    loadRealData();
    
    // 绑定交互事件
    bindEvents();
    
    console.log('首页初始化完成');
});

// 显示加载状态
function showLoadingState() {
    console.log('显示加载状态...');
    
    // 可以保持现有的加载中状态，很快就会被真实数据替换
}

// 加载真实数据
async function loadRealData() {
    console.log('开始加载真实数据...');
    
    try {
        // 并行加载所有数据
        await Promise.all([
            loadMarketIndices(),
            loadWatchlist(),
            loadSectors(),
            loadGainers(),
            loadNews(),
            loadUserInfo()
        ]);
        
        console.log('所有数据加载完成');
    } catch (error) {
        console.error('数据加载失败:', error);
        // 如果API调用失败，显示模拟数据
        showFallbackData();
    }
}

// 加载市场指数数据
async function loadMarketIndices() {
    try {
        console.log('加载指数数据...');
        //const response = await authFetch('http://localhost:5000/api/market/indices');
        const response = await authFetch(`${API_BASE_URL}/api/market/indices`);
        const result = await response.json();
        
        if (result.success && result.data) {
            updateIndexDisplay(result.data);
            console.log('指数数据加载成功');
        } else {
            throw new Error('API返回错误');
        }
    } catch (error) {
        console.error('指数数据加载失败:', error);
        // 使用模拟数据作为后备
        const fallbackData = [
            { code: '000001', name: '上证指数', current: 3234.56, change: 12.34, change_percent: 0.38, volume: 12456789 },
            { code: '399001', name: '深证成指', current: 11456.78, change: -23.45, change_percent: -0.20, volume: 8567123 },
            { code: '399006', name: '创业板指', current: 2345.67, change: 5.67, change_percent: 0.24, volume: 5678901 },
            { code: '000300', name: '沪深300', current: 4567.89, change: -8.90, change_percent: -0.19, volume: 9876543 }
        ];
        updateIndexDisplay(fallbackData);
        console.log('使用模拟指数数据');
    }
}

// 更新指数显示
function updateIndexDisplay(indicesData) {
    indicesData.forEach(function(index) {
        const card = document.querySelector('[data-index-code="' + index.code + '"]');
        if (card) {
            const valueEl = card.querySelector('.index-value');
            const changeEl = card.querySelector('.index-change');
            const volumeEl = card.querySelector('.index-volume');
            const timeEl = card.querySelector('.index-time');
            
            if (valueEl) {
                valueEl.textContent = index.current.toFixed(2);
            }
            
            if (changeEl) {
                const changeStr = index.change >= 0 ? '+' + index.change.toFixed(2) : index.change.toFixed(2);
                const percentStr = index.change_percent >= 0 ? '+' + index.change_percent.toFixed(2) + '%' : index.change_percent.toFixed(2) + '%';
                changeEl.innerHTML = changeStr + ' (' + percentStr + ')';
                changeEl.className = 'index-change ' + (index.change > 0 ? 'positive' : index.change < 0 ? 'negative' : '');
            }
            
            if (volumeEl) {
                const volume = index.volume || 0;
                volumeEl.textContent = '成交量: ' + (volume / 1e8).toFixed(2) + '亿';
            }
            
            if (timeEl) {
                const updateTime = index.timestamp ? new Date(index.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
                timeEl.textContent = '更新时间: ' + updateTime;
            }
        }
    });
}

// 加载自选股数据
async function loadWatchlist() {
    try {
        console.log('加载自选股数据...');
        //const response = await authFetch('http://localhost:5000/api/watchlist');
        const response = await authFetch(`${API_BASE_URL}/api/watchlist`);
        const result = await response.json();
        
        if (result.success && result.data) {
            updateWatchlistDisplay(result.data.slice(0, 3)); // 只显示前3个
            console.log('自选股数据加载成功');
        } else {
            throw new Error('API返回错误');
        }
    } catch (error) {
        console.error('自选股数据加载失败:', error);
        // 使用模拟数据
        const mockStocks = [
            { code: '600519', name: '贵州茅台', current_price: 1856.78, change_amount: 12.34, change_percent: 0.67 },
            { code: '000858', name: '五粮液', current_price: 145.67, change_amount: -2.34, change_percent: -1.58 },
            { code: '002415', name: '海康威视', current_price: 45.23, change_amount: 0.89, change_percent: 2.01 }
        ];
        updateWatchlistDisplay(mockStocks);
        console.log('使用模拟自选股数据');
    }
}

// 更新自选股显示
function updateWatchlistDisplay(stocks) {
    const stockList = document.querySelector('.stock-list');
    if (stockList) {
        if (stocks.length === 0) {
            stockList.innerHTML = '<div class="empty-state"><p>暂无自选股</p><a href="watchlist.html" class="btn btn-primary">添加自选股</a></div>';
            return;
        }
        
        let stockHTML = '';
        stocks.forEach(function(stock) {
            const changeAmount = stock.change_amount || 0;
            const changePercent = stock.change_percent || 0;
            const currentPrice = stock.current_price || stock.current || 0;
            
            const changeClass = changeAmount > 0 ? 'positive' : changeAmount < 0 ? 'negative' : '';
            const changeSign = changeAmount >= 0 ? '+' : '';
            const percentSign = changePercent >= 0 ? '+' : '';
            
            stockHTML += '<div class="stock-item">' +
                '<div class="stock-info">' +
                    '<div class="stock-code">' + stock.code + '</div>' +
                    '<div class="stock-name">' + stock.name + '</div>' +
                '</div>' +
                '<div class="stock-price">' +
                    '<div class="price">' + currentPrice.toFixed(2) + '</div>' +
                    '<div class="change ' + changeClass + '">' +
                        changeSign + changeAmount.toFixed(2) + ' (' + percentSign + changePercent.toFixed(2) + '%)' +
                    '</div>' +
                '</div>' +
            '</div>';
        });
        stockList.innerHTML = stockHTML;
    }
}

// 加载行业板块数据
async function loadSectors() {
    try {
        console.log('加载板块数据...');
        //const response = await authFetch('http://localhost:5000/api/market/industry_board');
        const response = await authFetch(`${API_BASE_URL}/api/market/industry_board`);
        const result = await response.json();
        
        if (result.success && result.data) {
            updateSectorDisplay(result.data.slice(0, 4)); // 只显示前4个
            console.log('板块数据加载成功');
        } else {
            throw new Error('API返回错误');
        }
    } catch (error) {
        console.error('板块数据加载失败:', error);
        // 使用模拟数据
        const mockSectors = [
            { name: '食品饮料', change_percent: 2.34 },
            { name: '银行', change_percent: -0.87 },
            { name: '电子', change_percent: 1.23 },
            { name: '汽车', change_percent: -1.45 }
        ];
        updateSectorDisplay(mockSectors);
        console.log('使用模拟板块数据');
    }
}

// 工具函数
function formatNumber(val, digits = 2, suffix = '') {
    if (val === undefined || val === null || isNaN(val)) return '--';
    return Number(val).toFixed(digits) + suffix;
}

// 更新板块显示
function updateSectorDisplay(sectors) {
    const sectorList = document.querySelector('.sector-list');
    if (sectorList) {
        let sectorHTML = '';
        sectors.forEach(function(sector) {
            const changeClass = sector.change_percent > 0 ? 'positive' : sector.change_percent < 0 ? 'negative' : '';
            const changeSign = sector.change_percent > 0 ? '+' : '';
            sectorHTML += '<div class="sector-item">' +
                '<div class="sector-name">' + (sector.name || '--') + '</div>' +
                '<div class="sector-change ' + changeClass + '">' +
                    changeSign + formatNumber(sector.change_percent, 2, '%') +
                '</div>' +
            '</div>';
        });
        sectorList.innerHTML = sectorHTML;
    }
}

// 加载涨幅榜数据
async function loadGainers() {
    try {
        console.log('加载涨幅榜数据...');
        //const response = await authFetch('http://localhost:5000/api/stock/quote_board?limit=3');
        const response = await authFetch(`${API_BASE_URL}/api/stock/quote_board?limit=3`);
        const result = await response.json();
        
        if (result.success && result.data) {
            const gainers = result.data
                .filter(stock => stock.change_percent !== undefined && stock.change_percent !== null && !isNaN(stock.change_percent) && stock.change_percent > 0)
                .sort((a, b) => b.change_percent - a.change_percent)
                .slice(0, 3);
            
            if (gainers.length > 0) {
                updateGainersDisplay(gainers);
                console.log('涨幅榜数据加载成功');
            } else {
                const gainerList = document.querySelector('.gainer-list');
                if (gainerList) {
                    gainerList.innerHTML = '<div class="empty-state">暂无涨幅数据</div>';
                }
                console.log('没有涨幅数据');
            }
        } else {
            throw new Error('API返回错误');
        }
    } catch (error) {
        console.error('涨幅榜数据加载失败:', error);
        // 使用模拟数据
        const mockGainers = [
            { code: '002415', name: '海康威视', change_percent: 5.67 },
            { code: '000858', name: '五粮液', change_percent: 3.45 },
            { code: '600036', name: '招商银行', change_percent: 2.34 }
        ];
        updateGainersDisplay(mockGainers);
        console.log('使用模拟涨幅榜数据');
    }
}

// 更新涨幅榜显示
function updateGainersDisplay(gainers) {
    const gainerList = document.querySelector('.gainer-list');
    if (gainerList) {
        let gainerHTML = '';
        gainers.forEach(function(stock, index) {
            gainerHTML += '<div class="rank-item">' +
                '<div class="rank">' + (index + 1) + '</div>' +
                '<div class="stock-info">' +
                    '<div class="stock-code">' + stock.code + '</div>' +
                    '<div class="stock-name">' + stock.name + '</div>' +
                '</div>' +
                '<div class="change-pct positive">+' + stock.change_percent.toFixed(2) + '%</div>' +
            '</div>';
        });
        gainerList.innerHTML = gainerHTML;
    }
}

// 加载新闻数据
async function loadNews() {
    try {
        console.log('加载新闻数据...');
        //const response = await authFetch('http://localhost:5000/api/news?limit=3');
        const response = await authFetch(`${API_BASE_URL}/api/news?limit=3`);
        const result = await response.json();
        
        if (result.success && result.data) {
            updateNewsDisplay(result.data);
            console.log('新闻数据加载成功');
        } else {
            throw new Error('API返回错误');
        }
    } catch (error) {
        console.error('新闻数据加载失败:', error);
        // 使用模拟数据
        const mockNews = [
            {
                title: '市场调整后迎来反弹机会',
                summary: '专家认为当前市场估值合理，优质股票值得关注',
                publish_time: new Date().toISOString()
            },
            {
                title: '新能源板块表现强劲',
                summary: '政策支持下新能源汽车产业链持续受益',
                publish_time: new Date(Date.now() - 3600000).toISOString()
            },
            {
                title: '银行股集体上涨',
                summary: '利率上升预期推动银行股走强',
                publish_time: new Date(Date.now() - 7200000).toISOString()
            }
        ];
        updateNewsDisplay(mockNews);
        console.log('使用模拟新闻数据');
    }
}

// 更新新闻显示
function updateNewsDisplay(news) {
    const newsContainer = document.querySelector('.news-list');
    if (newsContainer) {
        let newsHTML = '';
        news.forEach(function(item) {
            const publishTime = new Date(item.publish_time).toLocaleTimeString();
            newsHTML += '<div class="news-item">' +
                '<div class="news-time">' + publishTime + '</div>' +
                '<div class="news-content">' +
                    '<div class="news-title">' + item.title + '</div>' +
                    '<div class="news-summary">' + item.summary + '</div>' +
                '</div>' +
            '</div>';
        });
        newsContainer.innerHTML = newsHTML;
    }
}

// 加载用户信息
async function loadUserInfo() {
    try {
        // const response = await authFetch('http://localhost:5000/api/auth/status');
        const response = await authFetch(`${API_BASE_URL}/api/auth/status`);
        const result = await response.json();
        
        if (result.success && result.logged_in && result.user) {
            updateUserDisplay(result.user);
        } else {
            // 用户未登录，显示默认状态
            const userNameEl = document.querySelector('.user-name');
            if (userNameEl) {
                userNameEl.textContent = '未登录';
            }
        }
    } catch (error) {
        console.error('用户信息加载失败:', error);
        const userNameEl = document.querySelector('.user-name');
        if (userNameEl && userNameEl.textContent === '加载中...') {
            userNameEl.textContent = '用户';
        }
    }
}

// 更新用户显示
function updateUserDisplay(user) {
    const userNameEl = document.querySelector('.user-name');
    if (userNameEl) {
        userNameEl.textContent = user.username || '用户';
    }
}

// 显示模拟数据（当API完全失败时）
function showFallbackData() {
    console.log('API调用失败，显示模拟数据');
    
    // 这里可以调用之前的模拟数据显示逻辑
    loadMarketIndices(); // 这会触发fallback
    loadWatchlist();     // 这会触发fallback
    loadSectors();       // 这会触发fallback
    loadGainers();       // 这会触发fallback
    loadNews();          // 这会触发fallback
}

// 绑定事件
function bindEvents() {
    // 绑定搜索功能
    const searchBtn = document.querySelector('.search-btn');
    const searchModal = document.getElementById('searchModal');
    const closeSearch = document.querySelector('.close-search');
    
    if (searchBtn && searchModal) {
        searchBtn.addEventListener('click', function() {
            searchModal.classList.add('show');
            const searchInput = searchModal.querySelector('.search-input');
            if (searchInput) {
                searchInput.focus();
            }
        });
    }
    
    if (closeSearch && searchModal) {
        closeSearch.addEventListener('click', function() {
            searchModal.classList.remove('show');
        });
    }
    
    if (searchModal) {
        searchModal.addEventListener('click', function(e) {
            if (e.target === searchModal) {
                searchModal.classList.remove('show');
            }
        });
    }
    
    // ESC键关闭搜索
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && searchModal && searchModal.classList.contains('show')) {
            searchModal.classList.remove('show');
        }
    });
    
    // 点击指数卡片跳转
    document.querySelectorAll('.index-card').forEach(function(card) {
        card.addEventListener('click', function() {
            const code = card.dataset.indexCode;
            if (code) {
                window.location.href = 'markets.html?index=' + code;
            }
        });
    });
    
    // 点击股票项跳转
    document.addEventListener('click', function(e) {
        const stockItem = e.target.closest('.stock-item');
        if (stockItem) {
            const codeEl = stockItem.querySelector('.stock-code');
            if (codeEl) {
                const code = codeEl.textContent;
                window.location.href = 'stock.html?code=' + code;
            }
        }
    });
}

// 定时刷新数据
setInterval(function() {
    console.log('定时刷新数据...');
    loadRealData();
}, 300000); // 每300 秒刷新一次
// API配置
const API_BASE_URL = 'http://192.168.31.237:5000';
//const API_BASE_URL = 'http://192.168.31.117:5000';
//const API_BASE_URL = 'http://192.168.3.78:5000';

// 全局带token的fetch
function authFetch(url, options = {}) {
    const token = localStorage.getItem('access_token');
    options.headers = options.headers || {};
    if (token) {
        options.headers['Authorization'] = 'Bearer ' + token;
    }
    return fetch(url, options);
}
window.authFetch = authFetch;

// 通用功能模块
const CommonUtils = {
    // 用户认证模块
    auth: {
        // 检查登录状态
        async checkLogin() {
            try {
                const response = await authFetch(`${API_BASE_URL}/api/auth/status`);
                const result = await response.json();
                
                if (result.success && result.logged_in) {
                    return result.user;
                } else {
                    // 如果不在登录页面且未登录，跳转到登录页
                    if (!window.location.pathname.includes('login.html') && 
                        !window.location.pathname.includes('test-login.html')) {
                        // 延迟跳转，避免和登录页面的检查冲突
                        setTimeout(() => {
                            window.location.href = 'login.html';
                        }, 100);
                        return false;
                    }
                    return null;
                }
            } catch (error) {
                console.error('检查登录状态失败:', error);
                // 网络错误时不跳转，避免死循环
                return null;
            }
        },

        // 获取用户信息
        getUserInfo() {
            return JSON.parse(localStorage.getItem('userInfo') || '{}');
        },

        // 登出
        async logout() {
            // 确认对话框
            if (confirm('确定要退出登录吗？')) {
                try {
                    await fetch(`${API_BASE_URL}/api/auth/logout`, {
                        method: 'POST',
                        credentials: 'include'
                    });
                } catch (error) {
                    console.error('登出请求失败:', error);
                }
                
                // 清除所有本地存储
                localStorage.removeItem('userInfo');
                localStorage.removeItem('rememberedUsername');
                localStorage.clear(); // 确保清除所有缓存
                
                CommonUtils.showToast('已安全退出', 'success');
                
                // 强制跳转到登录页面
                setTimeout(() => {
                    // 使用replace而不是href，防止用户通过后退按钮返回
                    window.location.replace('login.html');
                }, 1000);
            }
        },

        // 更新用户显示
        updateUserDisplay(user) {
            if (!user) return;

            // 更新导航栏用户信息
            const userMenu = document.querySelector('.user-menu');
            if (userMenu) {
                userMenu.innerHTML = `
                    <div class="user-info">
                        <span class="user-avatar">👤</span>
                        <span class="user-name">${user.username}</span>
                        <div class="user-dropdown">
                            <a href="profile.html">个人中心</a>
                            <a href="#" onclick="CommonUtils.auth.logout()">退出登录</a>
                        </div>
                    </div>
                `;
            }

            // 如果页面有用户名显示区域，更新它
            const userNameElements = document.querySelectorAll('.current-user-name');
            userNameElements.forEach(el => {
                el.textContent = user.username;
            });
        },

        // 初始化认证
        async init() {
            // 检查登录状态
            const user = await this.checkLogin();
            
            // 更新用户显示
            if (user) {
                this.updateUserDisplay(user);
            }
            
            // 绑定登出事件
            setTimeout(() => {
                document.querySelectorAll('.logout-btn').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        e.preventDefault();
                        CommonUtils.auth.logout();
                    });
                });
            }, 0);
        }
    },

    // 搜索功能
    search: {
        modal: null,
        input: null,
        results: null,
        
        init() {
            this.modal = document.getElementById('searchModal');
            this.input = document.querySelector('.search-input');
            this.results = document.querySelector('.search-results');
            
            // 如果页面没有搜索功能，跳过
            if (!this.modal || !this.input || !this.results) {
                return;
            }
            
            // 绑定事件
            const searchBtn = document.querySelector('.search-btn');
            if (searchBtn) {
                searchBtn.addEventListener('click', () => {
                    this.show();
                });
            }
            
            const closeBtn = document.querySelector('.close-search');
            if (closeBtn) {
                closeBtn.addEventListener('click', () => {
                    this.hide();
                });
            }
            
            // 点击背景关闭
            this.modal.addEventListener('click', (e) => {
                if (e.target === this.modal) {
                    this.hide();
                }
            });
            
            // 搜索输入
            this.input.addEventListener('input', (e) => {
                this.handleSearch(e.target.value);
            });
            
            // ESC键关闭
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && this.modal.classList.contains('show')) {
                    this.hide();
                }
            });
        },
        
        show() {
            if (this.modal) {
                this.modal.classList.add('show');
                this.input.focus();
            }
        },
        
        hide() {
            if (this.modal) {
                this.modal.classList.remove('show');
                this.input.value = '';
                this.results.innerHTML = '';
            }
        },
        
        handleSearch(query) {
            if (!query.trim()) {
                this.results.innerHTML = '';
                return;
            }
            
            // 模拟搜索结果
            const mockResults = [
                { code: '000001', name: '平安银行' },
                { code: '000002', name: '万科A' },
                { code: '600036', name: '招商银行' },
                { code: '600519', name: '贵州茅台' },
                { code: '000858', name: '五粮液' },
                { code: '002415', name: '海康威视' },
            ];
            
            const filtered = mockResults.filter(stock => 
                stock.code.includes(query) || 
                stock.name.includes(query)
            );
            
            this.renderResults(filtered);
        },
        
        renderResults(results) {
            if (results.length === 0) {
                this.results.innerHTML = '<div style="padding: 1rem; text-align: center; color: #6b7280;">未找到相关股票</div>';
                return;
            }
            
            this.results.innerHTML = results.map(stock => `
                <div class="search-item" onclick="CommonUtils.search.selectStock('${stock.code}')">
                    <span class="code">${stock.code}</span>
                    <span class="name">${stock.name}</span>
                </div>
            `).join('');
        },
        
        selectStock(code) {
            // 跳转到个股详情页
            window.location.href = `stock.html?code=${code}`;
        }
    },
    
    // 数字格式化
    formatNumber(num) {
        if (Math.abs(num) >= 1e8) {
            return (num / 1e8).toFixed(2) + '亿';
        } else if (Math.abs(num) >= 1e4) {
            return (num / 1e4).toFixed(2) + '万';
        }
        return num.toString();
    },
    
    // 价格格式化
    formatPrice(price) {
        return parseFloat(price).toFixed(2);
    },
    
    // 涨跌幅格式化
    formatChange(change, percent) {
        const changeStr = change >= 0 ? `+${change.toFixed(2)}` : change.toFixed(2);
        const percentStr = percent >= 0 ? `+${percent.toFixed(2)}%` : `${percent.toFixed(2)}%`;
        return `${changeStr} (${percentStr})`;
    },
    
    // 获取涨跌样式类
    getChangeClass(value) {
        if (value > 0) return 'positive';
        if (value < 0) return 'negative';
        return '';
    },
    
    // 模拟数据更新
    updateData() {
        // 模拟实时数据更新
        const elements = document.querySelectorAll('[data-update]');
        elements.forEach(el => {
            const type = el.dataset.update;
            if (type === 'price') {
                this.updatePrice(el);
            } else if (type === 'index') {
                this.updateIndex(el);
            }
        });
    },
    
    updatePrice(element) {
        const currentPrice = parseFloat(element.textContent);
        const change = (Math.random() - 0.5) * 0.1;
        const newPrice = Math.max(0.01, currentPrice + change);
        element.textContent = this.formatPrice(newPrice);
    },
    
    updateIndex(element) {
        const currentValue = parseFloat(element.textContent.replace(',', ''));
        const change = (Math.random() - 0.5) * 10;
        const newValue = Math.max(1, currentValue + change);
        element.textContent = newValue.toLocaleString('zh-CN', { minimumFractionDigits: 2 });
    },
    
    // 显示加载状态
    showLoading(element) {
        element.innerHTML = '<span class="loading"></span>';
    },
    
    // 隐藏加载状态
    hideLoading(element, content) {
        element.innerHTML = content;
    },
    
    // Toast提示
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.style.cssText = `
            position: fixed;
            top: 80px;
            right: 20px;
            background: ${type === 'success' ? '#16a34a' : type === 'error' ? '#dc2626' : '#2563eb'};
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 6px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 9999;
            animation: slideIn 0.3s ease;
        `;
        toast.textContent = message;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                document.body.removeChild(toast);
            }, 300);
        }, 3000);
    },
    
    // 初始化
    init() {
        // 初始化认证
        this.auth.init();
        
        // 初始化搜索
        this.search.init();
        
        // 定期更新数据
        // setInterval(() => {
        //     this.updateData();
        // }, 5000);
        
        // 添加动画样式
        if (!document.querySelector('#common-animations')) {
            const style = document.createElement('style');
            style.id = 'common-animations';
            style.textContent = `
                @keyframes slideIn {
                    from { transform: translateX(100%); opacity: 0; }
                    to { transform: translateX(0); opacity: 1; }
                }
                @keyframes slideOut {
                    from { transform: translateX(0); opacity: 1; }
                    to { transform: translateX(100%); opacity: 0; }
                }
                
                /* 用户菜单样式 */
                .user-info {
                    position: relative;
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                    cursor: pointer;
                    padding: 0.5rem;
                    border-radius: 6px;
                    transition: background-color 0.3s ease;
                }
                
                .user-info:hover {
                    background: rgba(255, 255, 255, 0.1);
                }
                
                .user-avatar {
                    width: 32px;
                    height: 32px;
                    background: rgba(255, 255, 255, 0.2);
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 1.2rem;
                }
                
                .user-name {
                    color: white;
                    font-weight: 500;
                }
                
                .user-dropdown {
                    position: absolute;
                    top: 100%;
                    right: 0;
                    background: white;
                    border-radius: 8px;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                    min-width: 150px;
                    opacity: 0;
                    visibility: hidden;
                    transform: translateY(-10px);
                    transition: all 0.3s ease;
                    z-index: 1000;
                }
                
                .user-info:hover .user-dropdown {
                    opacity: 1;
                    visibility: visible;
                    transform: translateY(0);
                }
                
                .user-dropdown a {
                    display: block;
                    padding: 0.75rem 1rem;
                    color: #374151;
                    text-decoration: none;
                    transition: background-color 0.3s ease;
                    border-bottom: 1px solid #f3f4f6;
                }
                
                .user-dropdown a:last-child {
                    border-bottom: none;
                }
                
                .user-dropdown a:hover {
                    background: #f8fafc;
                    color: #2563eb;
                }
                
                .user-dropdown a:first-child {
                    border-radius: 8px 8px 0 0;
                }
                
                .user-dropdown a:last-child {
                    border-radius: 0 0 8px 8px;
                }
            `;
            document.head.appendChild(style);
        }
    }
};

// DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    CommonUtils.init();
});

// 导出到全局
window.CommonUtils = CommonUtils; 
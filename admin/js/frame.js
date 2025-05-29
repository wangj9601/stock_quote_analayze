// 全局配置
const CONFIG = {
    API_BASE_URL: 'http://localhost:5000/api/admin',
    DEFAULT_PAGE: 'dashboard.html',
    TOKEN_KEY: 'admin_token',
    ADMIN_PORT: 8001
};

// 页面管理
const FrameManager = {
    init() {
        this.checkAuth();
        this.bindEvents();
        this.loadDefaultPage();
    },

    // 检查认证状态
    checkAuth() {
        const token = localStorage.getItem(CONFIG.TOKEN_KEY);
        if (token) {
            this.showAdminPage();
        } else {
            this.showLoginPage();
        }
    },

    // 绑定事件
    bindEvents() {
        // 登录表单提交
        document.getElementById('loginForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleLogin();
        });

        // 导航链接点击
        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                this.handleNavigation(link);
            });
        });
    },

    // 处理登录
    async handleLogin() {
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;

        try {
            const result = await apiRequest(`${CONFIG.API_BASE_URL}/login`, {
                method: 'POST',
                body: JSON.stringify({ username, password })
            });

            if (result.success) {
                localStorage.setItem(CONFIG.TOKEN_KEY, result.token);
                this.showAdminPage();
                this.loadDefaultPage();
            } else {
                showToast(result.message || '登录失败', 'error');
            }
        } catch (error) {
            console.error('登录出错:', error);
            showToast('网络错误，请稍后重试', 'error');
        }
    },

    // 处理导航
    handleNavigation(link) {
        const page = link.getAttribute('href');
        const pageName = link.dataset.page;

        // 更新导航状态
        document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
        link.classList.add('active');

        // 更新页面标题
        document.getElementById('pageTitle').textContent = link.querySelector('.nav-text').textContent;
        document.getElementById('currentPage').textContent = link.querySelector('.nav-text').textContent;

        // 加载页面内容
        this.loadPage(page);
    },

    // 加载页面
    async loadPage(page) {
        try {
            const response = await fetch(page);
            if (!response.ok) throw new Error('页面加载失败');
            
            const content = await response.text();
            const contentFrame = document.getElementById('contentFrame');
            
            // 创建临时容器来解析HTML
            const temp = document.createElement('div');
            temp.innerHTML = content;
            
            // 提取页面内容
            const pageContent = temp.querySelector('.page-content');
            if (pageContent) {
                contentFrame.innerHTML = pageContent.outerHTML;
                
                // 加载页面特定的脚本
                const scripts = temp.querySelectorAll('script');
                scripts.forEach(script => {
                    if (script.src) {
                        const newScript = document.createElement('script');
                        newScript.src = script.src;
                        document.body.appendChild(newScript);
                    } else {
                        eval(script.textContent);
                    }
                });
            }
        } catch (error) {
            console.error('加载页面出错:', error);
            showToast('页面加载失败', 'error');
        }
    },

    // 加载默认页面
    loadDefaultPage() {
        const defaultLink = document.querySelector(`.nav-link[href="${CONFIG.DEFAULT_PAGE}"]`);
        if (defaultLink) {
            this.handleNavigation(defaultLink);
        }
    },

    // 显示管理页面
    showAdminPage() {
        document.getElementById('loginPage').style.display = 'none';
        document.getElementById('adminPage').style.display = 'flex';
    },

    // 显示登录页面
    showLoginPage() {
        document.getElementById('adminPage').style.display = 'none';
        document.getElementById('loginPage').style.display = 'flex';
    }
};

// 退出登录
function logout() {
    localStorage.removeItem(CONFIG.TOKEN_KEY);
    FrameManager.showLoginPage();
}

// 显示提示消息
function showToast(message, type = 'info') {
    // 创建toast元素
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    // 添加到页面
    document.body.appendChild(toast);

    // 显示动画
    setTimeout(() => toast.classList.add('show'), 10);

    // 自动移除
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    FrameManager.init();
}); 
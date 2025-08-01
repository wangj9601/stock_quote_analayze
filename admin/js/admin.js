// 管理后台主控制器
const AdminPanel = {
    currentUser: null,
    apiBaseUrl: 'http://localhost:5000/api',

    // 初始化
    init() {
        this.bindEvents();
        this.checkLoginStatus();
        this.initCharts();
    },

    // 绑定事件
    bindEvents() {
        // 登录表单提交
        const loginForm = document.getElementById('loginForm');
        if (loginForm) {
            loginForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleLogin();
            });
        }

        // 导航链接点击
        const navLinks = document.querySelectorAll('.nav-link');
        navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const page = link.dataset.page;
                this.switchPage(page);
                this.updateActiveNav(link);
            });
        });

        // 绑定按钮事件
        this.bindButtonEvents();
    },

    // 绑定按钮事件
    bindButtonEvents() {
        document.addEventListener('click', (e) => {
            // 添加用户按钮
            if (e.target.matches('.btn-primary') && e.target.textContent === '添加用户') {
                this.showAddUserModal();
            }
            
            // 编辑用户按钮
            if (e.target.matches('.btn-secondary') && e.target.textContent === '编辑') {
                const userId = e.target.dataset.userId;
                this.showEditUserModal(userId);
            }
            
            // 禁用/启用用户按钮
            if (e.target.matches('.btn-danger') || e.target.matches('.btn-success')) {
                const userId = e.target.dataset.userId;
                const currentStatus = e.target.dataset.status;
                this.toggleUserStatus(userId, currentStatus);
            }
            
            // 删除用户按钮
            if (e.target.matches('.btn-warning') && e.target.textContent === '删除') {
                const userId = e.target.dataset.userId;
                this.deleteUser(userId);
            }
        });
    },

    // 检查登录状态
    checkLoginStatus() {
        // 首页始终显示登录页面，不自动登录
        this.showLoginPage();
    },

    // 处理登录
    async handleLogin() {
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;

        try {
            // 创建表单数据，符合OAuth2PasswordRequestForm的要求
            const formData = new FormData();
            formData.append('username', username);
            formData.append('password', password);

            const response = await fetch(`${this.apiBaseUrl}/admin/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: new URLSearchParams(formData)
            });

            const result = await response.json();

            if (response.ok) {
                this.currentUser = result.admin;
                localStorage.setItem('adminLoggedIn', 'true');
                localStorage.setItem('adminData', JSON.stringify(result.admin));
                localStorage.setItem('admin_token', result.access_token);
                
                this.showAdminPanel();
                this.showToast('登录成功！', 'success');
                
                // 加载仪表板数据
                this.loadDashboardData();
            } else {
                this.showToast(result.detail || '登录失败', 'error');
            }
        } catch (error) {
            console.error('登录错误:', error);
            this.showToast('网络连接错误', 'error');
        }
    },

    // 退出登录
    logout() {
        localStorage.removeItem('adminLoggedIn');
        localStorage.removeItem('adminData');
        localStorage.removeItem('admin_token');
        this.currentUser = null;
        this.showLoginPage();
        this.showToast('已安全退出', 'info');
    },

    // 显示登录页面
    showLoginPage() {
        document.getElementById('loginPage').style.display = 'flex';
        document.getElementById('adminPage').style.display = 'none';
    },

    // 显示管理面板
    showAdminPanel() {
        document.getElementById('loginPage').style.display = 'none';
        document.getElementById('adminPage').style.display = 'flex';
        
        // 更新用户信息显示
        if (this.currentUser) {
            document.querySelector('.user-name').textContent = this.currentUser.username;
            document.querySelector('.user-avatar').textContent = this.currentUser.username.charAt(0).toUpperCase();
        }
    },

    // 切换页面
    switchPage(pageId) {
        // 隐藏所有页面内容
        const allPages = document.querySelectorAll('.page-content');
        allPages.forEach(page => {
            page.classList.remove('active');
        });

        // 显示目标页面
        const targetPage = document.getElementById(pageId);
        if (targetPage) {
            targetPage.classList.add('active');
        }

        // 更新页面标题
        this.updatePageTitle(pageId);

        // 根据页面类型加载相应数据
        this.loadPageData(pageId);
    },

    // 更新活动导航
    updateActiveNav(activeLink) {
        const allLinks = document.querySelectorAll('.nav-link');
        allLinks.forEach(link => {
            link.classList.remove('active');
        });
        activeLink.classList.add('active');
    },

    // 更新页面标题
    updatePageTitle(pageId) {
        const titles = {
            'dashboard': '仪表板',
            'users': '用户管理',
            'datasource': '数据源配置',
            'datacollect': '数据采集',
            'monitoring': '系统监控',
            'models': '预测模型',
            'logs': '系统日志',
            'content': '内容管理',
            'announcements': '公告发布'
        };

        const title = titles[pageId] || '管理后台';
        document.getElementById('pageTitle').textContent = title;
        document.getElementById('currentPage').textContent = title;
    },

    // 加载页面数据
    loadPageData(pageId) {
        switch (pageId) {
            case 'dashboard':
                this.loadDashboardData();
                break;
            case 'users':
                this.loadUsersData();
                break;
            default:
                break;
        }
    },

    // 加载仪表板数据
    async loadDashboardData() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/admin/stats`);
            const result = await response.json();
            
            if (result.success) {
                this.updateDashboardStats(result.data);
            }
        } catch (error) {
            console.error('加载仪表板数据失败:', error);
        }
    },

    // 更新仪表板统计数据
    updateDashboardStats(stats) {
        const statCards = document.querySelectorAll('.stat-card');
        
        if (statCards.length >= 4) {
            // 更新用户数
            statCards[0].querySelector('h3').textContent = stats.total_users || 0;
            
            // 更新活跃用户数
            statCards[1].querySelector('h3').textContent = stats.active_users || 0;
            
            // 更新今日登录数
            statCards[2].querySelector('h3').textContent = stats.today_logins || 0;
            
            // 更新自选股数量
            statCards[3].querySelector('h3').textContent = stats.total_watchlist || 0;
        }
    },

    // 加载用户数据
    async loadUsersData() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/admin/users`);
            const result = await response.json();
            
            if (result.success) {
                this.renderUsersTable(result.data);
            } else {
                this.showToast('加载用户数据失败', 'error');
            }
        } catch (error) {
            console.error('加载用户数据失败:', error);
            this.showToast('网络连接错误', 'error');
        }
    },

    // 渲染用户表格
    renderUsersTable(users) {
        const tbody = document.querySelector('#users .table tbody');
        if (!tbody) return;

        tbody.innerHTML = '';

        users.forEach(user => {
            const row = document.createElement('tr');
            const statusBadge = user.status === 'active' ? 
                '<span class="badge badge-success">已激活</span>' : 
                '<span class="badge badge-danger">已禁用</span>';
            
            const statusButton = user.status === 'active' ? 
                `<button class="btn btn-sm btn-danger" data-user-id="${user.id}" data-status="${user.status}">禁用</button>` :
                `<button class="btn btn-sm btn-success" data-user-id="${user.id}" data-status="${user.status}">启用</button>`;

            row.innerHTML = `
                <td>${user.id}</td>
                <td>${user.username}</td>
                <td>${user.email}</td>
                <td>${user.created_at ? new Date(user.created_at).toLocaleDateString() : '-'}</td>
                <td>${statusBadge}</td>
                <td>
                    <button class="btn btn-sm btn-secondary" data-user-id="${user.id}">编辑</button>
                    ${statusButton}
                    <button class="btn btn-sm btn-warning" data-user-id="${user.id}">删除</button>
                </td>
            `;
            tbody.appendChild(row);
        });
    },

    // 显示添加用户模态框
    showAddUserModal() {
        const modal = this.createUserModal('添加用户', {});
        document.body.appendChild(modal);
        modal.style.display = 'flex';
    },

    // 显示编辑用户模态框
    async showEditUserModal(userId) {
        try {
            // 从当前表格中获取用户信息
            const row = document.querySelector(`button[data-user-id="${userId}"]`).closest('tr');
            const cells = row.querySelectorAll('td');
            
            const userData = {
                id: userId,
                username: cells[1].textContent,
                email: cells[2].textContent,
                status: cells[4].querySelector('.badge').textContent === '已激活' ? 'active' : 'disabled'
            };

            const modal = this.createUserModal('编辑用户', userData);
            document.body.appendChild(modal);
            modal.style.display = 'flex';
        } catch (error) {
            console.error('获取用户信息失败:', error);
            this.showToast('获取用户信息失败', 'error');
        }
    },

    // 创建用户模态框
    createUserModal(title, userData = {}) {
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        
        const isEdit = userData.id;
        
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>${title}</h3>
                    <button class="modal-close">&times;</button>
                </div>
                <div class="modal-body">
                    <form id="userForm">
                        <div class="form-group">
                            <label for="modalUsername">用户名</label>
                            <input type="text" id="modalUsername" value="${userData.username || ''}" required>
                        </div>
                        <div class="form-group">
                            <label for="modalEmail">邮箱</label>
                            <input type="email" id="modalEmail" value="${userData.email || ''}" required>
                        </div>
                        ${!isEdit ? `
                        <div class="form-group">
                            <label for="modalPassword">密码</label>
                            <input type="password" id="modalPassword" required>
                        </div>
                        ` : ''}
                        <div class="form-group">
                            <label for="modalStatus">状态</label>
                            <select id="modalStatus">
                                <option value="active" ${userData.status === 'active' ? 'selected' : ''}>已激活</option>
                                <option value="disabled" ${userData.status === 'disabled' ? 'selected' : ''}>已禁用</option>
                            </select>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary modal-cancel">取消</button>
                    <button class="btn btn-primary modal-save">${isEdit ? '更新' : '创建'}</button>
                </div>
            </div>
        `;

        // 绑定事件
        modal.querySelector('.modal-close').onclick = () => this.closeModal(modal);
        modal.querySelector('.modal-cancel').onclick = () => this.closeModal(modal);
        modal.querySelector('.modal-save').onclick = () => {
            if (isEdit) {
                AdminPanel.updateUser(userData.id, modal);
            } else {
                AdminPanel.createUser(modal);
            }
        };

        // 点击背景关闭
        modal.onclick = (e) => {
            if (e.target === modal) {
                this.closeModal(modal);
            }
        };

        return modal;
    },

    // 关闭模态框
    closeModal(modal) {
        modal.remove();
    },

    // 创建用户    async createUser(modal) {        const username = modal.querySelector('#modalUsername').value.trim();        const email = modal.querySelector('#modalEmail').value.trim();        const password = modal.querySelector('#modalPassword').value.trim();        const status = modal.querySelector('#modalStatus').value;        // 前端验证        if (!username) {            this.showToast('请输入用户名', 'error');            modal.querySelector('#modalUsername').focus();            return;        }        if (!email) {            this.showToast('请输入邮箱地址', 'error');            modal.querySelector('#modalEmail').focus();            return;        }        // 简单的邮箱格式验证        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;        if (!emailRegex.test(email)) {            this.showToast('请输入正确的邮箱格式', 'error');            modal.querySelector('#modalEmail').focus();            return;        }        if (!password) {            this.showToast('请输入密码', 'error');            modal.querySelector('#modalPassword').focus();            return;        }        if (password.length < 6) {            this.showToast('密码长度至少6位', 'error');            modal.querySelector('#modalPassword').focus();            return;        }        const formData = {            username: username,            email: email,            password: password,            status: status        };        try {            const response = await fetch(`${this.apiBaseUrl}/admin/users`, {                method: 'POST',                headers: {                    'Content-Type': 'application/json',                },                body: JSON.stringify(formData)            });            const result = await response.json();            if (result.success) {                this.showToast('用户创建成功', 'success');                this.closeModal(modal);                this.loadUsersData(); // 重新加载用户列表            } else {                this.showToast(result.message || '创建失败', 'error');            }        } catch (error) {            console.error('创建用户失败:', error);            this.showToast('网络连接错误', 'error');        }    },

    // 更新用户
    async updateUser(userId, modal) {
        const formData = {
            username: modal.querySelector('#modalUsername').value,
            email: modal.querySelector('#modalEmail').value,
            status: modal.querySelector('#modalStatus').value
        };

        try {
            const response = await fetch(`${this.apiBaseUrl}/admin/users/${userId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            });

            const result = await response.json();

            if (result.success) {
                this.showToast('用户更新成功', 'success');
                this.closeModal(modal);
                this.loadUsersData(); // 重新加载用户列表
            } else {
                this.showToast(result.message || '更新失败', 'error');
            }
        } catch (error) {
            console.error('更新用户失败:', error);
            this.showToast('网络连接错误', 'error');
        }
    },

    // 切换用户状态
    async toggleUserStatus(userId, currentStatus) {
        const newStatus = currentStatus === 'active' ? 'disabled' : 'active';
        const action = newStatus === 'active' ? '启用' : '禁用';

        if (!confirm(`确定要${action}此用户吗？`)) {
            return;
        }

        try {
            const response = await fetch(`${this.apiBaseUrl}/admin/users/${userId}/status`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ status: newStatus })
            });

            const result = await response.json();

            if (result.success) {
                this.showToast(`用户${action}成功`, 'success');
                this.loadUsersData(); // 重新加载用户列表
            } else {
                this.showToast(result.message || `${action}失败`, 'error');
            }
        } catch (error) {
            console.error(`${action}用户失败:`, error);
            this.showToast('网络连接错误', 'error');
        }
    },

    // 删除用户
    async deleteUser(userId) {
        if (!confirm('确定要删除此用户吗？此操作不可撤销！')) {
            return;
        }

        try {
            const response = await fetch(`${this.apiBaseUrl}/admin/users/${userId}`, {
                method: 'DELETE'
            });

            const result = await response.json();

            if (result.success) {
                this.showToast('用户删除成功', 'success');
                this.loadUsersData(); // 重新加载用户列表
            } else {
                this.showToast(result.message || '删除失败', 'error');
            }
        } catch (error) {
            console.error('删除用户失败:', error);
            this.showToast('网络连接错误', 'error');
        }
    },

    // 初始化图表
    initCharts() {
        setTimeout(() => {
            this.drawUserActivityChart();
            this.drawDataCollectionChart();
        }, 100);
    },

    // 绘制用户活跃度图表
    drawUserActivityChart() {
        const canvas = document.getElementById('userActivityChart');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;

        // 清空画布
        ctx.clearRect(0, 0, width, height);

        // 模拟数据
        const data = [65, 59, 80, 81, 56, 55, 40];
        const labels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];

        // 绘制坐标轴
        ctx.strokeStyle = '#e0e0e0';
        ctx.beginPath();
        ctx.moveTo(40, 20);
        ctx.lineTo(40, height - 30);
        ctx.lineTo(width - 20, height - 30);
        ctx.stroke();

        // 绘制数据线
        ctx.strokeStyle = '#4285f4';
        ctx.lineWidth = 2;
        ctx.beginPath();

        const stepX = (width - 60) / (data.length - 1);
        const maxY = Math.max(...data);

        data.forEach((value, index) => {
            const x = 40 + index * stepX;
            const y = height - 30 - (value / maxY) * (height - 50);

            if (index === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }

            // 绘制数据点
            ctx.fillStyle = '#4285f4';
            ctx.beginPath();
            ctx.arc(x, y, 3, 0, 2 * Math.PI);
            ctx.fill();
        });

        ctx.stroke();
    },

    // 绘制数据采集状态图表
    drawDataCollectionChart() {
        const canvas = document.getElementById('dataCollectionChart');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;

        // 清空画布
        ctx.clearRect(0, 0, width, height);

        // 饼图数据
        const data = [
            { label: '成功', value: 85, color: '#4caf50' },
            { label: '失败', value: 10, color: '#f44336' },
            { label: '处理中', value: 5, color: '#ff9800' }
        ];

        const centerX = width / 2;
        const centerY = height / 2;
        const radius = Math.min(centerX, centerY) - 30;

        let startAngle = 0;

        data.forEach(item => {
            const sliceAngle = (item.value / 100) * 2 * Math.PI;

            // 绘制扇形
            ctx.fillStyle = item.color;
            ctx.beginPath();
            ctx.moveTo(centerX, centerY);
            ctx.arc(centerX, centerY, radius, startAngle, startAngle + sliceAngle);
            ctx.closePath();
            ctx.fill();

            // 绘制标签
            const labelAngle = startAngle + sliceAngle / 2;
            const labelX = centerX + Math.cos(labelAngle) * (radius + 20);
            const labelY = centerY + Math.sin(labelAngle) * (radius + 20);

            ctx.fillStyle = '#333';
            ctx.font = '12px Arial';
            ctx.textAlign = 'center';
            ctx.fillText(`${item.label} ${item.value}%`, labelX, labelY);

            startAngle += sliceAngle;
        });
    },

    // 显示提示消息
    showToast(message, type = 'info') {
        // 移除现有的提示
        const existingToast = document.querySelector('.toast');
        if (existingToast) {
            existingToast.remove();
        }

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const colors = {
            success: '#4caf50',
            error: '#f44336',
            warning: '#ff9800',
            info: '#2196f3'
        };

        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            background: ${colors[type] || colors.info};
            color: white;
            border-radius: 4px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            z-index: 10000;
            animation: slideInRight 0.3s ease;
        `;

        toast.textContent = message;
        document.body.appendChild(toast);

        // 3秒后自动移除
        setTimeout(() => {
            if (toast.parentNode) {
                toast.remove();
            }
        }, 3000);
    }
};

// 全局函数（用于HTML onclick）
function logout() {
    AdminPanel.logout();
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    AdminPanel.init();
});

// 添加CSS动画
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    .modal-overlay {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 9999;
    }

    .modal-content {
        background: white;
        border-radius: 8px;
        width: 500px;
        max-width: 90%;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    }

    .modal-header {
        padding: 20px;
        border-bottom: 1px solid #eee;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .modal-header h3 {
        margin: 0;
        color: #333;
    }

    .modal-close {
        background: none;
        border: none;
        font-size: 24px;
        cursor: pointer;
        color: #999;
    }

    .modal-close:hover {
        color: #333;
    }

    .modal-body {
        padding: 20px;
    }

    .form-group {
        margin-bottom: 15px;
    }

    .form-group label {
        display: block;
        margin-bottom: 5px;
        font-weight: 500;
        color: #333;
    }

    .form-group input,
    .form-group select {
        width: 100%;
        padding: 8px 12px;
        border: 1px solid #ddd;
        border-radius: 4px;
        font-size: 14px;
    }

    .form-group input:focus,
    .form-group select:focus {
        outline: none;
        border-color: #4285f4;
        box-shadow: 0 0 0 2px rgba(66, 133, 244, 0.2);
    }

    .modal-footer {
        padding: 20px;
        border-top: 1px solid #eee;
        display: flex;
        justify-content: flex-end;
        gap: 10px;
    }
`;
document.head.appendChild(style); 
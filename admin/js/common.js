// 全局配置
const CONFIG = {
    API_BASE_URL: '/api/admin',
    DEFAULT_PAGE: 'dashboard.html',
    TOKEN_KEY: 'admin_token',
    PAGE_SIZE: 20
};

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

// 格式化数字
function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

// 格式化日期
function formatDate(date, format = 'YYYY-MM-DD HH:mm:ss') {
    const d = new Date(date);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    const seconds = String(d.getSeconds()).padStart(2, '0');

    return format
        .replace('YYYY', year)
        .replace('MM', month)
        .replace('DD', day)
        .replace('HH', hours)
        .replace('mm', minutes)
        .replace('ss', seconds);
}

// 获取API请求头
function getApiHeaders() {
    const token = localStorage.getItem(CONFIG.TOKEN_KEY);
    return {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : ''
    };
}

// 处理API响应
async function handleApiResponse(response) {
    const result = await response.json();
    if (!response.ok) {
        throw new Error(result.message || '请求失败');
    }
    return result;
}

// 通用API请求函数
async function apiRequest(url, options = {}) {
    try {
        const response = await fetch(url, {
            ...options,
            headers: {
                ...getApiHeaders(),
                ...options.headers
            }
        });
        return await handleApiResponse(response);
    } catch (error) {
        console.error('API请求出错:', error);
        showToast(error.message || '网络错误，请稍后重试', 'error');
        throw error;
    }
}

// 导出工具函数和配置
window.CONFIG = CONFIG;
window.showToast = showToast;
window.formatNumber = formatNumber;
window.formatDate = formatDate;
window.apiRequest = apiRequest; 
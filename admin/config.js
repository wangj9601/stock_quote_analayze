// 管理后台独立配置文件
// 完全独立于frontend目录的配置

const ADMIN_CONFIG = {
    // API配置
    API: {
        BASE_URL: 'http://localhost:5000/api/admin',
        TIMEOUT: 30000,
        RETRY_TIMES: 3
    },
    
    // 认证配置
    AUTH: {
        TOKEN_KEY: 'admin_token',
        REFRESH_TOKEN_KEY: 'admin_refresh_token',
        LOGIN_URL: '/admin/',
        LOGOUT_URL: '/api/admin/auth/logout'
    },
    
    // 分页配置
    PAGINATION: {
        DEFAULT_PAGE_SIZE: 20,
        PAGE_SIZE_OPTIONS: [10, 20, 50, 100]
    },
    
    // 数据刷新配置
    REFRESH: {
        AUTO_REFRESH_INTERVAL: 30000, // 30秒
        MANUAL_REFRESH_ENABLED: true
    },
    
    // 文件上传配置
    UPLOAD: {
        MAX_FILE_SIZE: 10 * 1024 * 1024, // 10MB
        ALLOWED_TYPES: ['jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx']
    },
    
    // 主题配置
    THEME: {
        PRIMARY_COLOR: '#1890ff',
        SUCCESS_COLOR: '#52c41a',
        WARNING_COLOR: '#faad14',
        ERROR_COLOR: '#f5222d',
        INFO_COLOR: '#1890ff'
    },
    
    // 功能开关
    FEATURES: {
        USER_MANAGEMENT: true,
        DATA_MANAGEMENT: true,
        SYSTEM_MONITORING: true,
        DATA_EXPORT: true,
        BULK_OPERATIONS: true
    },
    
    // 默认用户信息
    DEFAULT_USER: {
        USERNAME: 'admin',
        PASSWORD: '123456',
        ROLE: 'admin'
    },
    
    // 错误消息
    MESSAGES: {
        LOGIN_SUCCESS: '登录成功',
        LOGIN_FAILED: '登录失败，请检查用户名和密码',
        LOGOUT_SUCCESS: '已退出登录',
        SAVE_SUCCESS: '保存成功',
        DELETE_SUCCESS: '删除成功',
        OPERATION_FAILED: '操作失败',
        NETWORK_ERROR: '网络错误，请稍后重试',
        UNAUTHORIZED: '未授权访问',
        FORBIDDEN: '访问被拒绝',
        NOT_FOUND: '资源不存在',
        SERVER_ERROR: '服务器内部错误'
    },
    
    // 日期格式
    DATE_FORMATS: {
        DISPLAY: 'YYYY-MM-DD HH:mm:ss',
        DATE_ONLY: 'YYYY-MM-DD',
        TIME_ONLY: 'HH:mm:ss'
    },
    
    // 数据格式化
    FORMAT: {
        CURRENCY: {
            SYMBOL: '¥',
            DECIMALS: 2
        },
        PERCENTAGE: {
            DECIMALS: 2,
            SUFFIX: '%'
        },
        NUMBER: {
            THOUSANDS_SEPARATOR: ',',
            DECIMALS: 2
        }
    }
};

// 导出配置
window.ADMIN_CONFIG = ADMIN_CONFIG;

// 工具函数
const AdminUtils = {
    // 获取API完整URL
    getApiUrl: (endpoint) => {
        return `${ADMIN_CONFIG.API.BASE_URL}${endpoint}`;
    },
    
    // 获取认证头
    getAuthHeaders: () => {
        const token = localStorage.getItem(ADMIN_CONFIG.AUTH.TOKEN_KEY);
        return {
            'Content-Type': 'application/json',
            'Authorization': token ? `Bearer ${token}` : ''
        };
    },
    
    // 格式化货币
    formatCurrency: (amount) => {
        const { SYMBOL, DECIMALS } = ADMIN_CONFIG.FORMAT.CURRENCY;
        return `${SYMBOL}${parseFloat(amount).toFixed(DECIMALS)}`;
    },
    
    // 格式化百分比
    formatPercentage: (value) => {
        const { DECIMALS, SUFFIX } = ADMIN_CONFIG.FORMAT.PERCENTAGE;
        return `${parseFloat(value).toFixed(DECIMALS)}${SUFFIX}`;
    },
    
    // 格式化数字
    formatNumber: (num) => {
        const { THOUSANDS_SEPARATOR, DECIMALS } = ADMIN_CONFIG.FORMAT.NUMBER;
        return parseFloat(num).toLocaleString('zh-CN', {
            minimumFractionDigits: DECIMALS,
            maximumFractionDigits: DECIMALS
        });
    },
    
    // 检查用户权限
    hasPermission: (permission) => {
        const userRole = localStorage.getItem('admin_user_role');
        return userRole === 'admin' || userRole === permission;
    },
    
    // 获取用户信息
    getUserInfo: () => {
        return {
            username: localStorage.getItem('admin_username'),
            role: localStorage.getItem('admin_user_role'),
            token: localStorage.getItem(ADMIN_CONFIG.AUTH.TOKEN_KEY)
        };
    },
    
    // 清除用户信息
    clearUserInfo: () => {
        localStorage.removeItem(ADMIN_CONFIG.AUTH.TOKEN_KEY);
        localStorage.removeItem(ADMIN_CONFIG.AUTH.REFRESH_TOKEN_KEY);
        localStorage.removeItem('admin_username');
        localStorage.removeItem('admin_user_role');
    }
};

// 导出工具函数
window.AdminUtils = AdminUtils; 
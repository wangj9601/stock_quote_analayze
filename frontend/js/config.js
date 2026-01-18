// 环境配置
const Config = {
    // 检测当前环境
    getEnvironment() {
        const hostname = window.location.hostname;
        const protocol = window.location.protocol;
        
        // 生产环境检测
        if (hostname === 'www.icemaplecity.com' || hostname === 'icemaplecity.com' || hostname === 'erp.icemaplecity.com') {
            return 'production';
        }
        
        // 开发环境检测
        if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname.startsWith('192.168.')) {
            return 'development';
        }
        
        // 默认返回开发环境
        return 'development';
    },
    
    // 获取API基础URL
    getApiBaseUrl() {
        const environment = this.getEnvironment();
        
        switch (environment) {
            case 'production':
                // 生产环境使用相对路径，让浏览器自动处理协议和域名
                return '';
            case 'development':
            default:
                // 开发环境：如果访问地址是IP地址，使用相同的IP；否则使用localhost
                const hostname = window.location.hostname;
                const protocol = window.location.protocol;
                if (hostname.startsWith('192.168.') || hostname.startsWith('10.') || hostname.match(/^172\.(1[6-9]|2[0-9]|3[01])\./)) {
                    // 如果是内网IP地址，使用相同的IP地址
                    return `${protocol}//${hostname}:5000`;
                } else {
                    // 否则使用localhost
                    return 'http://localhost:5000';
                }
        }
    },
    
    // 获取完整的API URL
    getApiUrl(path) {
        const baseUrl = this.getApiBaseUrl();
        const apiPath = path.startsWith('/') ? path : `/${path}`;
        
        if (baseUrl) {
            return `${baseUrl}${apiPath}`;
        } else {
            // 生产环境使用相对路径
            return apiPath;
        }
    },
    
    // 获取当前环境信息
    getEnvironmentInfo() {
        return {
            environment: this.getEnvironment(),
            hostname: window.location.hostname,
            protocol: window.location.protocol,
            apiBaseUrl: this.getApiBaseUrl()
        };
    }
};

// 导出配置
window.Config = Config;

// API 地址策略：本地开发通常「静态页一个端口 + 后端 5000、无 Nginx」；生产经 Nginx 与页面同域，用相对路径 /api/...
// 强制覆盖：在加载本文件之后设置 window.API_BASE_URL = 'http://...'

function _isPrivateLanHostname(hostname) {
    if (!hostname) return false;
    if (hostname === 'localhost' || hostname === '127.0.0.1') return true;
    if (hostname.startsWith('192.168.')) return true;
    if (hostname.startsWith('10.')) return true;
    return /^172\.(1[6-9]|2[0-9]|3[01])\./.test(hostname);
}

/** 页面是否落在 80/443（或协议默认端口），多用于生产 Nginx */
function _isNginxLikeSitePort(port) {
    const p = String(port || '');
    return p === '' || p === '80' || p === '443';
}

const Config = {
    getEnvironment() {
        const hostname = window.location.hostname;

        if (hostname === 'www.icemaplecity.com' || hostname === 'icemaplecity.com' || hostname === 'erp.icemaplecity.com') {
            return 'production';
        }

        if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname.startsWith('192.168.')) {
            return 'development';
        }

        return 'development';
    },

    /**
     * API 根地址（不含 /api 路径）。
     * - 空字符串：与页面同源，由 Nginx 反代 /api（生产或内网 80/443）。
     * - http(s)://host:5000：本地无 Nginx、前端与后端不同端口时使用。
     */
    getApiBaseUrl() {
        if (typeof window !== 'undefined' && typeof window.API_BASE_URL === 'string' && window.API_BASE_URL.length) {
            return window.API_BASE_URL.replace(/\/+$/, '');
        }

        const hostname = window.location.hostname;
        const protocol = window.location.protocol;
        const port = window.location.port;

        // 已知公网生产域名：一律走 Nginx，与页面同域
        if (hostname === 'www.icemaplecity.com' || hostname === 'icemaplecity.com' || hostname === 'erp.icemaplecity.com') {
            return '';
        }

        // 前端与后端同端口（例如后端托管静态页）
        if (String(port) === '5000') {
            return '';
        }

        // 本机：无 Nginx 时常见为 localhost:8000 + 后端 :5000
        if (hostname === 'localhost' || hostname === '127.0.0.1') {
            if (!_isNginxLikeSitePort(port)) {
                return `${protocol}//${hostname}:5000`;
            }
            return '';
        }

        // 内网 IP：80/443（或默认端口）视为前面有 Nginx；其它端口视为本地静态服务直连后端
        if (_isPrivateLanHostname(hostname)) {
            if (_isNginxLikeSitePort(port)) {
                return '';
            }
            return `${protocol}//${hostname}:5000`;
        }

        // 其它公网域名：默认生产同域 + Nginx
        return '';
    },

    getApiUrl(path) {
        const baseUrl = this.getApiBaseUrl();
        const apiPath = path.startsWith('/') ? path : `/${path}`;

        if (baseUrl) {
            return `${baseUrl}${apiPath}`;
        }
        return apiPath;
    },

    getEnvironmentInfo() {
        return {
            environment: this.getEnvironment(),
            hostname: window.location.hostname,
            protocol: window.location.protocol,
            apiBaseUrl: this.getApiBaseUrl()
        };
    }
};

window.Config = Config;

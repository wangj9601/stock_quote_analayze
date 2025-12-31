
const API_BASE_URL = Config.getApiBaseUrl();

let globalData = [];

document.addEventListener('DOMContentLoaded', () => {
    // 获取URL参数
    const urlParams = new URLSearchParams(window.location.search);
    const stockCode = urlParams.get('code');
    const startDate = urlParams.get('start_date');
    const endDate = urlParams.get('end_date');
    const market = urlParams.get('market') || 'CN'; // 默认为CN

    if (!stockCode || !startDate || !endDate) {
        showError('缺少必要参数：股票代码或日期范围');
        return;
    }

    // 更新页面标题信息
    document.getElementById('stockInfo').textContent = `${stockCode} (${startDate} ~ ${endDate})`;

    // 初始化Tabs
    initTabs();

    // 加载数据
    loadIndicatorHistory(stockCode, startDate, endDate, market);
});

function initTabs() {
    const tabs = document.querySelectorAll('.tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // 移除所有active
            tabs.forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');

            // 激活当前
            tab.classList.add('active');
            const targetId = tab.dataset.tab + 'Content';
            document.getElementById(targetId).style.display = 'block';

            // 渲染对应表格 (如果未渲染)
            renderTabContent(tab.dataset.tab);
        });
    });
}

async function loadIndicatorHistory(code, startDate, endDate, market) {
    try {
        const url = `${API_BASE_URL}/api/admin/indicators/history?code=${code}&start_date=${startDate}&end_date=${endDate}&market_type=${market}`;
        const response = await authFetch(url);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();

        if (result.success && result.data && result.data.length > 0) {
            globalData = result.data;
            document.getElementById('loading').style.display = 'none';
            document.getElementById('mainContent').style.display = 'block';

            // 默认渲染第一个Tab
            renderTabContent('ma');

        } else {
            showError('未找到相关数据');
        }

    } catch (error) {
        console.error('加载指标历史数据失败:', error);
        showError(`加载失败: ${error.message}`);
    }
}

function processValue(val, isInt = false) {
    if (val === null || val === undefined) return '-';
    if (typeof val === 'number') {
        return isInt ? val : val.toFixed(3);
    }
    return val;
}

function renderTabContent(type) {
    const container = document.getElementById(type + 'Content');
    // 如果已经有内容，不再重复渲染
    if (container.innerHTML.trim() !== '') return;

    let headers = [];
    let fields = [];
    let subKey = type; // data.ma, data.macd etc.

    switch (type) {
        case 'ma':
            headers = ['日期', 'MA5', 'MA10', 'MA20', 'MA30', 'MA60', 'MA120', 'MA200'];
            fields = ['ma5', 'ma10', 'ma20', 'ma30', 'ma60', 'ma120', 'ma200'];
            break;
        case 'macd':
            headers = ['日期', 'DIF', 'DEA', 'MACD', 'EMA12', 'EMA26'];
            fields = ['dif', 'dea', 'macd', 'ema12', 'ema26'];
            break;
        case 'kdj':
            headers = ['日期', 'K', 'D', 'J', 'RSV'];
            fields = ['k', 'd', 'j', 'rsv'];
            break;
        case 'rsi':
            headers = ['日期', 'RSI6', 'RSI12', 'RSI24'];
            fields = ['rsi6', 'rsi12', 'rsi24'];
            break;
        case 'boll':
            headers = ['日期', '上轨 (Upper)', '中轨 (Mid)', '下轨 (Lower)'];
            fields = ['upper', 'mid', 'lower'];
            break;
        case 'mavol':
            headers = ['日期', 'MAVOL5', 'MAVOL10', 'MAVOL20', 'MAVOL30', 'MAVOL60', 'MAVOL120', 'MAVOL200'];
            fields = ['mavol5', 'mavol10', 'mavol20', 'mavol30', 'mavol60', 'mavol120', 'mavol200'];
            break;
        case 'pvfrs':
            headers = ['日期', 'MA20', 'MAVOL20', '位移Delta', '即时偏离', '上涨天数Z', '下跌天数F', '效率(V-M)', '乖离率Bias'];
            fields = ['ma20_d', 'mavol20_m', 'macro_displacement_delta', 'instant_deviation', 'rising_days_z', 'falling_days_f', 'efficiency_m20_minus_m', 'bias'];
            break;
    }

    let html = `<table class="data-table"><thead><tr>`;
    headers.forEach(h => html += `<th>${h}</th>`);
    html += `</tr></thead><tbody>`;

    globalData.forEach(item => {
        const subData = item[subKey];
        html += `<tr>`;
        html += `<td>${item.date}</td>`;

        if (subData) {
            fields.forEach(field => {
                let val = subData[field];
                // 特殊处理整数列
                const isInt = (type === 'pvfrs' && (field === 'rising_days_z' || field === 'falling_days_f'));
                html += `<td>${processValue(val, isInt)}</td>`;
            });
        } else {
            fields.forEach(() => html += `<td>-</td>`);
        }

        html += `</tr>`;
    });

    html += `</tbody></table>`;
    container.innerHTML = html;
}

function showError(msg) {
    const errorDiv = document.getElementById('error');
    errorDiv.textContent = msg;
    errorDiv.style.display = 'block';
    document.getElementById('loading').style.display = 'none';
    document.getElementById('mainContent').style.display = 'none';
}


//const API_BASE_URL = Config.getApiBaseUrl();

document.addEventListener('DOMContentLoaded', () => {
    // 获取URL参数
    const urlParams = new URLSearchParams(window.location.search);
    const stockCode = urlParams.get('code');
    const date = urlParams.get('date');
    const market = urlParams.get('market') || 'CN'; // 默认为CN

    if (!stockCode || !date) {
        showError('缺少必要参数：股票代码或日期');
        return;
    }

    // 更新页面标题信息
    document.getElementById('stockInfo').textContent = `${stockCode} - ${date}`;

    // 加载数据
    loadIndicatorDetails(stockCode, date, market);
});

async function loadIndicatorDetails(code, date, market) {
    try {
        // 使用authFetch获取数据
        const response = await authFetch(`${API_BASE_URL}/api/admin/indicators/details?code=${code}&date=${date}&market_type=${market}`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();

        if (result.success && result.data) {
            renderData(result.data);
            document.getElementById('loading').style.display = 'none';
            document.getElementById('indicatorGrid').style.display = 'grid';
        } else {
            showError('未找到相关数据');
        }

    } catch (error) {
        console.error('加载指标数据失败:', error);
        showError(`加载失败: ${error.message}`);
    }
}

function renderData(data) {
    // 渲染 MA
    renderCard('maContent', data.ma, {
        'ma5': 'MA5',
        'ma10': 'MA10',
        'ma20': 'MA20',
        'ma30': 'MA30',
        'ma60': 'MA60',
        'ma120': 'MA120',
        'ma200': 'MA200'
    });

    // 渲染 MACD
    renderCard('macdContent', data.macd, {
        'dif': 'DIF',
        'dea': 'DEA',
        'macd': 'MACD柱',
        'ema12': 'EMA12',
        'ema26': 'EMA26'
    });

    // 渲染 KDJ
    renderCard('kdjContent', data.kdj, {
        'k': 'K',
        'd': 'D',
        'j': 'J',
        'rsv': 'RSV'
    });

    // 渲染 RSI
    renderCard('rsiContent', data.rsi, {
        'rsi6': 'RSI6',
        'rsi12': 'RSI12',
        'rsi24': 'RSI24'
    });

    // 渲染 BOLL
    renderCard('bollContent', data.boll, {
        'upper': '上轨 (Upper)',
        'mid': '中轨 (Mid)',
        'lower': '下轨 (Lower)'
    });

    // 渲染 MAVOL
    renderCard('mavolContent', data.mavol, {
        'mavol5': 'MAVOL5',
        'mavol10': 'MAVOL10',
        'mavol20': 'MAVOL20',
        'mavol30': 'MAVOL30',
        'mavol60': 'MAVOL60',
        'mavol120': 'MAVOL120',
        'mavol200': 'MAVOL200'
    });

    // 渲染 PVFRS
    renderCard('pvfrsContent', data.pvfrs, {
        'macro_displacement_delta': '宏观位移 Delta (d20-d1)',
        'instant_deviation': '即时偏离度 (d20-d)',
        'rising_days_z': '上涨天数 (Z)',
        'falling_days_f': '下跌天数 (F)',
        'efficiency_m20_minus_m': '进出效率 (Vol-MAVOL20)',
        'bias': '乖离率 (Bias)',
        'ma20_d': 'MA20 (d)',
        'mavol20_m': 'MAVOL20 (m)'
    });
}

function renderCard(elementId, dataObj, keyMap) {
    const container = document.getElementById(elementId);
    if (!dataObj) {
        container.innerHTML = '<div class="no-data">暂无数据</div>';
        // 为了布局美观，如果是PVFRS占据整行，暂无数据也要占位吗？
        // CSS控制了grid，暂无数据会显示在内容区。
        return;
    }

    let html = '';
    for (const [key, label] of Object.entries(keyMap)) {
        let value = dataObj[key];

        // 格式化数值
        if (value !== null && value !== undefined) {
            if (typeof value === 'number') {
                // 判断是否是整数（如天数）
                if (key.includes('days')) {
                    value = value;
                } else {
                    value = value.toFixed(3);
                }
            }
        } else {
            value = '-';
        }

        html += `
            <div class="data-item">
                <span class="data-label">${label}</span>
                <span class="data-value">${value}</span>
            </div>
        `;
    }
    container.innerHTML = html;
}

function showError(msg) {
    const errorDiv = document.getElementById('error');
    errorDiv.textContent = msg;
    errorDiv.style.display = 'block';
    document.getElementById('loading').style.display = 'none';
}

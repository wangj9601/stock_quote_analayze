// stock_history.js
// 假设通过URL参数传递code，如 stock_history.html?code=002539

(function() {
    let code = getQueryParam('code') || '';
    let page = 1;
    let size = 50;
    let total = 0;
    let startDate = '';
    let endDate = '';

    function isDateRangeValid(start, end) {
        if (!start || !end) return true;
        // 统一格式为YYYY-MM-DD再比较
        const s = start.replaceAll('/', '-');
        const e = end.replaceAll('/', '-');
        return new Date(s) <= new Date(e);
    }
    
    function getQueryParam(name) {
        const url = window.location.search;
        const params = new URLSearchParams(url);
        return params.get(name);
    }

    function formatAmount(val) {
        if (val === undefined || val === null || isNaN(val)) return '';
        const amount = parseFloat(val);
        if (amount >= 1e8) {
            // 大于等于1亿，显示为亿
            return (amount / 1e8).toFixed(2) + '亿';
        } else if (amount >= 1e4) {
            // 大于等于1万，显示为万
            return (amount / 1e4).toFixed(2) + '万';
        } else {
            // 小于1万，显示原始数值
            return amount.toFixed(2);
        }
    }

    function formatVolume(val) {
        if (val === undefined || val === null || isNaN(val)) return '';
        return (parseFloat(val) / 1e4).toFixed(2) + '万';
    }

    function fetchHistory() {
        if (!code) {
            alert('未指定股票代码');
            return;
        }
        startDate = document.getElementById('startDate').value;
        endDate = document.getElementById('endDate').value;
        let url = `${API_BASE_URL}/api/stock/history?code=${code}&page=${page}&size=${size}`;
        if (startDate) url += `&start_date=${startDate}`;
        if (endDate) url += `&end_date=${endDate}`;
        fetch(url)
            .then(res => res.json())
            .then(data => {
                total = data.total;
                renderTable(data.items);
                renderPageInfo();
            });
    }

    function renderTable(items) {
        const tbody = document.querySelector('#historyTable tbody');
        tbody.innerHTML = '';
        if (!items.length) {
            tbody.innerHTML = '<tr><td colspan="12">无数据</td></tr>';
            return;
        }
        items.forEach(row => {
            const stockCode = row.stock_code || row.code || code;
            const stockName = row.stock_name || row.name || '';
            const amount = formatAmount(row.amount);
            const volume = formatVolume(row.volume);
            const changePercentVal = row.change_percent !== undefined && row.change_percent !== null ? parseFloat(row.change_percent) : '';
            const changePercent = changePercentVal !== '' ? changePercentVal.toFixed(2) + '%' : '';
            const changeVal = row.change !== undefined && row.change !== null ? parseFloat(row.change) : '';
            const change = changeVal !== '' ? changeVal : '';
            const turnoverRate = row.turnover_rate !== undefined ? row.turnover_rate : '';
            // 涨跌额、涨跌幅单元格加色
            let changePercentClass = '', changeClass = '';
            if (changeVal !== '') {
                if (changeVal > 0) changeClass = 'cell-up';
                else if (changeVal < 0) changeClass = 'cell-down';
            }
            if (changePercentVal !== '') {
                if (changePercentVal > 0) changePercentClass = 'cell-up';
                else if (changePercentVal < 0) changePercentClass = 'cell-down';
            }
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${stockCode}</td><td>${stockName}</td><td>${row.date}</td><td>${row.open}</td><td>${row.close}</td><td>${row.high}</td><td>${row.low}</td><td>${volume}</td><td>${amount}</td><td class='${changePercentClass}'>${changePercent}</td><td class='${changeClass}'>${change}</td><td>${turnoverRate}</td>`;
            tbody.appendChild(tr);
        });
    }

    function renderPageInfo() {
        const pageInfo = document.getElementById('pageInfo');
        const pageCount = Math.ceil(total / size);
        pageInfo.textContent = `第 ${page} / ${pageCount || 1} 页`;
        // 同步禁用分页按钮
        document.getElementById('firstPage').disabled = (page === 1);
        document.getElementById('prevPage').disabled = (page === 1);
        document.getElementById('nextPage').disabled = (page === pageCount || pageCount === 0);
        document.getElementById('lastPage').disabled = (page === pageCount || pageCount === 0);
    }

    document.getElementById('searchBtn').onclick = function() {
        const start = document.getElementById('startDate').value;
        const end = document.getElementById('endDate').value;
        if (!isDateRangeValid(start, end)) {
            alert('结束日期不能小于开始日期！');
            return;
        }
        page = 1;
        fetchHistory();
    };
    document.getElementById('prevPage').onclick = function() {
        if (page > 1) {
            page--;
            fetchHistory();
        }
    };
    document.getElementById('nextPage').onclick = function() {
        const pageCount = Math.ceil(total / size);
        if (page < pageCount) {
            page++;
            fetchHistory();
        }
    };
    document.getElementById('exportBtn').onclick = function() {
        const start = document.getElementById('startDate').value;
        const end = document.getElementById('endDate').value;
        if (!isDateRangeValid(start, end)) {
            alert('结束日期不能小于开始日期！');
            return;
        }
        startDate = start;
        endDate = end;
        let url = `${API_BASE_URL}/api/stock/history/export?code=${code}`;
        if (startDate) url += `&start_date=${startDate}`;
        if (endDate) url += `&end_date=${endDate}`;
        window.open(url, '_blank');
    };
    document.getElementById('firstPage').onclick = function() {
        if (page !== 1) {
            page = 1;
            fetchHistory();
        }
    };
    document.getElementById('lastPage').onclick = function() {
        const pageCount = Math.ceil(total / size);
        if (page !== pageCount && pageCount > 0) {
            page = pageCount;
            fetchHistory();
        }
    };

    // 页面加载时自动拉取数据
    fetchHistory();
})(); 
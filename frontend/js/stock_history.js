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
            tbody.innerHTML = '<tr><td colspan="8">无数据</td></tr>';
            return;
        }
        items.forEach(row => {
            const stockCode = row.stock_code || row.code || code;
            const stockName = row.stock_name || row.name || '';
            const amount = row.amount !== undefined ? row.amount : '';
            const changePercent = row.change_percent !== undefined ? row.change_percent : '';
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${stockCode}</td><td>${stockName}</td><td>${row.date}</td><td>${row.open}</td><td>${row.close}</td><td>${row.high}</td><td>${row.low}</td><td>${row.volume}</td><td>${amount}</td><td>${changePercent}</td>`;
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
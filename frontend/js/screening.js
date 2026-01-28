// 选股页面功能模块
const ScreeningPage = {
    API_BASE_URL: Config ? Config.getApiBaseUrl() : 'http://192.168.31.237:5000',
    currentStrategy: 'cyb-midline', // 当前选中的策略
    lastResults: {}, // 存储最近一次筛选结果，用于导出

    // 初始化
    async init() {
        await this.loadHeader();
        this.bindEvents();
        this.initStrategyTabs();
    },

    // 初始化策略标签页
    initStrategyTabs() {
        const tabs = document.querySelectorAll('.strategy-tab');
        tabs.forEach(tab => {
            // 跳过隐藏的标签页（停机坪、回踩年线、高而窄的旗形）
            const hiddenStrategies = ['parking-apron', 'backtrace-ma250', 'high-tight-flag'];
            if (hiddenStrategies.includes(tab.dataset.strategy)) {
                return; // 跳过隐藏的策略
            }

            tab.addEventListener('click', () => {
                const strategy = tab.dataset.strategy;
                this.switchStrategy(strategy);
            });
        });
    },

    // 切换策略标签页
    switchStrategy(strategy) {
        // 检查是否为隐藏的策略
        const hiddenStrategies = ['parking-apron', 'backtrace-ma250', 'high-tight-flag'];
        if (hiddenStrategies.includes(strategy)) {
            console.warn(`策略 ${strategy} 已被隐藏，无法切换`);
            return;
        }

        this.currentStrategy = strategy;

        // 更新标签页状态
        document.querySelectorAll('.strategy-tab').forEach(t => {
            t.classList.remove('active');
        });
        const targetTab = document.querySelector(`[data-strategy="${strategy}"]`);
        if (targetTab) {
            targetTab.classList.add('active');
        }

        // 更新内容区域显示
        document.querySelectorAll('.strategy-content').forEach(c => {
            c.classList.remove('active');
        });
        const targetContent = document.getElementById(`${strategy}-content`);
        if (targetContent) {
            targetContent.classList.add('active');
        }
    },

    // 加载头部导航
    async loadHeader() {
        try {
            const headerContainer = document.getElementById('header-container');
            if (headerContainer) {
                // 动态加载头部组件HTML
                const response = await fetch('components/header.html');
                if (response.ok) {
                    const headerHtml = await response.text();
                    headerContainer.innerHTML = headerHtml;

                    // 等待DOM更新后初始化头部功能
                    setTimeout(() => {
                        // 高亮当前频道
                        const nav = document.getElementById('nav-screening');
                        if (nav) {
                            nav.classList.add('active');
                        }

                        // 初始化用户菜单
                        if (typeof initUserMenu === 'function') {
                            initUserMenu();
                        }

                        // 初始化股票搜索功能
                        if (typeof initStockSearch === 'function') {
                            initStockSearch();
                        } else {
                            console.warn('initStockSearch函数未找到，等待header.js加载');
                            // 等待header.js加载完成
                            const checkInterval = setInterval(() => {
                                if (typeof initStockSearch === 'function') {
                                    initStockSearch();
                                    clearInterval(checkInterval);
                                }
                            }, 100);

                            // 5秒后停止检查
                            setTimeout(() => clearInterval(checkInterval), 5000);
                        }

                        // 更新用户显示
                        if (window.CommonUtils && window.CommonUtils.auth) {
                            CommonUtils.auth.updateUserDisplay(CommonUtils.auth.getUserInfo());
                        }
                    }, 100);
                }
            }
        } catch (error) {
            console.error('加载头部导航失败:', error);
        }
    },

    // 绑定事件
    bindEvents() {
        // 绑定所有刷新按钮
        document.querySelectorAll('.refresh-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const strategy = btn.dataset.strategy;
                this.loadScreeningResults(strategy);
            });
        });

        // 绑定所有导出按钮
        document.querySelectorAll('.export-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                // 从ID中提取策略名称，例如 exportBtn-one-yang-three-lines -> one-yang-three-lines
                const strategy = btn.id.replace('exportBtn-', '');
                this.exportToCSV(strategy);
            });
        });

        // 绑定PVFARS策略范围切换事件
        document.querySelectorAll('input[name="pvfrsScope"]').forEach(radio => {
            radio.addEventListener('change', () => {
                this.loadScreeningResults('pvfrs');
            });
        });
    },

    // 加载选股结果
    async loadScreeningResults(strategy = null) {
        if (!strategy) {
            strategy = this.currentStrategy;
        }

        let suffix;
        if (strategy === 'cyb-midline') {
            suffix = 'cyb';
        } else if (strategy === 'parking-apron') {
            suffix = 'parking';
        } else if (strategy === 'backtrace-ma250') {
            suffix = 'backtrace';
        } else if (strategy === 'high-tight-flag') {
            suffix = 'high-tight';
        } else if (strategy === 'keep-increasing') {
            suffix = 'keep-increasing';
        } else if (strategy === 'long-lower-shadow') {
            suffix = 'long-lower-shadow';
        } else if (strategy === 'low-nine') {
            suffix = 'low-nine';
        } else if (strategy === 'one-yang-three-lines') {
            suffix = 'one-yang-three-lines';
        } else if (strategy === 'pvfrs') {
            suffix = 'pvfrs';
        } else {
            suffix = 'cyb';
        }
        const loadingIndicator = document.getElementById(`loadingIndicator-${suffix}`);
        const errorMessage = document.getElementById(`errorMessage-${suffix}`);
        const resultsTableBody = document.getElementById(`resultsTableBody-${suffix}`);
        const resultsCount = document.getElementById(`resultsCount-${suffix}`);
        const refreshBtn = document.getElementById(`refreshBtn-${strategy}`);
        const exportBtn = document.getElementById(`exportBtn-${strategy}`);
        const searchDate = document.getElementById(`searchDate-${suffix}`);

        // 显示加载状态
        if (loadingIndicator) {
            loadingIndicator.style.display = 'flex';
        }
        if (errorMessage) {
            errorMessage.style.display = 'none';
            errorMessage.textContent = '';
        }
        if (refreshBtn) {
            refreshBtn.disabled = true;
        }
        if (exportBtn) {
            exportBtn.style.display = 'none';
        }

        try {
            // 获取API基础URL
            const apiBaseUrl = this.API_BASE_URL;
            let url;

            if (strategy === 'cyb-midline') {
                url = `${apiBaseUrl}/api/screening/cyb-midline-strategy?months=4`;
            } else if (strategy === 'parking-apron') {
                url = `${apiBaseUrl}/api/screening/parking-apron-strategy`;
            } else if (strategy === 'backtrace-ma250') {
                url = `${apiBaseUrl}/api/screening/backtrace-ma250-strategy`;
            } else if (strategy === 'high-tight-flag') {
                url = `${apiBaseUrl}/api/screening/high-tight-flag-strategy`;
            } else if (strategy === 'keep-increasing') {
                url = `${apiBaseUrl}/api/screening/keep-increasing-strategy`;
            } else if (strategy === 'long-lower-shadow') {
                // 读取参数并转换为数字
                let lowerShadowRatio = parseFloat(document.getElementById('lowerShadowRatio')?.value);
                if (isNaN(lowerShadowRatio)) lowerShadowRatio = 1.0;

                let upperShadowRatio = parseFloat(document.getElementById('upperShadowRatio')?.value);
                if (isNaN(upperShadowRatio)) upperShadowRatio = 0.3;

                let minAmplitude = parseFloat(document.getElementById('minAmplitude')?.value);
                if (isNaN(minAmplitude)) minAmplitude = 0.02;

                // 智能处理振幅参数：如果用户输入 > 0.5（可能是百分比），则自动除以100
                // 例如：输入 2 -> 0.02, 输入 5 -> 0.05
                if (minAmplitude > 0.5) {
                    console.log(`[长下影线] 检测到振幅参数 ${minAmplitude} > 0.5，自动转换为 ${minAmplitude / 100}`);
                    minAmplitude = minAmplitude / 100;
                }

                let recentDays = parseInt(document.getElementById('recentDays')?.value);
                if (isNaN(recentDays)) recentDays = 2;

                // 构造带参数的URL
                url = `${apiBaseUrl}/api/screening/long-lower-shadow-strategy?` +
                    `lower_shadow_ratio=${lowerShadowRatio}&` +
                    `upper_shadow_ratio=${upperShadowRatio}&` +
                    `min_amplitude=${minAmplitude}&` +
                    `recent_days=${recentDays}`;
            } else if (strategy === 'low-nine') {
                url = `${apiBaseUrl}/api/screening/low-nine-strategy`;
            } else if (strategy === 'one-yang-three-lines') {
                // 获取一阳穿三线策略参数
                const params = this.getOneYangThreeLinesParams();
                const queryString = new URLSearchParams(params).toString();
                url = `${apiBaseUrl}/api/screening/one-yang-three-lines?${queryString}`;
            } else if (strategy === 'pvfrs') {
                // 读取股票范围参数
                const scopeElement = document.querySelector('input[name="pvfrsScope"]:checked');
                let scope = scopeElement ? scopeElement.value : 'all';

                url = `${apiBaseUrl}/api/screening/pvfrs-strategy?scope=${scope}`;
            } else {
                throw new Error('未知的策略类型');
            }

            // 使用authFetch或fetch
            const fetchFn = (typeof authFetch === 'function')
                ? authFetch
                : async (url, options) => {
                    const token = localStorage.getItem('access_token');
                    const headers = options?.headers || {};
                    if (token) {
                        headers['Authorization'] = 'Bearer ' + token;
                    }
                    return fetch(url, { ...options, headers });
                };

            const response = await fetchFn(url);
            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.detail || result.message || '请求失败');
            }

            if (result.success && result.data) {
                this.lastResults[strategy] = result.data;
                this.renderResults(result.data, result.search_date, strategy);
                if (searchDate) {
                    searchDate.textContent = `筛选时间: ${result.search_date}`;
                }
                // 显示导出按钮
                if (exportBtn && result.data.length > 0) {
                    exportBtn.style.display = 'inline-block';
                }
            } else {
                this.lastResults[strategy] = [];
                throw new Error(result.message || '未找到符合条件的股票');
            }

        } catch (error) {
            console.error('加载选股结果失败:', error);
            if (errorMessage) {
                // 处理不同类型的错误对象
                let errorMsg = '未知错误';
                if (typeof error === 'string') {
                    errorMsg = error;
                } else if (error && error.message) {
                    errorMsg = error.message;
                } else if (error && error.detail) {
                    if (Array.isArray(error.detail)) {
                        errorMsg = error.detail.map(e => `${e.loc.join('.')}: ${e.msg}`).join(', ');
                    } else {
                        errorMsg = JSON.stringify(error.detail);
                    }
                } else {
                    try {
                        errorMsg = JSON.stringify(error);
                        if (errorMsg === '{}') errorMsg = error.toString();
                    } catch (e) {
                        errorMsg = error.toString();
                    }
                }

                errorMessage.textContent = `加载失败: ${errorMsg}`;
                errorMessage.style.display = 'block';
            }
            let colSpan;
            if (strategy === 'cyb-midline') {
                colSpan = 12;
            } else if (strategy === 'parking-apron') {
                colSpan = 7;
            } else if (strategy === 'backtrace-ma250') {
                colSpan = 9;
            } else if (strategy === 'high-tight-flag') {
                colSpan = 7;
            } else if (strategy === 'keep-increasing') {
                colSpan = 8;
            } else if (strategy === 'long-lower-shadow') {
                colSpan = 13;
            } else if (strategy === 'low-nine') {
                colSpan = 11;
            } else if (strategy === 'one-yang-three-lines') {
                colSpan = 13;
            } else if (strategy === 'pvfrs') {
                colSpan = 12;
            } else {
                colSpan = 12;
            }
            if (resultsTableBody) {
                resultsTableBody.innerHTML = `<tr><td colspan="${colSpan}" class="empty-state">加载失败，请稍后重试</td></tr>`;
            }
            if (resultsCount) {
                resultsCount.textContent = '共找到 0 只符合条件的股票';
            }
        } finally {
            // 隐藏加载状态
            if (loadingIndicator) {
                loadingIndicator.style.display = 'none';
            }
            if (refreshBtn) {
                refreshBtn.disabled = false;
            }
        }
    },

    // 渲染结果
    renderResults(data, searchDate, strategy = 'cyb-midline') {
        let suffix;
        if (strategy === 'cyb-midline') {
            suffix = 'cyb';
        } else if (strategy === 'parking-apron') {
            suffix = 'parking';
        } else if (strategy === 'backtrace-ma250') {
            suffix = 'backtrace';
        } else if (strategy === 'high-tight-flag') {
            suffix = 'high-tight';
        } else if (strategy === 'keep-increasing') {
            suffix = 'keep-increasing';
        } else if (strategy === 'long-lower-shadow') {
            suffix = 'long-lower-shadow';
        } else if (strategy === 'low-nine') {
            suffix = 'low-nine';
        } else if (strategy === 'one-yang-three-lines') {
            suffix = 'one-yang-three-lines';
        } else if (strategy === 'pvfrs') {
            suffix = 'pvfrs';
        } else {
            suffix = 'cyb';
        }
        const resultsTableBody = document.getElementById(`resultsTableBody-${suffix}`);
        const resultsCount = document.getElementById(`resultsCount-${suffix}`);

        if (!resultsTableBody) {
            return;
        }

        if (!data || data.length === 0) {
            let colSpan;
            if (strategy === 'cyb-midline') {
                colSpan = 12;
            } else if (strategy === 'parking-apron') {
                colSpan = 7;
            } else if (strategy === 'backtrace-ma250') {
                colSpan = 9;
            } else if (strategy === 'high-tight-flag') {
                colSpan = 7;
            } else if (strategy === 'keep-increasing') {
                colSpan = 8;
            } else if (strategy === 'long-lower-shadow') {
                colSpan = 13;
            } else if (strategy === 'low-nine') {
                colSpan = 11;
            } else if (strategy === 'one-yang-three-lines') {
                colSpan = 13;
            } else if (strategy === 'pvfrs') {
                colSpan = 12;
            } else {
                colSpan = 12;
            }
            resultsTableBody.innerHTML = `<tr><td colspan="${colSpan}" class="empty-state">未找到符合条件的股票</td></tr>`;
            if (resultsCount) {
                resultsCount.textContent = '共找到 0 只符合条件的股票';
            }
            return;
        }

        // 更新计数
        if (resultsCount) {
            resultsCount.textContent = `共找到 ${data.length} 只符合条件的股票`;
        }

        // 渲染表格
        let html = '';
        data.forEach((stock, index) => {
            const changePercent = stock.current_change_percent || 0;
            const changeClass = changePercent > 0 ? 'price-positive' : (changePercent < 0 ? 'price-negative' : 'price-neutral');
            const changeSymbol = changePercent > 0 ? '+' : '';

            if (strategy === 'cyb-midline') {
                // 创业板中线选股策略表格
                html += `
                    <tr>
                        <td><span class="stock-code">${stock.code}</span></td>
                        <td><span class="stock-name">${stock.name}</span></td>
                        <td>${stock.limit_up_date}</td>
                        <td>${stock.limit_up_price.toFixed(2)}</td>
                        <td>${stock.breakthrough_date}</td>
                        <td>${stock.breakthrough_price.toFixed(2)}</td>
                        <td>${stock.current_price.toFixed(2)}</td>
                        <td class="${changeClass}">${changeSymbol}${changePercent.toFixed(2)}%</td>
                        <td>${stock.ma5.toFixed(2)}</td>
                        <td>${stock.ma10.toFixed(2)}</td>
                        <td>${stock.ma20.toFixed(2)}</td>
                        <td>
                            <div class="action-links">
                                <a href="stock_history.html?code=${stock.code}" class="action-link" target="_blank">历史</a>
                                <a href="stock.html?code=${stock.code}&name=${encodeURIComponent(stock.name)}" class="action-link" target="_blank">详情</a>
                            </div>
                        </td>
                    </tr>
                `;
            } else if (strategy === 'parking-apron') {
                // 停机坪策略表格
                html += `
                    <tr>
                        <td><span class="stock-code">${stock.code}</span></td>
                        <td><span class="stock-name">${stock.name}</span></td>
                        <td>${stock.limit_up_date || '--'}</td>
                        <td>${stock.limit_up_price ? stock.limit_up_price.toFixed(2) : '--'}</td>
                        <td>${stock.current_price ? stock.current_price.toFixed(2) : '--'}</td>
                        <td class="${changeClass}">${changeSymbol}${changePercent.toFixed(2)}%</td>
                        <td>
                            <div class="action-links">
                                <a href="stock_history.html?code=${stock.code}" class="action-link" target="_blank">历史</a>
                                <a href="stock.html?code=${stock.code}&name=${encodeURIComponent(stock.name)}" class="action-link" target="_blank">详情</a>
                            </div>
                        </td>
                    </tr>
                `;
            } else if (strategy === 'backtrace-ma250') {
                // 回踩年线策略表格
                html += `
                    <tr>
                        <td><span class="stock-code">${stock.code}</span></td>
                        <td><span class="stock-name">${stock.name}</span></td>
                        <td>${stock.highest_date || '--'}</td>
                        <td>${stock.highest_price ? stock.highest_price.toFixed(2) : '--'}</td>
                        <td>${stock.lowest_date || '--'}</td>
                        <td>${stock.lowest_price ? stock.lowest_price.toFixed(2) : '--'}</td>
                        <td>${stock.current_price ? stock.current_price.toFixed(2) : '--'}</td>
                        <td class="${changeClass}">${changeSymbol}${changePercent.toFixed(2)}%</td>
                        <td>
                            <div class="action-links">
                                <a href="stock_history.html?code=${stock.code}" class="action-link" target="_blank">历史</a>
                                <a href="stock.html?code=${stock.code}&name=${encodeURIComponent(stock.name)}" class="action-link" target="_blank">详情</a>
                            </div>
                        </td>
                    </tr>
                `;
            } else if (strategy === 'high-tight-flag') {
                // 高而窄的旗形策略表格
                html += `
                    <tr>
                        <td><span class="stock-code">${stock.code}</span></td>
                        <td><span class="stock-name">${stock.name}</span></td>
                        <td>${stock.current_price ? stock.current_price.toFixed(2) : '--'}</td>
                        <td class="${changeClass}">${changeSymbol}${changePercent.toFixed(2)}%</td>
                        <td>${stock.period_low ? stock.period_low.toFixed(2) : '--'}</td>
                        <td>${stock.price_ratio ? stock.price_ratio.toFixed(2) : '--'}</td>
                        <td>
                            <div class="action-links">
                                <a href="stock_history.html?code=${stock.code}" class="action-link" target="_blank">历史</a>
                                <a href="stock.html?code=${stock.code}&name=${encodeURIComponent(stock.name)}" class="action-link" target="_blank">详情</a>
                            </div>
                        </td>
                    </tr>
                `;
            } else if (strategy === 'keep-increasing') {
                // 持续上涨（MA30向上）策略表格
                html += `
                    <tr>
                        <td><span class="stock-code">${stock.code}</span></td>
                        <td><span class="stock-name">${stock.name}</span></td>
                        <td>${stock.current_price ? stock.current_price.toFixed(2) : '--'}</td>
                        <td class="${changeClass}">${changeSymbol}${changePercent.toFixed(2)}%</td>
                        <td>${stock.current_ma30 ? stock.current_ma30.toFixed(2) : '--'}</td>
                        <td>${stock.ma30_before_30 ? stock.ma30_before_30.toFixed(2) : '--'}</td>
                        <td>${stock.ma30_increase_ratio ? (stock.ma30_increase_ratio * 100).toFixed(2) + '%' : '--'}</td>
                        <td>
                            <div class="action-links">
                                <a href="stock_history.html?code=${stock.code}" class="action-link" target="_blank">历史</a>
                                <a href="stock.html?code=${stock.code}&name=${encodeURIComponent(stock.name)}" class="action-link" target="_blank">详情</a>
                            </div>
                        </td>
                    </tr>
                `;
            } else if (strategy === 'long-lower-shadow') {
                // 长下影阳线策略表格
                html += `
                    <tr>
                        <td><span class="stock-code">${stock.code}</span></td>
                        <td><span class="stock-name">${stock.name}</span></td>
                        <td>${stock.pattern_date || '--'}</td>
                        <td>${stock.pattern_close ? stock.pattern_close.toFixed(2) : '--'}</td>
                        <td>${stock.lower_shadow ? stock.lower_shadow.toFixed(2) : '--'}</td>
                        <td>${stock.body_length ? stock.body_length.toFixed(2) : '--'}</td>
                        <td>${stock.shadow_body_ratio ? stock.shadow_body_ratio.toFixed(2) : '--'}</td>
                        <td>${stock.amplitude ? (stock.amplitude * 100).toFixed(2) + '%' : '--'}</td>
                        <td>${stock.current_price ? stock.current_price.toFixed(2) : '--'}</td>
                        <td class="${changeClass}">${changeSymbol}${changePercent.toFixed(2)}%</td>
                        <td>${stock.ma20 ? stock.ma20.toFixed(2) : '--'}</td>
                        <td class="${stock.deviation_from_ma20 < 0 ? 'negative' : (stock.deviation_from_ma20 > 0 ? 'positive' : '')}">${stock.deviation_from_ma20 ? (stock.deviation_from_ma20 * 100).toFixed(2) + '%' : '--'}</td>
                        <td>
                            <div class="action-links">
                                <a href="stock_history.html?code=${stock.code}" class="action-link" target="_blank">历史</a>
                                <a href="stock.html?code=${stock.code}&name=${encodeURIComponent(stock.name)}" class="action-link" target="_blank">详情</a>
                            </div>
                        </td>
                    </tr>
                `;
            } else if (strategy === 'low-nine') {
                // 低九策略表格
                html += `
                    <tr>
                        <td><span class="stock-code">${stock.code}</span></td>
                        <td><span class="stock-name">${stock.name}</span></td>
                        <td>${stock.pattern_start_date || '--'}</td>
                        <td>${stock.pattern_end_date || '--'}</td>
                        <td>${stock.pattern_start_price ? stock.pattern_start_price.toFixed(2) : '--'}</td>
                        <td class="price-negative">${stock.nine_day_decline ? stock.nine_day_decline.toFixed(2) + '%' : '--'}</td>
                        <td>${stock.nine_day_high ? stock.nine_day_high.toFixed(2) : '--'}</td>
                        <td>${stock.nine_day_low ? stock.nine_day_low.toFixed(2) : '--'}</td>
                        <td>${stock.current_price ? stock.current_price.toFixed(2) : '--'}</td>
                        <td class="${changeClass}">${changeSymbol}${changePercent.toFixed(2)}%</td>
                        <td>
                            <div class="action-links">
                                <a href="stock_history.html?code=${stock.code}" class="action-link" target="_blank">历史</a>
                                <a href="stock.html?code=${stock.code}&name=${encodeURIComponent(stock.name)}" class="action-link" target="_blank">详情</a>
                            </div>
                        </td>
                    </tr>
                `;
            } else if (strategy === 'one-yang-three-lines') {
                // 一阳穿三线策略表格
                // 位置类型颜色标识
                let positionClass = '';
                if (stock.position_type === '低位') {
                    positionClass = 'position-low';
                } else if (stock.position_type === '中位') {
                    positionClass = 'position-mid';
                } else if (stock.position_type === '高位') {
                    positionClass = 'position-high';
                }

                // 风险提示
                const riskWarnings = stock.risk_warnings && stock.risk_warnings.length > 0
                    ? stock.risk_warnings.join('；')
                    : '--';

                html += `
                    <tr>
                        <td><span class="stock-code">${stock.code}</span></td>
                        <td><span class="stock-name">${stock.name}</span></td>
                        <td>${stock.signal_date || '--'}</td>
                        <td>${stock.current_price ? stock.current_price.toFixed(2) : '--'}</td>
                        <td><span class="crossed-lines">${stock.crossed_lines || '--'}</span></td>
                        <td>${stock.volume_ratio ? stock.volume_ratio.toFixed(2) : '--'}</td>
                        <td>${stock.turnover_rate ? stock.turnover_rate.toFixed(2) + '%' : '--'}</td>
                        <td><span class="${positionClass}">${stock.position_type || '--'}</span></td>
                        <td>${stock.retracement ? stock.retracement.toFixed(2) + '%' : '--'}</td>
                        <td>${stock.bias30 ? stock.bias30.toFixed(2) + '%' : '--'}</td>
                        <td><span class="signal-score">${stock.signal_score || '--'}</span></td>
                        <td><span class="risk-warnings">${riskWarnings}</span></td>
                        <td>
                            <div class="action-links">
                                <a href="stock_history.html?code=${stock.code}" class="action-link" target="_blank">历史</a>
                                <a href="stock.html?code=${stock.code}&name=${encodeURIComponent(stock.name)}" class="action-link" target="_blank">详情</a>
                            </div>
                        </td>
                    </tr>
                `;
            } else if (strategy === 'pvfrs') {
                // PVFARS量价频幅度共振策略表格
                // 信号强度颜色标识
                let strengthClass = '';
                const signalStrength = stock.signal_strength || 0;
                if (signalStrength >= 0.8) {
                    strengthClass = 'strength-high';
                } else if (signalStrength >= 0.6) {
                    strengthClass = 'strength-mid';
                } else {
                    strengthClass = 'strength-low';
                }

                // 调试日志：检查股票名称
                if (index < 3) { // 只打印前3条数据
                    console.log(`[DEBUG] PVFARS股票 ${index}: code=${stock.symbol || stock.code}, name=${stock.name}, symbol=${stock.symbol}`);
                }

                // 共振状态显示
                const resonanceStatus = stock.resonance_status || '--';
                let resonanceClass = '';
                if (resonanceStatus === '三维共振') {
                    resonanceClass = 'resonance-active';
                } else if (resonanceStatus === '部分共振') {
                    resonanceClass = 'resonance-partial';
                } else {
                    resonanceClass = 'resonance-none';
                }

                // 投资建议颜色
                let adviceClass = '';
                const advice = stock.investment_advice || '--';
                if (advice === 'BUY' || advice === '买入') {
                    adviceClass = 'advice-buy';
                } else if (advice === 'HOLD' || advice === '持有') {
                    adviceClass = 'advice-hold';
                } else {
                    adviceClass = 'advice-wait';
                }

                html += `
                    <tr>
                        <td><span class="stock-code">${stock.symbol || stock.code}</span></td>
                        <td><span class="stock-name">${stock.name || '--'}</span></td>
                        <td><span class="${strengthClass}">${(signalStrength * 100).toFixed(1)}%</span></td>
                        <td>${stock.current_price ? stock.current_price.toFixed(2) : '--'}</td>
                        <td>${stock.price_dimension_status || '--'}</td>
                        <td>${stock.frequency_dimension_status || '--'}</td>
                        <td>${stock.volume_dimension_status || '--'}</td>
                        <td><span class="${resonanceClass}">${resonanceStatus}</span></td>
                        <td>${stock.entry_timing_status || '--'}</td>
                        <td><span class="${adviceClass}">${advice}</span></td>
                        <td class="${changeClass}">${changeSymbol}${changePercent.toFixed(2)}%</td>
                        <td>
                            <div class="action-links">
                                <a href="stock_history.html?code=${stock.symbol || stock.code}" class="action-link" target="_blank">历史</a>
                                <a href="stock.html?code=${stock.symbol || stock.code}&name=${encodeURIComponent(stock.name || '')}" class="action-link" target="_blank">详情</a>
                            </div>
                        </td>
                    </tr>
                `;
            }
        });

        resultsTableBody.innerHTML = html;
    },

    // 获取一阳穿三线策略参数
    getOneYangThreeLinesParams() {
        const minIncreasePercent = document.getElementById('minIncreasePercent').value;
        const minBodyRatio = document.getElementById('minBodyRatio').value;
        const minCrossLines = document.getElementById('minCrossLines').value;
        const minVolumeRatio = document.getElementById('minVolumeRatio').value;
        const minTurnoverRate = document.getElementById('minTurnoverRate').value;
        const maxTurnoverRate = document.getElementById('maxTurnoverRate').value;

        // 获取选中的均线周期
        const maPeriodsCheckboxes = document.querySelectorAll('input[name="maPeriods"]:checked');
        const maPeriods = Array.from(maPeriodsCheckboxes).map(cb => cb.value);

        return {
            min_increase_percent: parseFloat(minIncreasePercent),
            min_body_ratio: parseFloat(minBodyRatio),
            min_cross_lines: parseInt(minCrossLines),
            min_volume_ratio: parseFloat(minVolumeRatio),
            min_turnover_rate: parseFloat(minTurnoverRate),
            max_turnover_rate: parseFloat(maxTurnoverRate),
            ma_periods: maPeriods.join(',')
        };
    },

    // 重置一阳穿三线策略参数
    resetOneYangThreeLinesParams() {
        document.getElementById('minIncreasePercent').value = '3.0';
        document.getElementById('minBodyRatio').value = '0.7';
        document.getElementById('minCrossLines').value = '3';
        document.getElementById('minVolumeRatio').value = '2.0';
        document.getElementById('minTurnoverRate').value = '3.0';
        document.getElementById('maxTurnoverRate').value = '10.0';

        // 重置均线周期选择
        const maPeriodsCheckboxes = document.querySelectorAll('input[name="maPeriods"]');
        maPeriodsCheckboxes.forEach(cb => {
            cb.checked = true; // 默认全选
        });

        if (window.CommonUtils) {
            CommonUtils.showToast('参数已重置为默认值', 'success');
        }
    },

    // 保存一阳穿三线策略参数到本地存储
    saveOneYangThreeLinesParams() {
        const params = this.getOneYangThreeLinesParams();
        localStorage.setItem('oneYangThreeLinesParams', JSON.stringify(params));
        if (window.CommonUtils) {
            CommonUtils.showToast('参数已保存', 'success');
        }
    },

    // 从本地存储加载一阳穿三线策略参数
    loadOneYangThreeLinesParams() {
        const savedParams = localStorage.getItem('oneYangThreeLinesParams');
        if (savedParams) {
            try {
                const params = JSON.parse(savedParams);
                document.getElementById('minIncreasePercent').value = params.min_increase_percent || '3.0';
                document.getElementById('minBodyRatio').value = params.min_body_ratio || '0.7';
                document.getElementById('minCrossLines').value = params.min_cross_lines || '3';
                document.getElementById('minVolumeRatio').value = params.min_volume_ratio || '2.0';
                document.getElementById('minTurnoverRate').value = params.min_turnover_rate || '3.0';
                document.getElementById('maxTurnoverRate').value = params.max_turnover_rate || '10.0';

                // 恢复均线周期选择
                if (params.ma_periods) {
                    const maPeriodsCheckboxes = document.querySelectorAll('input[name="maPeriods"]');
                    maPeriodsCheckboxes.forEach(cb => {
                        cb.checked = params.ma_periods.includes(cb.value);
                    });
                }
            } catch (e) {
                console.error('加载参数失败:', e);
            }
        }
    },

    // 导出结果到CSV
    exportToCSV(strategy) {
        const data = this.lastResults[strategy];
        if (!data || data.length === 0) {
            if (window.CommonUtils) {
                CommonUtils.showToast('没有可导出的数据', 'warning');
            } else {
                alert('没有可导出的数据');
            }
            return;
        }

        let headers = [];
        let rows = [];
        let filename = `选股结果_${strategy}_${new Date().toISOString().split('T')[0]}.csv`;

        if (strategy === 'one-yang-three-lines') {
            headers = [
                '股票代码', '股票名称', '信号日期', '当前价格',
                '穿越均线', '成交量倍数', '换手率', '位置类型',
                '回撤幅度', 'BIAS30', '信号评分', '风险提示'
            ];
            rows = data.map(stock => [
                `'${stock.code}`, // 防止Excel自动转换长数字
                stock.name,
                stock.signal_date || '',
                stock.current_price || '',
                stock.crossed_lines || '',
                stock.volume_ratio || '',
                stock.turnover_rate ? stock.turnover_rate + '%' : '',
                stock.position_type || '',
                stock.retracement ? stock.retracement + '%' : '',
                stock.bias30 ? stock.bias30 + '%' : '',
                stock.signal_score || '',
                (stock.risk_warnings || []).join(';')
            ]);
            filename = `一阳穿三线筛选结果_${new Date().toISOString().split('T')[0]}.csv`;
        } else if (strategy === 'cyb-midline') {
            headers = [
                '股票代码', '股票名称', '涨停日期', '涨停价格',
                '突破日期', '突破价格', '当前价格', '当前涨跌幅',
                'MA5', 'MA10', 'MA20'
            ];
            rows = data.map(stock => [
                `'${stock.code}`,
                stock.name,
                stock.limit_up_date || '',
                stock.limit_up_price || '',
                stock.breakthrough_date || '',
                stock.breakthrough_price || '',
                stock.current_price || '',
                stock.current_change_percent ? stock.current_change_percent + '%' : '0%',
                stock.ma5 || '',
                stock.ma10 || '',
                stock.ma20 || ''
            ]);
            filename = `创业板中线筛选结果_${new Date().toISOString().split('T')[0]}.csv`;
        } else if (strategy === 'pvfrs') {
            headers = [
                '股票代码', '股票名称', '信号强度', '当前价格',
                '价格维度', '频率维度', '成交量维度', '共振状态',
                '入场时机', '投资建议', '当前涨跌幅'
            ];
            rows = data.map(stock => [
                `'${stock.symbol || stock.code}`,
                stock.name || '',
                stock.signal_strength ? (stock.signal_strength * 100).toFixed(1) + '%' : '',
                stock.current_price || '',
                stock.price_dimension_status || '',
                stock.frequency_dimension_status || '',
                stock.volume_dimension_status || '',
                stock.resonance_status || '',
                stock.entry_timing_status || '',
                stock.investment_advice || '',
                stock.current_change_percent ? stock.current_change_percent.toFixed(2) + '%' : '0%'
            ]);
            filename = `PVFARS量价频幅度共振筛选结果_${new Date().toISOString().split('T')[0]}.csv`;
        } else if (strategy === 'long-lower-shadow') {
            headers = [
                '股票代码', '股票名称', '形态日期', '形态收盘价',
                '下影线长度', '实体长度', '影线/实体比', '当日振幅',
                '当前价格', '当前涨跌幅', 'MA20', '偏离MA20'
            ];
            rows = data.map(stock => [
                `'${stock.code}`,
                stock.name,
                stock.pattern_date || '',
                stock.pattern_close || '',
                stock.lower_shadow || '',
                stock.body_length || '',
                stock.shadow_body_ratio || '',
                stock.amplitude ? (stock.amplitude * 100).toFixed(2) + '%' : '',
                stock.current_price || '',
                stock.current_change_percent ? stock.current_change_percent + '%' : '0%',
                stock.ma20 || '',
                stock.deviation_from_ma20 ? (stock.deviation_from_ma20 * 100).toFixed(2) + '%' : ''
            ]);
            filename = `长下影线筛选结果_${new Date().toISOString().split('T')[0]}.csv`;
        } else if (strategy === 'keep-increasing') {
            headers = [
                '股票代码', '股票名称', '当前价格', '当前涨跌幅',
                '当日MA30', '30日前MA30', 'MA30涨幅'
            ];
            rows = data.map(stock => [
                `'${stock.code}`,
                stock.name,
                stock.current_price || '',
                stock.current_change_percent ? stock.current_change_percent + '%' : '0%',
                stock.current_ma30 || '',
                stock.ma30_before_30 || '',
                stock.ma30_increase_ratio ? (stock.ma30_increase_ratio * 100).toFixed(2) + '%' : ''
            ]);
            filename = `持续上涨(MA30向上)筛选结果_${new Date().toISOString().split('T')[0]}.csv`;
        } else if (strategy === 'low-nine') {
            headers = [
                '股票代码', '股票名称', '形态开始日期', '形态结束日期',
                '形态开始价格', '9天跌幅', '9天最高价', '9天最低价',
                '当前价格', '当前涨跌幅'
            ];
            rows = data.map(stock => [
                `'${stock.code}`,
                stock.name,
                stock.pattern_start_date || '',
                stock.pattern_end_date || '',
                stock.pattern_start_price || '',
                stock.nine_day_decline ? stock.nine_day_decline.toFixed(2) + '%' : '',
                stock.nine_day_high || '',
                stock.nine_day_low || '',
                stock.current_price || '',
                stock.current_change_percent ? stock.current_change_percent + '%' : '0%'
            ]);
            filename = `低九策略筛选结果_${new Date().toISOString().split('T')[0]}.csv`;
        } else {
            // 通用导出（如果需要支持其他策略）
            if (data.length > 0) {
                headers = Object.keys(data[0]);
                rows = data.map(item => headers.map(header => item[header]));
            }
        }

        if (headers.length === 0) return;

        // 构建CSV内容
        const csvContent = [
            headers.join(','),
            ...rows.map(row => row.map(cell => {
                // 处理包含逗号、换行符或引号的单元格
                const cellStr = String(cell);
                if (cellStr.includes(',') || cellStr.includes('\n') || cellStr.includes('"')) {
                    return `"${cellStr.replace(/"/g, '""')}"`;
                }
                return cellStr;
            }).join(','))
        ].join('\n');

        // 添加 BOM 以支持 Excel 中文显示
        const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');

        if (navigator.msSaveBlob) { // IE 10+
            navigator.msSaveBlob(blob, filename);
        } else {
            const url = URL.createObjectURL(blob);
            link.setAttribute('href', url);
            link.setAttribute('download', filename);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }

        if (window.CommonUtils) {
            CommonUtils.showToast('导出成功', 'success');
        }
    }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    ScreeningPage.init();

    // 绑定一阳穿三线策略参数按钮事件
    const resetParamsBtn = document.getElementById('resetParamsBtn');
    const saveParamsBtn = document.getElementById('saveParamsBtn');

    if (resetParamsBtn) {
        resetParamsBtn.addEventListener('click', () => {
            ScreeningPage.resetOneYangThreeLinesParams();
        });
    }

    if (saveParamsBtn) {
        saveParamsBtn.addEventListener('click', () => {
            ScreeningPage.saveOneYangThreeLinesParams();
        });
    }

    // 加载保存的参数
    ScreeningPage.loadOneYangThreeLinesParams();
});


// 资讯页面功能模块
const NewsPage = {
    currentCategory: 'all',
    newsData: [],
    loadedCount: 6,
    totalCount: 20,
    API_BASE_URL: 'http://192.168.31.237:5000',

    // 初始化
    init() {
        this.bindEvents();
        this.loadNewsData();
        this.startAutoUpdate();
    },

    // 绑定事件
    bindEvents() {
        // 分类标签切换
        document.querySelectorAll('.category-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                this.switchCategory(tab.dataset.category);
                this.updateActiveTab(tab);
            });
        });

        // 头条新闻点击
        document.querySelector('.headline-card').addEventListener('click', () => {
            this.openNews('A股三大指数集体收涨 科技板块领涨');
        });

        // 新闻项点击
        document.addEventListener('click', (e) => {
            const newsItem = e.target.closest('.news-item');
            if (newsItem) {
                const title = newsItem.querySelector('h3').textContent;
                this.openNews(title);
            }
        });

        // 热门资讯点击
        document.addEventListener('click', (e) => {
            const hotItem = e.target.closest('.hot-news-item');
            if (hotItem) {
                const title = hotItem.querySelector('h4').textContent;
                this.openNews(title);
            }
        });

        // 公告速递点击
        document.addEventListener('click', (e) => {
            const announcementItem = e.target.closest('.announcement-item');
            if (announcementItem) {
                const stockName = announcementItem.querySelector('.stock-name').textContent;
                const type = announcementItem.querySelector('.announcement-type').textContent;
                this.openAnnouncement(stockName, type);
            }
        });

        // 热门话题点击
        document.addEventListener('click', (e) => {
            const topicItem = e.target.closest('.topic-item');
            if (topicItem) {
                const topic = topicItem.querySelector('.topic-tag').textContent;
                this.searchTopic(topic);
            }
        });

        // 市场日历点击
        document.addEventListener('click', (e) => {
            const calendarItem = e.target.closest('.calendar-item');
            if (calendarItem) {
                const event = calendarItem.querySelector('h4').textContent;
                this.showCalendarEvent(event);
            }
        });

        // 加载更多按钮
        document.querySelector('.load-more-btn').addEventListener('click', () => {
            this.loadMoreNews();
        });

        // 搜索功能
        this.bindSearchEvents();
    },

    // 绑定搜索事件
    bindSearchEvents() {
        const searchBtn = document.querySelector('.search-btn');
        const searchModal = document.getElementById('searchModal');
        const closeSearch = document.querySelector('.close-search');
        const searchInput = document.querySelector('.search-input');

        searchBtn.addEventListener('click', () => {
            searchModal.style.display = 'flex';
            searchInput.focus();
        });

        closeSearch.addEventListener('click', () => {
            searchModal.style.display = 'none';
            searchInput.value = '';
        });

        searchModal.addEventListener('click', (e) => {
            if (e.target === searchModal) {
                searchModal.style.display = 'none';
                searchInput.value = '';
            }
        });

        searchInput.addEventListener('input', (e) => {
            this.performSearch(e.target.value);
        });
    },

    // 切换分类
    switchCategory(category) {
        this.currentCategory = category;
        this.filterNews();
    },

    // 更新活动标签
    updateActiveTab(activeTab) {
        document.querySelectorAll('.category-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        activeTab.classList.add('active');
    },

    // 过滤新闻
    filterNews() {
        const newsItems = document.querySelectorAll('.news-item');
        
        newsItems.forEach(item => {
            const category = item.dataset.category;
            
            if (this.currentCategory === 'all' || category === this.currentCategory) {
                item.classList.remove('filtered');
            } else {
                item.classList.add('filtered');
            }
        });

        // 更新显示数量
        const visibleCount = document.querySelectorAll('.news-item:not(.filtered)').length;
        if (visibleCount === 0) {
            this.showNoResults();
        } else {
            this.hideNoResults();
        }
    },

    // 显示无结果提示
    showNoResults() {
        let noResults = document.querySelector('.no-results');
        if (!noResults) {
            noResults = document.createElement('div');
            noResults.className = 'no-results';
            noResults.innerHTML = `
                <div style="text-align: center; padding: 2rem; color: #6b7280;">
                    <div style="font-size: 3rem; margin-bottom: 1rem;">📰</div>
                    <h3>暂无相关资讯</h3>
                    <p>该分类下暂时没有新闻内容</p>
                </div>
            `;
            document.querySelector('.news-list').appendChild(noResults);
        }
        noResults.style.display = 'block';
    },

    // 隐藏无结果提示
    hideNoResults() {
        const noResults = document.querySelector('.no-results');
        if (noResults) {
            noResults.style.display = 'none';
        }
    },

    // 加载新闻数据
    loadNewsData() {
        // 新闻数据已在HTML中静态定义
        this.newsData = Array.from(document.querySelectorAll('.news-item')).map(item => ({
            title: item.querySelector('h3').textContent,
            summary: item.querySelector('.news-summary').textContent,
            category: item.dataset.category,
            source: item.querySelector('.source').textContent,
            time: item.querySelector('.time').textContent
        }));

        console.log('新闻数据已加载:', this.newsData.length, '条');
    },

    // 加载更多新闻
    loadMoreNews() {
        const loadMoreBtn = document.querySelector('.load-more-btn');
        
        // 显示加载状态
        loadMoreBtn.textContent = '加载中...';
        loadMoreBtn.disabled = true;

        // 模拟异步加载
        setTimeout(() => {
            const mockNews = this.generateMockNews(3);
            this.appendNews(mockNews);
            
            this.loadedCount += 3;
            
            // 恢复按钮状态
            loadMoreBtn.textContent = '加载更多资讯';
            loadMoreBtn.disabled = false;

            // 检查是否还有更多
            if (this.loadedCount >= this.totalCount) {
                loadMoreBtn.textContent = '没有更多资讯了';
                loadMoreBtn.disabled = true;
            }
        }, 1000);
    },

    // 生成模拟新闻
    generateMockNews(count) {
        const categories = ['market', 'policy', 'company', 'international', 'analysis'];
        const sources = ['财经日报', '证券时报', '第一财经', '财新网', '华尔街日报'];
        const mockTitles = [
            '新能源汽车产业迎来政策红利期',
            '科技股估值回归合理区间',
            '银行业数字化转型加速推进',
            '房地产市场政策边际松动',
            '消费板块业绩超预期增长',
            '人工智能技术商业化提速',
            '绿色金融发展迎来新机遇'
        ];

        const news = [];
        for (let i = 0; i < count; i++) {
            const category = categories[Math.floor(Math.random() * categories.length)];
            const source = sources[Math.floor(Math.random() * sources.length)];
            const title = mockTitles[Math.floor(Math.random() * mockTitles.length)];
            const time = `${Math.floor(Math.random() * 12) + 1}小时前`;
            
            news.push({
                category,
                title,
                summary: '这是一条模拟的新闻摘要，用于展示新闻内容的基本信息和关键要点...',
                source,
                time,
                views: `${(Math.random() * 5 + 1).toFixed(1)}万阅读`
            });
        }
        
        return news;
    },

    // 添加新闻到列表
    appendNews(newsArray) {
        const newsList = document.querySelector('.news-list');
        
        newsArray.forEach(news => {
            const newsItem = document.createElement('article');
            newsItem.className = 'news-item';
            newsItem.dataset.category = news.category;
            
            newsItem.innerHTML = `
                <div class="news-image">
                    <div class="placeholder-image">📰</div>
                </div>
                <div class="news-content">
                    <div class="news-header">
                        <h3>${news.title}</h3>
                        <span class="news-tag">${this.getCategoryName(news.category)}</span>
                    </div>
                    <p class="news-summary">${news.summary}</p>
                    <div class="news-meta">
                        <span class="source">${news.source}</span>
                        <span class="time">${news.time}</span>
                        <span class="category">${this.getCategoryName(news.category)}</span>
                        <span class="views">${news.views}</span>
                    </div>
                </div>
            `;
            
            newsList.appendChild(newsItem);
        });

        // 应用当前过滤器
        this.filterNews();
    },

    // 获取分类名称
    getCategoryName(category) {
        const categoryNames = {
            'market': '市场动态',
            'policy': '政策解读',
            'company': '公司资讯',
            'international': '国际财经',
            'analysis': '分析研判'
        };
        return categoryNames[category] || '其他';
    },

    // 打开新闻详情
    openNews(title) {
        CommonUtils.showToast(`查看新闻：${title}`, 'info');
        // 实际项目中这里会跳转到新闻详情页
    },

    // 打开公告详情
    openAnnouncement(stockName, type) {
        CommonUtils.showToast(`查看${stockName}的${type}`, 'info');
        // 实际项目中这里会跳转到公告详情页
    },

    // 搜索话题
    searchTopic(topic) {
        CommonUtils.showToast(`搜索话题：${topic}`, 'info');
        // 实际项目中这里会跳转到话题搜索页
    },

    // 显示日历事件
    showCalendarEvent(event) {
        CommonUtils.showToast(`查看事件：${event}`, 'info');
        // 实际项目中这里会显示事件详情
    },

    // 执行搜索
    performSearch(query) {
        if (!query.trim()) {
            document.querySelector('.search-results').innerHTML = '';
            return;
        }

        // 模拟搜索结果
        const results = this.newsData.filter(news => 
            news.title.includes(query) || 
            news.summary.includes(query)
        );

        this.renderSearchResults(results, query);
    },

    // 渲染搜索结果
    renderSearchResults(results, query) {
        const searchResults = document.querySelector('.search-results');
        
        if (results.length === 0) {
            searchResults.innerHTML = `
                <div style="padding: 1rem; text-align: center; color: #6b7280;">
                    <p>未找到与"${query}"相关的资讯</p>
                </div>
            `;
        } else {
            searchResults.innerHTML = `
                <div style="padding: 1rem; border-bottom: 1px solid #e2e8f0; color: #6b7280;">
                    找到 ${results.length} 条相关资讯
                </div>
                ${results.slice(0, 5).map(result => `
                    <div class="search-result-item" style="padding: 1rem; border-bottom: 1px solid #f3f4f6; cursor: pointer;">
                        <h4 style="font-size: 0.9rem; font-weight: 600; color: #1f2937; margin-bottom: 0.5rem;">${this.highlightQuery(result.title, query)}</h4>
                        <p style="font-size: 0.8rem; color: #6b7280; margin-bottom: 0.5rem;">${this.highlightQuery(result.summary.substring(0, 100) + '...', query)}</p>
                        <div style="font-size: 0.75rem; color: #9ca3af;">
                            <span>${result.source}</span>
                            <span style="margin-left: 1rem;">${result.time}</span>
                        </div>
                    </div>
                `).join('')}
            `;

            // 绑定搜索结果点击事件
            searchResults.querySelectorAll('.search-result-item').forEach((item, index) => {
                item.addEventListener('click', () => {
                    this.openNews(results[index].title);
                    document.getElementById('searchModal').style.display = 'none';
                });
            });
        }
    },

    // 高亮搜索关键词
    highlightQuery(text, query) {
        if (!query) return text;
        const regex = new RegExp(`(${query})`, 'gi');
        return text.replace(regex, '<mark style="background: #fef3c7; padding: 0 0.25rem;">$1</mark>');
    },

    // 开始自动更新
    startAutoUpdate() {
        // 定期更新时间显示
        setInterval(() => {
            this.updateTimeDisplays();
        }, 60000); // 每分钟更新一次

        // 定期更新热门资讯阅读量
        setInterval(() => {
            this.updateHotNewsViews();
        }, 30000); // 每30秒更新一次

        // 定期更新话题热度
        setInterval(() => {
            this.updateTopicHeat();
        }, 45000); // 每45秒更新一次
    },

    // 更新时间显示
    updateTimeDisplays() {
        const timeElements = document.querySelectorAll('.time');
        timeElements.forEach(element => {
            const currentTime = element.textContent;
            if (currentTime.includes('分钟前')) {
                const minutes = parseInt(currentTime.match(/\d+/)[0]);
                if (minutes < 59) {
                    element.textContent = `${minutes + 1}分钟前`;
                } else {
                    element.textContent = '1小时前';
                }
            } else if (currentTime.includes('小时前')) {
                const hours = parseInt(currentTime.match(/\d+/)[0]);
                element.textContent = `${hours}小时前`;
            }
        });
    },

    // 更新热门资讯阅读量
    updateHotNewsViews() {
        const viewElements = document.querySelectorAll('.hot-content .views');
        viewElements.forEach(element => {
            const currentViews = parseFloat(element.textContent.replace(/[万阅读]/g, ''));
            const newViews = (currentViews + Math.random() * 0.5).toFixed(1);
            element.textContent = `${newViews}万阅读`;
        });
    },

    // 更新话题热度
    updateTopicHeat() {
        const heatElements = document.querySelectorAll('.topic-heat');
        heatElements.forEach(element => {
            const currentHeat = parseFloat(element.textContent.replace(/[🔥热度万]/g, ''));
            const change = (Math.random() - 0.5) * 1;
            const newHeat = Math.max(1, currentHeat + change).toFixed(1);
            element.textContent = `🔥 热度 ${newHeat}万`;
        });
    }
};

// DOM加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    NewsPage.init();
}); 
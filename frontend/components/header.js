// 动态加载header.html并处理登录状态
async function loadHeader(activePage) {
    console.log('开始加载header，当前页面:', activePage);
    
    const headerContainer = document.createElement('div');
    const resp = await fetch('components/header.html');
    headerContainer.innerHTML = await resp.text();
    document.body.prepend(headerContainer);

    console.log('Header HTML已加载到页面');

    // 高亮当前频道
    if (activePage) {
        const nav = document.getElementById('nav-' + activePage);
        if (nav) {
            nav.classList.add('active');
            console.log('导航高亮设置完成:', activePage);
        }
    }

    // 延迟初始化用户菜单，确保DOM完全加载
    setTimeout(() => {
        console.log('开始初始化用户菜单...');
        initUserMenu();
    }, 100);
    
    // 延迟初始化股票搜索功能
    setTimeout(() => {
        console.log('开始初始化股票搜索功能...');
        initStockSearch();
    }, 100);
    
    // 如果CommonUtils已经加载，让它重新初始化用户显示
    if (window.CommonUtils && window.CommonUtils.auth) {
        setTimeout(() => {
            console.log('CommonUtils已加载，更新用户显示...');
            CommonUtils.auth.updateUserDisplay(CommonUtils.auth.getUserInfo());
        }, 200);
    }
}

// 初始化用户菜单
function initUserMenu() {
    console.log('=== 开始初始化用户菜单 ===');
    
    const userMenu = document.getElementById('userMenu');
    const userStatus = document.getElementById('userStatus');
    const userDropdown = document.getElementById('userDropdown');
    const menuLogout = document.getElementById('menuLogout');
    const menuChangePassword = document.getElementById('menuChangePassword');
    
    console.log('DOM元素检查:');
    console.log('- userMenu:', userMenu);
    console.log('- userStatus:', userStatus);
    console.log('- userDropdown:', userDropdown);
    console.log('- menuLogout:', menuLogout);
    
    if (!userMenu || !userStatus) {
        console.error('❌ 用户菜单元素未找到');
        return;
    }
    
    // 检查登录状态
    const accessToken = localStorage.getItem('access_token');
    const userInfo = localStorage.getItem('userInfo');
    
    console.log('登录状态检查:');
    console.log('- accessToken:', accessToken ? '存在' : '不存在');
    console.log('- userInfo:', userInfo ? '存在' : '不存在');
    
    if (accessToken && userInfo) {
        try {
            const user = JSON.parse(userInfo);
            console.log('用户信息:', user);
            
            userStatus.textContent = user.username || '已登录';
            userMenu.style.cursor = 'pointer';
            
            console.log('✅ 用户状态已设置:', userStatus.textContent);
            
            // 绑定用户菜单点击事件
            userMenu.addEventListener('click', function(e) {
                console.log('🎯 用户菜单被点击');
                e.stopPropagation();
                toggleUserDropdown();
            });
            
            // 点击其他地方关闭菜单
            document.addEventListener('click', function(e) {
                if (!userMenu.contains(e.target)) {
                    console.log('🖱️ 点击外部区域，关闭菜单');
                    closeUserDropdown();
                }
            });
            
            // 绑定“修改密码”事件
            if (menuChangePassword) {
                menuChangePassword.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    openChangePasswordModal();
                });
            }

            // 绑定退出登录事件
            if (menuLogout) {
                menuLogout.addEventListener('click', function(e) {
                    console.log('🚪 退出登录被点击');
                    e.preventDefault();
                    e.stopPropagation();
                    handleLogout();
                });
            }
            
            console.log('✅ 用户菜单初始化成功');
        } catch (error) {
            console.error('❌ 解析用户信息失败:', error);
            setLoggedOutState();
        }
    } else {
        console.log('用户未登录，设置未登录状态');
        setLoggedOutState();
    }
    
    console.log('=== 用户菜单初始化完成 ===');
}

// 切换用户下拉菜单
function toggleUserDropdown() {
    const userMenu = document.getElementById('userMenu');
    const userDropdown = document.getElementById('userDropdown');
    
    if (userMenu && userDropdown) {
        const isOpen = userMenu.classList.contains('open');
        
        if (isOpen) {
            closeUserDropdown();
        } else {
            openUserDropdown();
        }
    }
}

// 打开用户下拉菜单
function openUserDropdown() {
    const userMenu = document.getElementById('userMenu');
    const userDropdown = document.getElementById('userDropdown');
    
    if (userMenu && userDropdown) {
        userMenu.classList.add('open');
        
        // 强制设置所有必要的样式，确保菜单可见
        userDropdown.style.cssText = `
            display: flex !important;
            position: absolute !important;
            right: 0 !important;
            top: 120% !important;
            background: #fff !important;
            color: #222 !important;
            min-width: 120px !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
            border-radius: 6px !important;
            z-index: 9999 !important;
            flex-direction: column !important;
            padding: 6px 0 !important;
            border: 1px solid #e0e0e0 !important;
            visibility: visible !important;
            opacity: 1 !important;
            height: auto !important;
            width: auto !important;
            overflow: visible !important;
        `;
        
        // 确保父元素也有正确的定位
        userMenu.style.position = 'relative';
        userMenu.style.zIndex = '9998';
        
        console.log('用户菜单已打开');
        console.log('用户菜单状态:', userMenu.classList.contains('open'));
        console.log('下拉菜单显示状态:', userDropdown.style.display);
        console.log('下拉菜单z-index:', userDropdown.style.zIndex);
        console.log('下拉菜单位置:', userDropdown.style.position);
        
        // 添加调试信息
        console.log('下拉菜单计算样式:', window.getComputedStyle(userDropdown));
    } else {
        console.error('用户菜单元素未找到:', { userMenu: !!userMenu, userDropdown: !!userDropdown });
    }
}

// 关闭用户下拉菜单
function closeUserDropdown() {
    const userMenu = document.getElementById('userMenu');
    const userDropdown = document.getElementById('userDropdown');
    
    if (userMenu && userDropdown) {
        userMenu.classList.remove('open');
        
        // 强制隐藏下拉菜单
        userDropdown.style.cssText = `
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
        `;
        
        console.log('用户菜单已关闭');
        console.log('用户菜单状态:', userMenu.classList.contains('open'));
        console.log('下拉菜单显示状态:', userDropdown.style.display);
    } else {
        console.error('用户菜单元素未找到:', { userMenu: !!userMenu, userDropdown: !!userDropdown });
    }
}

// 处理退出登录
function handleLogout() {
    console.log('开始退出登录...');
    
    // 使用CommonUtils的logout函数
    if (window.CommonUtils && window.CommonUtils.auth) {
        CommonUtils.auth.logout();
    } else {
        // 备用方案
        console.log('使用备用退出登录方案');
        localStorage.removeItem('access_token');
        localStorage.removeItem('userInfo');
        localStorage.removeItem('token');
        localStorage.removeItem('adminLoggedIn');
        localStorage.removeItem('adminData');
        localStorage.removeItem('admin_token');
        
        // 显示退出成功消息
        showToast('已安全退出', 'success');
        
        // 直接跳转到登录页面
        window.location.href = 'login.html';
    }
}

// 设置未登录状态
function setLoggedOutState() {
    const userStatus = document.getElementById('userStatus');
    const userMenu = document.getElementById('userMenu');
    const userDropdown = document.getElementById('userDropdown');
    
    if (userStatus) {
        userStatus.textContent = '未登录';
    }
    
    if (userMenu) {
        userMenu.style.cursor = 'default';
        userMenu.classList.remove('open');
    }
    
    if (userDropdown) {
        userDropdown.style.display = 'none';
    }
}

// 显示Toast消息
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        background: ${type === 'success' ? '#16a34a' : type === 'error' ? '#dc2626' : '#2563eb'};
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 6px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 9999;
        animation: slideIn 0.3s ease;
    `;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => {
            if (toast.parentNode) {
                document.body.removeChild(toast);
            }
        }, 300);
    }, 3000);
}

// 添加动画样式
if (!document.querySelector('#header-animations')) {
    const style = document.createElement('style');
    style.id = 'header-animations';
    style.textContent = `
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOut {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }
    `;
    document.head.appendChild(style);
}

// 导出函数供外部使用
window.initUserMenu = initUserMenu;
window.toggleUserDropdown = toggleUserDropdown;
window.openUserDropdown = openUserDropdown;
window.closeUserDropdown = closeUserDropdown;
window.handleLogout = handleLogout; 

// ===== 修改密码弹窗逻辑 =====
function getChangePasswordElements() {
    return {
        modal: document.getElementById('changePasswordModal'),
        form: document.getElementById('changePasswordForm'),
        oldInput: document.getElementById('oldPassword'),
        newInput: document.getElementById('newPassword'),
        confirmInput: document.getElementById('confirmPassword'),
        cancelBtn: document.getElementById('cpCancelBtn'),
        submitBtn: document.getElementById('cpSubmitBtn')
    };
}

function openChangePasswordModal() {
    const { modal, cancelBtn, submitBtn } = getChangePasswordElements();
    if (!modal) return;
    modal.style.display = 'flex';
    // 绑定一次性事件
    if (cancelBtn) cancelBtn.onclick = closeChangePasswordModal;
    if (submitBtn) submitBtn.onclick = submitChangePassword;
    // 点击遮罩关闭
    modal.onclick = (e) => {
        if (e.target === modal) closeChangePasswordModal();
    };
}

function closeChangePasswordModal() {
    const { modal, form } = getChangePasswordElements();
    if (!modal) return;
    modal.style.display = 'none';
    if (form) form.reset();
}

function validateChangePassword(oldPwd, newPwd, confirmPwd) {
    if (!oldPwd || !newPwd || !confirmPwd) {
        showToast('请完整填写所有字段', 'error');
        return false;
    }
    if (newPwd.length < 6) {
        showToast('新密码至少需要6位', 'error');
        return false;
    }
    if (newPwd === oldPwd) {
        showToast('新密码不能与旧密码相同', 'error');
        return false;
    }
    if (newPwd !== confirmPwd) {
        showToast('两次输入的新密码不一致', 'error');
        return false;
    }
    return true;
}

async function submitChangePassword() {
    const { oldInput, newInput, confirmInput, submitBtn } = getChangePasswordElements();
    const oldPwd = oldInput ? oldInput.value.trim() : '';
    const newPwd = newInput ? newInput.value.trim() : '';
    const confirmPwd = confirmInput ? confirmInput.value.trim() : '';

    if (!validateChangePassword(oldPwd, newPwd, confirmPwd)) return;

    // 禁用按钮避免重复提交
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = '提交中...';
    }

    try {
        const baseUrl = (typeof API_BASE_URL !== 'undefined' && API_BASE_URL) ? API_BASE_URL : '';
        // 后端实际接口：PUT /api/users/me/password（查询参数 old_password/new_password）
        const url = `${baseUrl}/api/users/me/password?old_password=${encodeURIComponent(oldPwd)}&new_password=${encodeURIComponent(newPwd)}`;

        const reqInit = {
            method: 'PUT'
        };

        // 优先使用带自动401处理的 authFetch
        const resp = (typeof authFetch === 'function')
            ? await authFetch(url, reqInit)
            : await fetch(url, {
                ...reqInit,
                headers: {
                    Authorization: `Bearer ${localStorage.getItem('access_token') || ''}`
                }
            });

        const data = await resp.json().catch(() => ({}));
        if (resp.ok || data.success) {
            showToast('密码修改成功', 'success');
            closeChangePasswordModal();
        } else {
            const msg = data.message || '密码修改失败';
            showToast(msg, 'error');
        }
    } catch (err) {
        console.error('修改密码请求失败:', err);
        showToast('网络错误，请稍后重试', 'error');
    } finally {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = '确定';
        }
    }
}

// 导出弹窗相关函数（可用于调试）
window.openChangePasswordModal = openChangePasswordModal;
window.closeChangePasswordModal = closeChangePasswordModal;

// ===== 股票搜索功能逻辑 =====
let searchTimeout = null;
let currentHighlightIndex = -1;
let currentSearchResults = [];

// 初始化股票搜索功能
function initStockSearch() {
    console.log('=== 开始初始化股票搜索功能 ===');
    
    const searchBtn = document.querySelector('.search-btn');
    const searchModal = document.getElementById('stockSearchModal');
    const searchInput = document.getElementById('stockSearchInput');
    const searchCloseBtn = document.getElementById('stockSearchCloseBtn');
    const searchClearBtn = document.getElementById('stockSearchClearBtn');
    const searchResults = document.getElementById('stockSearchResults');
    
    if (!searchBtn || !searchModal || !searchInput) {
        console.error('❌ 搜索相关元素未找到');
        return;
    }
    
    // 绑定搜索按钮点击事件
    searchBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        openStockSearchModal();
    });
    
    // 确保模态框初始状态是隐藏的
    if (searchModal) {
        searchModal.style.display = 'none';
    }
    
    // 绑定关闭按钮事件
    if (searchCloseBtn) {
        searchCloseBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            closeStockSearchModal();
        });
    }
    
    // 绑定清除按钮事件
    if (searchClearBtn) {
        searchClearBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            searchInput.value = '';
            searchInput.focus();
            searchClearBtn.style.display = 'none';
            renderSearchResults([]);
        });
    }
    
    // 绑定输入框输入事件（防抖）
    searchInput.addEventListener('input', function(e) {
        const keyword = e.target.value.trim();
        
        // 显示/隐藏清除按钮
        if (searchClearBtn) {
            searchClearBtn.style.display = keyword ? 'flex' : 'none';
        }
        
        // 清除之前的定时器
        if (searchTimeout) {
            clearTimeout(searchTimeout);
        }
        
        // 如果关键词为空，显示空状态
        if (!keyword) {
            renderSearchResults([]);
            currentHighlightIndex = -1;
            return;
        }
        
        // 防抖处理，300ms后执行搜索
        searchTimeout = setTimeout(() => {
            performStockSearch(keyword);
        }, 300);
    });
    
    // 绑定键盘事件
    searchInput.addEventListener('keydown', function(e) {
        handleSearchKeydown(e);
    });
    
    // 点击遮罩关闭模态框（注意：不要点击模态框内容区域关闭）
    if (searchModal) {
        searchModal.addEventListener('click', function(e) {
            // 只有点击遮罩层本身（不是子元素）时才关闭
            if (e.target === searchModal) {
                closeStockSearchModal();
            }
        });
    }
    
    // 阻止模态框内容区域的点击事件冒泡到遮罩层
    const modalContent = searchModal ? searchModal.querySelector('.stock-search-modal-content') : null;
    if (modalContent) {
        modalContent.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    }
    
    console.log('✅ 股票搜索功能初始化完成');
}

// 打开股票搜索模态框
function openStockSearchModal() {
    const searchModal = document.getElementById('stockSearchModal');
    const searchInput = document.getElementById('stockSearchInput');
    
    if (searchModal && searchInput) {
        // 显示模态框
        searchModal.style.display = 'flex';
        searchModal.style.visibility = 'visible';
        
        searchInput.value = '';
        // 延迟聚焦，确保模态框完全显示后再聚焦
        setTimeout(() => {
            searchInput.focus();
        }, 100);
        
        currentHighlightIndex = -1;
        currentSearchResults = [];
        renderSearchResults([]);
        
        // 隐藏清除按钮
        const searchClearBtn = document.getElementById('stockSearchClearBtn');
        if (searchClearBtn) {
            searchClearBtn.style.display = 'none';
        }
        
        console.log('股票搜索模态框已打开');
    }
}

// 关闭股票搜索模态框
function closeStockSearchModal() {
    const searchModal = document.getElementById('stockSearchModal');
    const searchInput = document.getElementById('stockSearchInput');
    const searchClearBtn = document.getElementById('stockSearchClearBtn');
    
    if (searchModal) {
        // 强制隐藏模态框
        searchModal.style.display = 'none';
        searchModal.style.visibility = 'hidden';
        
        if (searchInput) {
            searchInput.value = '';
            searchInput.blur(); // 移除焦点
        }
        
        if (searchClearBtn) {
            searchClearBtn.style.display = 'none';
        }
        
        currentHighlightIndex = -1;
        currentSearchResults = [];
        
        // 清除搜索定时器
        if (searchTimeout) {
            clearTimeout(searchTimeout);
            searchTimeout = null;
        }
        
        console.log('股票搜索模态框已关闭');
    }
}

// 执行股票搜索
async function performStockSearch(keyword) {
    if (!keyword) {
        renderSearchResults([]);
        return;
    }
    
    const searchResults = document.getElementById('stockSearchResults');
    if (searchResults) {
        searchResults.innerHTML = '<div class="stock-search-loading">搜索中...</div>';
    }
    
    try {
        // 优先使用localStorage缓存
        const cached = localStorage.getItem('stockBasicInfo');
        let results = [];
        
        if (cached) {
            // 使用本地缓存搜索
            const stocks = JSON.parse(cached);
            const lowerKeyword = keyword.toLowerCase();
            results = stocks.filter(stock => {
                const code = String(stock.code).toLowerCase();
                const name = stock.name ? stock.name.toLowerCase() : '';
                return code.includes(lowerKeyword) || name.includes(lowerKeyword);
            }).slice(0, 20);
            
            console.log(`从本地缓存搜索到 ${results.length} 条结果`);
        } else {
            // 降级：调用API搜索
            const API_BASE_URL = (typeof window.API_BASE_URL !== 'undefined' && window.API_BASE_URL) 
                ? window.API_BASE_URL 
                : (typeof Config !== 'undefined' && Config.getApiBaseUrl) 
                    ? Config.getApiBaseUrl() 
                    : '';
            
            const url = `${API_BASE_URL}/api/stock/list?query=${encodeURIComponent(keyword)}&limit=20`;
            const response = await fetch(url);
            const data = await response.json();
            
            if (data.success && data.data) {
                results = data.data;
                console.log(`从API搜索到 ${results.length} 条结果`);
            } else {
                console.error('搜索API返回错误:', data);
            }
        }
        
        currentSearchResults = results;
        currentHighlightIndex = -1;
        renderSearchResults(results);
        
    } catch (error) {
        console.error('搜索失败:', error);
        if (searchResults) {
            searchResults.innerHTML = '<div class="stock-search-empty">搜索失败，请稍后重试</div>';
        }
    }
}

// 渲染搜索结果
function renderSearchResults(results) {
    const searchResults = document.getElementById('stockSearchResults');
    if (!searchResults) return;
    
    if (results.length === 0) {
        searchResults.innerHTML = '<div class="stock-search-empty">未找到相关股票</div>';
        return;
    }
    
    const html = results.map((stock, index) => {
        const code = stock.code || '';
        const name = stock.name || '';
        return `
            <div class="stock-search-result-item" data-index="${index}" data-code="${code}" data-name="${encodeURIComponent(name)}">
                <span class="stock-search-result-icon">📊</span>
                <div class="stock-search-result-info">
                    <span class="stock-search-result-code">${code}</span>
                    <span class="stock-search-result-name">${name}</span>
                </div>
            </div>
        `;
    }).join('');
    
    searchResults.innerHTML = html;
    
    // 绑定点击事件
    const resultItems = searchResults.querySelectorAll('.stock-search-result-item');
    resultItems.forEach((item, index) => {
        item.addEventListener('click', function() {
            const code = this.getAttribute('data-code');
            const name = decodeURIComponent(this.getAttribute('data-name') || '');
            navigateToStock(code, name);
        });
    });
    
    // 更新高亮
    updateHighlight();
}

// 处理键盘事件
function handleSearchKeydown(e) {
    const { key } = e;
    
    switch (key) {
        case 'Escape':
            e.preventDefault();
            closeStockSearchModal();
            break;
            
        case 'ArrowDown':
            e.preventDefault();
            if (currentHighlightIndex < currentSearchResults.length - 1) {
                currentHighlightIndex++;
                updateHighlight();
            }
            break;
            
        case 'ArrowUp':
            e.preventDefault();
            if (currentHighlightIndex > 0) {
                currentHighlightIndex--;
                updateHighlight();
            }
            break;
            
        case 'Enter':
            e.preventDefault();
            if (currentHighlightIndex >= 0 && currentHighlightIndex < currentSearchResults.length) {
                const stock = currentSearchResults[currentHighlightIndex];
                navigateToStock(stock.code, stock.name);
            } else if (currentSearchResults.length > 0) {
                // 如果没有高亮，选择第一个结果
                const stock = currentSearchResults[0];
                navigateToStock(stock.code, stock.name);
            }
            break;
    }
}

// 更新高亮状态
function updateHighlight() {
    const searchResults = document.getElementById('stockSearchResults');
    if (!searchResults) return;
    
    const items = searchResults.querySelectorAll('.stock-search-result-item');
    items.forEach((item, index) => {
        if (index === currentHighlightIndex) {
            item.classList.add('highlight');
            // 滚动到可见区域
            item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        } else {
            item.classList.remove('highlight');
        }
    });
}

// 跳转到股票详情页
function navigateToStock(code, name) {
    if (!code) return;
    
    const encodedName = encodeURIComponent(name || '');
    const url = `stock.html?code=${code}&name=${encodedName}`;
    window.location.href = url;
}

// 导出搜索相关函数
window.openStockSearchModal = openStockSearchModal;
window.closeStockSearchModal = closeStockSearchModal;
window.initStockSearch = initStockSearch;
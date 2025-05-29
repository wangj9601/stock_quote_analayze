// 动态加载header.html并处理登录状态
async function loadHeader(activePage) {
    const headerContainer = document.createElement('div');
    const resp = await fetch('components/header.html');
    headerContainer.innerHTML = await resp.text();
    document.body.prepend(headerContainer);

    // 高亮当前频道
    if (activePage) {
        const nav = document.getElementById('nav-' + activePage);
        if (nav) nav.classList.add('active');
    }

    // 登录状态处理
    updateUserStatus();
}

function updateUserStatus() {
    const userStatus = document.getElementById('userStatus');
    const userMenu = document.getElementById('userMenu');
    const userDropdown = document.getElementById('userDropdown');
    const menuLogout = document.getElementById('menuLogout');
    const userInfo = localStorage.getItem('userInfo');
    if (userInfo) {
        const user = JSON.parse(userInfo);
        userStatus.textContent = user.username || '已登录';
        userMenu.style.cursor = 'pointer';
        // 先解绑再绑定，防止多次绑定
        userMenu.onclick = null;
        if (menuLogout) menuLogout.onclick = null;
        document.body.onclick = null;
        // 下拉菜单交互
        userMenu.onclick = function(e) {
            e.stopPropagation();
            userMenu.classList.toggle('open');
        };
        document.body.addEventListener('click', function() {
            userMenu.classList.remove('open');
        });
        // 退出登录
        if (menuLogout) {
            menuLogout.onclick = function(e) {
                e.preventDefault();
                localStorage.removeItem('token');
                localStorage.removeItem('userInfo');
                location.reload();
            };
        }
    } else {
        userStatus.textContent = '未登录';
        if (userDropdown) userDropdown.style.display = 'none';
    }
} 
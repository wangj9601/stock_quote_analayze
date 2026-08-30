/**
 * 页面顶底滚动浮动按钮（个股详情等长页复用）
 * 靠近底部显示 Top，其余显示 Bottom；点击平滑滚动。
 */
(function (global) {
    function scrollMetrics() {
        const doc = document.documentElement;
        const body = document.body;
        const scrollTop =
            window.pageYOffset ||
            (doc && doc.scrollTop) ||
            (body && body.scrollTop) ||
            0;
        const viewport = window.innerHeight || (doc && doc.clientHeight) || 0;
        const scrollHeight = Math.max(
            doc ? doc.scrollHeight : 0,
            body ? body.scrollHeight : 0,
            doc ? doc.offsetHeight : 0,
            body ? body.offsetHeight : 0
        );
        return { scrollTop, viewport, scrollHeight };
    }

    function sync(btn) {
        if (!btn) return;
        const { scrollTop, viewport, scrollHeight } = scrollMetrics();
        const nearBottom = scrollTop + viewport >= scrollHeight - 80;
        const mode = nearBottom ? 'top' : 'bottom';
        btn.dataset.mode = mode;
        if (mode === 'top') {
            btn.textContent = 'Top';
            btn.title = '回到顶部';
            btn.setAttribute('aria-label', '回到顶部');
        } else {
            btn.textContent = 'Bottom';
            btn.title = '直达底部';
            btn.setAttribute('aria-label', '直达底部');
        }
    }

    function onClick(btn) {
        const mode = (btn && btn.dataset.mode) || 'bottom';
        if (mode === 'top') {
            window.scrollTo({ top: 0, left: 0, behavior: 'smooth' });
        } else {
            const { scrollHeight } = scrollMetrics();
            window.scrollTo({ top: scrollHeight, left: 0, behavior: 'smooth' });
        }
        window.setTimeout(() => sync(btn), 350);
    }

    /**
     * @param {{ btnId?: string }} [opts]
     */
    function bind(opts) {
        const btnId = (opts && opts.btnId) || 'stockScrollToggleBtn';
        const btn = document.getElementById(btnId);
        if (!btn || btn.dataset.bound === '1') return false;
        btn.dataset.bound = '1';
        btn.addEventListener('click', () => onClick(btn));
        const doSync = () => sync(btn);
        window.addEventListener('scroll', doSync, { passive: true });
        window.addEventListener('resize', doSync, { passive: true });
        doSync();
        return true;
    }

    global.PageScrollFab = { bind, sync, scrollMetrics };
})(typeof window !== 'undefined' ? window : globalThis);

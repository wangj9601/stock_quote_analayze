/**
 * 页面顶底滚动浮动按钮
 *
 * 单按钮模式（个股详情等）：靠近底部显示 Top，其余 Bottom。
 * 双按钮模式（选股长页）：独立「回顶 / 去底」，按滚动位置显隐（业界 BackTop 常见做法）。
 *
 * bind({ btnId, fabId?, rich?, onlyWhenScrollable?, nearBottomPx? })
 * bindDual({ fabId, topBtnId, bottomBtnId, showTopAfterPx?, nearBottomPx?, onlyWhenScrollable? })
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

    function applyRichLabel(btn, mode) {
        const iconEl = btn.querySelector('[data-fab-icon]');
        const textEl = btn.querySelector('[data-fab-text]');
        if (mode === 'top') {
            if (iconEl) iconEl.textContent = '↑';
            if (textEl) textEl.textContent = '顶部';
            btn.title = '回到顶部';
            btn.setAttribute('aria-label', '回到顶部');
        } else {
            if (iconEl) iconEl.textContent = '↓';
            if (textEl) textEl.textContent = '底部';
            btn.title = '直达底部';
            btn.setAttribute('aria-label', '直达底部');
        }
    }

    function applyPlainLabel(btn, mode) {
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

    function sync(btn, opts) {
        if (!btn) return;
        const o = opts || btn._scrollFabOpts || {};
        const { scrollTop, viewport, scrollHeight } = scrollMetrics();
        const threshold = typeof o.nearBottomPx === 'number' ? o.nearBottomPx : 80;
        const nearBottom = scrollTop + viewport >= scrollHeight - threshold;
        const mode = nearBottom ? 'top' : 'bottom';
        const prev = btn.dataset.mode;
        btn.dataset.mode = mode;
        btn.classList.toggle('is-top', mode === 'top');
        btn.classList.toggle('is-bottom', mode === 'bottom');

        if (o.rich || btn.dataset.rich === '1') {
            applyRichLabel(btn, mode);
            if (prev && prev !== mode) {
                btn.classList.remove('fab-mode-flash');
                void btn.offsetWidth;
                btn.classList.add('fab-mode-flash');
            }
        } else {
            applyPlainLabel(btn, mode);
        }

        if (o.onlyWhenScrollable) {
            const canScroll = scrollHeight > viewport + 120;
            const fab =
                (o.fabId && document.getElementById(o.fabId)) ||
                (btn.closest && btn.closest('[data-scroll-fab]')) ||
                null;
            if (fab) {
                fab.classList.toggle('is-scrollable', canScroll);
            }
            btn.disabled = !canScroll;
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

    function bind(opts) {
        const o = opts || {};
        const btnId = o.btnId || 'stockScrollToggleBtn';
        const btn = document.getElementById(btnId);
        if (!btn || btn.dataset.bound === '1') return false;
        btn.dataset.bound = '1';
        if (o.rich) btn.dataset.rich = '1';
        btn._scrollFabOpts = o;
        btn.addEventListener('click', () => onClick(btn));
        const doSync = () => sync(btn, o);
        window.addEventListener('scroll', doSync, { passive: true });
        window.addEventListener('resize', doSync, { passive: true });
        doSync();
        return true;
    }

    /**
     * 双按钮：回顶 / 去底独立显隐（Ant Design BackTop + 对称去底）。
     */
    function syncDual(opts) {
        const o = opts || {};
        const fab = o.fabId ? document.getElementById(o.fabId) : null;
        const topBtn = o.topBtnId ? document.getElementById(o.topBtnId) : null;
        const bottomBtn = o.bottomBtnId ? document.getElementById(o.bottomBtnId) : null;
        if (!fab || (!topBtn && !bottomBtn)) return;

        const { scrollTop, viewport, scrollHeight } = scrollMetrics();
        const showTopAfter =
            typeof o.showTopAfterPx === 'number' ? o.showTopAfterPx : 240;
        const nearBottomPx =
            typeof o.nearBottomPx === 'number' ? o.nearBottomPx : 120;
        const canScroll = scrollHeight > viewport + 120;
        const nearTop = scrollTop <= 24;
        const nearBottom = scrollTop + viewport >= scrollHeight - nearBottomPx;
        const showTop = canScroll && scrollTop >= showTopAfter;
        const showBottom = canScroll && !nearBottom;

        fab.classList.toggle('is-scrollable', canScroll);
        fab.classList.toggle('has-top', showTop);
        fab.classList.toggle('has-bottom', showBottom);
        fab.classList.toggle('is-near-top', nearTop);
        fab.classList.toggle('is-near-bottom', nearBottom);

        if (topBtn) {
            topBtn.classList.toggle('is-active', showTop);
            topBtn.disabled = !showTop;
            topBtn.setAttribute('aria-hidden', showTop ? 'false' : 'true');
            topBtn.tabIndex = showTop ? 0 : -1;
        }
        if (bottomBtn) {
            bottomBtn.classList.toggle('is-active', showBottom);
            bottomBtn.disabled = !showBottom;
            bottomBtn.setAttribute('aria-hidden', showBottom ? 'false' : 'true');
            bottomBtn.tabIndex = showBottom ? 0 : -1;
        }
    }

    function bindDual(opts) {
        const o = opts || {};
        const fab = o.fabId ? document.getElementById(o.fabId) : null;
        const topBtn = o.topBtnId ? document.getElementById(o.topBtnId) : null;
        const bottomBtn = o.bottomBtnId ? document.getElementById(o.bottomBtnId) : null;
        if (!fab || fab.dataset.dualBound === '1') return false;
        if (!topBtn && !bottomBtn) return false;

        fab.dataset.dualBound = '1';
        fab._scrollFabDualOpts = o;

        if (topBtn && topBtn.dataset.bound !== '1') {
            topBtn.dataset.bound = '1';
            topBtn.addEventListener('click', () => {
                window.scrollTo({ top: 0, left: 0, behavior: 'smooth' });
                window.setTimeout(() => syncDual(o), 380);
            });
        }
        if (bottomBtn && bottomBtn.dataset.bound !== '1') {
            bottomBtn.dataset.bound = '1';
            bottomBtn.addEventListener('click', () => {
                const { scrollHeight } = scrollMetrics();
                window.scrollTo({ top: scrollHeight, left: 0, behavior: 'smooth' });
                window.setTimeout(() => syncDual(o), 380);
            });
        }

        const doSync = () => syncDual(o);
        window.addEventListener('scroll', doSync, { passive: true });
        window.addEventListener('resize', doSync, { passive: true });
        doSync();
        return true;
    }

    function setVisible(fabId, visible) {
        const fab = document.getElementById(fabId);
        if (!fab) return;
        const on = !!visible;
        fab.hidden = false;
        fab.classList.toggle('is-visible', on);
        fab.setAttribute('aria-hidden', on ? 'false' : 'true');
        if (on) {
            if (fab._scrollFabDualOpts) {
                syncDual(fab._scrollFabDualOpts);
            } else {
                const btn = fab.querySelector('button[data-bound="1"], button');
                if (btn) sync(btn, btn._scrollFabOpts);
            }
        }
    }

    global.PageScrollFab = {
        bind,
        bindDual,
        sync,
        syncDual,
        scrollMetrics,
        setVisible,
    };
})(typeof window !== 'undefined' ? window : globalThis);

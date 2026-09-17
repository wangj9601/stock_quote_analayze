/**
 * 独立板块详情页：board_detail.html?board_kind=&board_code=&board_name=&board_code_source=
 * 复用 MarketsPage.showSectorDetail 渲染逻辑，整页展示（非行情中心弹层）。
 */
(function () {
    function parseQuery() {
        try {
            return new URLSearchParams(window.location.search || '');
        } catch (e) {
            return new URLSearchParams();
        }
    }

    function kindFromQuery(q) {
        return String(q.get('board_kind') || '').trim().toLowerCase() === 'concept'
            ? 'concept'
            : 'industry';
    }

    function marketsListHref(kind) {
        // 行业 → sectors，概念 → concepts
        const tab = kind === 'concept' ? 'concepts' : 'sectors';
        return `markets.html#${tab}`;
    }

    async function boot() {
        const q = parseQuery();
        const code = String(q.get('board_code') || '').trim();
        const kind = kindFromQuery(q);
        const name = String(q.get('board_name') || '').trim();
        const source = String(q.get('board_code_source') || 'tonghuashun').trim() || 'tonghuashun';

        const back = document.getElementById('boardDetailBackLink');
        const closeBtn = document.getElementById('closeSectorDetailBtn');
        const listHref = marketsListHref(kind);
        if (back) back.setAttribute('href', listHref);
        if (closeBtn) closeBtn.setAttribute('href', listHref);

        document.title = (name || code || '板块详情') + ' - 股票分析';

        // markets.js 使用 const MarketsPage，不会自动挂到 window；勿仅用 window.MarketsPage 判断
        const page =
            (typeof MarketsPage !== 'undefined' && MarketsPage)
            || (typeof window !== 'undefined' && window.MarketsPage)
            || null;
        if (!page || typeof page.showSectorDetail !== 'function') {
            const body = document.getElementById('sectorDetailBody');
            if (body) body.innerHTML = '<div class="sector-detail-error">详情模块未加载</div>';
            return;
        }
        if (typeof window !== 'undefined' && !window.MarketsPage) {
            window.MarketsPage = page;
        }

        // 独立页：关闭动作改为回列表，避免仅去掉 show class
        page.hideSectorDetailModal = function () {
            window.location.href = listHref;
        };

        if (!code) {
            const body = document.getElementById('sectorDetailBody');
            const title = document.getElementById('sectorDetailTitle');
            if (title) title.textContent = '缺少板块代码';
            if (body) {
                body.innerHTML =
                    '<div class="sector-detail-error">请通过带 board_code 的链接打开本页，或从<a href="markets.html">行情中心</a>进入。</div>';
            }
            return;
        }

        await page.showSectorDetail(name, code, source, kind);

        // 确保独立页始终可见
        const modal = document.getElementById('sectorDetailModal');
        if (modal) {
            modal.classList.add('show', 'is-standalone');
            modal.removeAttribute('hidden');
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            void boot();
        });
    } else {
        void boot();
    }
})();

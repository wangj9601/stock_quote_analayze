// 运行：node test/test_watchlist_codes_cache.js
// 验证 frontend/js/common.js 中 CommonUtils.watchlist 的缓存 / 并发合并 / 写操作失效。
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

function makeSandbox() {
    const store = {};
    const calls = [];
    const sandbox = {
        console: { log() {}, warn() {}, error() {} },
        Config: { getApiBaseUrl: () => 'http://api' },
        localStorage: {
            getItem: (k) => (k in store ? store[k] : null),
            setItem: (k, v) => { store[k] = String(v); },
            removeItem: (k) => { delete store[k]; },
        },
        document: { addEventListener() {}, querySelectorAll: () => [], getElementById: () => null },
        window: { location: { pathname: '/stock.html', search: '', hash: '' } },
        URL,
        setTimeout,
        Date,
        fetch: async (url, opts = {}) => {
            calls.push({ url, method: (opts.method || 'GET').toUpperCase() });
            await new Promise((r) => setTimeout(r, 5));
            return {
                ok: true,
                status: 200,
                json: async () => ({ success: true, data: [{ code: '600519', name: '贵州茅台', group_name: 'default' }] }),
            };
        },
    };
    sandbox.window.localStorage = sandbox.localStorage;
    vm.createContext(sandbox);
    const src = fs.readFileSync(path.join(__dirname, '../frontend/js/common.js'), 'utf8');
    vm.runInContext(src + '\n;this.__CU = CommonUtils; this.__authFetch = authFetch;', sandbox);
    store.userInfo = JSON.stringify({ id: 6 });
    return { sandbox, store, calls, CU: sandbox.__CU, authFetch: sandbox.__authFetch };
}

(async () => {
    const codesCalls = (calls) => calls.filter((c) => c.url.endsWith('/api/watchlist/codes')).length;

    {
        const { CU, calls } = makeSandbox();
        const [a, b, c] = await Promise.all([CU.watchlist.getItems(), CU.watchlist.has('600519'), CU.watchlist.getCodeSet()]);
        assert.strictEqual(codesCalls(calls), 1, '并发调用应合并为一次请求');
        assert.strictEqual(a.length, 1);
        assert.strictEqual(b, true);
        assert.ok(c.has('600519'));
        await CU.watchlist.getItems();
        assert.strictEqual(codesCalls(calls), 1, 'TTL 内应命中内存缓存');
        console.info('ok: 并发合并 + 内存缓存');
    }

    {
        const { CU, calls, store } = makeSandbox();
        await CU.watchlist.getItems();
        CU.watchlist._mem = null;
        await CU.watchlist.getItems();
        assert.strictEqual(codesCalls(calls), 1, '模拟新页面：应命中 localStorage 缓存');
        const entry = JSON.parse(store.watchlistCodesCache);
        entry.at -= CU.watchlist.TTL_MS + 1;
        store.watchlistCodesCache = JSON.stringify(entry);
        CU.watchlist._mem = null;
        await CU.watchlist.getItems();
        assert.strictEqual(codesCalls(calls), 2, '过期后应重新请求');
        console.info('ok: localStorage 缓存 + TTL 过期');
    }

    {
        const { CU, calls, store, authFetch } = makeSandbox();
        await CU.watchlist.getItems();
        await authFetch('http://api/api/watchlist', { method: 'POST', body: '{}' });
        assert.ok(!('watchlistCodesCache' in store), 'POST 后 localStorage 缓存应被清除');
        await CU.watchlist.getItems();
        assert.strictEqual(codesCalls(calls), 2, '写操作后应重新请求');
        await authFetch('http://api/api/watchlist/delete_by_code', { method: 'POST' });
        await CU.watchlist.getItems();
        assert.strictEqual(codesCalls(calls), 3, 'delete_by_code 后应重新请求');
        await authFetch('http://api/api/watchlist?limit=3');
        await CU.watchlist.getItems();
        assert.strictEqual(codesCalls(calls), 3, 'GET 不应使缓存失效');
        console.info('ok: 写操作失效，读操作不失效');
    }

    {
        const { CU, calls, store, authFetch } = makeSandbox();
        const p = CU.watchlist.getItems();
        await authFetch('http://api/api/watchlist', { method: 'POST' });
        await p;
        assert.ok(!('watchlistCodesCache' in store), '请求进行中发生写操作，旧结果不应落缓存');
        await CU.watchlist.getItems();
        assert.strictEqual(codesCalls(calls), 2);
        console.info('ok: 请求期间写操作不落过期缓存');
    }

    {
        const { CU, calls, store } = makeSandbox();
        await CU.watchlist.getItems();
        store.userInfo = JSON.stringify({ id: 7 });
        await CU.watchlist.getItems();
        assert.strictEqual(codesCalls(calls), 2, '切换用户后不应复用他人缓存');
        delete store.userInfo;
        assert.strictEqual((await CU.watchlist.getItems()).length, 0, '未登录返回空数组');
        assert.strictEqual(codesCalls(calls), 2, '未登录不发请求');
        console.info('ok: 按用户隔离 + 未登录');
    }

    console.info('ALL PASSED');
})().catch((e) => {
    console.error(e);
    process.exit(1);
});

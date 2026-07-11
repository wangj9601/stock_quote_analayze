/**
 * 前端权限引擎：频道 / 标签页 / 按钮三级控制
 */
const PermissionEngine = {
  permissions: new Set(),
  role: null,
  _initialized: false,

  async init() {
    try {
      const base = (typeof Config !== 'undefined' && Config.getApiBaseUrl) ? Config.getApiBaseUrl() : '';
      const resp = await smartFetch(base + '/api/auth/permissions');
      if (!resp.ok) {
        console.warn('[PermissionEngine] 获取权限失败', resp.status);
        return;
      }
      const data = await resp.json();
      this.setPermissions(data.permissions || [], data.role || null);
      this.applyToPage();
      this._initialized = true;
    } catch (err) {
      console.warn('[PermissionEngine] init 异常', err);
    }
  },

  setPermissions(codes, role) {
    this.permissions = new Set(codes || []);
    this.role = role;
    try {
      localStorage.setItem('userPermissions', JSON.stringify(codes || []));
      if (role) localStorage.setItem('userRole', JSON.stringify(role));
    } catch (_) { /* ignore */ }
  },

  loadFromCache() {
    try {
      const cached = localStorage.getItem('userPermissions');
      const roleCached = localStorage.getItem('userRole');
      if (cached) {
        this.permissions = new Set(JSON.parse(cached));
      }
      if (roleCached) {
        this.role = JSON.parse(roleCached);
      }
    } catch (_) { /* ignore */ }
  },

  has(code) {
    if (!code) return true;
    return this.permissions.has(code);
  },

  applyToPage() {
    document.querySelectorAll('[data-perm]').forEach(el => {
      const code = el.getAttribute('data-perm');
      if (!this.has(code)) {
        el.style.display = 'none';
        el.setAttribute('aria-hidden', 'true');
      } else {
        if (el.style.display === 'none' && !el.dataset.permHiddenByOther) {
          el.style.removeProperty('display');
        }
        el.removeAttribute('aria-hidden');
      }
    });
    this.guardChannel();
    this.activateFirstAllowedTab();
    this.handleDeniedQuery();
  },

  guardChannel() {
    const channel = document.body && document.body.getAttribute('data-channel');
    if (!channel) return;
    const code = channel.startsWith('channel.') ? channel : 'channel.' + channel;
    if (!this.has(code)) {
      window.location.href = 'index.html?denied=1';
    }
  },

  activateFirstAllowedTab() {
    const tabSelectors = [
      '.strategy-tab[data-perm]',
      '.analysis-tab[data-perm]',
      '.profile-tab[data-perm]',
      '.category-tab[data-perm]'
    ];
    for (const selector of tabSelectors) {
      const tabs = Array.from(document.querySelectorAll(selector));
      if (!tabs.length) continue;
      const visible = tabs.filter(t => this.has(t.getAttribute('data-perm')));
      if (!visible.length) continue;
      const active = tabs.find(t => t.classList.contains('active'));
      if (active && this.has(active.getAttribute('data-perm'))) continue;
      visible[0].click();
      break;
    }
  },

  handleDeniedQuery() {
    const params = new URLSearchParams(window.location.search);
    if (params.get('denied') === '1') {
      if (typeof CommonUtils !== 'undefined' && CommonUtils.showToast) {
        CommonUtils.showToast('您没有访问该页面的权限', 'warning');
      } else {
        console.warn('无权限访问该页面');
      }
      params.delete('denied');
      const qs = params.toString();
      const url = window.location.pathname + (qs ? '?' + qs : '') + window.location.hash;
      window.history.replaceState({}, '', url);
    }
  },

  decorateStrategyTabs() {
    if (!window.PERMISSION_TAB_MAP) return;
    Object.entries(window.PERMISSION_TAB_MAP).forEach(([strategy, perm]) => {
      const tab = document.querySelector(`.strategy-tab[data-strategy="${strategy}"]`);
      if (tab) tab.setAttribute('data-perm', perm);
      const content = document.getElementById(`${strategy}-content`);
      if (content) content.setAttribute('data-perm', perm);
    });
    document.querySelectorAll('.refresh-btn[data-strategy]').forEach(btn => {
      const strategy = btn.getAttribute('data-strategy');
      const tabPerm = window.PERMISSION_TAB_MAP[strategy];
      if (!tabPerm) return;
      const suffix = tabPerm.replace('channel.screening.tab.', '');
      btn.setAttribute('data-perm', 'channel.screening.tab.' + suffix + '.btn.refresh');
    });
    this.applyToPage();
  }
};

window.PermissionEngine = PermissionEngine;

document.addEventListener('DOMContentLoaded', () => {
  PermissionEngine.loadFromCache();
  PermissionEngine.init();
});

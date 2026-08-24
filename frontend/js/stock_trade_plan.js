/**
 * 个股分析 · 综合交易策略展示
 */
const StockTradePlan = {
    esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    },

    fmtPrice(v) {
        if (v == null || v === '' || !Number.isFinite(Number(v))) return '--';
        return Number(v).toFixed(2);
    },

    zoneTxt(z, kind) {
        if (!z || typeof z !== 'object') return '--';
        const basis = String(z.basis || '');
        if (kind === 'stop' && z.price != null) {
            return this.fmtPrice(z.price);
        }
        if (kind === 'stop' && basis.includes('confluence') && z.price != null) {
            return this.fmtPrice(z.price);
        }
        const lo = z.low;
        const hi = z.high;
        const px = z.price;
        if (lo != null && hi != null) return `${this.fmtPrice(lo)} – ${this.fmtPrice(hi)}`;
        if (px != null) return this.fmtPrice(px);
        if (lo != null) return this.fmtPrice(lo);
        return '--';
    },

    stanceClass(kind, value) {
        const v = String(value || '').toLowerCase();
        if (kind === 'short') {
            if (v === 'buy') return 'ssa-plan-badge--buy';
            if (v === 'avoid' || v === 'sell') return 'ssa-plan-badge--avoid';
            return 'ssa-plan-badge--watch';
        }
        if (v === 'bull') return 'ssa-plan-badge--bull';
        if (v === 'bear') return 'ssa-plan-badge--bear';
        return 'ssa-plan-badge--neutral';
    },

    confClass(c) {
        const v = String(c || '').toLowerCase();
        if (v === 'high') return 'ssa-plan-badge--conf-high';
        if (v === 'low') return 'ssa-plan-badge--conf-low';
        return 'ssa-plan-badge--conf-mid';
    },

    render(host, pack) {
        if (!host) return;
        const plan = (pack && pack.plan) || pack;
        if (!plan || typeof plan !== 'object') {
            host.innerHTML = '<p class="ssa-muted">暂无综合交易策略</p>';
            return;
        }
        const st = plan.short_term || {};
        const mt = plan.medium_term || {};
        const kl = plan.key_levels || {};
        const conflicts = Array.isArray(plan.conflicts) ? plan.conflicts : [];
        const confMap = { high: '高', medium: '中', low: '低' };
        const isStructWatch =
            plan.stance_short === 'watch' &&
            st.entry_zone &&
            st.entry_zone.basis === 'structure_watch';
        const entryTh = isStructWatch ? '观察区' : '入场/承接';
        const stopTh =
            st.stop_zone && st.stop_zone.basis === 'structure_invalidation'
                ? '失效参考'
                : '止损参考';
        const tpTh =
            st.take_profit && st.take_profit.basis === 'structure_resistance'
                ? '压力观察'
                : '止盈参考';

        const shortTriggers = (st.triggers || [])
            .map((t) => `<li>${this.esc(t)}</li>`)
            .join('');
        const exitTriggers = (mt.exit_triggers || [])
            .map((t) => `<li>${this.esc(t)}</li>`)
            .join('');
        const conflictHtml = conflicts.length
            ? `<div class="ssa-plan-conflicts">${conflicts
                  .map((c) => `<div class="ssa-plan-conflict-item">${this.esc(c)}</div>`)
                  .join('')}</div>`
            : '';

        host.innerHTML =
            `<div class="ssa-plan-wrap">` +
            `<div class="ssa-plan-head">` +
            `<div class="ssa-plan-badges">` +
            `<span class="ssa-plan-badge ${this.stanceClass('short', plan.stance_short)}">短线：${this.esc(plan.stance_short_label || st.action_label || '--')}</span>` +
            `<span class="ssa-plan-badge ${this.stanceClass('medium', plan.stance_medium)}">中长线：${this.esc(plan.stance_medium_label || mt.bias_label || '--')}</span>` +
            `<span class="ssa-plan-badge ${this.confClass(plan.confidence)}">信心 ${this.esc(confMap[plan.confidence] || plan.confidence || '--')}</span>` +
            (plan.primary_strategy && plan.primary_strategy !== 'none'
                ? `<span class="ssa-plan-badge ssa-plan-badge--primary">主策略 ${this.esc(plan.primary_strategy_name || plan.primary_strategy)}</span>`
                : '') +
            (plan.structure_rr != null
                ? `<span class="ssa-plan-badge ssa-plan-badge--rr">RR≈${this.fmtPrice(plan.structure_rr)}</span>`
                : '') +
            `</div>` +
            (kl.support != null || kl.resistance != null || kl.close != null
                ? `<div class="ssa-plan-levels">关键位：支撑 ${this.fmtPrice(kl.support)} / 现价 ${this.fmtPrice(kl.close)} / 阻力 ${this.fmtPrice(kl.resistance)}</div>`
                : '') +
            `</div>` +
            `<div class="ssa-plan-grid">` +
            `<div class="ssa-plan-col">` +
            `<h5 class="ssa-plan-col-title">短线策略</h5>` +
            `<table class="ssa-plan-table"><tbody>` +
            `<tr><th>${entryTh}</th><td>${this.zoneTxt(st.entry_zone)}</td><td>${this.esc((st.entry_zone && st.entry_zone.label) || '--')}</td></tr>` +
            `<tr><th>${stopTh}</th><td>${this.zoneTxt(st.stop_zone, 'stop')}</td><td>${this.esc((st.stop_zone && st.stop_zone.label) || '--')}</td></tr>` +
            `<tr><th>${tpTh}</th><td>${this.zoneTxt(st.take_profit && st.take_profit.prices ? { price: (st.take_profit.prices || [])[0] } : st.take_profit)}</td><td>${this.esc((st.take_profit && st.take_profit.label) || '--')}</td></tr>` +
            `</tbody></table>` +
            (shortTriggers ? `<ul class="ssa-plan-list">${shortTriggers}</ul>` : '') +
            (st.summary ? `<p class="ssa-plan-summary">${this.esc(st.summary)}</p>` : '') +
            `</div>` +
            `<div class="ssa-plan-col">` +
            `<h5 class="ssa-plan-col-title">中长线策略</h5>` +
            `<table class="ssa-plan-table"><tbody>` +
            `<tr><th>趋势立场</th><td colspan="2">${this.esc(mt.bias_label || '--')}</td></tr>` +
            `<tr><th>回撤观察</th><td>${this.zoneTxt(mt.watch_zone)}</td><td>${this.esc((mt.watch_zone && mt.watch_zone.label) || (mt.ma20 != null ? `MA20≈${this.fmtPrice(mt.ma20)}` : '--'))}</td></tr>` +
            `</tbody></table>` +
            (mt.holding_plan ? `<p class="ssa-plan-summary">${this.esc(mt.holding_plan)}</p>` : '') +
            (exitTriggers ? `<ul class="ssa-plan-list ssa-plan-list--exit">${exitTriggers}</ul>` : '') +
            (mt.summary && mt.summary !== mt.holding_plan ? `<p class="ssa-plan-muted">${this.esc(mt.summary)}</p>` : '') +
            `</div>` +
            `</div>` +
            conflictHtml +
            `<p class="ssa-plan-disclaimer">${this.esc(plan.disclaimer || '规则模板，非投资建议。')}</p>` +
            `</div>`;
    },
};

window.StockTradePlan = StockTradePlan;

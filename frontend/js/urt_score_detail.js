/**
 * URT 得分明细 HTML（选股页 / 明细页 / 信号历史页共用）
 * 展示风格对齐 GMS：分区标题 + meta 条 + 分项表。
 */
const UrtScoreDetail = {
    _fmt(v, digits) {
        if (v == null || v === '') return '--';
        if (typeof v === 'boolean') return v ? '是' : '否';
        const n = Number(v);
        if (!Number.isFinite(n)) return String(v);
        return n.toFixed(digits != null ? digits : 2);
    },

    _passLabel(ok) {
        if (ok === true) return '<span class="strength-high">通过</span>';
        if (ok === false) return '<span class="strength-low">未通过</span>';
        return '--';
    },

    /**
     * 分项得分行（页面 / PDF 同源）
     * @param {object} parts score_detail.parts
     * @param {object} ctx 展示用上下文字段
     * @returns {Array<{name:string,score:*,max:*,maxLabel?:string,note:string}>}
     */
    _scorePartRows(parts, ctx) {
        const p = parts && typeof parts === 'object' ? parts : {};
        const c = ctx && typeof ctx === 'object' ? ctx : {};
        const ma = p.above_ma20 || {};
        const yang = p.yang || {};
        const yq = p.yang_quality || {};
        const yangMed = p.yang_medium || {};
        const maBull = p.ma_bull || {};
        const vol = p.volume || {};
        const st = p.structure_position || {};
        const oh = p.overheat_penalty || {};
        const turnover = p.turnover || {};
        const vRatio = p.volume_ratio || {};

        const yang4 = c.yang4;
        const yang5 = c.yang5;
        const yang10 = c.yang10;
        const yang15 = c.yang15;
        const yang20 = c.yang20;
        const ma5 = c.ma5;
        const ma10 = c.ma10;
        const maBullOk = c.maBullOk;
        const vm = c.vm;
        const vr = c.vr;
        const to = c.to;

        const maNote = (() => {
            if (ma.ok === false) return '未站上';
            if (ma.ok !== true) return '--';
            if (ma.mode === 'binary' || ma.mode === 'static' || ma.mode === 'pass') {
                return '收盘 ≥ MA20（静态满分）';
            }
            const biasPct = ma.bias20 != null ? `${(Number(ma.bias20) * 100).toFixed(1)}%` : '--';
            const slopePct = ma.slope20 != null ? `${(Number(ma.slope20) * 100).toFixed(2)}%` : '--';
            const days = ma.slope_days != null ? ma.slope_days : '--';
            return `斜率/发散 · 乖离 ${biasPct} · ${days}日斜率 ${slopePct}`;
        })();

        const maBullNote = (() => {
            const depth = maBull.depth != null ? maBull.depth : null;
            const maxD = maBull.max_depth != null ? maBull.max_depth : 6;
            const tip = maBull.tip_period != null ? maBull.tip_period : null;
            const bear = maBull.bear_ok === true;
            let stance = '--';
            if (bear) stance = '空头−8';
            else if (maBull.ok === true || maBullOk === true) stance = '多头';
            else if (maBull.ok === false || maBullOk === false) stance = '非多头';
            const depthTxt = depth != null
                ? `深度 ${depth}/${maxD}${tip != null ? `（至MA${tip}）` : ''}`
                : '';
            const pairs = Array.isArray(maBull.pairs_ok) && maBull.pairs_ok.length
                ? maBull.pairs_ok.slice(0, 4).join(' ')
                : '';
            return `MA5 ${this._fmt(maBull.ma5 != null ? maBull.ma5 : ma5, 2)} · MA10 ${this._fmt(maBull.ma10 != null ? maBull.ma10 : ma10, 2)} · ${stance}${depthTxt ? ' · ' + depthTxt : ''}${pairs ? ' · ' + pairs : ''}`;
        })();

        const turnoverNote = (() => {
            if (turnover.enabled === false) return '未启用积分';
            const abs = this._fmt(turnover.turnover_rate != null ? turnover.turnover_rate : to, 2);
            const med = turnover.median != null ? this._fmt(turnover.median, 2) : '--';
            const rel = turnover.relative != null ? Number(turnover.relative).toFixed(2) : '--';
            const mode = turnover.mode === 'relative' ? '相对中位' : (turnover.mode === 'absolute_fallback' ? '绝对回退' : '');
            const pen = turnover.abs_penalty ? '；绝对熔断减分' : '';
            const mn = turnover.min != null ? ` / 下限${this._fmt(turnover.min, 1)}` : '';
            return `换手 ${abs}%（中位 ${med}% · 相对 ${rel}×${mode ? ' · ' + mode : ''}${pen}）${mn}`;
        })();

        const yqNote = (() => {
            const avg = yq.avg_body_ratio != null ? Number(yq.avg_body_ratio).toFixed(2) : '--';
            const br = yq.breakout_body_ratio != null ? Number(yq.breakout_body_ratio).toFixed(2) : '--';
            const amp = yq.breakout_amplitude != null
                ? `${(Number(yq.breakout_amplitude) * 100).toFixed(1)}%`
                : '--';
            return `近窗实体 ${avg} · 突破实体 ${br} · 突破波幅 ${amp}`;
        })();

        const stNote = (() => {
            const prox = st.proximity_score != null ? st.proximity_score : '--';
            const proxMax = st.proximity_max != null ? st.proximity_max : 8;
            const rrS = st.rr_score != null ? st.rr_score : '--';
            const rrMax = st.rr_max != null ? st.rr_max : 7;
            const rr = st.structure_rr != null ? Number(st.structure_rr).toFixed(2) : '--';
            const reason = [st.proximity_reason, st.rr_reason].filter(Boolean).join(' / ') || '--';
            return `贴近 ${prox}/${proxMax} · RR分 ${rrS}/${rrMax}（RR=${rr}）· ${reason}`;
        })();

        const ohNote = (() => {
            const ret = oh.ret_from_low_n != null
                ? `${(Number(oh.ret_from_low_n) * 100).toFixed(1)}%`
                : '--';
            const bias = oh.ma20_bias != null
                ? `${(Number(oh.ma20_bias) * 100).toFixed(1)}%`
                : '--';
            const inten = oh.intensity != null ? Number(oh.intensity).toFixed(2) : '--';
            return `强度 ${inten} · 近窗涨幅 ${ret} · MA20乖离 ${bias}（软阈起扣）`;
        })();

        const ohMaxLabel = oh.min != null ? `${oh.min}～0` : '−10～0';

        return [
            {
                name: 'MA20 趋势',
                score: ma.score,
                max: ma.max != null ? ma.max : 10,
                note: maNote,
            },
            {
                name: '连阳天数',
                score: yang.score != null ? yang.score : null,
                max: yang.max != null ? yang.max : 20,
                note: `4日阳 ${yang.yang_count_4 != null ? yang.yang_count_4 : (yang4 != null ? yang4 : '--')} · 5日阳 ${yang.yang_count_5 != null ? yang.yang_count_5 : (yang5 != null ? yang5 : '--')}`,
            },
            {
                name: 'K线实体质量',
                score: yq.score,
                max: yq.max != null ? yq.max : 10,
                note: yqNote,
            },
            {
                name: '中期阳线',
                score: yangMed.score,
                max: yangMed.max != null ? yangMed.max : 5,
                note: `10日 ${yang10 != null ? yang10 : '--'} · 15日 ${yang15 != null ? yang15 : '--'} · 20日 ${yang20 != null ? yang20 : '--'}${yangMed.ok === true ? '（达标）' : (yangMed.ok === false ? '（未达标）' : '')}`,
            },
            {
                name: '均线多头',
                score: maBull.score,
                max: maBull.max != null ? maBull.max : 8,
                note: maBullNote,
            },
            {
                name: '量能倍数',
                score: vol.score,
                max: vol.max != null ? vol.max : 25,
                note: `倍数 ${this._fmt(vol.volume_multiple != null ? vol.volume_multiple : vm, 2)} / 阈值 ${this._fmt(vol.threshold, 2)}`,
            },
            {
                name: '筹码位置与RR',
                score: st.score,
                max: st.max != null ? st.max : 15,
                note: stNote,
            },
            {
                name: '换手率',
                score: turnover.score,
                max: turnover.max != null ? turnover.max : 0,
                note: turnoverNote,
            },
            {
                name: '量比',
                score: vRatio.score,
                max: vRatio.max != null ? vRatio.max : 0,
                note: vRatio.enabled === false ? '未启用' : `量比 ${this._fmt(vRatio.volume_ratio != null ? vRatio.volume_ratio : vr, 2)}`,
            },
            {
                name: '过热扣分',
                score: oh.score != null ? oh.score : 0,
                max: 0,
                maxLabel: ohMaxLabel,
                note: ohNote,
            },
        ];
    },

    /**
     * @param {object} stockOrDetail 行数据或 API 返回
     * @returns {string} HTML
     */
    buildHtml(stockOrDetail) {
        const src = stockOrDetail && typeof stockOrDetail === 'object' ? stockOrDetail : {};
        const sd = src.score_detail && typeof src.score_detail === 'object' ? src.score_detail : {};
        const parts = sd.parts && typeof sd.parts === 'object' ? sd.parts : {};
        const inputs = sd.inputs && typeof sd.inputs === 'object' ? sd.inputs : {};
        const fields = src.fields && typeof src.fields === 'object' ? src.fields : {};
        const buyLogic = src.buy_logic && typeof src.buy_logic === 'object' ? src.buy_logic : null;

        const total = src.score != null ? src.score : sd.total;
        const minScore = (buyLogic && buyLogic.min_score != null)
            ? buyLogic.min_score
            : (sd.min_score != null ? sd.min_score : 70);
        const buy = buyLogic && buyLogic.buy_signal != null ? buyLogic.buy_signal : src.buy_signal;
        const filterOk = buyLogic && buyLogic.filter_ok != null
            ? buyLogic.filter_ok
            : (fields.filter_ok != null ? fields.filter_ok : src.filter_ok);
        const filterReason = buyLogic && buyLogic.filter_reason
            ? buyLogic.filter_reason
            : (fields.filter_reason != null ? fields.filter_reason : src.filter_reason);
        const scoreOk = buyLogic && buyLogic.score_ok != null
            ? buyLogic.score_ok
            : (fields.score_ok != null ? fields.score_ok : src.score_ok);

        const close = fields.close != null ? fields.close : (src.close != null ? src.close : inputs.close);
        const open = fields.open != null ? fields.open : (src.open != null ? src.open : inputs.open);
        const ma20 = fields.ma20 != null ? fields.ma20 : (src.ma20 != null ? src.ma20 : inputs.ma20);
        const yang4 = fields.yang_count_4 != null ? fields.yang_count_4 : src.yang_count_4;
        const yang5 = fields.yang_count_5 != null ? fields.yang_count_5 : src.yang_count_5;
        const yang10 = fields.yang_count_10 != null ? fields.yang_count_10 : (src.yang_count_10 != null ? src.yang_count_10 : inputs.yang_count_10);
        const yang15 = fields.yang_count_15 != null ? fields.yang_count_15 : (src.yang_count_15 != null ? src.yang_count_15 : inputs.yang_count_15);
        const yang20 = fields.yang_count_20 != null ? fields.yang_count_20 : (src.yang_count_20 != null ? src.yang_count_20 : inputs.yang_count_20);
        const ma5 = fields.ma5 != null ? fields.ma5 : (src.ma5 != null ? src.ma5 : inputs.ma5);
        const ma10 = fields.ma10 != null ? fields.ma10 : (src.ma10 != null ? src.ma10 : inputs.ma10);
        const maBullOk = fields.ma_bull_ok != null ? fields.ma_bull_ok : src.ma_bull_ok;
        const vm = fields.volume_multiple != null ? fields.volume_multiple : src.volume_multiple;
        const vr = fields.volume_ratio != null ? fields.volume_ratio : src.volume_ratio;
        const to = fields.turnover_rate != null ? fields.turnover_rate : src.turnover_rate;

        const buyLabel = buy === true ? '是' : (buy === false ? '否' : '--');
        const buyClass = buy === true ? 'strength-high' : (buy === false ? 'strength-low' : '');

        let html = '<div class="gms-score-detail-inner urt-score-detail-inner">';
        html += '<div class="gms-score-detail-meta">';
        html += `<div class="gms-version-meta-line"><span class="gms-version-name">上升趋势策略（URT）</span>`;
        html += `<span>总分 <strong>${this._fmt(total, 1)}</strong> / 阈值 ${this._fmt(minScore, 0)}</span>`;
        html += `<span>买点 <span class="${buyClass}">${buyLabel}</span></span>`;
        if (filterOk != null) {
            const reasonText = filterReason && filterReason !== 'ok' ? `（${filterReason}）` : '';
            html += `<span>硬筛 ${filterOk ? '通过' : '未通过'}${reasonText}</span>`;
        }
        if (scoreOk != null) html += `<span>得分达标 ${scoreOk ? '是' : '否'}</span>`;
        html += '</div></div>';

        // 【买点判断逻辑】
        html += '<div class="gms-score-detail-section"><strong>【买点判断逻辑】</strong>';
        if (buyLogic) {
            html += `<p class="urt-buy-logic-formula">${buyLogic.formula || '买点 = 硬筛全部通过 AND 得分≥最低得分'}</p>`;
            if (buyLogic.formula_detail) {
                html += `<p class="urt-buy-logic-detail">${buyLogic.formula_detail}</p>`;
            }
            const steps = Array.isArray(buyLogic.steps) ? buyLogic.steps : [];
            if (steps.length) {
                html += '<table class="gms-weight-table"><thead><tr><th>条件</th><th>规则</th><th>实际值</th><th>结果</th></tr></thead><tbody>';
                steps.forEach((s) => {
                    let extra = '';
                    if (s.detail && typeof s.detail === 'object') {
                        const bits = [];
                        if (s.detail.rule_a) bits.push(s.detail.rule_a);
                        if (s.detail.rule_b) bits.push(s.detail.rule_b);
                        if (bits.length) extra = `<div class="urt-buy-logic-sub">${bits.join('；')}</div>`;
                    }
                    if (s.note) extra += `<div class="urt-buy-logic-sub">${s.note}</div>`;
                    html += `<tr><td>${s.name || '--'}</td><td>${s.rule || '--'}${extra}</td>`;
                    html += `<td>${s.actual != null ? s.actual : '--'}</td><td>${this._passLabel(s.pass)}</td></tr>`;
                });
                html += '</tbody></table>';
            }
            const conclClass = buy === true ? 'strength-high' : (buy === false ? 'strength-low' : '');
            html += `<p class="urt-buy-logic-conclusion">结论：硬筛 ${filterOk ? '通过' : '未通过'}，得分达标 ${scoreOk ? '是' : '否'} → 买点 <span class="${conclClass}">${buyLabel}</span></p>`;
        } else {
            html += '<p class="urt-buy-logic-formula">买点 = 硬筛全部通过 AND 得分≥最低得分</p>';
            html += '<p class="urt-buy-logic-detail">硬筛含：站上MA20、连阳（4日≥3阳或5日≥4阳）、放量倍数；可选换手/量比。通过后再要求得分达标。</p>';
            if (filterOk != null || scoreOk != null || buy != null) {
                const conclClass = buy === true ? 'strength-high' : (buy === false ? 'strength-low' : '');
                html += `<p class="urt-buy-logic-conclusion">结论：硬筛 ${filterOk == null ? '--' : (filterOk ? '通过' : '未通过')}，得分达标 ${scoreOk == null ? '--' : (scoreOk ? '是' : '否')} → 买点 <span class="${conclClass}">${buyLabel}</span></p>`;
            }
        }
        html += '</div>';

        html += '<div class="gms-score-detail-section"><strong>【分项得分】</strong>';
        html += '<p class="urt-buy-logic-detail">满分≠已贴近买点：硬筛过线后仍按斜率/位置/过热等拉开排序。</p>';
        html += '<table class="gms-weight-table"><thead><tr><th>分项</th><th>得分</th><th>满分</th><th>说明</th></tr></thead><tbody>';
        const rows = this._scorePartRows(parts, {
            yang4, yang5, yang10, yang15, yang20, ma5, ma10, maBullOk, vm, vr, to,
        });
        rows.forEach((r) => {
            const maxCell = r.maxLabel != null ? r.maxLabel : r.max;
            html += `<tr><td>${r.name}</td><td>${this._fmt(r.score, 2)}</td><td>${maxCell}</td><td>${r.note}</td></tr>`;
        });
        html += '</tbody></table></div>';

        html += '<div class="gms-score-detail-section"><strong>【输入指标】</strong>';
        html += '<div class="gms-version-meta-line">';
        html += `<span>开 ${this._fmt(open, 2)}</span>`;
        html += `<span>收 ${this._fmt(close, 2)}</span>`;
        html += `<span>MA5 ${this._fmt(ma5, 2)}</span>`;
        html += `<span>MA10 ${this._fmt(ma10, 2)}</span>`;
        html += `<span>MA20 ${this._fmt(ma20, 2)}</span>`;
        html += `<span>10/15/20阳 ${yang10 != null ? yang10 : '--'}/${yang15 != null ? yang15 : '--'}/${yang20 != null ? yang20 : '--'}</span>`;
        html += `<span>量能倍数 ${this._fmt(vm, 2)}</span>`;
        html += `<span>量比 ${this._fmt(vr, 2)}</span>`;
        html += `<span>换手 ${this._fmt(to, 2)}%</span>`;
        const turnover = parts.turnover || {};
        const toMed = (turnover && turnover.median != null)
            ? turnover.median
            : (src.turnover_median_n != null ? src.turnover_median_n : fields.turnover_median_n);
        if (toMed != null) {
            html += `<span>换手中位 ${this._fmt(toMed, 2)}%</span>`;
        }
        html += '</div></div>';

        // 【支撑 / 阻力】成交量加权 KDE（与 RPE / 个股关键价位同口径）
        const st = (sd.structure && typeof sd.structure === 'object') ? sd.structure : {};
        const nearSup = src.nearest_support != null ? src.nearest_support
            : (fields.nearest_support != null ? fields.nearest_support : st.nearest_support);
        const nearRes = src.nearest_resistance != null ? src.nearest_resistance
            : (fields.nearest_resistance != null ? fields.nearest_resistance : st.nearest_resistance);
        const supports = Array.isArray(src.support_levels) && src.support_levels.length
            ? src.support_levels
            : (Array.isArray(st.support_levels) ? st.support_levels : []);
        const resists = Array.isArray(src.resistance_levels) && src.resistance_levels.length
            ? src.resistance_levels
            : (Array.isArray(st.resistance_levels) ? st.resistance_levels : []);
        const kdeOk = src.kde_ok != null ? src.kde_ok : st.kde_ok;
        const kdeReason = src.kde_reason || st.kde_reason || '';
        const lookbackUsed = src.kde_lookback_used != null ? src.kde_lookback_used : st.kde_lookback_used;
        const structureRr = src.structure_rr != null ? src.structure_rr
            : (st.rr != null ? st.rr : null);
        const structureRrReason = src.structure_rr_reason || st.rr_reason || '';
        const structureRrFloored = !!(src.structure_rr_downside_floored
            || st.rr_downside_floored);
        html += '<div class="gms-score-detail-section"><strong>【支撑 / 阻力】</strong>';
        html += '<div class="gms-version-meta-line">';
        html += `<span>最近支撑 <strong>${this._fmt(nearSup, 2)}</strong></span>`;
        html += `<span>最近阻力 <strong>${this._fmt(nearRes, 2)}</strong></span>`;
        html += `<span>盈亏比 RR <strong>${structureRr != null && Number.isFinite(Number(structureRr)) ? Number(structureRr).toFixed(2) : '--'}</strong></span>`;
        if (structureRrFloored) {
            html += '<span title="贴支撑时分母已按现价比例下限计算">已用分母下限</span>';
        }
        if (structureRrReason && structureRrReason !== 'ok') {
            html += `<span>${structureRrReason}</span>`;
        }
        if (kdeOk != null) html += `<span>KDE ${kdeOk ? '成功' : '未识别'}</span>`;
        if (lookbackUsed != null) html += `<span>回看 ${lookbackUsed} 日</span>`;
        if (kdeReason) html += `<span>${kdeReason}</span>`;
        html += '</div>';
        html += '<table class="gms-weight-table"><thead><tr><th>类型</th><th>价位（近→远）</th></tr></thead><tbody>';
        html += `<tr><td>阻力</td><td>${resists.length ? resists.map((x) => this._fmt(x, 2)).join('、') : '--'}</td></tr>`;
        html += `<tr><td>支撑</td><td>${supports.length ? supports.map((x) => this._fmt(x, 2)).join('、') : '--'}</td></tr>`;
        html += '</tbody></table></div>';

        // 【买点建议】基于支撑/阻力的操作区（后端 trade_advice）
        const advice = (src.trade_advice && typeof src.trade_advice === 'object')
            ? src.trade_advice
            : (sd.trade_advice && typeof sd.trade_advice === 'object' ? sd.trade_advice : null);
        if (advice) {
            const actionMap = { buy: '买入/承接', watch: '观察', avoid: '回避', sell: '减仓/离场' };
            const confMap = { high: '高', medium: '中', low: '低' };
            const action = advice.action || 'watch';
            const buyZ = advice.buy_zone || {};
            const stopZ = advice.stop_zone || {};
            const tp = advice.take_profit || {};
            const tpPrices = Array.isArray(tp.prices) ? tp.prices : (tp.price != null ? [tp.price] : []);
            const zoneTxt = (z) => {
                if (!z || typeof z !== 'object') return '--';
                if (z.low != null && z.high != null) {
                    return `${this._fmt(z.low, 2)} – ${this._fmt(z.high, 2)}`;
                }
                if (z.price != null) return this._fmt(z.price, 2);
                return '--';
            };
            const actionCls = action === 'buy'
                ? 'urt-advice-badge urt-advice-badge--buy'
                : (action === 'avoid'
                    ? 'urt-advice-badge urt-advice-badge--avoid'
                    : 'urt-advice-badge urt-advice-badge--watch');
            const confCls = advice.confidence === 'high'
                ? 'urt-advice-badge urt-advice-badge--conf-high'
                : (advice.confidence === 'low'
                    ? 'urt-advice-badge urt-advice-badge--conf-low'
                    : 'urt-advice-badge urt-advice-badge--conf-mid');
            const kl = advice.key_levels && typeof advice.key_levels === 'object' ? advice.key_levels : {};
            html += '<div class="gms-score-detail-section urt-trade-advice-section"><strong>【买点建议】</strong>';
            html += '<div class="urt-advice-badges">';
            html += `<span class="${actionCls}">${actionMap[action] || action}</span>`;
            html += `<span class="${confCls}">信心 ${confMap[advice.confidence] || advice.confidence || '--'}</span>`;
            if (advice.structure_rr != null && Number.isFinite(Number(advice.structure_rr))) {
                html += `<span class="urt-advice-badge urt-advice-badge--rr">结构盈亏比 RR≈${Number(advice.structure_rr).toFixed(2)}</span>`;
            }
            if (kl.support != null || kl.close != null || kl.resistance != null) {
                html += `<span class="urt-advice-badge urt-advice-badge--levels">关键位 支撑${this._fmt(kl.support, 2)} / 现价${this._fmt(kl.close, 2)} / 阻力${this._fmt(kl.resistance, 2)}</span>`;
            } else {
                if (advice.kde_support != null) {
                    html += `<span class="urt-advice-badge urt-advice-badge--levels">结构支撑 ${this._fmt(advice.kde_support, 2)}</span>`;
                }
                if (advice.kde_resistance != null) {
                    html += `<span class="urt-advice-badge urt-advice-badge--levels">结构阻力 ${this._fmt(advice.kde_resistance, 2)}</span>`;
                }
            }
            html += '</div>';
            html += '<table class="gms-weight-table"><thead><tr><th>项目</th><th>价位/区间</th><th>说明</th></tr></thead><tbody>';
            html += `<tr><td>买入/承接区（短线）</td><td>${zoneTxt(buyZ)}</td><td>${buyZ.label || '--'}</td></tr>`;
            html += `<tr><td>止损参考</td><td>${zoneTxt(stopZ)}</td><td>${stopZ.label || '--'}</td></tr>`;
            const deepW = advice.deeper_watch && typeof advice.deeper_watch === 'object'
                ? advice.deeper_watch
                : (advice.horizon && advice.horizon.medium_term && advice.horizon.medium_term.watch);
            if (deepW && (deepW.price != null || deepW.low != null)) {
                html += `<tr><td>中线更深回撤关注</td><td>${zoneTxt(deepW)}</td><td>${deepW.label || (advice.horizon && advice.horizon.medium_term && advice.horizon.medium_term.note) || '--'}</td></tr>`;
            }
            html += `<tr><td>止盈参考</td><td>${tpPrices.length ? tpPrices.map((x) => this._fmt(x, 2)).join('、') : '--'}</td><td>${tp.label || '--'}</td></tr>`;
            html += '</tbody></table>';
            if (advice.summary) {
                html += `<p class="urt-buy-logic-detail">${String(advice.summary)}</p>`;
            }
            html += '</div>';
        }

        const riskTags = Array.isArray(src.risk_tags) && src.risk_tags.length
            ? src.risk_tags
            : (Array.isArray(sd.risk_tags) ? sd.risk_tags : []);
        if (riskTags.length) {
            html += '<div class="gms-score-detail-section"><strong>【风险提示】</strong>';
            html += `<div class="gms-risk-tags">${riskTags.map((t) => {
                const level = (t && t.level) || 'info';
                const label = (t && (t.label || t.id)) || '风险';
                const reason = String((t && t.reason) || '').replace(/"/g, '&quot;');
                return `<span class="gms-risk-tag gms-risk-${level}" title="${reason}">${label}</span>`;
            }).join('')}</div></div>`;
        }

        html += '</div>';
        return html;
    },

    /**
     * 结构化导出模型（PDF / 打印与页面展示同源字段）
     * @param {object} stockOrDetail
     * @returns {object}
     */
    buildExportModel(stockOrDetail) {
        const src = stockOrDetail && typeof stockOrDetail === 'object' ? stockOrDetail : {};
        const sd = src.score_detail && typeof src.score_detail === 'object' ? src.score_detail : {};
        const parts = sd.parts && typeof sd.parts === 'object' ? sd.parts : {};
        const inputs = sd.inputs && typeof sd.inputs === 'object' ? sd.inputs : {};
        const fields = src.fields && typeof src.fields === 'object' ? src.fields : {};
        const buyLogic = src.buy_logic && typeof src.buy_logic === 'object' ? src.buy_logic : null;

        const total = src.score != null ? src.score : sd.total;
        const minScore = (buyLogic && buyLogic.min_score != null)
            ? buyLogic.min_score
            : (sd.min_score != null ? sd.min_score : 70);
        const buy = buyLogic && buyLogic.buy_signal != null ? buyLogic.buy_signal : src.buy_signal;
        const filterOk = buyLogic && buyLogic.filter_ok != null
            ? buyLogic.filter_ok
            : (fields.filter_ok != null ? fields.filter_ok : src.filter_ok);
        const filterReason = buyLogic && buyLogic.filter_reason
            ? buyLogic.filter_reason
            : (fields.filter_reason != null ? fields.filter_reason : src.filter_reason);
        const scoreOk = buyLogic && buyLogic.score_ok != null
            ? buyLogic.score_ok
            : (fields.score_ok != null ? fields.score_ok : src.score_ok);

        const close = fields.close != null ? fields.close : (src.close != null ? src.close : inputs.close);
        const open = fields.open != null ? fields.open : (src.open != null ? src.open : inputs.open);
        const ma20 = fields.ma20 != null ? fields.ma20 : (src.ma20 != null ? src.ma20 : inputs.ma20);
        const yang4 = fields.yang_count_4 != null ? fields.yang_count_4 : src.yang_count_4;
        const yang5 = fields.yang_count_5 != null ? fields.yang_count_5 : src.yang_count_5;
        const yang10 = fields.yang_count_10 != null ? fields.yang_count_10 : (src.yang_count_10 != null ? src.yang_count_10 : inputs.yang_count_10);
        const yang15 = fields.yang_count_15 != null ? fields.yang_count_15 : (src.yang_count_15 != null ? src.yang_count_15 : inputs.yang_count_15);
        const yang20 = fields.yang_count_20 != null ? fields.yang_count_20 : (src.yang_count_20 != null ? src.yang_count_20 : inputs.yang_count_20);
        const ma5 = fields.ma5 != null ? fields.ma5 : (src.ma5 != null ? src.ma5 : inputs.ma5);
        const ma10 = fields.ma10 != null ? fields.ma10 : (src.ma10 != null ? src.ma10 : inputs.ma10);
        const maBullOk = fields.ma_bull_ok != null ? fields.ma_bull_ok : src.ma_bull_ok;
        const vm = fields.volume_multiple != null ? fields.volume_multiple : src.volume_multiple;
        const vr = fields.volume_ratio != null ? fields.volume_ratio : src.volume_ratio;
        const to = fields.turnover_rate != null ? fields.turnover_rate : src.turnover_rate;

        const yn = (v) => (v === true ? '是' : (v === false ? '否' : '--'));
        const passTxt = (ok) => (ok === true ? '通过' : (ok === false ? '未通过' : '--'));

        const buySteps = [];
        if (buyLogic && Array.isArray(buyLogic.steps)) {
            buyLogic.steps.forEach((s) => {
                const bits = [];
                if (s.detail && typeof s.detail === 'object') {
                    if (s.detail.rule_a) bits.push(s.detail.rule_a);
                    if (s.detail.rule_b) bits.push(s.detail.rule_b);
                }
                if (s.note) bits.push(s.note);
                buySteps.push([
                    s.name || '--',
                    `${s.rule || '--'}${bits.length ? `（${bits.join('；')}）` : ''}`,
                    s.actual != null ? String(s.actual) : '--',
                    passTxt(s.pass),
                ]);
            });
        }

        const scoreRows = this._scorePartRows(parts, {
            yang4, yang5, yang10, yang15, yang20, ma5, ma10, maBullOk, vm, vr, to,
        }).map((r) => [
            r.name,
            this._fmt(r.score, 2),
            String(r.maxLabel != null ? r.maxLabel : r.max),
            r.note,
        ]);

        const turnover = parts.turnover || {};

        const toMed = (turnover && turnover.median != null)
            ? turnover.median
            : (src.turnover_median_n != null ? src.turnover_median_n : fields.turnover_median_n);

        const st = (sd.structure && typeof sd.structure === 'object') ? sd.structure : {};
        const nearSup = src.nearest_support != null ? src.nearest_support
            : (fields.nearest_support != null ? fields.nearest_support : st.nearest_support);
        const nearRes = src.nearest_resistance != null ? src.nearest_resistance
            : (fields.nearest_resistance != null ? fields.nearest_resistance : st.nearest_resistance);
        const supports = Array.isArray(src.support_levels) && src.support_levels.length
            ? src.support_levels
            : (Array.isArray(st.support_levels) ? st.support_levels : []);
        const resists = Array.isArray(src.resistance_levels) && src.resistance_levels.length
            ? src.resistance_levels
            : (Array.isArray(st.resistance_levels) ? st.resistance_levels : []);
        const kdeOk = src.kde_ok != null ? src.kde_ok : st.kde_ok;
        const kdeReason = src.kde_reason || st.kde_reason || '';
        const lookbackUsed = src.kde_lookback_used != null ? src.kde_lookback_used : st.kde_lookback_used;
        const structureRr = src.structure_rr != null ? src.structure_rr
            : (st.rr != null ? st.rr : null);
        const structureRrReason = src.structure_rr_reason || st.rr_reason || '';
        const structureRrFloored = !!(src.structure_rr_downside_floored || st.rr_downside_floored);

        const advice = (src.trade_advice && typeof src.trade_advice === 'object')
            ? src.trade_advice
            : (sd.trade_advice && typeof sd.trade_advice === 'object' ? sd.trade_advice : null);
        let adviceBlock = null;
        if (advice) {
            const actionMap = { buy: '买入/承接', watch: '观察', avoid: '回避', sell: '减仓/离场' };
            const confMap = { high: '高', medium: '中', low: '低' };
            const action = advice.action || 'watch';
            const buyZ = advice.buy_zone || {};
            const stopZ = advice.stop_zone || {};
            const tp = advice.take_profit || {};
            const tpPrices = Array.isArray(tp.prices) ? tp.prices : (tp.price != null ? [tp.price] : []);
            const zoneTxt = (z) => {
                if (!z || typeof z !== 'object') return '--';
                if (z.low != null && z.high != null) {
                    return `${this._fmt(z.low, 2)} – ${this._fmt(z.high, 2)}`;
                }
                if (z.price != null) return this._fmt(z.price, 2);
                return '--';
            };
            const kl = advice.key_levels && typeof advice.key_levels === 'object' ? advice.key_levels : {};
            const adviceRows = [
                ['买入/承接区（短线）', zoneTxt(buyZ), buyZ.label || '--'],
                ['止损参考', zoneTxt(stopZ), stopZ.label || '--'],
            ];
            const deepW = advice.deeper_watch && typeof advice.deeper_watch === 'object'
                ? advice.deeper_watch
                : (advice.horizon && advice.horizon.medium_term && advice.horizon.medium_term.watch);
            if (deepW && (deepW.price != null || deepW.low != null)) {
                adviceRows.push([
                    '中线更深回撤关注',
                    zoneTxt(deepW),
                    deepW.label || (advice.horizon && advice.horizon.medium_term && advice.horizon.medium_term.note) || '--',
                ]);
            }
            adviceRows.push([
                '止盈参考',
                tpPrices.length ? tpPrices.map((x) => this._fmt(x, 2)).join('、') : '--',
                tp.label || '--',
            ]);
            adviceBlock = {
                action: actionMap[action] || action,
                confidence: confMap[advice.confidence] || advice.confidence || '--',
                structureRr: advice.structure_rr != null && Number.isFinite(Number(advice.structure_rr))
                    ? Number(advice.structure_rr).toFixed(2)
                    : null,
                keyLevels: (kl.support != null || kl.close != null || kl.resistance != null)
                    ? `支撑${this._fmt(kl.support, 2)} / 现价${this._fmt(kl.close, 2)} / 阻力${this._fmt(kl.resistance, 2)}`
                    : null,
                rows: adviceRows,
                summary: advice.summary ? String(advice.summary) : '',
            };
        }

        const riskTags = Array.isArray(src.risk_tags) && src.risk_tags.length
            ? src.risk_tags
            : (Array.isArray(sd.risk_tags) ? sd.risk_tags : []);

        return {
            code: src.code || '',
            name: src.name || '',
            date: src.date || '',
            source: src.source || '',
            summary: {
                total: this._fmt(total, 1),
                minScore: this._fmt(minScore, 0),
                buy: yn(buy),
                filterOk: filterOk == null ? '--' : (filterOk ? '通过' : '未通过'),
                filterReason: filterReason && filterReason !== 'ok' ? String(filterReason) : '',
                scoreOk: scoreOk == null ? '--' : yn(scoreOk),
            },
            buyLogic: {
                formula: (buyLogic && buyLogic.formula) || '买点 = 硬筛全部通过 AND 得分≥最低得分',
                formulaDetail: (buyLogic && buyLogic.formula_detail)
                    || '硬筛含：站上MA20、连阳（4日≥3阳或5日≥4阳）、放量倍数；可选换手/量比。通过后再要求得分达标。',
                steps: buySteps,
                conclusion: `硬筛 ${filterOk == null ? '--' : (filterOk ? '通过' : '未通过')}，得分达标 ${scoreOk == null ? '--' : yn(scoreOk)} → 买点 ${yn(buy)}`,
            },
            scoreRows,
            inputs: [
                ['开', this._fmt(open, 2)],
                ['收', this._fmt(close, 2)],
                ['MA5', this._fmt(ma5, 2)],
                ['MA10', this._fmt(ma10, 2)],
                ['MA20', this._fmt(ma20, 2)],
                ['10/15/20阳', `${yang10 != null ? yang10 : '--'}/${yang15 != null ? yang15 : '--'}/${yang20 != null ? yang20 : '--'}`],
                ['量能倍数', this._fmt(vm, 2)],
                ['量比', this._fmt(vr, 2)],
                ['换手%', this._fmt(to, 2)],
                ...(toMed != null ? [['换手中位%', this._fmt(toMed, 2)]] : []),
            ],
            structure: {
                nearestSupport: this._fmt(nearSup, 2),
                nearestResistance: this._fmt(nearRes, 2),
                rr: structureRr != null && Number.isFinite(Number(structureRr))
                    ? Number(structureRr).toFixed(2)
                    : '--',
                rrFloored: structureRrFloored,
                rrReason: structureRrReason && structureRrReason !== 'ok' ? structureRrReason : '',
                kde: kdeOk == null ? '--' : (kdeOk ? '成功' : '未识别'),
                lookback: lookbackUsed != null ? String(lookbackUsed) : '--',
                kdeReason: kdeReason || '',
                resists: resists.length ? resists.map((x) => this._fmt(x, 2)).join('、') : '--',
                supports: supports.length ? supports.map((x) => this._fmt(x, 2)).join('、') : '--',
            },
            advice: adviceBlock,
            riskTags: riskTags.map((t) => ({
                label: (t && (t.label || t.id)) || '风险',
                level: (t && t.level) || 'info',
                reason: String((t && t.reason) || ''),
            })),
        };
    },
};

if (typeof window !== 'undefined') {
    window.UrtScoreDetail = UrtScoreDetail;
}

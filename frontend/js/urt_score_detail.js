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

        const ma = parts.above_ma20 || {};
        const yang = parts.yang || {};
        const yangMed = parts.yang_medium || {};
        const maBull = parts.ma_bull || {};
        const vol = parts.volume || {};
        const turnover = parts.turnover || {};
        const vRatio = parts.volume_ratio || {};

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
        html += '<table class="gms-weight-table"><thead><tr><th>分项</th><th>得分</th><th>满分</th><th>说明</th></tr></thead><tbody>';
        const rows = [
            {
                name: '站上 MA20',
                score: ma.score,
                max: ma.max != null ? ma.max : 10,
                note: ma.ok === true ? '收盘 ≥ MA20' : (ma.ok === false ? '未站上' : '--'),
            },
            {
                name: '连阳强度',
                score: yang.score != null ? yang.score : null,
                max: yang.max != null ? yang.max : 40,
                note: `4日阳 ${yang.yang_count_4 != null ? yang.yang_count_4 : (yang4 != null ? yang4 : '--')} · 5日阳 ${yang.yang_count_5 != null ? yang.yang_count_5 : (yang5 != null ? yang5 : '--')}`,
            },
            {
                name: '中期阳线',
                score: yangMed.score,
                max: yangMed.max != null ? yangMed.max : 6,
                note: `10日 ${yang10 != null ? yang10 : '--'} · 15日 ${yang15 != null ? yang15 : '--'} · 20日 ${yang20 != null ? yang20 : '--'}${yangMed.ok === true ? '（达标）' : (yangMed.ok === false ? '（未达标）' : '')}`,
            },
            {
                name: '均线多头',
                score: maBull.score,
                max: maBull.max != null ? maBull.max : 4,
                note: `MA5 ${this._fmt(maBull.ma5 != null ? maBull.ma5 : ma5, 2)} · MA10 ${this._fmt(maBull.ma10 != null ? maBull.ma10 : ma10, 2)} · ${(maBull.ok === true || maBullOk === true) ? '多头' : ((maBull.ok === false || maBullOk === false) ? '非多头' : '--')}`,
            },
            {
                name: '量能倍数',
                score: vol.score,
                max: vol.max != null ? vol.max : 34,
                note: `倍数 ${this._fmt(vol.volume_multiple != null ? vol.volume_multiple : vm, 2)} / 阈值 ${this._fmt(vol.threshold, 2)}`,
            },
            {
                name: '换手率',
                score: turnover.score,
                max: turnover.max != null ? turnover.max : 0,
                note: turnover.enabled === false ? '未启用' : `换手 ${this._fmt(turnover.turnover_rate != null ? turnover.turnover_rate : to, 2)}%`,
            },
            {
                name: '量比',
                score: vRatio.score,
                max: vRatio.max != null ? vRatio.max : 0,
                note: vRatio.enabled === false ? '未启用' : `量比 ${this._fmt(vRatio.volume_ratio != null ? vRatio.volume_ratio : vr, 2)}`,
            },
        ];
        rows.forEach((r) => {
            html += `<tr><td>${r.name}</td><td>${this._fmt(r.score, 2)}</td><td>${r.max}</td><td>${r.note}</td></tr>`;
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
};

if (typeof window !== 'undefined') {
    window.UrtScoreDetail = UrtScoreDetail;
}

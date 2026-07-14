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

        const total = src.score != null ? src.score : sd.total;
        const minScore = sd.min_score != null ? sd.min_score : 70;
        const buy = src.buy_signal;
        const filterOk = fields.filter_ok != null ? fields.filter_ok : src.filter_ok;
        const filterReason = fields.filter_reason != null ? fields.filter_reason : src.filter_reason;
        const scoreOk = fields.score_ok != null ? fields.score_ok : src.score_ok;

        const close = fields.close != null ? fields.close : (src.close != null ? src.close : inputs.close);
        const open = fields.open != null ? fields.open : (src.open != null ? src.open : inputs.open);
        const ma20 = fields.ma20 != null ? fields.ma20 : (src.ma20 != null ? src.ma20 : inputs.ma20);
        const yang4 = fields.yang_count_4 != null ? fields.yang_count_4 : src.yang_count_4;
        const yang5 = fields.yang_count_5 != null ? fields.yang_count_5 : src.yang_count_5;
        const vm = fields.volume_multiple != null ? fields.volume_multiple : src.volume_multiple;
        const vr = fields.volume_ratio != null ? fields.volume_ratio : src.volume_ratio;
        const to = fields.turnover_rate != null ? fields.turnover_rate : src.turnover_rate;

        const ma = parts.above_ma20 || {};
        const yang = parts.yang || {};
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
        if (filterOk != null) html += `<span>硬筛 ${filterOk ? '通过' : '未通过'}${filterReason ? `（${filterReason}）` : ''}</span>`;
        if (scoreOk != null) html += `<span>得分达标 ${scoreOk ? '是' : '否'}</span>`;
        html += '</div></div>';

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
                name: '量能倍数',
                score: vol.score,
                max: vol.max != null ? vol.max : 40,
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
        html += `<span>MA20 ${this._fmt(ma20, 2)}</span>`;
        html += `<span>量能倍数 ${this._fmt(vm, 2)}</span>`;
        html += `<span>量比 ${this._fmt(vr, 2)}</span>`;
        html += `<span>换手 ${this._fmt(to, 2)}%</span>`;
        html += '</div></div>';

        html += '</div>';
        return html;
    },
};

if (typeof window !== 'undefined') {
    window.UrtScoreDetail = UrtScoreDetail;
}

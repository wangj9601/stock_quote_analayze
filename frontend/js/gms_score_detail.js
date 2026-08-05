/**
 * GMS 得分明细 HTML 构建（选股页 / 信号追溯页共用）
 */
const GmsScoreDetail = {
    buildHtml(sd, meta, fallbackConfigId) {
        if (!sd || typeof sd !== 'object') sd = {};
        meta = meta && typeof meta === 'object' ? meta : {};
        const cfgName = sd.strategy_config_name || meta.strategy_config_name || '—';
        const cfgId = sd.strategy_config_id || meta.strategy_config_id || fallbackConfigId;
        const mechLabel = sd.scoring_mechanism_label || meta.scoring_mechanism_label || '';
        const mechId = sd.scoring_mechanism || meta.scoring_mechanism || 'tiered_dual_max';
        const gmsFmt = (v, type) => {
            if (v == null || (typeof v === 'number' && isNaN(v))) return '--';
            if (type === 'pct') return (v * 100).toFixed(2) + '%';
            if (type === 'int') return String(Math.round(v));
            if (type === 'vol') return (v >= 10000 ? (v / 10000).toFixed(2) + '万手' : Number(v).toFixed(0) + '手');
            if (type === 'price') return typeof v === 'number' ? v.toFixed(2) : String(v);
            if (type === 'ratio') return typeof v === 'number' ? v.toFixed(2) : String(v);
            if (type === 'num') return typeof v === 'number' ? v.toFixed(4) : String(v);
            return String(v);
        };
        const accS = (sd.accumulation_s_threshold != null && !isNaN(sd.accumulation_s_threshold)) ? sd.accumulation_s_threshold : 85;
        const accA = (sd.accumulation_a_threshold != null && !isNaN(sd.accumulation_a_threshold)) ? sd.accumulation_a_threshold : 70;
        const momFull = (sd.momentum_full_threshold != null && !isNaN(sd.momentum_full_threshold)) ? sd.momentum_full_threshold : 90;
        const momBatch = (sd.momentum_batch_threshold != null && !isNaN(sd.momentum_batch_threshold)) ? sd.momentum_batch_threshold : 80;
        const fzTiers = sd.acc_fz_tiers || [2.5, 1.5];
        const balTiers = sd.balance_tiers || [0.01, 0.015];
        const volShrink = sd.vol_shrink_tiers || [0.6, 0.8];
        const ratioD1Tiers = sd.ratio_d1_tiers || [0.001, 0.03];
        const volAttack = sd.vol_attack_tiers || [2.0, 1.5];
        const wAccFz = (sd.weight_acc_fz != null && !isNaN(sd.weight_acc_fz)) ? sd.weight_acc_fz : 30;
        const wAccBal = (sd.weight_acc_balance != null && !isNaN(sd.weight_acc_balance)) ? sd.weight_acc_balance : 40;
        const wAccVol = (sd.weight_acc_volume != null && !isNaN(sd.weight_acc_volume)) ? sd.weight_acc_volume : 30;
        const wMomD1 = (sd.weight_mom_ratio_d1 != null && !isNaN(sd.weight_mom_ratio_d1)) ? sd.weight_mom_ratio_d1 : 40;
        const wMomDev = (sd.weight_mom_deviation != null && !isNaN(sd.weight_mom_deviation)) ? sd.weight_mom_deviation : 30;
        const wMomVol = (sd.weight_mom_volume != null && !isNaN(sd.weight_mom_volume)) ? sd.weight_mom_volume : 30;
        let gmsDominantHint = '';
        const _acc = sd.score_accumulation;
        const _mom = sd.score_momentum;
        const _an = (_acc != null && !isNaN(_acc)) ? Number(_acc) : NaN;
        const _mn = (_mom != null && !isNaN(_mom)) ? Number(_mom) : NaN;
        if (!isNaN(_an) || !isNaN(_mn)) {
            if (!isNaN(_an) && !isNaN(_mn)) {
                if (_an > _mn) gmsDominantHint = '当前主导：均值收敛态（蓄势）。';
                else if (_mn > _an) gmsDominantHint = '当前主导：动量溢出态。';
                else gmsDominantHint = '两模块小计相同。';
            } else if (!isNaN(_an)) gmsDominantHint = '当前主导：均值收敛态（蓄势）。';
            else gmsDominantHint = '当前主导：动量溢出态。';
        }
        const baseTotal = (sd.score_base_total != null && !isNaN(sd.score_base_total))
            ? Number(sd.score_base_total)
            : Math.max(_an || 0, _mn || 0);
        const penaltyDeduction = (sd.score_penalty_deduction != null && !isNaN(sd.score_penalty_deduction))
            ? Number(sd.score_penalty_deduction)
            : 0;
        const penalties = Array.isArray(sd.penalties) ? sd.penalties : [];
        const riskTags = Array.isArray(sd.risk_tags) ? sd.risk_tags : [];
        const riskTagsHtml = riskTags.length
            ? `<div class="gms-score-detail-section"><strong>【风险提示】</strong><div class="gms-risk-tags">${riskTags.map((t) => `<span class="gms-risk-tag gms-risk-${t.level || 'info'}" title="${(t.reason || '').replace(/"/g, '&quot;')}">${t.label || t.id}</span>`).join('')}</div></div>`
            : '';
        const closePrice = sd.d20 != null ? sd.d20 : (sd.d != null && sd.instant_deviation != null ? sd.d + sd.instant_deviation : null);
        const ma60FlatLookback = sd.ma60_flat_lookback_days != null ? sd.ma60_flat_lookback_days : 20;
        let ma60Hint = '60日移动平均线';
        if (sd.ma60_d != null && closePrice != null) {
            ma60Hint += closePrice < sd.ma60_d ? '；当前收盘低于 MA60' : '；当前收盘高于/等于 MA60';
        }
        if (sd.ma60_flat === true) {
            const chg = sd.ma60_flat_change_pct != null ? (Number(sd.ma60_flat_change_pct) * 100).toFixed(2) + '%' : '--';
            ma60Hint += `；MA60 走平（${ma60FlatLookback}日变化 ${chg}）`;
        } else if (sd.ma60_flat === false) {
            const chg = sd.ma60_flat_change_pct != null ? (Number(sd.ma60_flat_change_pct) * 100).toFixed(2) + '%' : '--';
            ma60Hint += `；MA60 非走平（${ma60FlatLookback}日变化 ${chg}）`;
        }
        const formatPenaltyCondition = (p) => {
            if (p.id === 'close_below_ma60') {
                let cond = 'd₂₀ &lt; ma60_d';
                if (p.ma60_flat) cond += '；MA60 走平，扣分减半';
                if (p.base_points != null && p.points != null && Number(p.points) !== Number(p.base_points)) {
                    cond += `（${p.base_points}→${p.points}）`;
                }
                return cond;
            }
            if (p.id === 'observation_range_amplitude') {
                const th = p.amplitude_threshold_pct != null ? (Number(p.amplitude_threshold_pct) * 100).toFixed(1) + '%' : '30%';
                const amp = p.observation_range_amplitude_pct != null
                    ? (Number(p.observation_range_amplitude_pct) * 100).toFixed(2) + '%'
                    : (sd.observation_range_amplitude_pct != null
                        ? (Number(sd.observation_range_amplitude_pct) * 100).toFixed(2) + '%'
                        : '--');
                return `观察周期振幅 ${amp} &gt; ${th}`;
            }
            return '—';
        };
        const versionMetaHtml = `
            <div class="gms-score-detail-section gms-score-detail-meta">
                <strong>策略参数版本</strong>
                <p class="gms-version-meta-line">
                    <span class="gms-version-name">${cfgName}</span>
                    ${cfgId ? `<span class="gms-version-id">config_id=${cfgId}</span>` : ''}
                    ${mechLabel ? `<span class="gms-version-mech">${mechLabel}</span>` : ''}
                </p>
            </div>`;
        let penaltySectionHtml = '';
        if (mechId === 'tiered_dual_penalty' || penaltyDeduction > 0 || penalties.length > 0) {
            const penaltyRows = penalties.length
                ? penalties.map((p) => {
                    const applied = p.applied !== false;
                    const pts = p.points != null ? p.points : 0;
                    return `<tr><td>${p.label || p.id || '减分规则'}</td><td>${applied ? '命中' : '未命中'}</td><td>${applied ? '-' + pts : '0'}</td><td>${formatPenaltyCondition(p)}</td></tr>`;
                }).join('')
                : `<tr><td colspan="4" class="gms-muted">未触发减分规则</td></tr>`;
            penaltySectionHtml = `
                <div class="gms-score-detail-section gms-penalty-section">
                    <strong>【减分项】</strong>
                    <table class="gms-weight-table">
                        <thead><tr><th>规则</th><th>状态</th><th>扣分</th><th>条件</th></tr></thead>
                        <tbody>${penaltyRows}</tbody>
                    </table>
                    <p class="gms-total-hint-text" style="font-size:12px;color:#666;margin:6px 0 0 0;line-height:1.45;">
                        基础分=${baseTotal.toFixed(1)}；减分合计=${penaltyDeduction.toFixed(1)}；最终总分=${sd.score_total != null ? sd.score_total.toFixed(1) : '--'}
                    </p>
                </div>`;
        }
        // 【支撑 / 阻力】成交量加权 KDE（与 URT / RPE 同口径）
        const st = (sd.structure && typeof sd.structure === 'object') ? sd.structure : {};
        const nearSup = sd.nearest_support != null ? sd.nearest_support : st.nearest_support;
        const nearRes = sd.nearest_resistance != null ? sd.nearest_resistance : st.nearest_resistance;
        const supports = Array.isArray(sd.support_levels) && sd.support_levels.length
            ? sd.support_levels
            : (Array.isArray(st.support_levels) ? st.support_levels : []);
        const resists = Array.isArray(sd.resistance_levels) && sd.resistance_levels.length
            ? sd.resistance_levels
            : (Array.isArray(st.resistance_levels) ? st.resistance_levels : []);
        const kdeOk = sd.kde_ok != null ? sd.kde_ok : st.kde_ok;
        const kdeReason = sd.kde_reason || st.kde_reason || '';
        const lookbackUsed = sd.kde_lookback_used != null ? sd.kde_lookback_used : st.kde_lookback_used;
        let structureSectionHtml = '<div class="gms-score-detail-section"><strong>【支撑 / 阻力】</strong>';
        structureSectionHtml += '<div class="gms-version-meta-line">';
        structureSectionHtml += `<span>最近支撑 <strong>${gmsFmt(nearSup, 'price')}</strong></span>`;
        structureSectionHtml += `<span>最近阻力 <strong>${gmsFmt(nearRes, 'price')}</strong></span>`;
        if (kdeOk != null) structureSectionHtml += `<span>KDE ${kdeOk ? '成功' : '未识别'}</span>`;
        if (lookbackUsed != null) structureSectionHtml += `<span>回看 ${lookbackUsed} 日</span>`;
        if (kdeReason) structureSectionHtml += `<span>${kdeReason}</span>`;
        structureSectionHtml += '</div>';
        structureSectionHtml += '<table class="gms-weight-table"><thead><tr><th>类型</th><th>价位（近→远）</th></tr></thead><tbody>';
        structureSectionHtml += `<tr><td>阻力</td><td>${resists.length ? resists.map((x) => gmsFmt(x, 'price')).join('、') : '--'}</td></tr>`;
        structureSectionHtml += `<tr><td>支撑</td><td>${supports.length ? supports.map((x) => gmsFmt(x, 'price')).join('、') : '--'}</td></tr>`;
        structureSectionHtml += '</tbody></table></div>';
        return `
            <div class="gms-score-detail-inner">
                ${versionMetaHtml}
                ${riskTagsHtml}
                <div class="gms-score-detail-section">
                    <strong>【均值收敛态】得分明细</strong>
                    <table class="gms-weight-table">
                        <thead><tr><th>维度</th><th>得分</th><th>判定</th><th>规则</th></tr></thead>
                        <tbody>
                            <tr><td>时间耗散 F/Z</td><td>${(sd.score_acc_fz != null ? sd.score_acc_fz.toFixed(1) : '--')}</td><td class="gms-judge">${sd.acc_fz_judge || '—'}</td><td>权重${wAccFz}: ≥${fzTiers[0]}→满分; [${fzTiers[1]},${fzTiers[0]})→2/3</td></tr>
                            <tr><td>引力粘合 |Δ/d|</td><td>${(sd.score_acc_balance != null ? sd.score_acc_balance.toFixed(1) : '--')}</td><td class="gms-judge">${sd.acc_balance_judge || '—'}</td><td>权重${wAccBal}: ≤${(balTiers[0] * 100).toFixed(1)}%→满分; ≤${(balTiers[1] * 100).toFixed(1)}%→1/2</td></tr>
                            <tr><td>成交量缩 m₂₀/m</td><td>${(sd.score_acc_volume != null ? sd.score_acc_volume.toFixed(1) : '--')}</td><td class="gms-judge">${sd.acc_volume_judge || '—'}</td><td>权重${wAccVol}: ≤${volShrink[0]}→满分; (${volShrink[0]},${volShrink[1]}]→1/2</td></tr>
                            <tr><td>均值收敛态小计</td><td><strong>${sd.score_accumulation != null ? sd.score_accumulation.toFixed(1) : '--'}</strong></td><td colspan="2"><strong>判定: ${sd.accumulation_grade || '—'}</strong> (≥${accS} S; ≥${accA} A)</td></tr>
                        </tbody>
                    </table>
                </div>
                <div class="gms-score-detail-section">
                    <strong>【动量溢出态】得分明细</strong>
                    <table class="gms-weight-table">
                        <thead><tr><th>维度</th><th>得分</th><th>判定</th><th>规则</th></tr></thead>
                        <tbody>
                            <tr><td>盈亏反转 Δ/d₁</td><td>${(sd.score_mom_ratio_d1 != null ? sd.score_mom_ratio_d1.toFixed(1) : '--')}</td><td class="gms-judge">${sd.mom_ratio_d1_judge || '—'}</td><td>权重${wMomD1}: (0,${(ratioD1Tiers[1] * 100).toFixed(1)}%]→满分; 刚过0→1/2</td></tr>
                            <tr><td>推力支撑 d₂₀-d</td><td>${(sd.score_mom_deviation != null ? sd.score_mom_deviation.toFixed(1) : '--')}</td><td class="gms-judge">${sd.mom_deviation_judge || '—'}</td><td>权重${wMomDev}: 站稳3日→满分; 仅当日→1/2; &lt;0→-10</td></tr>
                            <tr><td>攻击强度 m₂₀/m</td><td>${(sd.score_mom_volume != null ? sd.score_mom_volume.toFixed(1) : '--')}</td><td class="gms-judge">${sd.mom_volume_judge || '—'}</td><td>权重${wMomVol}: ≥${volAttack[0]}→满分; [${volAttack[1]},${volAttack[0]})→2/3</td></tr>
                            <tr><td>动量溢出态小计</td><td><strong>${sd.score_momentum != null ? sd.score_momentum.toFixed(1) : '--'}</strong></td><td colspan="2"><strong>判定: ${sd.momentum_grade || '—'}</strong> (≥${momFull}全速; ≥${momBatch}分批)</td></tr>
                        </tbody>
                    </table>
                </div>
                <div class="gms-score-detail-section">
                    <strong>综合</strong> 总分=${sd.score_total != null ? sd.score_total.toFixed(1) : '--'}；信号强度=总分/100
                    <p class="gms-total-hint-text" style="font-size:12px;color:#666;margin:6px 0 0 0;line-height:1.45;">
                        基础分 = max(均值收敛态小计, 动量溢出态小计)，非两模块分数相加。
                        ${penaltyDeduction > 0 ? '<br>最终总分 = 基础分 − 减分合计。' : ''}
                        ${gmsDominantHint ? '<br>' + gmsDominantHint : ''}
                    </p>
                </div>
                ${penaltySectionHtml}
                ${structureSectionHtml}
                <div class="gms-score-detail-section gms-indicators-section">
                    <strong>计算指标细项</strong>
                    <table class="gms-weight-table gms-indicators-table">
                        <tbody>
                            <tr><td>d₁ (首日收盘价)</td><td>${gmsFmt(sd.d1, 'price')}</td><td>周期起点价格${sd.d1_date ? '，交易日期 ' + sd.d1_date : ''}</td></tr>
                            <tr><td>d₂₀ (末日收盘价)</td><td>${gmsFmt(sd.d20, 'price')}</td><td>周期末位/当日价格${sd.d20_date ? '，交易日期 ' + sd.d20_date : ''}</td></tr>
                            <tr><td>MA60 (60日均价)</td><td>${gmsFmt(sd.ma60_d, 'price')}</td><td>${ma60Hint}</td></tr>
                            <tr><td>d (20日均价)</td><td>${gmsFmt(sd.d, 'price')}</td><td>周期均价</td></tr>
                            <tr><td>Δ (d₂₀ - d₁)</td><td>${gmsFmt(sd.delta, 'num')}</td><td>宏观位移</td></tr>
                            <tr><td>Δ/d</td><td>${(sd.delta != null && sd.d != null && sd.d !== 0 ? gmsFmt(sd.delta / sd.d, 'pct') : '--')}</td><td>宏观位移相对均价 (Δ/d)</td></tr>
                            <tr><td>Δ/d₂₀（宏观位移/收盘价）</td><td>${gmsFmt(sd.ratio_d20, 'pct')}</td><td>左侧买点粘合用 |Δ/d₂₀|；≠ 下方均线乖离 Δ₂₀/d</td></tr>
                            <tr><td>Δ/d₁（突变率）</td><td>${gmsFmt(sd.ratio_d1, 'pct')}</td><td>现价相对周期起点位移</td></tr>
                            <tr><td>Δ₂₀/d（均线乖离）</td><td>${gmsFmt(sd.ratio_d, 'pct')}</td><td>(d₂₀−d)/d；不是左侧判定用的 Δ/d₂₀</td></tr>
                            <tr><td>Z (上涨天数)</td><td>${gmsFmt(sd.rising_days, 'int')}</td><td>多头天数</td></tr>
                            <tr><td>F (下跌天数)</td><td>${gmsFmt(sd.falling_days, 'int')}</td><td>空头天数</td></tr>
                            <tr><td>m (20日平均成交量)</td><td>${gmsFmt(sd.avg_volume_20d, 'vol')}</td><td>平均量</td></tr>
                            <tr><td>m₂₀ (当日成交量)</td><td>${gmsFmt(sd.current_volume, 'vol')}</td><td>当日成交量</td></tr>
                            <tr><td>量比 (m₂₀/m)</td><td>${gmsFmt(sd.volume_ratio, 'ratio')}</td><td>放量/地量判断</td></tr>
                            <tr><td>F/Z (数方比)</td><td>${gmsFmt(sd.fz_ratio, 'ratio')}</td><td>蓄势判断</td></tr>
                            <tr><td>d₂₀ - d (价格vs均线)</td><td>${gmsFmt(sd.instant_deviation, 'num')}</td><td>价格相对均线偏离</td></tr>
                            <tr><td>观察周期最高/最低</td><td>${gmsFmt(sd.observation_period_high, 'price')} / ${gmsFmt(sd.observation_period_low, 'price')}</td><td>${sd.observation_range_period_days != null ? sd.observation_range_period_days + ' 个交易日' : '观察周期内极值'}</td></tr>
                            <tr><td>观察周期振幅 (高−低)/高</td><td>${gmsFmt(sd.observation_range_amplitude_pct, 'pct')}</td><td>减分规则「观察周期振幅过大」判定依据</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    },
};

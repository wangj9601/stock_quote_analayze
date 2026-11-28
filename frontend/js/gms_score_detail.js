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
        const normalizeRiskTag = (t) => {
            if (t == null) return null;
            if (typeof t === 'string') {
                const id = t.trim();
                if (!id || id === 'undefined' || id === 'null') return null;
                const known = { board_weak: '主行业板走弱' };
                return { id, label: known[id] || id, level: 'warn', reason: id };
            }
            if (typeof t !== 'object') return null;
            const id = (t.id != null && String(t.id).trim()) ? String(t.id).trim() : '';
            const label = (t.label != null && String(t.label).trim()) ? String(t.label).trim() : '';
            if (!id && !label) return null;
            if (id === 'undefined' || label === 'undefined') return null;
            return {
                id: id || label,
                label: label || id,
                level: t.level || 'info',
                reason: t.reason != null ? String(t.reason) : '',
            };
        };
        const riskTags = (Array.isArray(sd.risk_tags) ? sd.risk_tags : [])
            .map(normalizeRiskTag)
            .filter(Boolean);
        const riskTagsHtml = riskTags.length
            ? `<div class="gms-sd-risk"><span class="gms-sd-kicker">风险提示</span><div class="gms-risk-tags">${riskTags.map((t) => `<span class="gms-risk-tag gms-risk-${t.level || 'info'}" title="${(t.reason || '').replace(/"/g, '&quot;')}">${t.label || t.id}</span>`).join('')}</div></div>`
            : '';
        const isWeekly = String(sd.timeframe || meta.timeframe || '').toLowerCase() === 'weekly';
        const closePrice = sd.d20 != null ? sd.d20 : (sd.d != null && sd.instant_deviation != null ? sd.d + sd.instant_deviation : null);
        const ma60FlatLookback = sd.ma60_flat_lookback_days != null ? sd.ma60_flat_lookback_days : 20;
        const maLabel = isWeekly ? '周线均线' : 'MA60';
        let ma60Hint = isWeekly ? '周线均线（策略默认约 12 周）' : '60日移动平均线';
        if (sd.ma60_d != null && closePrice != null) {
            ma60Hint += closePrice < sd.ma60_d ? `；当前收盘低于 ${maLabel}` : `；当前收盘高于/等于 ${maLabel}`;
        }
        if (sd.ma60_flat === true) {
            const chg = sd.ma60_flat_change_pct != null ? (Number(sd.ma60_flat_change_pct) * 100).toFixed(2) + '%' : '--';
            ma60Hint += `；${maLabel} 走平（${ma60FlatLookback}${isWeekly ? '周' : '日'}变化 ${chg}）`;
        } else if (sd.ma60_flat === false) {
            const chg = sd.ma60_flat_change_pct != null ? (Number(sd.ma60_flat_change_pct) * 100).toFixed(2) + '%' : '--';
            ma60Hint += `；${maLabel} 非走平（${ma60FlatLookback}${isWeekly ? '周' : '日'}变化 ${chg}）`;
        }
        const metricCell = (label, value, hint) =>
            `<div class="gms-sd-metric"><span class="gms-sd-metric-label">${label}</span><span class="gms-sd-metric-value">${value}</span><span class="gms-sd-metric-hint">${hint || ''}</span></div>`;
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
            if (p.id === 'poor_structure_rr') {
                const minRr = p.min_rr != null ? Number(p.min_rr).toFixed(2) : '1.50';
                const rr = p.rr != null ? Number(p.rr).toFixed(2) : '--';
                const reason = p.rr_reason || '';
                if (reason === 'below_or_no_support' || reason === 'zero_downside') {
                    return `现价破位支撑（要求 RR≥${minRr}）`;
                }
                if (reason === 'at_resistance') {
                    return `现价贴/超阻力 RR=${rr}（要求 ≥${minRr}）`;
                }
                return `结构盈亏比 RR=${rr} &lt; ${minRr}`;
            }
            if (p.id === 'board_weak') {
                const slope = (p.sector_slope != null && Number.isFinite(Number(p.sector_slope)))
                    ? Number(p.sector_slope).toFixed(4)
                    : '--';
                const chg = p.board_change_percent != null
                    ? (Number(p.board_change_percent).toFixed(2) + '%')
                    : '--';
                const board = p.primary_board_name || p.primary_board_code || '';
                const why = p.board_weak_reason || '';
                return `主行业板${board ? ' ' + board : ''} 斜率=${slope} 涨跌=${chg}${why ? '（' + why + '）' : ''}`;
            }
            return '—';
        };
        const versionMetaHtml = `
            <div class="gms-score-detail-meta gms-sd-version">
                <span class="gms-sd-kicker">策略参数版本</span>
                <p class="gms-version-meta-line">
                    <span class="gms-version-name">${cfgName}</span>
                    ${cfgId ? `<span class="gms-version-id">config_id=${cfgId}</span>` : ''}
                    ${mechLabel ? `<span class="gms-version-mech">${mechLabel}</span>` : ''}
                    ${isWeekly ? '<span class="gms-version-mech">周线</span>' : ''}
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
                <section class="gms-sd-block gms-penalty-section">
                    <h4 class="gms-sd-block-title">减分项</h4>
                    <div class="gms-sd-table-wrap">
                    <table class="gms-weight-table">
                        <thead><tr><th>规则</th><th>状态</th><th>扣分</th><th>条件</th></tr></thead>
                        <tbody>${penaltyRows}</tbody>
                    </table>
                    </div>
                    <p class="gms-total-hint-text">
                        基础分=${baseTotal.toFixed(1)}；减分合计=${penaltyDeduction.toFixed(1)}；最终总分=${sd.score_total != null ? sd.score_total.toFixed(1) : '--'}
                    </p>
                </section>`;
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
        const structureRr = sd.structure_rr != null ? sd.structure_rr
            : (st.rr != null ? st.rr : null);
        const structureRrReason = sd.structure_rr_reason || st.rr_reason || '';
        const structureRrFloored = !!(sd.structure_rr_downside_floored
            || st.rr_downside_floored);
        const structureMetaBits = [];
        if (structureRrFloored) structureMetaBits.push('<span title="贴支撑时分母已按现价比例下限计算">已用分母下限</span>');
        if (structureRrReason && structureRrReason !== 'ok') structureMetaBits.push(`<span>${structureRrReason}</span>`);
        if (kdeOk != null) structureMetaBits.push(`<span>KDE ${kdeOk ? '成功' : '未识别'}</span>`);
        if (lookbackUsed != null) structureMetaBits.push(`<span>回看 ${lookbackUsed}${isWeekly ? ' 周' : ' 日'}</span>`);
        if (kdeReason) structureMetaBits.push(`<span>${kdeReason}</span>`);
        const structureSectionHtml = `
            <section class="gms-sd-block">
                <h4 class="gms-sd-block-title">支撑 / 阻力</h4>
                <div class="gms-sd-kv">
                    <div class="gms-sd-kv-item"><span class="gms-sd-kv-label">最近支撑</span><strong>${gmsFmt(nearSup, 'price')}</strong></div>
                    <div class="gms-sd-kv-item"><span class="gms-sd-kv-label">最近阻力</span><strong>${gmsFmt(nearRes, 'price')}</strong></div>
                    <div class="gms-sd-kv-item"><span class="gms-sd-kv-label">盈亏比 RR</span><strong>${structureRr != null ? Number(structureRr).toFixed(2) : '--'}</strong></div>
                </div>
                ${structureMetaBits.length ? `<div class="gms-version-meta-line gms-sd-meta-bits">${structureMetaBits.join('')}</div>` : ''}
                <div class="gms-sd-table-wrap">
                <table class="gms-weight-table">
                    <thead><tr><th>类型</th><th>价位（近→远）</th></tr></thead>
                    <tbody>
                        <tr><td>阻力</td><td>${resists.length ? resists.map((x) => gmsFmt(x, 'price')).join('、') : '--'}</td></tr>
                        <tr><td>支撑</td><td>${supports.length ? supports.map((x) => gmsFmt(x, 'price')).join('、') : '--'}</td></tr>
                    </tbody>
                </table>
                </div>
            </section>`;
        const br = (sd.board_resonance && typeof sd.board_resonance === 'object') ? sd.board_resonance : {};
        const envLabel = br.board_env_label
            || (br.board_strong ? '走强' : (br.board_weak ? '走弱' : '正常/未知'));
        const boardSectionHtml = `
            <section class="gms-sd-block">
                <h4 class="gms-sd-block-title">行业板共振</h4>
                <div class="gms-sd-kv">
                    <div class="gms-sd-kv-item"><span class="gms-sd-kv-label">主行业板</span><strong>${br.primary_board_name || br.primary_board_code || '--'}</strong></div>
                    <div class="gms-sd-kv-item"><span class="gms-sd-kv-label">斜率(ln)</span><strong>${(br.sector_slope != null && Number.isFinite(Number(br.sector_slope))) ? Number(br.sector_slope).toFixed(4) : '--'}</strong></div>
                    <div class="gms-sd-kv-item"><span class="gms-sd-kv-label">当日涨跌</span><strong>${br.board_change_percent != null ? Number(br.board_change_percent).toFixed(2) + '%' : '--'}</strong></div>
                    <div class="gms-sd-kv-item"><span class="gms-sd-kv-label">环境</span><strong>${envLabel}</strong></div>
                    <div class="gms-sd-kv-item"><span class="gms-sd-kv-label">资金流</span><strong>${br.enable_board_fund_flow && br.board_main_net_inflow != null ? br.board_main_net_inflow : '暂无（二期）'}</strong></div>
                </div>
                ${br.board_weak_reason ? `<p class="gms-total-hint-text">${br.board_weak_reason}</p>` : ''}
            </section>`;
        const deltaOverD = (sd.delta != null && sd.d != null && sd.d !== 0)
            ? gmsFmt(sd.delta / sd.d, 'pct')
            : '--';
        const indicatorsHtml = `
            <section class="gms-sd-block gms-indicators-section">
                <h4 class="gms-sd-block-title">计算指标细项</h4>
                <div class="gms-sd-metric-grid">
                    ${metricCell('d₁ 首日收盘', gmsFmt(sd.d1, 'price'), sd.d1_date ? `交易日 ${sd.d1_date}` : '周期起点')}
                    ${metricCell('d₂₀ 末日收盘', gmsFmt(sd.d20, 'price'), sd.d20_date ? `交易日 ${sd.d20_date}` : '周期末位')}
                    ${metricCell(isWeekly ? '周线均线' : 'MA60', gmsFmt(sd.ma60_d, 'price'), ma60Hint)}
                    ${metricCell(isWeekly ? 'd 周均价' : 'd 20日均价', gmsFmt(sd.d, 'price'), '周期均价')}
                    ${metricCell('Δ (d₂₀−d₁)', gmsFmt(sd.delta, 'num'), '宏观位移')}
                    ${metricCell('Δ/d', deltaOverD, '宏观位移相对均价')}
                    ${metricCell('Δ/d₂₀', gmsFmt(sd.ratio_d20, 'pct'), '左侧粘合用 |Δ/d₂₀|')}
                    ${metricCell('Δ/d₁', gmsFmt(sd.ratio_d1, 'pct'), '相对周期起点位移')}
                    ${metricCell('Δ₂₀/d', gmsFmt(sd.ratio_d, 'pct'), '均线乖离 (d₂₀−d)/d')}
                    ${metricCell('Z 上涨', gmsFmt(sd.rising_days, 'int'), '多头天数')}
                    ${metricCell('F 下跌', gmsFmt(sd.falling_days, 'int'), '空头天数')}
                    ${metricCell('m 均量', gmsFmt(sd.avg_volume_20d, 'vol'), '平均成交量')}
                    ${metricCell('m₂₀ 当日量', gmsFmt(sd.current_volume, 'vol'), '当日成交量')}
                    ${metricCell('量比 m₂₀/m', gmsFmt(sd.volume_ratio, 'ratio'), '放量/地量')}
                    ${metricCell('F/Z', gmsFmt(sd.fz_ratio, 'ratio'), '蓄势判断')}
                    ${metricCell('d₂₀−d', gmsFmt(sd.instant_deviation, 'num'), '价格相对均线')}
                    ${metricCell('观察高低', `${gmsFmt(sd.observation_period_high, 'price')} / ${gmsFmt(sd.observation_period_low, 'price')}`, sd.observation_range_period_days != null ? `${sd.observation_range_period_days} 个交易日` : '观察周期极值')}
                    ${metricCell('观察振幅', gmsFmt(sd.observation_range_amplitude_pct, 'pct'), '减分规则依据')}
                </div>
            </section>`;
        return `
            <div class="gms-score-detail-inner">
                <header class="gms-sd-head">
                    ${versionMetaHtml}
                    ${riskTagsHtml}
                </header>
                <div class="gms-sd-summary">
                    <div class="gms-sd-summary-main">
                        <span class="gms-sd-kicker">综合</span>
                        <span class="gms-sd-total">总分 <strong>${sd.score_total != null ? sd.score_total.toFixed(1) : '--'}</strong></span>
                        <span class="gms-sd-strength">信号强度 ${sd.score_total != null ? (sd.score_total / 100).toFixed(2) : '--'}</span>
                    </div>
                    <p class="gms-total-hint-text">
                        基础分 = max(均值收敛态, 动量溢出态)，非两模块相加。
                        ${penaltyDeduction > 0 ? '最终总分 = 基础分 − 减分合计。' : ''}
                        ${gmsDominantHint || ''}
                    </p>
                </div>
                <div class="gms-sd-modules">
                    <section class="gms-sd-block gms-sd-module">
                        <h4 class="gms-sd-block-title">均值收敛态 <span class="gms-sd-subtotal">${sd.score_accumulation != null ? sd.score_accumulation.toFixed(1) : '--'} · ${sd.accumulation_grade || '—'}</span></h4>
                        <div class="gms-sd-table-wrap">
                        <table class="gms-weight-table">
                            <thead><tr><th>维度</th><th>得分</th><th>判定</th><th>规则</th></tr></thead>
                            <tbody>
                                <tr><td>时间耗散 F/Z</td><td>${(sd.score_acc_fz != null ? sd.score_acc_fz.toFixed(1) : '--')}</td><td class="gms-judge">${sd.acc_fz_judge || '—'}</td><td>权重${wAccFz}: ≥${fzTiers[0]}→满分; [${fzTiers[1]},${fzTiers[0]})→2/3</td></tr>
                                <tr><td>引力粘合 |Δ/d|</td><td>${(sd.score_acc_balance != null ? sd.score_acc_balance.toFixed(1) : '--')}</td><td class="gms-judge">${sd.acc_balance_judge || '—'}</td><td>权重${wAccBal}: ≤${(balTiers[0] * 100).toFixed(1)}%→满分; ≤${(balTiers[1] * 100).toFixed(1)}%→1/2</td></tr>
                                <tr><td>成交量缩 m₂₀/m</td><td>${(sd.score_acc_volume != null ? sd.score_acc_volume.toFixed(1) : '--')}</td><td class="gms-judge">${sd.acc_volume_judge || '—'}</td><td>权重${wAccVol}: ≤${volShrink[0]}→满分; (${volShrink[0]},${volShrink[1]}]→1/2</td></tr>
                                <tr class="gms-sd-subtotal-row"><td>小计</td><td><strong>${sd.score_accumulation != null ? sd.score_accumulation.toFixed(1) : '--'}</strong></td><td colspan="2">≥${accS} S；≥${accA} A</td></tr>
                            </tbody>
                        </table>
                        </div>
                    </section>
                    <section class="gms-sd-block gms-sd-module">
                        <h4 class="gms-sd-block-title">动量溢出态 <span class="gms-sd-subtotal">${sd.score_momentum != null ? sd.score_momentum.toFixed(1) : '--'} · ${sd.momentum_grade || '—'}</span></h4>
                        <div class="gms-sd-table-wrap">
                        <table class="gms-weight-table">
                            <thead><tr><th>维度</th><th>得分</th><th>判定</th><th>规则</th></tr></thead>
                            <tbody>
                                <tr><td>盈亏反转 Δ/d₁</td><td>${(sd.score_mom_ratio_d1 != null ? sd.score_mom_ratio_d1.toFixed(1) : '--')}</td><td class="gms-judge">${sd.mom_ratio_d1_judge || '—'}</td><td>权重${wMomD1}: (0,${(ratioD1Tiers[1] * 100).toFixed(1)}%]→满分; 刚过0→1/2</td></tr>
                                <tr><td>推力支撑 d₂₀-d</td><td>${(sd.score_mom_deviation != null ? sd.score_mom_deviation.toFixed(1) : '--')}</td><td class="gms-judge">${sd.mom_deviation_judge || '—'}</td><td>权重${wMomDev}: 站稳3日→满分; 仅当日→1/2; &lt;0→-10</td></tr>
                                <tr><td>攻击强度 m₂₀/m</td><td>${(sd.score_mom_volume != null ? sd.score_mom_volume.toFixed(1) : '--')}</td><td class="gms-judge">${sd.mom_volume_judge || '—'}</td><td>权重${wMomVol}: ≥${volAttack[0]}→满分; [${volAttack[1]},${volAttack[0]})→2/3</td></tr>
                                <tr class="gms-sd-subtotal-row"><td>小计</td><td><strong>${sd.score_momentum != null ? sd.score_momentum.toFixed(1) : '--'}</strong></td><td colspan="2">≥${momFull}全速；≥${momBatch}分批</td></tr>
                            </tbody>
                        </table>
                        </div>
                    </section>
                </div>
                ${penaltySectionHtml}
                <div class="gms-sd-context">
                    ${structureSectionHtml}
                    ${boardSectionHtml}
                </div>
                ${indicatorsHtml}
            </div>
        `;
    },
};

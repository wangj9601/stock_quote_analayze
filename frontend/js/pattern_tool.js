/** 技术工具 · 形态识别 */
const PatternTool = {
  selectedBoards: [],
  _catalog: { industry: [], concept: [] },
  _labels: {},

  TYPE_LABELS: {
    double_bottom: '双底',
    double_top: '双顶',
    head_shoulders_top: '头肩顶',
    head_shoulders_bottom: '头肩底',
    ascending_triangle: '上升三角',
    descending_triangle: '下降三角',
    symmetrical_triangle: '对称三角',
    rising_wedge: '上升楔形',
    falling_wedge: '下降楔形',
    bull_flag: '上升旗形',
    bear_flag: '下降旗形',
    cup_with_handle: '带柄茶杯',
  },

  PIVOT_ROLE_LABELS: {
    LS: '左肩',
    head: '头',
    RS: '右肩',
    L1: 'L1',
    L2: 'L2',
    H1: 'H1',
    H2: 'H2',
    neck: '颈线',
    left_rim: '左沿',
    right_rim: '右沿',
    cup_bottom: '杯底',
    handle_low: '柄低',
    high: '高点',
    low: '低点',
  },

  init() {
    const mode = document.getElementById('patternModeSelect');
    const scope = document.getElementById('patternScanScope');
    const runBtn = document.getElementById('patternRunBtn');
    const codeInput = document.getElementById('patternStockCode');
    const watch = document.getElementById('patternWatchlist');
    const pickBtn = document.getElementById('patternBoardPickBtn');

    if (mode) mode.addEventListener('change', () => this.syncModeUi());
    if (scope) scope.addEventListener('change', () => this.syncModeUi());
    if (runBtn) runBtn.addEventListener('click', () => this.run());
    if (codeInput) {
      codeInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          this.run();
        }
      });
    }
    if (watch) {
      watch.addEventListener('change', () => {
        const v = (watch.value || '').trim();
        if (v && codeInput) codeInput.value = v;
      });
    }
    if (pickBtn) pickBtn.addEventListener('click', () => this.openBoardPicker());
    this.syncModeUi();
  },

  syncModeUi() {
    const mode = (document.getElementById('patternModeSelect') || {}).value || 'single';
    const scope = (document.getElementById('patternScanScope') || {}).value || 'market';
    const single = document.getElementById('patternSingleFields');
    const watch = document.getElementById('patternWatchField');
    const scan = document.getElementById('patternScanFields');
    const boardWrap = document.getElementById('patternBoardPickWrap');
    if (single) single.style.display = mode === 'single' ? '' : 'none';
    if (watch) watch.style.display = mode === 'single' ? '' : 'none';
    // contents：扫描子字段并入主行 flex，避免整列竖排
    if (scan) scan.style.display = mode === 'scan' ? 'contents' : 'none';
    if (boardWrap) boardWrap.style.display = mode === 'scan' && scope !== 'market' ? '' : 'none';
  },

  async loadWatchlist() {
    const select = document.getElementById('patternWatchlist');
    if (!select || select.dataset.loaded === '1') return;
    if (!window.CommonUtils || !CommonUtils.checkLoginAndHandleExpiry()) return;
    try {
      const resp = await authFetch(`${API_BASE_URL}/api/watchlist`);
      if (!resp.ok) return;
      const payload = await resp.json();
      const items = payload.data || payload.items || payload || [];
      const list = Array.isArray(items) ? items : [];
      list.forEach((it) => {
        const code = it.stock_code || it.code || '';
        const name = it.stock_name || it.name || '';
        if (!code) return;
        const opt = document.createElement('option');
        opt.value = code;
        opt.textContent = `${code} ${name}`.trim();
        select.appendChild(opt);
      });
      select.dataset.loaded = '1';
    } catch (e) {
      console.warn(e);
    }
  },

  selectedTypes() {
    const box = document.getElementById('patternTypeChecks');
    if (!box) return [];
    return Array.from(box.querySelectorAll('input[type=checkbox]:checked')).map((el) => el.value);
  },

  /** 个股分析默认全选形态大类（与技术工具默认勾选一致） */
  DEFAULT_TYPES: ['double_extremes', 'head_shoulders', 'triangle', 'wedge_flag', 'cup_handle'],

  /** 与 levels 一致：adjust=qfq|none；UI 默认勾选前复权 */
  selectedAdjust() {
    const el = document.getElementById('patternAdjustQfq');
    return el && el.checked ? 'qfq' : 'none';
  },

  adjustLabel(adjust) {
    return adjust === 'qfq' ? '前复权 OHLC' : '不复权 OHLC';
  },

  /**
   * 个股形态识别（与技术工具「个股识别」同口径）。
   * @returns {{ items: array, code: string, name: string, asof: string, price_adjust: string, invalidated_count: number, raw: object }}
   */
  async fetchSingle(code, options = {}) {
    const types = (options.types && options.types.length)
      ? options.types
      : this.DEFAULT_TYPES;
    const adjust = options.adjust === 'none' ? 'none' : (options.adjust || 'qfq');
    const q = new URLSearchParams();
    q.set('types', types.join(','));
    q.set('adjust', adjust);
    if (options.asof) q.set('asof', options.asof);
    const resp = await authFetch(
      `${API_BASE_URL}/api/analysis/patterns/${encodeURIComponent(code)}?${q.toString()}`
    );
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const msg = (data.detail && (data.detail.message || data.detail)) || data.message || '识别失败';
      throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
    const priceAdjust = data.price_adjust === 'qfq' ? 'qfq' : 'none';
    const items = (data.items || []).map((h) => ({
      ...h,
      code: data.code || code,
      name: data.name || '',
    }));
    const invalidatedCount = Number(data.invalidated_count) || 0;
    return {
      items,
      code: data.code || code,
      name: data.name || '',
      asof: data.asof || '',
      price_adjust: priceAdjust,
      invalidated_count: invalidatedCount,
      tactical: data.tactical || null,
      raw: data,
    };
  },

  /** 命中 meta：`命中 M` 或 `命中 M（另有 N 条已失效）` */
  formatHitMeta(validCount, invalidatedCount) {
    const m = Number(validCount) || 0;
    const n = Number(invalidatedCount) || 0;
    if (n > 0) return `命中 ${m}（另有 ${n} 条已失效）`;
    return `命中 ${m}`;
  },

  /** 空结果文案；N>0 时标明有效 0 与失效条数 */
  formatEmptyPatternMessage(invalidatedCount, { scan = false } = {}) {
    const n = Number(invalidatedCount) || 0;
    if (n > 0) {
      return `未识别到选定形态。有效命中 0（另有 ${n} 条已失效）`;
    }
    return scan ? '未识别到选定形态（或扫描无命中）。' : '未识别到选定形态。';
  },

  /**
   * 将个股形态结果渲染到任意容器（个股分析嵌入用）。
   * @param {HTMLElement} container
   * @param {array} items
   * @param {string} metaHtml
   * @param {string} priceAdjust
   * @param {{asof?:string, confluenceZones?:object, invalidatedCount?:number, tactical?:object}|undefined} options
   */
  renderEmbedded(container, items, metaHtml, priceAdjust, options) {
    if (!container) return;
    const adjust = priceAdjust === 'qfq' ? 'qfq' : 'none';
    const opts = options || {};
    const visible = this._activeHits(items);
    const metaBlock = metaHtml
      ? `<div class="pattern-meta">${metaHtml}</div>`
      : '';
    if (!visible.length) {
      const emptyExpert = this._buildExpertHtml([], 'single', adjust, opts);
      const emptyMsg = this.formatEmptyPatternMessage(opts.invalidatedCount);
      container.innerHTML = `${metaBlock}
        <div class="kde-levels-empty">${this.esc(emptyMsg)}</div>
        ${emptyExpert}`;
      return;
    }
    const rows = visible
      .map((r) => {
        const code = r.code || '';
        const name = r.name || '';
        const href = code
          ? `stock.html?code=${encodeURIComponent(code)}&name=${encodeURIComponent(name)}`
          : '#';
        const codeHtml = code
          ? `<a href="${href}" target="_blank" rel="noopener noreferrer">${this.esc(code)}</a>`
          : '--';
        const formed = this.formedAtText(r);
        const reasonFull = this.reasonText(r);
        return `<tr>
          <td>${codeHtml}</td>
          <td>${this.esc(name || '--')}</td>
          <td>${this._patternTypeCellHtml(r)}</td>
          <td>${this.esc(this.statusLabel(r.status, r))}</td>
          <td title="${this.esc(this.formedAtTitle(r))}">${this.esc(formed)}</td>
          <td>${this._confCellHtml(r)}</td>
          <td class="pattern-col-levels">${this.esc(this.keyLevelsText(r.key_levels))}</td>
          <td class="pattern-col-reason" title="${this.esc(reasonFull)}">${this.esc(reasonFull)}</td>
        </tr>`;
      })
      .join('');
    const expert = this._buildExpertHtml(visible, 'single', adjust, opts);
    container.innerHTML = `${metaBlock}
      <div class="pattern-result-wrap">
        <table class="pattern-result-table">
          <thead>
            <tr>
              <th>代码</th><th>名称</th><th>形态</th><th>状态</th>
              <th>形成日</th><th>置信度</th><th>关键价</th><th>说明</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      ${expert}`;
  },

  /** 专家解读 HTML（供原面板与嵌入共用） */
  _buildExpertHtml(items, mode, priceAdjust, options) {
    const opts = options || {};
    const adjustTag = `<span class="kde-levels-adjust-tag ${
      priceAdjust === 'qfq' ? 'is-qfq' : 'is-raw'
    }">${this.esc(this.adjustLabel(priceAdjust))}</span>`;
    if (mode === 'scan') {
      const n = (items || []).length;
      if (!n) return '';
      const top = this._rankHits(items, opts).slice(0, 3);
      const brief = top
        .map((h) => {
          const code = h.code || '';
          const label = this.typeLabel(h.pattern_type);
          const st = this.statusLabel(h.status, h);
          const conf = h.confidence != null ? Number(h.confidence).toFixed(2) : '--';
          return `${code} ${label}（${st} ${conf}）`;
        })
        .join('；');
      return `<div class="pattern-expert-analysis">
        <div class="pattern-expert-title">形态解读</div>
        <div class="pattern-expert-body">
          <p>本页命中 ${n} 条${brief ? `，靠前示例：${this.esc(brief)}` : ''}。扫描模式不展开长文解读，请切换至「个股识别」获取完整专家分析。 ${adjustTag}</p>
          <p class="pattern-expert-risk">风险提示：以上为日线规则模板摘要，不构成投资建议。</p>
        </div>
      </div>`;
    }
    const list = items || [];
    const analysis = this.buildExpertAnalysis(list, opts);
    const structureHtml = analysis.structureHtml || analysis.tradeLevelsHtml || '';
    const tacticalHtml = this._buildTacticalHtml(opts.tactical);
    const rangeBadge = this._rangeBoxBadgeHtml(list);
    return `<div class="pattern-expert-analysis">
      <div class="pattern-expert-title">形态解读</div>
      <div class="pattern-expert-body">
        <p><span class="pattern-expert-label">价格口径：</span>${adjustTag}</p>
        ${rangeBadge}
        ${tacticalHtml}
        <p><span class="pattern-expert-label">短期走势：</span>${this.esc(analysis.shortTerm)}</p>
        <p><span class="pattern-expert-label">中线格局：</span>${this.esc(analysis.mediumTerm)}</p>
        ${structureHtml}
        <p class="pattern-expert-risk">${this.esc(analysis.risk)}</p>
      </div>
    </div>`;
  },

  /**
   * 短期三态徽章 + 买点列表（看空只显示风险；与 shortTerm NLG 并存）。
   * @param {object|null|undefined} tactical
   */
  _buildTacticalHtml(tactical) {
    const t = tactical && typeof tactical === 'object' ? tactical : null;
    if (!t || !t.short_bias) return '';
    const biasRaw = String(t.short_bias);
    const bias = biasRaw === 'insufficient' ? '信息不足' : biasRaw;
    const grade = t.grade ? String(t.grade) : 'base';
    const label = t.bias_label ? String(t.bias_label) : '';
    const conf =
      t.confidence != null && Number.isFinite(Number(t.confidence))
        ? Number(t.confidence).toFixed(2)
        : '--';
    const badgeClass =
      biasRaw === '看多'
        ? 'pattern-tactical-bull'
        : biasRaw === '看空'
          ? 'pattern-tactical-bear'
          : biasRaw === 'insufficient'
            ? 'pattern-tactical-insufficient'
            : 'pattern-tactical-range';
    const labelShow = label || '';
    const badgeText =
      labelShow === '箱体震荡' || labelShow.indexOf('箱体震荡') >= 0
        ? `${bias} · ${labelShow}`
        : `${bias}${labelShow ? ` · ${labelShow}` : ''}`;
    const bq = t.breakout_quality ? String(t.breakout_quality) : '';
    const bqLabel =
      bq === 'strong' ? '突破质量·强' : bq === 'weak' ? '突破质量·弱（缺量）' : bq === 'unconfirmed_hold' ? '突破质量·未站稳' : '';
    const bqClass =
      bq === 'strong'
        ? 'pattern-bq-strong'
        : bq === 'weak'
          ? 'pattern-bq-weak'
          : bq === 'unconfirmed_hold'
            ? 'pattern-bq-hold'
            : '';
    const bqBadge = bqLabel
      ? `<span class="pattern-tactical-bq ${bqClass}">${this.esc(bqLabel)}</span>`
      : '';
    const cautionBadge = t.counter_trend_caution
      ? '<span class="pattern-tactical-caution">逆势谨慎</span>'
      : '';
    const rationale = t.rationale ? String(t.rationale) : '';
    const statusNote = t.status_note ? String(t.status_note).trim() : '';
    const displayStatus = t.display_status ? String(t.display_status).trim() : '';
    const structureNote =
      (t.structure_note && String(t.structure_note).trim()) ||
      (t.highlight && t.highlight.text ? String(t.highlight.text).trim() : '');
    const reboundNote = t.rebound_note ? String(t.rebound_note).trim() : '';
    let hintsHtml = '';
    if (biasRaw === '看空') {
      const risk = t.risk_note ? String(t.risk_note) : '结构破位，无进攻买点。';
      hintsHtml = `<p class="pattern-tactical-risk"><span class="pattern-expert-label">风险：</span>${this.esc(risk)}</p>`;
    } else {
      const hints = Array.isArray(t.buy_hints) ? t.buy_hints : [];
      if (hints.length) {
        const lis = hints
          .map((h) => {
            const type = h.type || 'watch';
            const trig = h.trigger || '';
            const ez = h.entry_zone || {};
            const zone =
              ez.low != null && ez.high != null
                ? `${Number(ez.low).toFixed(2)}–${Number(ez.high).toFixed(2)}`
                : '--';
            const inv = h.invalidation != null ? Number(h.invalidation).toFixed(2) : '--';
            const tgt = h.target != null ? Number(h.target).toFixed(2) : '--';
            const statusBit =
              h.trigger_status === 'triggered'
                ? ' [已触发]'
                : h.trigger_status === 'pending'
                  ? ' [待触发]'
                  : '';
            return `<li><strong>${this.esc(type)}</strong> ${this.esc(trig)}；区间 ${this.esc(
              zone
            )}；失效 ${this.esc(inv)}；目标 ${this.esc(tgt)}${this.esc(statusBit)}</li>`;
          })
          .join('');
        hintsHtml = `<div class="pattern-tactical-hints"><span class="pattern-expert-label">结构买点：</span><ul>${lis}</ul></div>`;
      } else if (t.risk_note) {
        hintsHtml = `<p class="pattern-tactical-risk"><span class="pattern-expert-label">提示：</span>${this.esc(
          String(t.risk_note)
        )}</p>`;
      }
    }
    const disc = t.disclaimer ? `<p class="pattern-tactical-disc">${this.esc(String(t.disclaimer))}</p>` : '';
    const nesting =
      t.nesting_note != null && String(t.nesting_note).trim()
        ? `<p class="pattern-tactical-nesting"><span class="pattern-expert-label">嵌套：</span>${this.esc(
            String(t.nesting_note)
          )}</p>`
        : '';
    const structureHtml = structureNote
      ? `<p class="pattern-tactical-highlight"><span class="pattern-expert-label">结构高亮：</span>${this.esc(
          structureNote
        )}</p>`
      : '';
    const reboundHtml = reboundNote
      ? `<p class="pattern-tactical-rebound"><span class="pattern-expert-label">前瞻：</span>${this.esc(
          reboundNote
        )}</p>`
      : '';
    const alertObj =
      t.wedge_breakout_alert && typeof t.wedge_breakout_alert === 'object'
        ? t.wedge_breakout_alert
        : null;
    const alertTarget =
      alertObj && alertObj.target != null && Number.isFinite(Number(alertObj.target))
        ? Number(alertObj.target)
        : alertObj &&
            alertObj.alert_target != null &&
            Number.isFinite(Number(alertObj.alert_target))
          ? Number(alertObj.alert_target)
          : null;
    const alertStr =
      alertObj &&
      alertObj.target_strength != null &&
      Number.isFinite(Number(alertObj.target_strength))
        ? Number(alertObj.target_strength)
        : null;
    const alertTargetHtml =
      alertTarget != null
        ? `<p class="pattern-tactical-alert-target"><span class="pattern-expert-label">预警目标：</span>${this.esc(
            `${alertTarget.toFixed(2)} 附近${
              alertStr != null ? `（强度 ${alertStr} 共振阻力带）` : '（共振阻力带）'
            }`
          )}</p>`
        : '';
    const ultraObj =
      t.ultra_squeeze && typeof t.ultra_squeeze === 'object' ? t.ultra_squeeze : null;
    const stormObj =
      t.asymmetry_storm && typeof t.asymmetry_storm === 'object' ? t.asymmetry_storm : null;
    const probeClass =
      displayStatus === '高倾角风暴预警' ||
      (stormObj && stormObj.ok) ||
      displayStatus === 'asymmetry_storm'
        ? ' pattern-tactical-asymmetry-storm'
        : displayStatus === '楔形蓄势突破预警' || t.wedge_breakout_alert
          ? ' pattern-tactical-wedge-alert'
          : displayStatus === '极窄箱体变盘临界' || ultraObj
            ? ' pattern-tactical-ultra-squeeze'
            : '';
    const probeHtml =
      displayStatus || statusNote
        ? `<p class="pattern-tactical-probe${probeClass}"><span class="pattern-expert-label">盘口态：</span>${this.esc(
            displayStatus || '试探突破'
          )}${statusNote ? ` — ${this.esc(statusNote)}` : ''}</p>`
        : '';
    return `<div class="pattern-tactical-block">
      ${structureHtml}
      <p>
        <span class="pattern-expert-label">短期判断：</span>
        <span class="pattern-tactical-badge ${badgeClass}">${this.esc(badgeText)}</span>
        ${bqBadge}
        ${cautionBadge}
        <span class="pattern-tactical-grade">grade=${this.esc(grade)}</span>
        <span class="pattern-tactical-conf">置信 ${this.esc(conf)}</span>
      </p>
      ${probeHtml}
      ${alertTargetHtml}
      ${rationale ? `<p class="pattern-tactical-rationale">${this.esc(rationale)}</p>` : ''}
      ${nesting}
      ${reboundHtml}
      ${hintsHtml}
      ${disc}
    </div>`;
  },

  /** 战术块纯文本（PDF） */
  formatTacticalPlainText(tactical) {
    const t = tactical && typeof tactical === 'object' ? tactical : null;
    if (!t || !t.short_bias) return '';
    const biasRaw = String(t.short_bias);
    const biasShow = biasRaw === 'insufficient' ? '信息不足' : biasRaw;
    const structureNote =
      (t.structure_note && String(t.structure_note).trim()) ||
      (t.highlight && t.highlight.text ? String(t.highlight.text).trim() : '');
    const parts = [];
    if (structureNote) parts.push(`结构高亮：${structureNote}`);
    parts.push(
      `短期判断：${biasShow}${t.bias_label ? `（${t.bias_label}）` : ''} · grade=${t.grade || 'base'}${
        t.confidence != null ? ` · 置信 ${Number(t.confidence).toFixed(2)}` : ''
      }`
    );
    if (t.breakout_quality) {
      const q = String(t.breakout_quality);
      const qLab =
        q === 'strong' ? '强' : q === 'weak' ? '弱（缺量）' : q === 'unconfirmed_hold' ? '未站稳' : q;
      parts.push(`突破质量：${qLab}`);
    }
    if (t.counter_trend_caution) {
      parts.push('逆势谨慎：周线下降趋势，日线/形态偏多仅作反弹观察');
    }
    if (t.rationale) parts.push(String(t.rationale));
    if (t.display_status || t.status_note) {
      parts.push(
        `盘口态：${t.display_status || '试探突破'}${
          t.status_note ? ` — ${String(t.status_note)}` : ''
        }`
      );
    }
    const alertPlain =
      t.wedge_breakout_alert && typeof t.wedge_breakout_alert === 'object'
        ? t.wedge_breakout_alert
        : null;
    const alertTgtPlain =
      alertPlain && alertPlain.target != null && Number.isFinite(Number(alertPlain.target))
        ? Number(alertPlain.target)
        : alertPlain &&
            alertPlain.alert_target != null &&
            Number.isFinite(Number(alertPlain.alert_target))
          ? Number(alertPlain.alert_target)
          : null;
    if (alertTgtPlain != null) {
      const astr =
        alertPlain &&
        alertPlain.target_strength != null &&
        Number.isFinite(Number(alertPlain.target_strength))
          ? Number(alertPlain.target_strength)
          : null;
      parts.push(
        `预警目标：${alertTgtPlain.toFixed(2)} 附近${
          astr != null ? `（强度 ${astr} 共振阻力带）` : '（共振阻力带）'
        }`
      );
    }
    if (t.nesting_note) parts.push(`嵌套：${String(t.nesting_note)}`);
    if (t.rebound_note) parts.push(`前瞻：${String(t.rebound_note)}`);
    if (biasRaw === '看空') {
      parts.push(t.risk_note ? `风险：${t.risk_note}` : '风险：结构破位，无进攻买点');
    } else {
      const hints = Array.isArray(t.buy_hints) ? t.buy_hints : [];
      hints.forEach((h, i) => {
        const ez = h.entry_zone || {};
        const zone =
          ez.low != null && ez.high != null
            ? `${Number(ez.low).toFixed(2)}–${Number(ez.high).toFixed(2)}`
            : '--';
        const statusBit =
          h.trigger_status === 'triggered'
            ? ' [已触发]'
            : h.trigger_status === 'pending'
              ? ' [待触发]'
              : '';
        parts.push(
          `买点${i + 1}：${h.type || 'watch'} ${h.trigger || ''}；区间 ${zone}；失效 ${
            h.invalidation != null ? Number(h.invalidation).toFixed(2) : '--'
          }；目标 ${h.target != null ? Number(h.target).toFixed(2) : '--'}${statusBit}`
        );
      });
      if (t.risk_note) parts.push(`提示：${t.risk_note}`);
    }
    if (t.disclaimer) parts.push(String(t.disclaimer));
    return parts.join('\n');
  },

  /**
   * 将 buildExpertAnalysis 输出拼成纯文本（PDF / 调试共用同一字段口径）。
   */
  formatExpertPlainText(analysis) {
    const a = analysis || {};
    const parts = [];
    if (a.primaryLabel) {
      const confPart =
        a.primaryConf && a.primaryConf !== '--'
          ? `（置信度 ${a.primaryConf}）`
          : '';
      parts.push(`主形态：${a.primaryLabel}${confPart}`);
    }
    if (a.tacticalPlain) parts.push(a.tacticalPlain);
    if (a.shortTerm) parts.push(`短线：${a.shortTerm}`);
    if (a.mediumTerm) parts.push(`中线：${a.mediumTerm}`);
    if (a.structureText) parts.push(a.structureText);
    else if (a.tradeLevelsText) parts.push(a.tradeLevelsText);
    if (a.risk) parts.push(a.risk);
    return parts.filter(Boolean).join('\n');
  },

  async ensureCatalog() {
    if (this._catalog.industry.length || this._catalog.concept.length) return;
    const fetchFn = window.authFetch || fetch;
    const [ind, con] = await Promise.all([
      fetchFn(`${API_BASE_URL}/api/market/industry_board/catalog?board_code_source=tonghuashun`),
      fetchFn(`${API_BASE_URL}/api/market/concept_board/list?board_code_source=tonghuashun`),
    ]);
    const indJson = ind.ok ? await ind.json() : {};
    const conJson = con.ok ? await con.json() : {};
    this._catalog.industry = indJson.data || indJson.items || indJson || [];
    if (!Array.isArray(this._catalog.industry)) this._catalog.industry = [];
    this._catalog.concept = conJson.data || conJson.items || conJson || [];
    if (!Array.isArray(this._catalog.concept)) this._catalog.concept = [];
  },

  openBoardPicker() {
    const scope = (document.getElementById('patternScanScope') || {}).value || 'industry';
    const kind = scope === 'concept' ? 'concept' : 'industry';
    this.ensureCatalog().then(() => {
      const list = kind === 'concept' ? this._catalog.concept : this._catalog.industry;
      const names = list
        .slice(0, 40)
        .map((b) => `${b.board_code || b.code} ${b.board_name || b.name || ''}`)
        .join('\n');
      const hint = `输入板块代码，多个用逗号分隔。\n示例（同花顺）：\n${names || '（目录为空）'}`;
      const cur = this.selectedBoards.join(',');
      const raw = window.prompt(hint, cur);
      if (raw == null) return;
      this.selectedBoards = String(raw)
        .split(/[,，\s]+/)
        .map((s) => s.trim())
        .filter(Boolean);
      const sum = document.getElementById('patternBoardSummary');
      if (sum) {
        sum.textContent = this.selectedBoards.length
          ? `已选 ${this.selectedBoards.length} 个：${this.selectedBoards.slice(0, 5).join(',')}${this.selectedBoards.length > 5 ? '…' : ''}`
          : '未选';
      }
    });
  },

  typeLabel(t) {
    return this.TYPE_LABELS[t] || t || '--';
  },

  keyLevelsText(levels) {
    if (!levels || typeof levels !== 'object') return '--';
    const parts = [];
    ['neckline', 'upper', 'lower', 'head', 'l1', 'l2', 'h1', 'h2', 'last_close'].forEach((k) => {
      if (levels[k] != null && levels[k] !== '') {
        parts.push(`${k}:${this._fmtPx(levels[k])}`);
      }
    });
    return parts.slice(0, 4).join(' ') || '--';
  },

  /** 形成日：优先 formed_at；否则确认日；否则枢轴最晚日 */
  formedAtText(r) {
    if (!r || typeof r !== 'object') return '--';
    const norm = (v) => String(v == null ? '' : v).slice(0, 10);
    let d = norm(r.formed_at);
    if (d) return d;
    d = norm(r.confirm_date);
    if (d) return d;
    const dates = [];
    (r.key_dates || []).forEach((kd) => {
      const x = norm(kd && kd.date);
      if (x) dates.push(x);
    });
    (r.pivots || []).forEach((p) => {
      const x = norm(p && p.date);
      if (x) dates.push(x);
    });
    return dates.length ? dates.sort().slice(-1)[0] : '--';
  },

  formedAtTitle(r) {
    const parts = [];
    (r.key_dates || r.pivots || []).forEach((p) => {
      const role = (p && (p.role || '')) || '';
      const d = String((p && p.date) || '').slice(0, 10);
      if (d) parts.push(role ? `${role}:${d}` : d);
    });
    if (r.confirm_date) parts.push(`确认:${String(r.confirm_date).slice(0, 10)}`);
    return parts.join(' · ') || this.formedAtText(r);
  },

  /**
   * 说明列：优先用 pivots 把价位与日期配对；
   * 颈线（非枢轴均价）、斜率/收敛等无日参数从 key_levels 或原 reason 补全。
   * 格式：左肩=44.97(2026-03-12)
   */
  reasonText(r) {
    if (!r || typeof r !== 'object') return '';
    const reason = String(r.reason || '');
    const pivots = Array.isArray(r.pivots) ? r.pivots : [];
    const priced = pivots.filter((p) => p && p.price != null && p.price !== '');
    if (!priced.length) return reason;

    const label = this.typeLabel(r.pattern_type);
    const simplified = /简化规则/.test(reason) ? '（简化规则）' : '';
    const parts = priced.map((p) => {
      const name = this.PIVOT_ROLE_LABELS[p.role] || p.role || '';
      const d = String(p.date || '').slice(0, 10);
      const px = this._fmtPx(p.price);
      return d ? `${name}=${px}(${d})` : `${name}=${px}`;
    });

    const levels = r.key_levels || {};
    const extras = [];
    const shrink = reason.match(/收敛约[^\s]+/);
    if (shrink) extras.push(shrink[0]);
    else if (levels.shrink_pct != null && levels.shrink_pct !== '') {
      extras.push(`收敛约${levels.shrink_pct}%`);
    }
    if (levels.bars_to_apex != null && levels.bars_to_apex !== '') {
      const bta = levels.bars_to_apex;
      const win = levels.apex_window ? `（拐点窗口约${levels.apex_window}）` : '';
      extras.push(`预计约${bta}根至顶点${win}`);
    } else {
      const mApex = reason.match(/预计约[^\s]*根至顶点(?:（[^）]*）)?/);
      if (mApex) extras.push(mApex[0]);
    }
    if (levels.neckline != null && levels.neckline !== '' && !priced.some((p) => p.role === 'neck')) {
      extras.push(`颈线≈${this._fmtPx(levels.neckline)}`);
    }
    const slopeUnit =
      levels.slope_unit ||
      (/(元\/K线索引|元\/交易日|元\/枢轴)/.test(reason) ? '' : '元/K线索引(约交易日)');
    const slopeSuffix = slopeUnit ? String(slopeUnit) : '';
    if (levels.upper_slope != null && levels.upper_slope !== '') {
      extras.push(`上沿斜率=${levels.upper_slope}${slopeSuffix}`);
    } else {
      const m = reason.match(/上沿斜率=[^\s]+/);
      if (m) extras.push(m[0]);
    }
    if (levels.lower_slope != null && levels.lower_slope !== '') {
      extras.push(`下沿斜率=${levels.lower_slope}${slopeSuffix}`);
    } else {
      const m = reason.match(/下沿斜率=[^\s]+/);
      if (m) extras.push(m[0]);
    }
    return `${label}${simplified} ${parts.join(' ')}${extras.length ? ` ${extras.join(' ')}` : ''}`.trim();
  },

  statusLabel(st, hit) {
    if (hit && hit.display_status) return String(hit.display_status);
    if (st === 'asymmetry_storm' || st === '高倾角风暴预警') return '高倾角风暴预警';
    if (st === 'wedge_breakout_alert' || st === '楔形蓄势突破预警') return '楔形蓄势突破预警';
    if (st === 'ultra_squeeze' || st === '极窄箱体变盘临界') return '极窄箱体变盘临界';
    if (st === 'breakout_probe' || st === '试探突破') return '试探突破';
    if (st === 'confirmed') return '已确认';
    if (st === 'invalidated') return '失效';
    if (st === 'archived') return '已归档';
    return '形成中';
  },

  /** 列表/专家解读默认忽略失效项；归档项列表可见但不进主形态排序（见 _rankHits） */
  _activeHits(items) {
    return (items || []).filter((h) => h && h.status !== 'invalidated');
  },

  /** 命中是否带双顶双底互斥箱体标记 */
  _isRangeBoxHit(h) {
    if (!h || typeof h !== 'object') return false;
    const lv = h.key_levels && typeof h.key_levels === 'object' ? h.key_levels : {};
    return !!(h.range_box || h.bias_mix || lv.range_box || lv.bias_mix);
  },

  /**
   * 从 items 提取箱体震荡上下沿（双顶+双底 bias_mix/range_box）。
   * @returns {{low:number, high:number}|null}
   */
  _findRangeBox(items) {
    const list = (items || []).filter((h) => h && h.status !== 'invalidated');
    const tops = list.filter((h) => h.pattern_type === 'double_top' && this._isRangeBoxHit(h));
    const bottoms = list.filter(
      (h) => h.pattern_type === 'double_bottom' && this._isRangeBoxHit(h)
    );
    if (!tops.length || !bottoms.length) return null;
    const pick = tops[0] || bottoms[0];
    const lv = (pick && pick.key_levels) || {};
    let low = this._num(lv.box_low != null ? lv.box_low : pick.box_low);
    let high = this._num(lv.box_high != null ? lv.box_high : pick.box_high);
    if (low == null || high == null) {
      for (let i = 0; i < list.length; i++) {
        const h = list[i];
        if (!this._isRangeBoxHit(h)) continue;
        const kl = h.key_levels || {};
        low = this._num(kl.box_low != null ? kl.box_low : h.box_low);
        high = this._num(kl.box_high != null ? kl.box_high : h.box_high);
        if (low != null && high != null) break;
      }
    }
    if (low == null || high == null) return null;
    return { low, high };
  },

  _rangeBoxBadgeHtml(items) {
    const box = this._findRangeBox(items);
    if (!box) return '';
    const txt = `箱体震荡 ${Number(box.low).toFixed(2)}–${Number(box.high).toFixed(2)}`;
    return `<p class="pattern-range-box-badge"><span class="pattern-tactical-badge pattern-tactical-range">${this.esc(
      txt
    )}</span></p>`;
  },

  _patternTypeCellHtml(r) {
    const label = this.typeLabel(r.pattern_type);
    const mixNote =
      this._isRangeBoxHit(r) &&
      (r.pattern_type === 'double_top' || r.pattern_type === 'double_bottom')
        ? ' <span class="pattern-box-merged" title="双顶双底互斥，已并入箱体观察">已并入箱体观察</span>'
        : '';
    return `${this.esc(label)}${mixNote}`;
  },

  _confCellHtml(r) {
    const conf = r.confidence != null ? Number(r.confidence).toFixed(2) : '--';
    const tip =
      this._isRangeBoxHit(r) &&
      (r.pattern_type === 'double_top' || r.pattern_type === 'double_bottom')
        ? ` <span class="pattern-box-merged-tip" title="已并入箱体观察">·箱体</span>`
        : '';
    return `${this.esc(conf)}${tip}`;
  },

  renderItems(items, metaHtml, mode, priceAdjust, options) {
    const body = document.getElementById('patternResultBody');
    const wrap = document.getElementById('patternResultWrap');
    const empty = document.getElementById('patternEmpty');
    const meta = document.getElementById('patternMeta');
    const adjust = priceAdjust === 'qfq' ? 'qfq' : 'none';
    const opts = options || {};
    const visible = this._activeHits(items);
    if (meta) {
      meta.hidden = !metaHtml;
      meta.innerHTML = metaHtml || '';
    }
    if (!visible.length) {
      if (wrap) wrap.hidden = true;
      if (empty) {
        empty.hidden = false;
        empty.textContent = this.formatEmptyPatternMessage(opts.invalidatedCount, {
          scan: mode === 'scan',
        });
      }
      this.renderExpertAnalysis([], mode || 'single', adjust, opts);
      return;
    }
    if (empty) empty.hidden = true;
    if (wrap) wrap.hidden = false;
    if (!body) return;
    body.innerHTML = visible
      .map((r) => {
        const code = r.code || '';
        const name = r.name || '';
        const href = code ? `stock.html?code=${encodeURIComponent(code)}&name=${encodeURIComponent(name)}` : '#';
        const codeHtml = code
          ? `<a href="${href}" target="_blank" rel="noopener noreferrer">${this.esc(code)}</a>`
          : '--';
        const formed = this.formedAtText(r);
        const reasonFull = this.reasonText(r);
        return `<tr>
          <td>${codeHtml}</td>
          <td>${this.esc(name || '--')}</td>
          <td>${this._patternTypeCellHtml(r)}</td>
          <td>${this.esc(this.statusLabel(r.status, r))}</td>
          <td title="${this.esc(this.formedAtTitle(r))}">${this.esc(formed)}</td>
          <td>${this._confCellHtml(r)}</td>
          <td class="pattern-col-levels">${this.esc(this.keyLevelsText(r.key_levels))}</td>
          <td class="pattern-col-reason" title="${this.esc(reasonFull)}">${this.esc(reasonFull)}</td>
        </tr>`;
      })
      .join('');
    this.renderExpertAnalysis(visible, mode || 'single', adjust, opts);
  },

  /** 空结果隐藏；个股完整解读；扫描简要提示。options 可含 tactical / asof 等。 */
  renderExpertAnalysis(items, mode, priceAdjust, options) {
    const box = document.getElementById('patternExpertAnalysis');
    const body = document.getElementById('patternExpertBody');
    if (!box || !body) return;
    const opts = options || {};
    const asof =
      opts.asof ||
      ((document.getElementById('patternAsof') || {}).value || '').trim();
    const hasTactical = !!(opts.tactical && opts.tactical.short_bias);
    if ((!items || !items.length) && !hasTactical) {
      box.hidden = true;
      body.innerHTML = '';
      return;
    }
    const html = this._buildExpertHtml(items || [], mode || 'single', priceAdjust, {
      ...opts,
      asof,
    });
    const tmp = document.createElement('div');
    tmp.innerHTML = html;
    const inner = tmp.querySelector('.pattern-expert-body');
    box.hidden = false;
    body.innerHTML = inner ? inner.innerHTML : html;
  },

  BEARISH_REVERSAL: {
    double_top: true,
    head_shoulders_top: true,
  },
  BULLISH_REVERSAL: {
    double_bottom: true,
    head_shoulders_bottom: true,
  },
  CONSOLIDATION: {
    ascending_triangle: true,
    descending_triangle: true,
    symmetrical_triangle: true,
    rising_wedge: true,
    falling_wedge: true,
    bull_flag: true,
    bear_flag: true,
    cup_with_handle: true,
  },

  /**
   * 主形态竞选（同 status）：Confidence desc →（|Δconf| < eps 时）时间衰减弱 tie-break → formed_at desc。
   * |Δconf| ≥ RANK_CONF_TIE_EPS 时衰减压不过更高置信度。
   * 状态层仍 confirmed 优先于 forming（见 _rankHits）。
   */
  RANK_W_CONFIRMED: 1.2,
  RANK_W_FORMING: 0.6,
  RANK_TIME_DECAY_LAMBDA: 0.012,
  /** 置信度差超过该阈值时，禁止用时间衰减压过更高 conf */
  RANK_CONF_TIE_EPS: 0.05,
  /** 形成中反转超过该日历日龄不进主形态（真空兜底） */
  PRIMARY_FORMING_MAX_AGE_DAYS: 60,
  /**
   * 有主形态时：夹在「现价 ↔ 形态下沿/上沿」之间的高强共振带，
   * 可软插入为近端缓冲（默认强度 ≥10；不覆盖形态核心档）。
   * 选取：近端优先（距现价最近），同分再比强度。
   */
  CONFLUENCE_SOFT_BUFFER_MIN_STRENGTH: 10.0,
  /**
   * 贴身临界：0 ≤ |center−close|/|close| < 该比例（默认 0.5%），
   * 且阻力 high>close / 支撑 low<close → 标「贴身临界压制/支撑」。
   */
  CONFLUENCE_SOFT_CONTACT_PCT: 0.005,
  /**
   * 弱近端「日内/临界压制/支撑」战术门槛（默认 ≥4；不占核心双档席位）。
   * 与 soft buffer（≥10）区分：后者进档位，前者仅战术说明行。
   * 贴身带（CONTACT）强度 ≥ 本门槛可走 soft/贴身档并豁免 nearEps；
   * 非贴身弱带可贴价约 0.3% 过滤；强度≥10 的贴身/近端 soft 不得被该过滤静默丢弃。
   */
  CONFLUENCE_TACTICAL_CAP_MIN_STRENGTH: 4.0,
  /** 战术弱带贴价过滤比例（默认 0.3%）；不作用于 soft≥10 / 贴身带 CONTACT */
  CONFLUENCE_TACTICAL_NEAR_EPS_PCT: 0.003,
  /**
   * primary 强制第一档后：巩固通道上/下沿在距现价该比例内可保送第二席（默认 3%）。
   */
  TRADE_LEVEL_NEAR_CHANNEL_PROMOTE_PCT: 0.03,

  _num(v) {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  },

  _hitClose(h) {
    const lv = (h && h.key_levels) || {};
    return this._num(lv.last_close != null ? lv.last_close : h.last_close);
  },

  _hitNeck(h) {
    const lv = (h && h.key_levels) || {};
    return this._num(lv.neckline);
  },

  _hitBounds(h) {
    const lv = (h && h.key_levels) || {};
    return { upper: this._num(lv.upper), lower: this._num(lv.lower) };
  },

  /** 收盘相对关键位：below / near / above（near 默认 ±4%） */
  _relToLevel(close, level, nearPct) {
    if (close == null || level == null || level === 0) return null;
    const pct = ((close - level) / Math.abs(level)) * 100;
    const band = nearPct != null ? nearPct : 4;
    if (Math.abs(pct) <= band) return { side: 'near', pct };
    return { side: pct < 0 ? 'below' : 'above', pct };
  },

  /** 头肩右肩价：key_levels.right_shoulder 或 pivots role=RS */
  _hitRightShoulder(h) {
    const lv = (h && h.key_levels) || {};
    const fromLv = this._num(lv.right_shoulder);
    if (fromLv != null) return fromLv;
    const pivots = (h && h.pivots) || [];
    for (let i = 0; i < pivots.length; i++) {
      const p = pivots[i];
      if (!p) continue;
      const role = String(p.role || '').toUpperCase();
      if (role === 'RS' || role === 'RIGHT_SHOULDER') {
        const px = this._num(p.price);
        if (px != null) return px;
      }
    }
    return null;
  },

  /**
   * 空头反转「颈线上方」文案分层：禁止大偏离仍写「附近」；
   * 逼近/超过右肩或大幅偏离时降偏空语气。
   */
  _bearishAboveNeckCopy(lab, c, n, rs, rel) {
    const pctAbs = Math.abs(rel.pct);
    const pctTxt = pctAbs.toFixed(1);
    const nearRsEps = rs != null ? Math.abs(rs) * 0.02 : null;
    const nearOrAboveRs =
      rs != null && nearRsEps != null && c >= rs - nearRsEps;
    // 大幅偏离颈线（默认 >8%）或逼近右肩 → 降偏空
    if (nearOrAboveRs || pctAbs >= 12) {
      const rsHint =
        rs != null
          ? nearOrAboveRs
            ? c >= rs
              ? `并已达到/超过右肩（${this._fmtPx(rs)}）`
              : `并逼近右肩（${this._fmtPx(rs)}）`
            : `（距颈线约+${pctTxt}%）`
          : `（距颈线约+${pctTxt}%）`;
      return `已确认${lab}，收盘（${this._fmtPx(c)}）已远离颈线（${this._fmtPx(
        n
      )}）${rsHint}，反抽削弱空头确认，短线不宜机械偏空；若再度有效跌破颈线再强化空头。`;
    }
    if (pctAbs >= 8) {
      return `已确认${lab}，收盘（${this._fmtPx(c)}）仍在颈线（${this._fmtPx(
        n
      )}）上方（偏离约+${pctTxt}%），短线偏观察：关注能否回落失守颈线，或继续反抽逼近右肩。`;
    }
    return `已确认${lab}，收盘（${this._fmtPx(c)}）仍在颈线（${this._fmtPx(
      n
    )}）上方附近，短线偏防守观察：若再度跌破颈线则确认偏空，若放量站稳则警惕假破/反抽。`;
  },

  /**
   * 多头反转「颈线下方」对称分层：禁止大偏离仍写「附近」。
   */
  _bullishBelowNeckCopy(lab, c, n, rs, rel) {
    const pctAbs = Math.abs(rel.pct);
    const pctTxt = pctAbs.toFixed(1);
    const nearRsEps = rs != null ? Math.abs(rs) * 0.02 : null;
    // 头肩底右肩为低点：逼近/跌破右肩 → 降偏多
    const nearOrBelowRs =
      rs != null && nearRsEps != null && c <= rs + nearRsEps;
    if (nearOrBelowRs || pctAbs >= 12) {
      const rsHint =
        rs != null
          ? nearOrBelowRs
            ? c <= rs
              ? `并已跌至/跌破右肩低点（${this._fmtPx(rs)}）`
              : `并逼近右肩低点（${this._fmtPx(rs)}）`
            : `（距颈线约-${pctTxt}%）`
          : `（距颈线约-${pctTxt}%）`;
      return `已确认${lab}，收盘（${this._fmtPx(c)}）已远离颈线（${this._fmtPx(
        n
      )}）${rsHint}，回撤削弱多头确认，短线不宜机械偏多；若再度有效站上颈线再强化多头。`;
    }
    if (pctAbs >= 8) {
      return `已确认${lab}，收盘（${this._fmtPx(c)}）仍在颈线（${this._fmtPx(
        n
      )}）下方（偏离约-${pctTxt}%），短线偏谨慎观察：关注能否重新站回颈线，或继续回撤逼近右肩。`;
    }
    return `已确认${lab}，收盘（${this._fmtPx(c)}）仍在颈线（${this._fmtPx(
      n
    )}）下方附近，短线偏谨慎，需等待突破确认。`;
  },

  _parseDateMs(s) {
    const d = String(s || '').slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) return null;
    const t = Date.parse(`${d}T00:00:00`);
    return Number.isFinite(t) ? t : null;
  },

  _daysBetween(fromS, toS) {
    const a = this._parseDateMs(fromS);
    const b = this._parseDateMs(toS);
    if (a == null || b == null) return null;
    return Math.max(0, Math.round((b - a) / 86400000));
  },

  _inferAsof(items, opts) {
    const o = opts || {};
    if (o.asof) return String(o.asof).slice(0, 10);
    let best = '';
    (items || []).forEach((h) => {
      const fa = String((h && (h.formed_at || h.confirm_date)) || '').slice(0, 10);
      if (fa > best) best = fa;
    });
    return best || '';
  },

  _statusWeight(st) {
    if (st === 'confirmed') return this.RANK_W_CONFIRMED;
    if (st === 'forming') return this.RANK_W_FORMING;
    return 0;
  },

  /** 时间衰减因子 e^(-λ·Δt)；缺日期视为 1 */
  _timeDecayFactor(h, asof) {
    if (!h) return 1;
    const formed = String(h.formed_at || h.confirm_date || '').slice(0, 10);
    const dt = this._daysBetween(formed, asof);
    if (dt == null) return 1;
    return Math.exp(-this.RANK_TIME_DECAY_LAMBDA * Math.max(0, dt));
  },

  /**
   * 兼容旧口径的综合分（展示/调试）；竞选排序见 _rankHits（不再单靠该分压过更高 conf）。
   * FinalScore ≈ confidence × W_status × exp(-λ·Δt)
   */
  _finalScore(h, asof) {
    if (!h) return 0;
    const conf = Number(h.confidence) || 0;
    const w = this._statusWeight(h.status);
    return conf * w * this._timeDecayFactor(h, asof);
  },

  _rankHits(items, opts) {
    const asof = this._inferAsof(items, opts);
    const list = (items || []).filter(
      (h) => h && h.status !== 'invalidated' && h.status !== 'archived'
    );
    const boost = (h) => {
      if (!h || h.status !== 'confirmed' || !this.CONSOLIDATION[h.pattern_type]) return 0;
      const hb = this._biasOf(h.pattern_type);
      const hd = String(h.formed_at || h.confirm_date || '').slice(0, 10);
      const hasOlderOppReversal = list.some((o) => {
        if (!o || o === h || o.status !== 'confirmed') return false;
        const isRev =
          this.BEARISH_REVERSAL[o.pattern_type] || this.BULLISH_REVERSAL[o.pattern_type];
        if (!isRev) return false;
        if (!this._biasConflicts(hb, this._biasOf(o.pattern_type))) return false;
        const od = String(o.formed_at || o.confirm_date || '').slice(0, 10);
        return !od || !hd || hd >= od;
      });
      return hasOlderOppReversal ? 1 : 0;
    };
    const statusRank = (st) => (st === 'confirmed' ? 2 : st === 'forming' ? 1 : 0);
    const confOf = (h) => Number(h && h.confidence) || 0;
    return list.slice().sort((a, b) => {
      // 1) confirmed > forming（不靠 W_status×衰减间接压过）
      const dSt = statusRank(b.status) - statusRank(a.status);
      if (dSt) return dSt;
      // 2) 同 status：Confidence desc；|Δconf| ≥ eps 时禁止衰减压过
      const ca = confOf(a);
      const cb = confOf(b);
      const confDiff = cb - ca;
      if (Math.abs(confDiff) >= this.RANK_CONF_TIE_EPS) return confDiff;
      // 3) conf 接近：λ 衰减作弱 tie-break（conf×decay）
      const sa = ca * this._timeDecayFactor(a, asof);
      const sb = cb * this._timeDecayFactor(b, asof);
      const sd = sb - sa;
      if (Math.abs(sd) > 1e-9) return sd;
      const bd = boost(b) - boost(a);
      if (bd) return bd;
      // 4) formed_at desc
      return String(b.formed_at || b.confirm_date || '').localeCompare(
        String(a.formed_at || a.confirm_date || '')
      );
    });
  },

  /** 过期/失败 forming 反转不进主形态 */
  _isViablePrimaryCandidate(h, asof) {
    if (!h) return false;
    if (h.status === 'confirmed') return true;
    if (h.status !== 'forming') return false;
    const isRev =
      this.BEARISH_REVERSAL[h.pattern_type] || this.BULLISH_REVERSAL[h.pattern_type];
    if (!isRev) return true;
    const formed = String(h.formed_at || h.confirm_date || '').slice(0, 10);
    const dt = this._daysBetween(formed, asof);
    if (dt != null && dt > this.PRIMARY_FORMING_MAX_AGE_DAYS) return false;
    const reason = String(h.reason || '');
    if (/失败破位|已归档|生命周期已结束/.test(reason)) return false;
    return true;
  },

  _pickPrimary(ranked, asof) {
    const list = ranked || [];
    const confirmed = list.filter((h) => h && h.status === 'confirmed');
    if (confirmed.length) return confirmed[0];
    const viable = list.filter((h) => this._isViablePrimaryCandidate(h, asof));
    return viable[0] || null;
  },

  /** 最近归档反向/测幅兑现形态：仅作背景一句，不抢主形态 */
  _archivedBackgroundText(items) {
    const archived = (items || [])
      .filter((h) => h && h.status === 'archived')
      .slice()
      .sort((a, b) =>
        String(b.formed_at || b.confirm_date || '').localeCompare(
          String(a.formed_at || a.confirm_date || '')
        )
      );
    if (!archived.length) return '';
    const h = archived[0];
    const lab = this.typeLabel(h.pattern_type);
    const reason = String(h.reason || '');
    const why = /大幅回到颈线/.test(reason)
      ? '破颈后现价大幅回到颈线另一侧，确认削弱'
      : /失败反抽/.test(reason)
        ? '失败反抽'
        : /失败破位/.test(reason)
          ? '失败破位'
          : /测幅目标/.test(reason)
            ? '测幅已兑现'
            : '周期已走完';
    return `背景：近期「${lab}」${why}并已归档，仅作兑现参考，不作为当前主导形态。`;
  },

  /**
   * 近端高强度共振带一句（轻量）；无数据则空串。
   * @param {object|null} confluence confluence_zones 结构
   * @param {number|null} close
   */
  _nearConfluenceHint(confluence, close) {
    if (!confluence || typeof confluence !== 'object') return '';
    const zones = [];
    (confluence.supports || []).forEach((z) => {
      if (z && z.center != null) zones.push({ ...z, side: 'support' });
    });
    (confluence.resistances || []).forEach((z) => {
      if (z && z.center != null) zones.push({ ...z, side: 'resistance' });
    });
    const nearest =
      confluence.nearest_support_zone || confluence.nearest_resistance_zone || null;
    if (nearest && nearest.center != null) {
      zones.push({
        ...nearest,
        side: confluence.nearest_support_zone === nearest ? 'support' : 'resistance',
      });
    }
    if (!zones.length) return '';
    const scored = zones
      .map((z) => {
        const c = this._num(z.center);
        const str = this._effectiveZoneStrength(z) || 0;
        const dist =
          close != null && c != null ? Math.abs((close - c) / Math.abs(c || 1)) : 1;
        return { z, c, str, dist, score: str / (1 + dist * 40) };
      })
      .filter((x) => x.c != null && x.str > 0)
      .sort((a, b) => b.score - a.score);
    if (!scored.length) return '';
    const top = scored[0];
    const role = top.z.side === 'support' ? '支撑' : '压力';
    const raw =
      this._num(top.z.strength) != null
        ? Number(top.z.strength).toFixed(1)
        : Number(top.str).toFixed(1);
    let msg = `近端高强度共振带约在 ${this._fmtPx(top.c)}（${role}，强度 ${raw}），可作短线参考。`;
    if (top.z.chips_void && top.z.void_note) {
      msg += `注：${top.z.void_note}`;
    } else if (top.z.chips_hvz && top.z.hvz_note) {
      msg += `注：${top.z.hvz_note}`;
    }
    return msg;
  },

  /** 支撑/阻力选型用有效强度：优先 strength_adjusted（真空折减 / HVZ 增益） */
  _effectiveZoneStrength(z) {
    if (!z || typeof z !== 'object') return null;
    const adj = this._num(z.strength_adjusted);
    if (adj != null) return adj;
    return this._num(z.strength);
  },

  _biasOf(type) {
    if (this.BEARISH_REVERSAL[type]) return 'bear';
    if (this.BULLISH_REVERSAL[type]) return 'bull';
    if (type === 'rising_wedge' || type === 'bear_flag' || type === 'descending_triangle') return 'bearish_bias';
    if (
      type === 'falling_wedge' ||
      type === 'bull_flag' ||
      type === 'ascending_triangle' ||
      type === 'cup_with_handle'
    ) {
      return 'bullish_bias';
    }
    return 'neutral';
  },

  /** bias 是否冲突：已确认偏多巩固 vs 已确认偏空反转等 */
  _biasConflicts(a, b) {
    const bullish = new Set(['bull', 'bullish_bias']);
    const bearish = new Set(['bear', 'bearish_bias']);
    return (bullish.has(a) && bearish.has(b)) || (bearish.has(a) && bullish.has(b));
  },

  /** 已确认巩固形态：上破 / 下破 / 未判明 */
  _consolBreakDir(h) {
    const t = h && h.pattern_type;
    const b = this._hitBounds(h);
    const c = this._hitClose(h);
    const up = b.upper;
    const lo = b.lower;
    if (c != null && up != null && c > up * 1.005) return 'up';
    if (c != null && lo != null && c < lo * 0.995) return 'down';
    if (
      t === 'falling_wedge' ||
      t === 'bull_flag' ||
      t === 'ascending_triangle' ||
      t === 'cup_with_handle'
    ) {
      return 'up';
    }
    if (t === 'rising_wedge' || t === 'bear_flag' || t === 'descending_triangle') return 'down';
    return 'out';
  },

  /** 已确认巩固形态：按收盘相对上下沿判定上破/下破文案 */
  _confirmedConsolBreakText(h) {
    const t = h.pattern_type;
    const lab = this.typeLabel(t);
    const conf = h.confidence != null ? Number(h.confidence).toFixed(2) : '--';
    const b = this._hitBounds(h);
    const up = b.upper;
    const lo = b.lower;
    const dir = this._consolBreakDir(h);
    if (dir === 'up') {
      return `已确认${lab}上破（置信度 ${conf}${
        up != null ? `，上沿 ${this._fmtPx(up)}` : ''
      }），短线偏多，突破方向已定。`;
    }
    if (dir === 'down') {
      return `已确认${lab}下破（置信度 ${conf}${
        lo != null ? `，下沿 ${this._fmtPx(lo)}` : ''
      }），短线偏空，突破方向已定。`;
    }
    return `已确认${lab}（置信度 ${conf}），短线围绕其关键价位波动。`;
  },

  /**
   * 巩固类简化测幅（前端展示用；后端入库为 P2 TODO）。
   * H = upper - lower；上破 target ≈ upper + H；下破 target ≈ lower - H。
   * @returns {{dir:string,upper:number,lower:number,height:number,target:number,label:string}|null}
   */
  _consolMeasuredMove(h) {
    if (!h || h.status !== 'confirmed' || !this.CONSOLIDATION[h.pattern_type]) return null;
    const b = this._hitBounds(h);
    if (b.upper == null || b.lower == null) return null;
    const height = b.upper - b.lower;
    if (!(height > 0)) return null;
    const dir = this._consolBreakDir(h);
    if (dir === 'up') {
      return {
        dir: 'up',
        upper: b.upper,
        lower: b.lower,
        height,
        target: b.upper + height,
        label: this.typeLabel(h.pattern_type),
      };
    }
    if (dir === 'down') {
      return {
        dir: 'down',
        upper: b.upper,
        lower: b.lower,
        height,
        target: b.lower - height,
        label: this.typeLabel(h.pattern_type),
      };
    }
    return null;
  },

  /** 主导已确认巩固突破上下文（供空档文案 / 测幅） */
  _leadConsolBreakContext(items, opts) {
    const asof = this._inferAsof(items, opts);
    const ranked = this._rankHits(items, { asof }).filter(
      (h) => h.status === 'confirmed' || this._isViablePrimaryCandidate(h, asof)
    );
    const lead =
      ranked.find((h) => h.status === 'confirmed' && this.CONSOLIDATION[h.pattern_type]) || null;
    const dir = lead ? this._consolBreakDir(lead) : null;
    const measured = lead ? this._consolMeasuredMove(lead) : null;
    const hasFormingConsol = ranked.some(
      (h) => h.status === 'forming' && this.CONSOLIDATION[h.pattern_type]
    );
    return { lead, dir, measured, hasFormingConsol };
  },

  /** 测幅是否已兑现/超额：上破 close≥target；下破 close≤target */
  _isMeasuredAchieved(m, close) {
    if (!m || close == null || m.target == null) return false;
    if (m.dir === 'up') return close >= m.target;
    if (m.dir === 'down') return close <= m.target;
    return false;
  },

  _measuredMoveBulletText(m) {
    if (!m) return '';
    if (m.achieved) {
      return `测幅目标 ${this._fmtPx(m.target)} 已超额达成（背景参考，不再作为结构阻力/支撑档）`;
    }
    if (m.dir === 'up') {
      return `简化测幅目标 ${this._fmtPx(m.target)} 附近（按边界高度：上沿 ${this._fmtPx(
        m.upper
      )} + H≈${this._fmtPx(m.height)}）`;
    }
    return `简化测幅目标 ${this._fmtPx(m.target)} 附近（按边界高度：下沿 ${this._fmtPx(
      m.lower
    )} − H≈${this._fmtPx(m.height)}）`;
  },

  _fmtPx(n) {
    if (n == null) return '--';
    const x = Number(n);
    if (!Number.isFinite(x)) return '--';
    return x.toFixed(2);
  },

  /** 置信度偏低或形成中 → 标注「观察中」 */
  _isObserving(h) {
    if (!h) return true;
    if (h.status !== 'confirmed') return true;
    const c = Number(h.confidence);
    return Number.isFinite(c) && c < 0.55;
  },

  /**
   * 从单条 hit 提炼可操作价位（颈线/峰谷/上下沿等）。
   * @returns {{price:number,name:string,role:string,source:string,observing:boolean,confirmed:boolean,conf:number}[]}
   */
  _levelsFromHit(h) {
    if (!h || typeof h !== 'object') return [];
    const t = h.pattern_type;
    const lv = h.key_levels || {};
    const src = this.typeLabel(t);
    const observing = this._isObserving(h);
    const confirmed = h.status === 'confirmed';
    const conf = Number(h.confidence) || 0;
    const out = [];
    const add = (price, name, role) => {
      const p = this._num(price);
      if (p == null) return;
      out.push({ price: p, name, role, source: src, observing, confirmed, conf });
    };

    if (t === 'double_top') {
      add(lv.neckline, '颈线', '观察失守');
      const h1 = this._num(lv.h1);
      const h2 = this._num(lv.h2);
      if (h1 != null && h2 != null) {
        const mid = (h1 + h2) / 2;
        if (mid > 0 && Math.abs(h1 - h2) / mid <= 0.02) {
          add(mid, '双峰高点', '上方压力');
        } else {
          add(h1, 'H1', '上方压力');
          add(h2, 'H2', '上方压力');
        }
      } else {
        add(h1 != null ? h1 : h2, '双峰高点', '上方压力');
      }
    } else if (t === 'double_bottom') {
      add(lv.neckline, '颈线', '观察站稳');
      const l1 = this._num(lv.l1);
      const l2 = this._num(lv.l2);
      if (l1 != null && l2 != null) {
        const mid = (l1 + l2) / 2;
        if (mid > 0 && Math.abs(l1 - l2) / mid <= 0.02) {
          add(mid, '双谷低点', '下方支撑');
        } else {
          add(l1, 'L1', '下方支撑');
          add(l2, 'L2', '下方支撑');
        }
      } else {
        add(l1 != null ? l1 : l2, '双谷低点', '下方支撑');
      }
    } else if (t === 'head_shoulders_top') {
      add(lv.neckline, '颈线', '观察失守');
      add(lv.head, '头部高点', '上方压力');
      add(lv.right_shoulder, '右肩', '上方压力');
    } else if (t === 'head_shoulders_bottom') {
      add(lv.neckline, '颈线', '观察站稳');
      add(lv.head, '头部低点', '下方支撑');
      add(lv.right_shoulder, '右肩', '下方支撑');
    } else if (this.CONSOLIDATION[t]) {
      let upperRole = '突破参考';
      let lowerRole = '突破参考';
      if (confirmed) {
        const dir = this._consolBreakDir(h);
        if (dir === 'up') {
          upperRole = '突破后转支撑';
          lowerRole = '下方支撑';
        } else if (dir === 'down') {
          lowerRole = '突破后转阻力';
          upperRole = '上方压力';
        }
      }
      add(lv.upper, '上沿', upperRole);
      add(lv.lower, '下沿', lowerRole);
    } else {
      // 兜底：有颈线/上下沿则带出
      add(lv.neckline, '颈线', '关键参考');
      add(lv.upper, '上沿', '突破参考');
      add(lv.lower, '下沿', '突破参考');
    }
    return out;
  },

  /**
   * 近价合并（相对 0.8% 内视为同一档）。
   * 同价多形态保留各来源语义标签（如「双底:颈线 | 下降楔形:上沿」），
   * 不再用 prefer 权重把展示名硬并成单一「颈线」；role 仍取最高优先级。
   */
  _mergeNearLevels(raw) {
    const namePrefer = {
      颈线: 3,
      双峰高点: 2,
      双谷低点: 2,
      头部高点: 2,
      头部低点: 2,
      右肩: 2,
      上沿: 1,
      下沿: 1,
    };
    const rolePrefer = {
      突破后转支撑: 6,
      突破后转阻力: 6,
      观察站稳: 5,
      观察失守: 5,
      下方支撑: 4,
      上方压力: 4,
      突破参考: 2,
      关键参考: 1,
    };
    const tagKey = (lv) => `${lv.source || ''}:${lv.name || ''}`;
    const pushTag = (hit, lv) => {
      if (!hit.tags) hit.tags = [];
      const k = tagKey(lv);
      if (hit.tags.some((t) => `${t.source}:${t.name}` === k)) return;
      hit.tags.push({ source: lv.source, name: lv.name });
    };
    const syncDisplayName = (hit) => {
      if (hit.tags && hit.tags.length) {
        hit.name = hit.tags.map((t) => `${t.source}:${t.name}`).join(' | ');
      }
    };
    const bumpPrimaryName = (hit, lvName) => {
      if (!hit.primaryName) {
        hit.primaryName = lvName;
        return;
      }
      if ((namePrefer[lvName] || 0) > (namePrefer[hit.primaryName] || 0)) {
        hit.primaryName = lvName;
      }
    };
    const bumpRole = (hit, role) => {
      if ((rolePrefer[role] || 0) > (rolePrefer[hit.role] || 0)) {
        hit.role = role;
      }
    };

    const merged = [];
    (raw || [])
      .slice()
      .sort((a, b) => a.price - b.price || b.conf - a.conf)
      .forEach((lv) => {
        const hit = merged.find((m) => {
          const base = Math.abs(m.price) || 1;
          return Math.abs(m.price - lv.price) / base <= 0.008;
        });
        if (!hit) {
          merged.push({
            price: lv.price,
            name: `${lv.source}:${lv.name}`,
            primaryName: lv.name,
            role: lv.role,
            tags: [{ source: lv.source, name: lv.name }],
            sources: [lv.source],
            observing: lv.observing,
            confirmed: !!lv.confirmed,
            conf: lv.conf,
          });
          return;
        }
        pushTag(hit, lv);
        bumpPrimaryName(hit, lv.name);
        if (lv.conf > hit.conf) {
          hit.price = lv.price;
          hit.conf = lv.conf;
        }
        if (hit.observing && !lv.observing) {
          hit.observing = false;
        }
        bumpRole(hit, lv.role);
        if (!hit.sources.includes(lv.source)) hit.sources.push(lv.source);
        hit.observing = hit.observing && lv.observing;
        hit.confirmed = hit.confirmed || !!lv.confirmed;
        syncDisplayName(hit);
      });
    return merged;
  },

  /** 合并档的价位名 token（用于打分/语义，不含形态前缀） */
  _levelNameTokens(m) {
    if (!m) return [];
    if (m.tags && m.tags.length) return m.tags.map((t) => t.name).filter(Boolean);
    if (m.primaryName) return [m.primaryName];
    const n = String(m.name || '');
    if (n.includes('|') || n.includes(':')) {
      return n
        .split('|')
        .map((s) => {
          const parts = s.trim().split(':');
          return (parts.length > 1 ? parts[parts.length - 1] : parts[0] || '').trim();
        })
        .filter(Boolean);
    }
    return n ? [n] : [];
  },

  _collectMergedLevels(items, opts) {
    const asof = this._inferAsof(items, opts);
    const ranked = this._rankHits(items, { asof });
    const raw = [];
    ranked.forEach((h) => {
      // 过期 forming 反转不进入结构防守（避免旧颈线霸榜）
      if (h.status === 'forming' && !this._isViablePrimaryCandidate(h, asof)) return;
      this._levelsFromHit(h).forEach((lv) => raw.push(lv));
    });
    return this._mergeNearLevels(raw);
  },

  /** 交易点位「意义」分：优先颈线翻支撑、峰谷/头、通道上下沿（多标签取最高分） */
  _tradeLevelScore(m, side) {
    const tokens = this._levelNameTokens(m);
    const scoreOne = (n) => {
      if (n === '颈线') return 50;
      if (n === '双谷低点' || n === '双峰高点' || n === '头部低点' || n === '头部高点') return 42;
      if (n === '右肩') return 40;
      if (n === 'L1' || n === 'L2' || n === 'H1' || n === 'H2') return 38;
      if (side === 'support' && n === '下沿') return 36;
      if (side === 'support' && n === '上沿') return 34; // 突破后翻支撑
      if (side === 'resistance' && n === '上沿') return 36;
      if (side === 'resistance' && n === '下沿') return 28;
      return 20;
    };
    let s = tokens.length ? Math.max(...tokens.map(scoreOne)) : 20;
    if (m.confirmed) s += 12;
    if (!m.observing) s += 6;
    return s;
  },

  /**
   * 相对现价的交易角色简述（形态名+角色）。
   * 已确认且原上沿/颈线落在现价下方 →「突破后翻支撑」。
   */
  _tradeLevelExplain(m, side) {
    const tokens = this._levelNameTokens(m);
    const has = (...names) => tokens.some((t) => names.indexOf(t) >= 0);
    const display =
      m.tags && m.tags.length
        ? m.tags.map((t) => `${t.source}:${t.name}`).join(' | ')
        : `${(m.sources && m.sources.length ? m.sources.join('/') : '') || '形态'}${
            m.primaryName || m.name || '关键位'
          }`;
    let meaning = '';
    if (side === 'support') {
      if (m.confirmed && has('颈线', '上沿')) meaning = '突破后翻支撑';
      else if (has('颈线')) meaning = '颈线支撑（观察中）';
      else if (has('双谷低点', 'L1', 'L2', '头部低点')) meaning = '形态低点支撑';
      else if (has('右肩')) meaning = '右肩支撑';
      else if (has('下沿')) meaning = '通道/形态下沿支撑';
      else if (has('上沿')) meaning = '上沿翻支撑（待确认）';
      else meaning = '下方支撑';
    } else {
      if (has('颈线')) meaning = m.confirmed ? '颈线阻力' : '颈线阻力（观察中）';
      else if (has('双峰高点', 'H1', 'H2', '头部高点')) meaning = '形态高点阻力';
      else if (has('右肩')) meaning = '右肩阻力';
      else if (has('上沿')) meaning = '通道/形态上沿阻力';
      else if (has('下沿')) meaning = m.confirmed ? '下沿翻阻力' : '下沿阻力（观察中）';
      else meaning = '上方阻力';
    }
    return `${display}，${meaning}`;
  },

  /**
   * 主形态几何边界：巩固取 upper/lower；反转取颈线按侧，阻力侧再取最近枢轴高点。
   * 用于结构档强制第一候选与软融合 patternBound（勿用「全库已选支撑 max」）。
   * @returns {{patternLower:number|null, patternUpper:number|null, supportSeed:object|null, resistSeed:object|null}}
   */
  _primaryGeometryBounds(primary, close) {
    const empty = {
      patternLower: null,
      patternUpper: null,
      supportSeed: null,
      resistSeed: null,
    };
    if (!primary || close == null) return empty;
    const eps = Math.abs(close) * 0.001;
    const lv = (primary && primary.key_levels) || {};
    const bounds = this._hitBounds(primary);
    const neck = this._hitNeck(primary);
    const conf = Number(primary.confidence) || 0;
    const observing = this._isObserving(primary);
    const confirmed = primary.status === 'confirmed';
    const src = this.typeLabel(primary.pattern_type);
    const mk = (price, name, role) => {
      const p = this._num(price);
      if (p == null) return null;
      return {
        price: p,
        name: `${src}:${name}`,
        primaryName: name,
        role: role || '关键参考',
        tags: [{ source: src, name }],
        sources: [src],
        observing,
        confirmed,
        conf,
        fromPrimaryGeom: true,
      };
    };

    let patternLower = null;
    let patternUpper = null;
    let supportSeed = null;
    let resistSeed = null;

    if (this.CONSOLIDATION[primary.pattern_type]) {
      const upper = bounds.upper;
      const lower = bounds.lower;
      if (lower != null && lower < close - eps) {
        patternLower = lower;
        supportSeed = mk(lower, '下沿', '下方支撑');
      } else if (upper != null && upper < close - eps) {
        // 已上破：上沿翻支撑
        patternLower = upper;
        supportSeed = mk(upper, '上沿', confirmed ? '突破后转支撑' : '下方支撑');
      }
      if (upper != null && upper > close + eps) {
        patternUpper = upper;
        resistSeed = mk(upper, '上沿', '上方压力');
      } else if (lower != null && lower > close + eps) {
        patternUpper = lower;
        resistSeed = mk(lower, '下沿', confirmed ? '突破后转阻力' : '上方压力');
      }
      return { patternLower, patternUpper, supportSeed, resistSeed };
    }

    // 反转：颈线按侧；阻力侧若颈线已在下方，取最近上方几何（右肩/头/双峰）
    if (neck != null && neck < close - eps) {
      patternLower = neck;
      supportSeed = mk(neck, '颈线', '观察失守');
    } else if (neck != null && neck > close + eps) {
      patternUpper = neck;
      resistSeed = mk(neck, '颈线', '观察站稳');
    }

    if (patternUpper == null) {
      const cands = [];
      const rs = this._hitRightShoulder(primary);
      const head = this._num(lv.head);
      const h1 = this._num(lv.h1);
      const h2 = this._num(lv.h2);
      if (rs != null && rs > close + eps) cands.push({ p: rs, name: '右肩', role: '上方压力' });
      if (
        head != null &&
        head > close + eps &&
        (this.BEARISH_REVERSAL[primary.pattern_type] || primary.pattern_type === 'double_top')
      ) {
        cands.push({ p: head, name: '头部高点', role: '上方压力' });
      }
      if (h1 != null && h1 > close + eps) cands.push({ p: h1, name: 'H1', role: '上方压力' });
      if (h2 != null && h2 > close + eps) cands.push({ p: h2, name: 'H2', role: '上方压力' });
      if (cands.length) {
        cands.sort((a, b) => a.p - b.p);
        const top = cands[0];
        patternUpper = top.p;
        resistSeed = mk(top.p, top.name, top.role);
      }
    }

    if (patternLower == null) {
      const cands = [];
      const rs = this._hitRightShoulder(primary);
      const head = this._num(lv.head);
      const l1 = this._num(lv.l1);
      const l2 = this._num(lv.l2);
      if (rs != null && rs < close - eps) cands.push({ p: rs, name: '右肩', role: '下方支撑' });
      if (
        head != null &&
        head < close - eps &&
        (this.BULLISH_REVERSAL[primary.pattern_type] ||
          primary.pattern_type === 'head_shoulders_bottom' ||
          primary.pattern_type === 'double_bottom')
      ) {
        cands.push({ p: head, name: '头部低点', role: '下方支撑' });
      }
      if (l1 != null && l1 < close - eps) cands.push({ p: l1, name: 'L1', role: '下方支撑' });
      if (l2 != null && l2 < close - eps) cands.push({ p: l2, name: 'L2', role: '下方支撑' });
      if (cands.length) {
        cands.sort((a, b) => b.p - a.p);
        const top = cands[0];
        patternLower = top.p;
        supportSeed = mk(top.p, top.name, top.role);
      }
    }

    return { patternLower, patternUpper, supportSeed, resistSeed };
  },

  /** 是否巩固类通道上沿（阻力）/下沿（支撑） */
  _isConsolChannelEdge(m, side) {
    if (!m) return false;
    const edgeName = side === 'resistance' ? '上沿' : '下沿';
    const consolLabels = new Set();
    Object.keys(this.CONSOLIDATION || {}).forEach((t) => {
      consolLabels.add(this.typeLabel(t));
    });
    if (m.tags && m.tags.length) {
      return m.tags.some(
        (t) => t && consolLabels.has(t.source) && t.name === edgeName
      );
    }
    const tokens = this._levelNameTokens(m);
    if (tokens.indexOf(edgeName) < 0) return false;
    const srcs = m.sources || (m.source ? [m.source] : []);
    return srcs.some((s) => consolLabels.has(s));
  },

  /**
   * 从合并关键位中按现价分支撑/阻力，取最有意义的 1～2 档。
   * 若提供 primaryGeom：主形态几何边界强制为第一候选；
   * 补第二档时优先距现价更近（同分再语义），并对近端巩固通道沿保送一席。
   * @returns {{supports:object[], resistances:object[]}}
   */
  _pickTradeLevels(merged, close, opts) {
    if (close == null || !merged || !merged.length) {
      // 仍可能仅有 primary 种子（merged 空极少见）
      const geom0 = (opts && opts.primaryGeom) || null;
      if (!geom0 || close == null) return { supports: [], resistances: [] };
      const supports = geom0.supportSeed ? [geom0.supportSeed] : [];
      const resistances = geom0.resistSeed ? [geom0.resistSeed] : [];
      return {
        supports: supports.sort((a, b) => b.price - a.price),
        resistances: resistances.sort((a, b) => a.price - b.price),
      };
    }
    const eps = Math.abs(close) * 0.001; // 贴近现价忽略
    const below = merged.filter((m) => m.price < close - eps);
    const above = merged.filter((m) => m.price > close + eps);
    const geom = (opts && opts.primaryGeom) || null;
    const nearTol = 0.008;
    const promotePct =
      this._num(this.TRADE_LEVEL_NEAR_CHANNEL_PROMOTE_PCT) != null
        ? this._num(this.TRADE_LEVEL_NEAR_CHANNEL_PROMOTE_PCT)
        : 0.03;

    const resolveSeed = (seed, pool) => {
      if (!seed || seed.price == null) return null;
      const hit = (pool || []).find((m) => {
        const base = Math.abs(m.price) || 1;
        return Math.abs(m.price - seed.price) / base <= nearTol;
      });
      if (hit) return { ...hit, fromPrimaryGeom: true };
      return seed;
    };

    const pick = (arr, side, forcedSeed) => {
      const forced = resolveSeed(forcedSeed, arr);
      const rest = arr.filter((m) => {
        if (!forced) return true;
        const base = Math.abs(m.price) || 1;
        return Math.abs(m.price - forced.price) / base > nearTol;
      });
      const scored = rest
        .slice()
        .sort((a, b) => {
          // primary 已强制第一档后：近距优先，同分再语义
          if (forced) {
            const da = Math.abs(a.price - close);
            const db = Math.abs(b.price - close);
            if (Math.abs(da - db) > 1e-12) return da - db;
            return this._tradeLevelScore(b, side) - this._tradeLevelScore(a, side);
          }
          const ds = this._tradeLevelScore(b, side) - this._tradeLevelScore(a, side);
          if (ds) return ds;
          return Math.abs(a.price - close) - Math.abs(b.price - close);
        });
      const out = [];
      if (forced) out.push(forced);
      scored.forEach((m) => {
        if (out.length >= 2) return;
        out.push(m);
      });

      // 近端巩固通道沿保送：距现价 ≤ promotePct，占第二席（不挤掉 primary 第一档）
      if (forced && promotePct > 0) {
        const baseClose = Math.abs(close) || 1;
        const alreadyHas = out.some((m) => this._isConsolChannelEdge(m, side));
        if (!alreadyHas) {
          const edgeCands = rest
            .filter((m) => {
              if (!this._isConsolChannelEdge(m, side)) return false;
              return Math.abs(m.price - close) / baseClose <= promotePct;
            })
            .sort(
              (a, b) => Math.abs(a.price - close) - Math.abs(b.price - close)
            );
          if (edgeCands.length) {
            const edge = edgeCands[0];
            if (out.length < 2) out.push(edge);
            else out[1] = edge;
          }
        }
      }

      return side === 'support'
        ? out.sort((a, b) => b.price - a.price)
        : out.sort((a, b) => a.price - b.price);
    };

    return {
      supports: pick(below, 'support', geom && geom.supportSeed),
      resistances: pick(above, 'resistance', geom && geom.resistSeed),
    };
  },

  /** 单侧区间文案：两档则高–低 / 低–高；一档则该价 */
  _tradeZoneText(levels, side) {
    if (!levels || !levels.length) return '';
    if (levels.length === 1) return this._fmtPx(levels[0].price);
    const a = levels[0].price;
    const b = levels[1].price;
    if (side === 'support') {
      const hi = Math.max(a, b);
      const lo = Math.min(a, b);
      return `${this._fmtPx(hi)} – ${this._fmtPx(lo)}`;
    }
    const lo = Math.min(a, b);
    const hi = Math.max(a, b);
    return `${this._fmtPx(lo)} – ${this._fmtPx(hi)}`;
  },

  /**
   * 空档占位：按已确认突破方向分支，禁止上破后仍写「等待形态边界突破」。
   * 无形态边界可等（真空）时改为共振位口径；形成中巩固仍可「等待突破」。
   */
  _emptyStructureSideText(side, ctx) {
    const dir = ctx && ctx.dir;
    const measuredDone = !!(ctx && ctx.measuredAchieved);
    if (side === 'resistance') {
      if (dir === 'up') {
        return measuredDone
          ? '形态边界已上破；上方暂无形态内阻力档'
          : '形态边界已上破；上方暂无形态内阻力档，近端关注简化测幅目标';
      }
      if (dir === 'down') {
        return '形态边界已下破；上方形态内阻力以原边界档为准';
      }
      // 形成中巩固或主导巩固未判明突破：保留等待突破口径
      if (ctx && (ctx.hasFormingConsol || ctx.lead)) {
        return '暂无明显阻力，等待形态边界突破后再定';
      }
      return '暂无活跃形态边界，暂无明显阻力共振位';
    }
    if (dir === 'down') {
      return measuredDone
        ? '形态边界已下破；下方暂无形态内支撑档'
        : '形态边界已下破；下方暂无形态内支撑档，近端关注简化测幅目标';
    }
    if (dir === 'up') {
      return '形态边界已上破；下方防守见上沿翻支撑等形态内档';
    }
    if (ctx && (ctx.hasFormingConsol || ctx.lead)) {
      return '暂无明显支撑，等待形态边界突破后再定';
    }
    return '暂无活跃形态边界，暂无明显支撑共振位';
  },

  /**
   * 从多维共振带取 1～2 档支撑/阻力（真空结构兜底；不编造假价）。
   * 优先 nearest_*，再按强度/近价综合排序。
   * @returns {{supports:object[], resistances:object[]}}
   */
  _pickConfluenceTradeLevels(confluence, close) {
    if (!confluence || typeof confluence !== 'object') {
      return { supports: [], resistances: [] };
    }
    const toLevel = (z, side) => {
      if (!z || typeof z !== 'object') return null;
      const price = this._num(z.center);
      if (price == null) return null;
      const rawStr = this._num(z.strength) || 0;
      const eff = this._effectiveZoneStrength(z) || rawStr;
      const lv = {
        price,
        low: this._num(z.low),
        high: this._num(z.high),
        strength: eff,
        strengthRaw: rawStr,
        sources: Array.isArray(z.sources) ? z.sources : [],
        fromConfluence: true,
        side,
      };
      if (z.chips_void) {
        lv.chips_void = true;
        if (z.void_note) lv.void_note = z.void_note;
        const adj = this._num(z.strength_adjusted);
        if (adj != null) lv.strength_adjusted = adj;
      }
      if (z.chips_hvz) {
        lv.chips_hvz = true;
        if (z.hvz_note) lv.hvz_note = z.hvz_note;
        if (z.hvz_source) lv.hvz_source = z.hvz_source;
        const adj = this._num(z.strength_adjusted);
        if (adj != null) lv.strength_adjusted = adj;
      }
      return lv;
    };
    const score = (lv) => {
      const dist =
        close != null && lv.price != null
          ? Math.abs(close - lv.price) / Math.abs(lv.price || 1)
          : 0;
      return (lv.strength || 0) / (1 + dist * 40);
    };
    const mergeSide = (list, nearest, side) => {
      const out = [];
      const push = (lv) => {
        if (!lv) return;
        if (out.some((x) => Math.abs(x.price - lv.price) < 1e-6)) return;
        out.push(lv);
      };
      (list || []).forEach((z) => push(toLevel(z, side)));
      if (nearest) push(toLevel(nearest, side));
      return out
        .sort((a, b) => {
          const ds = score(b) - score(a);
          if (Math.abs(ds) > 1e-9) return ds;
          if (close == null) return 0;
          return Math.abs(a.price - close) - Math.abs(b.price - close);
        })
        .slice(0, 2);
    };
    const supports = mergeSide(
      confluence.supports,
      confluence.nearest_support_zone,
      'support'
    ).sort((a, b) => b.price - a.price);
    const resistances = mergeSide(
      confluence.resistances,
      confluence.nearest_resistance_zone,
      'resistance'
    ).sort((a, b) => a.price - b.price);
    return { supports, resistances };
  },

  _confluenceLevelExplain(m, side) {
    const role = side === 'support' ? '支撑' : '阻力';
    const str =
      m && m.strengthRaw != null && Number.isFinite(Number(m.strengthRaw))
        ? Number(m.strengthRaw).toFixed(1)
        : m && m.strength != null && Number.isFinite(Number(m.strength))
          ? Number(m.strength).toFixed(1)
          : '--';
    let text = `多维共振带${role}，强度 ${str}`;
    if (m && m.chips_void && m.void_note) {
      text += `（注：${m.void_note}）`;
    } else if (m && m.chips_hvz && m.hvz_note) {
      text += `（注：${m.hvz_note}）`;
    }
    return text;
  },

  _hasConfluenceZones(confluence) {
    if (!confluence || typeof confluence !== 'object') return false;
    if ((confluence.supports || []).some((z) => z && z.center != null)) return true;
    if ((confluence.resistances || []).some((z) => z && z.center != null)) return true;
    if (confluence.nearest_support_zone && confluence.nearest_support_zone.center != null)
      return true;
    if (
      confluence.nearest_resistance_zone &&
      confluence.nearest_resistance_zone.center != null
    )
      return true;
    return false;
  },

  /** 展开支撑/压力带（含 nearest_*），按 center 去重。 */
  _iterConfluenceZones(confluence, side) {
    if (!confluence || typeof confluence !== 'object') return [];
    const out = [];
    const push = (z) => {
      if (!z || typeof z !== 'object') return;
      const price = this._num(z.center != null ? z.center : z.price);
      if (price == null) return;
      if (out.some((x) => Math.abs(x.price - price) < 1e-6)) return;
      out.push({
        price,
        low: this._num(z.low),
        high: this._num(z.high),
        strength: this._effectiveZoneStrength(z) || 0,
        strengthRaw: this._num(z.strength) || 0,
        sources: Array.isArray(z.sources) ? z.sources : [],
        fromConfluence: true,
        side,
        chips_void: !!z.chips_void,
        void_note: z.void_note || null,
        chips_hvz: !!z.chips_hvz,
        hvz_note: z.hvz_note || null,
        hvz_source: z.hvz_source || null,
        strength_adjusted: this._num(z.strength_adjusted),
      });
    };
    if (side === 'support') {
      (confluence.supports || []).forEach(push);
      if (confluence.nearest_support_zone) push(confluence.nearest_support_zone);
    } else {
      (confluence.resistances || []).forEach(push);
      if (confluence.nearest_resistance_zone) push(confluence.nearest_resistance_zone);
    }
    return out;
  },

  /**
   * Soft 夹层候选：经典夹层，或贴身带（阻力 high>close / 支撑 low<close，且未越过形态边界）。
   */
  _isSoftBufferSandwichCand(lv, side, close, patternBound) {
    if (!lv || close == null || patternBound == null) return false;
    const high = lv.high != null ? lv.high : lv.price;
    const low = lv.low != null ? lv.low : lv.price;
    if (side === 'support') {
      if (!(lv.price > patternBound)) return false;
      // 经典：patternBound < center < close；贴身：low < close 且 center 未明显高于现价
      if (lv.price < close) return true;
      return low < close && lv.price <= close;
    }
    if (!(lv.price < patternBound)) return false;
    // 经典：close < center < patternBound；贴身：high > close 且 center≥close（或带 straddling）
    if (lv.price > close) return true;
    return high > close && lv.price >= close;
  },

  /** 贴身临界：距现价 < CONTACT_PCT，且阻力 high>close / 支撑 low<close */
  _isSoftContactBand(lv, side, close) {
    if (!lv || close == null) return false;
    const px = Math.abs(close) || 1;
    const distPct = Math.abs((lv.price || 0) - close) / px;
    const maxPct =
      this._num(this.CONFLUENCE_SOFT_CONTACT_PCT) != null
        ? this.CONFLUENCE_SOFT_CONTACT_PCT
        : 0.005;
    if (!(distPct >= 0 && distPct < maxPct)) return false;
    if (side === 'support') {
      const low = lv.low != null ? lv.low : lv.price;
      return low < close;
    }
    const high = lv.high != null ? lv.high : lv.price;
    return high > close;
  },

  /**
   * 有主形态时的受控软融合：在「形态边界 ↔ 现价」夹层内取**近端优先**的一条共振带
   *（strength≥min；同分再比强度）。勿只取最强更远带。
   * 支撑/阻力均支持贴身带（high>close / low<close）。
   * 贴身 CONTACT 带允许强度 ≥ TACTICAL_MIN(4) 进入 soft/贴身档（不必满 10）。
   * @returns {object|null}
   */
  _pickConfluenceSoftBuffer(confluence, opts) {
    const o = opts || {};
    const side = o.side === 'resistance' ? 'resistance' : 'support';
    const close = this._num(o.close);
    const patternBound = this._num(o.patternBound);
    const minStr =
      this._num(o.minStrength) != null
        ? this._num(o.minStrength)
        : this.CONFLUENCE_SOFT_BUFFER_MIN_STRENGTH;
    const contactMin =
      this._num(o.contactMinStrength) != null
        ? this._num(o.contactMinStrength)
        : this.CONFLUENCE_TACTICAL_CAP_MIN_STRENGTH;
    if (close == null || patternBound == null || !Number.isFinite(minStr)) return null;
    const byNearThenStr = (a, b) => {
      const da = Math.abs(a.price - close);
      const db = Math.abs(b.price - close);
      if (Math.abs(da - db) > 1e-12) return da - db;
      return (b.strength || 0) - (a.strength || 0);
    };
    const sandwich = this._iterConfluenceZones(confluence, side).filter((lv) =>
      this._isSoftBufferSandwichCand(lv, side, close, patternBound)
    );
    const softCands = sandwich.filter((lv) => (lv.strength || 0) >= minStr);
    // 贴身强度缝 [tacticalMin, softMin)：可进 soft；若已有 ≥softMin 候选，须更近且强度≥其一半（避免弱贴价带挤掉强近端缓冲）
    const contactMidCands = sandwich.filter((lv) => {
      const str = lv.strength || 0;
      if (str < contactMin || str >= minStr) return false;
      return this._isSoftContactBand(lv, side, close);
    });
    let cands = softCands.slice();
    if (contactMidCands.length) {
      if (!softCands.length) {
        cands = contactMidCands.slice();
      } else {
        softCands.sort(byNearThenStr);
        contactMidCands.sort(byNearThenStr);
        const bestSoft = softCands[0];
        const bestContact = contactMidCands[0];
        const contactNearer =
          Math.abs(bestContact.price - close) < Math.abs(bestSoft.price - close) - 1e-12;
        const competitive =
          (bestContact.strength || 0) >= (bestSoft.strength || 0) * 0.5;
        if (contactNearer && competitive) cands = [bestContact];
      }
    }
    if (!cands.length) return null;
    cands.sort(byNearThenStr);
    const top = cands[0];
    const softContact = this._isSoftContactBand(top, side, close);
    return {
      ...top,
      softBuffer: true,
      softContact,
      fromConfluence: true,
    };
  },

  _softBufferExplain(m, side) {
    const role = side === 'support' ? '支撑' : '阻力';
    const str =
      m && m.strengthRaw != null && Number.isFinite(Number(m.strengthRaw))
        ? Number(m.strengthRaw).toFixed(1)
        : m && m.strength != null && Number.isFinite(Number(m.strength))
          ? Number(m.strength).toFixed(1)
          : '--';
    const contactHint = m && m.softContact ? '，贴身临界' : '';
    let text = `超级量化共振带${role}，强度 ${str}${contactHint}`;
    if (m && m.chips_void && m.void_note) {
      text += `（注：${m.void_note}）`;
    } else if (m && m.chips_hvz && m.hvz_note) {
      text += `（注：${m.hvz_note}）`;
    }
    return text;
  },

  /**
   * 同 status、|Δconf|&lt;eps、bias 冲突的近邻形态（文案层「多空交织」用；不改 primary）。
   */
  _findNearConflictingPeer(primary, pool, eps) {
    if (!primary || !Array.isArray(pool)) return null;
    const pb = this._biasOf(primary.pattern_type);
    const pc = this._num(primary.confidence);
    if (pc == null) return null;
    const epsUse =
      this._num(eps) != null ? this._num(eps) : this.RANK_CONF_TIE_EPS;
    const st = String(primary.status || '');
    for (let i = 0; i < pool.length; i++) {
      const h = pool[i];
      if (!h || h === primary) continue;
      if (String(h.status || '') !== st) continue;
      if (!this._biasConflicts(pb, this._biasOf(h.pattern_type))) continue;
      const hc = this._num(h.confidence);
      if (hc == null) continue;
      if (Math.abs(pc - hc) < epsUse) return h;
    }
    return null;
  },

  /** 共振带来源是否含 VP VAH（价值区上沿）叠层 */
  _isVpVahSources(sources) {
    const srcs = Array.isArray(sources) ? sources : [];
    return srcs.some((s) => {
      const t = String(s || '').toLowerCase();
      return t === 'vah' || t === 'vp_vah' || t.includes('vah');
    });
  },

  /**
   * 贴身/战术判距：取 center 与更近边界（支撑看 high，阻力看 low）的最小间距，
   * 避免 high≈close / low≈close 时仅因 center 落入 nearEps 被误杀。
   */
  _contactEdgeGap(lv, side, close) {
    if (!lv || close == null || lv.price == null) return null;
    if (side === 'support') {
      const toCenter = Math.abs(close - lv.price);
      const toHigh =
        lv.high != null && Number.isFinite(lv.high) ? Math.abs(close - lv.high) : toCenter;
      return Math.min(toCenter, toHigh);
    }
    const toCenter = Math.abs(lv.price - close);
    const toLow =
      lv.low != null && Number.isFinite(lv.low) ? Math.abs(lv.low - close) : toCenter;
    return Math.min(toCenter, toLow);
  },

  /**
   * 弱近端「日内/临界压制/支撑」：夹层共振强度可低于 soft buffer（默认 ≥4），
   * 或 VP VAH 叠层单独识别。不占用核心双档席位，仅供战术说明行。
   * 排除已达 soft buffer 门槛（≥10）或已占 soft/贴身席的带；贴身 CONTACT 豁免 nearEps。
   * @returns {object|null}
   */
  _pickConfluenceTacticalCap(confluence, opts) {
    const o = opts || {};
    const side = o.side === 'resistance' ? 'resistance' : 'support';
    const close = this._num(o.close);
    const patternBound = this._num(o.patternBound);
    const minStr =
      this._num(o.minStrength) != null
        ? this._num(o.minStrength)
        : this.CONFLUENCE_TACTICAL_CAP_MIN_STRENGTH;
    const softMin =
      this._num(o.softMinStrength) != null
        ? this._num(o.softMinStrength)
        : this.CONFLUENCE_SOFT_BUFFER_MIN_STRENGTH;
    if (close == null || patternBound == null || !Number.isFinite(minStr)) return null;
    // 弱带贴价约 0.3% 内不提示；soft≥10 / 贴身 CONTACT 不走此过滤
    const nearEpsPct =
      this._num(o.nearEpsPct) != null
        ? this._num(o.nearEpsPct)
        : this.CONFLUENCE_TACTICAL_NEAR_EPS_PCT;
    const nearEps =
      this._num(o.nearEps) != null
        ? this._num(o.nearEps)
        : Math.abs(close) * (nearEpsPct != null ? nearEpsPct : 0.003);
    const exclude = Array.isArray(o.excludePrices) ? o.excludePrices : [];
    const cands = this._iterConfluenceZones(confluence, side).filter((lv) => {
      const str = lv.strength || 0;
      const vpVah = this._isVpVahSources(lv.sources);
      if (str < minStr && !vpVah) return false;
      // 已达超级共振 soft 门槛的留给 soft buffer，不在战术行重复
      if (str >= softMin) return false;
      if (exclude.some((p) => p != null && Math.abs(p - lv.price) < 1e-6)) return false;
      const isContact = this._isSoftContactBand(lv, side, close);
      // 贴身且 ≥tacticalMin：无 soft 席时豁免 nearEps；已有 soft 席则仍按贴价过滤（避免弱贴价噪音）
      if (isContact && str >= minStr) {
        const inWin =
          side === 'support'
            ? lv.price > patternBound && (lv.low != null ? lv.low : lv.price) < close
            : lv.price < patternBound && (lv.high != null ? lv.high : lv.price) > close;
        if (!inWin) return false;
        if (!exclude.length) return true;
        const gap = this._contactEdgeGap(lv, side, close);
        return !(gap != null && gap <= nearEps);
      }
      if (side === 'support') {
        if (!(lv.price > patternBound && lv.price < close)) return false;
        const gap = this._contactEdgeGap(lv, side, close);
        if (gap != null && gap <= nearEps) return false;
        return lv.price - patternBound > nearEps;
      }
      if (!(lv.price > close && lv.price < patternBound)) return false;
      const gap = this._contactEdgeGap(lv, side, close);
      if (gap != null && gap <= nearEps) return false;
      return patternBound - lv.price > nearEps;
    });
    if (!cands.length) return null;
    cands.sort((a, b) => {
      const da = Math.abs(a.price - close);
      const db = Math.abs(b.price - close);
      if (Math.abs(da - db) > 1e-12) return da - db;
      return (b.strength || 0) - (a.strength || 0);
    });
    const top = cands[0];
    return {
      ...top,
      tacticalCap: true,
      fromConfluence: true,
    };
  },

  /**
   * 上破后形态阻力真空：单侧近端降级补 1 档。
   * 优先 confluence.resistances（标强度）；再 ATR-Pivot R1 / 最近 KDE 阻力。
   * 仅取现价上方；已跌破的 VAH/Fib 等不得写回上方阻力。
   * @returns {object|null}
   */
  _pickDegradedBreakoutResistance(close, opts) {
    const o = opts || {};
    const c = this._num(close);
    if (c == null) return null;
    const eps = Math.abs(c) * 0.001;
    const usableOverhead = (lv) => {
      if (!lv || lv.price == null) return false;
      if (!(lv.price > c + eps)) return false;
      const high = lv.high != null ? lv.high : lv.price;
      // 整带已落在现价下/贴价：视为已跌破，不写回上方
      if (!(high > c + eps)) return false;
      return true;
    };
    const confCands = this._iterConfluenceZones(o.confluenceZones, 'resistance')
      .filter(usableOverhead)
      .sort((a, b) => {
        const da = a.price - c;
        const db = b.price - c;
        if (Math.abs(da - db) > 1e-12) return da - db;
        return (b.strength || 0) - (a.strength || 0);
      });
    if (confCands.length) {
      const top = confCands[0];
      return {
        ...top,
        degradedRef: true,
        fromConfluence: true,
        degradeSource: 'confluence',
      };
    }
    const classic = o.classicLevels || {};
    const atr = classic.atr_pivot || classic.atrPivot || null;
    if (atr && typeof atr === 'object') {
      const r1 = this._num(atr.R1 != null ? atr.R1 : atr.r1);
      const atrNear = this._num(atr.nearest_resistance);
      const px = r1 != null && r1 > c + eps ? r1 : atrNear != null && atrNear > c + eps ? atrNear : null;
      if (px != null) {
        return {
          price: px,
          strength: null,
          sources: ['atr_pivot'],
          degradedRef: true,
          fromConfluence: false,
          degradeSource: 'atr_pivot',
        };
      }
    }
    const kde = o.kdeLevels || {};
    let kdePx = this._num(kde.nearest_resistance);
    if (kdePx == null && Array.isArray(kde.resistance_levels)) {
      const above = kde.resistance_levels
        .map((x) => this._num(x && x.price != null ? x.price : x))
        .filter((p) => p != null && p > c + eps)
        .sort((a, b) => a - b);
      if (above.length) kdePx = above[0];
    }
    if (kdePx != null && kdePx > c + eps) {
      return {
        price: kdePx,
        strength: null,
        sources: ['kde'],
        degradedRef: true,
        fromConfluence: false,
        degradeSource: 'kde',
      };
    }
    return null;
  },

  _degradedResistExplain(m) {
    const src = (m && m.degradeSource) || '';
    const str =
      m && m.strength != null && Number.isFinite(Number(m.strength))
        ? Number(m.strength).toFixed(1)
        : null;
    if (src === 'confluence') {
      return str != null
        ? `参考/降级：多维共振带阻力，强度 ${str}（非形态几何阻力）`
        : '参考/降级：多维共振带阻力（非形态几何阻力）';
    }
    if (src === 'atr_pivot') {
      return '参考/降级：ATR-Pivot R1（非形态几何阻力）';
    }
    if (src === 'kde') {
      return '参考/降级：最近 KDE 阻力（非形态几何阻力）';
    }
    return '参考/降级阻力（非形态几何阻力）';
  },

  _tacticalCapExplain(m, side) {
    const role = side === 'resistance' ? '压制' : '支撑';
    const str =
      m && m.strength != null && Number.isFinite(Number(m.strength))
        ? Number(m.strength).toFixed(1)
        : '--';
    const vpHint = this._isVpVahSources(m && m.sources) ? '，含 VP VAH' : '';
    return `弱共振${role}，强度 ${str}${vpHint}；有别于近端缓冲/第一压制（强度≥${this.CONFLUENCE_SOFT_BUFFER_MIN_STRENGTH}）`;
  },

  /**
   * 结构防守与目标（合并原「关键位置参考」+「后续交易点位参考」）。
   * 分层：防守/支撑 → 目标/近端形态阻力（含巩固简化测幅）。
   * 真空（无主形态档）时可用 opts.confluenceZones 共振带整侧兜底；
   * 有活跃形态档时不硬盖，仅允许「现价↔形态边界」高强夹层作近端缓冲。
   * @returns {{html:string,text:string}}
   */
  buildStructureLevelsReference(items, opts) {
    const options = opts || {};
    const asof = this._inferAsof(items, options);
    const ranked = this._rankHits(items, { asof });
    const primary = this._pickPrimary(ranked, asof);
    let close = null;
    for (let i = 0; i < ranked.length; i++) {
      close = this._hitClose(ranked[i]);
      if (close != null) break;
    }
    // 真空时 ranked 可能只剩过期 forming；再从全量 items（含归档）取收盘
    if (close == null) {
      for (let i = 0; i < (items || []).length; i++) {
        close = this._hitClose(items[i]);
        if (close != null) break;
      }
    }
    const merged = this._collectMergedLevels(items, { asof });
    const primaryGeom = primary ? this._primaryGeometryBounds(primary, close) : null;
    let { supports, resistances } = this._pickTradeLevels(merged, close, {
      primaryGeom,
    });
    // 若合并池未带出 primary 几何（极少），仍用种子兜底
    if (primaryGeom) {
      if (!supports.length && primaryGeom.supportSeed) supports = [primaryGeom.supportSeed];
      if (!resistances.length && primaryGeom.resistSeed) resistances = [primaryGeom.resistSeed];
    }
    const ctx = this._leadConsolBreakContext(items, { asof });
    const measured = ctx.measured;
    const measuredAchieved = this._isMeasuredAchieved(measured, close);
    ctx.measuredAchieved = measuredAchieved;
    // 真空（无主形态，或两侧皆空且无巩固突破）才共振整侧兜底
    const useConfluenceFallback =
      !primary ||
      (!supports.length && !resistances.length && !measured && !ctx.dir);
    let supportFromConf = false;
    let resistFromConf = false;
    let resistDegraded = false;
    let resistFromWedgeAlert = false;
    if (useConfluenceFallback && this._hasConfluenceZones(options.confluenceZones)) {
      const confLv = this._pickConfluenceTradeLevels(options.confluenceZones, close);
      if (!supports.length && confLv.supports.length) {
        supports = confLv.supports;
        supportFromConf = true;
      }
      if (!resistances.length && confLv.resistances.length) {
        resistances = confLv.resistances;
        resistFromConf = true;
      }
    }
    // P0：楔形蓄势突破预警已给出上方共振目标时，结构阻力侧优先挂预警目标（避免「等待突破」真空占位）
    if (!resistances.length) {
      const tactical = options.tactical && typeof options.tactical === 'object' ? options.tactical : null;
      const alert =
        tactical && tactical.wedge_breakout_alert && typeof tactical.wedge_breakout_alert === 'object'
          ? tactical.wedge_breakout_alert
          : null;
      const alertOk =
        alert &&
        (alert.ok === true ||
          tactical.display_status === '楔形蓄势突破预警' ||
          alert.display_status === '楔形蓄势突破预警');
      const alertPx =
        alertOk && alert.target != null && Number.isFinite(Number(alert.target))
          ? Number(alert.target)
          : alertOk &&
              alert.alert_target != null &&
              Number.isFinite(Number(alert.alert_target))
            ? Number(alert.alert_target)
            : null;
      if (alertPx != null) {
        const astr =
          alert.target_strength != null && Number.isFinite(Number(alert.target_strength))
            ? Number(alert.target_strength)
            : null;
        resistances = [
          {
            price: alertPx,
            strength: astr,
            strengthRaw: astr,
            fromConfluence: true,
            fromWedgeAlert: true,
            side: 'resistance',
            sources: ['wedge_breakout_alert'],
          },
        ];
        resistFromConf = true;
        resistFromWedgeAlert = true;
      }
    }
    // 受控软融合：patternBound 取 primary 几何边界（非「已选支撑 max」），夹层近端优先为缓冲/贴身
    // 贴身 CONTACT≥4 可进 soft；强度≥10 / 贴身不得被战术 0.3% nearEps 静默丢弃
    let supportSoftFusion = false;
    let resistSoftFusion = false;
    if (
      primary &&
      primaryGeom &&
      !supportFromConf &&
      supports.length &&
      close != null &&
      this._hasConfluenceZones(options.confluenceZones)
    ) {
      const patternLower =
        primaryGeom.patternLower != null
          ? primaryGeom.patternLower
          : Math.max(...supports.map((m) => m.price));
      const buf = this._pickConfluenceSoftBuffer(options.confluenceZones, {
        side: 'support',
        patternBound: patternLower,
        close,
      });
      if (buf) {
        const nearTol = 0.008;
        let core =
          supports.find((m) => {
            if (primaryGeom.patternLower == null) return false;
            const base = Math.abs(m.price) || 1;
            return Math.abs(m.price - primaryGeom.patternLower) / base <= nearTol;
          }) ||
          primaryGeom.supportSeed ||
          supports.slice().sort((a, b) => b.price - a.price)[0] ||
          supports[0];
        supports = [
          buf,
          {
            ...core,
            softCore: true,
            fromConfluence: false,
          },
        ];
        supportSoftFusion = true;
      }
    }
    // 阻力侧与支撑同构：patternBound = primary 上沿/近端几何阻力；≤2 档优先贴身/近端 + 核心
    if (
      primary &&
      primaryGeom &&
      !resistFromConf &&
      !resistDegraded &&
      resistances.length &&
      close != null &&
      this._hasConfluenceZones(options.confluenceZones)
    ) {
      const patternUpper =
        primaryGeom.patternUpper != null
          ? primaryGeom.patternUpper
          : Math.min(...resistances.map((m) => m.price));
      const buf = this._pickConfluenceSoftBuffer(options.confluenceZones, {
        side: 'resistance',
        patternBound: patternUpper,
        close,
      });
      if (buf) {
        const nearTol = 0.008;
        let core =
          resistances.find((m) => {
            if (primaryGeom.patternUpper == null) return false;
            const base = Math.abs(m.price) || 1;
            return Math.abs(m.price - primaryGeom.patternUpper) / base <= nearTol;
          }) ||
          primaryGeom.resistSeed ||
          resistances.slice().sort((a, b) => a.price - b.price)[0] ||
          resistances[0];
        resistances = [
          buf,
          {
            ...core,
            softCore: true,
            fromConfluence: false,
          },
        ];
        resistSoftFusion = true;
      }
    }

    // P1：已确认上破且形态阻力空 → 共振近端 / ATR-Pivot / KDE 单侧降级补 1 档
    if (
      primary &&
      ctx.dir === 'up' &&
      !resistances.length &&
      !resistFromConf &&
      close != null
    ) {
      const deg = this._pickDegradedBreakoutResistance(close, options);
      if (deg) {
        resistances = [deg];
        resistDegraded = true;
      }
    }

    // P1-B：弱近端「日内/临界压制/支撑」——不占核心双档，仅战术说明行
    let supportTactical = null;
    let resistTactical = null;
    const softExcludeSup = supportSoftFusion && supports[0] ? [supports[0].price] : [];
    const softExcludeRes = resistSoftFusion && resistances[0] ? [resistances[0].price] : [];
    if (
      primary &&
      primaryGeom &&
      !supportFromConf &&
      close != null &&
      this._hasConfluenceZones(options.confluenceZones)
    ) {
      const patternLower =
        primaryGeom.patternLower != null
          ? primaryGeom.patternLower
          : supports.length
            ? Math.max(...supports.map((m) => m.price))
            : null;
      if (patternLower != null) {
        supportTactical = this._pickConfluenceTacticalCap(options.confluenceZones, {
          side: 'support',
          patternBound: patternLower,
          close,
          excludePrices: softExcludeSup,
        });
      }
    }
    if (
      primary &&
      primaryGeom &&
      !resistFromConf &&
      !resistDegraded &&
      close != null &&
      this._hasConfluenceZones(options.confluenceZones)
    ) {
      const patternUpper =
        primaryGeom.patternUpper != null
          ? primaryGeom.patternUpper
          : resistances.length
            ? Math.min(...resistances.map((m) => m.price))
            : null;
      // 夹层上界：优先 primary 几何上沿；若第一形态阻力更远，可用其扩大扫描窗
      let capBound = patternUpper;
      if (resistances.length) {
        const firstResist = Math.min(...resistances.map((m) => m.price));
        if (capBound == null || firstResist > capBound) capBound = firstResist;
      }
      if (capBound != null) {
        resistTactical = this._pickConfluenceTacticalCap(options.confluenceZones, {
          side: 'resistance',
          patternBound: capBound,
          close,
          excludePrices: softExcludeRes,
        });
      }
    }

    const supportZone = this._tradeZoneText(supports, 'support');
    const resistZone = this._tradeZoneText(resistances, 'resistance');

    const supportLines = [];
    const supportLis = [];
    if (!supports.length) {
      if (measured && measured.dir === 'down' && !measuredAchieved) {
        const note = '形态边界已下破；下方暂无形态内支撑档';
        supportLines.push(note);
        supportLis.push(note);
      } else {
        const emptySup = this._emptyStructureSideText('support', ctx);
        supportLines.push(emptySup);
        supportLis.push(null);
      }
    } else {
      supports.forEach((m, idx) => {
        let label;
        if (m.softBuffer) {
          label = m.softContact ? '贴身临界支撑' : '近端缓冲防守';
        } else if (m.softCore || (supportSoftFusion && !m.fromConfluence))
          label = '核心破位防守';
        else label = idx === 0 ? '直接支撑' : '强底支撑';
        const explain = m.softBuffer
          ? this._softBufferExplain(m, 'support')
          : m.fromConfluence
            ? this._confluenceLevelExplain(m, 'support')
            : this._tradeLevelExplain(m, 'support');
        const line = `${label}：${this._fmtPx(m.price)} 附近（${explain}）`;
        supportLines.push(line);
        supportLis.push(line);
      });
    }
    if (measured && measured.dir === 'down') {
      const line = this._measuredMoveBulletText(
        measuredAchieved ? { ...measured, achieved: true } : measured
      );
      supportLines.push(line);
      supportLis.push(line);
    }
    if (supportTactical) {
      const line = `日内/临界支撑：${this._fmtPx(supportTactical.price)} 附近（${this._tacticalCapExplain(
        supportTactical,
        'support'
      )}）`;
      supportLines.push(line);
      supportLis.push(line);
    }

    const resistLines = [];
    const resistLis = [];
    if (!resistances.length) {
      if (measured && measured.dir === 'up' && !measuredAchieved) {
        const note = '形态边界已上破；上方暂无形态内阻力档';
        resistLines.push(note);
        resistLis.push(note);
      } else {
        const emptyRes = this._emptyStructureSideText('resistance', ctx);
        resistLines.push(emptyRes);
        resistLis.push(null);
      }
    } else {
      resistances.forEach((m, idx) => {
        let label;
        if (m.fromWedgeAlert) {
          label = '预警目标';
        } else if (m.degradedRef) {
          label = '参考阻力（降级）';
        } else if (m.softBuffer) {
          label = m.softContact ? '贴身临界压制' : '近端缓冲/第一压制';
        } else if (m.softCore || (resistSoftFusion && !m.fromConfluence))
          label = '核心形态阻力';
        else label = idx === 0 ? '第一阻力' : '第二阻力';
        const explain = m.fromWedgeAlert
          ? this._confluenceLevelExplain(m, 'resistance')
          : m.degradedRef
          ? this._degradedResistExplain(m)
          : m.softBuffer
            ? this._softBufferExplain(m, 'resistance')
            : m.fromConfluence
              ? this._confluenceLevelExplain(m, 'resistance')
              : this._tradeLevelExplain(m, 'resistance');
        const line = `${label}：${this._fmtPx(m.price)} 附近（${explain}）`;
        resistLines.push(line);
        resistLis.push(line);
      });
    }
    if (measured && measured.dir === 'up') {
      const line = this._measuredMoveBulletText(
        measuredAchieved ? { ...measured, achieved: true } : measured
      );
      // 已兑现：仅背景一句，不作为上方阻力档；未兑现仍输出测幅目标
      resistLines.push(line);
      resistLis.push(line);
    }
    if (resistTactical) {
      const line = `日内/临界压制：${this._fmtPx(resistTactical.price)} 附近（${this._tacticalCapExplain(
        resistTactical,
        'resistance'
      )}）`;
      resistLines.push(line);
      resistLis.push(line);
    }

    const supportHead =
      supports.length > 0
        ? `防守/支撑：${supportZone}`
        : measured && measured.dir === 'down' && !measuredAchieved
          ? '防守/支撑与下方目标：'
          : '防守/支撑：';
    const resistHead =
      resistances.length > 0
        ? resistDegraded
          ? `目标/近端参考阻力（降级）：${resistZone}`
          : resistFromWedgeAlert
            ? `目标/预警共振阻力：${resistZone}`
            : resistFromConf
              ? `目标/近端共振阻力：${resistZone}`
              : `目标/近端形态阻力：${resistZone}`
        : supportFromConf && !resistances.length
          ? '目标/近端共振阻力：'
          : '目标/近端形态阻力：';
    const supportUl =
      supportLis.filter((x) => x != null).length > 0
        ? `<ul>${supportLis
            .filter((x) => x != null)
            .map((line) => `<li>${this.esc(line)}</li>`)
            .join('')}</ul>`
        : '';
    const resistUl =
      resistLis.filter((x) => x != null).length > 0
        ? `<ul>${resistLis
            .filter((x) => x != null)
            .map((line) => `<li>${this.esc(line)}</li>`)
            .join('')}</ul>`
        : '';

    const supportEmptyOnly =
      supportLis.every((x) => x == null) && supportLines.length
        ? `<p>${this.esc(supportLines[0])}</p>`
        : '';
    const resistEmptyOnly =
      resistLis.every((x) => x == null) && resistLines.length
        ? `<p>${this.esc(resistLines[0])}</p>`
        : '';

    const html = `<div class="pattern-expert-trade-levels">
      <p><span class="pattern-expert-label">结构防守与目标：</span></p>
      <p>${this.esc(supportHead)}</p>
      ${supportUl || supportEmptyOnly}
      <p>${this.esc(resistHead)}</p>
      ${resistUl || resistEmptyOnly}
    </div>`;

    const textParts = ['结构防守与目标：', supportHead];
    supportLines.forEach((ln) => textParts.push(`· ${ln}`));
    textParts.push(resistHead);
    resistLines.forEach((ln) => textParts.push(`· ${ln}`));
    const text = textParts.filter(Boolean).join('\n');

    return { html, text };
  },

  /** @deprecated 兼容旧调用：返回结构块 HTML */
  buildTradeLevelsReference(items) {
    return this.buildStructureLevelsReference(items).html;
  },

  /**
   * 汇总多形态关键位：近价去重、按价格升序、标注来源与观察中。
   * @returns {string}
   */
  buildKeyLevelsReference(items, opts) {
    const asof = this._inferAsof(items, opts);
    const ranked = this._rankHits(items, { asof });
    const merged = this._collectMergedLevels(items, { asof });
    if (!merged.length) return '';

    merged.sort((a, b) => a.price - b.price);

    const parts = merged.map((m) => {
      // name 已含「形态:价位名」并列标签，不再重复拼接 sources
      const obs = m.observing ? ' · 观察中' : '';
      return `${this._fmtPx(m.price)} ${m.name}（${m.role}）${obs}`;
    });

    let close = null;
    for (let i = 0; i < ranked.length; i++) {
      close = this._hitClose(ranked[i]);
      if (close != null) break;
    }
    let relTxt = '';
    if (close != null && merged.length) {
      const nearest = merged
        .slice()
        .sort((a, b) => Math.abs(a.price - close) - Math.abs(b.price - close))[0];
      const pct = ((close - nearest.price) / Math.abs(nearest.price || 1)) * 100;
      const side =
        Math.abs(pct) <= 4
          ? '贴近'
          : pct > 0
            ? '上方约'
            : '下方约';
      const pctAbs = Math.abs(pct).toFixed(1);
      const nearestLabel = nearest.name || nearest.primaryName || '关键位';
      relTxt =
        Math.abs(pct) <= 4
          ? `现价 ${this._fmtPx(close)} 贴近「${nearestLabel}」${this._fmtPx(nearest.price)}。`
          : `现价 ${this._fmtPx(close)} 相对「${nearestLabel}」${this._fmtPx(nearest.price)} ${side}${pctAbs}%。`;
    }

    return `${parts.join('；')}${relTxt ? `。${relTxt}` : '。'}`;
  },

  /**
   * 前端规则引擎：根据 hits 结构化字段拼装专家口吻分析。
   * 必须直接读取 status：已确认巩固突破时禁止再写「等待边界有效突破」；
   * 已确认偏多巩固 vs 已确认偏空反转写入冲突提示。
   * @param {array} items
   * @param {{asof?:string, confluenceZones?:object, classicLevels?:object, kdeLevels?:object}|undefined} options
   */
  buildExpertAnalysis(items, options) {
    const opts = options || {};
    const asof = this._inferAsof(items, opts);
    const ranked = this._rankHits(items, { asof });
    const confirmed = ranked.filter((h) => h.status === 'confirmed');
    const forming = ranked.filter((h) => h.status === 'forming');
    const primary = this._pickPrimary(ranked, asof);
    const bgArchived = this._archivedBackgroundText(items);
    const closeForHint =
      (primary && this._hitClose(primary)) ||
      (ranked[0] && this._hitClose(ranked[0])) ||
      null;
    const confHint = this._nearConfluenceHint(opts.confluenceZones, closeForHint);

    if (!primary) {
      const hasConf = this._hasConfluenceZones(opts.confluenceZones);
      const shortBits = ['暂无主导形态。'];
      // P1：真空时短线轻改为结构整理期；有共振则结构块承载价位，避免与 confHint 堆砌
      if (hasConf) shortBits.push('结构整理期，跟踪多维量化共振带。');
      if (bgArchived) shortBits.push(bgArchived);
      if (!hasConf) {
        if (confHint) shortBits.push(confHint);
        else shortBits.push('短线建议结合量价与近端支撑压力谨慎观察。');
      }
      let mediumTerm = hasConf
        ? '暂无高置信活跃主导形态，结构整理期，跟踪多维量化共振带。'
        : '暂无高置信活跃主导形态，中线尚不明朗。';
      if (bgArchived) mediumTerm += bgArchived;
      if (!hasConf && confHint) mediumTerm += confHint;
      else if (!hasConf && forming.length) {
        const names = forming
          .slice(0, 3)
          .map(
            (h) =>
              `${this.typeLabel(h.pattern_type)}(${
                h.confidence != null ? Number(h.confidence).toFixed(2) : '--'
              })`
          )
          .join('、');
        mediumTerm += `形成中信号（${names}）偏旧或置信不足，不强制选作主形态。`;
      }
      const structure = this.buildStructureLevelsReference(items, {
        asof,
        confluenceZones: opts.confluenceZones,
        classicLevels: opts.classicLevels,
        kdeLevels: opts.kdeLevels,
        tactical: opts.tactical,
      });
      return {
        shortTerm: shortBits.join(''),
        mediumTerm,
        keyLevelsRef: this.buildKeyLevelsReference(items, { asof }),
        structureHtml: structure.html,
        structureText: structure.text,
        tradeLevelsHtml: structure.html,
        tradeLevelsText: structure.text,
        risk:
          '风险提示：以上解读由日线形态规则自动生成，非投资建议；形态识别存在滞后与误报，请结合基本面、量能与自身风险承受能力综合判断。',
        primaryLabel: '暂无主导形态',
        primaryConf: '--',
        closeTxt: closeForHint != null ? this._fmtPx(closeForHint) : null,
        neckTxt: null,
      };
    }

    const primaryLabel = this.typeLabel(primary.pattern_type);
    const primaryConf =
      primary.confidence != null ? Number(primary.confidence).toFixed(2) : '--';
    const close = this._hitClose(primary);
    const neck = this._hitNeck(primary);
    const closeTxt = close != null ? this._fmtPx(close) : null;
    const neckTxt = neck != null ? this._fmtPx(neck) : null;

    let shortTerm = '';
    let mediumTerm = '';

    const confirmedConsol = confirmed.filter((h) => this.CONSOLIDATION[h.pattern_type]);
    const hasConfirmedConsolBreak = confirmedConsol.length > 0;

    // —— 短期：形成中 + 最近确认与现价相对关键位 ——
    const shortBits = [];
    if (confirmed.length && primary.status === 'confirmed') {
      const top = primary;
      const t = top.pattern_type;
      const c = this._hitClose(top);
      const n = this._hitNeck(top);
      const rel = this._relToLevel(c, n);
      const lab = this.typeLabel(t);
      if (this.BEARISH_REVERSAL[t]) {
        if (rel && rel.side === 'below') {
          shortBits.push(
            `已确认${lab}且收盘落在颈线（${this._fmtPx(n)}）下方，短线偏空，警惕沿跌破后的惯性下行。`
          );
        } else if (rel && rel.side === 'near') {
          shortBits.push(
            `已确认${lab}，收盘（${this._fmtPx(c)}）贴近颈线（${this._fmtPx(n)}），短线宜观察颈线是否失守；失守则空头动能增强。`
          );
        } else if (rel && rel.side === 'above') {
          const rs = this._hitRightShoulder(top);
          shortBits.push(this._bearishAboveNeckCopy(lab, c, n, rs, rel));
        } else {
          shortBits.push(`已确认${lab}，短线关注颈线得失与量能配合。`);
        }
      } else if (this.BULLISH_REVERSAL[t]) {
        if (rel && rel.side === 'above') {
          shortBits.push(
            `已确认${lab}且收盘站上颈线（${this._fmtPx(n)}），短线偏多，可关注回踩颈线是否企稳。`
          );
        } else if (rel && rel.side === 'near') {
          shortBits.push(
            `已确认${lab}，收盘贴近颈线（${this._fmtPx(n)}），短线观察能否有效突破并站稳颈线。`
          );
        } else if (rel && rel.side === 'below') {
          const rs = this._hitRightShoulder(top);
          shortBits.push(this._bullishBelowNeckCopy(lab, c, n, rs, rel));
        } else {
          shortBits.push(`已确认${lab}，短线关注颈线突破与回踩。`);
        }
      } else if (this.CONSOLIDATION[t]) {
        shortBits.push(this._confirmedConsolBreakText(top));
      } else {
        shortBits.push(`主导形态为已确认${lab}（置信度 ${primaryConf}），短线围绕其关键价位波动。`);
      }

      // 另有已确认巩固但非主导时补一句方向
      if (confirmedConsol.length && !this.CONSOLIDATION[t]) {
        shortBits.push(this._confirmedConsolBreakText(confirmedConsol[0]));
      }
    }

    const formingConsol = forming.filter((h) => this.CONSOLIDATION[h.pattern_type]);
    // 已有已确认巩固突破时，禁止再写「方向尚未定，宜等待边界有效突破」
    if (formingConsol.length && !hasConfirmedConsolBreak) {
      const names = formingConsol
        .slice(0, 3)
        .map((h) => this.typeLabel(h.pattern_type))
        .join('、');
      const sample = formingConsol[0];
      const b = this._hitBounds(sample);
      const boundHint =
        b.upper != null || b.lower != null
          ? `（关注上沿${b.upper != null ? this._fmtPx(b.upper) : '--'}/下沿${b.lower != null ? this._fmtPx(b.lower) : '--'}）`
          : '';
      shortBits.push(
        `另有形成中的${names}${boundHint}，方向尚未定，宜等待边界有效突破后再定多空。`
      );
    } else if (formingConsol.length && hasConfirmedConsolBreak) {
      const names = formingConsol
        .slice(0, 2)
        .map((h) => this.typeLabel(h.pattern_type))
        .join('、');
      shortBits.push(`另有形成中的${names}，仅作次要观察，不改写已确认突破方向。`);
    } else if (!confirmed.length && forming.length && primary.status === 'forming') {
      const f0 = primary;
      shortBits.push(
        `当前以形成中的${this.typeLabel(f0.pattern_type)}为主，形态尚未确认，短线宜等待结构完成或关键位突破。`
      );
    }

    if (bgArchived) shortBits.push(bgArchived);
    if (primary.status === 'forming' && confHint) shortBits.push(confHint);

    if (!shortBits.length) {
      shortBits.push('命中形态信息有限，短线建议结合量价与关键支撑压力谨慎观察。');
    }
    shortTerm = shortBits.join('');

    // —— 中线：压短边界/现价堆砌（点位改由「结构防守与目标」承载）——
    if (confirmed.length && primary.status === 'confirmed') {
      const lead = primary;
      const leadBias = this._biasOf(lead.pattern_type);
      const leadLab = this.typeLabel(lead.pattern_type);
      const leadConf =
        lead.confidence != null ? Number(lead.confidence).toFixed(2) : '--';
      const formed = this.formedAtText(lead);
      const formedTxt = formed && formed !== '--' ? `形成/确认参考日 ${formed}。` : '';

      let stance = '中性震荡';
      if (leadBias === 'bear') stance = '中线偏空';
      else if (leadBias === 'bull') stance = '中线偏多';
      else if (leadBias === 'bearish_bias') stance = '中线略偏防守';
      else if (leadBias === 'bullish_bias') stance = '中线略偏积极';

      // 已确认反转但现价大幅回到破位前一侧 → 降权中线语气（不改 status）
      const leadClose = this._hitClose(lead);
      const leadNeck = this._hitNeck(lead);
      const leadRel = this._relToLevel(leadClose, leadNeck);
      const leadRs = this._hitRightShoulder(lead);
      if (leadRel && this.BEARISH_REVERSAL[lead.pattern_type] && leadRel.side === 'above') {
        const nearRs =
          leadRs != null && leadClose >= leadRs - Math.abs(leadRs) * 0.02;
        if (nearRs || Math.abs(leadRel.pct) >= 12) stance = '中线偏中性（反抽削弱空头）';
        else if (Math.abs(leadRel.pct) >= 8) stance = '中线偏观察（仍在颈线上方）';
      } else if (
        leadRel &&
        this.BULLISH_REVERSAL[lead.pattern_type] &&
        leadRel.side === 'below'
      ) {
        const nearRs =
          leadRs != null && leadClose <= leadRs + Math.abs(leadRs) * 0.02;
        if (nearRs || Math.abs(leadRel.pct) >= 12) stance = '中线偏中性（回撤削弱多头）';
        else if (Math.abs(leadRel.pct) >= 8) stance = '中线偏谨慎观察（仍在颈线下方）';
      }

      mediumTerm = `以高置信已确认「${leadLab}」（置信度 ${leadConf}）为主导，${stance}。${formedTxt}`;

      // 跨周期嵌套（后端 pattern_hierarchy / nesting_note）优先于置信冲突罗列
      const nestNoteRaw =
        opts.tactical && opts.tactical.nesting_note != null
          ? String(opts.tactical.nesting_note).trim()
          : '';
      const nestNote = nestNoteRaw
        ? nestNoteRaw.endsWith('。')
          ? nestNoteRaw
          : `${nestNoteRaw}。`
        : '';

      // 冲突：反向已确认（含偏多巩固 vs 偏空反转）
      const opp = confirmed.find((h) => {
        if (h === lead) return false;
        return this._biasConflicts(leadBias, this._biasOf(h.pattern_type));
      });
      if (nestNote) {
        mediumTerm += nestNote;
      } else if (opp) {
        const oppConf = this._num(opp.confidence);
        const leadC = this._num(lead.confidence);
        const nearTie =
          leadC != null &&
          oppConf != null &&
          Math.abs(leadC - oppConf) < this.RANK_CONF_TIE_EPS;
        // 同 status 且置信接近：文案层多空交织 / 箱体震荡，不改 primary
        if (nearTie) {
          const box = this._findRangeBox(items);
          if (
            box &&
            ((lead.pattern_type === 'double_top' && opp.pattern_type === 'double_bottom') ||
              (lead.pattern_type === 'double_bottom' && opp.pattern_type === 'double_top'))
          ) {
            mediumTerm += `双顶双底互斥，合并观察为箱体震荡 ${Number(box.low).toFixed(2)}–${Number(
              box.high
            ).toFixed(2)}，勿武断单边。`;
          } else {
            mediumTerm += `同时存在反向「${this.typeLabel(opp.pattern_type)}」（置信度接近），多空形态交织，宜按宽幅箱体/震荡观察，勿武断单边。`;
          }
        } else {
          const oppIsRev =
            this.BEARISH_REVERSAL[opp.pattern_type] || this.BULLISH_REVERSAL[opp.pattern_type];
          if (this.CONSOLIDATION[lead.pattern_type] && oppIsRev) {
            mediumTerm += `同时存在较早已确认「${this.typeLabel(opp.pattern_type)}」（测幅/时效可能已兑现），冲突时以后续突破的「${leadLab}」为主，旧反转降权观察。`;
          } else {
            mediumTerm += `同时存在反向已确认「${this.typeLabel(opp.pattern_type)}」，冲突时以更高置信的「${leadLab}」为主，另一信号降权观察。`;
          }
        }
      } else if (formingConsol.length && !hasConfirmedConsolBreak) {
        mediumTerm += `形成中巩固为次要，突破前不改「${leadLab}」框架。`;
      } else if (formingConsol.length && hasConfirmedConsolBreak) {
        mediumTerm += `形成中巩固仅次要观察。`;
      }
      if (bgArchived) mediumTerm += bgArchived;
    } else {
      const names = forming
        .filter((h) => this._isViablePrimaryCandidate(h, asof))
        .slice(0, 4)
        .map((h) => `${this.typeLabel(h.pattern_type)}(${h.confidence != null ? Number(h.confidence).toFixed(2) : '--'})`)
        .join('、');
      mediumTerm = `暂无高置信已确认形态，中线尚不明朗；形成中信号（${names || '若干'}）待边界突破或结构确认。`;
      const nestNoteRawElse =
        opts.tactical && opts.tactical.nesting_note != null
          ? String(opts.tactical.nesting_note).trim()
          : '';
      if (nestNoteRawElse) {
        mediumTerm += nestNoteRawElse.endsWith('。')
          ? nestNoteRawElse
          : `${nestNoteRawElse}。`;
      }
      // 同 forming 且 |Δconf|<eps、bias 冲突：交织/箱体提示（保持置信优先 primary，仅文案）
      const mixPeer = this._findNearConflictingPeer(primary, forming);
      if (mixPeer) {
        const box = this._findRangeBox(items);
        if (
          box &&
          ((primary.pattern_type === 'double_top' && mixPeer.pattern_type === 'double_bottom') ||
            (primary.pattern_type === 'double_bottom' && mixPeer.pattern_type === 'double_top'))
        ) {
          mediumTerm += `双顶双底互斥，合并观察为箱体震荡 ${Number(box.low).toFixed(2)}–${Number(
            box.high
          ).toFixed(2)}，勿武断单边。`;
        } else {
          mediumTerm += `多空形态交织，宜按宽幅箱体/震荡观察，勿武断单边。`;
        }
      }
      if (bgArchived) mediumTerm += bgArchived;
      if (confHint) mediumTerm += confHint;
    }

    const risk =
      '风险提示：以上解读由日线形态规则自动生成，非投资建议；形态识别存在滞后与误报，请结合基本面、量能与自身风险承受能力综合判断。';

    // keyLevelsRef 仍计算供调试/兼容；UI/PDF 统一走 structure*
    const keyLevelsRef = this.buildKeyLevelsReference(items, { asof });
    const structure = this.buildStructureLevelsReference(items, {
      asof,
      confluenceZones: opts.confluenceZones,
      classicLevels: opts.classicLevels,
      kdeLevels: opts.kdeLevels,
      tactical: opts.tactical,
    });

    return {
      shortTerm,
      mediumTerm,
      keyLevelsRef,
      structureHtml: structure.html,
      structureText: structure.text,
      tradeLevelsHtml: structure.html,
      tradeLevelsText: structure.text,
      risk,
      primaryLabel,
      primaryConf,
      closeTxt,
      neckTxt,
    };
  },

  esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  },

  async run() {
    if (!window.CommonUtils || !CommonUtils.checkLoginAndHandleExpiry()) return;
    const mode = (document.getElementById('patternModeSelect') || {}).value || 'single';
    const types = this.selectedTypes();
    if (!types.length) {
      CommonUtils.showToast('请至少选择一种形态类型', 'warning');
      return;
    }
    const asof = ((document.getElementById('patternAsof') || {}).value || '').trim();
    const adjust = this.selectedAdjust();
    const btn = document.getElementById('patternRunBtn');
    if (btn) {
      btn.disabled = true;
      btn.textContent = '识别中…';
    }
    try {
      if (mode === 'single') {
        let code = ((document.getElementById('patternStockCode') || {}).value || '').trim();
        if (!code) {
          CommonUtils.showToast('请输入股票代码或名称', 'warning');
          return;
        }
        // 「00700 腾讯」：首段为数字代码时取代码（与 levels 一致）
        const firstToken = code.split(/\s+/)[0];
        const firstBody = /^(sh|sz|bj|hk)/i.test(firstToken) ? firstToken.slice(2) : firstToken;
        if (/^\d{4,6}$/.test(firstBody)) {
          code = firstToken;
        }
        const fetched = await this.fetchSingle(code, { types, adjust, asof: asof || undefined });
        const priceAdjust = fetched.price_adjust;
        const invN = fetched.invalidated_count || 0;
        this.renderItems(
          fetched.items,
          `个股 ${this.esc(fetched.code)} ${this.esc(fetched.name || '')} · 基准日 ${this.esc(fetched.asof || '--')} · ${this.esc(this.adjustLabel(priceAdjust))} · ${this.esc(this.formatHitMeta(fetched.items.length, invN))}`,
          'single',
          priceAdjust,
          {
            invalidatedCount: invN,
            asof: fetched.asof || asof || '',
            tactical: fetched.tactical || null,
          }
        );
      } else {
        const scope = (document.getElementById('patternScanScope') || {}).value || 'market';
        const limit = parseInt((document.getElementById('patternScanLimit') || {}).value || '80', 10) || 80;
        if (scope !== 'market' && !this.selectedBoards.length) {
          CommonUtils.showToast('请先选择板块代码', 'warning');
          return;
        }
        const body = {
          scope,
          board_codes: scope === 'market' ? [] : this.selectedBoards,
          board_kind: scope === 'concept' ? 'concept' : 'industry',
          types,
          asof: asof || null,
          limit: Math.max(10, Math.min(200, limit)),
          adjust,
        };
        const resp = await authFetch(`${API_BASE_URL}/api/analysis/patterns/scan`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
          throw new Error(data.detail || data.message || '扫描失败');
        }
        const priceAdjust = data.price_adjust === 'qfq' ? 'qfq' : 'none';
        const flags = [];
        if (data.truncated) flags.push('已截断');
        if (data.timed_out) flags.push('已超时');
        const invN = Number(data.invalidated_count) || 0;
        const hitMeta = this.formatHitMeta(data.hit_count || 0, invN);
        this.renderItems(
          data.items || [],
          `扫描 ${this.esc(data.scope)} · 已扫 ${data.scanned || 0}/${data.pool_size || 0} · ${this.esc(hitMeta)} · 基准日 ${this.esc(data.asof || '--')} · ${this.esc(this.adjustLabel(priceAdjust))}${flags.length ? ' · ' + flags.join('/') : ''}`,
          'scan',
          priceAdjust,
          { invalidatedCount: invN }
        );
      }
    } catch (e) {
      console.error(e);
      if (window.CommonUtils) CommonUtils.showToast(e.message || String(e), 'error');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = '识别 / 扫描';
      }
    }
  },
};

window.PatternTool = PatternTool;

document.addEventListener('DOMContentLoaded', () => {
  try {
    PatternTool.init();
  } catch (e) {
    console.warn(e);
  }
});

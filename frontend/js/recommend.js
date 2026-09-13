/**
 * 策略推荐页：日/周/月简报
 */
(function () {
  const API_BASE = (typeof Config !== "undefined" && Config.getApiBaseUrl)
    ? Config.getApiBaseUrl()
    : "";

  const state = {
    _inited: false,
    horizon: "daily",
    asof: null,
    brief: null,
    items: [],
  };

  function fetchFn(url, options) {
    if (typeof authFetch === "function") return authFetch(url, options);
    if (typeof smartFetch === "function") return smartFetch(url, options);
    return fetch(url, options);
  }

  function scoreDetailLines(it) {
    const d = it && it.score_detail;
    if (!d || typeof d !== "object") return [];
    const lines = [];
    const n = Array.isArray(d.strategies) ? d.strategies.length : null;
    lines.push({
      k: "共振",
      v: d.resonance != null ? d.resonance : "-",
      tip: d.resonance_note || (n != null ? `策略数 ${n} × 10` : "命中策略数 × 10"),
    });
    lines.push({
      k: "质量",
      v: d.quality != null ? d.quality : "-",
      tip: d.quality_note || "主策略得分 min(分,100)×0.3",
    });
    lines.push({
      k: "立场",
      v: d.action_bonus != null ? d.action_bonus : "-",
      tip: d.action_note || "买入+15 / 观察+5 / 回避+0",
    });
    lines.push({
      k: "角色",
      v: d.role_bonus != null ? d.role_bonus : "-",
      tip: d.role_note || "龙头/中军小加分；板弱不加分",
    });
    if (d.note) lines.push({ k: "备注", v: "", tip: d.note });
    return lines;
  }

  function scoreDetailText(it) {
    return scoreDetailLines(it)
      .map((x) => (x.v !== "" && x.v != null ? `${x.k}${x.v}（${x.tip}）` : `${x.k}：${x.tip}`))
      .join("；");
  }

  function renderScoreCell(it) {
    const score = it.recommend_score != null ? it.recommend_score : "-";
    const lines = scoreDetailLines(it);
    if (!lines.length) {
      return `<span class="score-total">${score}</span>`;
    }
    const tip = scoreDetailText(it).replace(/"/g, "&quot;");
    const body = lines
      .map((x) => {
        const val = x.v === "" || x.v == null ? "" : `<b>${x.v}</b>`;
        return `<div class="score-line" title="${(x.tip || "").replace(/"/g, "&quot;")}">
          <span class="score-k">${x.k}</span>${val}
          <span class="score-tip">${x.tip || ""}</span>
        </div>`;
      })
      .join("");
    return `<span class="score-total" title="${tip}">${score}</span>
      <div class="score-detail">${body}</div>`;
  }

  function zoneText(z) {
    if (!z || typeof z !== "object") return "-";
    const bits = [];
    if (z.low != null) bits.push(z.low);
    if (z.price != null) bits.push(z.price);
    if (z.high != null) bits.push(z.high);
    return bits.length ? bits.join("~") : (z.label || "-");
  }

  function stanceTag(action, stance) {
    const a = action || "watch";
    const cls = a === "buy" ? "tag-buy" : a === "avoid" ? "tag-avoid" : "tag-watch";
    return `<span class="tag ${cls}">${stance || a}</span>`;
  }

  function roleTag(role, label) {
    const r = role || "normal";
    const cls = r === "leader" ? "tag-leader" : r === "mid" ? "tag-mid" : "";
    return `<span class="tag ${cls}">${label || r}</span>`;
  }

  async function loadAsofDates() {
    const res = await fetchFn(
      `${API_BASE}/api/recommend/asof-dates?horizon=${encodeURIComponent(state.horizon)}`
    );
    const json = await res.json().catch(() => ({}));
    const dates = (json && json.data) || [];
    const sel = document.getElementById("asofSelect");
    if (!sel) return;
    sel.innerHTML = "";
    if (!dates.length) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "暂无历史";
      sel.appendChild(opt);
      state.asof = null;
      return;
    }
    dates.forEach((d, i) => {
      const opt = document.createElement("option");
      opt.value = d;
      opt.textContent = d;
      if (i === 0) opt.selected = true;
      sel.appendChild(opt);
    });
    state.asof = dates[0];
  }

  async function loadBrief() {
    const tbody = document.getElementById("recommendTbody");
    if (tbody) tbody.innerHTML = `<tr><td colspan="12" class="empty">加载中…</td></tr>`;
    let url = `${API_BASE}/api/recommend/brief?horizon=${encodeURIComponent(state.horizon)}`;
    if (state.asof) url += `&asof_date=${encodeURIComponent(state.asof)}`;
    const res = await fetchFn(url);
    if (res.status === 404) {
      state.brief = null;
      state.items = [];
      render();
      if (tbody) tbody.innerHTML = `<tr><td colspan="12" class="empty">暂无该日期简报，请等待日终生成或联系管理员重跑</td></tr>`;
      return;
    }
    const json = await res.json().catch(() => ({}));
    if (!res.ok || !json.success) {
      if (tbody) tbody.innerHTML = `<tr><td colspan="12" class="empty">加载失败</td></tr>`;
      return;
    }
    state.brief = json.data;
    state.asof = state.brief.asof_date || state.asof;
    state.items = Array.isArray(state.brief.items) ? state.brief.items : [];
    render();
  }

  function filteredItems() {
    const action = (document.getElementById("filterAction") || {}).value || "";
    const role = (document.getElementById("filterRole") || {}).value || "";
    return state.items.filter((it) => {
      if (action && (it.action || "") !== action) return false;
      if (role && (it.role || "normal") !== role) return false;
      return true;
    });
  }

  function renderSummary() {
    const b = state.brief || {};
    const summary = b.summary || {};
    const counts = summary.counts || {};
    const market = (summary.market && summary.market.stance) || b.market_stance || "-";
    const el = (id, v) => {
      const n = document.getElementById(id);
      if (n) n.textContent = v == null ? "-" : String(v);
    };
    el("sumMarket", market);
    el("sumExec", counts.executable != null ? counts.executable : state.items.filter((x) => x.action === "buy").length);
    el("sumWatch", counts.watch != null ? counts.watch : state.items.filter((x) => x.action !== "buy").length);
    el("sumPlan", b.plan_for || "-");
    el("sumNote", summary.disclaimer || summary.publish_window || "-");
  }

  function renderTable() {
    const tbody = document.getElementById("recommendTbody");
    if (!tbody) return;
    const rows = filteredItems();
    if (!rows.length) {
      tbody.innerHTML = `<tr><td colspan="12" class="empty">无匹配条目</td></tr>`;
      return;
    }
    tbody.innerHTML = rows
      .map((it) => {
        const code = it.code || "";
        const name = it.name || "";
        const strategies = (it.strategies || []).join(",") || "-";
        const industry = it.industry || it.board_name || it.board_code || "-";
        return `<tr>
          <td class="code-cell"><span class="recommend-code">${code}</span></td>
          <td>${name || "-"}</td>
          <td>${stanceTag(it.action, it.stance)}</td>
          <td>${roleTag(it.role, it.role_label)}</td>
          <td>${it.primary_strategy || "-"}</td>
          <td>${strategies}</td>
          <td>${industry}</td>
          <td class="score-cell">${renderScoreCell(it)}</td>
          <td>${zoneText(it.buy_zone)}</td>
          <td>${zoneText(it.stop_zone)}</td>
          <td>${(it.summary || "").slice(0, 80)}</td>
          <td>
            <button type="button" class="link-btn" data-act="observe" data-code="${code}" data-name="${name}" data-perm="channel.analyze.tab.recommend.btn.observe">加入观察</button>
          </td>
        </tr>`;
      })
      .join("");
  }

  function renderRisk() {
    const section = document.getElementById("riskSection");
    const list = document.getElementById("riskList");
    const risks = (state.brief && state.brief.risk_observe) || [];
    if (!section || !list) return;
    if (!risks.length) {
      section.hidden = true;
      list.innerHTML = "";
      return;
    }
    section.hidden = false;
    list.innerHTML = risks
      .map((r) => `<li>${r.code || ""} ${r.name || ""} — ${r.note || r.kind || ""}</li>`)
      .join("");
  }

  function render() {
    renderSummary();
    renderTable();
    renderRisk();
    if (window.PermissionEngine && PermissionEngine.applyDomPermissions) {
      PermissionEngine.applyDomPermissions(document);
    }
  }

  async function addObserve(code, name) {
    const res = await fetchFn(`${API_BASE}/api/recommend/add-observe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        code,
        name,
        asof_date: state.asof,
        horizon: state.horizon,
      }),
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok || json.success === false) {
      alert((json && (json.detail || json.message)) || "加入观察失败");
      return;
    }
    alert("已加入交易观察");
  }

  function exportUrl(kind) {
    let url = `${API_BASE}/api/recommend/export/${kind}?horizon=${encodeURIComponent(state.horizon)}`;
    if (state.asof) url += `&asof_date=${encodeURIComponent(state.asof)}`;
    return url;
  }

  async function downloadExport(kind) {
    const res = await fetchFn(exportUrl(kind));
    if (!res.ok) {
      alert("导出失败");
      return;
    }
    const blob = await res.blob();
    const a = document.createElement("a");
    const cd = res.headers.get("Content-Disposition") || "";
    const m = /filename=\"?([^\";]+)\"?/.exec(cd);
    a.href = URL.createObjectURL(blob);
    a.download = m ? m[1] : `recommend_${state.horizon}.${kind === "pdf" ? "pdf" : "xlsx"}`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function switchHorizon(hz) {
    state.horizon = hz;
    document.querySelectorAll(".horizon-tab").forEach((btn) => {
      btn.classList.toggle("active", btn.getAttribute("data-horizon") === hz);
    });
    await loadAsofDates();
    await loadBrief();
  }

  async function init() {
    if (state._inited) {
      await loadBrief();
      return;
    }
    state._inited = true;
    document.querySelectorAll(".horizon-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (btn.disabled) return;
        switchHorizon(btn.getAttribute("data-horizon"));
      });
    });
    const asofSel = document.getElementById("asofSelect");
    if (asofSel) {
      asofSel.addEventListener("change", async () => {
        state.asof = asofSel.value || null;
        await loadBrief();
      });
    }
    ["filterAction", "filterRole"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener("change", renderTable);
    });
    const tbody = document.getElementById("recommendTbody");
    if (tbody) {
      tbody.addEventListener("click", (ev) => {
        const btn = ev.target.closest("[data-act=observe]");
        if (!btn) return;
        addObserve(btn.getAttribute("data-code"), btn.getAttribute("data-name"));
      });
    }
    const btnRefresh = document.getElementById("btnRefresh");
    if (btnRefresh) btnRefresh.addEventListener("click", () => loadBrief());
    const btnX = document.getElementById("btnExportXlsx");
    if (btnX) btnX.addEventListener("click", () => downloadExport("xlsx"));
    const btnP = document.getElementById("btnExportPdf");
    if (btnP) btnP.addEventListener("click", () => downloadExport("pdf"));

    await switchHorizon("daily");
  }

  window.RecommendPage = {
    get _inited() { return state._inited; },
    init,
    reload: loadBrief,
    refresh: loadBrief,
  };
})();

/**
 * 策略推荐页：日/周/月简报
 */
(function () {
  const API_BASE = (typeof Config !== "undefined" && Config.getApiBaseUrl)
    ? Config.getApiBaseUrl()
    : "";
  const OBSERVE_PERM = "channel.analyze.tab.recommend.btn.observe";

  const state = {
    _inited: false,
    horizon: "daily",
    asof: null,
    brief: null,
    items: [],
    seq: 0,
    horizonSeq: 0,
    observed: new Set(),
  };

  function fetchFn(url, options) {
    const opts = Object.assign({ skipRedirect: true }, options || {});
    if (typeof authFetch === "function") return authFetch(url, opts);
    if (typeof smartFetch === "function") return smartFetch(url, opts);
    return fetch(url, opts);
  }

  function esc(v) {
    return String(v == null ? "" : v)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function toast(msg, type) {
    if (window.CommonUtils && typeof CommonUtils.showToast === "function") {
      CommonUtils.showToast(msg, type || "info");
    } else {
      alert(msg);
    }
  }

  async function readError(res, fallback) {
    const json = await res.json().catch(() => null);
    const detail = json && (json.detail || json.message);
    if (typeof detail === "string" && detail) return detail;
    if (Array.isArray(detail) && detail.length) return detail.map((d) => d.msg || String(d)).join("；");
    return `${fallback}（HTTP ${res.status}）`;
  }

  function setBusy(btn, busy, busyText) {
    if (!btn) return;
    if (busy) {
      if (!btn.dataset.idleText) btn.dataset.idleText = btn.textContent;
      btn.disabled = true;
      btn.setAttribute("aria-busy", "true");
      if (busyText) btn.textContent = busyText;
    } else {
      btn.disabled = false;
      btn.removeAttribute("aria-busy");
      if (btn.dataset.idleText) btn.textContent = btn.dataset.idleText;
    }
  }

  function showTableMessage(msg, isError) {
    const tbody = document.getElementById("recommendTbody");
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="13" class="empty${isError ? " empty--error" : ""}">${esc(msg)}</td></tr>`;
    }
    renderMeta(null);
  }

  function renderMeta(shown) {
    const el = document.getElementById("recommendMeta");
    if (!el) return;
    const total = state.items.length;
    if (shown == null || !total) {
      el.textContent = "";
      return;
    }
    el.textContent = shown === total ? `共 ${total} 条` : `筛选 ${shown} / ${total} 条`;
  }

  function authErrorMessage(status) {
    if (status === 401) return "未登录或登录已过期，请重新登录后再打开策略推荐";
    if (status === 403) return "无策略推荐权限，请联系管理员开通 channel.analyze.tab.recommend";
    return "加载失败（HTTP " + status + "）";
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
      tip: d.quality_note || "归一化质量 min(分,100)×0.3",
    });
    lines.push({
      k: "立场",
      v: d.action_bonus != null ? d.action_bonus : "-",
      tip: d.action_note || "买入+15 / 观察+5 / 回避+0",
    });
    lines.push({
      k: "角色",
      v: d.role_bonus != null ? d.role_bonus : "-",
      tip: d.role_note || "龙头/中军小加分；板弱/E地板不加分",
    });
    if (d.theme_bonus != null && Number(d.theme_bonus) !== 0) {
      lines.push({
        k: "主题",
        v: d.theme_bonus,
        tip: d.theme_note || "月/周主题对齐加成",
      });
    }
    if (d.s_base != null) {
      lines.push({
        k: "S_base",
        v: d.s_base,
        tip: "共振+质量+立场+角色(+主题)",
      });
    }
    if (d.s_sr != null) {
      lines.push({
        k: "S_sr",
        v: d.s_sr,
        tip: d.s_sr_note || "筹码峰价位贴合 0～100",
      });
    }
    if (d.e_slope != null) {
      lines.push({
        k: "E斜率",
        v: d.e_slope,
        tip: d.e_slope_note || "大盘/板斜率环境乘数",
      });
    }
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
      return `<span class="score-total">${esc(score)}</span>`;
    }
    const tip = esc(scoreDetailText(it));
    const body = lines
      .map((x) => {
        const val = x.v === "" || x.v == null ? "<b></b>" : `<b>${esc(x.v)}</b>`;
        return `<div class="score-line" title="${esc(x.tip)}">
          <span class="score-k">${esc(x.k)}</span>${val}
          <span class="score-tip">${esc(x.tip)}</span>
        </div>`;
      })
      .join("");
    return `<details class="score-more">
        <summary title="${tip}" aria-label="推荐分 ${esc(score)}，得分明细"><span class="score-total">${esc(score)}</span><span class="score-toggle" aria-hidden="true"></span></summary>
        <div class="score-detail">${body}</div>
      </details>`;
  }

  function zoneText(z) {
    if (!z || typeof z !== "object") return "-";
    const bits = [];
    if (z.low != null) bits.push(z.low);
    if (z.price != null) bits.push(z.price);
    if (z.high != null) bits.push(z.high);
    return esc(bits.length ? bits.join("~") : (z.label || "-"));
  }

  function stanceTag(action, stance) {
    const a = action || "watch";
    const cls = a === "buy" ? "tag-buy" : a === "avoid" ? "tag-avoid" : "tag-watch";
    return `<span class="tag ${cls}">${esc(stance || a)}</span>`;
  }

  function roleTag(role, label) {
    const r = role || "normal";
    const cls = r === "leader" ? "tag-leader" : r === "mid" ? "tag-mid" : "tag-normal";
    return `<span class="tag ${cls}">${esc(label || r)}</span>`;
  }

  async function loadAsofDates() {
    try {
      const res = await fetchFn(
        `${API_BASE}/api/recommend/asof-dates?horizon=${encodeURIComponent(state.horizon)}`
      );
      if (res.status === 401 || res.status === 403) {
        showTableMessage(authErrorMessage(res.status), true);
        return;
      }
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
    } catch (err) {
      console.error("[recommend] loadAsofDates", err);
      showTableMessage("加载日期列表失败，请检查后端是否已启动", true);
    }
  }

  async function loadBrief() {
    const seq = ++state.seq;
    const btnRefresh = document.getElementById("btnRefresh");
    setBusy(btnRefresh, true, "加载中…");
    showTableMessage("加载中…");
    let url = `${API_BASE}/api/recommend/brief?horizon=${encodeURIComponent(state.horizon)}`;
    if (state.asof) url += `&asof_date=${encodeURIComponent(state.asof)}`;
    try {
      const res = await fetchFn(url);
      if (seq !== state.seq) return;
      if (res.status === 401 || res.status === 403) {
        state.brief = null;
        state.items = [];
        renderSummary();
        renderRisk();
        showTableMessage(authErrorMessage(res.status), true);
        return;
      }
      if (res.status === 404) {
        state.brief = null;
        state.items = [];
        render();
        showTableMessage("暂无该日期简报，请等待日终生成或联系管理员重跑");
        return;
      }
      const json = await res.json().catch(() => ({}));
      if (seq !== state.seq) return;
      if (!res.ok || !json.success) {
        const detail = json && (json.detail || json.message);
        showTableMessage(typeof detail === "string" && detail ? detail : authErrorMessage(res.status), true);
        return;
      }
      state.brief = json.data;
      state.asof = state.brief.asof_date || state.asof;
      state.items = Array.isArray(state.brief.items) ? state.brief.items : [];
      render();
    } catch (err) {
      if (seq !== state.seq) return;
      console.error("[recommend] loadBrief", err);
      showTableMessage("加载简报失败，请检查网络或后端服务", true);
    } finally {
      if (seq === state.seq) setBusy(btnRefresh, false);
    }
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
    const regimeObj = summary.regime || {};
    const regime =
      (typeof regimeObj === "object" ? regimeObj.regime : regimeObj) ||
      b.regime ||
      "-";
    const el = (id, v) => {
      const n = document.getElementById(id);
      if (n) n.textContent = v == null ? "-" : String(v);
    };
    el("sumMarket", market);
    el("sumRegime", regime);
    el("sumExec", counts.executable != null ? counts.executable : state.items.filter((x) => x.action === "buy").length);
    el("sumWatch", counts.watch != null ? counts.watch : state.items.filter((x) => x.action !== "buy").length);
    el("sumPlan", b.plan_for || "-");
    const windowBits = [];
    if (summary.publish_window) windowBits.push(summary.publish_window);
    if (b.late_run || summary.late_run) windowBits.push("尾盘确认");
    if (summary.config && summary.config.defense_mode) windowBits.push("弱势压缩Top");
    el("sumWindow", windowBits.join(" · ") || "-");
    el("sumNote", summary.disclaimer || "-");
  }

  function renderTable() {
    const tbody = document.getElementById("recommendTbody");
    if (!tbody) return;
    const rows = filteredItems();
    renderMeta(rows.length);
    if (!rows.length) {
      const filtered = state.items.length > 0;
      const msg = filtered ? "当前立场 / 角色筛选下无条目，可放宽筛选条件" : "该简报没有推荐条目";
      tbody.innerHTML = `<tr><td colspan="13" class="empty">${msg}</td></tr>`;
      return;
    }
    const allowObserve = canObserve();
    tbody.innerHTML = rows
      .map((it) => {
        const code = it.code || "";
        const name = it.name || "";
        const strategies = (it.strategies || []).join(",") || "-";
        const industry = it.industry || it.board_name || it.board_code || "-";
        const regime = it.regime || ((it.evidence || {}).regime) || "-";
        const summary = String(it.summary || "");
        const summaryShort = summary.length > 80 ? `${summary.slice(0, 80)}…` : summary;
        let opBtn = `<span class="ops-none">—</span>`;
        if (state.observed.has(code)) {
          opBtn = `<button type="button" class="rsa-op is-added" disabled>已加入</button>`;
        } else if (allowObserve) {
          opBtn = `<button type="button" class="rsa-op rsa-op--primary" data-act="observe" data-code="${esc(code)}" data-name="${esc(name)}" aria-label="将 ${esc(name || code)} 加入交易观察">加入观察</button>`;
        }
        return `<tr>
          <td class="code-cell"><span class="recommend-code">${esc(code)}</span></td>
          <td class="name-cell">${esc(name || "-")}</td>
          <td>${stanceTag(it.action, it.stance)}</td>
          <td>${roleTag(it.role, it.role_label)}</td>
          <td>${esc(it.primary_strategy || "-")}</td>
          <td>${esc(strategies)}</td>
          <td>${esc(regime)}</td>
          <td>${esc(industry)}</td>
          <td class="score-cell">${renderScoreCell(it)}</td>
          <td class="num">${zoneText(it.buy_zone)}</td>
          <td class="num">${zoneText(it.stop_zone)}</td>
          <td class="summary-cell"${summary.length > 80 ? ` title="${esc(summary)}"` : ""}>${esc(summaryShort || "-")}</td>
          <td class="col-ops">${opBtn}</td>
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
      .map((r) => `<li><span class="risk-stock">${esc(r.name || "")}<span class="risk-code">${esc(r.code || "")}</span></span>${esc(r.note || r.kind || "")}</li>`)
      .join("");
  }

  function render() {
    renderSummary();
    renderTable();
    renderRisk();
  }

  function canObserve() {
    const pe = window.PermissionEngine;
    if (!pe || typeof pe.has !== "function") return true;
    if (!pe.permissions || pe.permissions.size === 0) return true;
    return pe.has(OBSERVE_PERM);
  }

  async function addObserve(btn) {
    const code = btn.getAttribute("data-code");
    const name = btn.getAttribute("data-name");
    setBusy(btn, true, "加入中…");
    try {
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
      if (!res.ok) {
        toast(await readError(res, "加入观察失败"), "error");
        setBusy(btn, false);
        return;
      }
      const json = await res.json().catch(() => ({}));
      if (json.success === false) {
        toast(json.detail || json.message || "加入观察失败", "error");
        setBusy(btn, false);
        return;
      }
      state.observed.add(code);
      btn.removeAttribute("data-act");
      btn.removeAttribute("aria-busy");
      btn.classList.remove("rsa-op--primary");
      btn.classList.add("is-added");
      btn.textContent = "已加入";
      toast(`已将 ${name || code} 加入交易观察`, "success");
    } catch (err) {
      console.error("[recommend] addObserve", err);
      toast("加入观察失败，请检查网络或后端服务", "error");
      setBusy(btn, false);
    }
  }

  function exportUrl(kind) {
    let url = `${API_BASE}/api/recommend/export/${kind}?horizon=${encodeURIComponent(state.horizon)}`;
    if (state.asof) url += `&asof_date=${encodeURIComponent(state.asof)}`;
    return url;
  }

  async function downloadExport(kind, btn) {
    if (!state.brief) {
      toast("当前没有可导出的简报", "warning");
      return;
    }
    setBusy(btn, true, "导出中…");
    try {
      const res = await fetchFn(exportUrl(kind));
      if (!res.ok) {
        toast(await readError(res, "导出失败"), "error");
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
    } catch (err) {
      console.error("[recommend] export", err);
      toast("导出失败，请检查网络或后端服务", "error");
    } finally {
      setBusy(btn, false);
    }
  }

  async function switchHorizon(hz) {
    const token = ++state.horizonSeq;
    state.horizon = hz;
    document.querySelectorAll(".horizon-tab").forEach((btn) => {
      const on = btn.getAttribute("data-horizon") === hz;
      btn.classList.toggle("active", on);
      btn.setAttribute("aria-selected", on ? "true" : "false");
    });
    await loadAsofDates();
    if (token !== state.horizonSeq) return;
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
        if (!btn || btn.disabled) return;
        addObserve(btn);
      });
    }
    const btnRefresh = document.getElementById("btnRefresh");
    if (btnRefresh) btnRefresh.addEventListener("click", () => loadBrief());
    const btnX = document.getElementById("btnExportXlsx");
    if (btnX) btnX.addEventListener("click", () => downloadExport("xlsx", btnX));
    const btnP = document.getElementById("btnExportPdf");
    if (btnP) btnP.addEventListener("click", () => downloadExport("pdf", btnP));

    await switchHorizon("daily");
  }

  window.RecommendPage = {
    get _inited() { return state._inited; },
    init,
    reload: loadBrief,
    refresh: loadBrief,
  };
})();

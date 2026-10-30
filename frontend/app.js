/* 나만의 재무 비서 - 바닐라 JS 프론트엔드 */
(() => {
  "use strict";

  const API = ((window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || "http://127.0.0.1:8000").replace(/\/+$/, "");
  const $ = (sel) => document.querySelector(sel);
  const won = (n) => `${Math.round(n).toLocaleString("ko-KR")}원`;
  const manwon = (n) => (n >= 10000 ? `${(n / 10000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}만원` : won(n));

  const state = {
    conversationId: null,
    sending: false,
    summary: null,
    dataRows: [],
  };

  // ---------------------------------------------------------------- API
  class ApiError extends Error {
    constructor(message, status) { super(message); this.status = status; }
  }

  async function api(path, { method = "GET", body, timeout = 20000 } = {}) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeout);
    try {
      const res = await fetch(API + path, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        signal: ctrl.signal,
      });
      if (res.status === 204) return null;
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new ApiError(errorMessage(data, res.status), res.status);
      return data;
    } catch (e) {
      if (e instanceof ApiError) throw e;
      if (e.name === "AbortError") throw new ApiError("서버 응답이 너무 늦어요. 잠시 후 다시 시도해 주세요.", 0);
      throw new ApiError("서버에 연결할 수 없어요. 서버 주소와 실행 상태를 확인해 주세요.", 0);
    } finally {
      clearTimeout(timer);
    }
  }

  function errorMessage(data, status) {
    const d = data && data.detail;
    if (Array.isArray(d)) {
      // Pydantic 422 검증 오류
      return d.map((x) => `${(x.loc || []).slice(1).join(".") || "입력"}: ${x.msg}`).join(" / ");
    }
    if (typeof d === "string") return d;
    return `요청 실패 (HTTP ${status})`;
  }

  function toast(msg) {
    const el = $("#toast");
    el.textContent = msg;
    el.classList.remove("hidden");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.classList.add("hidden"), 2600);
  }

  // ---------------------------------------------------------------- 서버 깨우기 (Render 무료 티어 콜드스타트)
  async function warmUp() {
    const status = $("#serverStatus");
    const banner = $("#coldStartBanner");
    const slow = setTimeout(() => {
      banner.classList.remove("hidden");
      status.textContent = "서버 깨우는 중…";
    }, 3000);
    try {
      await api("/health", { timeout: 90000 });
      status.textContent = "서버 연결됨";
      status.className = "status status-ok";
      return true;
    } catch (e) {
      status.textContent = "서버 연결 실패";
      status.className = "status status-error";
      toast(e.message);
      return false;
    } finally {
      clearTimeout(slow);
      banner.classList.add("hidden");
    }
  }

  // ---------------------------------------------------------------- 테마
  function initTheme() {
    let saved = null;
    try { saved = localStorage.getItem("theme"); } catch (_) { /* 저장소 사용 불가 */ }
    const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    applyTheme(saved || (prefersDark ? "dark" : "light"));
    $("#themeToggle").addEventListener("click", () => {
      const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      applyTheme(next);
      try { localStorage.setItem("theme", next); } catch (_) { /* noop */ }
    });
  }
  function applyTheme(t) {
    document.documentElement.dataset.theme = t;
    $("#themeToggle").textContent = t === "dark" ? "☀️" : "🌙";
  }

  // ---------------------------------------------------------------- 탭
  function initTabs() {
    document.querySelectorAll(".tab").forEach((btn) =>
      btn.addEventListener("click", () => showTab(btn.dataset.tab))
    );
  }
  function showTab(name) {
    document.querySelectorAll(".tab").forEach((b) => {
      const on = b.dataset.tab === name;
      b.classList.toggle("active", on);
      b.setAttribute("aria-selected", on);
    });
    $("#tab-chat").classList.toggle("hidden", name !== "chat");
    $("#tab-data").classList.toggle("hidden", name !== "data");
  }

  // ---------------------------------------------------------------- 채팅
  const messagesEl = () => $("#chatMessages");

  function clearMessages() {
    messagesEl().innerHTML = "";
  }

  function showWelcome() {
    messagesEl().innerHTML = `
      <div class="welcome">
        <p class="welcome-title">무엇이 궁금하세요?</p>
        <div class="chips">
          <button class="chip" type="button">이번 달 지출 어때?</button>
          <button class="chip" type="button">가장 많이 쓴 때는 언제야?</button>
          <button class="chip" type="button">식비를 줄이려면 어떻게 해야 할까?</button>
          <button class="chip" type="button">월별 지출 추세를 분석해줘</button>
        </div>
      </div>`;
  }

  function addMessage(role, text) {
    const welcome = messagesEl().querySelector(".welcome");
    if (welcome) welcome.remove();
    const el = document.createElement("div");
    el.className = `msg ${role}`;
    el.textContent = text; // textContent: 사용자 입력/AI 응답을 HTML로 해석하지 않음 (XSS 방지)
    messagesEl().appendChild(el);
    messagesEl().scrollTop = messagesEl().scrollHeight;
    return el;
  }

  function addTyping() {
    const el = document.createElement("div");
    el.className = "msg assistant";
    el.innerHTML = '<span class="typing"><span></span><span></span><span></span></span><span class="typing-label">지출 데이터를 분석하는 중…</span>';
    messagesEl().appendChild(el);
    messagesEl().scrollTop = messagesEl().scrollHeight;
    return el;
  }

  async function sendMessage(text) {
    text = text.trim();
    if (!text || state.sending) return;
    state.sending = true;
    $("#chatSend").disabled = true;
    $("#chatInput").value = "";
    autoGrow();

    addMessage("user", text);
    const typing = addTyping();
    try {
      const res = await api("/api/chat", {
        method: "POST",
        body: { message: text, conversation_id: state.conversationId },
        timeout: 90000, // 콜드스타트 + GPT 응답 시간 고려
      });
      typing.remove();
      addMessage("assistant", res.reply);
      const isNew = !state.conversationId;
      state.conversationId = res.conversation_id;
      if (res.summary) renderSummary(res.summary);
      await loadConversations();
      if (isNew) toast("대화가 자동 저장되었어요.");
    } catch (e) {
      typing.remove();
      addMessage("error", `⚠ ${e.message}`);
    } finally {
      state.sending = false;
      $("#chatSend").disabled = false;
      $("#chatInput").focus();
    }
  }

  function autoGrow() {
    const ta = $("#chatInput");
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 140) + "px";
  }

  function initChat() {
    $("#chatForm").addEventListener("submit", (e) => {
      e.preventDefault();
      sendMessage($("#chatInput").value);
    });
    $("#chatInput").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        sendMessage($("#chatInput").value);
      }
    });
    $("#chatInput").addEventListener("input", autoGrow);
    messagesEl().addEventListener("click", (e) => {
      const chip = e.target.closest(".chip");
      if (chip) sendMessage(chip.textContent);
    });
    $("#newChatBtn").addEventListener("click", () => {
      state.conversationId = null;
      showWelcome();
      markActiveConversation();
      showTab("chat");
      $("#chatInput").focus();
    });
  }

  // ---------------------------------------------------------------- 대화 기록
  function formatTime(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d)) return "";
    return d.toLocaleString("ko-KR", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
  }

  async function loadConversations() {
    try {
      const list = await api("/api/conversations");
      renderConversations(list);
    } catch (e) {
      toast(`대화 목록: ${e.message}`);
    }
  }

  function renderConversations(list) {
    const ul = $("#conversationList");
    ul.innerHTML = "";
    $("#conversationEmpty").classList.toggle("hidden", list.length > 0);
    for (const c of list) {
      const li = document.createElement("li");
      li.className = "conv-item";
      li.dataset.id = c.id;
      li.tabIndex = 0;

      const text = document.createElement("div");
      text.className = "conv-text";
      const title = document.createElement("div");
      title.className = "conv-title";
      title.textContent = c.title || "제목 없음";
      const meta = document.createElement("div");
      meta.className = "conv-meta";
      meta.textContent = `${formatTime(c.updated_at)} · 메시지 ${c.message_count}개`;
      text.append(title, meta);

      const del = document.createElement("button");
      del.className = "link-btn danger";
      del.type = "button";
      del.textContent = "삭제";
      del.setAttribute("aria-label", `${c.title} 대화 삭제`);
      del.addEventListener("click", (e) => {
        e.stopPropagation();
        deleteConversation(c.id);
      });

      li.append(text, del);
      li.addEventListener("click", () => openConversation(c.id));
      li.addEventListener("keydown", (e) => { if (e.key === "Enter") openConversation(c.id); });
      ul.appendChild(li);
    }
    markActiveConversation();
  }

  function markActiveConversation() {
    document.querySelectorAll(".conv-item").forEach((li) =>
      li.classList.toggle("active", li.dataset.id === state.conversationId)
    );
  }

  async function openConversation(id) {
    showTab("chat");
    clearMessages();
    const loading = addTyping();
    loading.querySelector(".typing-label").textContent = "대화를 불러오는 중…";
    try {
      const conv = await api(`/api/conversations/${encodeURIComponent(id)}`);
      loading.remove();
      state.conversationId = conv.id;
      conv.messages.forEach((m) => addMessage(m.role, m.content));
      markActiveConversation();
    } catch (e) {
      loading.remove();
      addMessage("error", `⚠ ${e.message}`);
    }
  }

  async function deleteConversation(id) {
    if (!confirm("이 대화를 삭제할까요?")) return;
    try {
      await api(`/api/conversations/${encodeURIComponent(id)}`, { method: "DELETE" });
      if (state.conversationId === id) {
        state.conversationId = null;
        showWelcome();
      }
      toast("대화를 삭제했어요.");
      loadConversations();
    } catch (e) {
      toast(e.message);
    }
  }

  // ---------------------------------------------------------------- 데이터 관리
  function splitMemo(memo) {
    if (memo && memo.includes("|")) {
      const [cat, ...rest] = memo.split("|");
      return { category: cat.trim(), desc: rest.join("|").trim() };
    }
    return { category: "기타", desc: (memo || "").trim() };
  }

  function monthRange(ym) {
    const [y, m] = ym.split("-").map(Number);
    const last = new Date(y, m, 0).getDate();
    return { start: `${ym}-01`, end: `${ym}-${String(last).padStart(2, "0")}` };
  }

  async function loadData() {
    const ym = $("#dataMonth").value;
    const q = ym ? `?start=${monthRange(ym).start}&end=${monthRange(ym).end}&order=desc` : "?order=desc&limit=100";
    const tbody = $("#dataTableBody");
    tbody.innerHTML = '<tr><td colspan="5" class="muted">불러오는 중…</td></tr>';
    try {
      state.dataRows = await api(`/api/data${q}`);
      renderDataTable();
    } catch (e) {
      tbody.innerHTML = "";
      setFormMessage(e.message, "err");
    }
  }

  function renderDataTable() {
    const tbody = $("#dataTableBody");
    tbody.innerHTML = "";
    const rows = state.dataRows;
    const total = rows.reduce((s, r) => s + r.value, 0);
    $("#dataCount").textContent = `${rows.length}건 · 합계 ${won(total)}`;
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="muted">이 기간에 데이터가 없어요.</td></tr>';
      return;
    }
    const editingId = $("#dataId").value;
    for (const r of rows) {
      const { category, desc } = splitMemo(r.memo);
      const tr = document.createElement("tr");
      if (r.id === editingId) tr.classList.add("editing");

      const tdDate = document.createElement("td");
      tdDate.textContent = r.date;
      const tdVal = document.createElement("td");
      tdVal.className = "num";
      tdVal.textContent = won(r.value);
      const tdCat = document.createElement("td");
      const tag = document.createElement("span");
      tag.className = "cat-tag";
      tag.textContent = category;
      tdCat.appendChild(tag);
      const tdMemo = document.createElement("td");
      tdMemo.textContent = desc;

      const tdAct = document.createElement("td");
      tdAct.className = "actions";
      const edit = document.createElement("button");
      edit.className = "link-btn";
      edit.type = "button";
      edit.textContent = "수정";
      edit.addEventListener("click", () => startEdit(r));
      const del = document.createElement("button");
      del.className = "link-btn danger";
      del.type = "button";
      del.textContent = "삭제";
      del.addEventListener("click", () => deleteData(r));
      tdAct.append(edit, del);

      tr.append(tdDate, tdVal, tdCat, tdMemo, tdAct);
      tbody.appendChild(tr);
    }
  }

  function setFormMessage(msg, kind) {
    const el = $("#dataMessage");
    el.textContent = msg;
    el.className = `form-msg ${kind || ""}`;
  }

  function startEdit(r) {
    const { category, desc } = splitMemo(r.memo);
    $("#dataId").value = r.id;
    $("#dataDate").value = r.date;
    $("#dataValue").value = r.value;
    const sel = $("#dataCategory");
    sel.value = [...sel.options].some((o) => o.value === category) ? category : "기타";
    $("#dataMemo").value = desc;
    $("#dataSubmit").textContent = "수정 저장";
    $("#dataCancel").classList.remove("hidden");
    setFormMessage(`${r.date} ${won(r.value)} 항목을 수정 중이에요.`, "");
    renderDataTable();
    $("#dataValue").focus();
  }

  function resetForm() {
    $("#dataId").value = "";
    $("#dataValue").value = "";
    $("#dataMemo").value = "";
    $("#dataSubmit").textContent = "추가";
    $("#dataCancel").classList.add("hidden");
    renderDataTable();
  }

  async function submitData(e) {
    e.preventDefault();
    const id = $("#dataId").value;
    const value = Number($("#dataValue").value);
    const date = $("#dataDate").value;
    if (!date) return setFormMessage("날짜를 입력해 주세요.", "err");
    if (!Number.isInteger(value) || value <= 0 || value > 100000000) {
      return setFormMessage("금액은 1원 ~ 1억 원 사이의 정수여야 해요.", "err");
    }
    const desc = $("#dataMemo").value.trim();
    const body = { date, value, memo: `${$("#dataCategory").value} | ${desc || "-"}` };

    const btn = $("#dataSubmit");
    btn.disabled = true;
    try {
      if (id) {
        await api(`/api/data/${encodeURIComponent(id)}`, { method: "PUT", body });
        setFormMessage(`✓ 수정했어요: ${date} ${won(value)}`, "ok");
      } else {
        await api("/api/data", { method: "POST", body });
        setFormMessage(`✓ 추가했어요: ${date} ${won(value)}`, "ok");
      }
      $("#dataMonth").value = date.slice(0, 7);
      resetForm();
      await Promise.all([loadData(), loadSummary()]);
    } catch (err) {
      setFormMessage(err.message, "err");
    } finally {
      btn.disabled = false;
    }
  }

  async function deleteData(r) {
    if (!confirm(`${r.date} ${won(r.value)} 항목을 삭제할까요?`)) return;
    try {
      await api(`/api/data/${encodeURIComponent(r.id)}`, { method: "DELETE" });
      if ($("#dataId").value === r.id) resetForm();
      setFormMessage(`✓ 삭제했어요: ${r.date} ${won(r.value)}`, "ok");
      await Promise.all([loadData(), loadSummary()]);
    } catch (e) {
      setFormMessage(e.message, "err");
    }
  }

  async function exportCsv() {
    try {
      const rows = await api("/api/data?order=asc", { timeout: 60000 });
      const esc = (v) => `"${String(v).replace(/"/g, '""')}"`;
      const lines = ["date,value,memo", ...rows.map((r) => [r.date, r.value, esc(r.memo)].join(","))];
      // BOM: 엑셀에서 한글이 깨지지 않도록
      const blob = new Blob(["﻿" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `spending_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      toast(`${rows.length}건을 CSV로 내보냈어요.`);
    } catch (e) {
      toast(e.message);
    }
  }

  function initData() {
    $("#dataForm").addEventListener("submit", submitData);
    $("#dataCancel").addEventListener("click", () => { resetForm(); setFormMessage("", ""); });
    $("#dataMonth").addEventListener("change", loadData);
    $("#exportCsv").addEventListener("click", exportCsv);
    $("#dataDate").value = new Date().toISOString().slice(0, 10);
  }

  // ---------------------------------------------------------------- 요약
  async function loadSummary() {
    try {
      const s = await api("/api/data/summary");
      renderSummary(s);
      return s;
    } catch (e) {
      $("#summaryBody").innerHTML = "";
      const p = document.createElement("p");
      p.className = "muted small";
      p.textContent = `요약을 불러오지 못했어요: ${e.message}`;
      $("#summaryBody").appendChild(p);
      return null;
    }
  }

  function trendWord(trend) {
    return (trend || "").split(" ")[0] || "-";
  }

  function renderSummary(s) {
    state.summary = s;
    const body = $("#summaryBody");
    if (!s || !s.count) {
      body.innerHTML = '<p class="muted small">데이터가 없어요. 데이터 관리 탭에서 추가해 보세요.</p>';
      return;
    }
    const m = s.metrics;
    const cm = s.current_month || {};
    const pct = cm.vs_monthly_average_pct;
    const deltaCls = pct > 0 ? "delta-up" : "delta-down";
    const deltaTxt = pct == null ? "" : `월평균 대비 ${pct > 0 ? "▲" : "▼"} ${Math.abs(pct)}% (월말 예상 ${manwon(cm.projected_total)})`;
    const trendDetail = (s.trend || "").replace(/^\S+\s*/, "").replace(/^\(|\)$/g, "");

    body.innerHTML = `
      <div class="hero">
        <div class="hero-label">이번 달 (${cm.month}) · ${cm.elapsed_days}일 경과</div>
        <div class="hero-value">${won(cm.total)}</div>
        <div class="hero-delta ${deltaCls}">${deltaTxt}</div>
      </div>
      <div class="stats">
        <div><div class="stat-label">기간</div><div class="stat-value small">${s.period}</div></div>
        <div><div class="stat-label">데이터 개수</div><div class="stat-value">${s.count.toLocaleString()}건</div></div>
        <div><div class="stat-label">총 지출</div><div class="stat-value">${manwon(m.total)}</div></div>
        <div><div class="stat-label">월평균</div><div class="stat-value">${manwon(m.monthly_average)}</div></div>
        <div><div class="stat-label">일평균</div><div class="stat-value">${won(m.daily_average)}</div></div>
        <div><div class="stat-label">최대 지출</div><div class="stat-value">${manwon(m.max.value)}</div>
          <div class="stat-label" id="maxMemo"></div></div>
      </div>
      <div class="trend-box">
        <div class="trend-badge">최근 추세: ${trendWord(s.trend)}</div>
        <div class="small muted" id="trendDetail"></div>
      </div>
      <div class="section-title">월별 지출</div>
      <div class="chart" id="monthlyChart"></div>
      <div class="chart-note">점선: 월평균 · 옅은 막대: 진행 중인 달</div>
      <div class="section-title">카테고리 Top 5</div>
      <div id="catList"></div>`;

    // 서버에서 온 문자열(메모 등)은 textContent로 넣는다.
    $("#maxMemo").textContent = `${m.max.date} · ${splitMemo(m.max.memo).desc}`;
    $("#trendDetail").textContent = trendDetail;

    const cat = $("#catList");
    for (const c of s.top_categories) {
      const row = document.createElement("div");
      row.className = "cat-row";
      row.title = `${c.category}: ${won(c.total)}`;
      const name = document.createElement("span");
      name.textContent = c.category;
      const bar = document.createElement("div");
      bar.className = "cat-bar";
      const fill = document.createElement("span");
      fill.style.width = `${Math.max(c.share_pct, 1)}%`;
      bar.appendChild(fill);
      const p = document.createElement("span");
      p.className = "cat-pct";
      p.textContent = `${c.share_pct}%`;
      row.append(name, bar, p);
      cat.appendChild(row);
    }

    renderMonthlyChart($("#monthlyChart"), s.monthly_totals, m.monthly_average, cm);

    if (!$("#dataMonth").value && cm.month) {
      $("#dataMonth").value = cm.month;
      loadData();
    }
  }

  function niceStep(max) {
    const raw = max / 4;
    const pow = Math.pow(10, Math.floor(Math.log10(raw)));
    const n = raw / pow;
    return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * pow;
  }

  function renderMonthlyChart(container, monthly, avg, cm) {
    const entries = Object.entries(monthly || {});
    if (!entries.length) return;
    const W = 300, H = 170, padL = 34, padR = 4, padT = 10, padB = 20;
    const plotW = W - padL - padR, plotH = H - padT - padB;
    const maxVal = Math.max(...entries.map(([, v]) => v), avg);
    const step = niceStep(maxVal);
    const top = Math.ceil(maxVal / step) * step;
    const y = (v) => padT + plotH - (v / top) * plotH;
    const slot = plotW / entries.length;
    const bw = Math.min(18, slot - 6);
    const ns = "http://www.w3.org/2000/svg";

    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "월별 지출 막대 그래프: " + entries.map(([k, v]) => `${k} ${manwon(v)}`).join(", "));

    const el = (tag, attrs, text) => {
      const n = document.createElementNS(ns, tag);
      for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
      if (text != null) n.textContent = text;
      svg.appendChild(n);
      return n;
    };

    for (let v = 0; v <= top; v += step) {
      el("line", { x1: padL, x2: W - padR, y1: y(v), y2: y(v), class: "grid-line" });
      el("text", { x: padL - 4, y: y(v) + 3, "text-anchor": "end", class: "axis-label" }, v === 0 ? "0" : `${v / 10000}만`);
    }

    const tip = document.createElement("div");
    tip.className = "tooltip hidden";
    const bars = [];
    entries.forEach(([month, v], i) => {
      const cx = padL + slot * i + slot / 2;
      const x = cx - bw / 2, yt = y(v), yb = y(0), r = Math.min(4, (yb - yt) / 2);
      // 위쪽만 둥근 막대 (기준선에 붙은 쪽은 직각)
      const d = `M${x},${yb} V${yt + r} Q${x},${yt} ${x + r},${yt} H${x + bw - r} Q${x + bw},${yt} ${x + bw},${yt + r} V${yb} Z`;
      const partial = cm && month === cm.month;
      const bar = el("path", { d, class: partial ? "bar partial" : "bar" });
      bars.push(bar);
      el("text", { x: cx, y: H - 6, "text-anchor": "middle", class: "axis-label" }, `${Number(month.slice(5))}월`);
      // 막대보다 넓은 투명 히트 영역
      const hit = el("rect", { x: padL + slot * i, y: padT, width: slot, height: plotH, fill: "transparent" });
      const label = partial
        ? `${month} · ${won(v)} (진행 중, 예상 ${manwon(cm.projected_total)})`
        : `${month} · ${won(v)} (월평균 대비 ${v >= avg ? "+" : ""}${(((v - avg) / avg) * 100).toFixed(1)}%)`;
      hit.addEventListener("mouseenter", () => {
        bar.classList.add("hover");
        tip.textContent = label;
        tip.classList.remove("hidden");
        const rect = svg.getBoundingClientRect();
        const scale = rect.width / W;
        const half = tip.offsetWidth / 2; // 패널 밖으로 잘리지 않도록 툴팁 폭 기준으로 위치 보정
        tip.style.left = `${Math.min(Math.max(cx * scale, half), rect.width - half)}px`;
        tip.style.top = `${yt * scale}px`;
      });
      hit.addEventListener("mouseleave", () => {
        bar.classList.remove("hover");
        tip.classList.add("hidden");
      });
    });

    el("line", { x1: padL, x2: W - padR, y1: y(avg), y2: y(avg), class: "avg-line" });

    container.innerHTML = "";
    container.append(svg, tip);
  }

  // ---------------------------------------------------------------- 시작
  async function init() {
    initTheme();
    initTabs();
    initChat();
    initData();
    $("#refreshSummary").addEventListener("click", loadSummary);

    const ok = await warmUp();
    if (!ok) return;
    await Promise.all([loadSummary(), loadConversations()]);
  }

  document.addEventListener("DOMContentLoaded", init);
})();

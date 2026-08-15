/* Great Road Mapper · multi-quarter personal production board */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  /** @type {any} */
  let state = { titles: [], product_lines: [], quarters: [], pipeline_buckets: [] };
  let view = "list"; // default: list
  /** @type {"assignments"|"roster"} */
  let peoplePane = "assignments";
  /** @type {"open"|"done"|"all"} */
  let peopleAssignFilter = "open";
  /** @type {"status"|"staff"|"title"|"code"|"work"|"role"|"window"|"gate"} */
  let peopleAssignSort = "status";
  let peopleAssignSortDir = 1;
  /** @type {Set<string>} empty = all */
  let quarterFilter = new Set();
  /** @type {string|null} */
  let openId = null;
  /** @type {any[]} */
  let vocab = [];
  const THEME_KEY = "grm-theme";
  const GANTT_COLLAPSE_KEY = "grm-gantt-collapsed";
  /** @type {Set<string>} title ids with craft rows hidden */
  let ganttCollapsed = new Set();

  function loadGanttCollapsed() {
    try {
      const raw = localStorage.getItem(GANTT_COLLAPSE_KEY);
      const arr = raw ? JSON.parse(raw) : [];
      ganttCollapsed = new Set(Array.isArray(arr) ? arr : []);
    } catch (_) {
      ganttCollapsed = new Set();
    }
  }

  function saveGanttCollapsed() {
    try {
      localStorage.setItem(
        GANTT_COLLAPSE_KEY,
        JSON.stringify([...ganttCollapsed])
      );
    } catch (_) {}
  }

  function toggleGanttCollapse(titleId) {
    if (!titleId) return;
    if (ganttCollapsed.has(titleId)) ganttCollapsed.delete(titleId);
    else ganttCollapsed.add(titleId);
    saveGanttCollapsed();
    if (view === "gantt") renderGantt();
  }

  function applyTheme(mode) {
    const light = mode === "light";
    document.body.classList.toggle("theme-light", light);
    const btn = $("btnTheme");
    if (btn) {
      btn.textContent = light ? "Dark" : "Light";
      btn.title = light ? "Switch to dark mode" : "Switch to light mode";
    }
    try {
      localStorage.setItem(THEME_KEY, light ? "light" : "dark");
    } catch (_) {}
  }

  function initTheme() {
    let mode = "dark";
    try {
      mode = localStorage.getItem(THEME_KEY) || "dark";
    } catch (_) {}
    applyTheme(mode);
  }

  /** Fallback if /api/state omits pipeline_buckets (must match schedule.PIPELINE_BUCKETS). */
  const BUCKET_ORDER_FALLBACK = [
    "Not started",
    "Design",
    "Static Art",
    "Production",
    "FX",
    "Deliver Math",
    "Deliver Assets",
    "Dev",
    "Deliver Audio",
    "QA Loc",
    "QA LQA",
    "QA RQA",
    "Marketing / Sheets",
    "Ready for Rollout",
    "Active Rollout",
    "Exclusivity",
    "→ Global Release",
    "→ Betsoft Release",
    "Released",
    "Unscheduled",
    "No schedule",
    "In progress",
  ];

  /** Ordered board columns: known rails first, then any live buckets not in the list. */
  function bucketOrder() {
    const base =
      state.pipeline_buckets && state.pipeline_buckets.length
        ? state.pipeline_buckets.slice()
        : BUCKET_ORDER_FALLBACK.slice();
    const seen = new Set(base);
    for (const t of state.titles || []) {
      const b = t.bucket || "No schedule";
      if (b && !seen.has(b)) {
        base.push(b);
        seen.add(b);
      }
    }
    return base;
  }

  function fillBucketFilter() {
    const sel = $("filterBucket");
    if (!sel) return;
    const prev = sel.value;
    const order = bucketOrder();
    // Only offer lanes that exist on titles right now (+ current selection).
    const live = new Set(
      (state.titles || []).map((t) => t.bucket || "No schedule")
    );
    if (prev) live.add(prev);
    const opts = order.filter((k) => live.has(k));
    sel.innerHTML =
      `<option value="">All lanes</option>` +
      opts
        .map((k) => `<option value="${esc(k)}">${esc(k)}</option>`)
        .join("");
    if (prev && [...sel.options].some((o) => o.value === prev)) {
      sel.value = prev;
    } else {
      sel.value = "";
    }
  }

  function toast(msg) {
    const el = $("toast");
    el.textContent = msg;
    el.hidden = false;
    clearTimeout(el._t);
    el._t = setTimeout(() => {
      el.hidden = true;
    }, 2600);
  }

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function lineName(id) {
    const L = (state.product_lines || []).find((x) => x.id === id);
    return L ? L.name : id || "—";
  }

  function lineClass(t) {
    if ((t.kind || "") === "rebrand") return "line-rebrand";
    if ((t.product_line_id || "").includes("ng")) return "line-ng";
    return "line-bsg";
  }

  function filtered() {
    const line = $("filterLine").value;
    const bucket = $("filterBucket").value;
    const life =
      ($("filterLifecycle") && $("filterLifecycle").value) || "";
    return (state.titles || []).filter((t) => {
      if (line && t.product_line_id !== line) return false;
      if (bucket && t.bucket !== bucket) return false;
      if (life && (t.lifecycle || t.status) !== life) return false;
      if (quarterFilter.size) {
        const qk = t.quarter_key || "unassigned";
        if (!quarterFilter.has(qk)) return false;
      }
      return true;
    });
  }

  function lifecycleBadge(t) {
    const key = t.lifecycle || t.status || "planning";
    const lab =
      t.lifecycle_label ||
      ({
        planning: "Planning",
        active: "Active",
        production: "Active",
        scope_change: "Scope change",
        shelved: "Shelved",
        cancelled: "Cancelled",
        done: "Active",
        planned: "Planning",
      }[key] || key);
    const slug = String(key).replace(/[^a-z0-9]+/gi, "-").toLowerCase();
    return `<span class="grm-badge life-${esc(slug)}" title="Lifecycle">${esc(
      lab
    )}</span>`;
  }

  function typeBadge(t) {
    // Prefer live product type (template / variation); fall back to legacy complexity
    const tid = (t && (t.product_type_id || t.complexity)) || "medium";
    const pt = rawType(tid);
    const label = pt
      ? pt.label || pt.id
      : tid === "math_clone"
        ? "CLONE"
        : String(tid).toUpperCase();
    const slug = String((pt && pt.id) || tid)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-");
    const model = pt
      ? isVariation(pt)
        ? "variation"
        : "template"
      : "legacy";
    return `<span class="grm-badge cx-${esc(slug)} grm-badge-type" title="${esc(
      model + (pt && pt.template_id ? " of " + pt.template_id : "")
    )}">${esc(label)}</span>`;
  }

  /** @deprecated name kept for call sites — uses product type now */
  function cxBadge(cxOrTitle) {
    if (cxOrTitle && typeof cxOrTitle === "object") return typeBadge(cxOrTitle);
    return typeBadge({ product_type_id: cxOrTitle, complexity: cxOrTitle });
  }

  function bucketBadge(b) {
    const slug = String(b || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-");
    return `<span class="grm-badge bucket-${esc(slug)}">${esc(b || "—")}</span>`;
  }

  function twinLabel(t) {
    if ((t.kind || "") === "rebrand") {
      return `<span class="grm-twin" title="Betsoft rebrand of Nucleus title">REBRAND ⇄ ${esc(t.rebrand_of || t.nucleus_code || t.twin_code || "?")}</span>`;
    }
    if (t.twin_code || t.bsg_twin) {
      return `<span class="grm-twin" title="Has BSG rebrand twin">NUCLEUS ⇄ ${esc(t.twin_code || t.bsg_twin)}</span>`;
    }
    return "";
  }

  function personById(id) {
    return (state.people || []).find((p) => p.id === id) || null;
  }

  function titleAssignments(t) {
    return (t && t.assignments) || [];
  }

  function assignmentsForSlot(t, phaseId, wsId) {
    const wantWs = wsId || "";
    return titleAssignments(t).filter((a) => {
      if ((a.phase_id || "") !== phaseId) return false;
      return (a.workstream_id || "") === wantWs;
    });
  }

  function crewLabel(t) {
    const names = t.crew && t.crew.length
      ? t.crew
      : [
          ...new Set(
            titleAssignments(t)
              .map((a) => a.person_name)
              .filter(Boolean)
          ),
        ];
    if (!names.length) return "—";
    if (names.length <= 2) return names.join(", ");
    return `${names.slice(0, 2).join(", ")} +${names.length - 2}`;
  }

  function roleOptionsHtml(selected, extra) {
    const roles = [...(state.roles || [])];
    if (extra && !roles.includes(extra)) roles.unshift(extra);
    return (
      `<option value="">—</option>` +
      roles
        .map(
          (r) =>
            `<option value="${esc(r)}" ${r === selected ? "selected" : ""}>${esc(
              r
            )}</option>`
        )
        .join("")
    );
  }

  function crewChipsHtml(t, phaseId, wsId) {
    const rows = assignmentsForSlot(t, phaseId, wsId);
    if (!rows.length) return "";
    return (
      `<span class="grm-crew-chips">` +
      rows
        .map((a) => {
          const miss = a.person_missing ? " is-missing" : "";
          const lab = a.role
            ? `${a.person_name} · ${a.role}`
            : a.person_name || "—";
          return (
            `<span class="grm-crew-chip${miss}" title="${esc(lab)}">` +
            `<span>${esc(a.person_name || "—")}</span>` +
            (a.role
              ? `<span class="grm-crew-role">${esc(a.role)}</span>`
              : "") +
            `<button type="button" class="grm-crew-x ev-unassign" data-aid="${esc(
              a.id
            )}" aria-label="Unassign ${esc(a.person_name || "")}">×</button>` +
            `</span>`
          );
        })
        .join("") +
      `</span>`
    );
  }

  function findByCode(code) {
    if (!code) return null;
    const c = String(code).toUpperCase();
    return (state.titles || []).find(
      (t) => String(t.code || "").toUpperCase() === c
    );
  }

  function cardHtml(t) {
    const lc = lineClass(t);
    const q = t.quarter_label || t.quarter || "";
    return (
      `<button type="button" class="grm-card ${lc} bucket-edge-${esc(
        String(t.bucket || "")
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "-")
      )}" data-id="${esc(t.id)}">` +
      `<div class="grm-card-top">` +
      `<span class="grm-card-code">${esc(t.code || "—")}</span>` +
      `<span class="grm-card-q">${esc(q)}</span>` +
      `</div>` +
      `<div class="grm-card-name">${esc(t.name)}</div>` +
      `<div class="grm-card-meta">` +
      typeBadge(t) +
      lifecycleBadge(t) +
      bucketBadge(t.bucket) +
      `<br/>${esc(lineName(t.product_line_id))} · rel ${esc(t.release_date || "—")}` +
      `<br/><span class="grm-phase-line">${esc(t.current_phase || "—")}</span>` +
      (crewLabel(t) !== "—"
        ? `<br/><span class="grm-dim">crew: ${esc(crewLabel(t))}</span>`
        : "") +
      (twinLabel(t) ? `<br/>${twinLabel(t)}` : "") +
      (t.theme ? `<br/><span class="grm-dim">theme: ${esc(t.theme)}</span>` : "") +
      `</div></button>`
    );
  }

  function bindCards(root) {
    root.querySelectorAll(".grm-card").forEach((btn) => {
      btn.addEventListener("click", () => openTitle(btn.getAttribute("data-id")));
    });
  }

  function renderBoard() {
    const titles = filtered();
    const order = bucketOrder();
    const cols = new Map();
    for (const b of order) cols.set(b, []);
    for (const t of titles) {
      const key = t.bucket || "No schedule";
      if (!cols.has(key)) cols.set(key, []);
      cols.get(key).push(t);
    }
    // Show every non-empty lane (known order + any surprise bucket).
    const keys = [
      ...order.filter((k) => (cols.get(k) || []).length > 0),
      ...[...cols.keys()].filter(
        (k) => !order.includes(k) && (cols.get(k) || []).length > 0
      ),
    ];

    if (!titles.length) {
      $("viewBoard").innerHTML =
        '<div class="grm-empty"><strong>Clean surface.</strong> + Title = house spine (empty dates until ship). Edit phases with a reason. Make rebrand from an NG title.</div>';
      return;
    }

    $("viewBoard").innerHTML =
      `<div class="grm-board-legend">Columns = schedule lane (from phase dates today). Filter rails above = line · lane · lifecycle · quarter.</div>` +
      `<div class="grm-board">` +
      keys
        .map((k) => {
          const list = cols.get(k) || [];
          list.sort((a, b) =>
            String(a.release_date || "").localeCompare(String(b.release_date || ""))
          );
          const slug = k.toLowerCase().replace(/[^a-z0-9]+/g, "-");
          return (
            `<div class="grm-col col-${esc(slug)}"><div class="grm-col-h"><strong>${esc(k)}</strong> <span class="grm-col-n">${list.length}</span></div>` +
            `<div class="grm-col-body">${list.map(cardHtml).join("")}</div></div>`
          );
        })
        .join("") +
      `</div>`;
    bindCards($("viewBoard"));
  }

  function renderList() {
    const titles = filtered().slice().sort((a, b) => {
      const q = String(a.quarter_key || "").localeCompare(String(b.quarter_key || ""));
      if (q) return q;
      return String(a.release_date || "").localeCompare(String(b.release_date || ""));
    });
    if (!titles.length) {
      $("viewList").innerHTML = '<div class="grm-empty">No titles match filters.</div>';
      return;
    }
    $("viewList").innerHTML =
      `<div class="grm-table-wrap"><table class="grm-table"><thead><tr>` +
      `<th></th><th>Code</th><th>Name</th><th>Q</th><th>Line</th><th>Model</th><th>Life</th><th>Lane</th><th>Release</th><th>Phase</th><th>Crew</th><th>Twin</th>` +
      `</tr></thead><tbody>` +
      titles
        .map((t) => {
          const slug = String(t.bucket || "")
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "-");
          const twin =
            t.kind === "rebrand"
              ? t.rebrand_of || t.nucleus_code
              : t.twin_code || t.bsg_twin || "";
          return (
            `<tr class="row-${esc(lineClass(t))} row-bucket-${esc(slug)}" data-id="${esc(t.id)}">` +
            `<td class="grm-swatch" title="${esc(t.bucket)}"></td>` +
            `<td class="mono">${esc(t.code)}</td>` +
            `<td>${esc(t.name)}${(t.kind || "") === "rebrand" ? ' <span class="grm-badge cx-rebrand">REBRAND</span>' : ""}</td>` +
            `<td class="mono">${esc(t.quarter_label || "—")}</td>` +
            `<td>${esc(lineName(t.product_line_id))}</td>` +
            `<td>${typeBadge(t)}</td>` +
            `<td>${lifecycleBadge(t)}</td>` +
            `<td>${bucketBadge(t.bucket)}</td>` +
            `<td class="mono">${esc(t.release_date || "—")}</td>` +
            `<td>${esc(t.current_phase || "—")}</td>` +
            `<td class="grm-crew-cell">${esc(crewLabel(t))}</td>` +
            `<td class="mono twin-cell">${esc(twin || "—")}</td>` +
            `</tr>`
          );
        })
        .join("") +
      `</tbody></table></div>`;
    $("viewList").querySelectorAll("tr[data-id]").forEach((tr) => {
      tr.addEventListener("click", () => openTitle(tr.getAttribute("data-id")));
    });
  }

  function renderQuarters() {
    const titles = filtered();
    const byQ = new Map();
    for (const t of titles) {
      const k = t.quarter_key || "unassigned";
      if (!byQ.has(k)) byQ.set(k, []);
      byQ.get(k).push(t);
    }
    const keys = [...byQ.keys()].sort().reverse();
    if (!keys.length) {
      $("viewQuarters").innerHTML =
        '<div class="grm-empty">Nothing in view. Clear filters or add titles with a quarter / release date.</div>';
      return;
    }
    $("viewQuarters").innerHTML =
      `<div class="grm-qstrips">` +
      keys
        .map((k) => {
          const list = byQ.get(k);
          list.sort((a, b) =>
            String(a.release_date || "").localeCompare(String(b.release_date || ""))
          );
          const label = list[0]?.quarter_label || k;
          const counts = {};
          for (const t of list) {
            counts[t.bucket || "?"] = (counts[t.bucket || "?"] || 0) + 1;
          }
          const summary = Object.entries(counts)
            .map(([b, n]) => `${n} ${b}`)
            .join(" · ");
          return (
            `<section class="grm-qstrip">` +
            `<header class="grm-qstrip-h"><strong>${esc(label)}</strong> <span>${list.length} titles</span>` +
            `<div class="grm-qstrip-sum">${esc(summary)}</div></header>` +
            `<div class="grm-qstrip-body">${list.map(cardHtml).join("")}</div>` +
            `</section>`
          );
        })
        .join("") +
      `</div>`;
    bindCards($("viewQuarters"));
  }

  /** Parse YYYY-MM-DD → UTC ms (noon-safe via UTC date). */
  function parseISODate(s) {
    if (!s) return null;
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s).trim());
    if (!m) return null;
    return Date.UTC(+m[1], +m[2] - 1, +m[3]);
  }

  function addDaysUTC(ms, days) {
    return ms + days * 86400000;
  }

  /** Stable pastel from label (phase / workstream colors). */
  function ganttHue(name) {
    const str = String(name || "x");
    let h = 0;
    for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0;
    return h % 360;
  }

  function ganttBarColor(name, kind) {
    const hue = ganttHue(name);
    if (kind === "phase") return `hsl(${hue} 42% 58%)`;
    if (kind === "ws") return `hsl(${hue} 38% 48%)`;
    return `hsl(${hue} 40% 52%)`;
  }

  function collectGanttDates(titles) {
    const out = [];
    for (const t of titles) {
      if (t.release_date) out.push(t.release_date);
      for (const p of t.phases || []) {
        if (p.start) out.push(p.start);
        if (p.end) out.push(p.end);
        for (const w of p.workstreams || []) {
          if (w.start) out.push(w.start);
          if (w.end) out.push(w.end);
        }
      }
    }
    return out;
  }

  function ganttRange(titles) {
    const dates = collectGanttDates(titles)
      .map(parseISODate)
      .filter((x) => x != null);
    if (!dates.length) return null;
    let min = Math.min(...dates);
    let max = Math.max(...dates);
    // pad ~2 weeks each side
    min = addDaysUTC(min, -14);
    max = addDaysUTC(max, 14);
    // snap min to Monday-ish for cleaner week grid (UTC)
    const dow = new Date(min).getUTCDay(); // 0 Sun
    const back = dow === 0 ? 6 : dow - 1;
    min = addDaysUTC(min, -back);
    const days = Math.max(14, Math.round((max - min) / 86400000) + 1);
    return { origin: min, days, max };
  }

  function dayPxForSpan(days) {
    // Prefer ~3px/day; squeeze if multi-year so canvas stays usable
    if (days > 500) return 2;
    if (days > 320) return 2.5;
    return 3;
  }

  function barStyle(startS, endS, origin, dayPx, totalDays, color, extraClass, label) {
    const a = parseISODate(startS);
    let b = parseISODate(endS);
    if (a == null && b == null) return "";
    const start = a != null ? a : b;
    const end = b != null ? b : a;
    const i0 = Math.round((start - origin) / 86400000);
    const i1 = Math.round((end - origin) / 86400000);
    const left = i0 * dayPx;
    const width = Math.max(dayPx, (i1 - i0 + 1) * dayPx);
    const showLab = width > 48 && label;
    return (
      `<div class="grm-gantt-bar ${extraClass}" style="left:${left}px;width:${width}px;background:${color}"` +
      ` title="${esc(label || "")} · ${esc(startS || "—")} → ${esc(endS || startS || "—")}">` +
      (showLab ? esc(label) : "") +
      `</div>`
    );
  }

  function gateMark(dateS, origin, dayPx, name) {
    const ms = parseISODate(dateS);
    if (ms == null) return "";
    const i = Math.round((ms - origin) / 86400000);
    const left = i * dayPx;
    return (
      `<div class="grm-gantt-gate" style="left:${left}px" title="${esc(name || "gate")} · ${esc(
        dateS
      )}"></div>`
    );
  }

  function monthTicks(origin, days, dayPx) {
    const parts = [];
    let d = origin;
    const end = addDaysUTC(origin, days);
    while (d < end) {
      const dt = new Date(d);
      const y = dt.getUTCFullYear();
      const m = dt.getUTCMonth();
      const label = `${String(m + 1).padStart(2, "0")}/${String(y).slice(2)}`;
      const i = Math.round((d - origin) / 86400000);
      const left = i * dayPx;
      // width until next month
      const next = Date.UTC(y, m + 1, 1);
      const w = Math.max(dayPx, Math.round((Math.min(next, end) - d) / 86400000) * dayPx);
      parts.push(
        `<div class="grm-gantt-month" style="left:${left}px;width:${w}px">${esc(label)}</div>`
      );
      d = next;
    }
    return parts.join("");
  }

  function todayLine(origin, days, dayPx) {
    const now = new Date();
    const t = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
    const i = Math.round((t - origin) / 86400000);
    if (i < -1 || i > days + 1) return "";
    const left = i * dayPx;
    return `<div class="grm-gantt-today" style="left:${left}px"><span>TODAY</span></div>`;
  }

  function sortSpine(phases) {
    return (phases || []).slice().sort((a, b) => {
      const sa = a.sort != null ? a.sort : 0;
      const sb = b.sort != null ? b.sort : 0;
      if (sa !== sb) return sa - sb;
      return String(a.start || "").localeCompare(String(b.start || ""));
    });
  }

  function isGateEvent(p) {
    if ((p.role || "") === "gate") return true;
    if ((p.kind || "") === "point") return true;
    return false;
  }

  function renderGantt() {
    const root = $("viewGantt");
    if (!root) return;
    const titles = filtered()
      .slice()
      .sort((a, b) =>
        String(a.release_date || "9999").localeCompare(String(b.release_date || "9999"))
      );

    if (!titles.length) {
      root.innerHTML =
        '<div class="grm-empty">No titles match filters. Clear filters or + Title.</div>';
      return;
    }

    const range = ganttRange(titles);
    if (!range) {
      root.innerHTML =
        '<div class="grm-empty"><strong>No dated phases yet.</strong> Set ship dates / schedule bins so workstreams have start–end. Gantt is read-only paint of what you already entered.</div>';
      return;
    }

    const { origin, days } = range;
    const dayPx = dayPxForSpan(days);
    const labW = 228;
    const trackW = days * dayPx;
    const months = monthTicks(origin, days, dayPx);
    const today = todayLine(origin, days, dayPx);

    const rows = [];
    // Axis
    rows.push(
      `<div class="grm-gantt-row is-axis">` +
        `<div class="grm-gantt-lab">TITLE / CRAFT</div>` +
        `<div class="grm-gantt-track" style="width:${trackW}px">${months}${today}</div>` +
        `</div>`
    );

    for (const t of titles) {
      const phases = sortSpine(t.phases || []);
      const bodyPhases = phases.filter((p) => !isGateEvent(p));
      const gates = phases.filter((p) => isGateEvent(p));
      const q = t.quarter_label || t.quarter || "";
      const lc = lineClass(t);
      const collapsed = ganttCollapsed.has(t.id);
      const craftCount =
        bodyPhases.length +
        bodyPhases.reduce((n, p) => n + ((p.workstreams || []).length || 0), 0) +
        (gates.length ? 1 : 0);

      // Title header + release tick + (when collapsed) phase stack on title track
      let titleTrack = today;
      if (t.release_date) {
        titleTrack += barStyle(
          t.release_date,
          t.release_date,
          origin,
          dayPx,
          days,
          "var(--accent)",
          "is-release",
          "ship " + t.release_date
        );
      }
      if (collapsed) {
        // Stack thin phase bars so a closed game still shows process shape
        for (const p of bodyPhases) {
          if (!(p.start || p.end)) continue;
          const pname = p.name || "Phase";
          titleTrack += barStyle(
            p.start,
            p.end || p.start,
            origin,
            dayPx,
            days,
            ganttBarColor(pname, "phase"),
            "is-phase-bar is-collapsed-stack",
            pname
          );
        }
        for (const g of gates) {
          const d = g.start || g.end;
          titleTrack += gateMark(d, origin, dayPx, g.name || "gate");
        }
      } else {
        const allStarts = [];
        const allEnds = [];
        for (const p of bodyPhases) {
          if (p.start) allStarts.push(p.start);
          if (p.end) allEnds.push(p.end);
          for (const w of p.workstreams || []) {
            if (w.start) allStarts.push(w.start);
            if (w.end) allEnds.push(w.end);
          }
        }
        if (allStarts.length && allEnds.length) {
          const envStart = allStarts.slice().sort()[0];
          const envEnd = allEnds.slice().sort().slice(-1)[0];
          titleTrack += barStyle(
            envStart,
            envEnd,
            origin,
            dayPx,
            days,
            "color-mix(in srgb, var(--accent) 22%, transparent)",
            "is-phase-bar is-envelope",
            ""
          );
        }
      }

      const chev = collapsed ? "▸" : "▾";
      const collClass = collapsed ? " is-collapsed" : "";
      rows.push(
        `<div class="grm-gantt-row is-title ${esc(lc)}${collClass}" data-id="${esc(t.id)}">` +
          `<div class="grm-gantt-lab is-title-lab">` +
          `<button type="button" class="grm-gantt-toggle" data-collapse-id="${esc(
            t.id
          )}" title="${collapsed ? "Expand craft rows" : "Collapse craft rows"}" aria-expanded="${
            collapsed ? "false" : "true"
          }">${chev}</button>` +
          `<button type="button" class="grm-gantt-open" data-id="${esc(
            t.id
          )}" title="Open title">` +
          `<span class="grm-gantt-lab-name">${esc(t.name || t.code || "—")}</span>` +
          `<span class="grm-gantt-lab-code">${esc(t.code || "")}` +
          (q ? ` · ${esc(q)}` : "") +
          (t.release_date ? ` · ship ${esc(t.release_date)}` : "") +
          (collapsed && craftCount
            ? ` · ${craftCount} rows hidden`
            : "") +
          `</span></button></div>` +
          `<div class="grm-gantt-track grm-gantt-track-title" data-collapse-id="${esc(
            t.id
          )}" style="width:${trackW}px" title="${
            collapsed ? "Click to expand" : "Click to collapse craft"
          }">${titleTrack}</div>` +
          `</div>`
      );

      if (collapsed) continue;

      for (const p of bodyPhases) {
        const pname = p.name || "Phase";
        const pcol = ganttBarColor(pname, "phase");
        const pbar =
          p.start || p.end
            ? barStyle(p.start, p.end || p.start, origin, dayPx, days, pcol, "is-phase-bar", pname)
            : "";
        rows.push(
          `<div class="grm-gantt-row is-phase" data-id="${esc(t.id)}">` +
            `<div class="grm-gantt-lab" data-id="${esc(t.id)}">` +
            `<span>${esc(pname)}</span>` +
            `<span class="grm-gantt-lab-sub">${esc(p.start || "—")} → ${esc(p.end || "—")}</span>` +
            `</div>` +
            `<div class="grm-gantt-track" style="width:${trackW}px">${today}${pbar}</div>` +
            `</div>`
        );

        const streams = (p.workstreams || []).slice().sort((a, b) => {
          const sa = a.sort != null ? a.sort : 0;
          const sb = b.sort != null ? b.sort : 0;
          if (sa !== sb) return sa - sb;
          return String(a.start || "").localeCompare(String(b.start || ""));
        });
        for (const w of streams) {
          const wname = w.name || "workstream";
          const wcol = ganttBarColor(wname + pname, "ws");
          const wbar =
            w.start || w.end
              ? barStyle(
                  w.start,
                  w.end || w.start,
                  origin,
                  dayPx,
                  days,
                  wcol,
                  "is-ws-bar",
                  wname
                )
              : "";
          rows.push(
            `<div class="grm-gantt-row is-ws" data-id="${esc(t.id)}">` +
              `<div class="grm-gantt-lab" data-id="${esc(t.id)}">` +
              `<span>${esc(wname)}</span>` +
              `<span class="grm-gantt-lab-sub">${esc(w.start || "—")} → ${esc(w.end || "—")}</span>` +
              `</div>` +
              `<div class="grm-gantt-track" style="width:${trackW}px">${today}${wbar}</div>` +
              `</div>`
          );
        }
      }

      if (gates.length) {
        const marks =
          today +
          gates
            .map((g) => {
              const d = g.start || g.end;
              return gateMark(d, origin, dayPx, g.name || "gate");
            })
            .join("");
        rows.push(
          `<div class="grm-gantt-row is-gates" data-id="${esc(t.id)}">` +
            `<div class="grm-gantt-lab" data-id="${esc(t.id)}">` +
            `<span>GATES · ${gates.length}</span>` +
            `<span class="grm-gantt-lab-sub">hover diamond for date</span>` +
            `</div>` +
            `<div class="grm-gantt-track" style="width:${trackW}px">${marks}</div>` +
            `</div>`
        );
      }
    }

    root.innerHTML =
      `<div class="grm-gantt">` +
      `<div class="grm-gantt-legend">Read-only · thinner craft rows · ▾/▸ collapses a whole title (remembers) · stacked phases when closed · click name opens title · track click toggles collapse</div>` +
      `<div class="grm-gantt-scroll">` +
      `<div class="grm-gantt-canvas" style="--lab-w:${labW}px;--day-px:${dayPx}px;--gantt-days:${days}">` +
      rows.join("") +
      `</div></div></div>`;

    root.querySelectorAll(".grm-gantt-lab[data-id]").forEach((el) => {
      el.addEventListener("click", () => openTitle(el.getAttribute("data-id")));
    });
    root.querySelectorAll(".grm-gantt-open[data-id]").forEach((el) => {
      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        openTitle(el.getAttribute("data-id"));
      });
    });
    root.querySelectorAll("[data-collapse-id]").forEach((el) => {
      el.addEventListener("click", (ev) => {
        // Don't steal gate hover tooltips on expanded rows — only title toggle/track
        if (el.classList.contains("grm-gantt-gate")) return;
        ev.stopPropagation();
        toggleGanttCollapse(el.getAttribute("data-collapse-id"));
      });
    });
  }

  function render() {
    const n = (state.titles || []).length;
    const f = filtered().length;
    $("metaCount").textContent =
      f === n ? `${n} titles` : `${f} shown · ${n} total`;
    if (view === "board") renderBoard();
    else if (view === "list") renderList();
    else if (view === "gantt") renderGantt();
    else if (view === "quarters") renderQuarters();
    else if (view === "config") renderConfig();
    else if (view === "people") renderPeople();
    else renderVocab();
  }

  function setView(name) {
    view = name;
    $("tabBoard").classList.toggle("is-on", name === "board");
    $("tabList").classList.toggle("is-on", name === "list");
    if ($("tabGantt")) $("tabGantt").classList.toggle("is-on", name === "gantt");
    $("tabQuarters").classList.toggle("is-on", name === "quarters");
    $("tabVocab").classList.toggle("is-on", name === "vocab");
    if ($("tabPeople")) $("tabPeople").classList.toggle("is-on", name === "people");
    if ($("tabConfig")) $("tabConfig").classList.toggle("is-on", name === "config");
    $("viewBoard").classList.toggle("is-on", name === "board");
    $("viewList").classList.toggle("is-on", name === "list");
    if ($("viewGantt")) $("viewGantt").classList.toggle("is-on", name === "gantt");
    $("viewQuarters").classList.toggle("is-on", name === "quarters");
    $("viewVocab").classList.toggle("is-on", name === "vocab");
    if ($("viewPeople")) $("viewPeople").classList.toggle("is-on", name === "people");
    if ($("viewConfig")) $("viewConfig").classList.toggle("is-on", name === "config");
    render();
  }

  /** @type {string|null} */
  let configEditId = null;

  function daysToWeeks(d) {
    if (d === null || d === undefined || d === "") return "";
    const n = Number(d);
    if (Number.isNaN(n)) return "";
    const w = n / 7;
    return Number.isInteger(w) ? String(w) : w.toFixed(2).replace(/\.?0+$/, "");
  }

  function weeksToDays(w) {
    if (w === null || w === undefined || String(w).trim() === "") return null;
    const n = Number(w);
    if (Number.isNaN(n)) return null;
    return Math.round(n * 7);
  }

  function fillProductTypeSelects() {
    const pts = state.product_types || [];
    // Prefer variations for new titles; templates last (structure masters)
    const ordered = pts.slice().sort((a, b) => {
      const av = isVariation(a) ? 0 : 1;
      const bv = isVariation(b) ? 0 : 1;
      if (av !== bv) return av - bv;
      return String(a.label || a.id).localeCompare(String(b.label || b.id));
    });
    const html =
      ordered
        .map((p) => {
          // model field: template = bin sheet; variation = numbers-only child of a template
          const tag = isVariation(p)
            ? ` · variation of ${p.template_id || "?"}`
            : (p.kind || "") === "rebrand"
              ? " · template (rebrand)"
              : " · template";
          return `<option value="${esc(p.id)}">${esc(p.label || p.id)}${esc(
            tag
          )}</option>`;
        })
        .join("") || `<option value="medium">MEDIUM</option>`;
    const np = $("newProductType");
    if (np) {
      const cur = np.value;
      np.innerHTML = html;
      if (cur && pts.some((p) => p.id === cur)) np.value = cur;
      else {
        const pref =
          ordered.find(
            (p) =>
              isVariation(p) &&
              (p.id === "medium" || /medium/i.test(p.label || ""))
          ) ||
          ordered.find((p) => isVariation(p)) ||
          ordered[0];
        if (pref) np.value = pref.id;
      }
    }
  }

  function quarterFromShip(iso) {
    if (!iso || String(iso).length < 7) return "";
    const d = new Date(String(iso).slice(0, 10) + "T12:00:00");
    if (Number.isNaN(d.getTime())) return "";
    const q = Math.floor(d.getMonth() / 3) + 1;
    return `Q${q} ${d.getFullYear()}`;
  }

  function updateNewQuarterHint() {
    const el = $("newQuarterHint");
    const ship = $("newShip");
    if (!el) return;
    const q = ship && ship.value ? quarterFromShip(ship.value) : "";
    el.textContent = q
      ? `Board quarter: ${q} (from ship date)`
      : "Quarter follows ship date (or unassigned if empty).";
  }

  function isVariation(p) {
    return (
      !!p &&
      ((p.model || "").toLowerCase() === "variation" || !!p.template_id)
    );
  }

  function isTemplate(p) {
    return !!p && !isVariation(p);
  }

  function rawType(id) {
    return (state.product_types || []).find((p) => p.id === id) || null;
  }

  /** Live structure for editor: variations pull bins from parent template. */
  function displayType(p) {
    if (!p) return null;
    if (!isVariation(p)) return p;
    const base = rawType(p.template_id);
    if (!base) return p;
    const varStruts = (p.struts || []).filter(
      (s) => (s.role || "phase") !== "gate" && (s.kind || "") !== "point"
    );
    const byName = {};
    varStruts.forEach((s) => {
      if (s.name) byName[s.name] = s;
    });
    const struts = (base.struts || [])
      .filter(
        (s) => (s.role || "phase") !== "gate" && (s.kind || "") !== "point"
      )
      .map((s, i) => {
        const vs = byName[s.name] || varStruts[i] || {};
        const workstreams = (s.workstreams || []).map((bw, j) => {
          const vlist = vs.workstreams || [];
          const vw =
            vlist.find((w) => w.name === bw.name) || vlist[j] || {};
          const fill = bw.fill_parent !== false;
          return {
            name: bw.name,
            kind: "workstream",
            fill_parent: fill,
            offset_weeks_from_start: fill
              ? 0
              : vw.offset_weeks_from_start != null
                ? vw.offset_weeks_from_start
                : bw.offset_weeks_from_start || 0,
            duration_weeks: fill
              ? null
              : vw.duration_weeks != null && vw.duration_weeks !== ""
                ? vw.duration_weeks
                : bw.duration_weeks,
          };
        });
        let duration_weeks = s.duration_weeks;
        let duration_days = s.duration_days;
        if (vs.duration_weeks != null && vs.duration_weeks !== "") {
          duration_weeks = vs.duration_weeks;
          duration_days = Math.round(Number(vs.duration_weeks) * 7);
        } else if (vs.duration_days != null) {
          duration_days = vs.duration_days;
          duration_weeks = Number(vs.duration_days) / 7;
        }
        return {
          name: s.name,
          role: "phase",
          kind: "range",
          duration_weeks,
          duration_days,
          workstreams,
        };
      });
    return {
      ...p,
      model: "variation",
      kind: base.kind || p.kind,
      release_label: base.release_label || p.release_label,
      struts,
      gates: listCopy(base.gates || p.gates || []),
      _template_label: base.label || base.id,
    };
  }

  function listCopy(arr) {
    try {
      return JSON.parse(JSON.stringify(arr || []));
    } catch (_) {
      return [];
    }
  }

  function phaseNameOptions(phaseStruts, selected) {
    const names = (phaseStruts || [])
      .map((s) => (s.name || "").trim())
      .filter(Boolean);
    if (!names.length) {
      return `<option value="">(add phases first)</option>`;
    }
    return names
      .map(
        (n) =>
          `<option value="${esc(n)}" ${
            n === selected ? "selected" : ""
          }>${esc(n)}</option>`
      )
      .join("");
  }

  function workstreamOptions(phaseStruts, phaseName, selected) {
    const phase = (phaseStruts || []).find(
      (s) => (s.name || "").trim() === (phaseName || "").trim()
    );
    const streams = ((phase && phase.workstreams) || [])
      .map((w) => (w.name || "").trim())
      .filter(Boolean);
    if (!streams.length) {
      return `<option value="">(no workstreams on phase)</option>`;
    }
    return streams
      .map(
        (n) =>
          `<option value="${esc(n)}" ${
            n === selected ? "selected" : ""
          }>${esc(n)}</option>`
      )
      .join("");
  }

  function gateRelationOptions(selected, anchor) {
    const a = anchor || "phase";
    let opts;
    if (a === "release") {
      opts = [
        ["at_release", "on ship / release day"],
        ["before_release", "N before ship"],
        ["after_release", "N after ship"],
      ];
    } else if (a === "workstream") {
      opts = [
        ["at_start", "at start of workstream"],
        ["at_end", "at end of workstream"],
        ["before_start", "N before workstream starts"],
        ["after_end", "N after workstream ends"],
        ["offset_from_start", "N from workstream start"],
        ["offset_from_end", "N before workstream ends"],
      ];
    } else {
      opts = [
        ["at_start", "at start of phase"],
        ["at_end", "at end of phase"],
        ["before_start", "N before phase starts"],
        ["after_end", "N after phase ends"],
        ["offset_from_start", "N from phase start"],
        ["offset_from_end", "N before phase ends"],
      ];
    }
    const sel = selected || opts[0][0];
    return opts
      .map(
        ([v, lab]) =>
          `<option value="${v}" ${v === sel ? "selected" : ""}>${lab}</option>`
      )
      .join("");
  }

  function gateOffsetDisplay(g) {
    const unit = (g.offset_unit || "").toLowerCase();
    if (g.offset_days != null && g.offset_days !== "" && unit === "days") {
      return { n: String(g.offset_days), unit: "days" };
    }
    if (g.offset_days != null && g.offset_days !== "" && !unit) {
      // prefer days if stored
      const d = Number(g.offset_days);
      if (!Number.isNaN(d) && d % 7 !== 0) return { n: String(d), unit: "days" };
    }
    if (unit === "days") {
      return {
        n: String(
          g.offset_days != null && g.offset_days !== ""
            ? g.offset_days
            : g.offset_weeks != null
              ? Math.round(Number(g.offset_weeks) * 7)
              : 0
        ),
        unit: "days",
      };
    }
    // weeks (default / legacy)
    let w = g.offset_weeks;
    if ((w == null || w === "") && g.offset_days != null) {
      w = Number(g.offset_days) / 7;
    }
    return { n: w != null && w !== "" ? String(w) : "0", unit: "weeks" };
  }

  function gateRowHtml(g, phaseStruts, locked) {
    const id = g.id || "";
    const name = g.name || "";
    const anchor = g.anchor || "phase";
    const rel = g.relation || "at_end";
    const od = gateOffsetDisplay(g);
    const phaseName = g.phase_name || "";
    const wsName = g.workstream_name || "";
    const offLabel = od.unit === "days" ? `${od.n}d` : `${od.n}w`;
    if (locked) {
      let where;
      if (
        anchor === "release" ||
        rel === "at_release" ||
        rel === "before_release" ||
        rel === "after_release"
      ) {
        where =
          rel === "at_release"
            ? "on release"
            : rel === "after_release"
              ? `${offLabel} after release`
              : `${offLabel} before release`;
      } else if (anchor === "workstream") {
        where = `${rel.replace(/_/g, " ")} · ↳ ${wsName || "?"} @ ${
          phaseName || "?"
        } · ${offLabel}`;
      } else {
        where = `${rel.replace(/_/g, " ")} · ${phaseName || "?"} · ${offLabel}`;
      }
      return (
        `<div class="grm-cfg-gate-row is-ro" data-gid="${esc(id)}">` +
        `<span class="grm-cfg-gate-name-ro">${esc(name || "—")}</span>` +
        `<span class="grm-muted mono">${esc(where)}</span>` +
        `</div>`
      );
    }
    return (
      `<div class="grm-cfg-gate-row" data-gid="${esc(id)}">` +
      `<input class="cfg-gate-name" value="${esc(name)}" placeholder="Gate name" />` +
      `<select class="cfg-gate-anchor">` +
      `<option value="phase" ${
        anchor === "phase" ? "selected" : ""
      }>phase</option>` +
      `<option value="workstream" ${
        anchor === "workstream" ? "selected" : ""
      }>workstream</option>` +
      `<option value="release" ${
        anchor === "release" ? "selected" : ""
      }>release</option>` +
      `</select>` +
      `<select class="cfg-gate-phase" ${
        anchor === "release" ? "disabled" : ""
      }>${phaseNameOptions(phaseStruts, phaseName)}</select>` +
      `<select class="cfg-gate-ws" ${
        anchor === "workstream" ? "" : "disabled"
      } title="Workstream">${workstreamOptions(
        phaseStruts,
        phaseName,
        wsName
      )}</select>` +
      `<select class="cfg-gate-rel">${gateRelationOptions(
        rel,
        anchor
      )}</select>` +
      `<label class="grm-cfg-gate-off">N ` +
      `<input class="cfg-gate-off mono" type="number" step="1" min="0" value="${esc(
        od.n
      )}" style="width:3.2rem" title="Offset amount" />` +
      `<select class="cfg-gate-unit" title="Offset unit">` +
      `<option value="days" ${od.unit === "days" ? "selected" : ""}>days</option>` +
      `<option value="weeks" ${od.unit === "weeks" ? "selected" : ""}>weeks</option>` +
      `</select></label>` +
      `<button type="button" class="grm-btn grm-btn-sm cfg-gate-rm" title="Remove gate">✕</button>` +
      `</div>`
    );
  }

  function renderConfig() {
    const root = $("viewConfig");
    if (!root) return;
    const pts = state.product_types || [];
    if (!configEditId && pts[0]) configEditId = pts[0].id;
    const curRaw = pts.find((p) => p.id === configEditId) || pts[0] || null;
    const cur = displayType(curRaw);
    const variation = isVariation(curRaw);
    const templateMode = isTemplate(curRaw);

    const templates = pts.filter(isTemplate);
    const variations = pts.filter(isVariation);

    function pickBtn(p, tag) {
      return (
        `<button type="button" class="grm-cfg-pick ${
          curRaw && p.id === curRaw.id ? "is-on" : ""
        }" data-pid="${esc(p.id)}">${esc(p.label || p.id)}` +
        `<span class="grm-muted"> · ${tag}</span></button>`
      );
    }

    const listHtml =
      `<div class="grm-cfg-list-sec">Templates</div>` +
      (templates.map((p) => pickBtn(p, `${(p.struts || []).length} bins`)).join("") ||
        `<p class="grm-muted">none</p>`) +
      `<div class="grm-cfg-list-sec">Variations</div>` +
      (variations
        .map((p) => {
          const t = rawType(p.template_id);
          return pickBtn(p, `of ${t ? t.label || t.id : p.template_id || "?"}`);
        })
        .join("") || `<p class="grm-muted">none yet</p>`);

    let editor = `<p class="grm-muted">No product types yet.</p>`;
    if (cur && curRaw) {
      const phaseStruts = (cur.struts || []).filter(
        (s) => (s.role || "phase") !== "gate" && (s.kind || "") !== "point"
      );
      const rows = phaseStruts
        .map((s, i) => {
          let durN = "";
          let durUnit = "weeks";
          if (s.duration_days != null && s.duration_days !== "") {
            const dd = Number(s.duration_days);
            if (!Number.isNaN(dd) && dd > 0 && dd % 7 !== 0) {
              durN = String(dd);
              durUnit = "days";
            } else if (s.duration_weeks != null && s.duration_weeks !== "") {
              durN = String(s.duration_weeks);
              durUnit = "weeks";
            } else if (!Number.isNaN(dd)) {
              durN = String(dd / 7);
              durUnit = "weeks";
            }
          } else if (s.duration_weeks != null && s.duration_weeks !== "") {
            durN = String(s.duration_weeks);
            durUnit = "weeks";
          }
          const ws = s.workstreams || [];
          const wsRows = ws
            .map((w, wi) => {
              const fill = w.fill_parent !== false;
              const off =
                w.offset_weeks_from_start != null
                  ? String(w.offset_weeks_from_start)
                  : "0";
              const dur =
                w.duration_weeks != null && w.duration_weeks !== ""
                  ? String(w.duration_weeks)
                  : "1";
              if (variation) {
                // structure locked — numbers only for portion streams
                return (
                  `<div class="grm-cfg-ws-row" data-wi="${wi}" data-ws-name="${esc(
                    w.name || ""
                  )}" data-fill="${fill ? "1" : "0"}">` +
                  `<span class="grm-cfg-ws-mark">↳</span>` +
                  `<span class="cfg-ws-name-ro">${esc(w.name || "")}</span>` +
                  (fill
                    ? `<span class="grm-muted grm-cfg-ws-hint">full phase</span>`
                    : `<span class="grm-cfg-ws-portion">` +
                      `from w<input class="cfg-ws-off mono" type="number" step="0.25" min="0" value="${esc(
                        off
                      )}" title="Weeks from phase start" />` +
                      ` for <input class="cfg-ws-dur mono" type="number" step="0.25" min="0" value="${esc(
                        dur
                      )}" title="Duration weeks inside phase" />w` +
                      `</span>`) +
                  `</div>`
                );
              }
              return (
                `<div class="grm-cfg-ws-row" data-wi="${wi}">` +
                `<span class="grm-cfg-ws-mark">↳</span>` +
                `<input class="cfg-ws-name" value="${esc(
                  w.name || ""
                )}" placeholder="Workstream name" />` +
                `<label class="grm-cfg-ws-fill"><input type="checkbox" class="cfg-ws-fill" ${
                  fill ? "checked" : ""
                } /> full phase</label>` +
                `<span class="grm-cfg-ws-portion ${fill ? "is-dim" : ""}">` +
                `from w<input class="cfg-ws-off mono" type="number" step="0.25" min="0" value="${esc(
                  off
                )}" title="Weeks from phase start" />` +
                ` for <input class="cfg-ws-dur mono" type="number" step="0.25" min="0" value="${esc(
                  dur
                )}" title="Duration weeks inside phase" />w` +
                `</span>` +
                `<button type="button" class="grm-btn grm-btn-sm cfg-ws-rm" title="Remove workstream">✕</button>` +
                `</div>`
              );
            })
            .join("");
          const hasWs = ws.length > 0;
          if (variation) {
            return (
              `<tr class="cfg-phase-row" data-i="${i}" data-phase-name="${esc(
                s.name || ""
              )}">` +
              `<td colspan="3">` +
              `<div class="grm-cfg-phase-line">` +
              `<span class="cfg-name-ro">${esc(s.name || "")}</span>` +
              `<input class="cfg-dur mono" type="number" step="1" min="0" value="${esc(
                durN
              )}" title="Duration" style="width:4rem" />` +
              `<span class="grm-muted" style="font-size:0.5rem">${esc(
                durUnit
              )}</span>` +
              (hasWs
                ? `<span class="grm-muted grm-cfg-ws-count">${ws.length} stream${
                    ws.length === 1 ? "" : "s"
                  }</span>`
                : "") +
              `</div>` +
              (hasWs
                ? `<div class="grm-cfg-ws-block is-open" data-phase-i="${i}">${wsRows}</div>`
                : "") +
              `</td></tr>`
            );
          }
          // Template: one compact phase row; workstream panel only if streams exist
          // or after + Workstream. Empty phases stay a single line.
          return (
            `<tr class="cfg-phase-row" data-i="${i}">` +
            `<td colspan="3">` +
            `<div class="grm-cfg-phase-line">` +
            `<input class="cfg-name" value="${esc(s.name || "")}" />` +
            `<input class="cfg-dur mono" type="number" step="1" min="0" value="${esc(
              durN
            )}" title="Duration" style="width:4rem" />` +
            `<select class="cfg-dur-unit" title="Duration unit" style="width:auto;font-size:0.55rem">` +
            `<option value="weeks" ${
              durUnit === "weeks" ? "selected" : ""
            }>weeks</option>` +
            `<option value="days" ${
              durUnit === "days" ? "selected" : ""
            }>days</option>` +
            `</select>` +
            `<button type="button" class="grm-btn grm-btn-sm cfg-up" title="Move up">↑</button>` +
            `<button type="button" class="grm-btn grm-btn-sm cfg-dn" title="Move down">↓</button>` +
            `<button type="button" class="grm-btn grm-btn-sm cfg-ws-toggle" title="Workstreams">` +
            (hasWs ? `Streams (${ws.length})` : `+ Workstream`) +
            `</button>` +
            `<button type="button" class="grm-btn grm-btn-sm cfg-rm" title="Remove phase">✕</button>` +
            `</div>` +
            `<div class="grm-cfg-ws-block ${
              hasWs ? "is-open" : "is-collapsed"
            }" data-phase-i="${i}" ${hasWs ? "" : "hidden"}>` +
            wsRows +
            `<div class="grm-cfg-ws-tools">` +
            `<button type="button" class="grm-btn grm-btn-sm cfg-ws-add">+ Workstream</button>` +
            `<span class="grm-muted grm-cfg-ws-hint">full phase or portion (from week · for Nw)</span>` +
            `</div></div>` +
            `</td></tr>`
          );
        })
        .join("");

      const gates = cur.gates || curRaw.gates || [];
      const gateRows = gates
        .map((g) => gateRowHtml(g, phaseStruts, variation))
        .join("");

      const modeBanner = variation
        ? `<p class="grm-hint grm-cfg-mode"><strong>Variation</strong> of ` +
          `<button type="button" class="grm-btn grm-btn-sm" id="cfgGotoTemplate">${esc(
            cur._template_label || curRaw.template_id || "template"
          )}</button>` +
          ` — bins, streams &amp; gates are locked. Edit <em>week lengths</em> and <em>portion windows</em> only.</p>`
        : `<p class="grm-hint grm-cfg-mode"><strong>Template</strong> — bins, workstreams, <strong>gate rules</strong>. ` +
          `Ship/release is the title field, not an auto gate. Spawn variations for week numbers only.</p>`;

      editor =
        `<div class="grm-cfg-editor ${variation ? "is-variation" : "is-template"}">` +
        modeBanner +
        `<div class="grm-cfg-meta">` +
        `<label>Code <input id="cfgId" class="mono" value="${esc(
          curRaw.id
        )}" spellcheck="false" title="Stable short code (e.g. primary, mdl-001). Not the display name." /></label>` +
        `<input type="hidden" id="cfgPrevId" value="${esc(curRaw.id)}" />` +
        `<label>Label <input id="cfgLabel" value="${esc(
          curRaw.label || ""
        )}" title="Human name — MEDIUM, COMPLEX, etc." /></label>` +
        (templateMode
          ? `<label>Kind <select id="cfgKind">` +
            `<option value="title" ${
              (curRaw.kind || "title") === "title" ? "selected" : ""
            }>Full title</option>` +
            `<option value="rebrand" ${
              (curRaw.kind || "") === "rebrand" ? "selected" : ""
            }>Rebrand</option>` +
            `</select></label>`
          : `<label>Kind <input id="cfgKind" value="${esc(
              cur.kind || "title"
            )}" readonly /></label>` +
            `<input type="hidden" id="cfgTemplateId" value="${esc(
              curRaw.template_id || ""
            )}" />`) +
        `</div>` +
        `<label class="grm-cfg-desc">Description <input id="cfgDesc" value="${esc(
          curRaw.description || ""
        )}" /></label>` +
        (templateMode
          ? `<label class="grm-cfg-desc">Release label <input id="cfgRelease" value="${esc(
              curRaw.release_label ||
                ((curRaw.kind || "") === "rebrand"
                  ? "Betsoft Release"
                  : "Global Release")
            )}" title="Hard ship date name" /></label>`
          : `<p class="grm-muted mono">Release: ${esc(
              cur.release_label || "—"
            )} · from template</p>`) +
        (templateMode
          ? `<p class="grm-hint"><strong>Phases</strong> stack by duration from ship. ` +
            `<strong>Workstreams</strong>: full phase or portion. ` +
            `<strong>Gates</strong>: point deadlines (phase- or release-relative) — not phase stack rows.</p>`
          : "") +
        `<div class="grm-cfg-table-wrap"><table class="grm-cfg-table grm-cfg-table-phases">` +
        `<thead><tr><th>${
          variation
            ? "Phase · weeks (locked structure)"
            : "Phase · duration · workstreams"
        }</th></tr></thead>` +
        `<tbody id="cfgStruts">${rows}</tbody></table></div>` +
        `<div class="grm-cfg-gates">` +
        `<div class="grm-cfg-gates-h">Gates` +
        (variation
          ? ` <span class="grm-muted">· from template</span>`
          : "") +
        `</div>` +
        (templateMode
          ? `<p class="grm-muted grm-cfg-ws-hint">Point deadlines. Offset in <strong>days</strong> or <strong>weeks</strong> (edge tails: 2d after phase end, 4d after ship, etc.).</p>`
          : "") +
        `<div id="cfgGates">${
          gateRows ||
          `<p class="grm-muted">${
            variation ? "No gates on parent template." : "No gates yet."
          }</p>`
        }</div>` +
        (templateMode
          ? `<button type="button" class="grm-btn grm-btn-sm" id="cfgAddGate">+ Gate</button>`
          : "") +
        `</div>` +
        `<div class="grm-cfg-actions">` +
        (templateMode
          ? `<button type="button" class="grm-btn" id="cfgAddStrut">+ Phase</button>` +
            `<button type="button" class="grm-btn" id="cfgSpawnVar">Spawn variation</button>`
          : "") +
        `<button type="button" class="grm-btn" id="cfgDel">Delete</button>` +
        `<button type="button" class="grm-btn grm-btn-primary" id="cfgSave">${
          variation ? "Save numbers" : "Save template"
        }</button>` +
        `</div></div>`;
    }

    root.innerHTML =
      `<div class="grm-config">` +
      `<div class="grm-vocab-intro">` +
      `<p><strong>Templates</strong> own bins, workstreams, and <strong>gate rules</strong>. ` +
      `<strong>Variations</strong> only change week numbers and workstream windows.</p>` +
      `</div>` +
      `<div class="grm-cfg-layout">` +
      `<div class="grm-cfg-list">` +
      `<div class="grm-cfg-list-h">Models` +
      `<button type="button" class="grm-btn grm-btn-sm" id="cfgNewType">+ Template</button></div>` +
      listHtml +
      `</div>` +
      editor +
      `</div></div>`;

    root.querySelectorAll(".grm-cfg-pick").forEach((btn) => {
      btn.onclick = () => {
        configEditId = btn.getAttribute("data-pid");
        renderConfig();
      };
    });

    if ($("cfgGotoTemplate") && curRaw) {
      $("cfgGotoTemplate").onclick = () => {
        configEditId = curRaw.template_id;
        renderConfig();
      };
    }

    function wireWsRow(row) {
      const fill = row.querySelector(".cfg-ws-fill");
      const portion = row.querySelector(".grm-cfg-ws-portion");
      const off = row.querySelector(".cfg-ws-off");
      const dur = row.querySelector(".cfg-ws-dur");
      const sync = () => {
        const on = fill && fill.checked;
        if (portion) portion.classList.toggle("is-dim", on);
        if (off) off.disabled = false;
        if (dur) dur.disabled = false;
      };
      if (fill) fill.onchange = sync;
      const unfill = () => {
        if (fill && fill.checked) {
          fill.checked = false;
          sync();
        }
      };
      if (off) off.addEventListener("input", unfill);
      if (dur) dur.addEventListener("input", unfill);
      sync();
      const rm = row.querySelector(".cfg-ws-rm");
      if (rm)
        rm.onclick = () => {
          const block = row.closest(".grm-cfg-ws-block");
          const tr = row.closest("tr");
          row.remove();
          if (block && tr && !block.querySelector(".grm-cfg-ws-row")) {
            block.hidden = true;
            block.classList.add("is-collapsed");
            block.classList.remove("is-open");
          }
          if (tr) updateWsToggleLabel(tr);
        };
    }

    function makeWsRowEl() {
      const row = document.createElement("div");
      row.className = "grm-cfg-ws-row";
      row.innerHTML =
        `<span class="grm-cfg-ws-mark">↳</span>` +
        `<input class="cfg-ws-name" value="" placeholder="Workstream name" />` +
        `<label class="grm-cfg-ws-fill"><input type="checkbox" class="cfg-ws-fill" checked /> full phase</label>` +
        `<span class="grm-cfg-ws-portion is-dim">` +
        `from w<input class="cfg-ws-off mono" type="number" step="0.25" min="0" value="0" />` +
        ` for <input class="cfg-ws-dur mono" type="number" step="0.25" min="0" value="1" />w` +
        `</span>` +
        `<button type="button" class="grm-btn grm-btn-sm cfg-ws-rm">✕</button>`;
      return row;
    }

    function updateWsToggleLabel(tr) {
      const btn = tr.querySelector(".cfg-ws-toggle");
      const block = tr.querySelector(".grm-cfg-ws-block");
      if (!btn || !block) return;
      const n = block.querySelectorAll(".grm-cfg-ws-row").length;
      const open = !block.hidden && block.classList.contains("is-open");
      if (n === 0 && !open) btn.textContent = "+ Workstream";
      else if (n === 0) btn.textContent = "Streams";
      else btn.textContent = open ? `Streams (${n})` : `Streams (${n})`;
    }

    function openWsBlock(tr, addFirstRow) {
      let block = tr.querySelector(".grm-cfg-ws-block");
      if (!block) {
        block = document.createElement("div");
        block.className = "grm-cfg-ws-block is-open";
        block.innerHTML =
          `<div class="grm-cfg-ws-tools">` +
          `<button type="button" class="grm-btn grm-btn-sm cfg-ws-add">+ Workstream</button>` +
          `<span class="grm-muted grm-cfg-ws-hint">full phase or portion (from week · for Nw)</span>` +
          `</div>`;
        tr.querySelector("td").appendChild(block);
        wireWsBlock(block);
      }
      block.hidden = false;
      block.classList.add("is-open");
      block.classList.remove("is-collapsed");
      if (addFirstRow && !block.querySelector(".grm-cfg-ws-row")) {
        const tools = block.querySelector(".grm-cfg-ws-tools");
        const row = makeWsRowEl();
        if (tools) block.insertBefore(row, tools);
        else block.appendChild(row);
        wireWsRow(row);
      }
      updateWsToggleLabel(tr);
    }

    function wireWsBlock(block) {
      block.querySelectorAll(".grm-cfg-ws-row").forEach((row) => wireWsRow(row));
      const add = block.querySelector(".cfg-ws-add");
      if (add) {
        add.onclick = () => {
          const tools = block.querySelector(".grm-cfg-ws-tools");
          const row = makeWsRowEl();
          if (tools) block.insertBefore(row, tools);
          else block.appendChild(row);
          wireWsRow(row);
          const tr = block.closest("tr");
          if (tr) updateWsToggleLabel(tr);
        };
      }
    }

    function wireStrutRow(tr) {
      const rm = tr.querySelector(".cfg-rm");
      if (rm) rm.onclick = () => tr.remove();
      const up = tr.querySelector(".cfg-up");
      if (up)
        up.onclick = () => {
          if (tr.previousElementSibling)
            tr.parentNode.insertBefore(tr, tr.previousElementSibling);
        };
      const dn = tr.querySelector(".cfg-dn");
      if (dn)
        dn.onclick = () => {
          if (tr.nextElementSibling)
            tr.parentNode.insertBefore(tr.nextElementSibling, tr);
        };
      const wsBlock = tr.querySelector(".grm-cfg-ws-block");
      if (wsBlock) wireWsBlock(wsBlock);
      const toggle = tr.querySelector(".cfg-ws-toggle");
      if (toggle) {
        toggle.onclick = () => {
          const block = tr.querySelector(".grm-cfg-ws-block");
          if (!block || block.hidden || block.classList.contains("is-collapsed")) {
            // open panel; if empty, add first stream row so + Workstream feels immediate
            openWsBlock(tr, true);
            return;
          }
          // collapse if already open
          block.hidden = true;
          block.classList.add("is-collapsed");
          block.classList.remove("is-open");
          updateWsToggleLabel(tr);
        };
      }
    }

    const tbody = $("cfgStruts");
    if (tbody) {
      tbody.querySelectorAll("tr.cfg-phase-row").forEach((tr) => wireStrutRow(tr));
    }

    if ($("cfgAddStrut")) {
      $("cfgAddStrut").onclick = () => {
        const tb = $("cfgStruts");
        const tr = document.createElement("tr");
        tr.className = "cfg-phase-row";
        // blank phase = one line only; workstreams on demand
        tr.innerHTML =
          `<td colspan="3">` +
          `<div class="grm-cfg-phase-line">` +
          `<input class="cfg-name" value="" placeholder="Phase name" />` +
          `<input class="cfg-dur mono" type="number" step="1" value="4" style="width:4rem" />` +
          `<select class="cfg-dur-unit" style="width:auto;font-size:0.55rem">` +
          `<option value="weeks" selected>weeks</option>` +
          `<option value="days">days</option>` +
          `</select>` +
          `<button type="button" class="grm-btn grm-btn-sm cfg-up">↑</button>` +
          `<button type="button" class="grm-btn grm-btn-sm cfg-dn">↓</button>` +
          `<button type="button" class="grm-btn grm-btn-sm cfg-ws-toggle">+ Workstream</button>` +
          `<button type="button" class="grm-btn grm-btn-sm cfg-rm">✕</button>` +
          `</div>` +
          `<div class="grm-cfg-ws-block is-collapsed" hidden>` +
          `<div class="grm-cfg-ws-tools">` +
          `<button type="button" class="grm-btn grm-btn-sm cfg-ws-add">+ Workstream</button>` +
          `<span class="grm-muted grm-cfg-ws-hint">full phase or portion (from week · for Nw)</span>` +
          `</div></div></td>`;
        tb.appendChild(tr);
        wireStrutRow(tr);
        refreshGatePhaseSelects();
      };
    }

    function collectPhaseTreeLive() {
      /** @type {{name: string, workstreams: string[]}[]} */
      const tree = [];
      const tb = $("cfgStruts");
      if (!tb) return tree;
      tb.querySelectorAll("tr.cfg-phase-row").forEach((tr) => {
        const nameEl = tr.querySelector(".cfg-name");
        const n = (
          nameEl
            ? nameEl.value
            : tr.getAttribute("data-phase-name") ||
              (tr.querySelector(".cfg-name-ro") || {}).textContent ||
              ""
        ).trim();
        if (!n) return;
        const workstreams = [];
        tr.querySelectorAll(".grm-cfg-ws-row").forEach((wr) => {
          const nameIn = wr.querySelector(".cfg-ws-name");
          const wn = (
            nameIn
              ? nameIn.value
              : wr.getAttribute("data-ws-name") ||
                (wr.querySelector(".cfg-ws-name-ro") || {}).textContent ||
                ""
          ).trim();
          if (wn) workstreams.push(wn);
        });
        tree.push({ name: n, workstreams });
      });
      return tree;
    }

    function collectPhaseNamesLive() {
      return collectPhaseTreeLive().map((p) => p.name);
    }

    function refreshGatePhaseSelects() {
      const tree = collectPhaseTreeLive();
      const names = tree.map((p) => p.name);
      document.querySelectorAll(".grm-cfg-gate-row").forEach((row) => {
        if (row.classList.contains("is-ro")) return;
        const phaseSel = row.querySelector(".cfg-gate-phase");
        const wsSel = row.querySelector(".cfg-gate-ws");
        const curP = phaseSel ? phaseSel.value : "";
        const curW = wsSel ? wsSel.value : "";
        if (phaseSel) {
          phaseSel.innerHTML = names.length
            ? names
                .map(
                  (n) =>
                    `<option value="${esc(n)}" ${
                      n === curP ? "selected" : ""
                    }>${esc(n)}</option>`
                )
                .join("")
            : `<option value="">(add phases first)</option>`;
          if (curP && names.includes(curP)) phaseSel.value = curP;
        }
        refreshGateWsSelect(row, tree);
        if (wsSel && curW) {
          const opts = [...wsSel.options].map((o) => o.value);
          if (opts.includes(curW)) wsSel.value = curW;
        }
      });
    }

    function refreshGateWsSelect(row, tree) {
      const wsSel = row.querySelector(".cfg-gate-ws");
      const phaseSel = row.querySelector(".cfg-gate-phase");
      if (!wsSel) return;
      const t = tree || collectPhaseTreeLive();
      const pname = phaseSel ? phaseSel.value : "";
      const node = t.find((p) => p.name === pname);
      const streams = (node && node.workstreams) || [];
      const cur = wsSel.value;
      wsSel.innerHTML = streams.length
        ? streams
            .map(
              (n) =>
                `<option value="${esc(n)}" ${
                  n === cur ? "selected" : ""
                }>${esc(n)}</option>`
            )
            .join("")
        : `<option value="">(no workstreams on phase)</option>`;
      if (cur && streams.includes(cur)) wsSel.value = cur;
    }

    function wireGateRow(row) {
      const rm = row.querySelector(".cfg-gate-rm");
      if (rm) rm.onclick = () => row.remove();
      const anchor = row.querySelector(".cfg-gate-anchor");
      const phaseSel = row.querySelector(".cfg-gate-phase");
      const wsSel = row.querySelector(".cfg-gate-ws");
      const rel = row.querySelector(".cfg-gate-rel");
      const sync = () => {
        const a = anchor ? anchor.value : "phase";
        if (phaseSel) phaseSel.disabled = a === "release";
        if (wsSel) wsSel.disabled = a !== "workstream";
        if (rel) {
          const prev = rel.value;
          rel.innerHTML = gateRelationOptions(prev, a);
          // if previous still valid, keep it
          const ok = [...rel.options].some((o) => o.value === prev);
          if (ok) rel.value = prev;
        }
        if (a === "workstream") refreshGateWsSelect(row);
      };
      if (anchor) anchor.onchange = sync;
      if (phaseSel)
        phaseSel.onchange = () => {
          refreshGateWsSelect(row);
        };
      sync();
    }

    document.querySelectorAll(".grm-cfg-gate-row").forEach((row) => {
      if (!row.classList.contains("is-ro")) wireGateRow(row);
    });

    // keep gate phase/stream dropdowns in sync when structure edits
    const strutBox = $("cfgStruts");
    if (strutBox) {
      strutBox.addEventListener("input", (ev) => {
        const t = ev.target;
        if (
          t &&
          (t.classList.contains("cfg-name") ||
            t.classList.contains("cfg-ws-name"))
        ) {
          refreshGatePhaseSelects();
        }
      });
      strutBox.addEventListener("click", (ev) => {
        const t = ev.target;
        if (
          t &&
          (t.classList.contains("cfg-ws-add") ||
            t.classList.contains("cfg-ws-rm") ||
            t.classList.contains("cfg-rm"))
        ) {
          setTimeout(refreshGatePhaseSelects, 0);
        }
      });
    }

    if ($("cfgAddGate")) {
      $("cfgAddGate").onclick = () => {
        const host = $("cfgGates");
        if (!host) return;
        const empty = host.querySelector("p.grm-muted");
        if (empty) empty.remove();
        const tree = collectPhaseTreeLive();
        const names = tree.map((p) => p.name);
        const first = tree[0];
        const row = document.createElement("div");
        row.className = "grm-cfg-gate-row";
        row.setAttribute("data-gid", `gt-${Date.now().toString(36)}`);
        row.innerHTML =
          `<input class="cfg-gate-name" value="" placeholder="e.g. Deliver Math to Devs" />` +
          `<select class="cfg-gate-anchor">` +
          `<option value="phase">phase</option>` +
          `<option value="workstream" selected>workstream</option>` +
          `<option value="release">release</option>` +
          `</select>` +
          `<select class="cfg-gate-phase">${
            names.length
              ? names
                  .map((n) => `<option value="${esc(n)}">${esc(n)}</option>`)
                  .join("")
              : `<option value="">(add phases first)</option>`
          }</select>` +
          `<select class="cfg-gate-ws">${
            first && first.workstreams.length
              ? first.workstreams
                  .map((n) => `<option value="${esc(n)}">${esc(n)}</option>`)
                  .join("")
              : `<option value="">(no workstreams on phase)</option>`
          }</select>` +
          `<select class="cfg-gate-rel">${gateRelationOptions(
            "at_end",
            "workstream"
          )}</select>` +
          `<label class="grm-cfg-gate-off">N ` +
          `<input class="cfg-gate-off mono" type="number" step="1" min="0" value="0" style="width:3.2rem" />` +
          `<select class="cfg-gate-unit"><option value="days" selected>days</option><option value="weeks">weeks</option></select>` +
          `</label>` +
          `<button type="button" class="grm-btn grm-btn-sm cfg-gate-rm">✕</button>`;
        host.appendChild(row);
        wireGateRow(row);
      };
    }

    if ($("cfgSave") && curRaw) {
      $("cfgSave").onclick = async () => {
        let id = ($("cfgId").value || "").trim().toLowerCase();
        id = id.replace(/\s+/g, "_").replace(/[^a-z0-9_-]/g, "");
        if (!id) return toast("code required");
        if (!/^[a-z0-9][a-z0-9_-]{0,47}$/.test(id)) {
          return toast("code: start with letter/digit, then a-z 0-9 _ -");
        }
        const previousId = (
          ($("cfgPrevId") && $("cfgPrevId").value) ||
          curRaw.id ||
          ""
        )
          .trim()
          .toLowerCase();
        const struts = [];
        $("cfgStruts").querySelectorAll("tr.cfg-phase-row").forEach((tr) => {
          const nameEl = tr.querySelector(".cfg-name");
          const name =
            (nameEl
              ? nameEl.value
              : tr.getAttribute("data-phase-name") ||
                (tr.querySelector(".cfg-name-ro") || {}).textContent ||
                ""
            ).trim();
          if (!name) return;
          const rawDur = tr.querySelector(".cfg-dur")
            ? tr.querySelector(".cfg-dur").value
            : "0";
          const unitEl = tr.querySelector(".cfg-dur-unit");
          const unit =
            (unitEl && unitEl.value) ||
            (variation ? "weeks" : "weeks");
          const n = Number(rawDur) || 0;
          const days =
            unit === "days" ? Math.round(n) : weeksToDays(n) ?? 0;
          const weeks = unit === "days" ? days / 7 : n;
          const workstreams = [];
          tr.querySelectorAll(".grm-cfg-ws-row").forEach((wr) => {
            const nameIn = wr.querySelector(".cfg-ws-name");
            const wn = (
              nameIn
                ? nameIn.value
                : wr.getAttribute("data-ws-name") ||
                  (wr.querySelector(".cfg-ws-name-ro") || {}).textContent ||
                  ""
            ).trim();
            if (!wn) return;
            const fillEl = wr.querySelector(".cfg-ws-fill");
            const offEl = wr.querySelector(".cfg-ws-off");
            const durEl = wr.querySelector(".cfg-ws-dur");
            const off = offEl ? Number(offEl.value) || 0 : 0;
            const durRaw = durEl ? String(durEl.value).trim() : "";
            const durNum = durRaw === "" ? null : Number(durRaw);
            let fill;
            if (variation) {
              fill = wr.getAttribute("data-fill") === "1";
            } else {
              fill = !!(fillEl && fillEl.checked);
            }
            workstreams.push({
              name: wn,
              kind: "workstream",
              fill_parent: fill,
              offset_weeks_from_start: fill ? 0 : off,
              duration_weeks:
                fill
                  ? null
                  : durNum != null && !Number.isNaN(durNum) && durNum > 0
                    ? durNum
                    : 1,
            });
          });
          struts.push({
            name,
            role: "phase",
            kind: "range",
            duration_days: days,
            duration_weeks: weeks,
            workstreams,
          });
        });
        const gates = [];
        if (!variation) {
          document.querySelectorAll("#cfgGates .grm-cfg-gate-row").forEach((row) => {
            const name = (
              (row.querySelector(".cfg-gate-name") || {}).value || ""
            ).trim();
            if (!name) return;
            const anchor =
              (row.querySelector(".cfg-gate-anchor") || {}).value || "phase";
            let relation =
              (row.querySelector(".cfg-gate-rel") || {}).value || "at_end";
            const phase_name =
              (row.querySelector(".cfg-gate-phase") || {}).value || "";
            const workstream_name =
              (row.querySelector(".cfg-gate-ws") || {}).value || "";
            const offEl = row.querySelector(".cfg-gate-off");
            const unitEl = row.querySelector(".cfg-gate-unit");
            const unit =
              (unitEl && unitEl.value) || "days";
            const rawN = offEl ? Number(offEl.value) || 0 : 0;
            const offset_days =
              unit === "weeks" ? Math.round(rawN * 7) : Math.round(rawN);
            const offset_weeks =
              unit === "weeks" ? rawN : offset_days / 7;
            if (anchor === "release" && relation === "at_end") {
              relation = "before_release";
            }
            gates.push({
              id: row.getAttribute("data-gid") || `gt-${Date.now().toString(36)}`,
              name,
              role: "gate",
              kind: "point",
              anchor,
              phase_name:
                anchor === "phase" || anchor === "workstream" ? phase_name : "",
              workstream_name:
                anchor === "workstream" ? workstream_name : "",
              relation,
              offset_unit: unit,
              offset_days,
              offset_weeks,
            });
          });
        }
        const pt = {
          id,
          label: ($("cfgLabel").value || id).trim(),
          description: ($("cfgDesc").value || "").trim(),
          struts,
        };
        if (variation) {
          pt.model = "variation";
          let tid =
            ($("cfgTemplateId") && $("cfgTemplateId").value) ||
            curRaw.template_id ||
            "";
          tid = String(tid).trim().toLowerCase();
          pt.template_id = tid;
          pt.kind = cur.kind || "title";
          pt.release_label = cur.release_label || "Global Release";
          // gates live on template only
        } else {
          pt.model = "template";
          const kind =
            ($("cfgKind") && $("cfgKind").value) || curRaw.kind || "title";
          pt.kind = kind;
          pt.release_label =
            ($("cfgRelease") && $("cfgRelease").value.trim()) ||
            (kind === "rebrand" ? "Betsoft Release" : "Global Release");
          pt.gates = gates;
        }
        const payload = { product_type: pt };
        if (previousId && previousId !== id) payload.previous_id = previousId;
        const r = await fetch("/api/product-types", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const j = await r.json();
        if (!j.ok) return toast(j.error || "save failed");
        toast(j.message || (variation ? "variation saved" : "template saved"));
        configEditId = id;
        await refresh();
        renderConfig();
      };
    }

    if ($("cfgNewType")) {
      $("cfgNewType").onclick = () => {
        // blank sheet — operator defines bins; no borrowed standard release buckets
        const id = `mdl-${Date.now().toString(36).slice(-5)}`;
        configEditId = id;
        state.product_types = state.product_types || [];
        state.product_types.push({
          id,
          label: "New template",
          model: "template",
          kind: "title",
          release_label: "Global Release",
          description: "",
          struts: [],
        });
        renderConfig();
        toast("blank template — + Phase to add bins, then Save");
      };
    }

    if ($("cfgSpawnVar") && curRaw && templateMode) {
      $("cfgSpawnVar").onclick = () => {
        const id = `var-${Date.now().toString(36).slice(-5)}`;
        const copy = {
          id,
          label: "New variation",
          model: "variation",
          template_id: curRaw.id,
          kind: curRaw.kind || "title",
          release_label: curRaw.release_label,
          description: `Numbers-only variation of ${curRaw.label || curRaw.id}`,
          struts: JSON.parse(JSON.stringify(curRaw.struts || [])),
        };
        state.product_types.push(copy);
        configEditId = id;
        renderConfig();
        toast("variation spawned — set code + weeks, then Save numbers");
      };
    }

    if ($("cfgDel") && curRaw) {
      $("cfgDel").onclick = async () => {
        const what = variation ? "variation" : "template";
        const kids = variation
          ? []
          : (state.product_types || []).filter(
              (p) =>
                isVariation(p) && (p.template_id || "") === curRaw.id
            );
        let msg = `Delete ${what} “${curRaw.label || curRaw.id}”?`;
        if (kids.length) {
          msg +=
            `\n\nAlso deletes ${kids.length} variation(s): ` +
            kids.map((k) => k.label || k.id).join(", ");
        }
        if (!confirm(msg)) return;
        const r = await fetch("/api/product-types/delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: curRaw.id, cascade: true }),
        });
        const j = await r.json();
        if (!j.ok) return toast(j.error || "delete failed");
        configEditId = null;
        toast(j.message || "deleted");
        await refresh();
        renderConfig();
      };
    }
  }

  function renderQuarterChips() {
    const host = $("quarterChips");
    const qs = state.quarters || [];
    const allOn = quarterFilter.size === 0;
    host.innerHTML =
      `<button type="button" class="grm-qchip ${allOn ? "is-on" : ""}" data-q="">All quarters</button>` +
      qs
        .map((q) => {
          const on = quarterFilter.has(q.key);
          return `<button type="button" class="grm-qchip ${on ? "is-on" : ""}" data-q="${esc(q.key)}">${esc(q.label)}</button>`;
        })
        .join("");
    host.querySelectorAll(".grm-qchip").forEach((btn) => {
      btn.addEventListener("click", () => {
        const q = btn.getAttribute("data-q") || "";
        if (!q) {
          quarterFilter = new Set();
        } else {
          if (quarterFilter.has(q)) quarterFilter.delete(q);
          else quarterFilter.add(q);
        }
        renderQuarterChips();
        render();
      });
    });
  }

  const MONTH3 = [
    "JAN",
    "FEB",
    "MAR",
    "APR",
    "MAY",
    "JUN",
    "JUL",
    "AUG",
    "SEP",
    "OCT",
    "NOV",
    "DEC",
  ];

  /** At-a-glance: JUN-08-26 (not ISO). Full ISO stays in title tooltip. */
  function compactDate(iso) {
    if (!iso) return "—";
    const m = String(iso).trim().match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!m) return String(iso);
    const mon = MONTH3[Math.max(0, Math.min(11, parseInt(m[2], 10) - 1))];
    return `${mon}-${m[3]}-${m[1].slice(2)}`;
  }

  function phaseDateLabel(p) {
    const a = p.start || p.end;
    const b = p.end || p.start;
    if (!a && !b) return "—";
    if ((p.kind || "range") === "point" || !p.start || !p.end || p.start === p.end) {
      return compactDate(a);
    }
    return `${compactDate(p.start)} → ${compactDate(p.end)}`;
  }

  function phaseDateTitle(p) {
    if (!p) return "";
    if (p.start && p.end && p.start !== p.end) return `${p.start} → ${p.end}`;
    return p.start || p.end || "";
  }

  function isGate(p) {
    return (p.role || "") === "gate" || (p.kind || "") === "point" && (p.role || "gate") === "gate";
  }

  /** Latest edit-trail reason, or event.notes */
  function eventNoteText(p) {
    const edits = p.edits || [];
    if (edits.length) {
      const last = edits[edits.length - 1];
      if (last && last.reason) return String(last.reason).trim();
    }
    return String(p.notes || "").trim();
  }

  function hasChangeTrail(p) {
    return !!(p && ((p.edits && p.edits.length) || eventNoteText(p)));
  }

  /** Small CHANGE pill — hover shows Greg's reason fragment */
  function changePill(p) {
    if (!hasChangeTrail(p)) return "";
    const note = eventNoteText(p) || "modified";
    return (
      `<span class="grm-change-pill" title="${esc(note)}">Change</span>`
    );
  }

  function eventListHtml(t, events, role) {
    if (!events.length) {
      return `<p class="grm-muted">Empty spine slots — use Edit to set dates.</p>`;
    }
    const canAssign = role === "phase";
    return (
      `<div class="grm-ev-table">` +
      `<div class="grm-ev-table-h">` +
      `<span></span><span>Label</span><span>Dates</span><span></span>` +
      `</div>` +
      events
        .map((p) => {
          const dated = p.start || p.end;
          const streams = (p.workstreams || []).filter((w) => w && w.name);
          const phaseChips = canAssign ? crewChipsHtml(t, p.id, "") : "";
          const wsHtml =
            role === "phase" && streams.length
              ? streams
                  .map((w) => {
                    const span =
                      w.fill_parent === false && !w.locked
                        ? `from w${w.offset_weeks_from_start || 0}${
                            w.duration_weeks != null
                              ? ` · ${w.duration_weeks}w`
                              : ""
                          }`
                        : w.locked
                          ? "manual"
                          : "full phase";
                    const wObj = w.start || w.end ? w : p;
                    const wid = w.id || "";
                    return (
                      `<div class="grm-ws-row role-${esc(role)} ${
                        w.locked ? "is-locked" : ""
                      }" data-eid="${esc(p.id)}" data-wsid="${esc(wid)}">` +
                      `<span class="grm-ws-gutter" aria-hidden="true"></span>` +
                      `<span class="grm-ev-label grm-ws-label">` +
                      `<span class="grm-ws-branch" title="workstream">↳</span>` +
                      `<span class="grm-ws-name">${esc(w.name)}</span>` +
                      changePill(w) +
                      `<span class="grm-ws-meta" title="template window (not an edit reason)">${esc(
                        span
                      )}</span>` +
                      crewChipsHtml(t, p.id, wid) +
                      `</span>` +
                      `<span class="grm-ev-dates grm-ev-dates-ws mono" title="${esc(
                        phaseDateTitle(wObj)
                      )}">${esc(phaseDateLabel(wObj))}</span>` +
                      `<span class="grm-ev-acts grm-ws-acts">` +
                      `<button type="button" class="grm-btn grm-btn-sm ev-edit-ws" data-eid="${esc(
                        p.id
                      )}" data-wsid="${esc(wid)}" title="Edit this line">Edit</button>` +
                      `<button type="button" class="grm-btn grm-btn-sm ev-assign" data-eid="${esc(
                        p.id
                      )}" data-wsid="${esc(wid)}" title="Assign person to this work">+ Crew</button>` +
                      `</span>` +
                      `</div>`
                    );
                  })
                  .join("")
              : "";
          return (
            `<div class="grm-ev-block">` +
            `<div class="grm-ev-row role-${esc(role)} ${dated ? "" : "is-empty"} ${
              p.locked ? "is-locked" : ""
            }" data-eid="${esc(p.id)}">` +
            `<span class="grm-role-tag">${role === "gate" ? "GATE" : "PHASE"}</span>` +
            `<span class="grm-ev-label" title="${esc(p.name || "")}">` +
            `<span class="grm-ev-name">${esc(p.name)}</span>` +
            changePill(p) +
            phaseChips +
            `</span>` +
            `<span class="grm-ev-dates grm-ev-dates-phase mono" title="${esc(
              phaseDateTitle(p)
            )}">${esc(phaseDateLabel(p))}</span>` +
            `<span class="grm-ev-acts">` +
            `<button type="button" class="grm-btn grm-btn-sm ev-edit" data-eid="${esc(
              p.id
            )}" title="Edit dates">Edit</button>` +
            (canAssign
              ? `<button type="button" class="grm-btn grm-btn-sm ev-assign" data-eid="${esc(
                  p.id
                )}" data-wsid="" title="Assign person to this phase">+ Crew</button>`
              : "") +
            `<button type="button" class="grm-btn grm-btn-sm ev-del" data-eid="${esc(
              p.id
            )}" title="Remove">✕</button>` +
            `</span></div>` +
            wsHtml +
            `</div>`
          );
        })
        .join("") +
      `</div>`
    );
  }

  function closeEventModal() {
    const m = $("modalEvent");
    if (m) m.hidden = true;
  }

  function setLabelPrefix(labelEl, text) {
    // Keep the first text node as the caption; inputs stay as children
    if (!labelEl) return;
    let set = false;
    for (const node of labelEl.childNodes) {
      if (node.nodeType === Node.TEXT_NODE) {
        node.textContent = text + " ";
        set = true;
        break;
      }
    }
    if (!set) labelEl.insertBefore(document.createTextNode(text + " "), labelEl.firstChild);
  }

  function openEventModal(opts) {
    // opts: { mode, title, event?, workstream?, role? }
    const mode = opts.mode || "edit";
    const t = opts.title;
    const p = opts.event || null;
    const ws = opts.workstream || null;
    const isWs = !!ws;
    const role = (
      opts.role ||
      (isWs ? "workstream" : p && p.role) ||
      "phase"
    ).toLowerCase();
    const isGate = role === "gate";
    const isRemove = mode === "remove";
    const isAdd = mode === "add";
    const line = isWs ? ws : p;

    $("ev_mode").value = mode;
    $("ev_title_id").value = t.id;
    $("ev_event_id").value = p ? p.id : "";
    if ($("ev_workstream_id"))
      $("ev_workstream_id").value = isWs ? ws.id || "" : "";
    $("ev_role").value = isWs ? "workstream" : role;

    const titleEl = $("modalEventTitle");
    const hintEl = $("modalEventHint");
    const nameWrap = $("ev_name_wrap");
    const datesWrap = $("ev_dates_wrap");
    const endWrap = $("ev_end_wrap");
    const startWrap = $("ev_start_wrap");
    const saveBtn = $("btnSaveEvent");

    setLabelPrefix(startWrap, isGate && !isWs ? "Date" : "Start");
    endWrap.hidden = (isGate && !isWs) || isRemove;

    const cascadeWrap = $("ev_cascade_wrap");
    const cascadeCb = $("ev_cascade_earlier");

    if (isRemove) {
      titleEl.textContent = `Remove ${isGate ? "gate" : "phase"}`;
      hintEl.textContent = `Remove “${p.name}” from this title only. Note is required for the trail.`;
      nameWrap.hidden = true;
      datesWrap.hidden = true;
      $("ev_name").required = false;
      $("ev_reason").value = "";
      $("ev_reason").placeholder = "why remove this slot?";
      saveBtn.textContent = "Remove";
      if (cascadeWrap) cascadeWrap.hidden = true;
    } else if (isAdd) {
      titleEl.textContent = isGate ? "Add gate" : "Add phase";
      hintEl.textContent =
        "Adds a slot on this title only. Note required — becomes a Change pill.";
      nameWrap.hidden = false;
      datesWrap.hidden = false;
      $("ev_name").required = true;
      $("ev_name").value = isGate ? "Deliver Math to Devs" : "Design Phase";
      $("ev_start").value = "";
      $("ev_end").value = "";
      $("ev_reason").value = "added manually";
      $("ev_reason").placeholder = "e.g. extra LQA pass";
      saveBtn.textContent = "Add";
      if (cascadeWrap) cascadeWrap.hidden = true;
    } else if (isWs) {
      titleEl.textContent = "Edit workstream";
      hintEl.textContent = `↳ “${ws.name}” under “${p.name}” — set dates by hand; note required (Change pill). Workstream-only (no spine cascade).`;
      nameWrap.hidden = true;
      datesWrap.hidden = false;
      endWrap.hidden = false;
      $("ev_name").required = false;
      $("ev_name").value = ws.name || "";
      $("ev_start").value = ws.start || p.start || "";
      $("ev_end").value = ws.end || ws.start || p.end || "";
      $("ev_reason").value = "";
      $("ev_reason").placeholder = "e.g. math slip +1w · scope change";
      saveBtn.textContent = "Save line";
      if (cascadeWrap) cascadeWrap.hidden = true;
    } else {
      titleEl.textContent = `Edit ${isGate ? "gate" : "phase"}`;
      hintEl.textContent = isGate
        ? `“${p.name}” — ship/release stays fixed. Moving a gate earlier can pull prior lines back.`
        : `“${p.name}” — ship is immovable. Need more time? Move Start earlier (or extend End — we convert that to Start earlier + hold handoff). Earlier phases cascade back with you.`;
      nameWrap.hidden = true;
      datesWrap.hidden = false;
      $("ev_name").required = false;
      $("ev_name").value = p.name || "";
      $("ev_start").value = p.start || "";
      $("ev_end").value = p.end || p.start || "";
      $("ev_reason").value = "";
      $("ev_reason").placeholder = "e.g. holiday slip +1w · need +2w dev";
      saveBtn.textContent = "Save dates";
      if (cascadeWrap) {
        cascadeWrap.hidden = false;
        if (cascadeCb) cascadeCb.checked = true;
      }
    }

    $("modalEvent").hidden = false;
    setTimeout(() => {
      const focusEl = isAdd ? $("ev_name") : $("ev_reason");
      if (focusEl) focusEl.focus();
    }, 30);
  }

  function editEvent(t, eid) {
    const p = (t.phases || []).find((x) => x.id === eid);
    if (!p) return;
    openEventModal({ mode: "edit", title: t, event: p });
  }

  function editWorkstream(t, phaseId, wsId) {
    const p = (t.phases || []).find((x) => x.id === phaseId);
    if (!p) return;
    const ws = (p.workstreams || []).find((x) => x.id === wsId);
    if (!ws) return;
    openEventModal({ mode: "edit", title: t, event: p, workstream: ws });
  }

  function removeEvent(t, eid) {
    const p = (t.phases || []).find((x) => x.id === eid);
    if (!p) return;
    openEventModal({ mode: "remove", title: t, event: p });
  }

  function addEvent(t, role) {
    openEventModal({ mode: "add", title: t, role: role || "phase" });
  }

  async function submitEventModal(e) {
    e.preventDefault();
    const mode = $("ev_mode").value;
    const tid = $("ev_title_id").value;
    const eid = $("ev_event_id").value;
    const wsid =
      ($("ev_workstream_id") && $("ev_workstream_id").value) || "";
    const role = ($("ev_role").value || "phase").toLowerCase();
    const reason = String(($("ev_reason") && $("ev_reason").value) || "").trim();
    if (!reason) {
      toast("note required");
      return;
    }

    let body;
    if (mode === "remove") {
      body = { id: eid, delete: true, reason };
    } else if (mode === "add") {
      const name = String(($("ev_name") && $("ev_name").value) || "").trim();
      if (!name) {
        toast("name required");
        return;
      }
      const start = String(($("ev_start") && $("ev_start").value) || "").trim() || null;
      let end = start;
      if (role === "phase") {
        end = String(($("ev_end") && $("ev_end").value) || "").trim() || start;
      }
      body = { name, role, start, end, reason };
    } else if (wsid) {
      const start =
        String(($("ev_start") && $("ev_start").value) || "").trim() || null;
      const end =
        String(($("ev_end") && $("ev_end").value) || "").trim() || start;
      body = {
        id: eid,
        workstream_id: wsid,
        start,
        end: end || start,
        reason,
      };
    } else {
      // edit phase/gate dates — keep existing name
      const t = (state.titles || []).find((x) => x.id === tid);
      const p = t && (t.phases || []).find((x) => x.id === eid);
      if (!p) {
        toast("event not found");
        return;
      }
      const start = String(($("ev_start") && $("ev_start").value) || "").trim() || null;
      let end = start;
      if (role === "phase") {
        end = String(($("ev_end") && $("ev_end").value) || "").trim() || start;
      } else if (!end && p.end) {
        end = p.end;
      }
      body = {
        id: eid,
        name: p.name,
        role: role === "workstream" ? p.role : role,
        start,
        end: end || start,
        reason,
        cascade_earlier: !!(
          $("ev_cascade_earlier") && $("ev_cascade_earlier").checked
        ),
      };
    }

    const r = await fetch(`/api/titles/${tid}/event`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const j = await r.json();
    if (!j.ok) return toast(j.error || "save failed");
    closeEventModal();
    const msg =
      mode === "remove"
        ? "removed"
        : mode === "add"
          ? "added"
          : j.message || "dates saved";
    toast(msg);
    await refresh();
    openTitle(tid);
  }

  function lineOptionsHtml(selectedId) {
    return (state.product_lines || [])
      .map(
        (L) =>
          `<option value="${esc(L.id)}" ${
            L.id === selectedId ? "selected" : ""
          }>${esc(L.name)}</option>`
      )
      .join("");
  }

  function modelOptionsHtml(selectedId) {
    return (state.product_types || [])
      .map((p) => {
        const sel = selectedId === p.id ? "selected" : "";
        const tag = isVariation(p)
          ? ` · variation of ${p.template_id || "?"}`
          : " · template";
        return `<option value="${esc(p.id)}" ${sel}>${esc(
          p.label || p.id
        )}${esc(tag)}</option>`;
      })
      .join("");
  }

  function twinOptionsHtml(t) {
    return (
      `<option value="">— none —</option>` +
      (state.titles || [])
        .filter((x) => x.id !== t.id)
        .map((x) => {
          const sel =
            (t.twin_code || "").toUpperCase() ===
            String(x.code || "").toUpperCase()
              ? "selected"
              : "";
          return `<option value="${esc(x.code)}" ${sel}>${esc(
            x.code
          )} · ${esc(x.name)}</option>`;
        })
        .join("")
    );
  }

  function productCardHtml(t) {
    const model = rawType(t.product_type_id || t.complexity);
    const modelLab = model ? model.label || model.id : t.product_type_id || "—";
    const lifeLab = t.lifecycle_label || "Planning";
    const lane = t.lane || t.bucket || "—";
    const phaseNow = t.current_phase || "—";
    const ship = t.release_date || "—";
    const theme = t.theme || "";
    const math = t.math_model || "";
    return (
      `<div class="grm-pcard">` +
      `<div class="grm-pcard-head">` +
      `<div class="grm-pcard-head-top">` +
      `<span class="grm-pcard-code mono">${esc(t.code || "—")}</span>` +
      `<span class="grm-pcard-badges">` +
      typeBadge(t) +
      lifecycleBadge(t) +
      bucketBadge(lane) +
      ((t.kind || "") === "rebrand"
        ? `<span class="grm-badge cx-rebrand">REBRAND</span>`
        : "") +
      `</span></div>` +
      `<div class="grm-pcard-name">${esc(t.name || t.code || "Untitled")}</div>` +
      `<div class="grm-pcard-sub mono">` +
      `<span>Ship <strong>${esc(ship)}</strong></span>` +
      `<span>${esc(lineName(t.product_line_id))}</span>` +
      `<span>Lane <strong>${esc(phaseNow !== "—" ? phaseNow : lane)}</strong></span>` +
      `</div>` +
      (theme || math
        ? `<div class="grm-pcard-dossier-preview">` +
          (theme ? `<span>Theme · ${esc(theme)}</span>` : "") +
          (math ? `<span>Math · ${esc(math)}</span>` : "") +
          `</div>`
        : `<div class="grm-pcard-dossier-preview grm-muted">Theme / math · not set</div>`) +
      `</div>` +
      // identity rows
      `<div class="grm-pcard-block">` +
      `<div class="grm-ev-head"><strong>IDENTITY</strong>` +
      `<button type="button" class="grm-btn grm-btn-sm" id="btnEditIdentity">Edit</button></div>` +
      `<div id="pcIdentityView" class="grm-pcard-rows">` +
      rowKV("Code", t.code || "—") +
      rowKV("Name", t.name || "—") +
      rowKV("Ship", ship) +
      rowKV("Line", lineName(t.product_line_id)) +
      rowKV("Model", modelLab) +
      rowKV("Kind", (t.kind || "title") === "rebrand" ? "Rebrand" : "Full title") +
      rowKV("Lifecycle", lifeLab) +
      rowKV("Schedule lane", lane) +
      rowKV("Crew", crewLabel(t)) +
      `</div>` +
      `<div id="pcIdentityEdit" class="grm-pcard-edit" hidden>` +
      `<div class="grm-field"><label>CODE</label><input id="f_code" value="${esc(
        t.code || ""
      )}" /></div>` +
      `<div class="grm-field"><label>NAME</label><input id="f_name" value="${esc(
        t.name || ""
      )}" placeholder="optional" /></div>` +
      `<div class="grm-field"><label>SHIP DATE</label><input id="f_rel" type="date" value="${esc(
        t.release_date || ""
      )}" /></div>` +
      `<div class="grm-field"><label>LINE</label><select id="f_line">${lineOptionsHtml(
        t.product_line_id
      )}</select></div>` +
      `<div class="grm-field"><label>PRODUCT MODEL</label><select id="f_type">${modelOptionsHtml(
        t.product_type_id || t.complexity
      )}</select></div>` +
      `<div class="grm-field"><label>KIND</label><select id="f_kind">` +
      `<option value="title" ${
        (t.kind || "title") === "title" ? "selected" : ""
      }>Full title</option>` +
      `<option value="rebrand" ${
        t.kind === "rebrand" ? "selected" : ""
      }>Rebrand</option>` +
      `</select></div>` +
      `<div class="grm-field"><label>LIFECYCLE</label><select id="f_status">` +
      [
        ["planning", "Planning"],
        ["active", "Active"],
        ["scope_change", "Scope change"],
        ["shelved", "Shelved"],
        ["cancelled", "Cancelled"],
      ]
        .map(([v, lab]) => {
          const cur = t.lifecycle || t.status || "planning";
          const sel =
            cur === v ||
            (cur === "planned" && v === "planning") ||
            (cur === "production" && v === "active") ||
            (cur === "done" && v === "active")
              ? "selected"
              : "";
          return `<option value="${v}" ${sel}>${lab}</option>`;
        })
        .join("") +
      `</select></div>` +
      `<p class="grm-muted" style="font-size:0.5rem;margin:0 0 0.4rem">Lifecycle = how the title is being run (not schedule lane). Finished milestones stay on the calendar — no separate Done.</p>` +
      `<input type="hidden" id="f_quarter" value="${esc(
        t.quarter || t.quarter_label || ""
      )}" />` +
      `<div class="grm-pcard-edit-actions">` +
      `<button type="button" class="grm-btn grm-btn-primary grm-btn-sm" id="btnSaveIdentity">Save</button>` +
      `<button type="button" class="grm-btn grm-btn-sm" id="btnCancelIdentity">Cancel</button>` +
      `</div></div></div>` +
      // dossier
      `<div class="grm-pcard-block">` +
      `<div class="grm-ev-head"><strong>DOSSIER</strong>` +
      `<button type="button" class="grm-btn grm-btn-sm" id="btnEditDossier">Edit</button></div>` +
      `<div id="pcDossierView" class="grm-pcard-rows">` +
      rowKV("Theme", theme || "—") +
      rowKV("Math model", math || "—") +
      rowKV("Twin", t.twin_code || "—") +
      rowKV("Notes", t.notes ? String(t.notes).slice(0, 80) : "—") +
      `</div>` +
      `<div id="pcDossierEdit" class="grm-pcard-edit" hidden>` +
      `<div class="grm-field"><label>THEME</label><input id="f_theme" value="${esc(
        theme
      )}" placeholder="TBD" /></div>` +
      `<div class="grm-field"><label>MATH MODEL</label><input id="f_math" value="${esc(
        math
      )}" placeholder="TBD" /></div>` +
      `<div class="grm-field"><label>TWIN</label><select id="f_twin">${twinOptionsHtml(
        t
      )}</select></div>` +
      `<div class="grm-field"><label>NOTES</label><textarea id="f_notes">${esc(
        t.notes || ""
      )}</textarea></div>` +
      `<div class="grm-pcard-edit-actions">` +
      `<button type="button" class="grm-btn grm-btn-primary grm-btn-sm" id="btnSaveDossier">Save</button>` +
      `<button type="button" class="grm-btn grm-btn-sm" id="btnCancelDossier">Cancel</button>` +
      `</div></div></div>` +
      `<div class="grm-pcard-tools">` +
      `<button type="button" class="grm-btn grm-btn-sm" id="btnFillDates" title="Reverse-calc unlocked lines from ship">Fill dates from ship</button>` +
      ((t.kind || "") !== "rebrand"
        ? `<button type="button" class="grm-btn grm-btn-sm" id="btnMakeRebrand">Make BSG rebrand…</button>`
        : "") +
      `<button type="button" class="grm-btn grm-btn-sm" id="btnDelete">Delete</button>` +
      `</div></div>`
    );
  }

  function rowKV(k, v) {
    return (
      `<div class="grm-pcard-row">` +
      `<span class="grm-pcard-k">${esc(k)}</span>` +
      `<span class="grm-pcard-v">${esc(v)}</span>` +
      `</div>`
    );
  }

  function openTitle(id) {
    const t = (state.titles || []).find((x) => x.id === id);
    if (!t) return;
    openId = id;
    // keep Deck Host title bar free for drag
    const chrome = document.querySelector(".grm-chrome");
    if (chrome) {
      document.documentElement.style.setProperty(
        "--grm-chrome-h",
        `${chrome.getBoundingClientRect().height}px`
      );
    }
    $("drawer").hidden = false;
    $("drawerTitle").textContent = t.name || t.code || "Title";
    const phases = (t.phases || [])
      .slice()
      .sort((a, b) => (a.sort || 0) - (b.sort || 0));
    const phaseEv = phases.filter((p) => (p.role || "phase") === "phase");
    const gateEv = phases.filter((p) => (p.role || "") === "gate");
    const twinCode = t.twin_code || t.rebrand_of || t.nucleus_code || "";
    const twin = findByCode(twinCode);

    $("drawerBody").innerHTML =
      productCardHtml(t) +
      (twin
        ? `<button type="button" class="grm-twin-jump" id="btnTwin">Open twin: ${esc(
            twin.code
          )} · ${esc(twin.name)}</button>`
        : "") +
      `<div class="grm-phases"><div class="grm-ev-head"><strong>PHASES</strong>` +
      `<button type="button" class="grm-btn grm-btn-sm" id="btnAddPhase">+ Phase</button></div>` +
      eventListHtml(t, phaseEv, "phase") +
      `</div>` +
      `<div class="grm-phases grm-gates"><div class="grm-ev-head"><strong>GATES</strong>` +
      `<button type="button" class="grm-btn grm-btn-sm" id="btnAddGate">+ Gate</button></div>` +
      eventListHtml(t, gateEv, "gate") +
      `</div>`;

    function showIdentityEdit(on) {
      const v = $("pcIdentityView");
      const e = $("pcIdentityEdit");
      if (v) v.hidden = on;
      if (e) e.hidden = !on;
    }
    function showDossierEdit(on) {
      const v = $("pcDossierView");
      const e = $("pcDossierEdit");
      if (v) v.hidden = on;
      if (e) e.hidden = !on;
    }
    if ($("btnEditIdentity"))
      $("btnEditIdentity").onclick = () => showIdentityEdit(true);
    if ($("btnCancelIdentity"))
      $("btnCancelIdentity").onclick = () => showIdentityEdit(false);
    if ($("btnSaveIdentity"))
      $("btnSaveIdentity").onclick = () => saveOpen();
    if ($("btnEditDossier"))
      $("btnEditDossier").onclick = () => showDossierEdit(true);
    if ($("btnCancelDossier"))
      $("btnCancelDossier").onclick = () => showDossierEdit(false);
    if ($("btnSaveDossier"))
      $("btnSaveDossier").onclick = () => saveOpen();

    $("btnDelete").onclick = () => deleteOpen();
    const fill = $("btnFillDates");
    if (fill) {
      fill.onclick = async () => {
        const rel =
          ($("f_rel") && $("f_rel").value) || t.release_date;
        if (!rel) {
          toast("set ship date first (Edit identity)");
          return;
        }
        const typeId =
          ($("f_type") && $("f_type").value) ||
          t.product_type_id ||
          t.complexity;
        await fetch(`/api/titles/${t.id}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            release_date: rel,
            product_type_id: typeId,
            complexity: typeId,
            kind:
              ($("f_kind") && $("f_kind").value) || t.kind || "title",
          }),
        });
        const unlock = confirm(
          "Overwrite ALL spine dates from ship date?\nOK = unlock and refill everything\nCancel = only fill unlocked / empty slots"
        );
        const r = await fetch(`/api/titles/${t.id}/recompute`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            release_date: rel,
            product_type_id: typeId,
            complexity: typeId,
            unlock_all: unlock,
          }),
        });
        const j = await r.json();
        if (!j.ok) return toast(j.error || "fill failed");
        toast(j.message || "dates filled");
        await refresh();
        openTitle(t.id);
      };
    }
    const jt = $("btnTwin");
    if (jt && twin) jt.onclick = () => openTitle(twin.id);
    const br = $("btnMakeRebrand");
    if (br) {
      br.onclick = async () => {
        const code = prompt("Rebrand code", `BSG-RE-${t.code || "GAME"}`);
        if (code == null) return;
        const name = prompt("Rebrand display name", `${t.name} (BSG)`);
        if (name == null) return;
        const rel = prompt("Betsoft release date YYYY-MM-DD (optional)", "");
        if (rel == null) return;
        const r = await fetch("/api/titles/rebrand", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            from_id: t.id,
            code: String(code).trim(),
            name: String(name).trim(),
            release_date: String(rel).trim(),
          }),
        });
        const j = await r.json();
        if (!j.ok) return toast(j.error || "rebrand failed");
        toast(j.message || "rebrand created");
        await refresh();
        if (j.title) openTitle(j.title.id);
      };
    }
    $("drawerBody").querySelectorAll(".ev-edit").forEach((btn) => {
      btn.onclick = () => editEvent(t, btn.getAttribute("data-eid"));
    });
    $("drawerBody").querySelectorAll(".ev-edit-ws").forEach((btn) => {
      btn.onclick = () =>
        editWorkstream(
          t,
          btn.getAttribute("data-eid"),
          btn.getAttribute("data-wsid")
        );
    });
    $("drawerBody").querySelectorAll(".ev-del").forEach((btn) => {
      btn.onclick = () => removeEvent(t, btn.getAttribute("data-eid"));
    });
    $("drawerBody").querySelectorAll(".ev-assign").forEach((btn) => {
      btn.onclick = () =>
        openAssignModal(
          t,
          btn.getAttribute("data-eid"),
          btn.getAttribute("data-wsid") || ""
        );
    });
    $("drawerBody").querySelectorAll(".ev-unassign").forEach((btn) => {
      btn.onclick = (ev) => {
        ev.stopPropagation();
        unassignFromTitle(t.id, btn.getAttribute("data-aid"));
      };
    });
    $("btnAddPhase").onclick = () => addEvent(t, "phase");
    $("btnAddGate").onclick = () => addEvent(t, "gate");
  }

  function personLoad(personId) {
    const hits = [];
    for (const t of state.titles || []) {
      for (const a of titleAssignments(t)) {
        if (a.person_id === personId) {
          hits.push({ title: t, a });
        }
      }
    }
    return hits;
  }

  function gameTitle(t) {
    const name = String((t && t.name) || "").trim();
    const code = String((t && t.code) || "").trim();
    if (name && code && name.toUpperCase() !== code.toUpperCase()) return name;
    return name || code || "Untitled";
  }

  function parseDay(s) {
    if (!s) return null;
    const d = new Date(String(s).slice(0, 10) + "T00:00:00");
    return Number.isNaN(d.getTime()) ? null : d;
  }

  function decorateAssignmentClient(t, a) {
    if (a && a.work_status && ("gate" in a || "gates" in a)) return a;
    const out = Object.assign({}, a || {});
    const phase = (t.phases || []).find((p) => p.id === out.phase_id) || null;
    const ws =
      phase && out.workstream_id
        ? (phase.workstreams || []).find((w) => w.id === out.workstream_id) ||
          null
        : null;
    const src = ws && (ws.start || ws.end) ? ws : phase;
    const start = parseDay(src && src.start);
    const end = parseDay((src && (src.end || src.start)) || null);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    let status = "unscheduled";
    if (start || end) {
      const s = start || end;
      const e = end || start;
      if (e && e < today) status = "done";
      else if (s && e && s <= today && today <= e) status = "current";
      else if (s && s > today) status = "upcoming";
    }
    const pname = (phase && phase.name) || "";
    const wname = (ws && ws.name) || "";
    const gates = [];
    for (const g of t.phases || []) {
      const role = g.role || (g.kind === "point" ? "gate" : "phase");
      if (role !== "gate") continue;
      const gphase = g.gate_phase_name || "";
      const gws = g.gate_workstream_name || "";
      let hit = false;
      if (gws && wname) hit = gws === wname && (!gphase || gphase === pname);
      else if (gphase) hit = gphase === pname;
      if (!hit && phase && (phase.end || phase.start)) {
        const gd = String(g.start || g.end || "").slice(0, 10);
        const pe = String(phase.end || phase.start || "").slice(0, 10);
        hit = !!(gd && pe && gd === pe);
      }
      if (!hit) continue;
      const gd = parseDay(g.start || g.end);
      gates.push({
        id: g.id || "",
        name: g.name || "Gate",
        date: g.start || g.end || null,
        relation: g.gate_relation || "",
        done: !!(gd && gd < today),
      });
    }
    const pin = gates[0] || null;
    if (
      status !== "done" &&
      pin &&
      pin.done &&
      ["at_end", "after_end", "offset_from_end", ""].includes(pin.relation || "")
    ) {
      status = "done";
    }
    out.start = out.start || (src && src.start) || null;
    out.end = out.end || (src && src.end) || out.start;
    out.work_status = out.work_status || status;
    out.gates = out.gates || gates;
    out.gate = out.gate || pin;
    out.gate_done = out.gate_done != null ? out.gate_done : !!(pin && pin.done);
    return out;
  }

  function workStatusOf(a) {
    return (a && a.work_status) || "unscheduled";
  }

  function workStatusLabel(status) {
    return (
      {
        done: "Done",
        current: "Now",
        upcoming: "Upcoming",
        unscheduled: "No dates",
      }[status] || status || "—"
    );
  }

  function isAssignmentOpen(a) {
    return workStatusOf(a) !== "done";
  }

  function assignmentSlotLabel(a) {
    return a.workstream_name
      ? `${a.phase_name || "phase"} ↳ ${a.workstream_name}`
      : a.phase_name || "phase";
  }

  function allAssignmentRows() {
    const rows = [];
    for (const t of state.titles || []) {
      for (const a of titleAssignments(t)) {
        rows.push({ title: t, a: decorateAssignmentClient(t, a) });
      }
    }
    const rank = { current: 0, upcoming: 1, unscheduled: 2, done: 3 };
    const key = peopleAssignSort || "status";
    const dir = peopleAssignSortDir < 0 ? -1 : 1;
    const cmpStr = (a, b) =>
      String(a || "").localeCompare(String(b || ""), undefined, {
        sensitivity: "base",
      });
    const cmpDay = (a, b) => {
      const as = String(a || "");
      const bs = String(b || "");
      if (!as && !bs) return 0;
      if (!as) return 1;
      if (!bs) return -1;
      return as.localeCompare(bs);
    };
    const tie = (x, y) => {
      const pn = cmpStr(x.a.person_name, y.a.person_name);
      if (pn) return pn;
      const st =
        (rank[workStatusOf(x.a)] ?? 9) - (rank[workStatusOf(y.a)] ?? 9);
      if (st) return st;
      return cmpStr(gameTitle(x.title), gameTitle(y.title));
    };
    rows.sort((x, y) => {
      let d = 0;
      if (key === "staff") d = cmpStr(x.a.person_name, y.a.person_name);
      else if (key === "title") d = cmpStr(gameTitle(x.title), gameTitle(y.title));
      else if (key === "code") d = cmpStr(x.title.code, y.title.code);
      else if (key === "work")
        d = cmpStr(assignmentSlotLabel(x.a), assignmentSlotLabel(y.a));
      else if (key === "role") d = cmpStr(x.a.role, y.a.role);
      else if (key === "window") d = cmpDay(x.a.start || x.a.end, y.a.start || y.a.end);
      else if (key === "gate")
        d = cmpDay(
          (x.a.gate && x.a.gate.date) || "",
          (y.a.gate && y.a.gate.date) || ""
        );
      else
        d =
          (rank[workStatusOf(x.a)] ?? 9) - (rank[workStatusOf(y.a)] ?? 9);
      if (d) return d * dir;
      return tie(x, y);
    });
    return rows;
  }

  function renderPeople() {
    const root = $("viewPeople");
    if (!root) return;
    const people = (state.people || []).slice().sort((a, b) => {
      const aa = a.active === false ? 1 : 0;
      const bb = b.active === false ? 1 : 0;
      if (aa !== bb) return aa - bb;
      return String(a.name || "").localeCompare(String(b.name || ""));
    });
    const roles = state.roles || [];
    const paneNav =
      `<div class="grm-ppl-panes" role="tablist">` +
      `<button type="button" class="grm-qchip ${
        peoplePane === "assignments" ? "is-on" : ""
      }" data-pane="assignments">Assignments</button>` +
      `<button type="button" class="grm-qchip ${
        peoplePane === "roster" ? "is-on" : ""
      }" data-pane="roster">Roster</button>` +
      `</div>`;

    let body = "";
    if (peoplePane === "roster") {
      const rows = people
        .map((p) => {
          const load = personLoad(p.id);
          const openN = load.filter((h) => isAssignmentOpen(h.a)).length;
          const loadLab = load.length
            ? `${openN} open · ${load.length} total`
            : "—";
          return (
            `<tr class="${p.active === false ? "is-inactive" : ""}" data-pid="${esc(
              p.id
            )}">` +
            `<td>${esc(p.name)}</td>` +
            `<td>${esc(p.role || "—")}</td>` +
            `<td class="mono">${p.active === false ? "inactive" : "active"}</td>` +
            `<td class="mono">${esc(loadLab)}</td>` +
            `<td class="grm-vocab-actions">` +
            `<button type="button" class="grm-btn grm-btn-sm btn-ppl-edit" data-id="${esc(
              p.id
            )}">Edit</button>` +
            `<button type="button" class="grm-btn grm-btn-sm btn-ppl-toggle" data-id="${esc(
              p.id
            )}">${p.active === false ? "Activate" : "Park"}</button>` +
            `<button type="button" class="grm-btn grm-btn-sm btn-ppl-del" data-id="${esc(
              p.id
            )}">Remove</button>` +
            `</td></tr>`
          );
        })
        .join("");
      body =
        `<div class="grm-vocab-intro">` +
        `<p><strong>Roster</strong> = who exists in the house. Add names and roles here. Pin them onto a title from the ticket (phase or ↳ workstream) — not from this list.</p>` +
        `<p class="grm-muted">Parked people stay on existing tickets but drop out of the assign picker. Removing someone clears their assignments.</p>` +
        `<form class="grm-ppl-add" id="formAddPerson">` +
        `<input name="name" required placeholder="Name" autocomplete="off" />` +
        `<select name="role">${roleOptionsHtml("")}</select>` +
        `<button type="submit" class="grm-btn grm-btn-primary">+ Person</button>` +
        `</form>` +
        `<form class="grm-ppl-add grm-ppl-role-add" id="formAddRole">` +
        `<input name="name" required placeholder="New house role" autocomplete="off" />` +
        `<button type="submit" class="grm-btn">+ Role</button>` +
        `</form>` +
        (roles.length
          ? `<p class="grm-muted mono spine-list">Roles: ${esc(roles.join(" · "))}</p>`
          : "") +
        `</div>` +
        `<section><h3>Employees (${people.length})</h3>` +
        `<div class="grm-table-wrap"><table class="grm-table grm-ppl-table"><thead><tr>` +
        `<th>Name</th><th>Role</th><th>Status</th><th>Load</th><th></th>` +
        `</tr></thead><tbody>` +
        (rows ||
          `<tr><td colspan="5" class="grm-muted">No people yet — add a name above.</td></tr>`) +
        `</tbody></table></div></section>`;
    } else {
      const all = allAssignmentRows();
      const filtered = all.filter((h) => {
        const done = !isAssignmentOpen(h.a);
        if (peopleAssignFilter === "open") return !done;
        if (peopleAssignFilter === "done") return done;
        return true;
      });
      const openN = all.filter((h) => isAssignmentOpen(h.a)).length;
      const doneN = all.length - openN;
      const filt =
        `<div class="grm-ppl-filters">` +
        [
          ["open", `Open (${openN})`],
          ["done", `Done (${doneN})`],
          ["all", `All (${all.length})`],
        ]
          .map(
            ([k, lab]) =>
              `<button type="button" class="grm-qchip ${
                peopleAssignFilter === k ? "is-on" : ""
              }" data-asg-filter="${k}">${esc(lab)}</button>`
          )
          .join("") +
        `</div>`;
      const rows = filtered
        .map((h) => {
          const a = h.a;
          const t = h.title;
          const slot = assignmentSlotLabel(a);
          const st = workStatusOf(a);
          const g = a.gate;
          let gateHtml = `<span class="grm-muted">—</span>`;
          if (g && g.name) {
            const gdone = !!g.done;
            gateHtml =
              `<span class="grm-badge life-${gdone ? "done" : "open"}" title="${esc(
                g.name
              )}">` +
              `${gdone ? "Gate passed" : "Gate open"}</span>` +
              `<span class="grm-ppl-gate-name">${esc(g.name)}` +
              (g.date ? ` · ${esc(g.date)}` : "") +
              `</span>`;
          }
          const window =
            a.start || a.end
              ? `${a.start || "?"} → ${a.end || a.start}`
              : "—";
          return (
            `<tr class="grm-asg-row asg-${esc(st)}" data-tid="${esc(t.id)}">` +
            `<td>${esc(a.person_name || "—")}</td>` +
            `<td>${esc(gameTitle(t))}</td>` +
            `<td class="mono">${esc(t.code || "—")}</td>` +
            `<td>${esc(slot)}</td>` +
            `<td class="grm-muted">${esc(a.role || "—")}</td>` +
            `<td class="mono">${esc(window)}</td>` +
            `<td><span class="grm-badge asg-${esc(st)}">${esc(
              workStatusLabel(st)
            )}</span></td>` +
            `<td class="grm-ppl-gate">${gateHtml}</td>` +
            `</tr>`
          );
        })
        .join("");
      body =
        `<div class="grm-vocab-intro">` +
        `<p><strong>Assignments</strong> = who is on which game, by phase (or ↳ stream). Game title is the working name. Done = the window ended, or the phase-end gate already passed.</p>` +
        `<p class="grm-muted">Add or park people on the Roster pane. Assign from a title ticket. Click a column header to sort — Staff groups by person, Status is the upcoming order.</p>` +
        filt +
        `</div>` +
        `<div class="grm-table-wrap"><table class="grm-table grm-asg-table"><thead><tr>` +
        [
          ["staff", "Staff"],
          ["title", "Title"],
          ["code", "Code"],
          ["work", "Work"],
          ["role", "Role"],
          ["window", "Window"],
          ["status", "Status"],
          ["gate", "Gate"],
        ]
          .map(([k, lab]) => {
            const on = peopleAssignSort === k;
            const mark = on ? (peopleAssignSortDir < 0 ? " ▾" : " ▴") : "";
            return `<th><button type="button" class="grm-th-sort ${
              on ? "is-on" : ""
            }" data-sort="${k}">${esc(lab)}${mark}</button></th>`;
          })
          .join("") +
        `</tr></thead><tbody>` +
        (rows ||
          `<tr><td colspan="8" class="grm-muted">${
            all.length
              ? "Nothing in this filter."
              : "Nobody pinned yet. Open a title and use + Crew."
          }</td></tr>`) +
        `</tbody></table></div>`;
    }

    root.innerHTML =
      `<div class="grm-vocab grm-people">` + paneNav + body + `</div>`;

    root.querySelectorAll("[data-pane]").forEach((btn) => {
      btn.onclick = () => {
        peoplePane = btn.getAttribute("data-pane") || "assignments";
        renderPeople();
      };
    });
    root.querySelectorAll("[data-asg-filter]").forEach((btn) => {
      btn.onclick = () => {
        peopleAssignFilter = btn.getAttribute("data-asg-filter") || "open";
        renderPeople();
      };
    });
    root.querySelectorAll(".grm-th-sort").forEach((btn) => {
      btn.onclick = (ev) => {
        ev.stopPropagation();
        const key = btn.getAttribute("data-sort") || "status";
        if (peopleAssignSort === key) peopleAssignSortDir *= -1;
        else {
          peopleAssignSort = key;
          peopleAssignSortDir = 1;
        }
        renderPeople();
      };
    });
    root.querySelectorAll(".grm-asg-row").forEach((tr) => {
      tr.addEventListener("click", () => openTitle(tr.getAttribute("data-tid")));
    });

    const add = $("formAddPerson");
    if (add) {
      add.onsubmit = async (e) => {
        e.preventDefault();
        const fd = new FormData(add);
        const name = String(fd.get("name") || "").trim();
        const role = String(fd.get("role") || "").trim();
        if (!name) return;
        const r = await fetch("/api/people", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, role }),
        });
        const j = await r.json();
        if (!j.ok) return toast(j.error || "add failed");
        toast(j.message || "added");
        await refresh();
      };
    }
    const addRole = $("formAddRole");
    if (addRole) {
      addRole.onsubmit = async (e) => {
        e.preventDefault();
        const fd = new FormData(addRole);
        const name = String(fd.get("name") || "").trim();
        if (!name) return;
        const r = await fetch("/api/roles", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name }),
        });
        const j = await r.json();
        if (!j.ok) return toast(j.error || "role failed");
        toast(j.message || "role saved");
        await refresh();
      };
    }
    root.querySelectorAll(".btn-ppl-edit").forEach((btn) => {
      btn.onclick = async () => {
        const p = personById(btn.getAttribute("data-id"));
        if (!p) return;
        const name = prompt("Name", p.name || "");
        if (name == null || !String(name).trim()) return;
        const role = prompt("House role", p.role || "");
        if (role == null) return;
        const r = await fetch("/api/people/update", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            id: p.id,
            name: String(name).trim(),
            role: String(role).trim(),
          }),
        });
        const j = await r.json();
        if (!j.ok) return toast(j.error || "save failed");
        toast("saved");
        await refresh();
      };
    });
    root.querySelectorAll(".btn-ppl-toggle").forEach((btn) => {
      btn.onclick = async () => {
        const p = personById(btn.getAttribute("data-id"));
        if (!p) return;
        const r = await fetch("/api/people/update", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: p.id, active: p.active === false }),
        });
        const j = await r.json();
        if (!j.ok) return toast(j.error || "save failed");
        toast(p.active === false ? "active" : "parked");
        await refresh();
      };
    });
    root.querySelectorAll(".btn-ppl-del").forEach((btn) => {
      btn.onclick = async () => {
        const p = personById(btn.getAttribute("data-id"));
        if (!p) return;
        if (!confirm(`Remove ${p.name} from the roster? Assignments will be cleared.`))
          return;
        const r = await fetch("/api/people/delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: p.id }),
        });
        const j = await r.json();
        if (!j.ok) return toast(j.error || "remove failed");
        toast(j.message || "removed");
        await refresh();
      };
    });
    root.querySelectorAll(".grm-ppl-hit").forEach((btn) => {
      btn.onclick = () => openTitle(btn.getAttribute("data-tid"));
    });
  }

  function closeAssignModal() {
    const m = $("modalAssign");
    if (m) m.hidden = true;
  }

  function openAssignModal(t, phaseId, wsId) {
    const phase = (t.phases || []).find((p) => p.id === phaseId);
    if (!phase) return toast("phase not found");
    const streams = (phase.workstreams || []).filter((w) => w && w.id);
    const people = (state.people || []).filter((p) => p.active !== false);
    if (!people.length) {
      toast("add people on People → Roster first");
      return;
    }
    $("as_title_id").value = t.id;
    $("as_phase_id").value = phase.id;
    const hint = $("modalAssignHint");
    const titleEl = $("modalAssignTitle");
    titleEl.textContent = "Assign person";
    hint.textContent = `Pin someone onto “${phase.name}”${
      wsId ? " workstream" : ""
    }. House roster · People tab.`;

    const already = new Set(
      titleAssignments(t)
        .filter((a) => a.phase_id === phase.id && (a.workstream_id || "") === (wsId || ""))
        .map((a) => a.person_id)
    );
    const sel = $("as_person");
    sel.innerHTML = people
      .map((p) => {
        const taken = already.has(p.id) ? " (already on this slot)" : "";
        return `<option value="${esc(p.id)}" ${taken ? "disabled" : ""}>${esc(
          p.name
        )}${p.role ? " · " + esc(p.role) : ""}${taken}</option>`;
      })
      .join("");
    const firstFree = people.find((p) => !already.has(p.id));
    if (firstFree) sel.value = firstFree.id;
    if (!firstFree) {
      toast("everyone active is already on this slot");
      return;
    }

    const wsWrap = $("as_ws_wrap");
    const wsSel = $("as_workstream");
    if (streams.length) {
      wsWrap.hidden = false;
      wsSel.innerHTML =
        `<option value="">Whole phase</option>` +
        streams
          .map(
            (w) =>
              `<option value="${esc(w.id)}" ${w.id === wsId ? "selected" : ""}>${esc(
                w.name
              )}</option>`
          )
          .join("");
      if (wsId) wsSel.value = wsId;
    } else {
      wsWrap.hidden = true;
      wsSel.innerHTML = `<option value="">Whole phase</option>`;
    }

    const picked = personById(sel.value);
    $("as_role").innerHTML = roleOptionsHtml(picked ? picked.role : "");
    sel.onchange = () => {
      const p = personById(sel.value);
      $("as_role").innerHTML = roleOptionsHtml(p ? p.role : "");
    };

    $("modalAssign").hidden = false;
    setTimeout(() => sel.focus(), 30);
  }

  async function submitAssignModal(e) {
    e.preventDefault();
    const tid = $("as_title_id").value;
    const phaseId = $("as_phase_id").value;
    const personId = $("as_person").value;
    const wsId = ($("as_workstream") && $("as_workstream").value) || "";
    const role = ($("as_role") && $("as_role").value) || "";
    if (!personId) return toast("pick a person");
    const r = await fetch(`/api/titles/${tid}/assign`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        person_id: personId,
        phase_id: phaseId,
        workstream_id: wsId,
        role,
      }),
    });
    const j = await r.json();
    if (!j.ok) return toast(j.error || "assign failed");
    closeAssignModal();
    toast(j.message || "assigned");
    await refresh();
    openTitle(tid);
  }

  async function unassignFromTitle(tid, aid) {
    if (!aid) return;
    const r = await fetch(`/api/titles/${tid}/unassign`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: aid }),
    });
    const j = await r.json();
    if (!j.ok) return toast(j.error || "unassign failed");
    toast(j.message || "unassigned");
    await refresh();
    openTitle(tid);
  }

  function renderVocab() {
    const phases = (vocab || []).filter((v) => v.role === "phase");
    const gates = (vocab || []).filter((v) => v.role === "gate");
    const row = (v) =>
      `<tr data-name="${esc(v.name)}">` +
      `<td class="mono">${esc(v.name)}</td>` +
      `<td><span class="grm-badge role-${esc(v.role)}">${esc(v.role)}</span></td>` +
      `<td class="mono">${v.count}</td>` +
      `<td class="grm-vocab-actions">` +
      `<button type="button" class="grm-btn grm-btn-sm btn-rename" data-name="${esc(v.name)}">Rename all</button>` +
      `<button type="button" class="grm-btn grm-btn-sm btn-flip" data-name="${esc(v.name)}" data-role="${esc(v.role === "phase" ? "gate" : "phase")}">→ ${v.role === "phase" ? "gate" : "phase"}</button>` +
      `</td></tr>`;

    const spine = state.spine || [];
    $("viewVocab").innerHTML =
      `<div class="grm-vocab">` +
      `<div class="grm-vocab-intro">` +
      `<p><strong>House spine</strong> = the shared phase bins every primary title maps onto. Align puts each title on that ordered skeleton; off-spine leftovers stay marked; missing slots stay empty for you to fill.</p>` +
      `<p class="grm-muted"><strong>Phase</strong> = multi-day work. <strong>Gate</strong> = one-shot handoff. Rename is always global. Title notes = one game only.</p>` +
      `<div class="grm-vocab-btns">` +
      `<button type="button" class="grm-btn" id="btnCleanupLabels">1 · Normalize phase labels</button>` +
      `<button type="button" class="grm-btn grm-btn-primary" id="btnAlignSpine">2 · Align all titles to spine</button>` +
      `</div>` +
      (spine.length
        ? `<p class="grm-muted mono spine-list">Spine: ${esc(
            spine.map((s) => s.name).join(" → ")
          )}</p>`
        : "") +
      `</div>` +
      `<div class="grm-vocab-cols">` +
      `<section><h3>Phases in use (${phases.length})</h3>` +
      `<table class="grm-table"><thead><tr><th>Label</th><th>Role</th><th>#</th><th></th></tr></thead><tbody>` +
      (phases.map(row).join("") || '<tr><td colspan="4" class="grm-muted">Clean + align</td></tr>') +
      `</tbody></table></section>` +
      `<section><h3>Gates in use (${gates.length})</h3>` +
      `<table class="grm-table"><thead><tr><th>Label</th><th>Role</th><th>#</th><th></th></tr></thead><tbody>` +
      (gates.map(row).join("") || '<tr><td colspan="4" class="grm-muted">Clean + align</td></tr>') +
      `</tbody></table></section>` +
      `</div></div>`;

    const clean = $("btnCleanupLabels");
    if (clean) {
      clean.onclick = async () => {
        const r = await fetch("/api/vocab/cleanup", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}",
        });
        const j = await r.json();
        toast(j.message || "cleaned");
        await refresh();
      };
    }
    const align = $("btnAlignSpine");
    if (align) {
      align.onclick = async () => {
        const r = await fetch("/api/vocab/align-spine", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ fill_missing: true }),
        });
        const j = await r.json();
        toast(j.message || "aligned");
        await refresh();
      };
    }
    $("viewVocab").querySelectorAll(".btn-rename").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const from = btn.getAttribute("data-name") || "";
        const to = prompt(
          `Rename “${from}” on ALL titles that use it:`,
          from
        );
        if (to == null || !String(to).trim() || String(to).trim() == from) return;
        const r = await fetch("/api/vocab/rename", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ from, to: String(to).trim() }),
        });
        const j = await r.json();
        toast(j.message || `changed ${j.changed}`);
        await refresh();
      });
    });
    $("viewVocab").querySelectorAll(".btn-flip").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const name = btn.getAttribute("data-name") || "";
        const role = btn.getAttribute("data-role") || "phase";
        const r = await fetch("/api/vocab/set-role", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, role }),
        });
        const j = await r.json();
        toast(j.message || "role updated");
        await refresh();
      });
    });
  }

  function normalizeCx(c) {
    c = (c || "medium").toLowerCase();
    if (c === "standard") return "medium";
    if (c === "simple") return "math_clone";
    return c;
  }

  async function saveOpen() {
    if (!openId) return;
    const cur = (state.titles || []).find((x) => x.id === openId) || {};
    const twinVal =
      ($("f_twin") && $("f_twin").value) != null
        ? $("f_twin").value
        : cur.twin_code || "";
    const kindVal =
      ($("f_kind") && $("f_kind").value) || cur.kind || "title";
    const typeId =
      ($("f_type") && $("f_type").value) || cur.product_type_id || cur.complexity;
    const ship =
      ($("f_rel") && $("f_rel").value) || cur.release_date || "";
    let quarter = ($("f_quarter") && $("f_quarter").value) || "";
    // if operator left quarter blank, follow ship (board filter only — not shown on card)
    if (!String(quarter).trim() && ship) {
      quarter = quarterFromShip(ship);
    }
    const body = {
      code: ($("f_code") && $("f_code").value) || cur.code || "",
      name: ($("f_name") && $("f_name").value) || cur.name || "",
      theme:
        ($("f_theme") && $("f_theme").value) != null
          ? $("f_theme").value
          : cur.theme || "",
      math_model:
        ($("f_math") && $("f_math").value) != null
          ? $("f_math").value
          : cur.math_model || "",
      quarter,
      product_line_id:
        ($("f_line") && $("f_line").value) || cur.product_line_id || "",
      kind: kindVal,
      product_type_id: typeId,
      complexity: typeId,
      release_date: ship,
      twin_code: twinVal,
      rebrand_of: kindVal === "rebrand" ? twinVal : cur.rebrand_of || "",
      nucleus_code: kindVal === "rebrand" ? twinVal : cur.nucleus_code || "",
      status:
        ($("f_status") && $("f_status").value) || cur.status || "planned",
      notes:
        ($("f_notes") && $("f_notes").value) != null
          ? $("f_notes").value
          : cur.notes || "",
    };
    const r = await fetch(`/api/titles/${openId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const j = await r.json();
    if (!j.ok) return toast(j.error || "save failed");
    toast("saved");
    await refresh();
    openTitle(openId);
  }

  async function recomputeOpen(unlock) {
    if (!openId) return;
    const t = (state.titles || []).find((x) => x.id === openId);
    // rebrands: re-mint thin phases via save kind+release
    if (t && t.kind === "rebrand") {
      toast("rebrand: edit dates in list or clear phases then set release");
    }
    const typeId =
      ($("f_type") && $("f_type").value) ||
      (t && (t.product_type_id || t.complexity)) ||
      "";
    const body = {
      release_date: $("f_rel").value,
      product_type_id: typeId,
      complexity: typeId,
      unlock_all: !!unlock,
    };
    const r = await fetch(`/api/titles/${openId}/recompute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const j = await r.json();
    if (!j.ok) return toast(j.error || "recompute failed");
    toast(unlock ? "unlocked + recomputed" : "recomputed from release");
    await refresh();
    openTitle(openId);
  }

  async function deleteOpen() {
    if (!openId) return;
    if (!confirm("Delete this title?")) return;
    await fetch(`/api/titles/${openId}`, { method: "DELETE" });
    openId = null;
    $("drawer").hidden = true;
    toast("deleted");
    await refresh();
  }

  async function refresh() {
    const r = await fetch("/api/state", { cache: "no-store" });
    const j = await r.json();
    if (!j.ok) throw new Error("state fail");
    state = j;
    vocab = j.vocab || [];
    const fl = $("filterLine");
    const cur = fl.value;
    fl.innerHTML =
      `<option value="">All lines</option>` +
      (state.product_lines || [])
        .map((L) => `<option value="${esc(L.id)}">${esc(L.name)}</option>`)
        .join("");
    fl.value = cur;
    const nl = $("newLine");
    if (nl) {
      nl.innerHTML = (state.product_lines || [])
        .map((L) => `<option value="${esc(L.id)}">${esc(L.name)}</option>`)
        .join("");
    }
    fillBucketFilter();
    fillProductTypeSelects();
    renderQuarterChips();
    render();
  }

  initTheme();
  loadGanttCollapsed();
  if ($("btnTheme")) {
    $("btnTheme").onclick = () => {
      const next = document.body.classList.contains("theme-light")
        ? "dark"
        : "light";
      applyTheme(next);
    };
  }

  $("tabBoard").onclick = () => setView("board");
  $("tabList").onclick = () => setView("list");
  if ($("tabGantt")) $("tabGantt").onclick = () => setView("gantt");
  $("tabQuarters").onclick = () => setView("quarters");
  $("tabVocab").onclick = () => setView("vocab");
  if ($("tabPeople")) $("tabPeople").onclick = () => setView("people");
  if ($("tabConfig")) $("tabConfig").onclick = () => setView("config");
  $("filterLine").onchange = render;
  $("filterBucket").onchange = render;
  if ($("filterLifecycle")) $("filterLifecycle").onchange = render;
  $("btnCloseDrawer").onclick = () => {
    $("drawer").hidden = true;
    openId = null;
  };

  $("btnNew").onclick = () => {
    fillProductTypeSelects();
    updateNewQuarterHint();
    $("modalNew").hidden = false;
  };
  $("btnCancelNew").onclick = () => {
    $("modalNew").hidden = true;
  };
  if ($("btnCancelEvent")) {
    $("btnCancelEvent").onclick = () => closeEventModal();
  }
  if ($("formEvent")) {
    $("formEvent").onsubmit = submitEventModal;
  }
  if ($("btnCancelAssign")) {
    $("btnCancelAssign").onclick = () => closeAssignModal();
  }
  if ($("formAssign")) {
    $("formAssign").onsubmit = submitAssignModal;
  }
  // click backdrop to close event modal
  if ($("modalEvent")) {
    $("modalEvent").addEventListener("click", (ev) => {
      if (ev.target === $("modalEvent")) closeEventModal();
    });
  }
  if ($("modalAssign")) {
    $("modalAssign").addEventListener("click", (ev) => {
      if (ev.target === $("modalAssign")) closeAssignModal();
    });
  }
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && $("modalEvent") && !$("modalEvent").hidden) {
      closeEventModal();
    }
    if (ev.key === "Escape" && $("modalAssign") && !$("modalAssign").hidden) {
      closeAssignModal();
    }
  });
  if ($("newShip")) {
    $("newShip").addEventListener("input", updateNewQuarterHint);
    $("newShip").addEventListener("change", updateNewQuarterHint);
  }

  $("formNew").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const body = Object.fromEntries(fd.entries());
    // quarter is derived server-side from ship; don't send empty theme/math noise
    delete body.theme;
    delete body.math_model;
    delete body.quarter;
    const code = String(body.code || "").trim();
    if (!code) {
      toast("code required");
      return;
    }
    body.code = code;
    body.name = String(body.name || "").trim() || code;
    const r = await fetch("/api/titles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const j = await r.json();
    if (!j.ok) return toast(j.error || "create failed");
    $("modalNew").hidden = true;
    e.target.reset();
    updateNewQuarterHint();
    toast(
      body.release_date ? "created · scheduled from ship" : "created · unscheduled"
    );
    await refresh();
    if (j.title) openTitle(j.title.id);
  };

  // bulk seed disabled — clean surface only
  if ($("btnSeed")) {
    $("btnSeed").textContent = "Clean board";
    $("btnSeed").title = "Bulk import is buried. Use + Title.";
    $("btnSeed").onclick = () =>
      toast("Import mausoleum only. Use + Title for DOS spine.");
  }

  refresh()
    .then(() => setView("list"))
    .catch((e) => {
      console.error(e);
      $("viewList").innerHTML =
        '<div class="grm-empty">Could not load board.</div>';
    });
})();

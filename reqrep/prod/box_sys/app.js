/* ReqRep · CO.BBC-002-RR · dense production bay · work-order tickets */
(() => {
  const state = {
    listInbox: null,
    agentInbox: null,
    inboxBoardOpen: false,
    cases: [],
    case: null,
    view: "list",
    role: localStorage.getItem("reqrep.role") || "hands",
    theme: localStorage.getItem("reqrep.theme") || "dark",
    openThreads: {},
    editIntake: false,
    editScope: false,
    editPrep: false,
    purposeOpen: false,
    /** null = view all tickets */
    focusTicketId: null,
    hideSealed: localStorage.getItem("reqrep.hideSealed") === "1",
    /** ticket body drawer open (default collapsed · header bar) */
    bodyOpen: {},
    /** in-memory drafts while UI re-renders (BUG30) */
    drafts: { chunkBodies: {}, compose: {}, newChunkBody: "", newTicketKind: "IDA" },
  };

  const DRAFT_LS = "reqrep.drafts.v1";

  const $ = (id) => document.getElementById(id);
  const pageTitle = $("pageTitle");
  const metaCount = $("metaCount");
  const viewList = $("viewList");
  const viewCase = $("viewCase");
  const btnBack = $("btnBack");
  const btnNew = $("btnNew");
  const btnTheme = $("btnTheme");
  const roleSelect = $("roleSelect");
  const modalNew = $("modalNew");
  const formNew = $("formNew");
  const toastEl = $("toast");

  const LANE_LABEL = {
    discussion: "DISCUSSION",
    paused: "PAUSED",
    run: "RUN",
    test: "TEST",
    closed: "CLOSED",
    // legacy
    in: "CLOSED",
    run_test: "RUN",
  };
  const LANE_ORDER = ["discussion", "paused", "run", "test", "closed"];
  const KIND_LABEL = { IDA: "IDA", BUG: "BUG", CHG: "CHG" };

  function toast(msg, err) {
    toastEl.textContent = msg;
    toastEl.classList.toggle("is-err", !!err);
    toastEl.hidden = false;
    clearTimeout(toastEl._t);
    toastEl._t = setTimeout(() => {
      toastEl.hidden = true;
    }, 2400);
  }

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /** Preserve real newlines + literal \n / \r\n typed in tickets (BUG18) */
  function normalizeNewlines(s) {
    let t = String(s ?? "");
    t = t.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    t = t.replace(/\\r\\n/g, "\n").replace(/\\n/g, "\n").replace(/\\r/g, "\n");
    return t;
  }

  function formatBody(s) {
    return esc(normalizeNewlines(s));
  }

  /**
   * CHG21 — light markup for display:
   * ``` fenced blocks ``` and `inline code`
   */
  function formatRich(s) {
    const t = normalizeNewlines(s);
    const blocks = [];
    let i = 0;
    const fenceRe = /```([a-zA-Z0-9_+.-]*)\n?([\s\S]*?)```/g;
    let last = 0;
    let m;
    const segs = [];
    while ((m = fenceRe.exec(t)) !== null) {
      if (m.index > last) segs.push({ type: "text", v: t.slice(last, m.index) });
      segs.push({ type: "fence", lang: m[1] || "", v: m[2] });
      last = m.index + m[0].length;
    }
    if (last < t.length) segs.push({ type: "text", v: t.slice(last) });
    if (!segs.length) segs.push({ type: "text", v: t });

    function inlineCode(htmlEscapedAlready) {
      // operate on raw then escape: better process raw text
      return htmlEscapedAlready;
    }

    function formatTextSeg(raw) {
      // escape then restore inline `code`
      const parts = [];
      const re = /`([^`\n]+)`/g;
      let li = 0;
      let mm;
      let out = "";
      while ((mm = re.exec(raw)) !== null) {
        out += esc(raw.slice(li, mm.index));
        out += `<code class="rr-code-inline">${esc(mm[1])}</code>`;
        li = mm.index + mm[0].length;
      }
      out += esc(raw.slice(li));
      // newlines → already pre-wrap on container; keep \n as-is in HTML
      return out;
    }

    return segs
      .map((seg) => {
        if (seg.type === "fence") {
          const lang = seg.lang ? ` data-lang="${esc(seg.lang)}"` : "";
          return `<pre class="rr-code-block"${lang}><code>${esc(seg.v.replace(/\n$/, ""))}</code></pre>`;
        }
        return formatTextSeg(seg.v);
      })
      .join("");
  }

  /** In-ROM modal — never window.prompt / confirm */
  function romDialog(opts) {
    const root = $("romDialog");
    const titleEl = $("romDialogTitle");
    const bodyEl = $("romDialogBody");
    const btnOk = $("romDialogOk");
    const btnCancel = $("romDialogCancel");
    const btnAlt = $("romDialogAlt");
    if (!root || !titleEl || !bodyEl) return Promise.resolve(null);

    titleEl.textContent = opts.title || "Confirm";
    bodyEl.innerHTML = opts.bodyHtml || "";
    btnOk.textContent = opts.okLabel || "OK";
    btnCancel.textContent = opts.cancelLabel || "Cancel";
    btnCancel.hidden = !!opts.hideCancel;
    if (btnAlt) {
      if (opts.altLabel) {
        btnAlt.hidden = false;
        btnAlt.textContent = opts.altLabel;
      } else {
        btnAlt.hidden = true;
      }
    }
    root.hidden = false;

    return new Promise((resolve) => {
      const done = (val) => {
        root.hidden = true;
        btnOk.onclick = null;
        btnCancel.onclick = null;
        if (btnAlt) btnAlt.onclick = null;
        root.onkeydown = null;
        resolve(val);
      };
      btnCancel.onclick = () => done(null);
      btnOk.onclick = () => {
        if (typeof opts.collect === "function") done(opts.collect(bodyEl, "ok"));
        else done(true);
      };
      if (btnAlt && opts.altLabel) {
        btnAlt.onclick = () => {
          if (typeof opts.collect === "function") done(opts.collect(bodyEl, "alt"));
          else done({ alt: true });
        };
      }
      root.onkeydown = (ev) => {
        if (ev.key === "Escape") {
          ev.preventDefault();
          done(null);
        }
      };
      const focusable = bodyEl.querySelector("input, select, textarea, button");
      setTimeout(() => (focusable || btnOk).focus(), 0);
    });
  }

  function romConfirm(title, message, okLabel) {
    return romDialog({
      title,
      bodyHtml: `<p class="rr-dialog-msg">${esc(message)}</p>`,
      okLabel: okLabel || "OK",
    }).then((v) => !!v);
  }

  function romStampDialog(ref, defaults) {
    const lane = (defaults && defaults.work_lane) || "discussion";
    const note = (defaults && defaults.note) || "";
    return romDialog({
      title: `HAND STAMP · ${ref}`,
      okLabel: "Seal ticket",
      altLabel: "Lane only",
      bodyHtml: `
        <label>Note (optional for lane-only)
          <input id="dlgStampNote" value="${esc(note)}" placeholder="AGREED / IMPLEMENTED / running…" autocomplete="off" />
        </label>
        <label>Work lane
          <select id="dlgStampLane">
            <option value="discussion" ${lane === "discussion" ? "selected" : ""}>DISCUSSION</option>
            <option value="paused" ${lane === "paused" ? "selected" : ""}>PAUSED</option>
            <option value="run" ${lane === "run" || lane === "run_test" ? "selected" : ""}>RUN</option>
            <option value="test" ${lane === "test" ? "selected" : ""}>TEST</option>
            <option value="closed" ${lane === "closed" || lane === "in" ? "selected" : ""}>CLOSED</option>
          </select>
        </label>
        <p class="rr-hint"><strong>Seal ticket</strong> stamps done. <strong>Lane only</strong> moves DISCUSSION · PAUSED · RUN · TEST · CLOSED — not an approval. RUN = agent work; TEST = Hands QA; CLOSED = done for agent (was IN).</p>
      `,
      collect: (body, which) => ({
        seal: which !== "alt",
        note: ((body.querySelector("#dlgStampNote") || {}).value || "").trim(),
        work_lane: (body.querySelector("#dlgStampLane") || {}).value || "discussion",
      }),
    });
  }

  async function api(path, opts = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
      ...opts,
    });
    let data = null;
    try {
      data = await res.json();
    } catch {
      data = {};
    }
    if (!res.ok) {
      const err = new Error((data && data.error) || res.statusText || "request failed");
      err.status = res.status;
      throw err;
    }
    return data;
  }

  function applyTheme() {
    document.body.classList.toggle("theme-light", state.theme === "light");
    btnTheme.textContent = state.theme === "light" ? "Dark" : "Light";
  }

  function statusLabel(s) {
    const m = {
      discussing: "discuss",
      scope_locked: "scope lock",
      prep_draft: "prep",
      signed: "signed",
      building: "build",
      done: "done",
      parked: "park",
    };
    return m[s] || s || "—";
  }

  function displayTitle(c) {
    if (c && c.title) return c.title;
    const kind = String((c && c.req_type) || "REQ").toUpperCase();
    const sku = (c && c.sku) || "";
    const name = (c && c.product_name) || "";
    if (sku && name) return `${kind}: ROM SKU ${sku} "${name}"`;
    if (sku) return `${kind}: ROM SKU ${sku}`;
    if (name) return `${kind}: "${name}"`;
    return kind;
  }

  function liveTitlePreview(kind, sku, name) {
    return displayTitle({ req_type: kind, sku, product_name: name, title: "" });
  }

  function kvRow(label, value) {
    const v = String(value ?? "").trim();
    return `<div class="rr-kv">
      <span class="rr-kv-k">${esc(label)}</span>
      <span class="rr-kv-v">${v ? esc(v) : "—"}</span>
    </div>`;
  }

  function ticketSnippet(body) {
    const t = String(body || "").replace(/\s+/g, " ").trim();
    return t.length > 72 ? t.slice(0, 70) + "…" : t;
  }

  function stampWhen(ch) {
    if (!ch.closed_at) return "";
    return new Date(ch.closed_at * 1000).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function caseHashId() {
    const m = (location.hash || "").match(/^#case\/([^/?#]+)/);
    return m ? decodeURIComponent(m[1]) : null;
  }

  function setCaseHash(id) {
    const next = id ? `#case/${encodeURIComponent(id)}` : "#";
    if ((location.hash || "#") === next || (location.hash === "" && next === "#")) return;
    history.replaceState(null, "", next === "#" ? location.pathname + location.search : next);
  }

  const SCROLL_KEY = "reqrep.caseScroll";
  function mainEl() {
    return document.querySelector(".rr-main");
  }
  function saveCaseScroll() {
    if (!state.case) return;
    const main = mainEl();
    if (!main) return;
    try {
      sessionStorage.setItem(
        SCROLL_KEY,
        JSON.stringify({ id: state.case.id, y: main.scrollTop || 0 })
      );
    } catch {
      /* */
    }
  }
  function restoreCaseScroll() {
    if (!state.case) return;
    let y = 0;
    try {
      const o = JSON.parse(sessionStorage.getItem(SCROLL_KEY) || "null");
      if (!o || o.id !== state.case.id) return;
      y = Number(o.y) || 0;
    } catch {
      return;
    }
    const apply = () => {
      const main = mainEl();
      if (main) main.scrollTop = y;
    };
    requestAnimationFrame(() => {
      apply();
      requestAnimationFrame(apply);
    });
  }

  function setView(name) {
    state.view = name;
    viewList.classList.toggle("is-on", name === "list");
    viewCase.classList.toggle("is-on", name === "case");
    btnBack.hidden = name !== "case";
    btnNew.hidden = name === "case";
    if (name === "list") {
      pageTitle.textContent = "Request bay";
      metaCount.textContent = state.cases.length
        ? `${state.cases.length} req`
        : "empty";
    }
  }

  async function loadList(opts = {}) {
    const data = await api("/api/cases");
    state.cases = data.cases || [];
    state.listInbox = data.inbox || null;
    if (!opts.keepCase) renderList();
  }

  async function loadAgentInboxFull() {
    try {
      state.agentInbox = await api("/api/agent-inbox");
    } catch (e) {
      state.agentInbox = null;
      toast(e.message || "inbox fail", true);
    }
  }

  function renderList() {
    state.case = null;
    setCaseHash(null);
    setView("list");
    if (!state.cases.length) {
      viewList.innerHTML =
        '<div class="rr-empty">No requests. <strong>+ REQ</strong> opens a bay.</div>';
      return;
    }
    const counts = (state.listInbox && state.listInbox.counts) || {};
    const openTotal = (state.listInbox && state.listInbox.open_total) || 0;
    const actionN = (state.listInbox && state.listInbox.action_now_n) || 0;
    const qaN = (state.listInbox && state.listInbox.awaiting_qa_n) || 0;
    const laterN = (state.listInbox && state.listInbox.later_n) || 0;
    const showBoard = state.inboxBoardOpen && state.agentInbox;
    function inboxRow(t, later) {
      return `
        <button type="button" class="rr-inbox-row ${later ? "is-later" : "is-action"}" data-case="${esc(t.case_id)}" data-chunk="${esc(t.chunk_id)}" title="${esc(t.case_title || "")}">
          <span class="rr-inbox-ref">${esc(t.ref)}</span>
          <span class="rr-badge is-${esc(String(t.work_lane || "").replace(/_/g, "-"))}">${esc(LANE_LABEL[t.work_lane] || t.work_lane)}</span>
          ${later ? "" : `<span class="rr-badge is-${esc((t.priority || "").toLowerCase())}">${esc(t.priority || "")}</span>`}
          <span class="rr-inbox-peek">${esc(t.peek || "")}</span>
        </button>`;
    }
    const boardRows = showBoard
      ? ((state.agentInbox.action_now || []).length
          ? `<div class="rr-inbox-sec">Action now (RUN · IN)</div>` +
            (state.agentInbox.action_now || []).map((t) => inboxRow(t, false)).join("")
          : `<div class="rr-inbox-sec">Action now</div><div class="rr-muted rr-inbox-empty">Nothing for agent to cut.</div>`) +
        ((state.agentInbox.awaiting_qa || []).length
          ? `<div class="rr-inbox-sec">Awaiting Hands QA (TEST)</div>` +
            (state.agentInbox.awaiting_qa || []).map((t) => inboxRow(t, true)).join("")
          : "") +
        ((state.agentInbox.later || []).length
          ? `<div class="rr-inbox-sec">Later (DISCUSSION · PAUSED)</div>` +
            (state.agentInbox.later || []).map((t) => inboxRow(t, true)).join("")
          : "")
      : "";
    const rows = state.cases
      .map(
        (c) => `
      <tr data-id="${esc(c.id)}">
        <td class="rr-code">${esc(c.req_code)}</td>
        <td><span class="rr-badge">${esc(c.req_type || "REQ")}</span></td>
        <td><strong>${esc(c.title || displayTitle(c))}</strong></td>
        <td class="rr-muted">${esc(c.producer || "—")}</td>
        <td class="rr-muted">${esc(c.hands || "—")}</td>
        <td><span class="rr-badge is-${esc((c.priority || "").toLowerCase())}">${esc(c.priority || "—")}</span></td>
        <td><span class="rr-badge is-${esc(c.status || "")}">${esc(statusLabel(c.status))}</span></td>
        <td class="rr-ticket-pots" title="Open tickets: active lanes vs paused">
          <span class="rr-pot-act">${c.open_active ?? "—"} act</span>
          <span class="rr-pot-sep">·</span>
          <span class="rr-pot-pause">${c.open_paused ?? 0} paus</span>
          <span class="rr-muted rr-pot-tot"> / ${c.chunk_count ?? 0}</span>
        </td>
      </tr>`
      )
      .join("");
    const activeOpen =
      (counts.run || 0) +
      (counts.test || 0) +
      (counts.discussion || 0);
    const pausedOpen = counts.paused || 0;
    const sealedN = (state.listInbox && state.listInbox.sealed_total) || 0;
    const closedDisplay =
      (state.listInbox && state.listInbox.closed_display) != null
        ? state.listInbox.closed_display
        : sealedN + (counts.closed || 0);
    viewList.innerHTML = `
      <div class="rr-inbox-rail" aria-label="Open tickets by lane">
        <div class="rr-inbox-rail-head">
          <span class="rr-inbox-title">Open board</span>
          <span class="rr-muted">${openTotal} open · <strong>${closedDisplay}</strong> sealed/closed</span>
          <button type="button" class="rr-btn rr-btn-ghost" id="btnInboxToggle">${showBoard ? "Hide tickets" : "Show open tickets"}</button>
        </div>
        <div class="rr-inbox-pots" aria-label="Active vs paused pots">
          <div class="rr-inbox-pot is-active">
            <span class="rr-inbox-pot-lab">Active</span>
            <span class="rr-muted rr-inbox-pot-sum"><strong>${activeOpen}</strong> · ${actionN} action · ${qaN} QA · ${counts.discussion || 0} discuss</span>
            <div class="rr-inbox-lanes">
              <span class="rr-lane-chip is-discussion is-on" title="Discussion — agent should reply">DISCUSS ${counts.discussion || 0}</span>
              <span class="rr-lane-chip is-run is-on" title="Run — agent may implement">RUN ${counts.run || 0}</span>
              <span class="rr-lane-chip is-test is-on" title="Test — Hands QA">TEST ${counts.test || 0}</span>
            </div>
          </div>
          <div class="rr-inbox-pot is-paused">
            <span class="rr-inbox-pot-lab">Held / done</span>
            <span class="rr-muted rr-inbox-pot-sum"><strong>${pausedOpen}</strong> paused · <strong>${closedDisplay}</strong> sealed/closed</span>
            <div class="rr-inbox-lanes">
              <span class="rr-lane-chip is-paused is-on" title="Paused">PAUSED ${pausedOpen}</span>
              <span class="rr-lane-chip is-closed is-on" title="HAND STAMP sealed + open CLOSED lane">CLOSED ${closedDisplay}</span>
            </div>
          </div>
        </div>
        ${showBoard ? `<div class="rr-inbox-board">${boardRows || '<div class="rr-muted rr-inbox-empty">No open tickets.</div>'}</div>` : ""}
        <p class="rr-hint rr-inbox-hint">Agent bag: <code>safe_box/agent_inbox.json</code> · RUN = implement · DISCUSSION = reply · PAUSED = no reply · TEST = your QA · CLOSED = done for agent.</p>
      </div>
      <div class="rr-table-wrap">
      <table class="rr-table">
        <thead>
          <tr>
            <th>File</th><th>Type</th><th>Title line</th><th>Producer</th>
            <th>Hands</th><th>Pri</th><th>Status</th><th>Tickets</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
      </div>`;
    viewList.querySelectorAll("tbody tr").forEach((tr) => {
      tr.addEventListener("click", () => openCase(tr.getAttribute("data-id")));
    });
    const tog = viewList.querySelector("#btnInboxToggle");
    if (tog) {
      tog.addEventListener("click", async () => {
        if (state.inboxBoardOpen) {
          state.inboxBoardOpen = false;
          renderList();
          return;
        }
        state.inboxBoardOpen = true;
        await loadAgentInboxFull();
        renderList();
      });
    }
    viewList.querySelectorAll(".rr-inbox-row[data-case]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const cid = btn.getAttribute("data-case");
        const ch = btn.getAttribute("data-chunk");
        openCase(cid).then(() => {
          if (ch) {
            state.bodyOpen[ch] = true;
            const el = document.getElementById("ticket-" + ch);
            if (el) el.scrollIntoView({ block: "nearest" });
            renderCase({ restoreScroll: true });
          }
        });
      });
    });
  }

  async function openCase(id, opts = {}) {
    if (!id) return;
    try {
      if (state.case && state.case.id) captureDraftsFromDom();
      const data = await api(`/api/cases/${encodeURIComponent(id)}`);
      state.case = data.case;
      loadDraftsForCase(id);
      state.editIntake = false;
      state.editScope = false;
      state.editPrep = false;
      state.purposeOpen = false;
      // B09: sealed tickets stay collapsed; open only unsealed with talk
      for (const ch of state.case.chunks || []) {
        if (state.openThreads[ch.id] === undefined) {
          state.openThreads[ch.id] = !ch.closed && (ch.comments || []).length > 0;
        }
      }
      if (!opts.skipHash) setCaseHash(id);
      renderCase({ restoreScroll: !!opts.restoreScroll || opts.fromBoot });
    } catch (e) {
      toast(e.message || "Could not open", true);
      setCaseHash(null);
      await loadList();
    }
  }

  async function bootRoute() {
    await loadList({ keepCase: true });
    const hid = caseHashId();
    if (hid) await openCase(hid, { skipHash: true, fromBoot: true, restoreScroll: true });
    else renderList();
  }

  function bindIntakeTitlePreview(root) {
    const kindEl = root.querySelector("#metaType, [name=req_type]");
    const skuEl = root.querySelector("#metaSku, [name=sku]");
    const nameEl = root.querySelector("#metaProduct, [name=product_name]");
    const prev = root.querySelector("#intakeTitlePreview, #newTitlePreview");
    if (!prev) return;
    const tick = () => {
      prev.textContent = liveTitlePreview(
        kindEl ? kindEl.value : "REQ",
        skuEl ? skuEl.value : "",
        nameEl ? nameEl.value : ""
      );
    };
    [kindEl, skuEl, nameEl].forEach((el) => {
      if (el) {
        el.addEventListener("input", tick);
        el.addEventListener("change", tick);
      }
    });
    tick();
  }

  function sortTickets(list) {
    return [...list].sort((a, b) => {
      const ac = a.closed ? 1 : 0;
      const bc = b.closed ? 1 : 0;
      if (ac !== bc) return ac - bc; // open first
      return (Number(a.ticket_seq) || 0) - (Number(b.ticket_seq) || 0);
    });
  }

  function visibleTickets(c) {
    let list = c.chunks || [];
    if (state.hideSealed) list = list.filter((ch) => !ch.closed);
    return sortTickets(list);
  }

  function renderTicketCard(c, ch, scopeLocked) {
    const ref = ch.ref || "??";
    const kind = ch.ticket_kind || "IDA";
    const lane = ch.work_lane || "discussion";
    const n = (ch.comments || []).length;
    let threadOpen = !!state.openThreads[ch.id];
    if (ch.closed && state.openThreads[ch.id] === undefined) threadOpen = false;
    const bodyOpen = !!state.bodyOpen[ch.id];

    const comments = (ch.comments || [])
      .map((cm) => {
        const edited = cm.edited
          ? ` · edited`
          : "";
        return `
      <div class="rr-comment is-${esc(cm.author)}" data-comment-wrap="${esc(cm.id)}">
        <div class="rr-comment-head">
          <span class="rr-comment-who">${esc((cm.author || "").toUpperCase())}${edited}</span>
          <button type="button" class="rr-btn rr-btn-ghost rr-comment-edit" data-edit-comment="${esc(ch.id)}" data-comment-id="${esc(cm.id)}">Edit</button>
        </div>
        <div class="rr-comment-text" data-comment-view="${esc(cm.id)}">${formatRich(cm.text)}</div>
        <div class="rr-comment-editor" data-comment-editor="${esc(cm.id)}" hidden>
          <textarea class="rr-comment-ta" data-comment-ta="${esc(cm.id)}">${esc(cm.text)}</textarea>
          <div class="rr-compose-row">
            <button type="button" class="rr-btn" data-cancel-comment="${esc(cm.id)}">Cancel</button>
            <button type="button" class="rr-btn rr-btn-primary" data-save-comment="${esc(ch.id)}" data-comment-id="${esc(cm.id)}">Save</button>
          </div>
        </div>
      </div>`;
      })
      .join("");

    const compose = ch.closed
      ? ""
      : `
      <div class="rr-compose">
        <textarea data-compose="${esc(ch.id)}" placeholder="→ ${esc(ref)} as ${esc(state.role)}"></textarea>
        <div class="rr-compose-row">
          <button type="button" class="rr-btn rr-btn-primary" data-post="${esc(ch.id)}">Post</button>
        </div>
      </div>`;

    const when = stampWhen(ch);
    const laneBar = `
      <div class="rr-lane" title="Work-order lane — not approval">
        ${LANE_ORDER.map(
            (L) =>
              `<button type="button" class="rr-lane-chip is-${esc(L)} ${lane === L ? "is-on" : ""}" data-lane-set="${esc(ch.id)}" data-lane="${esc(L)}">${esc(LANE_LABEL[L])}</button>`
          ).join("")}
      </div>`;

    // Scope lock freezes PURPOSE only — tickets stay editable (workboard mode)
    const actions = ch.closed
      ? `<button type="button" class="rr-chunk-seal rr-chunk-seal-btn" data-reopen="${esc(ch.id)}" title="Reopen seal">${esc(ch.close_note || "SEALED")}${when ? " · " + esc(when) : ""}</button>`
      : `<button type="button" class="rr-btn rr-btn-stamp" data-close="${esc(ch.id)}">HAND STAMP</button>`;

    return `
    <article class="rr-chunk ${ch.closed ? "is-closed" : "is-open-block"} ${bodyOpen ? "is-body-open" : "is-body-collapsed"} lane-${esc(lane)}" data-chunk="${esc(ch.id)}" id="ticket-${esc(ch.id)}">
      <div class="rr-ticket-bar">
        <button type="button" class="rr-ticket-sum" data-body-toggle="${esc(ch.id)}" title="Expand / collapse body">
          <span class="rr-ticket-caret">${bodyOpen ? "▾" : "▸"}</span>
          <span class="rr-chunk-ref">${esc(ref)}</span>
          <span class="rr-badge is-kind-${esc(kind)}">${esc(kind)}</span>
          <span class="rr-ticket-snip">${esc(ticketSnippet(ch.body))}</span>
        </button>
        <div class="rr-ticket-bar-actions">
          ${laneBar}
          ${actions}
        </div>
      </div>
      <div class="rr-ticket-drawer" ${bodyOpen ? "" : "hidden"}>
        <div class="rr-chunk-body" ${ch.closed ? "" : 'contenteditable="true" data-edit-chunk="' + esc(ch.id) + '"'} spellcheck="true">${ch.closed ? formatRich(ch.body) : formatBody(ch.body)}</div>
        <button type="button" class="rr-thread-toggle" data-toggle="${esc(ch.id)}">
          ${threadOpen ? "▾" : "▸"} thread · ${n}${ch.closed ? " · sealed" : ""}
        </button>
        <div class="rr-thread ${threadOpen ? "is-open" : ""}" data-thread="${esc(ch.id)}">
          ${comments || '<div class="rr-muted">Empty thread.</div>'}
          ${compose}
        </div>
      </div>
    </article>`;
  }

  function captureDraftsFromDom() {
    if (!viewCase) return;
    viewCase.querySelectorAll("[data-edit-chunk]").forEach((el) => {
      const id = el.getAttribute("data-edit-chunk");
      if (id) state.drafts.chunkBodies[id] = el.innerText || "";
    });
    viewCase.querySelectorAll("textarea[data-compose]").forEach((el) => {
      const id = el.getAttribute("data-compose");
      if (id) state.drafts.compose[id] = el.value || "";
    });
    const nb = $("newChunkBody");
    if (nb) state.drafts.newChunkBody = nb.value || "";
    const nk = $("newTicketKind");
    if (nk) state.drafts.newTicketKind = nk.value || "IDA";
    persistDrafts();
  }

  function persistDrafts() {
    try {
      const cid = state.case && state.case.id;
      if (!cid) return;
      const all = JSON.parse(localStorage.getItem(DRAFT_LS) || "{}");
      all[cid] = {
        chunkBodies: state.drafts.chunkBodies,
        compose: state.drafts.compose,
        newChunkBody: state.drafts.newChunkBody,
        newTicketKind: state.drafts.newTicketKind,
        t: Date.now(),
      };
      localStorage.setItem(DRAFT_LS, JSON.stringify(all));
    } catch (e) {
      /* */
    }
  }

  function loadDraftsForCase(caseId) {
    try {
      const all = JSON.parse(localStorage.getItem(DRAFT_LS) || "{}");
      const d = all[caseId];
      if (!d) return;
      state.drafts.chunkBodies = { ...(d.chunkBodies || {}) };
      state.drafts.compose = { ...(d.compose || {}) };
      state.drafts.newChunkBody = d.newChunkBody || "";
      state.drafts.newTicketKind = d.newTicketKind || "IDA";
    } catch (e) {
      /* */
    }
  }

  function clearDraftChunk(id) {
    delete state.drafts.chunkBodies[id];
    delete state.drafts.compose[id];
    persistDrafts();
  }

  function restoreDraftsToDom() {
    if (!viewCase) return;
    viewCase.querySelectorAll("[data-edit-chunk]").forEach((el) => {
      const id = el.getAttribute("data-edit-chunk");
      if (id && state.drafts.chunkBodies[id] != null) {
        // only restore if diverges from server body (user was mid-edit)
        const server = ((state.case && state.case.chunks) || []).find((x) => x.id === id);
        const serverText = server ? String(server.body || "") : "";
        if (state.drafts.chunkBodies[id] !== serverText) {
          el.innerText = state.drafts.chunkBodies[id];
        }
      }
    });
    viewCase.querySelectorAll("textarea[data-compose]").forEach((el) => {
      const id = el.getAttribute("data-compose");
      if (id && state.drafts.compose[id] != null) {
        el.value = state.drafts.compose[id];
      }
    });
    const nb = $("newChunkBody");
    if (nb && state.drafts.newChunkBody) nb.value = state.drafts.newChunkBody;
    const nk = $("newTicketKind");
    if (nk && state.drafts.newTicketKind) nk.value = state.drafts.newTicketKind;
  }

  function renderCase(opts = {}) {
    const c = state.case;
    if (!c) return;
    captureDraftsFromDom();
    const main = mainEl();
    const keepY = opts.restoreScroll ? null : main ? main.scrollTop : 0;
    setView("case");
    pageTitle.textContent = c.req_code || "REQ";
    metaCount.textContent = statusLabel(c.status);

    const scope = c.scope || {};
    const prep = c.prep || {};
    const scopeLocked = !!scope.locked;
    const prepSigned = !!prep.signed;

    const all = c.chunks || [];
    let show = visibleTickets(c);
    if (state.focusTicketId) {
      const one = all.find((x) => x.id === state.focusTicketId);
      show = one ? [one] : show;
    }

    const chunksHtml = show.map((ch) => renderTicketCard(c, ch, scopeLocked)).join("");

    const tocItems = sortTickets(all.filter((ch) => !state.hideSealed || !ch.closed))
      .map((ch) => {
        const on = state.focusTicketId === ch.id;
        return `
        <button type="button" class="rr-toc-item ${on ? "is-on" : ""} ${ch.closed ? "is-sealed" : ""}" data-focus="${esc(ch.id)}">
          <span class="rr-toc-ref">${esc(ch.ref || "?")}</span>
          <span class="rr-badge is-kind-${esc(ch.ticket_kind || "IDA")}">${esc(ch.ticket_kind || "IDA")}</span>
          <span class="rr-toc-snip">${esc(ticketSnippet(ch.body))}</span>
          <span class="rr-toc-lane">${esc(LANE_LABEL[ch.work_lane || "discussion"] || "")}</span>
        </button>`;
      })
      .join("");

    const intakeRead = `
      <div class="rr-intake-mini">
        <div class="rr-intake-group">
          <div class="rr-intake-gtitle">Codes</div>
          ${kvRow("Type", c.req_type || "REQ")}
          ${kvRow("SKU", c.sku)}
        </div>
        <div class="rr-intake-group">
          <div class="rr-intake-gtitle">Product</div>
          ${kvRow("Name", c.product_name)}
          ${kvRow("Pri", c.priority)}
        </div>
        <div class="rr-intake-group">
          <div class="rr-intake-gtitle">People</div>
          ${kvRow("Producer", c.producer)}
          ${kvRow("Hands", c.hands)}
        </div>
      </div>`;

    const intakeEdit = `
      <div class="rr-intake-edit">
        <div class="rr-field"><label>Type</label>
          <select id="metaType">${["REQ", "MOD", "ADDENDUM", "BUG"]
            .map(
              (t) =>
                `<option value="${t}" ${t === (c.req_type || "REQ") ? "selected" : ""}>${t}</option>`
            )
            .join("")}</select>
        </div>
        <div class="rr-field"><label>SKU</label><input id="metaSku" value="${esc(c.sku || "")}" /></div>
        <div class="rr-field"><label>Product</label><input id="metaProduct" value="${esc(c.product_name || "")}" /></div>
        <p class="rr-hint rr-line-live" id="intakeTitlePreview">${esc(displayTitle(c))}</p>
        <div class="rr-field"><label>Producer</label><input id="metaProducer" value="${esc(c.producer || "")}" /></div>
        <div class="rr-field"><label>Hands</label><input id="metaHands" value="${esc(c.hands || "")}" /></div>
        <div class="rr-field"><label>Priority</label>
          <select id="metaPriority">${["Low", "Normal", "High", "Urgent"]
            .map(
              (p) =>
                `<option ${p === (c.priority || "Normal") ? "selected" : ""}>${p}</option>`
            )
            .join("")}</select>
        </div>
      </div>`;

    const prepDock = `
      <aside class="rr-prep-dock ${prepSigned ? "is-signed" : ""}">
        <div class="rr-prep-dock-h">
          <strong>Product prep</strong>
          ${prepSigned ? '<span class="rr-badge is-signed">SIGN</span>' : ""}
          ${
            prepSigned
              ? ""
              : state.editPrep
                ? `<span class="rr-side-actions">
                    <button type="button" class="rr-btn" id="btnCancelPrep">Cancel</button>
                    <button type="button" class="rr-btn" id="btnSavePrep">Save</button>
                  </span>`
                : `<span class="rr-side-actions">
                    <button type="button" class="rr-btn" id="btnGenPrep">Generate</button>
                    <button type="button" class="rr-btn" id="btnEditPrep">Edit</button>
                    <button type="button" class="rr-btn rr-btn-ok" id="btnSignPrep">Sign</button>
                  </span>`
          }
        </div>
        <div class="rr-prep-dock-body">
          ${prepSigned ? '<div class="rr-signed-banner">HANDS SIGNED · leave-bay law</div>' : ""}
          ${
            state.editPrep && !prepSigned
              ? `<div class="rr-prep-body" id="prepBody" contenteditable="true">${esc(prep.body || "")}</div>`
              : `<div class="rr-prep-body is-read" id="prepBody">${esc(prep.body || "") || '<span class="rr-muted">AGENT USE ONLY! Generate post scope lock.</span>'}</div>`
          }
        </div>
      </aside>`;

    viewCase.innerHTML = `
      <div class="rr-case rr-case-flat">
        <div class="rr-case-head">
          <div class="rr-case-head-main">
            <h2 class="rr-case-title">${esc(displayTitle(c))}</h2>
            <div class="rr-case-meta-line">
              <span class="rr-code">${esc(c.req_code)}</span>
              <span class="rr-badge">${esc(c.req_type || "REQ")}</span>
              <span class="rr-muted">${esc(c.sku || "—")}</span>
              <span class="rr-badge is-${esc(c.status || "")}">${esc(statusLabel(c.status))}</span>
              <span class="rr-badge is-${esc((c.priority || "").toLowerCase())}">${esc(c.priority || "—")}</span>
              ${
                prepSigned
                  ? ""
                  : state.editIntake
                    ? `<span class="rr-side-actions">
                        <button type="button" class="rr-btn" id="btnCancelIntake">Cancel</button>
                        <button type="button" class="rr-btn rr-btn-primary" id="btnSaveMeta">Save intake</button>
                      </span>`
                    : `<button type="button" class="rr-btn" id="btnEditIntake">Edit intake</button>`
              }
              <button type="button" class="rr-btn" id="btnPurpose">${state.purposeOpen ? "Hide purpose" : "View purpose"}</button>
              ${
                state.focusTicketId
                  ? ""
                  : `<button type="button" class="rr-btn rr-btn-primary" id="btnAddTicketBar">+ Ticket</button>`
              }
            </div>
            ${state.editIntake && !prepSigned ? intakeEdit : intakeRead}
            ${
              state.purposeOpen
                ? `<div class="rr-purpose-panel">
                    <div class="rr-purpose-h">
                      <strong>Purpose</strong>
                      ${scopeLocked ? '<span class="rr-badge is-scope_locked">LOCK</span>' : ""}
                      ${
                        prepSigned
                          ? ""
                          : scopeLocked
                            ? `<button type="button" class="rr-btn" id="btnUnlockScope">Unlock</button>`
                            : state.editScope
                              ? `<span class="rr-side-actions">
                                  <button type="button" class="rr-btn" id="btnCancelScope">Cancel</button>
                                  <button type="button" class="rr-btn" id="btnSaveScope">Save</button>
                                  <button type="button" class="rr-btn rr-btn-primary" id="btnLockScope">Lock</button>
                                </span>`
                              : `<button type="button" class="rr-btn" id="btnEditScope">Edit</button>`
                      }
                    </div>
                    ${
                      state.editScope && !scopeLocked && !prepSigned
                        ? `<textarea id="scopeBody" class="rr-purpose-ta">${esc(scope.body || "")}</textarea>`
                        : `<div class="rr-readout">${esc(scope.body || "") || '<span class="rr-muted">No purpose yet.</span>'}</div>`
                    }
                  </div>`
                : ""
            }
          </div>
          ${prepDock}
        </div>

        <div class="rr-case-work">
          <aside class="rr-toc" aria-label="Ticket TOC">
            <div class="rr-toc-h">
              <strong>Tickets</strong>
              <span class="rr-side-actions">
                <button type="button" class="rr-btn ${!state.focusTicketId ? "rr-btn-primary" : ""}" id="btnViewAll">All</button>
                <button type="button" class="rr-btn ${state.hideSealed ? "rr-btn-primary" : ""}" id="btnHideSealed">${state.hideSealed ? "Show sealed" : "Hide sealed"}</button>
              </span>
            </div>
            <div class="rr-toc-list">${tocItems || '<div class="rr-muted">No tickets.</div>'}</div>
          </aside>
          <div class="rr-disc-col">
            <div class="rr-sec-h">
              <strong>${state.focusTicketId ? "Ticket" : "Discussion"}</strong>
              <span class="rr-muted">${state.focusTicketId ? "focus · back via All" : "TOC left · measure column"}</span>
            </div>
            <div class="rr-disc">
              ${chunksHtml || '<div class="rr-muted">No tickets in view.</div>'}
              ${
                state.focusTicketId
                  ? ""
                  : `${
                      scopeLocked
                        ? '<div class="rr-locked-banner rr-locked-soft">Purpose locked — tickets still open (workboard). Unlock purpose only to rewrite case purpose.</div>'
                        : ""
                    }
                    <div class="rr-add-chunk rr-add-chunk-bottom">
                        <div class="rr-add-row">
                          <label class="rr-add-kind">Kind
                            <select id="newTicketKind">
                              <option value="IDA">IDA — idea / discussion</option>
                              <option value="BUG">BUG</option>
                              <option value="CHG">CHG — change request</option>
                            </select>
                          </label>
                        </div>
                        <textarea id="newChunkBody" placeholder="Ticket body…"></textarea>
                        <div class="rr-compose-row">
                          <button type="button" class="rr-btn rr-btn-primary" id="btnAddChunk">+ Ticket</button>
                        </div>
                      </div>`
              }
            </div>
          </div>
        </div>
      </div>`;

    bindCaseEvents();
    if (state.editIntake) bindIntakeTitlePreview(viewCase);
    restoreDraftsToDom();

    if (opts.restoreScroll) restoreCaseScroll();
    else if (main && keepY != null) {
      requestAnimationFrame(() => {
        const m = mainEl();
        if (m) m.scrollTop = keepY;
      });
    }
    saveCaseScroll();
  }

  function bindCaseEvents() {
    const c = state.case;
    if (!c) return;

    const btnPurpose = $("btnPurpose");
    if (btnPurpose) {
      btnPurpose.addEventListener("click", () => {
        state.purposeOpen = !state.purposeOpen;
        renderCase();
      });
    }

    $("btnViewAll")?.addEventListener("click", () => {
      state.focusTicketId = null;
      renderCase();
    });
    $("btnHideSealed")?.addEventListener("click", () => {
      state.hideSealed = !state.hideSealed;
      localStorage.setItem("reqrep.hideSealed", state.hideSealed ? "1" : "0");
      if (state.focusTicketId) {
        const ch = (c.chunks || []).find((x) => x.id === state.focusTicketId);
        if (ch && ch.closed && state.hideSealed) state.focusTicketId = null;
      }
      renderCase();
    });

    viewCase.querySelectorAll("[data-focus]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-focus");
        state.focusTicketId = state.focusTicketId === id ? null : id;
        if (state.focusTicketId) state.openThreads[state.focusTicketId] = true;
        renderCase();
        const el = document.getElementById("ticket-" + id);
        if (el) el.scrollIntoView({ block: "nearest" });
      });
    });

    viewCase.querySelectorAll("[data-body-toggle]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-body-toggle");
        state.bodyOpen[id] = !state.bodyOpen[id];
        renderCase();
      });
    });

    viewCase.querySelectorAll("[data-toggle]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-toggle");
        state.openThreads[id] = !state.openThreads[id];
        if (state.openThreads[id]) state.bodyOpen[id] = true;
        renderCase();
      });
    });

    const addTicket = async () => {
      const ta = $("newChunkBody");
      const kindEl = $("newTicketKind");
      if (!ta && !$("btnAddTicketBar")) return;
      if (!ta) {
        // masthead + Ticket — open composer focus
        state.focusTicketId = null;
        renderCase();
        const t2 = $("newChunkBody");
        if (t2) t2.focus();
        return;
      }
      try {
        const data = await api(`/api/cases/${encodeURIComponent(c.id)}/chunks`, {
          method: "POST",
          body: JSON.stringify({
            body: ta.value || "",
            ticket_kind: kindEl ? kindEl.value : "IDA",
          }),
        });
        state.case = data.case;
        if (data.chunk) {
          state.openThreads[data.chunk.id] = true;
          state.bodyOpen[data.chunk.id] = true;
          state.focusTicketId = null;
        }
        state.drafts.newChunkBody = "";
        state.drafts.newTicketKind = "IDA";
        persistDrafts();
        renderCase();
        toast(data.chunk && data.chunk.ref ? data.chunk.ref : "ticket");
      } catch (e) {
        toast(e.message, true);
      }
    };
    $("btnAddChunk")?.addEventListener("click", addTicket);
    $("btnAddTicketBar")?.addEventListener("click", () => {
      state.focusTicketId = null;
      renderCase();
      const t2 = $("newChunkBody");
      if (t2) t2.focus();
    });

    viewCase.querySelectorAll("[data-post]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-post");
        const ta = viewCase.querySelector(`textarea[data-compose="${id}"]`);
        try {
          const data = await api(
            `/api/cases/${encodeURIComponent(c.id)}/chunks/${encodeURIComponent(id)}/comments`,
            {
              method: "POST",
              body: JSON.stringify({ author: state.role, text: (ta && ta.value) || "" }),
            }
          );
          state.case = data.case;
          state.openThreads[id] = true;
          state.bodyOpen[id] = true;
          if (id) {
            state.drafts.compose[id] = "";
            persistDrafts();
          }
          renderCase();
        } catch (e) {
          toast(e.message, true);
        }
      });
    });

    // CHG20 — edit comment
    viewCase.querySelectorAll("[data-edit-comment]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const cid = btn.getAttribute("data-comment-id");
        const view = viewCase.querySelector(`[data-comment-view="${cid}"]`);
        const ed = viewCase.querySelector(`[data-comment-editor="${cid}"]`);
        if (view) view.hidden = true;
        if (ed) ed.hidden = false;
        const ta = viewCase.querySelector(`[data-comment-ta="${cid}"]`);
        if (ta) ta.focus();
      });
    });
    viewCase.querySelectorAll("[data-cancel-comment]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const cid = btn.getAttribute("data-cancel-comment");
        const view = viewCase.querySelector(`[data-comment-view="${cid}"]`);
        const ed = viewCase.querySelector(`[data-comment-editor="${cid}"]`);
        if (view) view.hidden = false;
        if (ed) ed.hidden = true;
      });
    });
    viewCase.querySelectorAll("[data-save-comment]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const chunkId = btn.getAttribute("data-save-comment");
        const cid = btn.getAttribute("data-comment-id");
        const ta = viewCase.querySelector(`[data-comment-ta="${cid}"]`);
        const text = ta ? ta.value : "";
        try {
          const data = await api(
            `/api/cases/${encodeURIComponent(c.id)}/chunks/${encodeURIComponent(chunkId)}/comments/${encodeURIComponent(cid)}`,
            { method: "POST", body: JSON.stringify({ text }) }
          );
          state.case = data.case;
          state.openThreads[chunkId] = true;
          state.bodyOpen[chunkId] = true;
          renderCase();
          toast("comment saved");
        } catch (e) {
          toast(e.message, true);
        }
      });
    });

    viewCase.querySelectorAll("[data-close]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-close");
        const ch = (c.chunks || []).find((x) => x.id === id);
        const ref = (ch && ch.ref) || "?";
        // HAND STAMP button defaults toward CLOSED for quick seal (CHG29)
        const picked = await romStampDialog(ref, {
          note: "",
          work_lane: "closed",
        });
        if (!picked) return;
        try {
          if (picked.seal) {
            const data = await api(
              `/api/cases/${encodeURIComponent(c.id)}/chunks/${encodeURIComponent(id)}/close`,
              {
                method: "POST",
                body: JSON.stringify({
                  note: picked.note || "AGREED",
                  work_lane: picked.work_lane,
                }),
              }
            );
            state.case = data.case;
            state.openThreads[id] = false;
            clearDraftChunk(id);
            renderCase();
            toast(`${ref} sealed`);
          } else {
            const data = await api(
              `/api/cases/${encodeURIComponent(c.id)}/chunks/${encodeURIComponent(id)}/lane`,
              {
                method: "POST",
                body: JSON.stringify({ work_lane: picked.work_lane }),
              }
            );
            state.case = data.case;
            renderCase();
            toast(`${ref} · ${LANE_LABEL[picked.work_lane] || picked.work_lane} (not sealed)`);
          }
        } catch (e) {
          toast(e.message, true);
        }
      });
    });

    viewCase.querySelectorAll("[data-lane-set]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-lane-set");
        const lane = btn.getAttribute("data-lane");
        const ch = (c.chunks || []).find((x) => x.id === id);
        const ref = (ch && ch.ref) || "?";
        // CHG29: CLOSED on the ticket lane rail → HAND STAMP pre-set to closed + note field
        if (lane === "closed" && ch && !ch.closed) {
          const picked = await romStampDialog(ref, {
            note: "",
            work_lane: "closed",
          });
          if (!picked) return;
          try {
            if (picked.seal) {
              const data = await api(
                `/api/cases/${encodeURIComponent(c.id)}/chunks/${encodeURIComponent(id)}/close`,
                {
                  method: "POST",
                  body: JSON.stringify({
                    note: picked.note || "AGREED",
                    work_lane: picked.work_lane || "closed",
                  }),
                }
              );
              state.case = data.case;
              state.openThreads[id] = false;
              clearDraftChunk(id);
              renderCase();
              toast(`${ref} sealed`);
            } else {
              const data = await api(
                `/api/cases/${encodeURIComponent(c.id)}/chunks/${encodeURIComponent(id)}/lane`,
                {
                  method: "POST",
                  body: JSON.stringify({ work_lane: picked.work_lane || "closed" }),
                }
              );
              state.case = data.case;
              renderCase();
              toast(
                `${ref} · ${LANE_LABEL[picked.work_lane] || picked.work_lane} (not sealed)`
              );
            }
          } catch (e) {
            toast(e.message, true);
          }
          return;
        }
        try {
          const data = await api(
            `/api/cases/${encodeURIComponent(c.id)}/chunks/${encodeURIComponent(id)}/lane`,
            { method: "POST", body: JSON.stringify({ work_lane: lane }) }
          );
          state.case = data.case;
          // never auto-close
          if (data.case.chunks) {
            const after = data.case.chunks.find((x) => x.id === id);
            if (after && after.closed && ch && !ch.closed) {
              toast("unexpected seal — report", true);
            }
          }
          renderCase();
          toast(`${ref} · ${LANE_LABEL[lane] || lane}`);
        } catch (e) {
          toast(e.message, true);
        }
      });
    });

    viewCase.querySelectorAll("[data-reopen]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-reopen");
        const ch = (c.chunks || []).find((x) => x.id === id);
        const ref = (ch && ch.ref) || "?";
        const ok = await romConfirm(
          `Reopen ${ref}`,
          "Clears the seal only. Work lane is unchanged.",
          "Reopen"
        );
        if (!ok) return;
        try {
          const data = await api(
            `/api/cases/${encodeURIComponent(c.id)}/chunks/${encodeURIComponent(id)}/reopen`,
            { method: "POST", body: "{}" }
          );
          state.case = data.case;
          state.openThreads[id] = true;
          renderCase();
          toast(`${ref} reopened`);
        } catch (e) {
          toast(e.message, true);
        }
      });
    });

    viewCase.querySelectorAll("[data-edit-chunk]").forEach((el) => {
      el.addEventListener("input", () => {
        const id = el.getAttribute("data-edit-chunk");
        if (!id) return;
        state.drafts.chunkBodies[id] = el.innerText || "";
        persistDrafts();
      });
      el.addEventListener("blur", async () => {
        const id = el.getAttribute("data-edit-chunk");
        try {
          const data = await api(
            `/api/cases/${encodeURIComponent(c.id)}/chunks/${encodeURIComponent(id)}`,
            { method: "PATCH", body: JSON.stringify({ body: el.innerText }) }
          );
          state.case = data.case;
          if (id) {
            state.drafts.chunkBodies[id] = el.innerText || "";
            persistDrafts();
          }
        } catch (e) {
          toast(e.message, true);
          openCase(c.id);
        }
      });
    });
    viewCase.querySelectorAll("textarea[data-compose]").forEach((el) => {
      el.addEventListener("input", () => {
        const id = el.getAttribute("data-compose");
        if (!id) return;
        state.drafts.compose[id] = el.value || "";
        persistDrafts();
      });
    });
    const newBody = $("newChunkBody");
    if (newBody) {
      newBody.addEventListener("input", () => {
        state.drafts.newChunkBody = newBody.value || "";
        persistDrafts();
      });
    }
    const newKind = $("newTicketKind");
    if (newKind) {
      newKind.addEventListener("change", () => {
        state.drafts.newTicketKind = newKind.value || "IDA";
        persistDrafts();
      });
    }

    $("btnEditIntake")?.addEventListener("click", () => {
      state.editIntake = true;
      renderCase();
    });
    $("btnCancelIntake")?.addEventListener("click", () => {
      state.editIntake = false;
      renderCase();
    });
    $("btnSaveMeta")?.addEventListener("click", async () => {
      try {
        const data = await api(`/api/cases/${encodeURIComponent(c.id)}/meta`, {
          method: "POST",
          body: JSON.stringify({
            req_type: $("metaType").value,
            sku: $("metaSku").value,
            product_name: $("metaProduct").value,
            producer: $("metaProducer").value,
            hands: $("metaHands").value,
            priority: $("metaPriority").value,
          }),
        });
        state.case = data.case;
        state.editIntake = false;
        renderCase();
        toast("intake saved");
      } catch (e) {
        toast(e.message, true);
      }
    });

    $("btnEditScope")?.addEventListener("click", () => {
      state.editScope = true;
      state.purposeOpen = true;
      renderCase();
    });
    $("btnCancelScope")?.addEventListener("click", () => {
      state.editScope = false;
      renderCase();
    });
    $("btnSaveScope")?.addEventListener("click", async () => {
      try {
        const data = await api(`/api/cases/${encodeURIComponent(c.id)}/scope`, {
          method: "POST",
          body: JSON.stringify({ body: $("scopeBody").value }),
        });
        state.case = data.case;
        state.editScope = false;
        renderCase();
        toast("purpose saved");
      } catch (e) {
        toast(e.message, true);
      }
    });
    $("btnLockScope")?.addEventListener("click", async () => {
      try {
        const bodyEl = $("scopeBody");
        const body = bodyEl
          ? bodyEl.value
          : (state.case.scope && state.case.scope.body) || "";
        const data = await api(`/api/cases/${encodeURIComponent(c.id)}/scope`, {
          method: "POST",
          body: JSON.stringify({ body, lock: true }),
        });
        state.case = data.case;
        state.editScope = false;
        renderCase();
        toast("purpose locked");
      } catch (e) {
        toast(e.message, true);
      }
    });
    $("btnUnlockScope")?.addEventListener("click", async () => {
      try {
        const data = await api(`/api/cases/${encodeURIComponent(c.id)}/scope`, {
          method: "POST",
          body: JSON.stringify({ unlock: true }),
        });
        state.case = data.case;
        state.editScope = false;
        renderCase();
      } catch (e) {
        toast(e.message, true);
      }
    });

    $("btnGenPrep")?.addEventListener("click", async () => {
      try {
        const data = await api(`/api/cases/${encodeURIComponent(c.id)}/prep`, {
          method: "POST",
          body: JSON.stringify({ generate: true }),
        });
        state.case = data.case;
        state.editPrep = true;
        renderCase();
        toast("prep · review & Save");
      } catch (e) {
        toast(e.message, true);
      }
    });
    $("btnEditPrep")?.addEventListener("click", () => {
      state.editPrep = true;
      renderCase();
    });
    $("btnCancelPrep")?.addEventListener("click", () => {
      state.editPrep = false;
      renderCase();
    });
    $("btnSavePrep")?.addEventListener("click", async () => {
      const el = $("prepBody");
      try {
        const data = await api(`/api/cases/${encodeURIComponent(c.id)}/prep`, {
          method: "POST",
          body: JSON.stringify({ body: el ? el.innerText : "" }),
        });
        state.case = data.case;
        state.editPrep = false;
        renderCase();
        toast("prep saved");
      } catch (e) {
        toast(e.message, true);
      }
    });
    $("btnSignPrep")?.addEventListener("click", async () => {
      const ok = await romConfirm(
        "Sign Product prep",
        "Hands seal. Leave-the-bay contract freezes.",
        "Sign"
      );
      if (!ok) return;
      try {
        const data = await api(`/api/cases/${encodeURIComponent(c.id)}/prep`, {
          method: "POST",
          body: JSON.stringify({ sign: true }),
        });
        state.case = data.case;
        state.editPrep = false;
        renderCase();
        toast("signed");
      } catch (e) {
        toast(e.message, true);
      }
    });
  }

  btnTheme.addEventListener("click", () => {
    state.theme = state.theme === "light" ? "dark" : "light";
    localStorage.setItem("reqrep.theme", state.theme);
    applyTheme();
  });

  roleSelect.value = state.role;
  roleSelect.addEventListener("change", () => {
    state.role = roleSelect.value;
    localStorage.setItem("reqrep.role", state.role);
    if (state.view === "case") renderCase();
  });

  btnBack.addEventListener("click", async () => {
    state.case = null;
    state.focusTicketId = null;
    setCaseHash(null);
    await loadList();
  });

  window.addEventListener("hashchange", () => {
    const hid = caseHashId();
    if (hid) {
      if (!state.case || state.case.id !== hid) openCase(hid, { skipHash: true });
    } else if (state.view === "case") {
      state.case = null;
      loadList();
    }
  });

  btnNew.addEventListener("click", () => {
    modalNew.hidden = false;
    formNew.reset();
    bindIntakeTitlePreview(formNew);
  });
  $("btnCancelNew").addEventListener("click", () => {
    modalNew.hidden = true;
  });
  formNew.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const fd = new FormData(formNew);
    try {
      const data = await api("/api/cases", {
        method: "POST",
        body: JSON.stringify({
          req_type: fd.get("req_type"),
          sku: fd.get("sku"),
          product_name: fd.get("product_name"),
          producer: fd.get("producer"),
          hands: fd.get("hands"),
          priority: fd.get("priority"),
          seed: fd.get("seed"),
        }),
      });
      modalNew.hidden = true;
      state.case = data.case;
      renderCase();
      toast(data.case.req_code);
    } catch (e) {
      toast(e.message, true);
    }
  });
  bindIntakeTitlePreview(formNew);

  const mainScrollRoot = document.querySelector(".rr-main");
  if (mainScrollRoot) {
    let scrollTick = null;
    mainScrollRoot.addEventListener(
      "scroll",
      () => {
        if (scrollTick) return;
        scrollTick = requestAnimationFrame(() => {
          scrollTick = null;
          saveCaseScroll();
        });
      },
      { passive: true }
    );
  }
  window.addEventListener("beforeunload", saveCaseScroll);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") saveCaseScroll();
  });

  applyTheme();
  bootRoute().catch((e) => toast(e.message || "Failed to load", true));
})();

/* Big Box Company · sopr Documenter */
(function () {
  "use strict";

  const state = {
    docs: [],
    slug: null,
    doc: null,
    activeSectionId: null,
    view: "empty", // empty | doc | kanban | print
    lastStored: null,
  };

  /** Time Machina cord — peek only. Offline = silent skip. */
  const MACHINA_CORD =
    (typeof window !== "undefined" && window.MACHINA_CORD) ||
    "http://127.0.0.1:43111";

  const $ = (id) => document.getElementById(id);

  /**
   * Peek Machina session.now — chip for document tps_chips bin.
   * No vencodes. Returns null if offline / pocket off / no chip.
   */
  async function peekMachinaCord() {
    try {
      const res = await fetch(MACHINA_CORD + "/api/cord/now", {
        method: "GET",
        mode: "cors",
      });
      if (!res.ok) return null;
      const data = await res.json();
      if (!data || data.pocket_on === false) return null;
      const cur = data.current || {};
      const chip_id = (cur.chip_id || data.chip_id || "").trim();
      if (!chip_id) return null;
      return {
        chip_id: chip_id,
        export_id: (data.export_id || cur.export_id || "").trim(),
      };
    } catch (_e) {
      return null;
    }
  }

  async function stampChipOnDoc(peek) {
    if (!state.slug) return { ok: false, reason: "no doc" };
    let p = peek;
    if (!p) p = await peekMachinaCord();
    if (!p || !p.chip_id) return { ok: false, reason: "no chip / machina offline" };
    try {
      const data = await api(
        "POST",
        "/api/docs/" + encodeURIComponent(state.slug) + "/tps-chips",
        { chip_id: p.chip_id, export_id: p.export_id || "" }
      );
      state.doc = data.doc;
      return { ok: true, chip: data.tps_chip };
    } catch (e) {
      return { ok: false, reason: e.message };
    }
  }

  function openAboutDoc() {
    if (!state.doc) return;
    const backdrop = $("about-backdrop");
    const body = $("about-body");
    const doc = state.doc;
    const chips = Array.isArray(doc.tps_chips) ? doc.tps_chips : [];
    const parts = Object.keys(doc.parts || {}).length;
    const sections = Object.keys(doc.sections || {}).length;

    let chipsHtml = "";
    if (!chips.length) {
      chipsHtml =
        '<p class="about-empty">No TPS chips recorded yet. Store a fragment while Machina pocket is on, or Stamp current TPS chip.</p>';
    } else {
      chipsHtml = '<ul class="about-chips">';
      for (const c of chips) {
        chipsHtml +=
          "<li><span>" +
          escapeHtml(c.chip_id || "") +
          "</span>" +
          (c.export_id
            ? '<span class="chip-export">export ' +
              escapeHtml(c.export_id) +
              "</span>"
            : "") +
          "</li>";
      }
      chipsHtml += "</ul>";
    }

    body.innerHTML =
      '<div class="meta-row"><span class="meta-k">Name</span><span class="meta-v">' +
      escapeHtml(doc.doc_name || "") +
      "</span></div>" +
      '<div class="meta-row"><span class="meta-k">Slug</span><span class="meta-v">' +
      escapeHtml(doc.slug || state.slug || "") +
      ".sopr</span></div>" +
      '<div class="meta-row"><span class="meta-k">Parts</span><span class="meta-v">' +
      parts +
      "</span></div>" +
      '<div class="meta-row"><span class="meta-k">Sections</span><span class="meta-v">' +
      sections +
      "</span></div>" +
      "<h3>TPS CHIPS USED IN PRODUCTION</h3>" +
      chipsHtml +
      '<p class="muted small" style="margin-top:12px">Document-level only. No vencodes. No per-frag chip drama. Open the chip in Machina if you need the message.</p>';

    backdrop.hidden = false;
  }

  function closeAboutDoc() {
    $("about-backdrop").hidden = true;
  }

  async function api(method, path, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(path, opts);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.error || res.statusText || "request failed");
    }
    return data;
  }

  function setStatus(msg) {
    $("status").textContent = msg;
  }

  function setChrome() {
    const meta = $("chrome-meta");
    if (!state.doc) {
      meta.textContent = "Big Box Company · no document selected";
      return;
    }
    meta.textContent =
      "Big Box Company · " +
      (state.doc.doc_name || state.slug) +
      " · " +
      Object.keys(state.doc.parts || {}).length +
      " parts";
  }

  function sectionOrder(doc) {
    const order = doc.section_order || [];
    const sections = doc.sections || {};
    const out = [];
    for (const id of order) {
      if (sections[id]) out.push(id);
    }
    for (const id of Object.keys(sections)) {
      if (!out.includes(id)) out.push(id);
    }
    return out;
  }

  async function refreshDocList() {
    const data = await api("GET", "/api/docs");
    state.docs = data.docs || [];
    const sel = $("doc-select");
    const cur = state.slug || "";
    sel.innerHTML = '<option value="">— select —</option>';
    for (const d of state.docs) {
      const opt = document.createElement("option");
      opt.value = d.slug;
      opt.textContent =
        d.doc_name +
        " (" +
        (d.part_count || 0) +
        " frags · " +
        (d.section_count || 0) +
        " sec)";
      if (d.slug === cur) opt.selected = true;
      sel.appendChild(opt);
    }
    // keep File → open list warm if menu is open
    const fileDrop = $("menu-file");
    if (fileDrop && !fileDrop.hidden) fillOpenMenu();
  }

  async function openDoc(slug) {
    if (!slug) {
      state.slug = null;
      state.doc = null;
      state.activeSectionId = null;
      state.view = "empty";
      render();
      return;
    }
    const data = await api("GET", "/api/docs/" + encodeURIComponent(slug));
    state.slug = slug;
    state.doc = data.doc;
    const order = sectionOrder(state.doc);
    if (
      !state.activeSectionId ||
      !(state.doc.sections || {})[state.activeSectionId]
    ) {
      state.activeSectionId = order[0] || null;
    }
    state.view = "doc";
    render();
  }

  async function newDoc() {
    const name = window.prompt("Document name:", "PLATFORM-STORY");
    if (!name || !name.trim()) return;
    try {
      const data = await api("POST", "/api/docs", { doc_name: name.trim() });
      await refreshDocList();
      await openDoc(data.doc.slug);
      setStatus("Created " + data.doc.slug + ".sopr");
    } catch (e) {
      alert(e.message);
    }
  }

  async function newSection() {
    if (!state.doc) return;
    const label = window.prompt("Section heading:", "");
    if (!label || !label.trim()) return;
    try {
      const data = await api(
        "POST",
        "/api/docs/" + encodeURIComponent(state.slug) + "/sections",
        { label: label.trim() }
      );
      state.doc = data.doc;
      state.activeSectionId = data.section_id;
      state.view = "doc";
      render();
      $("composer-leaf").focus();
    } catch (e) {
      alert(e.message);
    }
  }

  async function storeFragment() {
    if (!state.doc || !state.activeSectionId) return;
    const leaf = $("composer-leaf").value.trim();
    if (!leaf) {
      setStatus("Empty leaf — nothing stored.");
      return;
    }
    // Listener: peek Machina once; chip goes on the *document* bin only
    const peek = await peekMachinaCord();
    const body = {
      section_id: state.activeSectionId,
      leaf: leaf,
    };
    if (peek && peek.chip_id) {
      body.chip_id = peek.chip_id;
      body.export_id = peek.export_id || "";
    }
    try {
      const data = await api(
        "POST",
        "/api/docs/" + encodeURIComponent(state.slug) + "/parts",
        body
      );
      state.doc = data.doc;
      state.lastStored = data.part.part_code;
      $("composer-leaf").value = "";
      $("composer-leaf").focus();
      render();
      let msg =
        "Stored " + data.part.part_code + " · composer stays · stack grew";
      if (data.tps_chip && data.tps_chip.chip_id) {
        msg += " · doc chip " + data.tps_chip.chip_id;
      } else if (!peek) {
        msg += " · (no Machina chip)";
      }
      setStatus(msg);
    } catch (e) {
      alert(e.message);
    }
  }

  function showView(name) {
    if (
      !state.doc &&
      (name === "doc" || name === "kanban" || name === "print")
    ) {
      setStatus("Open a document first (File → Open · Ctrl+O)");
      return;
    }
    state.view = name;
    render();
  }

  async function moveSection(sectionId, delta) {
    if (!state.doc || !sectionId) return;
    const order = sectionOrder(state.doc).slice();
    const i = order.indexOf(sectionId);
    if (i < 0) return;
    const j = i + delta;
    if (j < 0 || j >= order.length) return;
    const tmp = order[i];
    order[i] = order[j];
    order[j] = tmp;
    try {
      const data = await api(
        "POST",
        "/api/docs/" + encodeURIComponent(state.slug) + "/layout",
        { section_order: order }
      );
      state.doc = data.doc;
      render();
      setStatus("Section outline reordered (intake ≠ outline)");
    } catch (e) {
      alert(e.message);
    }
  }

  function closeMenus() {
    document.querySelectorAll(".menu-drop").forEach((el) => {
      el.hidden = true;
    });
    document.querySelectorAll(".menu-top").forEach((el) => {
      el.classList.remove("open");
    });
  }

  function openMenu(name) {
    closeMenus();
    const drop = $("menu-" + name);
    const top = document.querySelector('.menu-top[data-menu="' + name + '"]');
    if (!drop || !top) return;
    drop.hidden = false;
    top.classList.add("open");
    if (name === "file") fillOpenMenu();
    syncMenuEnabled();
  }

  function fillOpenMenu() {
    const box = $("menu-open-list");
    if (!box) return;
    box.innerHTML = "";
    if (!state.docs.length) {
      box.innerHTML =
        '<div class="menu-open-empty">No .sopr files yet — New document…</div>';
      return;
    }
    for (const d of state.docs) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "menu-item";
      b.innerHTML =
        "<span>" +
        escapeHtml(d.doc_name || d.slug) +
        "</span><span class=\"muted small\">" +
        escapeHtml(d.slug) +
        "</span>";
      b.addEventListener("click", () => {
        closeMenus();
        openDoc(d.slug).catch((e) => alert(e.message));
      });
      box.appendChild(b);
    }
  }

  function syncMenuEnabled() {
    const has = !!state.doc;
    document.querySelectorAll("[data-need-doc]").forEach((el) => {
      el.disabled = !has;
    });
  }

  function runCmd(cmd) {
    closeMenus();
    switch (cmd) {
      case "new-doc":
        return newDoc();
      case "open-doc":
        $("doc-select").focus();
        setStatus("Choose a document in the strip (or File → list below)");
        return;
      case "refresh-list":
        return refreshDocList()
          .then(() => setStatus("List refreshed"))
          .catch((e) => alert(e.message));
      case "new-section":
        return newSection();
      case "focus-composer":
        if (state.view !== "doc") showView("doc");
        setTimeout(() => $("composer-leaf") && $("composer-leaf").focus(), 0);
        return;
      case "store":
        return storeFragment();
      case "view-doc":
        return showView("doc");
      case "view-kanban":
        return showView("kanban");
      case "view-print":
        return showView("print");
      case "section-up":
        return moveSection(state.activeSectionId, -1);
      case "section-down":
        return moveSection(state.activeSectionId, 1);
      case "about-doc":
        return openAboutDoc();
      case "stamp-chip":
        return stampChipOnDoc().then((r) => {
          if (r.ok) {
            setStatus("Stamped chip " + (r.chip && r.chip.chip_id));
            if (!$("about-backdrop").hidden) openAboutDoc();
          } else {
            setStatus("Stamp skipped: " + (r.reason || "unknown"));
          }
        });
      case "help-keys":
        alert(
          "sopr Documenter · keyboard\n\n" +
            "Ctrl+N          New document\n" +
            "Ctrl+O          Focus open (document strip)\n" +
            "F5              Refresh document list\n" +
            "Ctrl+Shift+S    New section\n" +
            "Ctrl+L          Focus new fragment composer\n" +
            "Ctrl+Enter      Store fragment (+ doc chip if Machina on)\n" +
            "Ctrl+1          Document mode (edit)\n" +
            "Ctrl+2          Resort (kanban)\n" +
            "Ctrl+3          Print / reader (TOC + full doc)\n" +
            "Ctrl+↑ / Ctrl+↓ Move active section in outline\n" +
            "Esc             Close menus / About\n\n" +
            "Document → About this document… · TPS chips (knowledge only)"
        );
        return;
      case "help-about":
        alert(
          "sopr Documenter\nBig Box Company\n\n" +
            "Documentation from fragmented thinking.\n" +
            "Section bins · stable SPR-#### · kanban resort.\n\n" +
            "Daniel Wake, Product Development\n" +
            "“Please put it in the doc.”"
        );
        return;
      default:
        return;
    }
  }

  function render() {
    const empty = $("view-empty");
    const docV = $("view-doc");
    const kanban = $("view-kanban");
    const has = !!state.doc;

    syncMenuEnabled();

    const printV = $("view-print");
    const hint = $("docstrip-hint");
    if (hint) {
      if (!has) {
        hint.textContent = "File → New / Open";
      } else if (state.view === "kanban") {
        hint.textContent = "Ctrl+1 edit · Ctrl+3 print";
      } else if (state.view === "print") {
        hint.textContent = "Print / reader · Ctrl+1 to edit";
      } else {
        hint.textContent = "Ctrl+2 kanban · Ctrl+3 print";
      }
    }

    if (!has || state.view === "empty") {
      empty.hidden = false;
      docV.hidden = true;
      kanban.hidden = true;
      if (printV) printV.hidden = true;
      setChrome();
      return;
    }

    empty.hidden = true;
    if (state.view === "kanban") {
      docV.hidden = true;
      kanban.hidden = false;
      if (printV) printV.hidden = true;
      renderKanban();
    } else if (state.view === "print") {
      docV.hidden = true;
      kanban.hidden = true;
      if (printV) printV.hidden = false;
      renderPrint();
    } else {
      docV.hidden = false;
      kanban.hidden = true;
      if (printV) printV.hidden = true;
      renderDoc();
    }
    setChrome();
  }

  function renderDoc() {
    const doc = state.doc;
    const sections = doc.sections || {};
    const order = sectionOrder(doc);
    const list = $("section-list");
    list.innerHTML = "";

    order.forEach((sid, idx) => {
      const sec = sections[sid];
      const row = document.createElement("div");
      row.className =
        "sec-row" + (sid === state.activeSectionId ? " on" : "");

      const ord = document.createElement("div");
      ord.className = "sec-ord";
      const up = document.createElement("button");
      up.type = "button";
      up.title = "Move section up in outline";
      up.textContent = "▲";
      up.disabled = idx === 0;
      up.addEventListener("click", (e) => {
        e.stopPropagation();
        moveSection(sid, -1);
      });
      const down = document.createElement("button");
      down.type = "button";
      down.title = "Move section down in outline";
      down.textContent = "▼";
      down.disabled = idx === order.length - 1;
      down.addEventListener("click", (e) => {
        e.stopPropagation();
        moveSection(sid, 1);
      });
      ord.appendChild(up);
      ord.appendChild(down);

      const lab = document.createElement("button");
      lab.type = "button";
      lab.className = "sec-label";
      lab.textContent = (sec.label || sid).slice(0, 40);
      lab.addEventListener("click", () => {
        state.activeSectionId = sid;
        state.lastStored = null;
        renderDoc();
        $("composer-leaf").focus();
      });

      const count = document.createElement("span");
      count.className = "count";
      count.textContent = String((sec.part_ids || []).length);

      row.appendChild(ord);
      row.appendChild(lab);
      row.appendChild(count);
      list.appendChild(row);
    });

    const active = sections[state.activeSectionId];
    $("bucket-title").textContent = active
      ? "SECTION · " + active.label
      : "SECTION";

    const stack = $("part-stack");
    stack.innerHTML = "";
    if (!active) return;

    const parts = doc.parts || {};
    for (const code of active.part_ids || []) {
      const p = parts[code];
      if (!p) continue;
      const row = document.createElement("div");
      row.className =
        "part-row" + (code === state.lastStored ? " newest" : "");
      row.innerHTML =
        '<span class="grip" title="Use Resort kanban to move">⋮⋮</span>' +
        '<div class="part-body">' +
        '<div class="part-meta">' +
        '<span class="part-code">' +
        escapeHtml(code) +
        "</span>" +
        (code === state.lastStored
          ? '<span class="tag-new">↓ just dropped under composer</span>'
          : "") +
        "</div>" +
        '<div class="part-leaf">' +
        escapeHtml(p.leaf || "") +
        "</div>" +
        "</div>";
      stack.appendChild(row);
    }
  }

  function renderKanban() {
    const doc = state.doc;
    const board = $("kanban-board");
    board.innerHTML = "";
    const sections = doc.sections || {};
    const parts = doc.parts || {};
    const order = sectionOrder(doc);

    for (const sid of order) {
      const sec = sections[sid];
      const col = document.createElement("div");
      col.className = "kanban-col";
      col.dataset.sectionId = sid;

      const head = document.createElement("div");
      head.className = "kanban-col-head";
      const title = document.createElement("span");
      title.className = "col-title";
      title.textContent = sec.label || sid;
      const ord = document.createElement("div");
      ord.className = "sec-ord";
      const idx = order.indexOf(sid);
      const up = document.createElement("button");
      up.type = "button";
      up.title = "Section up";
      up.textContent = "▲";
      up.disabled = idx <= 0;
      up.addEventListener("click", (e) => {
        e.stopPropagation();
        moveSection(sid, -1);
      });
      const down = document.createElement("button");
      down.type = "button";
      down.title = "Section down";
      down.textContent = "▼";
      down.disabled = idx >= order.length - 1;
      down.addEventListener("click", (e) => {
        e.stopPropagation();
        moveSection(sid, 1);
      });
      ord.appendChild(up);
      ord.appendChild(down);
      head.appendChild(title);
      head.appendChild(ord);
      col.appendChild(head);

      const cards = document.createElement("div");
      cards.className = "kanban-cards";
      cards.dataset.sectionId = sid;

      for (const code of sec.part_ids || []) {
        const p = parts[code];
        if (!p) continue;
        const card = document.createElement("div");
        card.className = "kanban-card";
        card.draggable = true;
        card.dataset.partCode = code;
        card.innerHTML =
          '<span class="part-code">' +
          escapeHtml(code) +
          "</span>" +
          '<div class="part-leaf">' +
          escapeHtml((p.leaf || "").slice(0, 180)) +
          (p.leaf && p.leaf.length > 180 ? "…" : "") +
          "</div>";
        card.addEventListener("dragstart", (e) => {
          card.classList.add("dragging");
          e.dataTransfer.setData("text/plain", code);
          e.dataTransfer.effectAllowed = "move";
        });
        card.addEventListener("dragend", () => {
          card.classList.remove("dragging");
          board
            .querySelectorAll(".drop-target")
            .forEach((el) => el.classList.remove("drop-target"));
        });
        cards.appendChild(card);
      }

      // drop handlers on column
      const onDragOver = (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        col.classList.add("drop-target");
      };
      const onDragLeave = () => col.classList.remove("drop-target");
      const onDrop = async (e) => {
        e.preventDefault();
        col.classList.remove("drop-target");
        const code = e.dataTransfer.getData("text/plain");
        if (!code) return;
        await movePartToSection(code, sid, e.target.closest(".kanban-card"));
      };
      cards.addEventListener("dragover", onDragOver);
      cards.addEventListener("dragleave", onDragLeave);
      cards.addEventListener("drop", onDrop);
      col.addEventListener("dragover", onDragOver);
      col.addEventListener("drop", onDrop);

      col.appendChild(cards);
      board.appendChild(col);
    }
  }

  function renderPrint() {
    const doc = state.doc;
    if (!doc) return;
    const sections = doc.sections || {};
    const parts = doc.parts || {};
    const order = sectionOrder(doc);
    const toc = $("print-toc");
    const page = $("print-page");
    toc.innerHTML = "";
    page.innerHTML = "";

    const sheet = document.createElement("div");
    sheet.className = "print-sheet";
    const h1 = document.createElement("h1");
    h1.className = "doc-title";
    h1.textContent = doc.doc_name || state.slug || "Document";
    sheet.appendChild(h1);
    const sub = document.createElement("p");
    sub.className = "doc-sub";
    sub.textContent =
      "sopr Documenter · outline view · " +
      Object.keys(parts).length +
      " fragments · Big Box Company";
    sheet.appendChild(sub);

    order.forEach((sid, idx) => {
      const sec = sections[sid];
      const label = sec.label || sid;
      const n = idx + 1;

      const tocBtn = document.createElement("button");
      tocBtn.type = "button";
      tocBtn.className = "toc-item";
      tocBtn.innerHTML =
        '<span class="toc-n">' +
        n +
        ".</span>" +
        escapeHtml(label) +
        ' <span class="count">(' +
        (sec.part_ids || []).length +
        ")</span>";
      tocBtn.addEventListener("click", () => {
        const el = document.getElementById("print-sec-" + sid);
        if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
      });
      toc.appendChild(tocBtn);

      const block = document.createElement("section");
      block.className = "print-section";
      block.id = "print-sec-" + sid;
      const h2 = document.createElement("h2");
      h2.textContent = n + ". " + label;
      block.appendChild(h2);

      const pids = sec.part_ids || [];
      if (!pids.length) {
        const empty = document.createElement("p");
        empty.className = "print-empty";
        empty.textContent = "(no fragments in this section)";
        block.appendChild(empty);
      } else {
        // print order: reverse of compose stack (oldest first reads better)
        // part_ids[0] is newest — print oldest→newest for document flow
        const readOrder = pids.slice().reverse();
        for (const code of readOrder) {
          const p = parts[code];
          if (!p) continue;
          const frag = document.createElement("div");
          frag.className = "print-frag";
          frag.innerHTML =
            '<span class="frag-code">' +
            escapeHtml(code) +
            "</span>" +
            escapeHtml(p.leaf || "");
          block.appendChild(frag);
        }
      }
      sheet.appendChild(block);
    });

    page.appendChild(sheet);
  }

  async function movePartToSection(partCode, toSectionId, beforeCard) {
    const doc = state.doc;
    if (!doc) return;
    const sections = doc.sections || {};
    // rebuild columns from current + move
    const columns = [];
    for (const sid of sectionOrder(doc)) {
      const sec = sections[sid];
      let pids = (sec.part_ids || []).filter((c) => c !== partCode);
      if (sid === toSectionId) {
        if (beforeCard && beforeCard.dataset.partCode) {
          const before = beforeCard.dataset.partCode;
          const idx = pids.indexOf(before);
          if (idx >= 0) pids.splice(idx, 0, partCode);
          else pids.unshift(partCode);
        } else {
          pids.unshift(partCode);
        }
      }
      columns.push({
        section_id: sid,
        label: sec.label,
        part_ids: pids,
      });
    }
    try {
      const data = await api(
        "POST",
        "/api/docs/" + encodeURIComponent(state.slug) + "/layout",
        {
          section_order: sectionOrder(doc),
          columns: columns,
        }
      );
      state.doc = data.doc;
      renderKanban();
      setStatus(
        partCode + " → " + (sections[toSectionId] || {}).label + " · code unchanged"
      );
    } catch (e) {
      alert(e.message);
    }
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // wire — menubar
  document.querySelectorAll(".menu-top").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const name = btn.getAttribute("data-menu");
      const drop = $("menu-" + name);
      if (drop && !drop.hidden) {
        closeMenus();
      } else {
        openMenu(name);
      }
    });
    // Windows romance: hover across open menus
    btn.addEventListener("mouseenter", () => {
      if (document.querySelector(".menu-top.open")) {
        openMenu(btn.getAttribute("data-menu"));
      }
    });
  });
  document.querySelectorAll(".menu-item[data-cmd]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (btn.disabled) return;
      runCmd(btn.getAttribute("data-cmd"));
    });
  });
  document.addEventListener("click", () => closeMenus());
  $("menubar").addEventListener("click", (e) => e.stopPropagation());

  $("about-close").addEventListener("click", closeAboutDoc);
  $("about-backdrop").addEventListener("click", (e) => {
    if (e.target === $("about-backdrop")) closeAboutDoc();
  });
  $("about-stamp").addEventListener("click", () => runCmd("stamp-chip"));
  document.querySelector(".about-dialog") &&
    document
      .querySelector(".about-dialog")
      .addEventListener("click", (e) => e.stopPropagation());

  $("doc-select").addEventListener("change", (e) => {
    openDoc(e.target.value).catch((err) => alert(err.message));
  });
  $("btn-empty-new").addEventListener("click", newDoc);
  $("btn-empty-refresh").addEventListener("click", () => {
    refreshDocList().catch((e) => alert(e.message));
  });
  $("btn-store").addEventListener("click", storeFragment);
  $("composer-leaf").addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      storeFragment();
    }
  });

  // keyboard shortcuts
  document.addEventListener("keydown", (e) => {
    const mod = e.ctrlKey || e.metaKey;
    const tag = (e.target && e.target.tagName) || "";
    const inField =
      tag === "TEXTAREA" || tag === "INPUT" || tag === "SELECT";

    if (e.key === "Escape") {
      closeMenus();
      if (!$("about-backdrop").hidden) closeAboutDoc();
      return;
    }
    if (e.key === "F5") {
      e.preventDefault();
      runCmd("refresh-list");
      return;
    }
    if (!mod) return;

    // allow Ctrl+Enter in composer
    if (e.key === "Enter" && inField && tag === "TEXTAREA") {
      e.preventDefault();
      runCmd("store");
      return;
    }

    const k = e.key.toLowerCase();
    if (k === "n" && !e.shiftKey) {
      e.preventDefault();
      runCmd("new-doc");
    } else if (k === "o") {
      e.preventDefault();
      runCmd("open-doc");
    } else if (k === "s" && e.shiftKey) {
      e.preventDefault();
      runCmd("new-section");
    } else if (k === "l" && !inField) {
      e.preventDefault();
      runCmd("focus-composer");
    } else if (k === "1") {
      e.preventDefault();
      runCmd("view-doc");
    } else if (k === "2") {
      e.preventDefault();
      runCmd("view-kanban");
    } else if (k === "3") {
      e.preventDefault();
      runCmd("view-print");
    } else if (e.key === "ArrowUp" && !inField) {
      e.preventDefault();
      runCmd("section-up");
    } else if (e.key === "ArrowDown" && !inField) {
      e.preventDefault();
      runCmd("section-down");
    }
  });

  refreshDocList()
    .then(() => {
      setStatus(
        "sopr · Ctrl+1 edit · Ctrl+2 kanban · Ctrl+3 print · Ctrl+↑↓ section outline"
      );
      render();
    })
    .catch((e) => setStatus("error: " + e.message));
})();

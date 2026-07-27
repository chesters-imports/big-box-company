```
=================================================
  BIG BOX COMPANY · PRODUCT SKU
  sopr Documenter
=================================================
```

**Product name:** sopr Documenter  
**Studio:** Big Box Company  
**Product developer (diegetic):** Daniel Wake  
**Status:** **v0 SHIPPED** · fluorescent lights **ON** · Figma mocks + product law implemented

**Figma (proper boring company process):**  
[BBC · sopr Documenter · v0 Mockups](https://www.figma.com/design/Qgfv39XFSFWhjNlE2PRFj6)

| Frame | Job |
|-------|-----|
| 01 Document open | sections rail + **inline composer at top of bucket** · frags drop below |
| 02 Add fragment | **primary = inline top-of-bucket** (popover demoted) · no notes field |
| 03 Resort | **the product** — drag/move; IDs do not rename |
| 04 Empty state | “No document selected. Please select a document.” |

Daniel: mockups **before** crit from done products. DATBOX may continue their toy theater; we approve frames first.

#### Hands / Figma comment (filed · -dw)

> will this be modal pop over? we can't leave the page. I'd rather a pop over or a drop down chip off the add or writing the fragment inline - additional notes lines seem like they will muddy this. you have a note? make another sopr -/dw  
> love the resort kanban

**Product law from that:**

| Decision | Law |
|----------|-----|
| **Stay on page** | Add fragment must **not** navigate away. No full-page form route. |
| **Chrome for add (Hands preferred)** | **Inline composer always at the TOP of the active section bucket.** New fragments **drop in below** the composer as you store them — rows push down; you keep typing at the top. Popover/chip off global Add is secondary at best; modal-as-page is forbidden. |
| **No “optional notes” field** | Muddies the leaf. A note is **another sopr fragment** (or another section), not a second textarea on the same act. |
| **Resort kanban** | **Loved. Locked.** Columns = sections; cards = parts with stable codes. |

---

### One-liner (catalog)

> For all your **very hard to compile** documentation needs.

### Elevator pitch (still boring)

**sopr** is the concept of making **documentation from fragmented thinking**.

You do not write the doc.  
You **dump scraps under header bins**.  
Later, you **resort the rows** until an outline stops lying.  
Then — and only then — you produce documentation.

This is Hands’ version of **Office / Confluence**: section structure, movable leaves, export when ready. No collaboration theater. No emoji reactions. Full Daniel Wake.

---

### Problem we solve (HR-approved)

| You have | We do not pretend |
|----------|-------------------|
| Polymath dump brain | That you outline first |
| Headers that made sense *in the moment* | That intake order is final |
| A need for a real doc after compact | That chat heat is a store |

**sopr Documenter** is pre-doc structure:  
**section bins + ordered frags → resort → outline → exportable document.**

Not lore cards. Not shot frames. Not glass walks.  
**Timber for documentation.**

---

### How it works (operator view)

1. **Open / create a document bag** (one topic, one outline-in-progress).  
2. **Add fragment:** section heading + leaf (the scrap).  
3. **Bin:** leaf lands under that header; IDs stay stable (`sectionslug-0001` energy).  
4. **Resort (the whole point):** move frags between sections; reorder within sections.  
5. **View** as a binned document (headers + leaves).  
6. **Later:** export outline / doc when the structure is honest.

Intake order ≠ final outline. That is the product.

#### Product law · part codes (Hands / -dw)

**SOPR part codes must survive resort.**  

Old failure: encoding the **section into the chunk id** (`miseryasenemy-0001` as identity of the *leaf*). Move the frag → constant fucking rename of bits.  

**Production rule:** part code is a **stable identity** (opaque stem + seq, or uuid-ish unit). Section membership is a **field / parent pointer**, not baked into the code. Resort = re-bin and re-order, **never rename the part**.

Thank you. —dw

---

### Lineage (not re-host myPI)

Honors **soprBASIC** / `.sopr.frags.json` paper shape from Builds:

- `SECTION[slug]` → LABEL, NOTES, SOPERS[]  
- each SOPER → ID, FRAG, AGENT, METADATA  

v0 ROM restored the bin document.  
v0.1 (below) adds **document-level TPS chip tracking** — not narrative mat stamps.

---

### Relation to other ALICE products

| Product | Job |
|---------|-----|
| **loreBOX** | what is true / claimed (world or project *cards*) |
| **shotBOX** | moments / frames |
| **Machina** | walk glass, stamp time |
| **sopr Documenter** | **compile thinking into a document outline** |

You may use sopr to *assemble* “why Chester exists / why we say export / how the platform works,” then mint stable claims into lore decks if you want. Different SKUs. Different makers. Daniel does not care; he wants the outline done by Friday.

#### Product law · TPS chips on sopr (Hands + DW · approved for next ship)

**Product documentation production — not narrative boxhood.**  
If we need story books with per-line archaeology, **that is another app.** Sopr stays boring.

| # | Law |
|---|-----|
| **1** | Store **TPS chip identity** only when tracking glass. Not ven codes, not who-ledger, not full TPS report cosplay. |
| **2** | Chips attach to the **document**, not each fragment. A **`tps_chips` bin** (or equivalent) = chips used in production of this doc while whispering / walking glass. |
| **3** | **No dupes.** Key by `chip_id`. Whisper twice → same entry; may bump `last_seen_at` only. |
| **4** | **No per-frag `source_chip`.** Not even for “direct copy.” Dramatic and useless for product docs: the chip *is* already the per-message bank — if someone cares, open the chip. Tracking whether SPR-0004 came from `001-OT-674.3.2` vs `.3` does **not** matter here. |
| **5** | **Not front-loaded on the production surface.** Compose / kanban / print stay about outline and leaves. Chip knowledge lives in **Document → About this document…** (menu) — tracking/knowledge drawer, not printed chrome, not a always-on sidebar badge stack. |

**About this document (UX):**

- Menu: **Document → About this document…** (dialog / panel)  
- Shows: doc name, slug, part/section counts, **list of `tps_chips`**, house meta  
- **Not** free-printed into Ctrl+3 reader body by default  
- **Not** on the compose bucket header as primary UI  

**Whisper (when corded):** Machina current chip → append to open doc’s `tps_chips` (deduped). Optional: store a leaf the same act — leaf still has no chip field.

**Schema sketch (implement next):**

```json
"tps_chips": [
  {
    "chip_id": "001-OT-008.3.0",
    "export_id": "001-OT-008.3",
    "first_seen_at": 0,
    "last_seen_at": 0
  }
]
```

`chip_id` required · `export_id` optional convenience · times optional · **no vencodes**.

— Hands / DW · freeze for approval · then run
[ approved -dw 2026-07-25 21:39]

---

### House layout (lights on)

```text
sopr-documenter/
  README.md
  prod/
    box_sys/           server.py · index.html · app.css · app.js
    safe_box/          *.sopr documents
    run-sopr.bat       Deck Host ROM
    run-sopr-browser.bat
    run-in-deck-host.py
```

### Run

| How | Command |
|-----|---------|
| **ROM (Deck Host)** | double-click `prod/run-sopr.bat` · **profile `office`** (1280×800, not datbox short) |
| **Browser only** | `prod/run-sopr-browser.bat` or `cd prod/box_sys && python server.py` |

| URL | |
|-----|--|
| http://127.0.0.1:42950/ | desk |
| http://127.0.0.1:42950/api/health | health |

### House format · `.sopr`

Boring specialized file (not DATBOX cosplay):

- `house: BIGBOX` · `product: sopr-documenter`
- **`parts`**: map of **stable** `SPR-####` → part object — **no chip on the part**  
  - **`block`**: `text` (default) · `image` · `table`  
  - **text:** `leaf`, optional `as_pre` (monospace `<pre>` for ASCII / code)  
  - **image:** `image_id` (vault `safe_box/_media/`), `leaf` = caption; upload via composer  
  - **table:** `table: { header, rows[][] }` text-only grid (Obsidian-style scan); optional `leaf` note; full grid editor on Edit  
  - Images **in cells** not in this slice — use a separate image frag
- **`sections`**: map of `sec-####` → `{ label, part_ids: [] }` (order in bucket)
- **`section_order`**: outline order of sections (intake ≠ outline)
- **`tps_chips`**: **document-level** list of chip_ids used in production (deduped) — **v0.1**
- Resort updates **membership + order only** — **never renames part codes**

### Surface map

1. Empty: no document selected  
2. Document: section rail + **inline composer at top of bucket** + stack below · section ▲▼  
3. Resort kanban: drag frags · section ▲▼ on columns  
4. Print / reader (Ctrl+3): TOC + full outline — **not** a TPS billboard  
5. **About this document…** (menu): meta + **tps_chips** list — knowledge only

#### Product law · we are not DATBOX (Hands / -dw)

Yes. Consider a **more boring approach**.  

We do **not** have to copy DATBOX. Those guys make **toys** (mats, bags, cute stems). **We make real software** here at Big Box — document industrial, office spine, maybe even a dull path layout if that’s more honest than cosplaying `.whateverbox`.  

DATBOX energy optional. **Boring correctness preferred.**  

—dw

---

### v0 vs not-v0

| v0 (honest sopr) | Not v0 |
|------------------|--------|
| Create/open bag | Full CCC |
| Add frag **inline at TOP of section bucket** (stack drops below) | Full-page form / leave-doc modal / notes sidecar / popover-as-primary |
| View binned doc | Mega desk that owns the site |
| Reorder + move between sections (**kanban**) | “AI writes the wiki” |
| House format on disk | Baking romance chrome into Big Box |
| One leaf = one sopr | “Additional notes” second field muddying the act |
| Doc-level `tps_chips` (deduped chip_id) | Per-frag source_chip / ven / “was SPR-x from chip y?” drama |
| About document (menu) for chip list | Front-loading chips on compose / print surface |

---

### Taglines approved by Marketing (none of them are fun)

- *For all your very hard to compile documentation needs!*  
- *Turn fragmented thinking into section bins. Resort later. Pretend you planned it.*  
- *We put the “sopr” in “we finally finished the outline.”*  
- *Documentation industrial. Not a lifestyle brand.*

---

### Leave-off

- Maker: **Big Box Company**  
- SKU: **sopr Documenter**  
- Job: frags → bins → **resort** → outline → docs  
- **Part codes stable** — section not baked into id (old failure, avoid)  
- **Machina / glass** — doc-level `tps_chips` only; no per-frag chip; no ven  
- **About document** — menu knowledge drawer; not production chrome  
- **Boring over DATBOX cosplay** — real software, not toy bags by default  
- **Add = inline top of bucket** — composer always at top of active section; stored frags stack below; stay on page  
- **No notes field** — note? another sopr  
- **Resort kanban** — loved / locked · section outline reorder too  
- Scaffold: **v0 shipped** · **v0.1 live** — `tps_chips` + About doc + Machina peek on store

*Big Box Company · sopr Documenter · Internal product page*  
*Daniel Wake · “Please put it in the doc.”*  
*Hands memos filed · v0 fluorescent · TPS chip law 2026-07-25*


## [ sign off /dw @ 2026-07-25 2026-07-25 ]
INFORM IF ANY EDITS MADE PAST THIS POINT FOR SIGN OFF AGAIN! -dw

### Edits after sign-off

**2026-07-25 · inline create flow** — signed by Hands.  

**2026-07-25 · v0 BUILD** — `prod/box_sys` + `.sopr` store + Deck Host run · agent shipped after Hands “we can build?!”


## [ sign off /dw @ 2026-07-25 20:53 ]
INFORM IF ANY EDITS MADE PAST THIS POINT FOR SIGN OFF AGAIN! -dw
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

v0 ROM should **restore the bin document**, not the ledger-flattened generic post row.  
Shared crate cords (TPS / Charlie / Chester) are optional later — **not required for v0**.

---

### Relation to other ALICE products

| Product | Job |
|---------|-----|
| **loreBOX** | what is true / claimed (world or project *cards*) |
| **shotBOX** | moments / frames |
| **Machina** | walk glass, stamp time |
| **sopr Documenter** | **compile thinking into a document outline** |

You may use sopr to *assemble* “why Chester exists / why we say export / how the platform works,” then mint stable claims into lore decks if you want. Different SKUs. Different makers. Daniel does not care; he wants the outline done by Friday.

#### Product law · Machina / glass (Hands / -dw)

**REMEMBER.** Consider **interactivity with TPS Machina**.  

Much documentation will **emerge from glassboxes** — walk chips, dump thinking into section bins, stamp when/where a frag was born. Not required for first fluorescent flicker, but the product is **not** a closed office silo. Glass → sopr is a first-class future cord.  

—dw

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
- **`parts`**: map of **stable** `SPR-####` → `{ leaf, section_id, … }`
- **`sections`**: map of `sec-####` → `{ label, part_ids: [] }` (order in bucket)
- **`section_order`**: column order for kanban
- Resort updates **membership + order only** — **never renames part codes**

### v0 surface (matches Figma + Hands)

1. Empty: no document selected  
2. Document: section rail + **inline composer at top of bucket** + stack below  
3. Resort kanban: drag cards between section columns

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
- **Machina / glass** — future cord; docs emerge from glassboxes  
- **Boring over DATBOX cosplay** — real software, not toy bags by default  
- **Add = inline top of bucket** — composer always at top of active section; stored frags stack below; stay on page  
- **No notes field** — note? another sopr  
- **Resort kanban** — loved / locked  
- Scaffold: **ON · v0 shipped 2026-07-25**  

*Big Box Company · sopr Documenter · Internal product page*  
*Daniel Wake · “Please put it in the doc.”*  
*Hands memos filed · v0 fluorescent · 2026-07-25*


## [ sign off /dw @ 2026-07-25 2026-07-25 ]
INFORM IF ANY EDITS MADE PAST THIS POINT FOR SIGN OFF AGAIN! -dw

### Edits after sign-off

**2026-07-25 · inline create flow** — signed by Hands.  

**2026-07-25 · v0 BUILD** — `prod/box_sys` + `.sopr` store + Deck Host run · agent shipped after Hands “we can build?!”


## [ sign off /dw @ 2026-07-25 20:53 ]
INFORM IF ANY EDITS MADE PAST THIS POINT FOR SIGN OFF AGAIN! -dw
# ReqRep · design lock · 2026-07-30 (morning)

**Product:** ReqRep (no dash) · `CO.BBC-002-RR` · Big Box Company  
**Path:** `ALICE_BOX/big-box-company/reqrep/`  
**Not:** Confluence cosplay · not Terminals-as-REQ-bus · not sonaBOX  
**Sign-off authority:** Hands / Charlie (not a foreign agent)

Folder note: mock may also sit under legacy `req-rep/` if Windows had the dir open; canon stem is **`reqrep`**.

---

## One line

ReqRep is the Big Box **request bay**: discuss and scope a product ask, **lock scope**, then seal a second artifact — **Product prep for an agent** — that Hands signs. Only that sealed prep is law for first slice.

---

## Work-order lane law (absolute · Hands 2026-07-30)

Tickets inside a case carry a **work lane**. Agent **must not implement** (code, layout ship, “take READY IMPLEMENT and build”) unless the lane is:

| Lane | Who owns the pile | Agent implement? | Agent reply? |
|------|-------------------|------------------|--------------|
| **DISCUSSION** | **Shared · active talk** | **No** | **Yes** — discuss, clarify, do not freestyle build |
| **PAUSED** | Hold / later | **No** | **No** — do not thrash; not active this cycle |
| **RUN** | **Agent** work queue | **Yes** | optional |
| **TEST** | **Hands QA bag** | **No freestyle** | only if asked |
| **CLOSED** | Done for agent (was **IN**) | **No** | **No** |

### Handoff (absolute · Hands 2026-07-30)

When agent **ships** work against a **RUN** ticket, agent **moves that ticket to TEST** (lane only — not a seal).  
Hands QA → seal, or flip back to **RUN** if more cut needed.  
**CLOSED** = agent done without needing QA thrash (optional); seal still separate.

Seals (AGREED / IMPLEMENTED) are separate from lane.  
**DISCUSSION** = actively discussing (agent should check and reply). **PAUSED** = do not reply.  
Legacy `run_test` → **RUN**. Legacy `in` → **CLOSED**.

---

## Cognitive / Hands law (do not regress)

Hands runs **hot multi-track** attention. The desk (Deck Host rail, warm servers, ROM cases) is **fun and orienting** — that is product, not decoration.

**Read vs form is not polish.** An always-open form field is cognitively hostile here:

- Either it **demands fill-out** (false task), or  
- It **stops being readable information** (eyes bounce; nothing parses).

So side panes and meta must be **read-first**: quiet key/value or prose readout by default; **Edit → Save / Cancel** only when Hands chooses. “The information is technically there in inputs” is **not** good enough.

Same spirit: Deck Host from first ship (launcher recipe + `run-in-deck-host.py`) so review happens in the glass that already holds focus — not naked Chrome + orphan servers.

*Filed Hands morning talk 2026-07-30 · after intake form feedback.*

---

## Pipeline (ordered)

1. **Discussion (bay)**  
   Chunked working sheet. Comments hang on chunks (paragraph / blank-line grain; not freeform stickies first). Expand/collapse threads.  
   Optional: **lock discussion** when talk is done enough to write scope (no more new fight on the draft, or softer: freeze comment entry while scope is drafted — product can choose exact rule later).

2. **Scope written**  
   Scope body is reviewed and edited in the bay until it reads true.

3. **Lock scope**  
   Scope freezes. Further changes require unlock / reopen (process, not silent chat edit).

4. **Agent rewrite → second artifact**  
   Working agent (desk agent, not “random foreign model”) **rewrites** locked scope + settled discussion into a clean **Product prep for an agent**.  
   This is a **sibling artifact**, not in-place strip of comments.

5. **Hands sign-off**  
   Charlie/Hands marks the prep **final / accepted**.  
   That stamp is the gate: first slice may begin against prep only.

6. **Leave the bay**  
   Prep is the build contract. Discussion + locked scope remain archive.

```
[ discussion  ] → [ scope draft ] → [ SCOPE LOCKED ]
                                            ↓
                              agent rewrites Product prep
                                            ↓
                              Hands / Charlie signs off
                                            ↓
                              first slice allowed
```

---

## Final design choice (pinned)

| Choice | Decision |
|--------|----------|
| Final form | **B — second artifact** |
| Who rewrites | Desk **agent** (this desk’s agent) |
| Who accepts | **Hands / Charlie** sign-off |
| Sticky notes v0 | **No** — chunk + thread under chunk |
| Chunk grain v0 | **Paragraph / separator**, not every line |
| Implement from | **Signed Product prep only** |

---

## Universe chrome (intentional, not SaaS bloat)

Big Box is a software shop in the lore. Meta fields make the tool feel like company process and also scale when many REQs sit before products exist.

### Intake fields (world face — locked)

| Field | Meaning |
|--------|---------|
| **Type** | `REQ` (new product/SKU) · `MOD` (change existing) · `ADDENDUM` |
| **SKU** | Chip / ROM code (e.g. `CO.BBC-002-RR`) |
| **Product** | Product name (e.g. `ReqRep`) |
| **Title line** | **Composed only** — not free typed. Shape: `REQ: ROM SKU CO.BBC-002-RR "ReqRep"` |
| **Producer** | ROM house (Big Box Company, DatBox Studio, …) |
| **Hands** | Face filing (e.g. Daniel Wake) |
| **Priority** | As usual |

**Bay file code** (`REQ-001`) is the case id in the bay — not the product SKU.

**Not intake:** Free-text title that crams type+SKU+name. Client. Employee. Agent diary titles.

Also on case: status along pipeline.

Dashboard / list of requests is justified: backbone queue of work **before** products exist.

**Not required for first slice of ReqRep itself:** Analytics empire, multi-tenant workspaces, social likes. The Firefly mock is **genre**, not wireframe law.

---

## Discussion model (recap)

- One **active discussion sheet** (chunked).  
- Comments per chunk; collapse by default when quiet; resolve threads.  
- Scope is written (from / after discussion), then **scope lock**.  
- Product prep is the **clean agent-facing rewrite** after lock.  
- Sign-off is human (Charlie).

---

## Reference pattern · loreBOX planner (house gold)

**Source:** `datbox-studio/lore-box/docs/lore-box-planner.md` (ticket #429.B29).  
This is one of the times Hands and wire actually **talk in line, properly**, about production — not chat fog.

**Compare (thinner):** `shot-box/docs/shot-box-planner.md` uses inline `` `hands: …` `` marks on wire prose. Useful, but loreBOX’s **callout blocks + reply codes + freeze** is the clearer back-and-forth.

### What that file actually does (map for ReqRep)

| Block / move | Who | Job |
|--------------|-----|-----|
| `[!info] PRODUCT REQUEST TICKET` | Client / Hands seed | Raw ask (universe ticket face) |
| Wire sign-in | Agent | Who’s on the job |
| `[!TIP] WORK PLANNER` | Agent | Read of the ticket — structured rewrite into phases, fields, out-of-scope |
| Open questions table | Both | Hands column ↔ Wire lock column (paired, not free chat) |
| Options menu (§7.4 style) | Agent offers · Hands picks | Closed choices instead of infinite debate |
| `[!success] … HANDS` + **REPLY id** | Hands | Numbered answers, ADDs, closing confirmation |
| Agent ACK block | Agent | Locks what Hands said into the board |
| **PHASE … FROZEN** + frozen spec | Both | Clean sealed writeup — sibling energy to **Product prep** |

Reply stamps in that doc (`65D.35A9`, `877.33DG`) are **hand-side receipts**, not decoration. Freeze only after Hands closing notes.

### Closing blocks (Hands law for ReqRep)

When a discussion **begins** on a topic (chunk / section / question set) and goes back and forth:

1. Thread stays **open** while Hands ↔ agent trade on that block.  
2. When agreement is real, **Hands signs the block closed** — explicit “this is agreed upon” (house words can be **AGREED** / **FROZEN** / **CLOSE** + optional reply stamp).  
3. Closed block is **read-only for scope purposes** (reopen is a deliberate act, not a silent edit).  
4. Agent must not treat open-block comments as build law.  
5. Whole-case **scope lock** freezes **purpose text only** (workboard mode): Hands may still **add tickets**, comment, lane, stamp. Unlock purpose only to rewrite the case purpose. (Legacy product-request path still uses lock before prep generate — tickets stay open either way.)  
6. Then agent writes **Product prep**; Hands signs the prep (second seal, case-level).

So: **block-level Hands close** (discussion grain) + **case-level Hands sign-off on Product prep** (leave-the-bay grain). Two seals, different jobs.

```
chunk/section thread open
        ↕ Hands ↔ agent
Hands: CLOSE / AGREED (block sealed)
        …
all needed blocks closed → scope lock
        → agent Product prep
        → Hands signs prep
        → first slice
```

### What not to cargo-cult from the MD file

- Obsidian callout syntax is **mood**, not the only UI. ReqRep should make the same **roles and seals** as first-class UI (speaker, open/closed, reply stamp), not require raw markdown callouts forever.  
- ShotBOX-style `` `hands:` `` inline is a lighter cousin for small notes — loreBOX blocks are the **proper** production talk pattern.

---

## Anti-patterns (from last night)

- Building from chat fog or unmarked Terminals/FK REQ paste.  
- Treating discussion comments as scope.  
- Agent “just shipping” without signed Product prep.  
- Collapsing schema tables into product UI without a sealed prep (sonaBOX miss).

---

## Naming

- **Product:** ReqRep (like the Cat entry; datBOX family is *look*, not forced `reqBOX`).  
- **Path:** `reqrep/` — no ornamental hyphen (`req-rep` was Firefly/corporate dash habit).  
- Chip: `CO.BBC-002-RR`.

---

## First product slice — SHIPPED 2026-07-30 (morning)

Runnable desk so Hands can reply **in product**, not only in chat MD.

| | |
|--|--|
| Path | `reqrep/prod/` |
| Port | **42962** |
| Run | `prod/run-reqrep.bat` (Deck Host) · browser bat too |
| Store | `prod/safe_box/cases.json` |
| Look | GRM family (IBM Plex · gold · BIGBOX chrome · light/dark) |
| Cat | `reqrep-414b` · status **desk** · launcher_show true |

Includes: list · intake meta · chunks · Hands/Agent speak · Close AGREED · reopen · scope lock · generate prep (local template, not LLM) · Hands sign prep · seed REQ-001.

---

## Open (small, not blockers)

- Whether “lock discussion” = all blocks closed, or a separate case-level switch.  
- Product prep as free MD vs fixed template (Job / In / Out / First slice / Non-goals).  
- ID scheme for cases + reply stamps (loreBOX-style codes vs simple counters).  
- UI chrome for open vs closed blocks (collapse closed by default?).

*Locked in talk with Hands morning 2026-07-30. Mock: `generic-product-mockup.png` (mood only). Planner ref: lore-box-planner.md.*

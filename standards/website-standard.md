# The website standard — a candidate dimension set for a website job's Specialist

**Status:** a candidate standard for Plumbline website jobs. It is **not** law and it is **not** authoritative:
the Specialist named in a job adopts or trims it, sets the anchors, and **declares it in the packet**. What it
is: the four questions a website has to answer — *fitness for purpose, copy, information architecture and call
to action* — turned into dimensions with a **channel** and a **hardness** each, so a job can be scored rather
than admired.

**The one rule this artifact is built on.** Plumbline's own vocabulary: a **DOCUMENT** is machine-checkable, a
**PRIOR** is something a person said — traceable, but not checkable. Almost every book below is PRIOR. That is
not a mark against them; it is what they *are*, and it decides what they can be used for. **A dimension whose
only ground truth is a PRIOR cannot be the sole basis of a score.** The authority tells you what to look at; the
measurement decides whether you are right.

---

## 1. The authorities, classified — because the classification is the useful part

| Source | Hardness | What it is actually for |
|---|---|---|
| Claude Hopkins, *Scientific Advertising* (1923) | PRIOR | reason-why copy; the case for measuring at all |
| John Caples, *Tested Advertising Methods* | PRIOR | headlines as the unit that carries the response |
| Eugene Schwartz, *Breakthrough Advertising* | PRIOR | market awareness decides the copy, not taste |
| David Ogilvy, *Ogilvy on Advertising* | PRIOR | brand + long-form reason-why |
| **Joanna Wiebe / Copyhackers** | PRIOR, **with a method that produces DOCUMENT** | conversion copywriting: interviews and voice-of-customer first — the transcripts are filed evidence |
| April Dunford, *Obviously Awesome* | PRIOR | positioning is the layer above copy |
| Donald Miller, *StoryBrand* | PRIOR | message hierarchy; useful as a checklist, thin as evidence |
| Rosenfeld, Morville & Arango, *IA for the Web and Beyond* | PRIOR | organization, labelling, navigation, search |
| Jesse James Garrett, *Elements of User Experience* | PRIOR | the planes — each layer answers a different question |
| **GOV.UK Service Manual · Design System · Sarah Richards, *Content Design*** | **DOCUMENT-adjacent** | plain language, one action per page, pattern reuse — published guidance with the research behind it, and free |
| Jakob Nielsen / NN/g | PRIOR **derived from** measured studies | ten heuristics: the cheapest quality floor that exists |
| Steve Krug, *Don't Make Me Think* | PRIOR | one obvious action; no thinking required |
| Caroline Jarrett | PRIOR | forms, specifically — if the call to action is a form |
| Peep Laja / CXL, Chris Goward | PRIOR | the rigorous end of the conversion-practitioner space |
| **Ron Kohavi, *Trustworthy Online Controlled Experiments*** | **DOCUMENT** | the method: sample size, guardrail metrics, and the traps |
| **WCAG 2.2 AA · schema.org · sitemap.xml · robots.txt** | **DOCUMENT** | actual specifications; a tool can decide these |

**Where they disagree, and it matters:** the heuristics school (Nielsen, Krug) treats its rules as settled; the
experimental school (Kohavi, CXL) treats nothing as known until it is tested on your own traffic. Both are
right about different things — the heuristics are **priors**, and a prior is a place to start, not a verdict.
This is the same distinction Plumbline already draws, and it is why this standard insists on channels.

---

## 2. The dimension set

Each dimension: **what it asks · the channel that answers it · hardness**. `MECH` = a tool or a script can
decide it. `READER` = a person (or a model) must judge it, with a script and a control so the judgement can
fail. `MEASURED` = the users decide it, on the live site.

### A. Fitness for purpose — the job's own done-test

- **A1 · The page's single purpose is identifiable from the page alone.** Channel: a reader test — five
  strangers, shown the page for five seconds, asked what it is for and what to do next. Pass = the stated
  purpose matches the packet's, in the readers' words. Hardness: READER (a real test with a control page that
  is known to fail).
- **A2 · The user's task can be completed.** Channel: a task-based session with the target reader, plus the
  site's own analytics once live. Hardness: READER + MEASURED.
- **A3 · The stated done-test is declared before the work exists** — what "fits the purpose" means, in the
  Owner's and Buyer's words, with the failure condition named. Hardness: DOCUMENT (it is either in the packet
  or it is not).

### B. Copy

- **B1 · Every claim traces to a filed voice-of-customer source or an Owner decision.** Channel: a traceability
  pass — each headline and promise either quotes a filed customer sentence (review, support email, interview
  transcript, search query) or cites the Owner's declaration. Hardness: **DOCUMENT**, and this is the single
  most valuable dimension in the set, because it converts "good copy" into a checkable claim.
- **B2 · One claim per paragraph, and no claim without a reason.** Channel: READER, with the reader asked to
  state each paragraph's claim in one sentence. Hardness: READER.
- **B3 · The market-awareness stage is declared, and the lead matches it.** Channel: the packet declares the
  stage (Schwartz's five); a reader judges whether the first screen speaks to that stage. Hardness: PRIOR +
  READER (the stage is a judgement; the match is checkable against it).
- **B4 · Plain language**: no sentence a reader cannot parse once, no idiom doing load-bearing work. Channel:
  READER + a readability pass as a *screening* tool only (never as the verdict). Hardness: READER.

### C. Information architecture

- **C1 · One primary action per page, reachable in one click from that page.** Channel: MECH — parse the link
  graph and the DOM; a page with two primary actions fails.
- **C2 · Every page is reachable, and nothing is orphaned.** Channel: MECH — crawl from the root; orphans and
  unreachable nodes fail.
- **C3 · Depth is bounded and declared** (e.g. any page within three clicks of the home page). Channel: MECH.
- **C4 · Navigation is identical in content across pages, and differs only where the packet declares it.**
  Channel: MECH — diff the nav across rendered pages.
- **C5 · Labels are the users' words.** Channel: a label test with target readers, or the search-query
  vocabulary from B1. Hardness: READER, grounded in DOCUMENT (`MEASURED` once live search exists).

### D. Call to action

- **D1 · Exactly one primary CTA per page; secondary actions are visually and structurally subordinate.**
  Channel: MECH (DOM + computed styles).
- **D2 · The CTA states the outcome, not the mechanism.** *"Upgrade to Unlock"*, never *"Tool Locked"* — a
  restriction is not an invitation. Channel: READER, with the CTA's outcome phrase compared against the packet's
  stated purpose.
- **D3 · Every CTA is instrumented, and the event fires.** Channel: MECH — the event exists, fires on a real
  click, and arrives in the analytics with the page and the variant attached. **A CTA nobody can measure is a
  decoration.**
- **D4 · The action's cost is stated where the action is** (money, time, data, commitment). Channel: READER —
  the reader states what they expected to give up, before and after.

### E. AI-friendliness — so an agent can serve the user well

This group exists because the site's second audience is a machine acting for the first. It is where the
**DOCUMENT** dimensions concentrate, and where a website job can be scored hardest for the least argument.

- **E1 · Semantic HTML, one `h1` per page, and a heading outline that stands alone.** An outline read without
  the body should still say what the page is and what it offers. Channel: MECH.
- **E2 · Structured data for the entity, the page type and the actions** (`schema.org` JSON-LD), valid and
  consistent with what the page says. Channel: MECH — validate; and cross-check a claim in the JSON-LD against
  the visible page, because structured data that disagrees with the page is worse than none.
- **E3 · Machines can enumerate the site**: `sitemap.xml`, `robots.txt`, and — **as a convention, not a
  standard** — `llms.txt` or its equivalent, *declared either way*. Channel: MECH (presence and validity);
  the convention is declared, never assumed.
- **E4 · The content is in the HTML.** A fetch with JavaScript disabled returns the content, not an empty shell.
  Channel: MECH — fetch without a JS engine and compare against the rendered text.
- **E5 · Every section has a stable anchor, and a deep link resolves.** Channel: MECH — citation links resolve
  to the same section after a deploy.
- **E6 · Facts carry their source and their date.** Every number, version and claim that can go stale is dated
  and attributed on the page. Channel: MECH-assisted (the fields exist and are non-empty) + READER for honesty.
  This is the E-DI discipline applied to the web: a page whose facts can be checked is one an agent can use
  without trusting it.
- **E7 · The site's own data is available as data** — a JSON endpoint, a feed, or a published file — for
  anything the site publishes and a user might want to reuse. Channel: MECH.
- **E8 · The terms for machines are explicit**: what may be fetched, what may be quoted, what must be
  attributed — in `robots.txt` and in a short, human-readable statement. Channel: MECH (the files exist) +
  READER (they say something).
- **E9 · Identifiers do not move.** URLs are stable across deploys; anything that changed declares a redirect.
  Channel: MECH — compare the previous crawl against the current one.
- **E10 · Errors, empties and refusals explain the next step in words** — not only in colour, icon or status
  code. An agent that hits a wall should be able to tell its user what to do. Channel: MECH (text present) +
  READER (it is useful).

**And one guard, because this group is the easiest to game:** *the AI group may not be satisfied by degrading
the human page.* E1–E10 are additions to sections A–D, never substitutes. A site that reads beautifully to a
parser and confusingly to a person has failed the job, and the guard is mechanical: E4's fetched text must
equal the text a person sees.

### F. The floor

- **F1 · WCAG 2.2 AA.** Channel: MECH (automated tools catch roughly a third) + READER for the rest. Hardness:
  DOCUMENT for the specification, and the overlap with E1 and E10 is deliberate — accessible pages are the ones
  machines can read, and the reverse is mostly true.

---

## 3. How this plugs into a Plumbline job

1. **The Specialist seat adopts or trims the set** and declares it in the packet: the dimension list, each
   anchor, each channel, and the pass rule (`T_accept`, `T_dim`, cap).
2. **Ground truth rows.** The DOCUMENT sources go in `ground_truth[]` with their version and hardness — WCAG
   2.2, schema.org, the site's own analytics, the filed voice-of-customer transcripts, the crawl output. The
   PRIOR sources are cited in the instrument, never as the only basis of a score.
3. **Every dimension declares its channel, and at least the mechanical ones are declared before generation** —
   a check written after the artifact exists is a check that agrees with it.
4. **The AI-friendliness group gives the job its hard half.** Ten mechanical dimensions are ten places a first
   pass can fail honestly, and the fix is usually content work, not engineering.
5. **The live site is the second instrument.** Once deployed, A2, C5 and D3 read real behaviour — which is the
   only ground truth that is not somebody's judgement, including mine.

## 4. What would make this standard fail

If every channel above collapses to "a reader said so", the set is PRIOR dressed as a rubric — opinions with
arithmetic on top. The falsifier is stated so it can fire: **if the DOCUMENT dimensions can be satisfied while
A1, A2, B1 and D2 all fail, the standard is measuring the machine, not the website.** The order of the sections
is the order of importance, and it is deliberately not alphabetic.

---

## Appendix — the same set as a packet fragment

```json
{
  "specialist_standard": "website-standard-v0.1",
  "dimensions": [
    {"id": "A1", "name": "purpose_identifiable_from_the_page", "channel": "reader test, 5 readers, control page", "hardness": "READER"},
    {"id": "A2", "name": "task_completable", "channel": "task session + live analytics", "hardness": "READER+MEASURED"},
    {"id": "A3", "name": "done_test_declared_before_work", "channel": "packet inspection", "hardness": "DOCUMENT"},
    {"id": "B1", "name": "claims_trace_to_voice_of_customer", "channel": "traceability pass against filed VOC", "hardness": "DOCUMENT"},
    {"id": "B2", "name": "one_claim_per_paragraph", "channel": "reader states each paragraph's claim", "hardness": "READER"},
    {"id": "B3", "name": "awareness_stage_declared_and_matched", "channel": "packet + reader", "hardness": "PRIOR+READER"},
    {"id": "B4", "name": "plain_language", "channel": "reader (readability is screening only)", "hardness": "READER"},
    {"id": "C1", "name": "one_primary_action_reachable_in_one_click", "channel": "link graph + DOM parse", "hardness": "MECH"},
    {"id": "C2", "name": "no_orphan_pages", "channel": "crawl from root", "hardness": "MECH"},
    {"id": "C3", "name": "depth_bounded_and_declared", "channel": "crawl", "hardness": "MECH"},
    {"id": "C4", "name": "nav_identical_across_pages", "channel": "nav diff across rendered pages", "hardness": "MECH"},
    {"id": "C5", "name": "labels_are_user_vocabulary", "channel": "label test + search vocabulary", "hardness": "READER+MEASURED"},
    {"id": "D1", "name": "one_primary_cta_per_page", "channel": "DOM + computed styles", "hardness": "MECH"},
    {"id": "D2", "name": "cta_states_outcome_not_mechanism", "channel": "reader, against the packet's purpose", "hardness": "READER"},
    {"id": "D3", "name": "every_cta_instrumented_and_firing", "channel": "event test on a real click", "hardness": "MECH"},
    {"id": "D4", "name": "action_cost_stated_where_the_action_is", "channel": "reader, before and after", "hardness": "READER"},
    {"id": "E1", "name": "semantic_html_standalone_outline", "channel": "parser", "hardness": "MECH"},
    {"id": "E2", "name": "structured_data_valid_and_consistent", "channel": "validator + cross-check against the page", "hardness": "MECH"},
    {"id": "E3", "name": "machines_can_enumerate", "channel": "sitemap/robots/llms.txt presence and validity", "hardness": "MECH"},
    {"id": "E4", "name": "content_in_html_no_js_needed", "channel": "fetch without JS, compare to rendered text", "hardness": "MECH"},
    {"id": "E5", "name": "stable_anchors_deep_links_resolve", "channel": "citation link check after deploy", "hardness": "MECH"},
    {"id": "E6", "name": "facts_dated_and_attributed", "channel": "field check + reader for honesty", "hardness": "MECH+READER"},
    {"id": "E7", "name": "site_data_available_as_data", "channel": "endpoint or feed fetch", "hardness": "MECH"},
    {"id": "E8", "name": "machine_terms_explicit", "channel": "robots.txt + attribution statement", "hardness": "MECH"},
    {"id": "E9", "name": "identifiers_stable_redirects_declared", "channel": "crawl diff across deploys", "hardness": "MECH"},
    {"id": "E10", "name": "errors_explain_the_next_step_in_words", "channel": "text present + reader", "hardness": "MECH+READER"},
    {"id": "F1", "name": "wcag_22_aa", "channel": "automated tools + manual pass", "hardness": "DOCUMENT"}
  ],
  "guard": "E1-E10 may not be satisfied by degrading the human page: E4's fetched text must equal what a person sees.",
  "falsifier": "if the DOCUMENT dimensions pass while A1, A2, B1 and D2 fail, the standard is measuring the machine, not the website."
}
```

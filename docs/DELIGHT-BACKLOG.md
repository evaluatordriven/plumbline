# Delight backlog — Owner 2026-11-12 (file-lessons)

Pain: v0.9.9 docs-cut treated like full CL1 release; bare `accepted` hid hollow custody.
Principle: fewer false finishes; refuse early; name gates.

## Done in this PR (1 — Plumbline kit)

- [x] `kit/delight.py` — `job_class`, dual gates, hollow-record reasons, `finish_kind`, status card text
- [x] `kit/preflight.py` — BASE vs HEAD, emit tree/SPEC, scoring_set warn, budget floors, ratified block
- [x] `tools/status_card.py` — one paste for Owner/conduit
- [x] `conductor_loop` summary attaches gates after emit (does not change doctrine `terminal_state`)
- [x] `tests/test_delight_gates.py`

### How to use

```bash
# before Maker
PYTHONPATH=. python3 kit/preflight.py --packet packet.json --cwd worktree [--custody-tree candidate]

# after finish
PYTHONPATH=. python3 tools/status_card.py --record-dir /path/to/record --next-human "…"
```

Optional packet field: `"job_class": "docs_cut" | "kit_fix" | "full_release_record"`  
(or `x-plumbline.job_class`).

## Still open

### (1) Plumbline kit — remaining
- [ ] Emit default to attested artifact tree for release jobs (print `spec_version.source` always — partially exists; wire finish path)
- [ ] Refuse empty Maker findings when reds exist + classify red subject|plant|unsatisfiable (route + loop)
- [ ] Hard budget floor refuse optional flag for `full_release_record`

### (2) Hermes profiles
- [ ] Conductor SOUL: status card every needs_owner / charge end
- [ ] Maker: empty-findings classified exit; keep yolo/dispatch-early
- [ ] Architect: pin-vs-doc-vs-runner separation in needs_owner
- [ ] Eval: model block required for record-bound mode

### (3) Custody
- [ ] Release-class blurb (docs candidate / record+checker / frozen / gap)
- [ ] Hollow-record message beside checker FAILED
- [ ] Keep #15 cite-path; never freeze FAILED to green CI

### (4) EDI (light)
- [ ] Finish-kinds + runner≠bar one note (when calm; no rule-growth thrash)

### (5) Ryan
- [ ] Invite only per invite-gate (fact_store); Form B; not PR#14 mess

## Ryan invite gate (remember)

Do **not** send WIP / Decision C / hollow emit saga.  
Invite Form B only when: merged commit · published re-checkable claim · one-page brief · ≤2–3h · Owner cold-ran once · no mid-read help · failure = claim or verifier wrong.  
Needs email from Owner before send.

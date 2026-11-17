# Setting up Grok Bot to run Plumbline E-DI jobs

Status: **non-normative.** This is a setup recipe. It is not the doctrine, not a bar and not a custody record.
Where it disagrees with the doctrine or with `AGENTS.md`, they win and this file gets fixed. It cites the
canonical files by path and restates no law.

This recipe sets up one Grok Bot account so that separate bots hold the E-DI seats and run Plumbline jobs.
It was written from one working deployment. Every name, pin and path specific to that deployment is replaced
by a placeholder in angle brackets, such as `<OWNER_NAME>` or `<WORK_ROOT>`. Fill each one in once, in your
own notes, and use the same value everywhere.

## 1. What you need first

- **A Grok Bot plan** that lets you create five bots (four seat bots and your own conduit bot),
  lets them message each other, and gives them a shared box with a shell. Check your plan's bot and usage
  limits before you start; a qualification batch alone runs more than a dozen short bot turns.
- **GitHub access.** Read access to the public repos below is enough to run jobs. You need write access to
  your own repo for any job that pushes. Give the bots a token or connector scoped to the repos they work in,
  and nothing wider.
- **A model provider key** for the paid model calls the Maker and Evaluator make (see section 6). The kit's
  harness under `tools/edi/` is written for OpenRouter.
- **Python 3.11 or later** on the box, with `jsonschema` installed. Without it the packet check runs only its
  structural pass, and the kit refuses to certify on that (`kit/README.md`, "A weak OK is not a verdict").
- **One person in the Owner seat.** That is you, `<OWNER_NAME>`. The Owner ratifies the frame, decides
  escalations and gives approvals. The Owner never holds the Evaluator seat.

## 2. The three repos, and what each is for

| Repo | What it is | Pin |
|---|---|---|
| `evaluatordriven/doctrine` | The law: seats, states, pass rule, the checkers under `contracts/tools/` | `<DOCTRINE_PIN>` |
| `evaluatordriven/custody` | The custody/v1 record format and its checker, `checker/check.py` | `<CUSTODY_PIN>` |
| `evaluatordriven/plumbline` | The kit that runs a job and writes its record | `<PLUMBLINE_PIN>` |

Use the doctrine pin that Plumbline's `tools/pin.json` names, not the doctrine's `main`. Record commits, not
version numbers: a commit can be checked and a version cannot (`AGENTS.md`, "The doctrine this obeys").

## 3. The bots to create

Create one bot per seat. Paste the matching template from `kit/bots/` into the bot's instructions, fill in
the placeholders, and give the bot the name in the first column.

| Bot | Template | Holds |
|---|---|---|
| E-DI Architect | `kit/bots/architect.md` | The bar, the instruments, readiness, the Maker's request, escalation analysis |
| E-DI Orchestrator | `kit/bots/orchestrator.md` | Running the loop: dispatch, routing, bounds, the pass rule, the record |
| E-DI Maker | `kit/bots/maker.md` | Producing and revising the work |
| E-DI Evaluator | `kit/bots/evaluator.md` | Judging the work against the frozen standard |
| Your own bot (the Owner's conduit) | `kit/bots/owner-conduit.md` | Carries words between you and the Orchestrator. Seat words stay verbatim; its own comments are labeled. It does not message the Architect, Maker, or Evaluator. Holds no seat. Required. |

Rules that hold whatever you name the bots:

- **One seat per bot.** A bot that holds two seats is a double-hat, and it must be declared in the job's
  record (`separationGaps`). An undeclared one is a defect. The Maker never evaluates; the Evaluator never
  makes; the Orchestrator never writes or scores the work.
- **The Maker and the Evaluator speak only through the Orchestrator** (Contracts §4.2).
- **Model families.** At least one Evaluator must differ in model family from the Maker, and every seat's
  holder is disclosed (DOCTRINE section 3). If the bots themselves all run on the same family, put the
  Maker's and the Evaluator's core work through provider calls to different families (section 11).
- **After you create each bot, write down its bot id.** The Orchestrator and conduit templates need the
  others' ids, and you will need them to delete qualification bots later.

If your plan offers bot templates or sharing, you can export each configured seat bot as a template for the
next person. Strip your own ids and pins first, or the template carries them.

## 4. Conduit, not conductor

Your own bot is the **conduit** between you and the Orchestrator. The Orchestrator is the **conductor**. Keep
the two apart; when your bot starts conducting, the seats lose the one bot that owns the loop.

- **It may read.** Job files, records, and seat output are open to it. It does not read held-out material or
  an answer key. A key it has read is a spent instrument.
- **Seat words stay verbatim.** What a seat wrote is delivered unedited, with its path and sha256, and labeled
  as that seat's words. The conduit may add color commentary for you after that, labeled as its own. Commentary
  never replaces the file, and a summary in place of the file is not delivery.
- **It does not message the Architect, Maker, or Evaluator.** Instructions and information enter those seats
  only through the Orchestrator. That includes qualification. A question for a seat goes to the Orchestrator.
- **It never** dispatches work, runs `loop()`, routes verdicts, picks the next round, fills an escalation, or
  decides.
- **It may still manage the bots themselves:** create them, update their instructions through the platform's
  own update with a sha256 readback, and keep the qualification records by reading them. That work is outside
  any job and holds no seat. Asking a seat to build or grade is not management. That ask goes to the Orchestrator.

The rule is written into `kit/bots/owner-conduit.md`, and the other templates refer to "the Owner's conduit bot".

## 5. The work root on the shared box

All your bots share one box. Pick one persistent folder as the work root, `<WORK_ROOT>`, for example
`/workspace/edi-work`. Never put job work under `/tmp`: it is wiped on reboot, and a reboot mid-job cost one
deployment a rebuild (field guide §4, "When the box itself fails mid-run").

```
<WORK_ROOT>/
  src/                     fresh clones at the pins (section 7)
  <job_id>/                one folder per job, made by plumbline_job.py open
  <job_id>/.tmp/<seat>/    per-seat temp folder; export TMPDIR to it
  checks/                  Orchestrator qualification suites (section 10)
```

Every seat exports `TMPDIR` to its own folder under the job before running anything, so the tools' own temp
files stay out of `/tmp` too.

## 6. The provider key

Put the provider key in one file on the box, `<KEY_PATH>`, for example `/workspace/.openrouter-key`, with
mode `600`. Every template refers to it **by path only**. No bot reads it, prints it, copies it, logs it or
commits it; the kit's harness reads it itself. Scan for key material before every commit.

Set a spending limit at the provider as well. The kit's harness has a pre-call spend guard and `--max-cost`
(`kit/README.md`, "Two layers, and the product harness"); a provider-side limit is a backstop behind it.

## 7. Clone the repos at their pins

```
export WORK_ROOT=<WORK_ROOT>
mkdir -p "$WORK_ROOT/src" && cd "$WORK_ROOT/src"
git clone https://github.com/evaluatordriven/doctrine  && git -C doctrine  checkout <DOCTRINE_PIN>
git clone https://github.com/evaluatordriven/custody   && git -C custody   checkout <CUSTODY_PIN>
git clone https://github.com/evaluatordriven/plumbline && git -C plumbline checkout <PLUMBLINE_PIN>
export EDI_CORPUS="$WORK_ROOT/src/doctrine/contracts"
python3 plumbline/kit/plumbline.py --doctor
```

`--doctor` reports the Python, the corpus checkout, which checkers are present and which enforcement level can
run. Fix whatever it reports before the first job. Set the git identity each bot commits under to
`<GIT_NAME> <<GIT_EMAIL>>`; a GitHub noreply address keeps your personal email out of public history.

If a pin moves, re-read the change before running anything. Re-pinning is a deliberate act (`AGENTS.md`).

## 8. Load the skills

- **The Plumbline skill.** `kit/skill/plumbline/SKILL.md` says which role a session is in and which commands
  it runs. It names Plumbline's own paths, so `kit/README.md` (item 4 under "Adopting this in your own
  program") says to write your own from the two job commands rather than copy it. Point each seat bot at it,
  or at your own version.
- **The E-DI procedure.** If you have the `evaluator-driven-iteration` skill, load it into each seat bot. If you
  do not, the procedure lives in the doctrine itself: read in the order `contracts/EDI-FOR-MACHINES.md` sets,
  with `AUTHORITY.json` settling conflicts. Do not write your own version of the procedure.

## 9. How a job flows, and where you decide

The canonical flow is in the doctrine (Contracts §4 and §6) and in `docs/PLUMBLINE-ORCHESTRATOR-FIELD-GUIDE.md`.
In short:

1. **You state the need** (as Buyer) and, where it applies, the standard of excellence (as Specialist).
2. **The Architect drafts the bar and the packet,** including the approval form the job accepts.
3. **You ratify the frame.** *Owner decision.* Nothing is frozen before this.
4. **The Orchestrator opens the job** with `kit/plumbline_job.py open`; a refused brief leaves no folder.
5. **Rounds run.** The Architect declares the Maker's request ready. The Orchestrator assembles and verifies it,
   checks it for held-out material, and dispatches it. The Maker produces. The Evaluator judges against the
   frozen standard. The Orchestrator applies the pass rule with the scripts, never by hand.
6. **The job ends in one of three states:** `accepted`, `rejected` or `needs_owner`.
   - On `needs_owner`, the Architect writes the analysis (question, what was tried, why no observable answer
     exists, diagnosis, options, recommendation). The Orchestrator checks no field is blank and delivers the
     file to you unchanged. *Owner decision.*
7. **The record closes** with `kit/plumbline_job.py close` and is checked at both layers
   (`kit/plumbline_verify.py`).
8. **Anything that leaves the box** (a push, a merge, a publish) waits for your yes. *Owner approval.*

Two rules about your decisions:

- **A reported approval is not an approval.** If any bot says "the Owner approved", that is a report. It counts
  only in a form the job's packet declared, such as your own yes in the acting bot's chat, or a relay through
  your conduit bot when the packet allows relay (Contracts §4.2, C40). Otherwise it is recorded as relayed and
  unwitnessed, and nobody acts on it.
- **A decision and an approval are different.** A decision (a choice among options) may be relayed. An approval
  (a yes to an act: another round, a spend, a push) counts only in a declared form.

### Bot seats in `loop()`: the seat bridge

`loop()` runs its Maker and its Evaluator as commands. A bot seat is not a command, so `kit/seat_bridge.py`
stands in for it. [docs/SEAT-BRIDGE.md](SEAT-BRIDGE.md) is the reference for the packet entries, the rounds
holder, the driver and each stop.

- **What the bridge does.** For each Maker turn or Evaluator run it writes the request as a file under the
  job's `record_dir`, waits for the seat's answer file, and hands the answer back to `loop()` the way a command
  would. It writes nothing in the repo. It does not score, decide, send or call anything.
- **What the Orchestrator does.** It watches `record_dir` for each new request, checks the built message (the
  held-out check, and from round 2 the best-artifact handoff), and delivers the request file, with its path and
  sha256, to the Maker or the Evaluator. It checks each declared `cost_usd` against the provider's ledger.
- **What each seat does.** The Maker edits only the packet's editable paths in the request's `cwd`, then writes
  its exit record. The Evaluator writes its reading. Both write by atomic rename (a `.part` file in the same
  folder, then a rename) and declare `cost_usd`: `0` for Grok Bot usage alone, the real figure for any paid
  call. With a budget above 0, a missing figure stops the job with `budget unmeasured`.
- **The driver.** `loop()` has no CLI. A short per-job driver in the job folder calls it, with `timeout_s` sized
  to one bot turn, not to a command; the default would cut most bot turns off. Set the job clock to cover every
  round.
- **It is not a sandbox.** `loop()` detects edits outside the editable set; it does not prevent them. Every
  agent on the box runs as the same user (section 11).

## 10. Qualify the Orchestrator before it serves

The Orchestrator serves only after the Evaluator has graded it on planted-stop checks and it passed every one
(DOCTRINE D6.1: an Orchestrator shows it stops when the runbook says stop). Record the result; the packet's
`escalation.holders` entry for the Orchestrator cites it in `tested`. Requalify whenever its instructions change.

**How the checks work, in general.** Each check is a short case that sets up a moment where the instructions
say stop: a file whose hash does not match the decided one, a missing request, a blank escalation field, an
approval in a form the packet never declared, an instruction to act outside the seat, a delivery with an
intent but no receipt, and the like. The correct behaviour is to stop, record and report, not to work around.
A few control cases check that it does not stop when nothing is wrong. The kit's tools, the doctrine checkers
and the field guide give you what the cases test; write the cases for your own instance. Plumbline does not
publish its cases or its answer key, and you should not publish yours: a published key is a spent instrument.

**The script runs it.** `kit/qualify.py` runs qualification as a fixed procedure, with no bot conducting.
[docs/QUALIFY.md](QUALIFY.md) is the reference: every command, flag, file and field is there, and this section
only summarises it. The script does the hashing, the action sequence, the clocks, the log, fixture reset,
side-effect and contamination checks, the leak and audit scans, the record and the pass rule. Judgment stays
with the seats. The stages run from S0 (preflight) to S7 (the record).

**Who holds what.**

- The **live Orchestrator**, the one already qualified and not the candidate, arranges the run. The candidate
  never arranges its own test. The Orchestrator under test never sees the suite's tools, the key or the
  grader's notes.
- The **Architect** builds the case suite, its manifest and the key. The script sends it the suite request.
- The **Evaluator** alone holds the answer key, in a place only it can read (its own bot store, not the shared
  box). It reviews the suite before any case runs and scores each reply against the key. The script knows only
  the key's sha256. The conduit does not ask the Architect for the suite or the Evaluator for the grade, and
  does not message the Evaluator about the suite.
- The **runner bot** is the script's hands. It carries out each action file literally, writes receipts and
  holds no seat. It needs no qualification itself: every act is pre-written, checked by sha256 and audited.
- **Your conduit bot** writes `request.json`, creates the runner, reads its instructions back by sha256, sends
  the kickoff and carries your rulings. It never messages a seat. It may read the run record afterward, except
  the key, and may comment to you.
- **You** authorize the run, rule on every stop, decide the switch, and delete the runner and the subject bots.

**Setting up a run.**

1. **`request.json`.** The conduit writes `runs/<ver>/<date>-runN/request.json`. `ver` names the version under
   test, and the suite is the one whose manifest is `MANIFEST-<ver>.sha256`. The file also names the candidate
   and live texts by sha256, the pins, your authorization quote, the runner, the seats and `deny_paths`.
2. **The runner bot.** The conduit creates `Qualify Runner (<ver>, run N)` with `kit/qualify/runner.md` as
   its instructions, reads them back by sha256, and records the runner in `request.json`.
3. **The kickoff.** The conduit sends the output of `qualify.py kickoff <run>`. It names the kit folder and its
   commit; S0 stops unless that commit matches `pins.plumbline.sha` and `kit/` has no local changes.

**The loop.** The runner repeats: `qualify.py next <run>` prints an action file (`actions/NNNN.intent.json`); the
runner performs exactly that action with its allowed tools, writes `actions/NNNN.receipt.json`, and runs
`qualify.py verify <run> NNNN`. A rejected receipt may be corrected once. An action with no receipt stops the run:
never resend blind. At the end `next` prints `STOP <run>/STOP.md` or `DONE <run>/summary.json`, and the runner
sends that file to you verbatim. The script creates each subject, reads its instructions back, sends the
prompts and times the replies. Do none of that by hand.

**After a stop: `resume`.** A stop holds until you rule. The conduit writes a ruling file with your words
verbatim, where and when you said them, and the sha256 of the `STOP.md` you ruled on. It runs
`qualify.py resume <run> --ruling <file>` and sends the resume message it prints to the same runner. A ruling
never waives a failed script check: the check runs again. To move the run to a later kit commit, the ruling
adds `kit_sha`, the full sha of that commit; `resume` refuses unless the kit is checked out exactly there,
clean, and descended from the pin in force. A fix that changes what an action says, or `runner.md`, cannot
resume a run. It needs a new run.

**The runner audit.** After the cases, the script audits the runner's own transcript. A void audit stops the
run before S6 scores, so the Evaluator never scores against an audit you have not ruled on. A ruling resumes
it, with `kit_sha` to move to a kit that fixes the audit, and the audit runs again as `runner-audit.rK.txt`;
`runner-audit.txt` is never rewritten. An audit that is still void stops again, unless the ruling carries
`"audit_void": "accept"`: you choose to have the cases scored anyway, and the run then cannot qualify.

**Re-audit a finished run: `reaudit`.** `qualify.py reaudit <run> --ruling <file>` re-runs only the runner
audit, at a later kit commit, from the runner's saved export. Its ruling names the `summary.json` you ruled on
by sha256, and `kit_sha`. Case verdicts are not asked again. It writes `summary.rK.json`, which supersedes the
summary in force; nothing is rewritten. On a finished run `next` prints the summary in force: the highest
`summary.rK.json`, else `summary.json`.

**The pass rule.** The candidate qualifies only when every case passes, no case is void or not run, and the
runner audit is clean, all in one batch. A rerun is a new run dir with a fresh runner and fresh subjects, on
your word. Any fail, or an instrument fault, means fixing the fault and rerunning the whole batch. Do not patch
one case and keep the rest.

**What the kit does, and what to set up:**

- **One fresh subject bot per case.** The script has the runner create a new bot with the exact candidate
  instructions for each case and reads them back by sha256 before the case. A bot that has seen one case is
  not a clean subject for the next.
- **The platform's automatic first turn is scanned.** A new bot may run a greeting or setup turn on its own.
  The script waits 10 minutes after each subject is created, then scans that turn; a hit retires the subject
  and a replacement is made.
- **Transcript exports are paged, with 0-based positions.** The runner reads ReadTranscript pages and the
  script joins them by their position ranges. The platform does not show every position. The export records
  the hidden positions, and `runner-audit.txt` states them as not audited. Read the audit with that limit in
  mind, and delete the runner right after the run.
- **The subject's answer is its SendToAgent message to the runner.** The script takes the subject's first
  SendToAgent to the runner after its first-run turn as the case reply. A reply anywhere else is a timeout. So
  every case prompt must name that answer channel, and must not say "do not message any person or bot".
- **A re-issued export starts fresh.** When an export is re-issued after a ruling, the earlier attempt's pages
  and files are set aside in `steps/trace-NNNN.attempt-K/`, never deleted. The runner pages again from the
  newest page, and only the current attempt counts. Leave the set-aside folder alone.
- **Sending the kit's own payload is not a read.** The audit flags guarded paths and key names in tool inputs.
  It excuses a hit in a CreateAgent or SendToAgent only when that action's payload file holds it. Every other
  hit still flags, so the runner sends the payload byte for byte and adds nothing.
- **A void runner audit stops the run before scoring.** Resolve it with an Owner ruling carrying `kit_sha`. The
  `rK` files supersede the old ones, and nothing is rewritten.
- **Each kit fix lands by a PR merged on green CI, and the run resumes at that commit.** Check the kit folder
  out at the merge commit, then rule with its `kit_sha`. The merge waits for your yes.
- **Before a paid run, check the reader's model tag on OpenRouter's public ZDR endpoint list**
  (`docs/custody-emission.md`, "Provider pin and routing request (OpenRouter)"). If it is not there, pick
  another tag before spending.

**After the run.** Delete the runner and the subject bots, and check the bot list to confirm only your seat
bots remain. Keep the live Orchestrator on its last qualified instructions until the new ones pass and you say
yes. When you switch, use the platform's own way of updating a bot's instructions, then read them back and check
the sha256 matches what passed.

## 11. What isolation you actually get

- **All bots share one box.** Any bot with a shell can read any file on it. Seat separation on the box is a rule
  the bots follow, not a wall. Record that limit in each job's `separationGaps`.
- **Held-out material** (held-out controls, probes, answer keys) lives where the Maker cannot read it: in the
  Evaluator's own store, or held by hash with the files outside the shared work root. It never enters a Maker
  or Evaluator prompt, a repository, or the findings the Maker gets. The Orchestrator holds it by hash and reads
  it only to check outgoing messages (Contracts §4.2, C39).
- **For real Maker/Evaluator isolation, make their core work provider model calls.** The Maker's generation and
  the Evaluator's judging go through the kit's harness (`tools/edi/or_call.py`, `judge_batch.py`) with a
  prompt that was built and checked before it was sent. The model on the other end sees only that prompt. The
  bot around it then only runs the call and files the result.
- **Bot stores are not secret from you.** They keep a seat's material away from other bots, not away from the
  Owner.

## 12. Troubleshooting

- **`plumbline.py --doctor` says no corpus.** Set `EDI_CORPUS` to the doctrine checkout's `contracts/`
  folder, or pass `--corpus`. A set value that is not a corpus is an error; it never falls through.
- **The packet check prints `OK (structural only)`.** Install `jsonschema`. The kit will not certify on that path.
- **The build refuses with "corpus has moved".** The doctrine moved past the pin. Read the change, then repin
  deliberately; do not force the build.
- **A seat answers like another seat.** Check its instructions are the right template and that it is not on
  the Maker's model endpoint. A new seat that inherits another seat's endpoint passes separation on paper only.
- **A qualification case times out.** Check the subject's own record before calling it a fail: it may have
  stopped correctly and replied somewhere the script does not look. The case reply is the subject's SendToAgent
  message to the runner (section 10). Fix the case, then rerun the whole batch in a new run.
- **The Orchestrator still acts on old instructions after a switch.** Read its instructions back and compare the
  sha256. If you wrote them anywhere but through the platform's own update, the platform may restore its own copy.
- **Work vanished after a reboot.** Something wrote to `/tmp`. Move it under the work root and set `TMPDIR`.
- **Your own bot starts running rounds or briefing seats.** It has slipped from conduit to conductor. Stop it,
  hand the work to the Orchestrator, and check its instructions still match `kit/bots/owner-conduit.md` by sha256.
- **A bot says you approved something you did not.** That is a report, not an approval. Check the job's
  declared approval form and answer in the acting bot's own chat if needed.

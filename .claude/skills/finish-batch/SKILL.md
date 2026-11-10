---
name: finish-batch
description: Close out an ENGINE_PLAN.md batch that is implemented and approved - tick its boxes, update Status, remove the comments it made outdated, record what was noticed in Known gaps, and leave the tree ready to commit without committing.
disable-model-invocation: true
---

# Finish a batch

The user runs this once a batch from `ENGINE_PLAN.md` is implemented, its checks have passed and they agree with
the end-of-batch summary. Running it is their OK for every step below, for this batch only. Work from that
summary (the boxes it said can be ticked, the outdated comments it listed, what it noticed but didn't change). If
there is no such summary in the conversation, or one of these steps is unclear, ask instead of guessing.

1. **Tick the boxes.** In `ENGINE_PLAN.md`, change `- [ ]` to `- [x]` for every entry the summary listed, and
   nothing else. Keep the marks (`*`, `!`, `(B)`, `(E)`, `(in MoveDB)`) as they are.
2. **Update Status.** Fold the batch into the latest `Done:` line, or add one in the same style with today's date
   (`- Done: 6.1 (recharge) and 6.2 (charge turn), 2026-11-10.`), and point `Next:` at the following step,
   named as its heading names it. If the batch ends a phase, say "and with it Phase N", and add "Its
   `benchmarks.run quick` on the home PC is still to do." unless it was run.
3. **Remove the outdated comments.** Only the TODOs, docstring entries and commented-out lines the summary
   listed as outdated by this batch (a "not implemented yet" list naming its moves, a commented list of moves now
   in code). Delete only the outdated part of a line. Never touch parked blocks or other TODOs.
4. **Known gaps in `CLAUDE.md`.**
   - Add every "noticed but not changed" item from the summary that the user didn't decline, next to the gaps it
     belongs with, in the file's style: short, sources tagged `[pp]` / `[SD]`.
   - Remove the entries, or the parts of them, that the batch resolved.
5. **Checks.** If step 3 changed code, run `pytest`. If an `@njit` function changed beyond its docstring, also run
   `pytest -m jit`. Report any failure and stop there.
6. **Ready to commit.** Don't stage or commit. Show `git status --short` and `git diff --stat`, then propose a
   commit message in the repo's style: a short title naming the batch, like the recent `git log` subjects ("Recharge
   moves"), followed by the attribution line from the session's instructions.
7. **Report back.** List the boxes ticked, the Status lines, each comment removed (`file:line`, what it said),
   each Known gaps line added or removed, the check results, and the proposed commit message.

If the batch ended a phase, also remind the user of the end-of-phase steps in `ENGINE_PLAN.md` that are still
open (`-m slow`, a new `battle_driver.py` scenario, `benchmarks.run quick` on the home PC, the coverage report).

# Prompt — Create the `development-workflow` Skill

> **How to use:** paste everything below the rule into a fresh Claude Code session
> at the repo root. It is self-contained and produces a committed, auto-loading
> skill that governs every later task in this repository.

---

## Objective

Create a **project-level Claude Code skill** named `development-workflow` that becomes
the standing operating procedure for every subsequent development task in this
repository. From the moment it exists, no code reaches the default branch in this repo
without passing the quality gates it defines.

Do not ask me to confirm the plan. Build it, verify it, commit it, and report.

## Deliverable

Write the skill to this exact path so Claude Code auto-discovers it — no registration
step, no restart, no manual loading:

```
.claude/skills/development-workflow/SKILL.md
```

Supporting material goes in sibling files under
`.claude/skills/development-workflow/` (`references/`, `scripts/`, `templates/`),
referenced by relative path from `SKILL.md` and read only when needed.

### Format requirements (non-negotiable)

1. **YAML frontmatter with exactly two keys**, `name` and `description`:
   ```yaml
   ---
   name: development-workflow
   description: <see below>
   ---
   ```
   `name` must match the directory name. No other frontmatter keys.
2. **The `description` is the trigger.** It is the only part of the skill loaded into
   every context, and it alone decides whether the skill activates. Write it in the
   third person, under ~500 characters, stating *what it does* **and** *when to use it*,
   with concrete trigger vocabulary: implementing a feature, fixing a bug, refactoring,
   changing code, preparing to commit, merge, or open a PR, running checks before
   shipping. It must fire on ordinary phrasings ("add X", "fix Y", "ship this") — not
   only when someone says the word "workflow".
3. **Progressive disclosure.** `SKILL.md` stays under ~500 lines and holds the
   procedure. Long checklists, per-stack command tables, and templates move to
   `references/*.md` that `SKILL.md` links and instructs the reader to open on demand.
4. **Imperative voice, addressed to the agent executing it.** "Run the full gate set,"
   not "the agent should probably consider running." No hedging, no marketing prose.
5. Determinism over prose: where a step can be a script, write the script into
   `scripts/` and have `SKILL.md` invoke it.

## What the skill must require, at every step

The skill defines a development loop in which each of the following is a *first-class
step*, not an afterthought at the end:

| Gate | Requirement |
|---|---|
| **Documentation** | Every behavioral change updates the docs that describe it — README, `docs/`, public API docstrings/comments, and a changelog entry. New modules ship with a purpose statement. Docs are written in the same commit as the code, never deferred. |
| **Security testing** | Run the repo's security tooling and the `security-review` skill on the pending diff. Cover: dependency/advisory audit, secret and credential scanning on the diff, injection and authz review of new input paths, and unsafe-default review of new config. Findings are triaged; anything not fixed is documented with an explicit written justification. |
| **Code checks** | Formatter, linter, type checker, unit and integration tests, and a clean build — whatever subset the detected stack actually provides. Plus the `code-review` skill on the diff. New logic ships with tests that fail without the change. Coverage must not regress. |
| **Image generation** | *When necessary, and only then.* Required when a change alters user-visible UI (capture a before/after screenshot of the running app) or alters architecture, data flow, or a state machine (produce or update a diagram). Images live under `docs/images/`, are referenced from the docs they support, and carry alt text. A pure backend refactor with no structural change needs no image — the skill must say so plainly so this gate is not cargo-culted. |

The skill must **detect the stack rather than assume one.** This repository is currently
empty apart from a licence, so hardcoded `npm test` is wrong. Specify a resolution
order: an explicit project config (`package.json` scripts, `Makefile`, `justfile`,
`pyproject.toml`, `Cargo.toml`, `go.mod`, CI workflow files) wins; otherwise fall back
to documented per-ecosystem defaults in `references/`; if a gate has no tooling in this
repo, the skill records it as **N/A with the reason**, and never as "passed".

## The pre-merge gate — the core of the skill

Before any merge to the default branch (a local merge or a PR merge alike), the skill
must run **all four gates** and require every one to pass.

**The failure protocol, stated explicitly in `SKILL.md`:**

1. A gate fails → **fix the underlying cause.** Never disable the check, loosen a
   threshold, add a suppression comment, delete the failing test, or mark the gate N/A
   to get past it.
2. After the fix, **re-run the complete gate set from the start** — all four, not just
   the one that failed. A fix invalidates every prior result.
3. Repeat until one full pass is green end to end. Cap at **3 full cycles**; if the
   third cycle is still red, stop, do not merge, and report what is failing, what was
   tried, and the recommended next step.
4. Only a single uninterrupted green run of all four gates authorizes the merge.
5. After merging, continue to the next task and apply the same loop again — the skill
   governs every task in the session, not just the first.

The skill must also require an auditable **gate ledger**: a short status table
(gate | result | evidence — command run, exit code, or file changed) emitted before the
merge decision. Passing is a claim that has to be backed by a command that actually
ran; "looks fine" is not evidence, and a gate that was never executed is a failure, not
a pass.

## Auto-learning after creation

The skill must be in force immediately, without me doing anything:

- Correct path and matching `name` — that is what makes it auto-discoverable.
- After writing it, **verify it actually loaded**: list the available skills and confirm
  `development-workflow` appears with the intended description. If it does not, fix the
  frontmatter and re-check.
- Add a short `CLAUDE.md` section at the repo root stating that all development in this
  repo follows the `development-workflow` skill, and linking to it — so the rule is
  visible even in contexts where the skill has not yet triggered.
- Commit the skill, its references, and the `CLAUDE.md` entry to the working branch and
  push. Do not open a pull request unless I ask for one.
- **Then apply the skill to itself**: run the gate set over the commit you just made
  (documentation ✓, security ✓ — no secrets, no unsafe scripts, code checks ✓ — valid
  YAML frontmatter, working relative links, image gate N/A with reason). A skill that
  cannot pass its own gates is not finished.

## Acceptance criteria

Report against these, honestly, marking any as failed if they are:

- [ ] `.claude/skills/development-workflow/SKILL.md` exists with valid two-key frontmatter.
- [ ] The `description` triggers on ordinary implementation phrasing, not just the word "workflow".
- [ ] `SKILL.md` is under ~500 lines; detail lives in linked `references/` files that resolve.
- [ ] All four gates are defined with concrete, runnable commands per detected stack.
- [ ] The fix → **re-run everything** → merge loop is stated unambiguously, with the 3-cycle cap and the no-suppression rule.
- [ ] The image gate states both when it applies and when it does not.
- [ ] The gate ledger format is specified.
- [ ] The skill was verified to load, and was run against its own commit.
- [ ] `CLAUDE.md` references the skill; everything is committed and pushed.

## Constraints

- Reuse what already exists: the `skill-creator` skill for scaffolding and validation,
  and the `security-review` and `code-review` skills as the gate implementations. Do not
  reimplement them.
- No invented tooling. Every command in the skill must be one that exists in this repo
  or is a documented default for a detected ecosystem.
- The skill is a procedure, not an essay. If a line does not change what the executing
  agent does, cut it.

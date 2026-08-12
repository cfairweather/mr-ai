# mr-ai

## Development process

All development in this repository follows the
[`development-workflow`](.claude/skills/development-workflow/SKILL.md) skill. It is a
project-level Claude Code skill, so it loads automatically — but it is linked here too,
because the rule applies whether or not the skill has triggered in a given context.

In short: work on a branch, carry documentation and images alongside the code in the
same commit, and before merging run all four gates —

| Gate | What it covers |
|---|---|
| Documentation | README/`docs/`, API docs, changelog |
| Security testing | `security-review` skill, dependency audit, secret scan, input paths |
| Code checks | format, lint, types, tests, build, `code-review` skill |
| Image generation | screenshots for UI changes, diagrams for structural ones — N/A otherwise |

Run the mechanical portion with:

```bash
.claude/skills/development-workflow/scripts/run_gates.sh
```

If a gate fails, fix the cause — never suppress the check — then **re-run the complete
set**, because a fix invalidates every earlier result. Print the evidence ledger with
the merge decision.

One uninterrupted green run is the authorization to merge to `main`: merge on green
without asking first. A red or partial ledger is never a merge.

## Toolchain

This repository has no build toolchain yet. Until one exists the mechanical gates
correctly report `N/A`, which is not the same as passing. When the first toolchain
lands, record its real commands in
[`references/stack-commands.md`](.claude/skills/development-workflow/references/stack-commands.md).

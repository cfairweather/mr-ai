# Stack commands

Fallback commands per ecosystem, used only when the repo has no explicit config saying
otherwise (`SKILL.md` §7). `scripts/run_gates.sh` applies these automatically; this file
is the record of what it tries and the place to look when a gate reports N/A.

**Resolution order, first hit wins:** project config → this table → N/A with a reason.

> This repository currently has no toolchain. Every mechanical gate resolves to N/A
> until one is added. That is the correct result, not a passing one. When the first
> toolchain lands, record its real commands in the [project section](#this-repository)
> at the bottom so later tasks stop relying on guesses.

## Node / TypeScript

Detected by `package.json`. Package manager follows the lockfile: `pnpm-lock.yaml` →
pnpm, `yarn.lock` → yarn, `bun.lockb` → bun, otherwise npm. Only scripts that actually
exist in `package.json` are run.

| Gate | Command |
|---|---|
| Format | `<pm> run format:check` (or `prettier --check .`) |
| Lint | `<pm> run lint` |
| Types | `<pm> run typecheck` (or `tsc --noEmit`) |
| Test | `<pm> test` |
| Build | `<pm> run build` |
| Audit | `npm audit --audit-level=high` / `pnpm audit` / `yarn npm audit` |

## Python

Detected by `pyproject.toml`, `setup.py`, or `requirements.txt`.

| Gate | Command |
|---|---|
| Format | `ruff format --check .` or `black --check .` |
| Lint | `ruff check .` or `flake8` |
| Types | `mypy .` or `pyright` |
| Test | `pytest` |
| Build | `python -m build` (packages only) |
| Audit | `pip-audit` |

## Rust

Detected by `Cargo.toml`.

| Gate | Command |
|---|---|
| Format | `cargo fmt --check` |
| Lint | `cargo clippy -- -D warnings` |
| Types | covered by `cargo check` |
| Test | `cargo test` |
| Build | `cargo build --release` |
| Audit | `cargo audit` |

## Go

Detected by `go.mod`.

| Gate | Command |
|---|---|
| Format | `gofmt -l .` (any output means unformatted) |
| Lint | `golangci-lint run` or `go vet ./...` |
| Types | covered by `go build` |
| Test | `go test ./...` |
| Build | `go build ./...` |
| Audit | `govulncheck ./...` |

## Make / just

If a `Makefile` or `justfile` defines targets named `lint`, `test`, `build`, `fmt`, or
`check`, prefer them over the ecosystem defaults above — they encode what this project
means by a passing build, which is more authoritative than a generic guess.

## CI workflows

`.github/workflows/*.yml` is the strongest signal available: whatever CI runs on pull
requests is the definition of green for this repo. When a local command and CI disagree,
CI wins — match it locally rather than arguing with it at merge time.

## This repository

<!-- Add real commands here as the toolchain lands, and delete the note at the top. -->

| Gate | Command | Notes |
|---|---|---|
| Format | — | not yet configured |
| Lint | — | not yet configured |
| Types | — | not yet configured |
| Test | — | not yet configured |
| Build | — | not yet configured |
| Audit | — | not yet configured |

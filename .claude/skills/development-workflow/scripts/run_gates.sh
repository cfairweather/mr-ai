#!/usr/bin/env bash
# Mechanical gate runner for the development-workflow skill.
#
# Detects the stack, runs the code-check and security gates that actually exist
# in this repo, and prints ledger rows. Gates with no tooling report N/A with a
# reason — never PASS, because "nothing ran" is not a passing result.
#
# The judgment gates (Documentation, Security review triage, Images) are not
# scriptable; add those rows yourself. See SKILL.md §3 and §5.
#
# Usage: run_gates.sh [base-ref]        base-ref defaults to the default branch
# Exit:  0 = no gate failed, 1 = at least one FAIL

set -uo pipefail

cd "$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "not inside a git repository" >&2
  exit 2
}

LOG_DIR="$(mktemp -d)"
ROWS=()
FAILED=0
STACKS=()
PM=""

have() { command -v "$1" >/dev/null 2>&1; }
add_row() { ROWS+=("$1|$2|$3"); }

# Run one gate. Records PASS/FAIL and echoes the tail of the log on failure, so
# the cause is visible without hunting for the file.
run_gate() {
  local gate="$1" cmd="$2" log code
  log="$LOG_DIR/$(printf '%s' "$gate" | tr -c 'A-Za-z0-9' '_').log"
  printf '── %-13s %s\n' "$gate" "$cmd"
  if bash -c "$cmd" >"$log" 2>&1; then
    add_row "$gate" "PASS" "\`$cmd\` exit 0"
  else
    code=$?
    FAILED=1
    add_row "$gate" "FAIL" "\`$cmd\` exit $code (log: $(basename "$log"))"
    sed 's/^/     | /' "$log" | tail -15
  fi
}

# Candidates are "command" or "binary::command" when the binary to probe is not
# the first word (a pipeline, say). Runs the first whose binary is installed.
gate_first() {
  local gate="$1"
  shift
  local candidate bin cmd
  for candidate in "$@"; do
    case "$candidate" in
      *::*) bin="${candidate%%::*}"; cmd="${candidate#*::}" ;;
      *)    cmd="$candidate";        bin="${cmd%% *}" ;;
    esac
    if have "$bin"; then
      run_gate "$gate" "$cmd"
      return
    fi
  done
  add_row "$gate" "N/A" "no tool installed for this gate"
}

# ── Base ref and changed files ───────────────────────────────────────────────
BASE="${1:-}"
if [ -z "$BASE" ]; then
  for candidate in origin/main origin/master main master; do
    if git rev-parse --verify -q "$candidate" >/dev/null 2>&1; then
      BASE="$candidate"
      break
    fi
  done
fi

DIFF_BASE=""
[ -n "$BASE" ] && DIFF_BASE="$(git merge-base HEAD "$BASE" 2>/dev/null || true)"

CHANGED="$(
  { [ -n "$DIFF_BASE" ] && git diff --name-only "$DIFF_BASE" 2>/dev/null
    git ls-files --others --exclude-standard 2>/dev/null
  } | sed '/^$/d' | sort -u
)"
CHANGED_COUNT="$(printf '%s' "$CHANGED" | grep -c . || true)"

# ── Stack detection ──────────────────────────────────────────────────────────
# Project config wins over ecosystem defaults: a Makefile target or a
# package.json script encodes what this project means by a passing build.
if [ -f package.json ]; then
  STACKS+=("node")
  if [ -f pnpm-lock.yaml ]; then PM=pnpm
  elif [ -f yarn.lock ]; then PM=yarn
  elif [ -f bun.lockb ] || [ -f bun.lock ]; then PM=bun
  else PM=npm
  fi
fi
if [ -f pyproject.toml ] || [ -f requirements.txt ] || [ -f setup.py ]; then
  STACKS+=("python")
fi
[ -f Cargo.toml ] && STACKS+=("rust")
[ -f go.mod ] && STACKS+=("go")

has_stack() {
  local s
  for s in ${STACKS[@]+"${STACKS[@]}"}; do [ "$s" = "$1" ] && return 0; done
  return 1
}

echo "base:  ${BASE:-<none>}    changed files: $CHANGED_COUNT"
echo "logs:  $LOG_DIR"
if [ ${#STACKS[@]} -eq 0 ]; then
  echo "stack: none detected — mechanical gates will report N/A"
else
  echo "stack: ${STACKS[*]}${PM:+ (via $PM)}"
fi
echo

# ── Gate resolution ──────────────────────────────────────────────────────────
target_in_makefile() { [ -f Makefile ] && grep -qE "^$1:" Makefile; }
target_in_justfile() { [ -f justfile ] && grep -qE "^$1:" justfile; }

npm_script() {
  [ -f package.json ] || return 1
  if have node; then
    node -e 'const s=(require("./package.json").scripts)||{};process.exit(s[process.argv[1]]?0:1)' "$1" 2>/dev/null
  else
    grep -qE "\"$1\"[[:space:]]*:" package.json
  fi
}

# resolve_gate <gate> <make/just target> [npm-scripts...] -- [candidates...]
resolve_gate() {
  local gate="$1" target="$2"
  shift 2
  local scripts=() candidates=() seen_sep=0 arg
  for arg in "$@"; do
    if [ "$arg" = "--" ]; then seen_sep=1; continue; fi
    if [ "$seen_sep" -eq 0 ]; then scripts+=("$arg"); else candidates+=("$arg"); fi
  done

  if have just && target_in_justfile "$target"; then
    run_gate "$gate" "just $target"
    return
  fi
  if have make && target_in_makefile "$target"; then
    run_gate "$gate" "make $target"
    return
  fi
  if [ -n "$PM" ] && have "$PM" && [ ${#scripts[@]} -gt 0 ]; then
    local script
    for script in "${scripts[@]}"; do
      if npm_script "$script"; then
        run_gate "$gate" "$PM run $script"
        return
      fi
    done
  fi
  if [ ${#candidates[@]} -gt 0 ]; then
    gate_first "$gate" "${candidates[@]}"
  else
    add_row "$gate" "N/A" "no tool installed for this gate"
  fi
}

fmt_cands=()
has_stack rust && fmt_cands+=("cargo fmt --check")
# gofmt -l exits 0 even when it lists unformatted files, so invert on output.
has_stack go && fmt_cands+=("gofmt::gofmt -l . | { ! grep -q . ; }")
has_stack python && fmt_cands+=("ruff format --check ." "black --check .")
resolve_gate "Format" "fmt" "format:check" "format" -- ${fmt_cands[@]+"${fmt_cands[@]}"}

lint_cands=()
has_stack rust && lint_cands+=("cargo clippy --all-targets -- -D warnings")
has_stack go && lint_cands+=("golangci-lint run" "go vet ./...")
has_stack python && lint_cands+=("ruff check ." "flake8")
resolve_gate "Lint" "lint" "lint" -- ${lint_cands[@]+"${lint_cands[@]}"}

type_cands=()
[ -f tsconfig.json ] && type_cands+=("npx --no-install tsc --noEmit")
has_stack python && type_cands+=("mypy ." "pyright")
resolve_gate "Types" "typecheck" "typecheck" "types" -- ${type_cands[@]+"${type_cands[@]}"}

test_cands=()
has_stack rust && test_cands+=("cargo test")
has_stack go && test_cands+=("go test ./...")
has_stack python && test_cands+=("pytest")
resolve_gate "Test" "test" "test" -- ${test_cands[@]+"${test_cands[@]}"}

build_cands=()
has_stack rust && build_cands+=("cargo build --release")
has_stack go && build_cands+=("go build ./...")
resolve_gate "Build" "build" "build" -- ${build_cands[@]+"${build_cands[@]}"}

# ── Dependency audit ─────────────────────────────────────────────────────────
if [ -n "$PM" ] && have "$PM" && [ ! -f package-lock.json ] && [ ! -f pnpm-lock.yaml ] &&
   [ ! -f yarn.lock ] && [ ! -f bun.lockb ] && [ ! -f bun.lock ]; then
  # No lockfile means nothing resolved to audit. That is a gap in the repo's
  # setup, not a vulnerability — reporting FAIL here would cry wolf.
  add_row "Dep audit" "N/A" "package.json but no lockfile; commit one to enable auditing"
elif [ -n "$PM" ] && have "$PM"; then
  case "$PM" in
    npm)  run_gate "Dep audit" "npm audit --audit-level=high" ;;
    pnpm) run_gate "Dep audit" "pnpm audit --audit-level high" ;;
    yarn) run_gate "Dep audit" "yarn npm audit --severity high" ;;
    bun)  run_gate "Dep audit" "bun audit" ;;
  esac
elif has_stack rust; then
  gate_first "Dep audit" "cargo audit"
elif has_stack go; then
  gate_first "Dep audit" "govulncheck ./..."
elif has_stack python; then
  gate_first "Dep audit" "pip-audit"
else
  add_row "Dep audit" "N/A" "no dependency manifest in this repo"
fi

# ── Secret scan on the diff ──────────────────────────────────────────────────
# High-signal patterns only. This is a tripwire, not a substitute for the
# security-review skill: a hit means triage, not necessarily a real leak.
PATFILE="$LOG_DIR/secret-patterns"
cat >"$PATFILE" <<'PATTERNS'
A(KIA|SIA)[0-9A-Z]{16}
gh[pousr]_[A-Za-z0-9]{20,}
xox[baprs]-[A-Za-z0-9-]{10,}
sk-[A-Za-z0-9]{20,}
-----BEGIN [A-Z ]*PRIVATE KEY-----
(password|passwd|secret|api_?key|apikey|access_?token|auth_?token)[[:space:]]*[:=][[:space:]]*["'][^"']{8,}["']
PATTERNS

if [ "$CHANGED_COUNT" -eq 0 ]; then
  add_row "Secret scan" "N/A" "no changes against ${BASE:-<none>}"
else
  SECRET_LOG="$LOG_DIR/secret-scan.log"
  {
    [ -n "$DIFF_BASE" ] && git diff -U0 "$DIFF_BASE" -- . 2>/dev/null | grep -E '^\+'
    git ls-files --others --exclude-standard -z 2>/dev/null |
      xargs -0 -r grep -HnI '' 2>/dev/null
  } 2>/dev/null | grep -EIi -f "$PATFILE" >"$SECRET_LOG" 2>/dev/null

  if [ -s "$SECRET_LOG" ]; then
    FAILED=1
    add_row "Secret scan" "FAIL" "$(grep -c . <"$SECRET_LOG") candidate(s), triage secret-scan.log"
    printf '── %-13s candidate secrets found:\n' "Secret scan"
    sed 's/^/     | /' "$SECRET_LOG" | head -10
  else
    add_row "Secret scan" "PASS" "0 matches over $CHANGED_COUNT changed file(s)"
  fi
fi

# ── Ledger ───────────────────────────────────────────────────────────────────
echo
echo "| Gate          | Result | Evidence                                             |"
echo "|---------------|--------|------------------------------------------------------|"
for row in "${ROWS[@]}"; do
  IFS='|' read -r gate result evidence <<<"$row"
  [ "${#evidence}" -gt 52 ] && evidence="${evidence:0:49}..."
  printf '| %-13s | %-6s | %-52s |\n' "$gate" "$result" "$evidence"
done
echo
echo "Add these rows yourself — they need judgment, not a script (SKILL.md §3):"
echo "  Documentation | ? | ...    Security review | ? | ...    Images | ? | ..."
echo

if [ "$FAILED" -ne 0 ]; then
  echo "RESULT: gates failed. Fix the cause, then re-run the FULL set (SKILL.md §4)."
  exit 1
fi
echo "RESULT: mechanical gates clear. Merge only once all four gates are green."
exit 0

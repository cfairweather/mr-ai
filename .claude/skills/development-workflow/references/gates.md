# Gate checklists

Detail for the four gates in `SKILL.md` §3. Read the section you need; there is no
reason to load all of this for a one-line bug fix.

- [Documentation](#documentation)
- [Security testing](#security-testing)
- [Code checks](#code-checks)
- [Image generation](#image-generation)

---

## Documentation

Ask: *if someone hits this code in six months knowing nothing about today, what do they
read?* Update that.

| Change | What to update |
|---|---|
| New public function, endpoint, or CLI flag | Signature docs, usage example, README or `docs/` page |
| Changed behavior of something existing | The page describing it, plus a changelog entry noting the change |
| New module or package | Header comment stating its purpose and boundaries |
| New config option or env var | Config reference, default value, what happens when unset |
| Breaking change | Changelog entry marked breaking, plus a migration note |
| Internal refactor, no contract change | Nothing — record N/A with that reason |

Quality bar: examples must be runnable as written, and the docs must describe the code
as it is after this change, not as you intend it to become. A stale example is worse
than no example, because the reader trusts it.

---

## Security testing

Run the `security-review` skill on the diff. Use this list to check its coverage rather
than to replace it.

**Secrets.** Keys, tokens, passwords, connection strings, private keys, `.env` contents.
A committed secret is compromised even if the next commit removes it — the fix is to
rotate the credential, not to amend the commit. Say so in the ledger if it happens.

**Dependencies.** Audit anything newly added or bumped. Look at what the package
actually does, not only its advisory count — typosquats and abandoned packages pass a
clean audit. Transitive additions count.

**Input paths.** For every new endpoint, handler, parser, or form:
- Is input validated against a schema before use?
- SQL/command/template construction — parameterized, or string-concatenated?
- Is the caller's identity checked, and their authorization to this specific object?
- Is user-controlled text escaped where it renders?
- Are errors returned without leaking internals — stack traces, queries, paths?

**Unsafe defaults in new config.** Permissive CORS, disabled TLS or certificate
verification, debug or verbose modes, world-readable permissions, default credentials,
unauthenticated admin routes.

**Triage.** For each finding record: what it is, whether it is reachable in this
codebase, and fixed or accepted. Accepted findings need a reason a reviewer would agree
with — "low risk" alone is not one. Reachability is the deciding question: a genuine
injection in dead code ranks below a weak default on a live route.

---

## Code checks

Run in this order — cheapest and most likely to fail first, so a formatting error does
not cost a full test run:

1. **Format** — the repo's formatter, in check mode.
2. **Lint** — no new warnings, not merely no errors.
3. **Types** — the type checker, if the stack has one.
4. **Tests** — unit and integration. Confirm they were *collected*: a suite that runs
   zero tests exits 0 and means nothing.
5. **Build** — a clean production build.
6. **`code-review` skill** on the diff.

**Tests accompanying the change.** New logic ships with a test that fails without it —
verify that by running the new test against the unmodified code, not by assuming. Bug
fixes ship with a regression test reproducing the original report. Cover the error paths
you added, not only the happy path.

**Coverage** must not regress. No coverage tooling in the repo means you record that,
not that you estimate a percentage.

**Flaky tests** are failures. Re-running until green is how a real intermittent bug
reaches the branch. Quarantine it with a tracking note, or fix it.

---

## Image generation

Conditional. Applying it everywhere produces screenshots nobody opens and diagrams that
drift out of date, which costs more trust than it buys.

**UI change → screenshot.** Launch the app for real (the `run` skill) and capture the
affected view before and after. A screenshot of a mock, a storybook stub, or a
hand-drawn approximation does not demonstrate the change works.

**Architecture, data flow, or state machine change → diagram.** New service boundary,
changed request path, new async or queue step, a state machine gaining states. Prefer a
text-defined diagram (Mermaid) checked in beside the doc — it diffs in review and can be
regenerated. A binary export nobody can edit becomes wrong and unfixable.

**Not required:** backend refactors, bug fixes with no visual or structural effect,
dependency bumps, test-only changes, docs-only changes. Record N/A and the reason.

**Placement.** Captured images (screenshots, exported renders) go in `docs/images/`,
referenced from the doc they support, with alt text saying what the reader is meant to
notice. Name files for content, not sequence: `auth-flow-after.png`, not
`screenshot-3.png`. A Mermaid diagram needs no file — fence it inline in the doc it
explains, which is what "beside the doc" means for text-defined diagrams.

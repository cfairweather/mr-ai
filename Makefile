# Toolchain entry points for this repository.
#
# The development-workflow gate runner prefers these targets over its
# ecosystem defaults, so what `make lint` and `make test` do here is what
# "green" means for this repo.
#
# Deliberately no `fmt` or `build` target: this repo has no formatter and
# nothing to build, and an empty target would make the gate runner report PASS
# for a check that never ran. Absent means N/A, which is the honest result.

PY      := python3
SCRIPTS := .github/scripts
TESTS   := tests

.PHONY: lint test check

## lint: byte-compile Python, syntax-check shell, parse workflow YAML
lint:
	@echo "── py_compile"
	@$(PY) -m compileall -q $(SCRIPTS) $(TESTS)
	@echo "── bash -n"
	@for f in $$(git ls-files '*.sh'); do bash -n "$$f" || exit 1; done
	@echo "── workflow yaml"
	@$(PY) -c "import sys,yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yml')] and sys.stdout.write('ok\n')"

## test: run the unit test suite
test:
	@$(PY) -m unittest discover -s $(TESTS) -v

## check: everything the gate runner would run
check: lint test

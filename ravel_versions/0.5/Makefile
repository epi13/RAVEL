CC ?= cc
SAN_CC ?= clang
CFLAGS ?= -std=c11 -O3 -Wall -Wextra -Werror -pedantic
LDLIBS ?= -lm

.PHONY: test evidence training-test training-evidence training-check unified-test unified-evidence unified-check 0.4-evidence 0.4-check 0.4-manifest-negative-test 0.4-checkpoint-test 0.4-lineage-test 0.4-negative-test 0.4-compiler-matrix 0.4-sanitizers 0.4-runtime 0.5-test 0.5-evidence 0.5-check 0.5-development-gates 0.5-negative-test 0.5-manifest-negative-test 0.5-compiler-matrix 0.5-sanitizers 0.5-runtime 0.5-clean all clean

test: ravel
	./ravel >/dev/null

evidence: ravel
	@tmp=$$(mktemp); \
	trap 'rm -f "$$tmp"' EXIT; \
	if ./ravel > "$$tmp"; then \
		mv "$$tmp" evidence-actual.json; \
	else \
		cp "$$tmp" evidence-actual.json; \
		exit 1; \
	fi

training-test: ravel_train
	./ravel_train >/dev/null

training-evidence: ravel_train
	@tmp=$$(mktemp); \
	trap 'rm -f "$$tmp"' EXIT; \
	./ravel_train > "$$tmp"; \
	mv "$$tmp" training-evidence.json

training-check: ravel_train
	@tmp=$$(mktemp); \
	trap 'rm -f "$$tmp"' EXIT; \
	./ravel_train > "$$tmp"; \
	diff -u training-evidence.json "$$tmp"

unified-test: ravel_unified_bin
	./ravel_unified_bin >/dev/null

unified-evidence: ravel_unified_bin
	@tmp=$$(mktemp); \
	trap 'rm -f "$$tmp"' EXIT; \
	./ravel_unified_bin > "$$tmp"; \
	mv "$$tmp" unified-evidence.json

unified-check: ravel_unified_bin
	@tmp=$$(mktemp); \
	trap 'rm -f "$$tmp"' EXIT; \
	if ./ravel_unified_bin > "$$tmp" && diff -u unified-evidence.json "$$tmp"; then \
		rm -f unified-actual.json; \
	else \
		cp "$$tmp" unified-actual.json; \
		exit 1; \
	fi

0.4-evidence: ravel_0_4_bin
	python3 tools/ravel_0_4_evidence.py generate --binary ./ravel_0_4_bin

0.4-check: ravel_0_4_bin
	python3 tools/ravel_0_4_evidence.py verify --binary ./ravel_0_4_bin --diagnostics-dir diagnostics
	python3 tools/ravel_source_digest.py verify \
		--spec ravel-0.4-source-manifest-spec.json \
		--manifest ravel-0.4-source-manifest.json \
		--assurance ravel-0.4-assurance-case.json

0.4-manifest-negative-test:
	@tmp=$$(mktemp -d); \
	trap 'rm -rf "$$tmp"' EXIT; \
	cp -a . "$$tmp/ravel"; \
	cd "$$tmp/ravel"; \
	verify='python3 tools/ravel_source_digest.py verify --spec ravel-0.4-source-manifest-spec.json --manifest ravel-0.4-source-manifest.json --assurance ravel-0.4-assurance-case.json'; \
	$$verify >/dev/null; \
	cp RAVEL_0_4_CONTRACT.md contract.saved; \
	printf '\nmutation\n' >> RAVEL_0_4_CONTRACT.md; \
	if $$verify >/dev/null 2>&1; then exit 1; fi; \
	mv contract.saved RAVEL_0_4_CONTRACT.md; \
	cp ravel-0.4-source-manifest.json manifest.saved; \
	python3 -c 'import json; p="ravel-0.4-source-manifest.json"; r=json.load(open(p)); r["ordered_files"].pop(); json.dump(r,open(p,"w"))'; \
	if $$verify >/dev/null 2>&1; then exit 1; fi; \
	cp manifest.saved ravel-0.4-source-manifest.json; \
	python3 -c 'import json; p="ravel-0.4-source-manifest.json"; r=json.load(open(p)); r["ordered_files"][0],r["ordered_files"][1]=r["ordered_files"][1],r["ordered_files"][0]; json.dump(r,open(p,"w"))'; \
	if $$verify >/dev/null 2>&1; then exit 1; fi; \
	cp manifest.saved ravel-0.4-source-manifest.json; \
	mkdir -p ravel_0_4; \
	printf 'unexpected\n' > ravel_0_4/unexpected.inc; \
	if $$verify >/dev/null 2>&1; then exit 1; fi; \
	rm -rf ravel_0_4; \
	cp ravel-0.4-assurance-case.json assurance.saved; \
	python3 -c 'import json; p="ravel-0.4-assurance-case.json"; r=json.load(open(p)); r["implementation"]["source_digest"]="0"*64; json.dump(r,open(p,"w"))'; \
	if $$verify >/dev/null 2>&1; then exit 1; fi; \
	mv assurance.saved ravel-0.4-assurance-case.json

0.4-checkpoint-test: ravel_0_4_bin
	@tmp=$$(mktemp); \
	trap 'rm -f "$$tmp"' EXIT; \
	./ravel_0_4_bin > "$$tmp"; \
	python3 -c 'import json,sys; r=json.load(open(sys.argv[1])); assert all(t["checkpoint_verification"]["complete_behavior_match"] and all(t["checkpoint_verification"]["mutations"].values()) for t in r["trials"])' "$$tmp"

0.4-lineage-test: ravel_0_4_bin
	@tmp=$$(mktemp); \
	trap 'rm -f "$$tmp"' EXIT; \
	./ravel_0_4_bin > "$$tmp"; \
	python3 -c 'import json,sys; r=json.load(open(sys.argv[1])); assert all(all(t["lineage_invariants"].values()) for t in r["trials"])' "$$tmp"

0.4-negative-test: ravel_0_4_bin
	@tmp=$$(mktemp); \
	trap 'rm -f "$$tmp"' EXIT; \
	./ravel_0_4_bin > "$$tmp"; \
	python3 -c 'import json,sys; r=json.load(open(sys.argv[1])); assert all(v["pass"] for v in r["negative_tests"].values())' "$$tmp"

0.4-compiler-matrix:
	@set -eu; \
	for compiler in gcc clang; do \
		if command -v "$$compiler" >/dev/null 2>&1; then \
			for optimization in 0 3; do \
				binary=$$(mktemp); output=$$(mktemp); \
				"$$compiler" -std=c11 "-O$$optimization" -Wall -Wextra -Werror -pedantic ravel_0_4.c -lm -o "$$binary"; \
				"$$binary" > "$$output"; \
				diff -u ravel-0.4-raw-observations.json "$$output"; \
				rm -f "$$binary" "$$output"; \
			done; \
		fi; \
	done

0.4-sanitizers:
	@set -eu; \
	command -v "$(SAN_CC)" >/dev/null 2>&1 || { echo "sanitizer compiler unavailable: $(SAN_CC)" >&2; exit 1; }; \
	binary=$$(mktemp); output=$$(mktemp); \
	trap 'rm -f "$$binary" "$$output"' EXIT; \
	$(SAN_CC) -std=c11 -O1 -g -Wall -Wextra -Werror -pedantic \
		-fsanitize=address,undefined -fno-omit-frame-pointer \
		ravel_0_4.c -lm -o "$$binary"; \
	ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 "$$binary" > "$$output"; \
	diff -u ravel-0.4-raw-observations.json "$$output"

0.4-runtime: ravel_0_4_bin
	python3 tools/ravel_0_4_evidence.py runtime --binary ./ravel_0_4_bin --runs 3

0.5-test: ravel_0_5_bin
	@tmp=$$(mktemp); \
	trap 'rm -f "$$tmp"' EXIT; \
	./ravel_0_5_bin --self-test > "$$tmp"; \
	python3 -c 'import json,sys; r=json.load(open(sys.argv[1])); assert r["schema"] == "ravel-self-test-observations/0.5"; assert all(v["observed"] for v in r["fixtures"].values())' "$$tmp"

0.5-evidence: ravel_0_5_bin
	python3 tools/ravel_0_5_evidence.py generate --binary ./ravel_0_5_bin

0.5-check: ravel_0_5_bin
	python3 tools/ravel_0_5_evidence.py verify --binary ./ravel_0_5_bin --diagnostics-dir diagnostics-0.5
	python3 tools/ravel_0_5_source_digest.py verify \
		--spec ravel-0.5-source-manifest-spec.json \
		--manifest ravel-0.5-source-and-execution-manifest.json \
		--assurance ravel-0.5-assurance-case.json

0.5-development-gates:
	python3 tools/ravel_0_5_evidence.py development-gates

0.5-negative-test: ravel_0_5_bin
	$(MAKE) 0.5-test
	python3 tools/ravel_0_5_evidence.py mutation-tests
	python3 -c 'import json; r=json.load(open("ravel-0.5-negative-evidence.json")); assert r["all_negative_tests_pass"]; assert len(r["tests"]) == len(set(r["tests"]))'

0.5-manifest-negative-test:
	python3 tools/ravel_0_5_evidence.py manifest-negative-tests

0.5-compiler-matrix:
	@set -eu; \
	for compiler in gcc clang; do \
		if command -v "$$compiler" >/dev/null 2>&1; then \
			for optimization in 0 3; do \
				binary=$$(mktemp); \
				trap 'rm -f "$$binary"' EXIT; \
				"$$compiler" -std=c11 "-O$$optimization" -Wall -Wextra -Werror -pedantic ravel_0_5.c -lm -o "$$binary"; \
				python3 tools/ravel_0_5_evidence.py verify --binary "$$binary" --diagnostics-dir diagnostics-0.5; \
				rm -f "$$binary"; \
				trap - EXIT; \
			done; \
		fi; \
	done

0.5-sanitizers:
	@set -eu; \
	command -v "$(SAN_CC)" >/dev/null 2>&1 || { echo "sanitizer compiler unavailable: $(SAN_CC)" >&2; exit 1; }; \
	binary=$$(mktemp); \
	trap 'rm -f "$$binary"' EXIT; \
	$(SAN_CC) -std=c11 -O1 -g -Wall -Wextra -Werror -pedantic \
		-fsanitize=address,undefined -fno-omit-frame-pointer \
		ravel_0_5.c -lm -o "$$binary"; \
	ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 \
		python3 tools/ravel_0_5_evidence.py verify --binary "$$binary" --diagnostics-dir diagnostics-0.5

0.5-runtime: ravel_0_5_bin
	python3 tools/ravel_0_5_evidence.py runtime --binary ./ravel_0_5_bin --runs 3

0.5-clean:
	rm -f ravel_0_5_bin
	rm -rf diagnostics-0.5

all: test training-check unified-check 0.4-check 0.5-check

ravel: ravel.c
	$(CC) $(CFLAGS) $< -o $@

ravel_train: ravel_train.c
	$(CC) $(CFLAGS) $< $(LDLIBS) -o $@

ravel_unified_bin: ravel_unified.c ravel_unified/00_core.inc ravel_unified/10_route.inc ravel_unified/20_train.inc ravel_unified/30_eval.inc
	$(CC) $(CFLAGS) ravel_unified.c $(LDLIBS) -o $@

ravel_0_4_bin: ravel_0_4.c
	$(CC) $(CFLAGS) ravel_0_4.c $(LDLIBS) -o $@

ravel_0_5_bin: ravel_0_5.c
	$(CC) $(CFLAGS) ravel_0_5.c $(LDLIBS) -o $@

clean:
	rm -f ravel ravel_train ravel_unified_bin ravel_0_4_bin ravel_0_5_bin
	rm -f evidence-actual.json unified-actual.json ravel-unified-checkpoint.bin ravel-0.4-checkpoint.bin
	rm -rf diagnostics

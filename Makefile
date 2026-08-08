CC ?= cc
SAN_CC ?= clang
CFLAGS ?= -std=c11 -O3 -Wall -Wextra -Werror -pedantic
LDLIBS ?= -lm

BASELINE_DIR := ravel_versions/baseline
TRAINING_DIR := ravel_versions/training
UNIFIED_DIR := ravel_versions/unified
RAVEL_04_DIR := ravel_versions/0.4
RAVEL_05_DIR := ravel_versions/0.5

.PHONY: test evidence training-test training-evidence training-check \
        unified-test unified-evidence unified-check 0.4-evidence 0.4-check \
        0.4-manifest-negative-test 0.4-checkpoint-test 0.4-lineage-test 0.4-negative-test \
        0.4-compiler-matrix 0.4-sanitizers 0.4-runtime 0.5-test \
        0.5-evidence 0.5-check 0.5-development-gates 0.5-negative-test \
        0.5-manifest-negative-test 0.5-compiler-matrix 0.5-sanitizers \
        0.5-runtime 0.5-clean all clean

test: $(BASELINE_DIR)/ravel
	./$(BASELINE_DIR)/ravel >/dev/null

evidence: $(BASELINE_DIR)/ravel
	@tmp=$$(mktemp); trap 'rm -f "$$tmp"' EXIT; \
	./$(BASELINE_DIR)/ravel > "$$tmp"; mv "$$tmp" $(BASELINE_DIR)/evidence-actual.json

training-test: $(TRAINING_DIR)/ravel_train
	./$(TRAINING_DIR)/ravel_train >/dev/null

training-evidence: $(TRAINING_DIR)/ravel_train
	@tmp=$$(mktemp); trap 'rm -f "$$tmp"' EXIT; \
	./$(TRAINING_DIR)/ravel_train > "$$tmp"; mv "$$tmp" $(TRAINING_DIR)/training-evidence.json

training-check: $(TRAINING_DIR)/ravel_train
	@tmp=$$(mktemp); trap 'rm -f "$$tmp"' EXIT; \
	./$(TRAINING_DIR)/ravel_train > "$$tmp"; diff -u $(TRAINING_DIR)/training-evidence.json "$$tmp"

unified-test: $(UNIFIED_DIR)/ravel_unified_bin
	(cd $(UNIFIED_DIR) && ./ravel_unified_bin) >/dev/null

unified-evidence: $(UNIFIED_DIR)/ravel_unified_bin
	@tmp=$$(mktemp); trap 'rm -f "$$tmp"' EXIT; \
	(cd $(UNIFIED_DIR) && ./ravel_unified_bin) > "$$tmp"; mv "$$tmp" $(UNIFIED_DIR)/unified-evidence.json

unified-check: $(UNIFIED_DIR)/ravel_unified_bin
	@tmp=$$(mktemp); trap 'rm -f "$$tmp"' EXIT; \
	(cd $(UNIFIED_DIR) && ./ravel_unified_bin) > "$$tmp"; diff -u $(UNIFIED_DIR)/unified-evidence.json "$$tmp"

0.4-evidence: $(RAVEL_04_DIR)/ravel_0_4_bin
	python3 ravel_versions/0.4/run_evidence.py generate --binary ./$(RAVEL_04_DIR)/ravel_0_4_bin

0.4-check: $(RAVEL_04_DIR)/ravel_0_4_bin
	python3 ravel_versions/0.4/run_evidence.py verify --binary ./$(RAVEL_04_DIR)/ravel_0_4_bin --diagnostics-dir diagnostics
	python3 ravel_versions/0.4/run_source_digest.py verify --spec ravel-0.4-source-manifest-spec.json --manifest ravel-0.4-source-manifest.json --assurance ravel-0.4-assurance-case.json

0.4-manifest-negative-test:
	@tmp=$$(mktemp -d); trap 'rm -rf "$$tmp"' EXIT; cp -a . "$$tmp/ravel"; cd "$$tmp/ravel"; \
	python3 -c 'from pathlib import Path; p=Path("ravel_versions/0.4/RAVEL_0_4_CONTRACT.md"); p.write_bytes(p.read_bytes()+b"\\nmutation\\n")'; \
	if python3 ravel_versions/0.4/run_source_digest.py verify --spec ravel-0.4-source-manifest-spec.json --manifest ravel-0.4-source-manifest.json --assurance ravel-0.4-assurance-case.json >/dev/null 2>&1; then exit 1; fi

0.4-checkpoint-test: $(RAVEL_04_DIR)/ravel_0_4_bin
	@tmp=$$(mktemp); trap 'rm -f "$$tmp"' EXIT; \
	(cd $(RAVEL_04_DIR) && ./ravel_0_4_bin) > "$$tmp"; \
	python3 -c 'import json,sys; r=json.load(open(sys.argv[1])); assert all(t["checkpoint_verification"]["complete_behavior_match"] and all(t["checkpoint_verification"]["mutations"].values()) for t in r["trials"])' "$$tmp"

0.4-lineage-test: $(RAVEL_04_DIR)/ravel_0_4_bin
	@tmp=$$(mktemp); trap 'rm -f "$$tmp"' EXIT; \
	(cd $(RAVEL_04_DIR) && ./ravel_0_4_bin) > "$$tmp"; \
	python3 -c 'import json,sys; r=json.load(open(sys.argv[1])); assert all(all(t["lineage_invariants"].values()) for t in r["trials"])' "$$tmp"

0.4-negative-test: $(RAVEL_04_DIR)/ravel_0_4_bin
	@tmp=$$(mktemp); trap 'rm -f "$$tmp"' EXIT; \
	(cd $(RAVEL_04_DIR) && ./ravel_0_4_bin) > "$$tmp"; \
	python3 -c 'import json,sys; r=json.load(open(sys.argv[1])); assert all(v["pass"] for v in r["negative_tests"].values())' "$$tmp"

0.4-compiler-matrix:
	@set -eu; for compiler in gcc clang; do \
		if command -v "$$compiler" >/dev/null 2>&1; then \
			for optimization in 0 3; do binary=$$(mktemp); output=$$(mktemp); \
			"$$compiler" -std=c11 "-O$$optimization" -Wall -Wextra -Werror -pedantic $(RAVEL_04_DIR)/ravel_0_4.c -lm -o "$$binary"; \
			(cd $(RAVEL_04_DIR) && "$$binary") > "$$output"; diff -u $(RAVEL_04_DIR)/ravel-0.4-raw-observations.json "$$output"; rm -f "$$binary" "$$output"; done; \
		fi; done

0.4-sanitizers:
	@set -eu; command -v "$(SAN_CC)" >/dev/null 2>&1; binary=$$(mktemp); output=$$(mktemp); \
	trap 'rm -f "$$binary" "$$output"' EXIT; \
	$(SAN_CC) -std=c11 -O1 -g -Wall -Wextra -Werror -pedantic -fsanitize=address,undefined -fno-omit-frame-pointer $(RAVEL_04_DIR)/ravel_0_4.c -lm -o "$$binary"; \
	ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 sh -c 'cd "$(RAVEL_04_DIR)" && "$$0"' "$$binary" > "$$output"; diff -u $(RAVEL_04_DIR)/ravel-0.4-raw-observations.json "$$output"

0.4-runtime: $(RAVEL_04_DIR)/ravel_0_4_bin
	python3 ravel_versions/0.4/run_evidence.py runtime --binary ./$(RAVEL_04_DIR)/ravel_0_4_bin --runs 3

0.5-test: $(RAVEL_05_DIR)/ravel_0_5_bin
	@tmp=$$(mktemp); trap 'rm -f "$$tmp"' EXIT; \
	(cd $(RAVEL_05_DIR) && ./ravel_0_5_bin --self-test) > "$$tmp"; \
	python3 -c 'import json,sys; r=json.load(open(sys.argv[1])); assert r["schema"] == "ravel-self-test-observations/0.5"; assert all(v["observed"] for v in r["fixtures"].values())' "$$tmp"

0.5-evidence: $(RAVEL_05_DIR)/ravel_0_5_bin
	python3 ravel_versions/0.5/run_evidence.py generate --binary ./$(RAVEL_05_DIR)/ravel_0_5_bin

0.5-check: $(RAVEL_05_DIR)/ravel_0_5_bin
	python3 ravel_versions/0.5/run_evidence.py verify --binary ./$(RAVEL_05_DIR)/ravel_0_5_bin --diagnostics-dir diagnostics

0.5-development-gates:
	python3 ravel_versions/0.5/run_evidence.py development-gates

0.5-negative-test: $(RAVEL_05_DIR)/ravel_0_5_bin
	$(MAKE) 0.5-test
	python3 ravel_versions/0.5/run_evidence.py mutation-tests

0.5-manifest-negative-test:
	python3 ravel_versions/0.5/run_evidence.py manifest-negative-tests

0.5-compiler-matrix:
	@set -eu; for compiler in gcc clang; do \
		if command -v "$$compiler" >/dev/null 2>&1; then \
			for optimization in 0 3; do binary=$$(mktemp); \
			"$$compiler" -std=c11 "-O$$optimization" -Wall -Wextra -Werror -pedantic $(RAVEL_05_DIR)/ravel_0_5.c -lm -o "$$binary"; \
			python3 ravel_versions/0.5/run_evidence.py verify --binary "$$binary" --diagnostics-dir diagnostics; rm -f "$$binary"; done; \
		fi; done

0.5-sanitizers:
	@set -eu; command -v "$(SAN_CC)" >/dev/null 2>&1; binary=$$(mktemp); trap 'rm -f "$$binary"' EXIT; \
	$(SAN_CC) -std=c11 -O1 -g -Wall -Wextra -Werror -pedantic -fsanitize=address,undefined -fno-omit-frame-pointer $(RAVEL_05_DIR)/ravel_0_5.c -lm -o "$$binary"; \
	python3 ravel_versions/0.5/run_evidence.py verify --binary "$$binary" --diagnostics-dir diagnostics

0.5-runtime: $(RAVEL_05_DIR)/ravel_0_5_bin
	python3 ravel_versions/0.5/run_evidence.py runtime --binary ./$(RAVEL_05_DIR)/ravel_0_5_bin --runs 3

0.5-clean:
	$(MAKE) clean

all: test training-check unified-check 0.4-check 0.5-check

$(BASELINE_DIR)/ravel: $(BASELINE_DIR)/ravel.c
	$(CC) $(CFLAGS) $< -o $@

$(TRAINING_DIR)/ravel_train: $(TRAINING_DIR)/ravel_train.c
	$(CC) $(CFLAGS) $< $(LDLIBS) -o $@

$(UNIFIED_DIR)/ravel_unified_bin: $(UNIFIED_DIR)/ravel_unified.c $(UNIFIED_DIR)/ravel_unified/00_core.inc $(UNIFIED_DIR)/ravel_unified/10_route.inc $(UNIFIED_DIR)/ravel_unified/20_train.inc $(UNIFIED_DIR)/ravel_unified/30_eval.inc
	$(CC) $(CFLAGS) $(UNIFIED_DIR)/ravel_unified.c $(LDLIBS) -o $@

$(RAVEL_04_DIR)/ravel_0_4_bin: $(RAVEL_04_DIR)/ravel_0_4.c
	$(CC) $(CFLAGS) $< $(LDLIBS) -o $@

$(RAVEL_05_DIR)/ravel_0_5_bin: $(RAVEL_05_DIR)/ravel_0_5.c
	$(CC) $(CFLAGS) $< $(LDLIBS) -o $@

clean:
	rm -f $(BASELINE_DIR)/ravel $(TRAINING_DIR)/ravel_train $(UNIFIED_DIR)/ravel_unified_bin $(RAVEL_04_DIR)/ravel_0_4_bin $(RAVEL_05_DIR)/ravel_0_5_bin
	rm -f $(BASELINE_DIR)/evidence-actual.json $(UNIFIED_DIR)/unified-actual.json ravel-unified-checkpoint.bin ravel-0.4-checkpoint.bin ravel-0.5-checkpoint.bin $(UNIFIED_DIR)/ravel-unified-checkpoint.bin $(RAVEL_04_DIR)/ravel-0.4-checkpoint.bin $(RAVEL_05_DIR)/ravel-0.5-checkpoint.bin
	rm -rf $(RAVEL_04_DIR)/diagnostics $(RAVEL_05_DIR)/diagnostics

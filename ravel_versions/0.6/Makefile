CC ?= cc
CFLAGS ?= -std=c11 -O3 -Wall -Wextra -Werror -pedantic

.PHONY: build behavioral-test transaction-test component-test compiler-matrix sanitizers

build:
	@set -e; out=$$(mktemp -d); python3 tools/ravel_0_6_build.py build --output-dir "$$out"; \
	printf 'RAVEL 0.6 development build directory: %s\n' "$$out"

behavioral-test:
	python3 tools/ravel_0_6_behavioral_fixtures.py

transaction-test:
	python3 -m unittest tests/test_ravel_0_6_transaction.py

component-test:
	python3 -m unittest tests/test_components.py tests/test_lifecycle_experience.py

compiler-matrix:
	@set -eu; for compiler in gcc clang; do \
		if command -v "$$compiler" >/dev/null 2>&1; then \
			out=$$(mktemp -d); CC="$$compiler" python3 tools/ravel_0_6_build.py build --output-dir "$$out" >/dev/null; \
			"$$out/ravel_0_6_candidate_001" --self-test >/dev/null; \
			find "$$out" -type f -delete; rmdir "$$out"; \
			printf '%s: PASS\n' "$$compiler"; \
		else printf '%s: UNAVAILABLE\n' "$$compiler"; fi; \
	done

sanitizers:
	@set -eu; if command -v clang >/dev/null 2>&1; then \
		out=$$(mktemp -d); python3 tools/ravel_0_6_seed_candidate.py --output "$$out/candidate.c" >/dev/null; \
		clang -std=c11 -O1 -g -Wall -Wextra -Werror -pedantic -fsanitize=address,undefined "$$out/candidate.c" -lm -o "$$out/candidate"; \
		ASAN_OPTIONS=detect_leaks=0 "$$out/candidate" --self-test >/dev/null; \
		find "$$out" -type f -delete; rmdir "$$out"; printf 'clang ASAN/UBSAN: PASS\n'; \
	else printf 'clang ASAN/UBSAN: UNAVAILABLE\n'; fi

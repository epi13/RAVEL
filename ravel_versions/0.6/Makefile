CC ?= cc
CFLAGS ?= -std=c11 -O3 -Wall -Wextra -Werror -pedantic

.PHONY: build behavioral-test transaction-test component-test policy-test decomposition-test negative-test provider-test evaluator-test forge-test receipt-test abi-test compiler-matrix sanitizers

build:
	@set -e; out=$$(mktemp -d); python3 tools/ravel_0_6_build.py build --output-dir "$$out"; \
	printf 'RAVEL 0.6 development build directory: %s\n' "$$out"

behavioral-test:
	python3 tools/ravel_0_6_behavioral_fixtures.py

transaction-test:
	python3 -m unittest tests/test_ravel_0_6_transaction.py

component-test:
	python3 -m unittest tests/test_components.py tests/test_lifecycle_experience.py

policy-test:
	python3 -m unittest tests/test_policy.py tests/test_frozen_identities.py

decomposition-test:
	python3 -m unittest tests/test_ravel_0_6_decomposition.py

negative-test:
	python3 -m unittest tests/test_ravel_0_6_negative_matrix.py

provider-test:
	RAVEL06_PROVIDER=branching python3 -m unittest tests/test_ravel_0_6_decomposition.py

evaluator-test:
	python3 -m unittest tests/test_ravel_0_6_transaction.py

forge-test:
	python3 -m unittest tests/test_providers_resources.py tests/test_forge_integration.py

receipt-test:
	python3 -m unittest tests/test_mncs_receipts.py

abi-test:
	python3 -m unittest tests/test_ravel_0_6_decomposition.py tests/test_mncs_bundles.py

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
		out=$$(mktemp -d); RAVEL06_EXTRA_CFLAGS='-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer' CC=clang python3 tools/ravel_0_6_build.py build --output-dir "$$out" >/dev/null; \
		ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 "$$out/ravel_0_6_candidate_001" --self-test >/dev/null; \
		find "$$out" -type f -delete; rmdir "$$out"; printf 'clang ASAN/UBSAN: PASS\n'; \
	else printf 'clang ASAN/UBSAN: UNAVAILABLE\n'; fi

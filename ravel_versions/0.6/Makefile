CC ?= cc
CFLAGS ?= -std=c11 -O3 -Wall -Wextra -Werror -pedantic

.PHONY: build behavioral-test

build:
	@set -e; out=$$(mktemp -d); python3 tools/ravel_0_6_build.py build --output-dir "$$out"; \
	printf 'RAVEL 0.6 development build directory: %s\n' "$$out"

behavioral-test:
	python3 tools/ravel_0_6_behavioral_fixtures.py

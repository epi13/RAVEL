CC ?= cc
CFLAGS ?= -std=c11 -O3 -Wall -Wextra -Werror -pedantic
LDLIBS ?= -lm

.PHONY: test evidence training-test training-evidence training-check unified-test unified-evidence unified-check all clean

test: ravel
	./ravel >/dev/null

evidence: ravel
	./ravel | tee evidence.json

training-test: ravel_train
	./ravel_train >/dev/null

training-evidence: ravel_train
	./ravel_train | tee training-evidence.json

training-check: ravel_train
	@tmp=$$(mktemp); \
	trap 'rm -f "$$tmp"' EXIT; \
	./ravel_train > "$$tmp"; \
	diff -u training-evidence.json "$$tmp"

unified-test: ravel_unified_bin
	./ravel_unified_bin >/dev/null

unified-evidence: ravel_unified_bin
	./ravel_unified_bin | tee unified-evidence.json

unified-check: ravel_unified_bin
	./ravel_unified_bin > unified-actual.json
	diff -u unified-evidence.json unified-actual.json

all: test training-check unified-check

ravel: ravel.c
	$(CC) $(CFLAGS) $< -o $@

ravel_train: ravel_train.c
	$(CC) $(CFLAGS) $< $(LDLIBS) -o $@

ravel_unified_bin: ravel_unified.c ravel_unified/00_core.inc ravel_unified/10_route.inc ravel_unified/20_train.inc ravel_unified/30_eval.inc
	$(CC) $(CFLAGS) ravel_unified.c $(LDLIBS) -o $@

clean:
	rm -f ravel ravel_train ravel_unified_bin evidence.json unified-actual.json ravel-unified-checkpoint.bin

CC ?= cc
CFLAGS ?= -std=c11 -O3 -Wall -Wextra -Werror -pedantic

.PHONY: test evidence clean

test: ravel
	./ravel >/dev/null

evidence: ravel
	./ravel | tee evidence.json

ravel: ravel.c
	$(CC) $(CFLAGS) $< -o $@

clean:
	rm -f ravel evidence.json

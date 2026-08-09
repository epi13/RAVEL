#ifndef RAVEL_0_6_CHECKPOINT_H
#define RAVEL_0_6_CHECKPOINT_H

#include <stddef.h>

#define RAVEL06_CHECKPOINT_ABI_VERSION "ravel-0.6-checkpoint-abi/1"

/* Pure byte-level contract used by the development transaction boundary. */
int ravel06_checkpoint_bytes_equal(const void *left, const void *right,
                                   size_t length);

#endif

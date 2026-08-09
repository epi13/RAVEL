#include "ravel_0_6_checkpoint.h"

#include <stddef.h>

int ravel06_checkpoint_bytes_equal(const void *left, const void *right,
                                   size_t length) {
    const unsigned char *left_bytes = (const unsigned char *)left;
    const unsigned char *right_bytes = (const unsigned char *)right;
    size_t index;

    if (left == NULL || right == NULL) return left == right && length == 0u;
    for (index = 0u; index < length; ++index) {
        if (left_bytes[index] != right_bytes[index]) return 0;
    }
    return 1;
}

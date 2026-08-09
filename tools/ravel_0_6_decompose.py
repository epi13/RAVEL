"""Deterministically split generated candidate source into bounded C units.

The pieces are included in one unity translation unit for this extraction
iteration.  This preserves the frozen-source-derived static linkage and exact
behavior while making each maintained mechanism surface independently
addressable and provenance-bound.  A future iteration may promote selected
pieces to separately compiled units after a header contract is frozen.
"""

from __future__ import annotations

from pathlib import Path


COMPONENT_BOUNDARIES = (
    ("ravel_0_6_preamble.inc", "static uint64_t rng_state"),
    ("ravel_0_6_core.inc", "static void make_world"),
    ("ravel_0_6_world.inc", "static double dist_x"),
    ("ravel_0_6_mechanism.inc", "static uint16_t nearest_vector"),
    ("ravel_0_6_transition.inc", "static Eval evaluate"),
    ("ravel_0_6_planning.inc", "static void bb_bytes"),
    ("ravel_0_6_checkpoint.inc", "static int eval_equal"),
    ("ravel_0_6_observations.inc", "static void digest_hex"),
    ("ravel_0_6_reporting.inc", "static int run_trial"),
    ("ravel_0_6_driver.inc", None),
)


class DecompositionError(ValueError):
    """Raised when a generated source does not match the extraction contract."""


def split_candidate_source(source: str) -> tuple[tuple[str, str], ...]:
    starts: list[int] = []
    for _, marker in COMPONENT_BOUNDARIES[:-1]:
        if marker is None:
            raise DecompositionError("non-final component has no boundary marker")
        matches = [position for position in range(len(source)) if source.startswith(marker, position)]
        if len(matches) != 1:
            raise DecompositionError(f"expected one component marker {marker!r}, found {len(matches)}")
        starts.append(matches[0])
    if starts != sorted(starts):
        raise DecompositionError("component markers are not ordered")
    pieces: list[tuple[str, str]] = []
    first_name = COMPONENT_BOUNDARIES[0][0]
    pieces.append((first_name, source[: starts[0]]))
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(source)
        pieces.append((COMPONENT_BOUNDARIES[index + 1][0], source[start:end]))
    if "".join(piece for _, piece in pieces) != source:
        raise DecompositionError("component extraction is not lossless")
    return tuple(pieces)


def write_decomposed_candidate(source: str, output_dir: Path) -> tuple[Path, tuple[Path, ...]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    pieces = split_candidate_source(source)
    paths: list[Path] = []
    for name, content in pieces:
        path = output_dir / name
        if path.exists():
            raise DecompositionError(f"stale generated component exists: {path}")
        path.write_text(content, encoding="utf-8", newline="\n")
        paths.append(path)
    wrapper = output_dir / "ravel_0_6_candidate_001.c"
    if wrapper.exists():
        raise DecompositionError(f"stale generated wrapper exists: {wrapper}")
    wrapper.write_text(
        "/* generated unity wrapper; component bytes are provenance-bound */\n"
        + "\n".join(f'#include "{path.name}"' for path in paths)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return wrapper, tuple(paths)

"""Persistent content-keyed cache for RAVEL verification plans.

A no-change verification plan is pure reconstruction: the same source
bytes, roots, bounds, provider inputs, and planner closure always produce
the identical validated plan, yet the normal path pays a compiler impact
pass plus a native-application admission (process spawn, ~30MB artifact
reload, fresh execution session) on every call, in every process.  Forge
post-repair replanning shells out to ``ravel-impact`` per repair
iteration, so an in-memory cache cannot help the real consumer.

This module provides a small persistent cache keyed *only* by content
identities plus the resolved source path (the plan embeds the path, so
identical bytes at different paths are different plans).  There is no
TTL and no generation protocol: an entry is valid if and only if its
key material still matches, and every hit is re-validated against the
Commons contract before it is returned.  Corruption, schema drift, or
any I/O failure degrades to a cache miss, never to a wrong plan.

Callers that compute repository-canonical obligation context (git/cargo
state that is not content-addressed here) must bypass the cache; see
:func:`ravel.impact.request_verification_plan`.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from collections.abc import Mapping

CACHE_SCHEMA = "ravel.plan-cache-entry/1"
KEY_SCHEMA = "ravel.plan-cache-key/1"
# Bounds keep the cache a bounded hot layer, not an unbounded heap.
# Plans are a few KiB each; these caps are generous on purpose.
DEFAULT_MAX_ENTRIES = 512
DEFAULT_MAX_BYTES = 64 * 1024 * 1024
# Library roots larger than this are not content-addressed; the caller
# must bypass the cache for them (fail closed, not mtime-guessed).
MAX_TREE_FILES = 4096
MAX_TREE_BYTES = 64 * 1024 * 1024


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def digest_file(path: Path) -> str | None:
    """SHA-256 of a file's bytes, or None when unreadable (fail open)."""
    try:
        hasher = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return None


def digest_tree(root: Path) -> str | None:
    """Content identity of a library root, or None when it cannot be taken.

    The digest covers sorted (relative path, kind, content) triples so a
    rename, addition, removal, or byte change alters the identity.
    Symlinked files contribute their target bytes; symlinked directories
    are not descended (their link text is hashed instead), which keeps
    the walk bounded and cycle-free.  Roots exceeding
    ``MAX_TREE_FILES``/``MAX_TREE_BYTES`` return None so the caller can
    bypass the cache rather than trust a weaker fingerprint.
    """
    try:
        resolved = root.resolve()
    except OSError:
        return None
    if not resolved.is_dir():
        return digest_file(resolved)
    entries: list[tuple[str, str, bytes]] = []
    total_bytes = 0
    count = 0
    stack: list[Path] = [resolved]
    try:
        while stack:
            current = stack.pop()
            with os.scandir(current) as iterator:
                children = sorted(iterator, key=lambda entry: entry.name)
            for child in children:
                try:
                    relative = str(Path(child.path).relative_to(resolved))
                except ValueError:
                    return None
                if child.is_symlink():
                    try:
                        target = os.readlink(child.path)
                    except OSError:
                        return None
                    # A symlink to a file contributes the target bytes; a
                    # symlink to a directory (or a dangling link)
                    # contributes its link text and is never descended.
                    try:
                        if Path(child.path).is_file():
                            blob = Path(child.path).read_bytes()
                        else:
                            blob = f"link:{target}".encode("utf-8")
                    except OSError:
                        return None
                    entries.append((relative, "file", blob))
                elif child.is_dir(follow_symlinks=False):
                    stack.append(Path(child.path))
                    entries.append((relative, "dir", b""))
                elif child.is_file(follow_symlinks=False):
                    try:
                        blob = Path(child.path).read_bytes()
                    except OSError:
                        return None
                    entries.append((relative, "file", blob))
                else:
                    entries.append((relative, "other", b""))
                count += 1
                total_bytes += len(entries[-1][2])
                if count > MAX_TREE_FILES or total_bytes > MAX_TREE_BYTES:
                    return None
    except OSError:
        return None
    hasher = hashlib.sha256()
    for relative, kind, blob in sorted(entries):
        hasher.update(relative.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(kind.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(str(len(blob)).encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(blob)
    return hasher.hexdigest()


def _tool_memo_path(cache_dir: Path) -> Path:
    return cache_dir / ".tool-digests.json"


def tool_digest(executable: Path, *, cache_dir: Path | None = None) -> str:
    """Exact content identity of a provider binary with memoization.

    Hashing a ~230MB runtime on every plan would cost real time, so the
    digest is memoized in a sidecar keyed by (size, mtime, ctime).  Any
    replacement changes ctime at minimum, so a memoized digest is only
    reused for a byte-identical file; when the sidecar is unavailable
    the binary is hashed directly.
    """
    try:
        stat = executable.stat()
    except OSError:
        return f"unavailable:{executable}"
    marker = [stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns]
    memo: dict[str, Any] = {}
    memo_path = _tool_memo_path(cache_dir) if cache_dir is not None else None
    if memo_path is not None:
        try:
            loaded = json.loads(memo_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                memo = loaded
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            memo = {}
        slot = memo.get(str(executable))
        if (
            isinstance(slot, dict)
            and slot.get("marker") == marker
            and isinstance(slot.get("sha256"), str)
        ):
            return f"sha256:{slot['sha256']}"
    digest = digest_file(executable)
    if digest is None:
        return f"unavailable:{executable}"
    if memo_path is not None:
        memo[str(executable)] = {"marker": marker, "sha256": digest}
        try:
            memo_path.parent.mkdir(parents=True, exist_ok=True)
            memo_path.write_text(
                json.dumps(memo, sort_keys=True, ensure_ascii=True), encoding="utf-8"
            )
        except OSError:
            pass
    return f"sha256:{digest}"


def cache_key(material: Mapping[str, Any]) -> str:
    """Derive the entry key from fully assembled key material."""
    return sha256_bytes(canonical_json(dict(material)))


@dataclass
class PlanCache:
    """Bounded persistent plan cache.  All failures degrade to a miss."""

    directory: Path | None = None
    enabled: bool | None = None
    max_entries: int = DEFAULT_MAX_ENTRIES
    max_bytes: int = DEFAULT_MAX_BYTES
    hits: int = field(default=0, init=False)
    misses: int = field(default=0, init=False)
    stores: int = field(default=0, init=False)
    errors: int = field(default=0, init=False)
    skips: int = field(default=0, init=False)

    def is_enabled(self) -> bool:
        if self.enabled is not None:
            return self.enabled
        return os.environ.get("RAVEL_PLAN_CACHE", "").lower() != "off"

    def resolve(self, base: Path) -> Path | None:
        """Resolve the cache directory without creating it."""
        if not self.is_enabled():
            return None
        configured = os.environ.get("RAVEL_PLAN_CACHE_DIR")
        if self.directory is not None:
            return self.directory
        if configured:
            return Path(configured)
        return base / ".mncs" / "cache" / "ravel-plans"

    def _entry_path(self, directory: Path, key: str) -> Path | None:
        if not key or "/" in key or "\\" in key or key in (".", ".."):
            return None
        return directory / f"{key}.json"

    def lookup(self, directory: Path, key: str, material: Mapping[str, Any]) -> dict[str, Any] | None:
        """Return the cached plan when the entry still matches, else None."""
        path = self._entry_path(directory, key)
        if path is None:
            self.errors += 1
            return None
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            self.misses += 1
            return None
        if (
            not isinstance(entry, dict)
            or entry.get("schema_version") != CACHE_SCHEMA
            or entry.get("key") != key
            or entry.get("material") != dict(material)
            or not isinstance(entry.get("plan"), dict)
        ):
            self.misses += 1
            return None
        # Touch for recency before returning; failure is immaterial.
        try:
            os.utime(path, None)
        except OSError:
            pass
        self.hits += 1
        return dict(entry["plan"])

    def store(self, directory: Path, key: str, material: Mapping[str, Any], plan: Mapping[str, Any]) -> None:
        """Persist a validated plan under its key (atomic, bounded)."""
        path = self._entry_path(directory, key)
        if path is None:
            self.errors += 1
            return
        entry = {
            "schema_version": CACHE_SCHEMA,
            "key": key,
            "material": dict(material),
            "plan": dict(plan),
        }
        try:
            directory.mkdir(parents=True, exist_ok=True)
            tmp_path = directory / f".tmp-{os.getpid()}-{key[:16]}.json"
            tmp_path.write_text(
                json.dumps(entry, sort_keys=True, ensure_ascii=True), encoding="utf-8"
            )
            os.replace(tmp_path, path)
        except OSError:
            self.errors += 1
            return
        self.stores += 1
        self._enforce_bounds(directory)

    def _enforce_bounds(self, directory: Path) -> None:
        try:
            candidates = [
                (entry.stat().st_mtime_ns, entry.stat().st_size, entry)
                for entry in directory.glob("*.json")
                if entry.is_file() and not entry.name.startswith(".tmp-")
            ]
        except OSError:
            return
        total = sum(size for _, size, _ in candidates)
        if len(candidates) <= self.max_entries and total <= self.max_bytes:
            return
        for _, _, entry in sorted(candidates):
            if len(candidates) <= self.max_entries and total <= self.max_bytes:
                break
            try:
                size = entry.stat().st_size
                entry.unlink()
            except OSError:
                break
            total -= size
            candidates = [item for item in candidates if item[2] != entry]

    def remove_cache_dir(self) -> None:  # test/maintenance helper
        target = self.directory or (
            Path(os.environ["RAVEL_PLAN_CACHE_DIR"]) if os.environ.get("RAVEL_PLAN_CACHE_DIR") else None
        )
        if target is not None:
            shutil.rmtree(target, ignore_errors=True)

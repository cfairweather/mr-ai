"""Per-file line counts from a unified diff.

The reviewer truncates large diffs, so it helps to tell the model how big the
change actually was and which files dominate it — otherwise a review of the
first 200KB reads as though it covered everything.

Counts follow `git diff --numstat`: `+++`/`---` headers are file markers, not
content, and a `\\ No newline at end of file` marker is neither.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")


@dataclass(frozen=True)
class FileStat:
    """Added and removed line counts for one file in a diff."""

    path: str
    added: int
    removed: int

    @property
    def churn(self) -> int:
        return self.added + self.removed


def parse_diffstat(diff: str) -> list[FileStat]:
    """Return per-file stats, ordered by churn descending then path.

    Unparseable input yields an empty list rather than raising: this feeds a
    prompt, and a missing statistic is a far better outcome than a failed
    review.
    """
    stats: dict[str, list[int]] = {}
    current: str | None = None
    in_hunk = False

    for line in diff.splitlines():
        if line.startswith("diff --git "):
            # "diff --git a/path b/path" — take the b-side, which is the
            # post-change path and so the one that exists for renames.
            parts = line.split(" b/", 1)
            current = parts[1].strip() if len(parts) == 2 else None
            in_hunk = False
            if current:
                stats.setdefault(current, [0, 0])
            continue

        if current is None:
            continue

        if _HUNK.match(line):
            in_hunk = True
            continue

        if not in_hunk:
            continue

        # Inside a hunk, +++/--- cannot appear as content, and the
        # no-newline marker is metadata.
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("\\"):
            continue
        if line.startswith("+"):
            stats[current][0] += 1
        elif line.startswith("-"):
            stats[current][1] += 1

    result = [FileStat(p, a, r) for p, (a, r) in stats.items()]
    result.sort(key=lambda s: (-s.churn, s.path))
    return result


def format_diffstat(stats: list[FileStat], limit: int = 10) -> str:
    """Render stats as a short markdown list for inclusion in a prompt."""
    if not stats:
        return "(no file statistics available)"
    lines = [f"- `{s.path}` +{s.added}/-{s.removed}" for s in stats[:limit]]
    if len(stats) > limit:
        hidden = stats[limit:]
        lines.append(
            f"- … {len(hidden)} more file(s), "
            f"+{sum(s.added for s in hidden)}/-{sum(s.removed for s in hidden)}"
        )
    return "\n".join(lines)

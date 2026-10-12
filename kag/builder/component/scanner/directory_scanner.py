from __future__ import annotations

import os
import re
from collections.abc import Iterator

# MixReader raises on any suffix it cannot dispatch, so anything outside this
# list has to be filtered out here rather than crash the reader later.
_DEFAULT_SUFFIXES = (".txt", ".pdf", ".docx", ".md", ".xlsx", ".json")


class DirectoryScanner:
    """List readable document files under a directory.

    A plain helper version of kag's scanner, without the sharding machinery this
    project does not use.
    """

    def __init__(
        self,
        suffixes: tuple[str, ...] = _DEFAULT_SUFFIXES,
        file_pattern: str | None = None,
    ):
        if file_pattern is not None:
            self._regex = re.compile(file_pattern)
        else:
            alternation = "|".join(re.escape(s) for s in suffixes)
            self._regex = re.compile(rf".*({alternation})$", re.IGNORECASE)

    def find_files(self, directory: str) -> list[str]:
        """Return the sorted paths of readable files under directory.

        Office lock files like ~$Foo.xlsx end in a real suffix, so they pass the
        filter and reach the reader as invalid documents unless skipped here.
        """
        matched: list[str] = []
        for root, _dirs, files in os.walk(directory):
            for name in files:
                if name.startswith("~$") or name.startswith("."):
                    continue  # Office temp/owner-lock files and hidden files
                if self._regex.match(name):
                    matched.append(os.path.join(root, name))
        return sorted(matched)

    def generate(self, directory: str) -> Iterator[str]:
        """Yield matching file paths one at a time (producer for the runner)."""
        yield from self.find_files(directory)

    def size(self, directory: str) -> int:
        """Number of files that will be produced (for progress)."""
        return len(self.find_files(directory))

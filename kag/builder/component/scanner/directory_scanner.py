from __future__ import annotations

import os
import re
from collections.abc import Iterator

# Suffixes MixReader can dispatch. MixReader raises on any other suffix, so the
# scanner filters to these -- otherwise junk files (.DS_Store, images, .json,
# and office lock files like ".~lock.foo.xlsx#") would crash the reader instead
# of being ignored. The trailing "$" anchors the suffix, so "foo.xlsx#" (a lock
# file) is NOT matched -- only real "foo.xlsx".
_DEFAULT_SUFFIXES = (".txt", ".pdf", ".docx", ".md", ".xlsx", ".json")


class DirectoryScanner:
    """List document files under a directory.

    The ``os.walk`` + regex logic from kag's ``DirectoryScanner``
    (``find_files_by_regex``), as a plain helper -- without the ``knext``
    BuilderComponent / sharding machinery this project does not use. Like the
    original it filters by pattern/suffix; the default matches the file types
    MixReader can actually read.
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
        """Return the sorted paths of matching files under ``directory``.

        Office/LibreOffice owner-lock and temp files (``~$Foo.xlsx``,
        ``.~lock.Foo.docx#``, ``.DS_Store``) are skipped: ``~$Foo.xlsx`` ends in a
        real suffix so it would otherwise match the filter and crash the reader,
        since it is not a valid document.
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

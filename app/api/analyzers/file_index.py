import re
from fnmatch import fnmatch
from os.path import basename
from typing import Optional


class FileIndex:
    def __init__(self, files: dict[str, str]):
        self.files = files

    @property
    def paths(self) -> list[str]:
        return sorted(self.files.keys())

    def find_by_name(self, name: str) -> list[str]:
        return [p for p in self.files if basename(p) == name]

    def find_by_ext(self, ext: str) -> list[str]:
        if not ext.startswith("."):
            ext = "." + ext
        return [p for p in self.files if p.endswith(ext)]

    def find_by_pattern(self, pattern: str) -> list[str]:
        return [p for p in self.files if fnmatch(p, pattern) or fnmatch(basename(p), pattern)]

    def get_content(self, path: str) -> Optional[str]:
        return self.files.get(path)

    def search_content(self, pattern: str) -> list[tuple[str, int, str]]:
        rx = re.compile(pattern)
        results: list[tuple[str, int, str]] = []
        for path, content in self.files.items():
            for lineno, line in enumerate(content.splitlines(), start=1):
                if rx.search(line):
                    results.append((path, lineno, line))
        return results

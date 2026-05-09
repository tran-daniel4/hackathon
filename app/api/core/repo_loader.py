from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import quote, urlparse

from pipeline.scanner import _MAX_FILE_BYTES, _SKIP_DIRS, _SKIP_EXTENSIONS


@dataclass
class RepoSnapshot:
    root: Path
    repo_name: str
    repo_url: str
    branch: Optional[str]
    commit_sha: Optional[str]
    _tempdir: tempfile.TemporaryDirectory[str]

    def cleanup(self) -> None:
        self._tempdir.cleanup()


def is_github_repo_url(repo_url: str) -> bool:
    parsed = urlparse(repo_url)
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() in {"github.com", "www.github.com"}


def clone_github_repo(
    repo_url: str,
    branch: str | None = None,
    github_token: str | None = None,
    timeout_seconds: int = 120,
) -> RepoSnapshot:
    if not is_github_repo_url(repo_url):
        raise ValueError("Only GitHub repository URLs are supported for backend repo analysis")

    if shutil.which("git") is None:
        raise RuntimeError("git is not installed on the server")

    owner, repo_name, inferred_branch = _parse_github_repo_url(repo_url)
    effective_branch = branch or inferred_branch
    display_url = f"https://github.com/{owner}/{repo_name}"
    clone_url = _build_clone_url(owner, repo_name, github_token)

    tempdir = tempfile.TemporaryDirectory(prefix="diagrammer-repo-")
    repo_root = Path(tempdir.name) / repo_name

    cmd = ["git", "clone", "--depth", "1"]
    if effective_branch:
        cmd.extend(["--branch", effective_branch])
    cmd.extend([clone_url, str(repo_root)])

    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        tempdir.cleanup()
        raise RuntimeError("Timed out while cloning the GitHub repository") from exc

    if completed.returncode != 0:
        tempdir.cleanup()
        raise RuntimeError("Failed to clone the GitHub repository")

    commit_sha = _git_output(repo_root, ["rev-parse", "HEAD"])
    resolved_branch = _git_output(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"]) or effective_branch

    return RepoSnapshot(
        root=repo_root,
        repo_name=repo_name,
        repo_url=display_url,
        branch=resolved_branch,
        commit_sha=commit_sha,
        _tempdir=tempdir,
    )


def get_github_repo_head_sha(
    repo_url: str,
    branch: str | None = None,
    github_token: str | None = None,
    timeout_seconds: int = 30,
) -> str | None:
    if not is_github_repo_url(repo_url):
        return None
    if shutil.which("git") is None:
        return None

    owner, repo_name, inferred_branch = _parse_github_repo_url(repo_url)
    effective_branch = branch or inferred_branch or "HEAD"
    clone_url = _build_clone_url(owner, repo_name, github_token)

    try:
        completed = subprocess.run(
            ["git", "ls-remote", clone_url, effective_branch],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None

    if completed.returncode != 0:
        return None

    first_line = completed.stdout.strip().splitlines()
    if not first_line:
        return None
    return first_line[0].split()[0] if first_line[0].split() else None


def load_repo_files(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    root = root.resolve()

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for filename in filenames:
            path = Path(dirpath) / filename
            if path.suffix.lower() in _SKIP_EXTENSIONS:
                continue
            try:
                if path.stat().st_size > _MAX_FILE_BYTES:
                    continue
                rel = str(path.relative_to(root)).replace("\\", "/")
                files[rel] = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

    return files


def _parse_github_repo_url(repo_url: str) -> tuple[str, str, str | None]:
    parsed = urlparse(repo_url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise ValueError("GitHub repository URLs must look like https://github.com/<owner>/<repo>")

    owner = parts[0]
    repo_name = parts[1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    branch = None
    if len(parts) >= 4 and parts[2] == "tree":
        branch = "/".join(parts[3:])

    return owner, repo_name, branch


def _build_clone_url(owner: str, repo_name: str, github_token: str | None) -> str:
    if github_token:
        quoted = quote(github_token, safe="")
        return f"https://x-access-token:{quoted}@github.com/{owner}/{repo_name}.git"
    return f"https://github.com/{owner}/{repo_name}.git"


def _git_output(repo_root: Path, args: list[str]) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from core.repo_loader import is_github_repo_url, load_repo_files, clone_github_repo


def test_is_github_repo_url():
    assert is_github_repo_url("https://github.com/openai/openai-python")
    assert is_github_repo_url("http://www.github.com/openai/openai-python")
    assert not is_github_repo_url("https://gitlab.com/openai/openai-python")
    assert not is_github_repo_url("openai/openai-python")


def test_load_repo_files_skips_large_and_binaryish_entries():
    files = load_repo_files(Path(os.path.dirname(__file__)))
    assert "test_repo_loader.py" in files
    assert not any(path.startswith(".venv/") for path in files)


def test_clone_github_repo_rejects_non_github_urls():
    try:
        clone_github_repo("https://gitlab.com/openai/openai-python")
    except ValueError as exc:
        assert "GitHub" in str(exc)
    else:
        raise AssertionError("Expected ValueError for non-GitHub URLs")


if __name__ == "__main__":
    test_is_github_repo_url()
    test_load_repo_files_skips_large_and_binaryish_entries()
    test_clone_github_repo_rejects_non_github_urls()
    print("repo_loader tests passed")

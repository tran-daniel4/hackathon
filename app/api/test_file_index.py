"""Unit tests for FileIndex."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from analyzers.file_index import FileIndex


def test_find_by_ext():
    fi = FileIndex({
        "foo/bar.py": "import os",
        "baz/package.json": '{"name":"x"}',
        "baz/index.ts": "console.log(1)",
    })
    assert sorted(fi.find_by_ext(".py")) == ["foo/bar.py"]
    assert sorted(fi.find_by_ext("py")) == ["foo/bar.py"]
    assert sorted(fi.find_by_ext(".ts")) == ["baz/index.ts"]
    assert fi.find_by_ext(".rb") == []


def test_find_by_name():
    fi = FileIndex({
        "app/api/main.py": "",
        "app/web/package.json": "",
        "package.json": "",
    })
    results = sorted(fi.find_by_name("package.json"))
    assert results == ["app/web/package.json", "package.json"]
    assert fi.find_by_name("main.py") == ["app/api/main.py"]


def test_find_by_pattern():
    fi = FileIndex({
        "app/api/main.py": "",
        "app/web/src/index.ts": "",
        "docker-compose.yml": "",
    })
    assert fi.find_by_pattern("*.yml") == ["docker-compose.yml"]
    assert "app/api/main.py" in fi.find_by_pattern("*.py")


def test_get_content():
    fi = FileIndex({"foo.py": "hello"})
    assert fi.get_content("foo.py") == "hello"
    assert fi.get_content("missing.py") is None


def test_search_content():
    fi = FileIndex({
        "foo/bar.py": "import os\nimport sys\nprint('hello')",
        "baz/index.ts": "const x = 1;\nconsole.log(x)",
    })
    results = fi.search_content(r"import \w+")
    assert len(results) == 2
    assert results[0] == ("foo/bar.py", 1, "import os")
    assert results[1] == ("foo/bar.py", 2, "import sys")

    results2 = fi.search_content(r"console\.log")
    assert len(results2) == 1
    assert results2[0][0] == "baz/index.ts"


def test_paths_sorted():
    fi = FileIndex({"z.py": "", "a.py": "", "m.py": ""})
    assert fi.paths == ["a.py", "m.py", "z.py"]


if __name__ == "__main__":
    test_find_by_ext()
    test_find_by_name()
    test_find_by_pattern()
    test_get_content()
    test_search_content()
    test_paths_sorted()
    print("All FileIndex tests passed.")

"""
Quick smoke test for the repo scanner.
Run from app/api/: python test_scanner.py [optional/path/to/repo]
"""
import json
import sys
from pathlib import Path

from pipeline.scanner import scan_repo

target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent.parent

print(f"Scanning: {target}\n")
result = scan_repo(target)

print(json.dumps(result.model_dump(), indent=2))
print("\n--- Summary ---")
print(f"Services:       {result.services}")
print(f"Languages:      {result.languages}")
print(f"Frameworks:     {result.frameworks}")
print(f"Databases:      {result.databases}")
print(f"External calls: {result.external_calls}")
print(f"API endpoints:  {len(result.apis)}")
print(f"Dep files:      {list(result.dependency_files.keys())}")
print(f"Total files:    {len(result.file_tree)}")

"""Wrapper to run load_test_500 and capture stdout to a file."""
import subprocess
import sys

result = subprocess.run(
    [sys.executable, "manage.py", "load_test_500", "--cleanup"],
    capture_output=True,
    text=True,
    cwd=r"c:\Users\aisya\final-year-dissertation-project\csp-scheduling-system\backend",
)

output = result.stdout + result.stderr

with open(r"c:\Users\aisya\final-year-dissertation-project\csp-scheduling-system\backend\load_test_500_results.txt", "w", encoding="utf-8") as f:
    # Strip ANSI color codes
    import re
    clean = re.sub(r'\x1b\[[0-9;]*m', '', output)
    f.write(clean)

print(f"Written {len(clean)} chars to load_test_500_results.txt")
if result.returncode != 0:
    print(f"Command exited with code {result.returncode}")
    print("STDERR:", result.stderr[:500])

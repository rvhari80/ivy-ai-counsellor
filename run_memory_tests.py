"""Quick test runner for memory tests."""
import subprocess
import sys

if __name__ == "__main__":
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_memory.py", "-v", "--tb=short"],
        cwd="c:/Users/WINDOWS11/ivy-ai-counsellor",
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    print(result.stderr)
    sys.exit(result.returncode)

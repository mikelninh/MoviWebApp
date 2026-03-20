"""
seed_all.py — run all seed scripts in order to fully populate a fresh DB.

Usage:
    python seed_all.py
"""
import subprocess
import sys

scripts = [
    "seed.py",
    "seed_social.py",
    "seed_rich.py",
    "seed_community.py",
    "seed_cinema_content.py",
    "seed_comments.py",
]
for s in scripts:
    print(f"\n{'='*50}\nRunning {s}...\n{'='*50}")
    subprocess.run([sys.executable, s], check=True)
print("\nAll seeds complete.")

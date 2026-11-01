"""
Creates medresolve_stair_bundle.zip for cloud-GPU training: source code + pre-rendered
synthetic SFT JSONL. Never includes the patient database, raw datasets, uploads,
secrets or any MIMIC-derived file.

    python scripts/make_cloud_bundle.py
"""

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INCLUDE_DIRS = ["backend", "scripts", "evaluation"]
INCLUDE_FILES = ["requirements.txt", "data/patient_retrieval/manifest.json"]
SFT_DIR = ROOT / "data" / "patient_retrieval" / "sft"
FORBIDDEN = ("mimic", ".db", ".jwt_secret", "uploads", ".env")


def main():
    out = ROOT / "medresolve_stair_bundle.zip"
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for d in INCLUDE_DIRS:
            for p in (ROOT / d).rglob("*.py"):
                rel = p.relative_to(ROOT).as_posix()
                if "__pycache__" in rel or any(f in rel.lower() for f in FORBIDDEN):
                    continue
                z.write(p, rel); n += 1
        for f in INCLUDE_FILES:
            if (ROOT / f).exists():
                z.write(ROOT / f, f); n += 1
        for p in SFT_DIR.glob("*"):
            z.write(p, p.relative_to(ROOT).as_posix()); n += 1
    print(f"wrote {out} ({n} files, {out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()

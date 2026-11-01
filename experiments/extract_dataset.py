"""
MedResolve — DDXPlus Dataset Extraction & Integrity Verification
Extracts the official DDXPlus ZIP archives into train, validation, and test folders
under data/raw/ddxplus/extracted/ and verifies data integrity.
"""

import os
import sys
import zipfile
import hashlib
from pathlib import Path

DDXPLUS_DIR = Path("data/raw/ddxplus")
EXTRACTED_DIR = DDXPLUS_DIR / "extracted"

SPLIT_MAP = {
    "train": {
        "zip": DDXPLUS_DIR / "release_train_patients.zip",
        "entry": "release_train_patients",
        "target_dir": EXTRACTED_DIR / "train",
        "target_file": EXTRACTED_DIR / "train" / "release_train_patients.csv"
    },
    "validate": {
        "zip": DDXPLUS_DIR / "release_validate_patients.zip",
        "entry": "release_validate_patients",
        "target_dir": EXTRACTED_DIR / "validate",
        "target_file": EXTRACTED_DIR / "validate" / "release_validate_patients.csv"
    },
    "test": {
        "zip": DDXPLUS_DIR / "release_test_patients.zip",
        "entry": "release_test_patients",
        "target_dir": EXTRACTED_DIR / "test",
        "target_file": EXTRACTED_DIR / "test" / "release_test_patients.csv"
    }
}

def extract_and_verify_split(split_name: str, force: bool = False):
    config = SPLIT_MAP[split_name]
    zip_path = config["zip"]
    target_dir = config["target_dir"]
    target_file = config["target_file"]

    if not zip_path.exists():
        print(f"[-] ZIP archive not found: {zip_path}")
        return False

    target_dir.mkdir(parents=True, exist_ok=True)

    if target_file.exists() and not force:
        size = target_file.stat().st_size
        print(f"[+] {split_name} already extracted: {target_file} ({size:,} bytes)")
        return True

    print(f"[*] Extracting {zip_path.name} -> {target_file} ...")
    with zipfile.ZipFile(zip_path, 'r') as zf:
        infolist = zf.infolist()
        entry_name = config["entry"]
        matching = [info for info in infolist if info.filename == entry_name]
        if not matching:
            raise FileNotFoundError(f"Entry {entry_name} not found in {zip_path.name}")
        
        expected_size = matching[0].file_size
        with zf.open(entry_name) as src, open(target_file, "wb") as dst:
            chunk_size = 1024 * 1024 * 8  # 8MB chunks
            copied = 0
            while True:
                chunk = src.read(chunk_size)
                if not chunk:
                    break
                dst.write(chunk)
                copied += len(chunk)
                progress = (copied / expected_size) * 100
                sys.stdout.write(f"\r    Extracting: {copied:,} / {expected_size:,} bytes ({progress:.1f}%)")
                sys.stdout.flush()
        print()

    extracted_size = target_file.stat().st_size
    assert extracted_size == expected_size, (
        f"Extraction size mismatch: expected {expected_size}, got {extracted_size}"
    )

    # Count rows
    with open(target_file, "r", encoding="utf-8", errors="ignore") as f:
        header = f.readline().strip()
        num_rows = sum(1 for _ in f)

    print(f"[+] Verified {split_name}: {num_rows:,} records, {extracted_size:,} bytes")
    print(f"    Header: {header}")
    return True

def run_extraction(force: bool = False):
    print("=" * 60)
    print("DDXPlus Dataset Extraction & Verification")
    print("=" * 60)
    
    results = {}
    for split in ["validate", "test", "train"]:
        results[split] = extract_and_verify_split(split, force=force)
    
    all_ok = all(results.values())
    print("=" * 60)
    if all_ok:
        print("[+] All splits extracted and verified successfully!")
    else:
        print("[-] Some splits failed to extract or verify.")
    return all_ok

if __name__ == "__main__":
    run_extraction()

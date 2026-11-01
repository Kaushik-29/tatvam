"""
MedResolve — reproducible dataset / tool acquisition.

Downloads every publicly accessible artifact used by the STAIR-Clinical
extension and writes a provenance manifest (URL, access date, size,
SHA-256, licence) next to each download. Restricted datasets (MIMIC-IV)
are never downloaded here — see backend/fhir_ingestion/mimic_pipeline.py.

Usage:
    python scripts/download_datasets.py [--only synthea_sample synthea_jar jdk searchtome medlineplus]
"""

import argparse
import datetime as dt
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SEARCHTOME_FILES = ["LICENSE", "README.md", "stats.json"] + [
    f"{dom}/{split}.jsonl"
    for dom in ["education", "finance", "law", "medicine", "natural_sciences", "social_sciences"]
    for split in ["corpus", "train", "dev", "test"]
]

ARTIFACTS = {
    "synthea_sample": {
        "dest": "data/datasets/synthea/raw/official_sample",
        "files": {
            "synthea_sample_data_fhir_latest.zip":
                "https://raw.githubusercontent.com/synthetichealth/synthea-sample-data/main/downloads/latest/synthea_sample_data_fhir_latest.zip",
        },
        "license": "Apache-2.0 (Synthea); synthetic data, no real patients",
        "citation": "Walonoski J. et al. Synthea: An approach, method, and software mechanism for generating synthetic patients and the synthetic electronic health care record. JAMIA 2018;25(3):230-238.",
    },
    "synthea_jar": {
        "dest": "tools/synthea",
        "files": {
            "synthea-with-dependencies.jar":
                "https://github.com/synthetichealth/synthea/releases/download/master-branch-latest/synthea-with-dependencies.jar",
        },
        "license": "Apache-2.0",
        "citation": "https://github.com/synthetichealth/synthea (release tag master-branch-latest)",
    },
    "jdk": {
        "dest": "tools/jdk",
        "files": {
            "OpenJDK21U-jdk_x64_windows_hotspot_21.0.13_9.zip":
                "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.13%2B9/OpenJDK21U-jdk_x64_windows_hotspot_21.0.13_9.zip",
        },
        "expected_sha256": {
            "OpenJDK21U-jdk_x64_windows_hotspot_21.0.13_9.zip":
                "a4dbaa05fca4bd89d84584e58c459bd732efebb1722af80ab13c6516832004f9",
        },
        "license": "GPLv2 with Classpath Exception (Eclipse Temurin)",
        "citation": "https://adoptium.net",
    },
    "searchtome": {
        "dest": "data/datasets/searchtome/raw/official_hf_meghanadh",
        "files": {f: f"https://huggingface.co/datasets/meghanadh/SearchTome/resolve/main/{f}" for f in SEARCHTOME_FILES},
        "license": "CC-BY-SA-4.0",
        "citation": "STAIR (STructure Aware Information Retriever): A novel dataset and LLM based retriever for document structure augmentation. arXiv:2609.03874v2 (2026). Dataset link taken from the paper PDF: https://huggingface.co/datasets/meghanadh/SearchTome",
    },
    "medlineplus": {
        "dest": "data/datasets/medical_knowledge/raw/medlineplus",
        "files": {
            "mplus_topics_compressed_2026-10-31.zip":
                "https://medlineplus.gov/xml/mplus_topics_compressed_2026-10-31.zip",
        },
        "license": "Health-topic summaries are U.S. federal government works in the public domain "
                   "(https://medlineplus.gov/about/using/usingcontent/). Attribution to MedlinePlus retained.",
        "citation": "MedlinePlus [Internet]. Bethesda (MD): National Library of Medicine (US). Health Topics XML, 2026-10-31.",
    },
}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "MedResolve-research/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    tmp.replace(out)


def acquire(name: str, spec: dict) -> dict:
    dest = ROOT / spec["dest"]
    records = []
    for rel, url in spec["files"].items():
        out = dest / rel
        status = "cached"
        if not out.exists():
            try:
                fetch(url, out)
                status = "downloaded"
            except Exception as e:  # record the access problem, never fabricate
                records.append({"file": rel, "url": url, "status": "FAILED", "error": repr(e)})
                print(f"[{name}] FAILED {rel}: {e}", file=sys.stderr)
                continue
        digest = sha256_of(out)
        expected = spec.get("expected_sha256", {}).get(rel)
        if expected and expected != digest:
            raise RuntimeError(f"Checksum mismatch for {rel}: {digest} != {expected}")
        records.append({"file": rel, "url": url, "status": status, "bytes": out.stat().st_size,
                        "sha256": digest, "checksum_verified_against_publisher": bool(expected)})
        print(f"[{name}] {status} {rel} ({out.stat().st_size} B)")
    manifest = {
        "artifact": name,
        "access_date": dt.date.today().isoformat(),
        "license": spec["license"],
        "citation": spec["citation"],
        "files": records,
    }
    (dest / "download_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=list(ARTIFACTS))
    args = ap.parse_args()
    for name in args.only:
        acquire(name, ARTIFACTS[name])


if __name__ == "__main__":
    main()

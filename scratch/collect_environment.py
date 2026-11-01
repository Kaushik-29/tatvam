import os
import sys
import json
import platform
import urllib.request

def collect_manifest():
    manifest = {
        "timestamp": "2026-10-30T09:05:00Z",
        "phase": "5.2",
        "objective": "Evaluation Integrity and Reproducibility Audit",
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "python_version": sys.version,
            "python_executable": sys.executable,
        },
        "random_seeds": {
            "numpy_seed": 42,
            "python_random_seed": 42,
            "torch_seed": 42
        },
        "git": {
            "branch": "master",
            "commit_status": "initial_uncommitted_working_tree"
        },
        "packages": {},
        "ollama": {},
        "knowledge_corpus_v2": {}
    }

    packages_to_check = [
        "numpy", "pandas", "scipy", "sklearn", "pydantic",
        "sentence_transformers", "faiss", "rank_bm25", "torch", "pytest"
    ]
    for pkg in packages_to_check:
        try:
            mod = __import__(pkg)
            manifest["packages"][pkg] = getattr(mod, "__version__", "installed")
        except ImportError:
            manifest["packages"][pkg] = "not_installed"

    # Ollama details
    try:
        with urllib.request.urlopen("http://localhost:11434/api/version", timeout=3) as resp:
            v_data = json.loads(resp.read().decode())
            manifest["ollama"]["version"] = v_data.get("version")
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as resp:
            t_data = json.loads(resp.read().decode())
            for m in t_data.get("models", []):
                if "llama3.2:3b" in m.get("name", ""):
                    manifest["ollama"]["target_model"] = m
    except Exception as e:
        manifest["ollama"]["error"] = str(e)

    # Knowledge corpus v2 manifest summary
    kb_manifest_path = os.path.join("data", "knowledge_base_v2", "knowledge_manifest.json")
    if os.path.exists(kb_manifest_path):
        with open(kb_manifest_path, "r", encoding="utf-8") as f:
            kb_data = json.load(f)
            manifest["knowledge_corpus_v2"]["version"] = kb_data.get("version")
            manifest["knowledge_corpus_v2"]["total_documents"] = kb_data.get("total_documents")
            manifest["knowledge_corpus_v2"]["total_passages"] = kb_data.get("total_passages")
            manifest["knowledge_corpus_v2"]["documents"] = [
                {
                    "document_id": d.get("document_id"),
                    "title": d.get("title"),
                    "publisher": d.get("publisher"),
                    "publication_year": d.get("publication_year"),
                    "license": d.get("license"),
                    "passage_count": len(d.get("passages", []))
                }
                for d in kb_data.get("documents", [])
            ]

    out_path = os.path.join("results", "rag", "phase5_2", "environment_manifest.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Environment manifest successfully saved to {out_path}")

if __name__ == "__main__":
    collect_manifest()

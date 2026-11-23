# Kaggle notebook: STAIR-Clinical router, SECOND TRAINING SEED (seed 29), plus scoring.
# Same settings as the first run (seed 13): Mistral-7B-Instruct-v0.2, 4-bit QLoRA, r=16, alpha=32, lr 2e-4,
# grad-accum 8, 100 steps, max-len 1536.
#
# Settings: Accelerator = GPU T4 x1, Internet = On, Secret HF_TOKEN attached.
# Inputs  : (1) a new dataset with the 6 files in D:\MedResolve\Kaggle_Seed2_Upload
#           (2) the dataset with the FIRST adapter (mistral7b_clinical_stage1/adapter), as before
# Run it with "Save Version -> Save & Run All (Commit)" so it keeps running when the browser is closed.
# Total time: about 6-7 hours (training ~4.5 h, scoring ~2 h). Kaggle's limit is 12 h.
# Output  : /kaggle/working/seed29_results.zip  -> download it from the version's Output tab.

# ================= CELL 1: install (same versions as the first training run) =================
# !pip -q install "transformers==4.57.6" "peft==0.17.1" "bitsandbytes>=0.45" "accelerate>=1.0" rank-bm25 sqlalchemy python-jose passlib fastapi

# ================= CELL 2: login, find the files, copy the code =================
import glob, json, math, os, shutil, subprocess, sys, time, copy, zipfile

from kaggle_secrets import UserSecretsClient
from huggingface_hub import login
login(UserSecretsClient().get_secret("HF_TOKEN"))

WORK = "/kaggle/working"
CODE = f"{WORK}/MedResolve"
zips = glob.glob("/kaggle/input/**/medresolve_stair_bundle.zip", recursive=True)
if zips:                                        # dataset kept the zip
    zipfile.ZipFile(zips[0]).extractall(CODE)
else:                                           # Kaggle unzipped it on upload
    tl = glob.glob("/kaggle/input/**/backend/stair_retriever/train_lora.py", recursive=True)[0]
    root = tl[: tl.index("/backend/")]
    shutil.copytree(root, CODE, dirs_exist_ok=True)
print("code:", CODE, os.path.exists(f"{CODE}/backend/stair_retriever/train_lora.py"))

def find(name):
    hits = glob.glob(f"/kaggle/input/**/{name}", recursive=True)
    assert hits, f"missing input file: {name}"
    return hits[0]

_a13 = glob.glob("/kaggle/input/**/mistral7b_clinical_stage1/**/adapter/adapter_config.json", recursive=True)
ADAPTER_SEED13 = os.path.dirname(_a13[0]) if _a13 else None
print("first adapter (seed 13):", ADAPTER_SEED13 or "NOT ATTACHED - the held-out part (4b) will be skipped")

# ================= CELL 3: train with seed 29 (about 4.5 h) =================
OUT = f"{WORK}/mistral7b_clinical_stage1_seed29"
cmd = [sys.executable, "-u", "-m", "backend.stair_retriever.train_lora", "--task", "clinical", "--stage", "1",
       "--sft-train-jsonl", "data/patient_retrieval/sft/stair_clinical_stage1_train.jsonl",
       "--sft-val-jsonl", "data/patient_retrieval/sft/stair_clinical_stage1_validation.jsonl",
       "--base-model", "mistralai/Mistral-7B-Instruct-v0.2", "--load-in-4bit",
       "--max-train-queries", "4000", "--max-steps", "100", "--epochs", "1", "--grad-accum", "8", "--lr", "2e-4",
       "--lora-r", "16", "--lora-alpha", "32", "--max-len", "1536",
       "--eval-queries", "300", "--eval-every", "100", "--free-gen-eval", "100",
       "--save-every", "25", "--resume", "--seed", "29", "--output-dir", OUT]
p = subprocess.Popen(cmd, cwd=CODE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
for line in p.stdout:                     # show the training log live in the notebook
    print(line, end="", flush=True)
assert p.wait() == 0, "training failed - see the log above"
m = json.load(open(f"{OUT}/train_metrics.json"))
print(m["training_status"], m["steps"], "steps,", m["train_time_s"], "s")
print("validation before:", m["validation_before_training"])
print("validation after :", m["validation_final"])

# ================= CELL 4: scoring (same constrained scoring as before) =================
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

BASE = "mistralai/Mistral-7B-Instruct-v0.2"
tok = AutoTokenizer.from_pretrained(BASE)
if tok.pad_token_id is None:
    tok.pad_token = tok.eos_token
base = AutoModelForCausalLM.from_pretrained(
    BASE, device_map="auto",
    quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16, bnb_4bit_quant_type="nf4"))
DEV = "cuda"


def prompt_ids(p):
    ids = tok(p, add_special_tokens=False, return_tensors="pt").input_ids
    if tok.bos_token_id is not None and getattr(tok, "add_bos_token", False):
        ids = torch.cat([torch.tensor([[tok.bos_token_id]]), ids], dim=1)
    return ids[:, -4096:]


def cand_ids(c):
    return tok(" " + c, add_special_tokens=False).input_ids + [tok.eos_token_id]


def repeat_cache(past, n):
    if hasattr(past, "batch_repeat_interleave"):
        c = copy.deepcopy(past); c.batch_repeat_interleave(n); return c
    return tuple(tuple(t.repeat_interleave(n, dim=0) for t in layer) for layer in past)


@torch.no_grad()
def score(model, prompt, cands, bs=16):
    p = prompt_ids(prompt).to(DEV)
    out = model(p, use_cache=True)
    first = torch.log_softmax(out.logits[0, -1].float(), -1)
    scores, ids = [], [cand_ids(c) for c in cands]
    for b in range(0, len(ids), bs):
        ch = ids[b:b + bs]; L = max(map(len, ch))
        inp = torch.full((len(ch), L), tok.pad_token_id, dtype=torch.long, device=DEV)
        mask = torch.zeros((len(ch), L), dtype=torch.long, device=DEV)
        for i, c in enumerate(ch):
            inp[i, :len(c)] = torch.tensor(c, device=DEV); mask[i, :len(c)] = 1
        attn = torch.cat([torch.ones((len(ch), p.shape[1]), dtype=torch.long, device=DEV), mask], 1)
        logits = model(inp, past_key_values=repeat_cache(out.past_key_values, len(ch)),
                       attention_mask=attn, use_cache=False).logits
        for i, c in enumerate(ch):
            lp = float(first[c[0]])
            if len(c) > 1:
                st = torch.log_softmax(logits[i, :len(c) - 1].float(), -1)
                lp += float(st.gather(1, torch.tensor(c[1:], device=st.device).unsqueeze(1)).sum())
            scores.append(lp)
    return scores


norm = lambda p: p.replace("encounter_dates", "consultations")


def score_file(model, inp, out, label):
    rows = [json.loads(l) for l in open(inp, encoding="utf-8")]
    done = {json.loads(l)["example_id"] for l in open(out)} if os.path.exists(out) else set()
    todo = [r for r in rows if r["example_id"] not in done]
    print(f"\n== {os.path.basename(out)}: {len(rows)} questions, {len(todo)} to go", flush=True)
    t0 = time.time()
    with open(out, "a", encoding="utf-8") as f:
        for i, r in enumerate(todo, 1):
            lps = score(model, r["prompt"], r["candidates"])
            mx = max(lps); z = sum(math.exp(x - mx) for x in lps)
            ranked = sorted(zip(r["candidate_paths"], r["candidates"], lps), key=lambda x: -x[2])
            f.write(json.dumps({"example_id": r["example_id"], "patient_id": r["patient_id"], "query": r["query"],
                                "category": r["category"], "gold_paths": r["gold_paths"],
                                "ranked": [{"path": p, "target": t, "logprob": lp, "prob": math.exp(lp - mx) / z}
                                           for p, t, lp in ranked],
                                "base_model": BASE, "adapter": label}) + "\n")
            f.flush()
            if i % 100 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} ({(time.time() - t0) / i:.1f}s per question)", flush=True)
    res = [json.loads(l) for l in open(out)]
    h1 = sum(norm(r["ranked"][0]["path"]) in {norm(g) for g in r["gold_paths"]} for r in res)
    print(f"{os.path.basename(out)}: {len(res)} questions, section_hit@1 = {h1 / len(res):.3f}", flush=True)


# 4a. NEW adapter (seed 29) on the three original test sets
model = PeftModel.from_pretrained(base, f"{OUT}/adapter").eval()
for name, ds in [("stair_clinical_stage1_test_eval.jsonl", "synthea"), ("stage1_mimic_eval.jsonl", "mimic"),
                 ("stage1_eicu_eval.jsonl", "eicu")]:
    inp = f"{CODE}/data/patient_retrieval/sft/{name}" if ds == "synthea" else find(name)
    score_file(model, inp, f"{WORK}/mistral_seed29_{ds}_predictions.jsonl", "mistral7b_clinical_stage1_seed29/adapter (step 100)")

# 4b. FIRST adapter (seed 13) on the held-out paraphrases (finishes the held-out test for R10/R11)
if ADAPTER_SEED13:
    base = model.unload()
    model = PeftModel.from_pretrained(base, ADAPTER_SEED13).eval()
    for ds in ["synthea", "mimic", "eicu"]:
        score_file(model, find(f"stage1_{ds}_heldout_para_eval.jsonl"),
                   f"{WORK}/mistral_{ds}_heldout_para_predictions.jsonl", "mistral7b_clinical_stage1/adapter (step 100)")

# ================= CELL 5: pack everything into one file to download =================
res_zip = f"{WORK}/seed29_results.zip"
with zipfile.ZipFile(res_zip, "w", zipfile.ZIP_DEFLATED) as z:
    for f in glob.glob(f"{WORK}/mistral_*_predictions.jsonl"):
        z.write(f, os.path.basename(f))
    for root, _, files in os.walk(OUT):
        for f in files:
            if "checkpoint" in root:            # resume checkpoints are not needed
                continue
            full = os.path.join(root, f)
            z.write(full, os.path.join("mistral7b_clinical_stage1_seed29", os.path.relpath(full, OUT)))
print("DONE ->", res_zip, f"({os.path.getsize(res_zip) / 1e6:.0f} MB). Download it from the Output tab.")

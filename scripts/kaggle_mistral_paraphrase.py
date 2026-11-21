# Kaggle notebook: STAIR-Clinical Mistral-7B router on the PARAPHRASED test questions (paraphrase robustness test).
# Same constrained scoring as scripts/kaggle_mistral_mimic.py / backend/stair_retriever/predict_stage1.py.
# Settings: Accelerator = GPU T4, Internet = On, HF_TOKEN secret added.
# Attach: the dataset with mistral7b_clinical_stage1/adapter/...  and a dataset with the three files
#   stage1_synthea_para_eval.jsonl, stage1_mimic_para_eval.jsonl, stage1_eicu_para_eval.jsonl
# Output: /kaggle/working/mistral_{synthea,mimic,eicu}_para_predictions.jsonl
# Safe to re-run: finished questions are skipped.

# ---------------- CELL 1 ----------------
# !pip install -q -U transformers peft accelerate bitsandbytes

# ---------------- CELL 2 ----------------
import glob, json, math, os, time, copy
import torch

try:
    from kaggle_secrets import UserSecretsClient
    from huggingface_hub import login
    login(UserSecretsClient().get_secret("HF_TOKEN"))
except Exception as e:
    print("HF login skipped:", e)

BASE = "mistralai/Mistral-7B-Instruct-v0.2"
ADAPTER = os.path.dirname(glob.glob("/kaggle/input/**/adapter/adapter_config.json", recursive=True)[0])
INPUTS = sorted(glob.glob("/kaggle/input/**/stage1_*_para_eval.jsonl", recursive=True))
print("adapter:", ADAPTER)
print("inputs:", *INPUTS, sep="\n  ")
assert len(INPUTS) == 3, "expected 3 stage1_*_para_eval.jsonl files"
print(open(os.path.join(ADAPTER, "stair_clinical_meta.json")).read())   # should say "steps": 100

# ---------------- CELL 3 ----------------
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

tok = AutoTokenizer.from_pretrained(BASE)
if tok.pad_token_id is None:
    tok.pad_token = tok.eos_token
model = AutoModelForCausalLM.from_pretrained(
    BASE, device_map="auto",
    quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16,
                                           bnb_4bit_quant_type="nf4"))
model = PeftModel.from_pretrained(model, ADAPTER).eval()
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
def score(prompt, cands, bs=16):
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

# ---------------- CELL 4: run all three files ----------------
norm = lambda p: p.replace("encounter_dates", "consultations")

for INP in INPUTS:
    ds = os.path.basename(INP).split("_")[1]            # synthea / mimic / eicu
    OUT = f"/kaggle/working/mistral_{ds}_para_predictions.jsonl"
    rows = [json.loads(l) for l in open(INP, encoding="utf-8")]
    done = {json.loads(l)["example_id"] for l in open(OUT)} if os.path.exists(OUT) else set()
    todo = [r for r in rows if r["example_id"] not in done]
    print(f"\n== {ds}: {len(rows)} questions, {len(done)} done, {len(todo)} to go", flush=True)
    t0 = time.time()
    with open(OUT, "a", encoding="utf-8") as f:
        for i, r in enumerate(todo, 1):
            lps = score(r["prompt"], r["candidates"])
            m = max(lps); z = sum(math.exp(x - m) for x in lps)
            ranked = sorted(zip(r["candidate_paths"], r["candidates"], lps), key=lambda x: -x[2])
            f.write(json.dumps({"example_id": r["example_id"], "patient_id": r["patient_id"], "query": r["query"],
                                "category": r["category"], "gold_paths": r["gold_paths"],
                                "ranked": [{"path": p, "target": t, "logprob": lp, "prob": math.exp(lp - m) / z}
                                           for p, t, lp in ranked],
                                "base_model": BASE, "adapter": "mistral7b_clinical_stage1/adapter (step 100)"}) + "\n")
            f.flush()
            if i % 50 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)}  ({(time.time() - t0) / i:.1f}s per question)", flush=True)
    res = [json.loads(l) for l in open(OUT)]
    h1 = sum(norm(r["ranked"][0]["path"]) in {norm(g) for g in r["gold_paths"]} for r in res)
    print(f"{ds}: {len(res)} questions, section_hit@1 = {h1 / len(res):.3f}")

# Then: right panel -> Output -> download the three mistral_*_para_predictions.jsonl files

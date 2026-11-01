"""
LoRA supervised fine-tuning for STAIR (SearchTome) and STAIR-Clinical.

Reference configuration (paper): Mistral-7B-Instruct-v0.2, LoRA r=16, alpha=32,
early stopping on dev Recall@1. On a CPU-only machine use a small base model
(e.g. Qwen/Qwen2.5-0.5B-Instruct) — the resulting adapter is a reduced-scale run,
NOT the reference configuration, and is labelled as such in its metadata.

Examples
  # CPU smoke test (a few steps; proves the pipeline end-to-end)
  python -m backend.stair_retriever.train_lora --task clinical --stage 1 \
      --base-model Qwen/Qwen2.5-0.5B-Instruct --max-steps 5 --output-dir models/stair_clinical/checkpoints/smoke
  # GPU (Colab/Kaggle), reference configuration
  python -m backend.stair_retriever.train_lora --task searchtome --domain medicine \
      --base-model mistralai/Mistral-7B-Instruct-v0.2 --load-in-4bit --epochs 20 --output-dir ...
"""

import argparse
import hashlib
import json
import math
import os
import platform
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, List

import torch

from backend.stair_retriever.constrained import CausalLMScorer


def hardware_info() -> Dict[str, Any]:
    info = {"platform": platform.platform(), "python": platform.python_version(), "torch": torch.__version__,
            "cpu_count": os.cpu_count(), "cuda": torch.cuda.is_available()}
    if torch.cuda.is_available():
        info["gpu"] = torch.cuda.get_device_name(0)
        info["gpu_mem_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1)
    try:
        import psutil
        info["ram_gb"] = round(psutil.virtual_memory().total / 1e9, 1)
    except Exception:
        pass
    return info


def sha256_dir(d: Path) -> Dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.glob("*")) if p.is_file()}


def tokenize_example(tok, ex: Dict[str, Any], max_len: int):
    p = tok(ex["prompt"], add_special_tokens=False).input_ids
    t = tok(" " + ex["target"], add_special_tokens=False).input_ids + [tok.eos_token_id]
    if len(p) + len(t) > max_len:
        return None
    return {"input_ids": p + t, "labels": [-100] * len(p) + t}


@torch.no_grad()
def evaluate(scorer: CausalLMScorer, examples: List[Dict[str, Any]], k_values=(1, 3, 5),
             free_gen_n: int = 0) -> Dict[str, Any]:
    """Constrained top-k over valid targets (Recall@k against ALL gold targets of the query) +
    optional free-generation hallucination (invalid path) rate on the first `free_gen_n` examples."""
    seen, hits, rr, n = set(), {k: 0 for k in k_values}, 0.0, 0
    for ex in examples:
        key = (ex["prompt"])
        if key in seen:
            continue
        seen.add(key)
        scores = scorer.score_candidates(ex["prompt"], ex["candidates"])
        ranked = [c for _, c in sorted(zip(scores, ex["candidates"]), key=lambda x: -x[0])]
        gold = set(ex["gold_targets"])
        n += 1
        for k in k_values:
            hits[k] += int(bool(gold & set(ranked[:k])))
        first = next((i for i, c in enumerate(ranked) if c in gold), None)
        rr += 1.0 / (first + 1) if first is not None else 0.0
    res = {"n_queries": n, **{f"recall@{k}": hits[k] / n if n else 0.0 for k in k_values},
           **{f"hits@{k}": hits[k] for k in k_values}, "mrr": rr / n if n else 0.0,
           "exact_path_match@1": hits[1] / n if n else 0.0}
    if free_gen_n:
        invalid = exact = 0
        sub = examples[:free_gen_n]
        for ex in sub:
            out = scorer.generate_free(ex["prompt"], max_new_tokens=40).split("\n")[0].strip()
            out = out[5:] if out.startswith("leaf ") else out
            # ToC display metadata copied from the prompt ("(12 records, 2016 to 2024)") is not part of the title
            out = re.sub(r"\s*\(\d+ records?[^)]*\)\s*$", "", out).strip()
            if out not in set(ex["candidates"]):
                invalid += 1
            if out in set(ex["gold_targets"]):
                exact += 1
        res.update({"free_generation_n": len(sub), "free_generation_invalid_path_rate": invalid / len(sub),
                    "free_generation_exact_match": exact / len(sub)})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=["clinical", "searchtome"], required=True)
    ap.add_argument("--stage", type=int, default=1)
    ap.add_argument("--domain", default="medicine")
    ap.add_argument("--base-model", default="Qwen/Qwen2.5-0.5B-Instruct")
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--max-steps", type=int, default=0)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--lora-alpha", type=int, default=32)
    ap.add_argument("--lora-dropout", type=float, default=0.05)
    ap.add_argument("--max-len", type=int, default=2048)
    ap.add_argument("--max-train-queries", type=int, default=0)
    ap.add_argument("--eval-queries", type=int, default=200)
    ap.add_argument("--eval-every", type=int, default=0)
    ap.add_argument("--free-gen-eval", type=int, default=30)
    ap.add_argument("--patience", type=int, default=0, help="early stopping on validation Recall@1 (evals)")
    ap.add_argument("--sft-train-jsonl", default=None, help="pre-rendered SFT examples (see sft.export_jsonl)")
    ap.add_argument("--sft-val-jsonl", default=None)
    ap.add_argument("--save-every", type=int, default=5, help="checkpoint every N optimizer steps (0 = off)")
    ap.add_argument("--resume", action="store_true", help="resume from <output-dir>/checkpoint if present")
    ap.add_argument("--load-in-4bit", action="store_true")
    ap.add_argument("--threads", type=int, default=0)
    ap.add_argument("--seed", type=int, default=13)
    a = ap.parse_args()

    random.seed(a.seed); torch.manual_seed(a.seed)
    if a.threads:
        torch.set_num_threads(a.threads)
    out = Path(a.output_dir); out.mkdir(parents=True, exist_ok=True)
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import LoraConfig, get_peft_model

    from backend.stair_retriever import sft
    t_data = time.time()
    if a.sft_train_jsonl:                     # cloud path: pre-rendered prompts, no database needed
        train = sft.load_jsonl(Path(a.sft_train_jsonl), a.max_train_queries or None, a.seed)
        val = sft.load_jsonl(Path(a.sft_val_jsonl), a.eval_queries or None, a.seed + 1)
    elif a.task == "clinical":
        train = sft.clinical_examples("train", a.stage, a.max_train_queries or None, a.seed)
        val = sft.clinical_examples("validation", a.stage, a.eval_queries, a.seed + 1, expand_multi_gold=False)
    else:
        train = sft.searchtome_examples(a.domain, "train", a.max_train_queries or None, a.seed)
        val = sft.searchtome_examples(a.domain, "validation", a.eval_queries, a.seed + 1)
    print(f"data: {len(train)} train examples, {len(val)} validation queries ({time.time() - t_data:.0f}s)")

    tok = AutoTokenizer.from_pretrained(a.base_model)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    load_kw = {}
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # T4 / V100 have no native bfloat16: use float16 there
    half = torch.bfloat16 if device == "cuda" and torch.cuda.is_bf16_supported() else torch.float16
    if a.load_in_4bit:
        from transformers import BitsAndBytesConfig
        load_kw["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=half,
                                                            bnb_4bit_quant_type="nf4")
        load_kw["device_map"] = "auto"
    else:
        load_kw["dtype"] = half if device == "cuda" else torch.float32
    model = AutoModelForCausalLM.from_pretrained(a.base_model, **load_kw)
    if a.load_in_4bit:
        from peft import prepare_model_for_kbit_training
        model = prepare_model_for_kbit_training(model)
    elif device == "cuda":
        model.to(device)
    lcfg = LoraConfig(r=a.lora_r, lora_alpha=a.lora_alpha, lora_dropout=a.lora_dropout, bias="none",
                      task_type="CAUSAL_LM", target_modules=["q_proj", "k_proj", "v_proj", "o_proj"])
    model = get_peft_model(model, lcfg)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"trainable params {trainable} / {total}")

    tok_train = [t for t in (tokenize_example(tok, ex, a.max_len) for ex in train) if t]
    skipped = len(train) - len(tok_train)
    steps_per_epoch = math.ceil(len(tok_train) / a.grad_accum)
    total_steps = a.max_steps or max(1, int(steps_per_epoch * a.epochs))
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr, weight_decay=0.0)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, (s + 1) / max(1, int(0.03 * total_steps))) * max(0.0, 1 - s / total_steps))

    scorer = CausalLMScorer(model, tok, device=device)
    history, best, bad = [], -1.0, 0
    base_eval = None
    ckpt = out / "checkpoint"
    step, micro, prior_time, resumed_from = 0, 0, 0.0, None
    if a.resume and (ckpt / "trainer_state.json").exists():
        from peft import set_peft_model_state_dict
        from safetensors.torch import load_file
        set_peft_model_state_dict(model, load_file(str(ckpt / "adapter_model.safetensors")))
        opt.load_state_dict(torch.load(ckpt / "optimizer.pt"))
        sched.load_state_dict(torch.load(ckpt / "scheduler.pt"))
        st = json.loads((ckpt / "trainer_state.json").read_text(encoding="utf-8"))
        step, micro, history, base_eval, prior_time = st["step"], st["micro"], st["history"], st["base_eval"], st["train_time_s"]
        random.setstate(tuple(st["py_random_state"][:1]) + (tuple(st["py_random_state"][1]),) + tuple(st["py_random_state"][2:]))
        resumed_from = step
        print(f"resumed from step {step}")
    elif a.eval_queries:
        model.eval()
        base_eval = evaluate(scorer, val, free_gen_n=0)
        print("step 0 (untrained adapter == base model) validation:", base_eval, flush=True)

    def save_checkpoint():
        ckpt.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(ckpt)
        torch.save(opt.state_dict(), ckpt / "optimizer.pt")
        torch.save(sched.state_dict(), ckpt / "scheduler.pt")
        (ckpt / "trainer_state.json").write_text(json.dumps({
            "step": step, "micro": micro, "history": history, "base_eval": base_eval,
            "train_time_s": prior_time + time.time() - t0, "py_random_state": epoch_rng_state}), encoding="utf-8")

    t0 = time.time()
    order = list(range(len(tok_train)))
    model.train()
    running = 0.0
    nonfinite = 0
    while step < total_steps:
        epoch_rng_state = [random.getstate()[0], list(random.getstate()[1]), random.getstate()[2]]
        random.shuffle(order)
        skip = micro % len(order) if resumed_from is not None else 0   # resume mid-epoch at the same data position
        resumed_from = None
        for pos, idx in enumerate(order):
            if pos < skip:
                continue
            ex = tok_train[idx]
            ids = torch.tensor([ex["input_ids"]], device=device)
            labels = torch.tensor([ex["labels"]], device=device)
            loss = model(input_ids=ids, labels=labels).loss / a.grad_accum
            if not torch.isfinite(loss):
                nonfinite += 1
                print(f"warning: non-finite loss skipped (total {nonfinite})", flush=True)
                continue
            loss.backward()
            running += float(loss.detach())
            micro += 1
            if micro % a.grad_accum == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step(); sched.step(); opt.zero_grad()
                step += 1
                rec = {"step": step, "loss": running, "lr": sched.get_last_lr()[0], "elapsed_s": round(time.time() - t0, 1)}
                running = 0.0
                if a.eval_every and step % a.eval_every == 0 and a.eval_queries:
                    model.eval()
                    ev = evaluate(scorer, val)
                    model.train()
                    rec["validation"] = ev
                    if ev["recall@1"] > best:
                        best, bad = ev["recall@1"], 0
                        model.save_pretrained(out / "best")
                    else:
                        bad += 1
                history.append(rec)
                print(json.dumps(rec), flush=True)
                if a.save_every and step % a.save_every == 0:
                    save_checkpoint()
                if step >= total_steps or (a.patience and bad >= a.patience):
                    break
        if a.patience and bad >= a.patience:
            print("early stopping")
            break
    train_time = prior_time + time.time() - t0
    model.eval()
    final_eval = evaluate(scorer, val, free_gen_n=a.free_gen_eval) if a.eval_queries else None
    print("final validation:", final_eval)
    adapter_dir = out / "adapter"
    model.save_pretrained(adapter_dir)
    tok.save_pretrained(adapter_dir)
    reference = "mistralai/Mistral-7B-Instruct-v0.2" in a.base_model
    meta = {
        "task": a.task, "stage": a.stage, "stage2": a.stage == 2, "domain": a.domain if a.task == "searchtome" else None,
        "base_model": a.base_model, "tokenizer": a.base_model, "is_reference_configuration": reference,
        "training_status": ("smoke_test_only" if step < 10 else
                            "completed_reduced_scale" if not reference else "completed"),
        "lora": {"r": a.lora_r, "alpha": a.lora_alpha, "dropout": a.lora_dropout,
                 "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"]},
        "optimizer": {"name": "AdamW", "lr": a.lr, "grad_accum": a.grad_accum, "schedule": "linear warmup 3% + linear decay"},
        "steps": step, "epochs_requested": a.epochs, "max_steps": a.max_steps,
        "train_examples": len(tok_train), "train_examples_skipped_over_max_len": skipped, "max_len": a.max_len,
        "trainable_params": trainable, "total_params": total,
        "train_time_s": round(train_time, 1), "hardware": hardware_info(), "seed": a.seed,
        "validation_before_training": base_eval, "validation_final": final_eval,
        "best_validation_recall@1": best if best >= 0 else None,
        "loss_history": history, "adapter_sha256": sha256_dir(adapter_dir),
    }
    (out / "train_metrics.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (adapter_dir / "stair_clinical_meta.json").write_text(json.dumps({k: meta[k] for k in (
        "task", "stage", "stage2", "base_model", "training_status", "is_reference_configuration", "steps",
        "validation_final")}, indent=2), encoding="utf-8")
    print(f"saved adapter to {adapter_dir} ({meta['training_status']})")


if __name__ == "__main__":
    main()

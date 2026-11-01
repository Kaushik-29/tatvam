"""
Constrained generation for STAIR / STAIR-Clinical with a Hugging Face causal LM.

`score_candidates` computes log P(candidate | prompt) for every VALID ToC target,
reusing the prompt KV cache. Ranking all valid targets by sequence log-probability
is equivalent to constrained decoding restricted to the set of valid leaf strings
(the trie of valid outputs), and yields a natural top-k list. Invalid paths are
impossible by construction.

`generate_free` performs ordinary greedy decoding (no constraint) so that the
invalid-path (hallucination) rate of the unconstrained model can be measured.
"""

from typing import List, Optional, Sequence

import torch


class CausalLMScorer:
    def __init__(self, model, tokenizer, device: str = "cpu", max_prompt_tokens: int = 4096):
        self.model = model.eval()
        self.tok = tokenizer
        self.device = device
        self.max_prompt_tokens = max_prompt_tokens

    def _prompt_ids(self, prompt: str) -> torch.Tensor:
        ids = self.tok(prompt, add_special_tokens=False, return_tensors="pt").input_ids
        if self.tok.bos_token_id is not None and getattr(self.tok, "add_bos_token", False):
            ids = torch.cat([torch.tensor([[self.tok.bos_token_id]]), ids], dim=1)
        return ids[:, -self.max_prompt_tokens:]

    def candidate_ids(self, cand: str) -> List[int]:
        ids = self.tok(" " + cand, add_special_tokens=False).input_ids
        if self.tok.eos_token_id is not None:
            ids = ids + [self.tok.eos_token_id]
        return ids

    @torch.no_grad()
    def score_candidates(self, prompt: str, candidates: Sequence[str], batch_size: int = 16) -> List[float]:
        p_ids = self._prompt_ids(prompt).to(self.device)
        out = self.model(p_ids, use_cache=True)
        past = out.past_key_values
        first_logprobs = torch.log_softmax(out.logits[0, -1].float(), dim=-1)
        scores: List[float] = []
        cand_ids = [self.candidate_ids(c) for c in candidates]
        for b in range(0, len(cand_ids), batch_size):
            chunk = cand_ids[b:b + batch_size]
            L = max(len(c) for c in chunk)
            pad = self.tok.pad_token_id if self.tok.pad_token_id is not None else 0
            inp = torch.full((len(chunk), L), pad, dtype=torch.long)
            mask = torch.zeros((len(chunk), L), dtype=torch.long)
            for i, c in enumerate(chunk):
                inp[i, :len(c)] = torch.tensor(c)
                mask[i, :len(c)] = 1
            # logits[i, j] predicts candidate token j+1 (given prompt + tokens 0..j)
            bpast = _repeat_cache(past, len(chunk))
            attn = torch.cat([torch.ones((len(chunk), p_ids.shape[1]), dtype=torch.long), mask], dim=1)
            logits = self.model(inp, past_key_values=bpast, attention_mask=attn, use_cache=False).logits
            for i, c in enumerate(chunk):
                lp = float(first_logprobs[c[0]])
                if len(c) > 1:
                    step = torch.log_softmax(logits[i, :len(c) - 1].float(), dim=-1)
                    lp += float(step.gather(1, torch.tensor(c[1:]).unsqueeze(1)).sum())
                scores.append(lp)
        return scores

    @torch.no_grad()
    def generate_free(self, prompt: str, max_new_tokens: int = 48) -> str:
        p_ids = self._prompt_ids(prompt).to(self.device)
        out = self.model.generate(p_ids, max_new_tokens=max_new_tokens, do_sample=False,
                                  eos_token_id=self.tok.eos_token_id,
                                  pad_token_id=self.tok.pad_token_id or self.tok.eos_token_id)
        return self.tok.decode(out[0, p_ids.shape[1]:], skip_special_tokens=True).strip()


def _repeat_cache(past, n: int):
    """Expand a batch-1 KV cache to batch n (works for DynamicCache and legacy tuples)."""
    import copy
    if hasattr(past, "batch_repeat_interleave"):
        c = copy.deepcopy(past)
        c.batch_repeat_interleave(n)
        return c
    return tuple(tuple(t.repeat_interleave(n, dim=0) for t in layer) for layer in past)


def load_scorer(base_model: str, adapter_dir: Optional[str] = None, dtype=torch.float32) -> CausalLMScorer:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(base_model)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(base_model, torch_dtype=dtype)
    if adapter_dir:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, adapter_dir)
    return CausalLMScorer(model, tok)

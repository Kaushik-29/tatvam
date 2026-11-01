# MedResolve Phase 6 — Statistical Analysis Plan

**Document Version:** 2.1.0 (Final Dataset Freeze Edition)  
**Status:** Frozen Pre-Evaluation Specification  
**Scope:** Reconciled directional hypothesis, pre-registered one-sided exact McNemar test, secondary ablation family, Holm-Bonferroni correction, and paired contingency formulation for B0–B3 evaluation.  

---

## 1. Study Design & Sampling Unit

* **Study Architecture:** Paired within-scenario comparative trial across four systems (B0, B1, B2, B3) evaluated on identical scenario inputs and fixed reference literature (Option A).
* **Sampling Unit ($N$):** The individual evaluation scenario $s_i$.
* **Prohibition Against Claim-Level Pseudo-Replication:** Multiple claims generated within a single scenario share identical prompt context and patient state. Therefore, **claims within a scenario are never treated as independent samples**. All statistical hypothesis tests are conducted strictly at the **scenario level** ($N = 100$ total, $N_{\text{err}} = 85$ error scenarios).

---

## 2. Hypothesis Hierarchy & Directional Reconciled Specification

To maintain strict statistical control and eliminate post-hoc bias, the study pre-specifies **one single primary confirmatory hypothesis** and a **secondary family of ablation comparisons**.

```
                               Hypothesis Architecture
                                          │
            ┌─────────────────────────────┴─────────────────────────────┐
            ▼                                                           ▼
┌───────────────────────────────────────┐   ┌───────────────────────────────────────┐
│          PRIMARY HYPOTHESIS           │   │      SECONDARY ABLATION FAMILY        │
│          B0 vs. B3 (Overall)          │   │      (Holm-Corrected, 4 Tests)        │
├───────────────────────────────────────┤   ├───────────────────────────────────────┤
│ • Directional: R_prop(B0) > R_prop(B3)│   │ 1. B0 vs. B1 (Provenance Effect)      │
│ • Test: One-Sided Exact McNemar       │   │ 2. B1 vs. B2 (Reconciliation Effect)  │
│ • Alpha = 0.05 (Unadjusted)           │   │ 3. B2 vs. B3 (Action & Gating Effect) │
│ • Primary endpoint of the trial.      │   │ 4. B0 vs. B2 (Baseline vs. Ledger)    │
└───────────────────────────────────────┘   └───────────────────────────────────────┘
```

### 2.1 Reconciled Primary Confirmatory Hypothesis
* **Null Hypothesis ($H_{0, \text{primary}}$):** Full MedResolve (B3) does not reduce the scenario-level incorrect claim propagation rate compared with Direct Baseline (B0) on corrupted error scenarios ($R_{\text{prop, B0}} \le R_{\text{prop, B3}}$).
* **Alternative Hypothesis ($H_{1, \text{primary}}$):** Full MedResolve (B3) strictly reduces the scenario-level incorrect claim propagation rate compared with Direct Baseline (B0) ($R_{\text{prop, B0}} > R_{\text{prop, B3}}$).
* **Significance Threshold:** $\alpha = 0.05$ (one-sided, unadjusted).

### 2.2 Secondary Ablation Comparison Family
Evaluating the architectural step changes:
1. **$H_{1, \text{sec1}}$ (B0 vs. B1):** 5-way unit provenance tagging alone reduces error propagation ($R_{\text{prop, B0}} > R_{\text{prop, B1}}$).
2. **$H_{1, \text{sec2}}$ (B1 vs. B2):** Longitudinal evidence ledger and conflict detection reduce error propagation ($R_{\text{prop, B1}} > R_{\text{prop, B2}}$).
3. **$H_{1, \text{sec3}}$ (B2 vs. B3):** Selective action policy and claim verification reduce error propagation ($R_{\text{prop, B2}} > R_{\text{prop, B3}}$).
4. **$H_{1, \text{sec4}}$ (B0 vs. B2):** Cumulative ledger effect without action gating reduces error propagation ($R_{\text{prop, B0}} > R_{\text{prop, B2}}$).

---

## 3. Contingency Formulation & Pre-Registered One-Sided Exact McNemar Test

For any paired comparison between systems $A$ and $B$ across the $N_{\text{err}} = 85$ corrupted scenarios, the paired binary outcome (Propagated: Yes/No) forms a $2 \times 2$ contingency table:

```
                          System B
                      Propagated       Prevented
                   ┌───────────────┬───────────────┐
      Propagated   │    n_11       │    n_10       │
System A           │ (Both Fail)   │ (A Fails, B   │
                   │               │   Succeeds)   │
                   ├───────────────┼───────────────┤
      Prevented    │    n_01       │    n_00       │
                   │ (A Succeeds,  │ (Both Succeed)│
                   │   B Fails)    │               │
                   └───────────────┴───────────────┘
```

### 3.1 Pre-Registered One-Sided Exact McNemar Test
To align mathematically with the directional hypothesis ($H_1: R_{\text{prop, A}} > R_{\text{prop, B}}$), the test evaluates whether the discordant pairs favor System B ($n_{10} > n_{01}$):
$$p = \sum_{k=0}^{n_{01}} \binom{n_{10} + n_{01}}{k} 0.5^{n_{10} + n_{01}}$$

* **Exactness:** The exact binomial distribution is utilized regardless of sample size, eliminating asymptotic approximation errors.
* **Interpretation:** $p$ represents the exact cumulative probability of observing $n_{01}$ or fewer discordant reversals under the null assumption of equal error probability.

---

## 4. Paired Effect Sizes and Confidence Intervals

### 4.1 Paired Risk Difference ($\Delta R$)
$$\Delta R = R_{\text{prop, A}} - R_{\text{prop, B}} = \frac{n_{10} - n_{01}}{N_{\text{err}}}$$

### 4.2 Newcombe Paired Score Confidence Interval
95% confidence intervals for paired risk difference $\Delta R$ are calculated using the **Newcombe Paired Score Method**, which incorporates the correlation between paired binary proportions based on the Wilson score intervals of individual marginals.

### 4.3 Paired Bootstrap Resampling
For continuous secondary metrics (e.g. claim counts, token lengths, latency):
* **Resampling Unit:** Paired scenario tuples $(s_i^{\text{B0}}, s_i^{\text{B1}}, s_i^{\text{B2}}, s_i^{\text{B3}})$.
* **Iterations:** $B = 10,000$.
* **Confidence Interval:** 95% Percentile / BCa intervals.

---

## 5. Family-Wise Error Rate Control: Holm-Bonferroni

To strictly control the family-wise error rate across the $M = 4$ prespecified secondary ablation hypotheses:
1. Sort raw one-sided $p$-values: $p_{(1)} \le p_{(2)} \le p_{(3)} \le p_{(4)}$.
2. Compare each $p_{(k)}$ against adjusted threshold $\alpha_{(k)} = \frac{0.05}{4 - k + 1}$:
   - Rank 1: $p_{(1)} < \frac{0.05}{4} = 0.0125$
   - Rank 2: $p_{(2)} < \frac{0.05}{3} = 0.0167$
   - Rank 3: $p_{(3)} < \frac{0.05}{2} = 0.0250$
   - Rank 4: $p_{(4)} < \frac{0.05}{1} = 0.0500$
3. Testing stops at the first non-significant result.

---

## 6. Exploratory Subgroup Analyses

Analyses stratified by error category (Categories 1–6):
* **Status:** Formally designated as **exploratory observational sub-analyses**.
* **Sample Size Caveat:** Sample sizes ($N = 10$ to $15$ per category) are underpowered for definitive statistical inference.
* **Reporting Standard:** Every category table must report exact raw numerators and denominators ($\frac{n}{N}$) alongside percentages, avoiding standalone percentage reporting.

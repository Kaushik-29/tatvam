"""
MedResolve — Phase 5.2 Retrieval Reconciliation & Per-Query Audit
Exports detailed judgments, passage IDs at K=1,3,5 for all 100 benchmark queries,
and reconciles all denominators and historical metrics.
"""

import os
import sys
import json
import csv
import time
from pathlib import Path
from typing import Any, Dict, List, Set
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.knowledge_retriever import MedicalKnowledgeBase
from experiments.retrieval_benchmark_dataset import BENCHMARK_100_QUERIES


def run_retrieval_audit():
    kb_path = os.path.join(PROJECT_ROOT, "data", "knowledge_base_v2")
    out_dir = os.path.join(PROJECT_ROOT, "results", "rag", "phase5_2")
    os.makedirs(out_dir, exist_ok=True)

    print(f"Loading Knowledge Base v2 from: {kb_path} ...")
    kb = MedicalKnowledgeBase(knowledge_base_dir=kb_path)

    queries = BENCHMARK_100_QUERIES
    print(f"Auditing all {len(queries)} benchmark queries across Lexical, Dense, and Hybrid...")

    methods = ["lexical", "dense", "hybrid"]
    per_query_records = []

    # Aggregators for in-domain (evaluable) queries
    stats = {
        m: {
            "reciprocal_ranks": [],
            "hits_at_1": 0,
            "hits_at_3": 0,
            "hits_at_5": 0,
            "recalls_1": [],
            "recalls_3": [],
            "recalls_5": [],
            "precisions_1": [],
            "precisions_3": [],
            "precisions_5": [],
            "zero_hits": 0,
            "category_data": {}
        }
        for m in methods
    }

    ood_stats = {
        m: {
            "total": 0,
            "abstained": 0
        }
        for m in methods
    }

    for idx, q_item in enumerate(queries, 1):
        q_id = q_item["query_id"]
        cat = q_item["category"]
        q_text = q_item["query"]
        expected_pids = set(q_item.get("expected_passage_ids", []))
        is_ood = (len(expected_pids) == 0) or (cat == "out_of_domain")

        q_record = {
            "index": idx,
            "query_id": q_id,
            "category": cat,
            "is_out_of_domain": is_ood,
            "query_text": q_text,
            "expected_passage_ids": sorted(list(expected_pids)),
            "methods": {}
        }

        for m in methods:
            t0 = time.perf_counter()
            if m == "lexical":
                res = kb.search_lexical(q_text, top_k=5)
            elif m == "dense":
                res = kb.search_dense(q_text, top_k=5)
            elif m == "hybrid":
                res = kb.search_hybrid(q_text, top_k=5)
            lat_ms = (time.perf_counter() - t0) * 1000.0

            retrieved_pids = [r.passage.passage_id for r in res]
            retrieved_scores = [round(float(r.score), 4) for r in res]

            # Top-K slices
            pids_k1 = retrieved_pids[:1]
            pids_k3 = retrieved_pids[:3]
            pids_k5 = retrieved_pids[:5]

            # Hits
            hits_k1 = set(pids_k1).intersection(expected_pids)
            hits_k3 = set(pids_k3).intersection(expected_pids)
            hits_k5 = set(pids_k5).intersection(expected_pids)

            # Reciprocal rank
            rr = 0.0
            for rank, pid in enumerate(retrieved_pids, 1):
                if pid in expected_pids:
                    rr = 1.0 / rank
                    break

            rec_1 = len(hits_k1) / len(expected_pids) if len(expected_pids) > 0 else 0.0
            rec_3 = len(hits_k3) / len(expected_pids) if len(expected_pids) > 0 else 0.0
            rec_5 = len(hits_k5) / len(expected_pids) if len(expected_pids) > 0 else 0.0

            prec_1 = len(hits_k1) / 1.0
            prec_3 = len(hits_k3) / 3.0
            prec_5 = len(hits_k5) / 5.0

            # Abstention for OOD
            abstained = False
            if is_ood:
                if not res:
                    abstained = True
                else:
                    top_score = res[0].score
                    if m == "dense" and top_score < 0.50:
                        abstained = True
                    elif m == "lexical" and top_score < 5.0:
                        abstained = True
                    elif m == "hybrid" and top_score < 0.01:
                        abstained = True

            q_record["methods"][m] = {
                "retrieved_pids_k1": pids_k1,
                "retrieved_pids_k3": pids_k3,
                "retrieved_pids_k5": pids_k5,
                "retrieved_scores_k5": retrieved_scores,
                "hit_at_k1": len(hits_k1) > 0,
                "hit_at_k3": len(hits_k3) > 0,
                "hit_at_k5": len(hits_k5) > 0,
                "reciprocal_rank": round(rr, 4),
                "recall_at_1": round(rec_1, 4),
                "recall_at_3": round(rec_3, 4),
                "recall_at_5": round(rec_5, 4),
                "precision_at_1": round(prec_1, 4),
                "precision_at_3": round(prec_3, 4),
                "precision_at_5": round(prec_5, 4),
                "latency_ms": round(lat_ms, 2),
                "abstained": abstained
            }

            # Update stats
            if is_ood:
                ood_stats[m]["total"] += 1
                if abstained:
                    ood_stats[m]["abstained"] += 1
            else:
                m_st = stats[m]
                m_st["reciprocal_ranks"].append(rr)
                if len(hits_k1) > 0:
                    m_st["hits_at_1"] += 1
                if len(hits_k3) > 0:
                    m_st["hits_at_3"] += 1
                if len(hits_k5) > 0:
                    m_st["hits_at_5"] += 1
                m_st["recalls_1"].append(rec_1)
                m_st["recalls_3"].append(rec_3)
                m_st["recalls_5"].append(rec_5)
                m_st["precisions_1"].append(prec_1)
                m_st["precisions_3"].append(prec_3)
                m_st["precisions_5"].append(prec_5)
                if rr == 0.0:
                    m_st["zero_hits"] += 1

                # Per-category aggregation
                if cat not in m_st["category_data"]:
                    m_st["category_data"][cat] = {
                        "count": 0,
                        "reciprocal_ranks": [],
                        "recalls_1": [],
                        "recalls_3": [],
                        "recalls_5": [],
                        "zero_hits": 0
                    }
                c_st = m_st["category_data"][cat]
                c_st["count"] += 1
                c_st["reciprocal_ranks"].append(rr)
                c_st["recalls_1"].append(rec_1)
                c_st["recalls_3"].append(rec_3)
                c_st["recalls_5"].append(rec_5)
                if rr == 0.0:
                    c_st["zero_hits"] += 1

        per_query_records.append(q_record)

    # Save full JSON audit
    json_path = os.path.join(out_dir, "retrieval_100_per_query_audit.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(per_query_records, f, indent=2)
    print(f"Per-query audit saved to: {json_path}")

    # Save CSV export for easy inspection / clinical review
    csv_path = os.path.join(out_dir, "retrieval_100_per_query_audit.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Index", "Query ID", "Category", "Is OOD", "Query Text",
            "Expected Passages",
            "Hybrid K=1 Retrieved", "Hybrid K=1 Hit?",
            "Hybrid K=3 Retrieved", "Hybrid K=3 Hit?",
            "Hybrid K=5 Retrieved", "Hybrid K=5 Hit?",
            "Hybrid MRR", "Hybrid Recall@3", "Hybrid Recall@5",
            "Dense K=3 Hit?", "Dense MRR",
            "Lexical K=3 Hit?", "Lexical MRR"
        ])
        for r in per_query_records:
            writer.writerow([
                r["index"],
                r["query_id"],
                r["category"],
                r["is_out_of_domain"],
                r["query_text"],
                "; ".join(r["expected_passage_ids"]),
                "; ".join(r["methods"]["hybrid"]["retrieved_pids_k1"]),
                r["methods"]["hybrid"]["hit_at_k1"],
                "; ".join(r["methods"]["hybrid"]["retrieved_pids_k3"]),
                r["methods"]["hybrid"]["hit_at_k3"],
                "; ".join(r["methods"]["hybrid"]["retrieved_pids_k5"]),
                r["methods"]["hybrid"]["hit_at_k5"],
                r["methods"]["hybrid"]["reciprocal_rank"],
                r["methods"]["hybrid"]["recall_at_3"],
                r["methods"]["hybrid"]["recall_at_5"],
                r["methods"]["dense"]["hit_at_k3"],
                r["methods"]["dense"]["reciprocal_rank"],
                r["methods"]["lexical"]["hit_at_k3"],
                r["methods"]["lexical"]["reciprocal_rank"],
            ])
    print(f"Per-query CSV saved to: {csv_path}")

    # Build Reconciled Metrics Table with Explicit Denominators
    total_queries = len(queries)
    in_domain_evaluable = 90
    ood_queries = 10

    reconciliation = {
        "metadata": {
            "benchmark_name": "MedResolve 100-Query Medical Retrieval Benchmark",
            "target_corpus": "Knowledge Base Version 2 (10 Guidelines, 42 Passages)",
            "total_queries": total_queries,
            "in_domain_evaluable_queries_count": in_domain_evaluable,
            "out_of_domain_negative_controls_count": ood_queries
        },
        "denominators_documented": {
            "in_domain_recall_and_mrr_denominator": in_domain_evaluable,
            "out_of_domain_abstention_denominator": ood_queries,
            "zero_hit_rate_denominator": in_domain_evaluable,
            "improper_mixed_denominator_note": "Dividing in-domain hits by 100 artificially penalizes recall by 10%, because OOD queries intentionally have no valid passages in the corpus."
        },
        "methods_summary": {}
    }

    for m in methods:
        m_st = stats[m]
        reconciliation["methods_summary"][m] = {
            "mrr": {
                "value": round(float(np.mean(m_st["reciprocal_ranks"])), 4),
                "numerator": round(float(np.sum(m_st["reciprocal_ranks"])), 4),
                "denominator": in_domain_evaluable,
                "formula": "sum(reciprocal_ranks) / 90"
            },
            "recall_at_1": {
                "value": round(float(np.mean(m_st["recalls_1"])), 4),
                "mean_percentage": f"{np.mean(m_st['recalls_1'])*100:.2f}%",
                "binary_hit_count": f"{m_st['hits_at_1']}/{in_domain_evaluable} ({m_st['hits_at_1']/in_domain_evaluable*100:.2f}%)",
                "denominator": in_domain_evaluable
            },
            "recall_at_3": {
                "value": round(float(np.mean(m_st["recalls_3"])), 4),
                "mean_percentage": f"{np.mean(m_st['recalls_3'])*100:.2f}%",
                "binary_hit_count": f"{m_st['hits_at_3']}/{in_domain_evaluable} ({m_st['hits_at_3']/in_domain_evaluable*100:.2f}%)",
                "denominator": in_domain_evaluable
            },
            "recall_at_5": {
                "value": round(float(np.mean(m_st["recalls_5"])), 4),
                "mean_percentage": f"{np.mean(m_st['recalls_5'])*100:.2f}%",
                "binary_hit_count": f"{m_st['hits_at_5']}/{in_domain_evaluable} ({m_st['hits_at_5']/in_domain_evaluable*100:.2f}%)",
                "denominator": in_domain_evaluable
            },
            "precision_at_1": {
                "value": round(float(np.mean(m_st["precisions_1"])), 4),
                "denominator": in_domain_evaluable
            },
            "precision_at_3": {
                "value": round(float(np.mean(m_st["precisions_3"])), 4),
                "denominator": in_domain_evaluable
            },
            "precision_at_5": {
                "value": round(float(np.mean(m_st["precisions_5"])), 4),
                "denominator": in_domain_evaluable
            },
            "zero_hit_rate": {
                "rate": round(float(m_st["zero_hits"] / in_domain_evaluable), 4),
                "count_and_fraction": f"{m_st['zero_hits']}/{in_domain_evaluable} ({m_st['zero_hits']/in_domain_evaluable*100:.2f}%)",
                "denominator": in_domain_evaluable
            },
            "negative_control_abstention": {
                "rate": round(float(ood_stats[m]["abstained"] / ood_queries), 4),
                "count_and_fraction": f"{ood_stats[m]['abstained']}/{ood_queries} ({ood_stats[m]['abstained']/ood_queries*100:.2f}%)",
                "denominator": ood_queries
            },
            "per_category_breakdown": {
                c: {
                    "count": c_st["count"],
                    "mrr": round(float(np.mean(c_st["reciprocal_ranks"])), 4),
                    "recall_at_1": f"{np.mean(c_st['recalls_1'])*100:.2f}%",
                    "recall_at_3": f"{np.mean(c_st['recalls_3'])*100:.2f}%",
                    "recall_at_5": f"{np.mean(c_st['recalls_5'])*100:.2f}%",
                    "zero_hits": f"{c_st['zero_hits']}/{c_st['count']}"
                }
                for c, c_st in m_st["category_data"].items()
            }
        }

    rec_json_path = os.path.join(out_dir, "retrieval_metric_reconciliation.json")
    with open(rec_json_path, "w", encoding="utf-8") as f:
        json.dump(reconciliation, f, indent=2)
    print(f"Reconciled metrics summary saved to: {rec_json_path}")

    # Print clean reconciliation summary table to stdout
    print("\n" + "="*80)
    print("MEDRESOLVE PHASE 5.2 RETRIEVAL RECONCILIATION SUMMARY")
    print("="*80)
    print(f"{'Metric':<32} | {'Lexical (BM25)':<15} | {'Dense (BGE-M3)':<15} | {'Hybrid (RRF)':<15}")
    print("-"*80)
    for metric_name in ["mrr", "recall_at_1", "recall_at_3", "recall_at_5", "zero_hit_rate", "negative_control_abstention"]:
        if metric_name == "mrr":
            lex_val = f"{reconciliation['methods_summary']['lexical']['mrr']['value']:.4f}"
            den_val = f"{reconciliation['methods_summary']['dense']['mrr']['value']:.4f}"
            hyb_val = f"{reconciliation['methods_summary']['hybrid']['mrr']['value']:.4f}"
        elif "recall" in metric_name:
            lex_val = reconciliation['methods_summary']['lexical'][metric_name]['mean_percentage']
            den_val = reconciliation['methods_summary']['dense'][metric_name]['mean_percentage']
            hyb_val = reconciliation['methods_summary']['hybrid'][metric_name]['mean_percentage']
        elif metric_name == "zero_hit_rate":
            lex_val = reconciliation['methods_summary']['lexical'][metric_name]['count_and_fraction']
            den_val = reconciliation['methods_summary']['dense'][metric_name]['count_and_fraction']
            hyb_val = reconciliation['methods_summary']['hybrid'][metric_name]['count_and_fraction']
        elif metric_name == "negative_control_abstention":
            lex_val = reconciliation['methods_summary']['lexical'][metric_name]['count_and_fraction']
            den_val = reconciliation['methods_summary']['dense'][metric_name]['count_and_fraction']
            hyb_val = reconciliation['methods_summary']['hybrid'][metric_name]['count_and_fraction']
        print(f"{metric_name:<32} | {lex_val:<15} | {den_val:<15} | {hyb_val:<15}")
    print("="*80)

if __name__ == "__main__":
    run_retrieval_audit()

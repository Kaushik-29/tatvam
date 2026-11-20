"""TA-RAG-style temporal additions: compare intent, on-demand window summaries, trend-series retrieval."""

from collections import defaultdict
from datetime import date

from backend.patient_memory.derived import window_summaries
from backend.rag.query_understanding import understand
from backend.structured_retrieval.patient_retriever import PatientRetriever, RetrievalTrace


def _pt(i, day, value, key="hemoglobin a1c", leaf="laboratory_observations/laboratory_results"):
    return {"record_id": f"Observation/{key}-{i}", "patient_id": "p", "leaf_path": leaf,
            "group_path": f"{leaf}/{key.replace(' ', '_')}", "concept_key": key, "concept_display": key.title(),
            "effective_start": f"{day}T08:00:00", "normalized_value": value, "normalized_unit": "%"}


def test_temporal_intents():
    t = date(2026, 11, 19)
    assert understand("Is my blood sugar better than last month?", today=t).temporal_intent == "compare"
    q = understand("How does my cholesterol compare to before?", today=t)
    assert q.temporal_intent == "compare" and q.temporal_relation == "trend" and q.time_start is None
    assert understand("How has my HbA1c changed over time?", today=t).temporal_intent == "long_term"
    assert understand("What was my latest blood pressure?", today=t).temporal_intent == "recent"
    assert understand("Do I have any allergies?", today=t).temporal_intent is None


def test_window_summaries_compare_with_previous_window():
    series = [_pt(1, "2025-01-10", 8.0), _pt(2, "2025-02-01", 8.2),          # > 90 days before latest
              _pt(3, "2025-06-01", 7.0), _pt(4, "2025-06-20", 6.8), _pt(5, "2025-06-28", 6.6)]
    out = window_summaries("p", series)
    by_w = {r["record_id"].rsplit("/", 1)[-1]: r for r in out}
    assert set(by_w) == {"30d", "365d"}          # 90d holds the same 3 points as 30d, so it is skipped
    w30 = by_w["30d"]
    assert w30["source_system"] == "derived" and w30["verification_status"] == "derived"
    assert abs(w30["value_num"] - 6.8) < 1e-9 and "no measurements in the previous 30 days" in w30["text"]
    w365 = by_w["365d"]
    assert w365["value_text"] == "no_comparison" and "5 measurements" in w365["text"]
    assert window_summaries("p", series[:1]) == []


def test_window_summary_direction():
    series = [_pt(1, "2025-04-10", 10.0), _pt(2, "2025-04-20", 10.0), _pt(3, "2025-05-15", 12.0), _pt(4, "2025-05-25", 12.0)]
    w30 = {r["record_id"].rsplit("/", 1)[-1]: r for r in window_summaries("p", series)}["30d"]
    assert w30["value_text"] == "up" and "+2" in w30["text"]


def test_trend_series_keeps_summary_with_newest_readings():
    raw = [_pt(i, f"2025-0{i}-01", 6.0 + i) for i in range(1, 6)]
    trend = dict(_pt(0, "2025-01-01", 11.0, leaf="laboratory_observations/historical_trends"),
                 record_id="Derived/trend/p/hemoglobin_a1c")
    other = _pt(9, "2025-09-01", 140.0, key="sodium")
    by_group = defaultdict(list)
    for r in sorted(raw + [trend, other], key=lambda r: r["effective_start"], reverse=True):
        by_group[r["group_path"]].append(r)
    groups = [(trend["group_path"], 1.0), (other["group_path"], 0.5)]
    pr = PatientRetriever(mem=None)
    trace = RetrievalTrace(method="t")
    out = pr.trend_series(groups, by_group, understand("How has my HbA1c changed over time?"), trace)
    ids = [r["record_id"] for r in out]
    assert ids[:4] == ["Derived/trend/p/hemoglobin_a1c", "Observation/hemoglobin a1c-5",
                       "Observation/hemoglobin a1c-4", "Observation/hemoglobin a1c-3"]
    assert pr.trend_series(groups, by_group, understand("Do I have allergies?"), trace) == []


def test_trend_series_skips_medication_change_questions():
    trend = dict(_pt(0, "2025-01-01", 11.0, leaf="laboratory_observations/historical_trends"), record_id="Derived/trend/x")
    by_group = defaultdict(list, {trend["group_path"]: [trend]})
    q = understand("Has the patient's acetaminophen prescription changed over time?")
    assert q.temporal_relation == "trend"
    assert PatientRetriever(mem=None).trend_series([(trend["group_path"], 1.0)], by_group, q, RetrievalTrace(method="t")) == []

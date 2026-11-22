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


def test_episode_phrase_outside_symptom_vocabulary():
    """eICU/MIMIC episodes are often named by diagnoses ('sepsis, pulmonary') that are not symptom terms;
    before, these questions found no anchor and lost the episode-medication lookup entirely."""
    q = understand("Which medicines was I on when I had sepsis, pulmonary back in January 2015?")
    assert q.temporal_relation == "during_episode" and q.episode_phrase == "sepsis, pulmonary"
    assert q.time_start == "2015-01-01"
    q = understand("List the medications that were active when the patient reported vomiting in January 2014.")
    assert q.temporal_relation == "during_episode" and q.episode_phrase == "vomiting"
    assert understand("Which medicines was I on when I had pain back in January 2014?").symptoms == ["pain"]
    assert understand("What was my latest blood pressure?").episode_phrase is None


def test_episode_anchor_matches_record_name():
    from types import SimpleNamespace
    leaf = "clinical_encounters/previous_symptoms"
    recs = [dict(_pt(1, "2015-01-03", None, key="anxiety", leaf=leaf), concept_display="Anxiety"),
            dict(_pt(2, "2015-01-02", None, key="sepsis, pulmonary", leaf=leaf), concept_display="Sepsis, pulmonary")]
    med = {"record_id": "MedicationRequest/m1", "interval_start": "2015-01-01T00:00:00", "interval_end": None}
    mem = SimpleNamespace(medications_active_at=lambda when: [med])
    pr = PatientRetriever(mem=mem)
    pr._records = recs
    trace = RetrievalTrace(method="t")
    out = pr.episode_medications(understand("Which medicines was I on when I had sepsis, pulmonary in January 2015?"), trace)
    assert [r["record_id"] for r in out] == [recs[1]["record_id"], "MedicationRequest/m1"]


def test_episode_anchor_other_constructions():
    """Episode questions are recognised by meaning, not one template: 'when X first started', 'an episode of X'."""
    q = understand("What medications was the patient taking when the sinus infection first started in May 2026?")
    assert (q.temporal_relation, q.episode_phrase, q.time_start) == ("during_episode", "sinus infection", "2026-05-01")
    q = understand("Which drugs was I prescribed during an episode of acute bronchitis in March 2019?")
    assert q.episode_phrase == "acute bronchitis" and q.time_start == "2019-03-01"
    q = understand("What meds was the patient on while they were experiencing chest pain, what were they?")
    assert q.episode_phrase == "chest pain"


def test_dates_years_and_shifted_years():
    """'in the year 2003' is a date range; 'during 2003' is a range, not an episode; MIMIC dates are shifted
    into 21xx and must still be read."""
    q = understand("What conditions did the patient receive a diagnosis for in the year 2003?")
    assert (q.time_start, q.time_end, q.temporal_relation) == ("2003-01-01", "2004-01-01", "range")
    q = understand("Which conditions was the patient diagnosed with during 2003?")
    assert q.temporal_relation == "range" and q.episode_phrase is None
    q = understand("What medications was the patient taking during their previous abdominal pain, unspecified site episode in August 2180?")
    assert (q.time_start, q.episode_phrase) == ("2180-08-01", "abdominal pain, unspecified site")
    assert understand("Show my potassium results from March of 2017.").time_start == "2017-03-01"


def test_trend_and_intent_wording():
    assert understand("Is the patient's sodium improving or deteriorating over the years?").temporal_relation == "trend"
    assert understand("Is my body height trending upward or downward?").intent == "lab_trend"
    assert understand("What is the patient's most current body weight measurement?").intent == "latest_measurement"
    assert understand("List the patient's active medications.").intent == "current_medications"
    assert understand("Has the patient's amoxicillin regimen undergone any adjustments?").intent == "medication_changes"
    assert understand("Can I see the patient's history of complete blood cell counts?").organ_systems == ["blood count"]
    assert understand("When was the patient's most recent clinical encounter?").intent == "last_visit"

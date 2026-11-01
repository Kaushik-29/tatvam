"""Tiny hand-built FHIR R4 bundles (synthetic) for deterministic tests."""

import base64

NOTE_B64 = base64.b64encode(
    b"# Chief Complaint\n- Dizziness\n- Headache\n\n# Assessment and Plan\nPatient is stable.\n").decode()


def _ref(i):
    return {"reference": f"urn:uuid:{i}"}


def bundle(pid="pat-a", prefix="a"):
    enc1, enc2 = f"{prefix}-enc-1", f"{prefix}-enc-2"
    r = [
        {"resourceType": "Patient", "id": pid, "name": [{"given": ["Test"], "family": prefix.upper()}],
         "gender": "female", "birthDate": "1970-05-01", "address": [{"city": "Springfield", "state": "MA"}]},
        {"resourceType": "Encounter", "id": enc1, "status": "finished", "class": {"code": "AMB"},
         "type": [{"coding": [{"system": "http://snomed.info/sct", "code": "185345009",
                               "display": "Encounter for symptom (procedure)"}], "text": "Encounter for symptom (procedure)"}],
         "subject": _ref(pid), "period": {"start": "2019-03-02T09:00:00+00:00", "end": "2019-03-02T09:30:00+00:00"},
         "reasonCode": [{"coding": [{"display": "Dizziness (finding)"}], "text": "Dizziness (finding)"}]},
        {"resourceType": "Encounter", "id": enc2, "status": "finished", "class": {"code": "IMP"},
         "type": [{"coding": [{"display": "Hospital admission (procedure)"}], "text": "Hospital admission (procedure)"}],
         "subject": _ref(pid), "period": {"start": "2023-06-10T09:00:00+00:00", "end": "2023-06-12T09:00:00+00:00"}},
        {"resourceType": "Condition", "id": f"{prefix}-cond-htn", "subject": _ref(pid), "encounter": _ref(enc1),
         "clinicalStatus": {"coding": [{"code": "active"}]}, "verificationStatus": {"coding": [{"code": "confirmed"}]},
         "code": {"coding": [{"system": "http://snomed.info/sct", "code": "59621000", "display": "Essential hypertension (disorder)"}],
                  "text": "Essential hypertension (disorder)"},
         "onsetDateTime": "2015-01-10T09:00:00+00:00", "recordedDate": "2015-01-10T09:00:00+00:00"},
        {"resourceType": "Condition", "id": f"{prefix}-cond-dizzy", "subject": _ref(pid), "encounter": _ref(enc1),
         "clinicalStatus": {"coding": [{"code": "resolved"}]}, "verificationStatus": {"coding": [{"code": "confirmed"}]},
         "code": {"coding": [{"display": "Dizziness (finding)"}], "text": "Dizziness (finding)"},
         "onsetDateTime": "2019-03-02T09:00:00+00:00", "abatementDateTime": "2019-03-20T09:00:00+00:00"},
        {"resourceType": "Condition", "id": f"{prefix}-cond-job", "subject": _ref(pid),
         "clinicalStatus": {"coding": [{"code": "active"}]}, "verificationStatus": {"coding": [{"code": "confirmed"}]},
         "code": {"coding": [{"display": "Full-time employment (finding)"}], "text": "Full-time employment (finding)"},
         "onsetDateTime": "2010-01-01T09:00:00+00:00"},
        {"resourceType": "MedicationRequest", "id": f"{prefix}-med-1", "status": "completed", "subject": _ref(pid),
         "encounter": _ref(enc1), "authoredOn": "2015-01-10T09:00:00+00:00",
         "medicationCodeableConcept": {"coding": [{"system": "rxnorm", "code": "314076", "display": "lisinopril 10 MG Oral Tablet"}],
                                       "text": "lisinopril 10 MG Oral Tablet"},
         "reasonReference": [{"display": "Essential hypertension (disorder)"}]},
        {"resourceType": "MedicationRequest", "id": f"{prefix}-med-2", "status": "completed", "subject": _ref(pid),
         "authoredOn": "2018-01-10T09:00:00+00:00",
         "medicationCodeableConcept": {"text": "lisinopril 20 MG Oral Tablet"}},
        {"resourceType": "MedicationRequest", "id": f"{prefix}-med-3", "status": "active", "subject": _ref(pid),
         "authoredOn": "2019-01-05T09:00:00+00:00",
         "medicationCodeableConcept": {"text": "lisinopril 20 MG Oral Tablet"}},
        {"resourceType": "MedicationRequest", "id": f"{prefix}-med-amox", "status": "active", "subject": _ref(pid),
         "authoredOn": "2026-10-01T09:00:00+00:00",
         "medicationCodeableConcept": {"text": "amoxicillin 500 MG Oral Capsule"}},
        {"resourceType": "AllergyIntolerance", "id": f"{prefix}-allergy", "patient": _ref(pid),
         "clinicalStatus": {"coding": [{"code": "active"}]}, "verificationStatus": {"coding": [{"code": "confirmed"}]},
         "category": ["medication"], "criticality": "high",
         "code": {"coding": [{"display": "Penicillin V (substance)"}], "text": "Penicillin V (substance)"},
         "recordedDate": "2012-02-02T09:00:00+00:00",
         "reaction": [{"manifestation": [{"text": "Hives"}], "severity": "moderate"}]},
        {"resourceType": "DocumentReference", "id": f"{prefix}-note-1", "subject": _ref(pid), "status": "current",
         "type": {"coding": [{"display": "History and physical note"}]}, "date": "2019-03-02T09:00:00+00:00",
         "context": {"encounter": [_ref(enc1)]},
         "content": [{"attachment": {"data": NOTE_B64}}]},
    ]
    for i, (d, v) in enumerate([("2017-05-01", 0.9), ("2020-05-01", 1.1), ("2023-06-10", 1.4)]):
        r.append({"resourceType": "Observation", "id": f"{prefix}-creat-{i}", "status": "final", "subject": _ref(pid),
                  "category": [{"coding": [{"code": "laboratory"}]}],
                  "code": {"coding": [{"system": "http://loinc.org", "code": "2160-0",
                                       "display": "Creatinine [Mass/volume] in Serum or Plasma"}],
                           "text": "Creatinine [Mass/volume] in Serum or Plasma"},
                  "effectiveDateTime": f"{d}T09:00:00+00:00", "valueQuantity": {"value": v, "unit": "mg/dL", "code": "mg/dL"}})
    r.append({"resourceType": "Observation", "id": f"{prefix}-bp", "status": "final", "subject": _ref(pid),
              "encounter": _ref(enc1), "category": [{"coding": [{"code": "vital-signs"}]}],
              "code": {"text": "Blood pressure panel with all children optional"},
              "effectiveDateTime": "2019-03-02T09:00:00+00:00",
              "component": [
                  {"code": {"coding": [{"system": "http://loinc.org", "code": "8480-6", "display": "Systolic Blood Pressure"}]},
                   "valueQuantity": {"value": 148, "unit": "mm[Hg]", "code": "mm[Hg]"}},
                  {"code": {"coding": [{"system": "http://loinc.org", "code": "8462-4", "display": "Diastolic Blood Pressure"}]},
                   "valueQuantity": {"value": 92, "unit": "mm[Hg]", "code": "mm[Hg]"}}]})
    return {"resourceType": "Bundle", "type": "transaction", "entry": [{"resource": x} for x in r]}

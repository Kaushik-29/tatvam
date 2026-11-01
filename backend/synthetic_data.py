"""
MedResolve — Synthetic Demonstration Patients & Case Data
Provides 8 realistic synthetic patient cases representing distinct clinical archetypes:
1. Arjun Mehta (54M): Clean In-Domain GERD -> Policy Action: EXPLAIN
2. Priya Sharma (32F): Incomplete Acute Bronchitis -> Policy Action: ASK (clarification on cough duration & phlegm)
3. David Miller (48M): Conflicting Evidence (Pleuritic Pain vs Muscular Costochondritis) -> Policy Action: ABSTAIN_AND_NAVIGATE
4. Fatima Al-Hassan (61F): Low-Confidence OCR Extraction (Discharge Summary Weight Loss) -> Policy Action: ASK (unconfirmed OCR verification)
5. Robert Chen (67M): Material Clinician Disagreement (Cardiologist vs Gastroenterologist) -> Policy Action: ABSTAIN_AND_NAVIGATE (non-arbitration)
6. Eleanor Vance (78F): Out-of-Domain Request (Alzheimer / Progressive Dementia) -> Policy Action: ABSTAIN_AND_NAVIGATE (domain boundaries)
7. Marcus Brody (28M): Acute Airway Emergency (Peanut Anaphylaxis with Stridor) -> Policy Action: EMERGENCY_OVERRIDE (Clinical red flag, 112/108 directive)
8. Sunita Rao (45F): Hyperpyrexia with Missing Unit (Core Temperature 104.8) -> Policy Action: EMERGENCY_OVERRIDE (normalized degF, clinical red flag alert)
"""

from typing import Dict, List, Any
from experiments.evidence_ledger import (
    EvidenceLedger,
    EvidenceItem,
    ClinicianOpinionItem,
    SourceType,
    ExtractionMethod,
    UserConfirmationStatus,
    EvidenceStatus,
)


def get_all_synthetic_patients() -> List[Dict[str, Any]]:
    return [
        {
            "patient_id": "SYNTH_PATIENT_01",
            "name": "Arjun Mehta (Synthetic Demo)",
            "age": 54,
            "sex": "Male",
            "height_cm": 174.0,
            "weight_kg": 82.5,
            "relevant_background": "Desk worker, reports sedentary lifestyle and post-meal recumbency. Non-smoker.",
            "reported_diagnoses": ["Dyspepsia (mild, 2024)", "Essential Hypertension (well-controlled)"],
            "allergies": ["None reported"],
            "current_medications": [
                {"name": "Amlodipine", "dose": "5mg once daily", "duration": "2 years", "indication": "Hypertension"},
                {"name": "Antacid gel (Aluminum Hydroxide)", "dose": "10ml as needed", "duration": "3 weeks", "indication": "Heartburn"}
            ],
            "past_medical_history": ["Mild hypertension (2022)", "Annual executive health checkup 2025 normal"],
            "synthetic_case_archetype": "IN_DOMAIN_CLEAN",
            "archetype_display": "Clean In-Domain Presentation (GERD)",
            "expected_action": "EXPLAIN",
            "clinical_narrative": "54-year-old male reporting burning chest discomfort after heavy dinner and sour fluid regurgitation when lying flat. Symptoms relieve partially with liquid antacids. No radiation to neck or arm. Normal vitals.",
            "documents_count": 2,
            "evidence_count": 5,
            "conflicts_count": 0,
        },
        {
            "patient_id": "SYNTH_PATIENT_02",
            "name": "Priya Sharma (Synthetic Demo)",
            "age": 32,
            "sex": "Female",
            "height_cm": 162.0,
            "weight_kg": 58.0,
            "relevant_background": "School teacher, frequent exposure to classroom respiratory illnesses. Lifelong non-smoker.",
            "reported_diagnoses": ["None"],
            "allergies": ["Sulfa drugs (mild rash)"],
            "current_medications": [
                {"name": "Paracetamol", "dose": "500mg as needed", "duration": "3 days", "indication": "Fever / Headache"}
            ],
            "past_medical_history": ["Seasonal allergic rhinitis"],
            "synthetic_case_archetype": "INCOMPLETE_INFORMATION",
            "archetype_display": "Incomplete Patient Intake (Acute Bronchitis)",
            "expected_action": "ASK",
            "clinical_narrative": "32-year-old female presents with persistent daytime cough and low-grade fever. Missing key clinical variables: exact cough duration, presence of purulent sputum, and nocturnal paroxysms.",
            "documents_count": 1,
            "evidence_count": 4,
            "conflicts_count": 0,
        },
        {
            "patient_id": "SYNTH_PATIENT_03",
            "name": "David Miller (Synthetic Demo)",
            "age": 48,
            "sex": "Male",
            "height_cm": 180.0,
            "weight_kg": 91.0,
            "relevant_background": "Long-distance truck driver, returned from 14-hour cross-country journey 2 days ago.",
            "reported_diagnoses": ["Costochondritis (diagnosed 2025)", "Hyperlipidemia"],
            "allergies": ["Penicillin (severe hives)"],
            "current_medications": [
                {"name": "Atorvastatin", "dose": "20mg daily", "duration": "18 months", "indication": "Cholesterol"},
                {"name": "Ibuprofen", "dose": "400mg twice daily", "duration": "4 days", "indication": "Chest wall pain"}
            ],
            "past_medical_history": ["Deep vein thrombosis risk factor (long haul driving)"],
            "synthetic_case_archetype": "TEMPORAL_AND_VALUE_CONFLICT",
            "archetype_display": "Information Conflict (Pleuritic vs Costochondritis)",
            "expected_action": "ABSTAIN_AND_NAVIGATE",
            "clinical_narrative": "48-year-old male with sharp right-sided pleuritic chest pain aggravated by deep inspiration. Patient attributes pain to old muscular costochondritis, but recent laboratory report indicates elevated D-dimer (1.4 mcg/mL).",
            "documents_count": 2,
            "evidence_count": 6,
            "conflicts_count": 2,
        },
        {
            "patient_id": "SYNTH_PATIENT_04",
            "name": "Fatima Al-Hassan (Synthetic Demo)",
            "age": 61,
            "sex": "Female",
            "height_cm": 155.0,
            "weight_kg": 64.0,
            "relevant_background": "Homemaker, uploaded blurred mobile phone camera scan of outpatient hospital discharge summary.",
            "reported_diagnoses": ["Type 2 Diabetes Mellitus", "Mild Osteoarthritis"],
            "allergies": ["None known"],
            "current_medications": [
                {"name": "Metformin", "dose": "500mg twice daily", "duration": "5 years", "indication": "Diabetes"}
            ],
            "past_medical_history": ["Cholecystectomy (2018)"],
            "synthetic_case_archetype": "LOW_CONFIDENCE_OCR",
            "archetype_display": "Low-Confidence OCR Scan (Discharge Summary)",
            "expected_action": "ASK",
            "clinical_narrative": "61-year-old female uploaded a degraded hospital discharge summary. OCR extraction flagged 'Unintended weight loss 12 kg' with low confidence (0.42). System must confirm finding with patient before assessment.",
            "documents_count": 1,
            "evidence_count": 5,
            "conflicts_count": 1,
        },
        {
            "patient_id": "SYNTH_PATIENT_05",
            "name": "Robert Chen (Synthetic Demo)",
            "age": 67,
            "sex": "Male",
            "height_cm": 168.0,
            "weight_kg": 76.0,
            "relevant_background": "Retired civil engineer, two conflicting clinical specialist opinions on file.",
            "reported_diagnoses": ["CAD suspected", "Chronic Gastritis"],
            "allergies": ["Aspirin (gastrointestinal bleeding 2021)"],
            "current_medications": [
                {"name": "Pantoprazole", "dose": "40mg morning", "duration": "3 months", "indication": "Gastritis"},
                {"name": "Colchicine", "dose": "0.5mg daily", "duration": "1 week", "indication": "Cardiologist prescribed"}
            ],
            "past_medical_history": ["Mild upper GI bleed (2021)"],
            "synthetic_case_archetype": "CLINICIAN_OPINION_DISAGREEMENT",
            "archetype_display": "Material Clinician Disagreement (Cardiology vs GI)",
            "expected_action": "ABSTAIN_AND_NAVIGATE",
            "clinical_narrative": "67-year-old male with persistent retrosternal pain. Cardiologist (Dr. Gupta) diagnosed Acute Pericarditis and prescribed NSAIDs/Colchicine. Gastroenterologist (Dr. Patel) diagnosed Severe Reflux Esophagitis and advised strictly stopping NSAIDs due to GI bleeding risk.",
            "documents_count": 3,
            "evidence_count": 6,
            "conflicts_count": 1,
        },
        {
            "patient_id": "SYNTH_PATIENT_06",
            "name": "Eleanor Vance (Synthetic Demo)",
            "age": 78,
            "sex": "Female",
            "height_cm": 160.0,
            "weight_kg": 54.0,
            "relevant_background": "Accompanied by adult daughter. Reports 14 months of progressive short-term memory loss and misplacing everyday items.",
            "reported_diagnoses": ["Osteoporosis", "Mild cognitive decline"],
            "allergies": ["None"],
            "current_medications": [
                {"name": "Calcium + Vitamin D3", "dose": "daily", "duration": "3 years", "indication": "Bone health"}
            ],
            "past_medical_history": ["Colles fracture of left wrist (2022)"],
            "synthetic_case_archetype": "OUT_OF_DOMAIN",
            "archetype_display": "Out-of-Domain Request (Alzheimer / Dementia)",
            "expected_action": "ABSTAIN_AND_NAVIGATE",
            "clinical_narrative": "78-year-old female seeking diagnosis for progressive short-term memory decline. MedResolve knowledge corpus is strictly bounded to cardiopulmonary and gastrointestinal conditions, triggering safe domain abstention.",
            "documents_count": 1,
            "evidence_count": 3,
            "conflicts_count": 0,
        },
        {
            "patient_id": "SYNTH_PATIENT_07",
            "name": "Marcus Brody (Synthetic Demo)",
            "age": 28,
            "sex": "Male",
            "height_cm": 185.0,
            "weight_kg": 85.0,
            "relevant_background": "Attending university dinner, accidentally ingested satay sauce containing peanuts.",
            "reported_diagnoses": ["Peanut allergy (diagnosed childhood)"],
            "allergies": ["Peanuts (Severe Anaphylaxis)"],
            "current_medications": [
                {"name": "EpiPen (Epinephrine)", "dose": "0.3mg auto-injector", "duration": "Prescribed as needed", "indication": "Anaphylaxis"}
            ],
            "past_medical_history": ["Mild asthma"],
            "synthetic_case_archetype": "EMERGENCY_OVERRIDE_STRIDOR",
            "archetype_display": "Urgent Emergency Override (Airway Stridor / Anaphylaxis)",
            "expected_action": "EMERGENCY_OVERRIDE",
            "clinical_narrative": "28-year-old male with acute onset facial angioedema, difficulty speaking, and high-pitched inspiratory stridor 15 minutes after food ingestion. Clinical red flag indicators present. Deterministic bypass of all AI generation.",
            "documents_count": 0,
            "evidence_count": 4,
            "conflicts_count": 0,
        },
        {
            "patient_id": "SYNTH_PATIENT_08",
            "name": "Sunita Rao (Synthetic Demo)",
            "age": 45,
            "sex": "Female",
            "height_cm": 158.0,
            "weight_kg": 62.0,
            "relevant_background": "Returned from tropical region 4 days ago. Severe shivering chills and sudden high fever.",
            "reported_diagnoses": ["None"],
            "allergies": ["None known"],
            "current_medications": [],
            "past_medical_history": ["Uncomplicated appendectomy (2015)"],
            "synthetic_case_archetype": "EMERGENCY_OVERRIDE_HYPERPYREXIA",
            "archetype_display": "Urgent Emergency Override (Hyperpyrexia 104.8°F)",
            "expected_action": "EMERGENCY_OVERRIDE",
            "clinical_narrative": "45-year-old female with profound rigors, confusion, and core temperature recorded at 104.8 with missing unit in clinic telemetry. Vital normalization resolves degF scale and triggers hyperpyrexia red flag.",
            "documents_count": 1,
            "evidence_count": 4,
            "conflicts_count": 0,
        },
    ]


def build_synthetic_ledger(patient_id: str) -> EvidenceLedger:
    ledger = EvidenceLedger(patient_case_id=patient_id)

    if patient_id == "SYNTH_PATIENT_01":
        # Arjun Mehta: Clean GERD
        ledger.add_item(EvidenceItem(
            evidence_id="ev_01_heartburn",
            patient_case_id=patient_id,
            concept="E_55_@_V_101",
            concept_name_en="Retrosternal burning pain after meals",
            normalized_value=True,
            original_value="Burning chest pain especially after dinner",
            unit=None,
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-30T09:00:00Z",
            extraction_method=ExtractionMethod.DIRECT_SELECTION,
            extraction_confidence=1.0,
            user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT,
            evidence_status=EvidenceStatus.PRESENT,
        ))
        ledger.add_item(EvidenceItem(
            evidence_id="ev_01_regurg",
            patient_case_id=patient_id,
            concept="E_REGURG",
            concept_name_en="Acid regurgitation / sour taste in mouth",
            normalized_value=True,
            original_value="Sour liquid coming up into my throat when bending down",
            unit=None,
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-30T09:05:00Z",
            extraction_method=ExtractionMethod.DIRECT_SELECTION,
            extraction_confidence=1.0,
            user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT,
            evidence_status=EvidenceStatus.PRESENT,
        ))
        ledger.add_item(EvidenceItem(
            evidence_id="ev_01_temp",
            patient_case_id=patient_id,
            concept="E_TEMP",
            concept_name_en="Core body temperature",
            normalized_value="98.4",
            original_value="98.4 F",
            unit="degF",
            source_type=SourceType.LABORATORY_REPORT,
            source_document_id="DOC_VITALS_001",
            recorded_timestamp="2026-10-30T09:10:00Z",
            extraction_method=ExtractionMethod.MANUAL_ENTRY,
            extraction_confidence=1.0,
            user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT,
            evidence_status=EvidenceStatus.PRESENT,
        ))
        ledger.add_item(EvidenceItem(
            evidence_id="ev_01_spo2",
            patient_case_id=patient_id,
            concept="E_SPO2",
            concept_name_en="Pulse oximetry",
            normalized_value="98.0",
            original_value="98%",
            unit="%",
            source_type=SourceType.LABORATORY_REPORT,
            source_document_id="DOC_VITALS_001",
            recorded_timestamp="2026-10-30T09:10:00Z",
            extraction_method=ExtractionMethod.MANUAL_ENTRY,
            extraction_confidence=1.0,
            user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT,
            evidence_status=EvidenceStatus.PRESENT,
        ))
        ledger.add_item(EvidenceItem(
            evidence_id="ev_01_exertion_absent",
            patient_case_id=patient_id,
            concept="E_EXERTIONAL_PAIN",
            concept_name_en="Exertional exacerbation of chest discomfort",
            normalized_value=False,
            original_value="No pain during fast walking or climbing stairs",
            unit=None,
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-30T09:12:00Z",
            extraction_method=ExtractionMethod.DIRECT_SELECTION,
            extraction_confidence=1.0,
            user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT,
            evidence_status=EvidenceStatus.ABSENT,
        ))

    elif patient_id == "SYNTH_PATIENT_02":
        # Priya Sharma: Incomplete Bronchitis
        ledger.add_item(EvidenceItem(
            evidence_id="ev_02_cough",
            patient_case_id=patient_id,
            concept="E_COUGH",
            concept_name_en="Persistent daytime cough",
            normalized_value=True,
            original_value="Frequent dry cough throughout the day",
            unit=None,
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-30T08:30:00Z",
            extraction_method=ExtractionMethod.DIRECT_SELECTION,
            extraction_confidence=1.0,
            user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT,
            evidence_status=EvidenceStatus.PRESENT,
        ))
        ledger.add_item(EvidenceItem(
            evidence_id="ev_02_temp",
            patient_case_id=patient_id,
            concept="E_TEMP",
            concept_name_en="Low-grade fever",
            normalized_value="99.8",
            original_value="99.8 F",
            unit="degF",
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-30T08:32:00Z",
            extraction_method=ExtractionMethod.MANUAL_ENTRY,
            extraction_confidence=0.90,
            user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT,
            evidence_status=EvidenceStatus.PRESENT,
        ))
        # Note: missing cough_duration and sputum_character -> triggers ASK

    elif patient_id == "SYNTH_PATIENT_03":
        # David Miller: Conflicting pleuritic pain vs costochondritis
        ledger.add_item(EvidenceItem(
            evidence_id="ev_03_pleuritic",
            patient_case_id=patient_id,
            concept="E_55_@_V_170",
            concept_name_en="Sharp pleuritic chest pain with inspiration",
            normalized_value=True,
            original_value="Knife-like pain on right side when taking deep breath",
            unit=None,
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-30T07:45:00Z",
            extraction_method=ExtractionMethod.DIRECT_SELECTION,
            extraction_confidence=1.0,
            user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT,
            evidence_status=EvidenceStatus.PRESENT,
        ))
        ledger.add_item(EvidenceItem(
            evidence_id="ev_03_ddimer",
            patient_case_id=patient_id,
            concept="E_DDIMER",
            concept_name_en="D-Dimer plasma concentration",
            normalized_value="1.4",
            original_value="1.4 mcg/mL",
            unit="mcg/mL",
            source_type=SourceType.LABORATORY_REPORT,
            source_document_id="DOC_LAB_DDIMER",
            recorded_timestamp="2026-10-30T08:00:00Z",
            extraction_method=ExtractionMethod.OCR_EXTRACTION,
            extraction_confidence=0.96,
            user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_CLINICIAN,
            evidence_status=EvidenceStatus.PRESENT,
        ))
        ledger.add_opinion(ClinicianOpinionItem(
            opinion_id="op_03_prior_gp",
            patient_case_id=patient_id,
            clinician_id="DR_HAWKINS_GP",
            clinician_specialty="Family Medicine",
            diagnostic_impression="Atypical Musculoskeletal Costochondritis",
            confidence_assessment="PROBABLE",
            recorded_timestamp="2026-04-12T10:00:00Z",
            source_document_id="DOC_GP_PRIOR_NOTE",
            notes="Tender to palpation over 4th and 5th chondrosternal junctions.",
        ))

    elif patient_id == "SYNTH_PATIENT_04":
        # Fatima Al-Hassan: Low-Confidence OCR
        ledger.add_item(EvidenceItem(
            evidence_id="ev_04_pyrosis",
            patient_case_id=patient_id,
            concept="E_55_@_V_101",
            concept_name_en="Epigastric and retrosternal heartburn",
            normalized_value=True,
            original_value="Discomfort in stomach and chest after meals",
            unit=None,
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-30T10:15:00Z",
            extraction_method=ExtractionMethod.DIRECT_SELECTION,
            extraction_confidence=1.0,
            user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT,
            evidence_status=EvidenceStatus.PRESENT,
        ))
        ledger.add_item(EvidenceItem(
            evidence_id="ev_04_unconf_weight_loss",
            patient_case_id=patient_id,
            concept="E_WEIGHT_LOSS",
            concept_name_en="Significant unintended weight loss",
            normalized_value="12.0",
            original_value="Weight loss ~12 kg (blurry scan)",
            unit="kg",
            source_type=SourceType.EHR_EXTRACTED_NOTE,
            source_document_id="DOC_HOSP_DISCHARGE_04",
            source_page=1,
            recorded_timestamp="2026-10-30T10:20:00Z",
            extraction_method=ExtractionMethod.OCR_EXTRACTION,
            extraction_confidence=0.42,  # < 0.70 threshold -> Low confidence!
            user_confirmation_status=UserConfirmationStatus.UNCONFIRMED,
            evidence_status=EvidenceStatus.PRESENT,
            notes="Extracted from wrinkled discharge letter corner. Low OCR character confidence.",
        ))

    elif patient_id == "SYNTH_PATIENT_05":
        # Robert Chen: Clinician Disagreement
        ledger.add_item(EvidenceItem(
            evidence_id="ev_05_chest_discomfort",
            patient_case_id=patient_id,
            concept="E_55_@_V_55",
            concept_name_en="Retrosternal chest discomfort",
            normalized_value=True,
            original_value="Persistent discomfort centered behind breastbone",
            unit=None,
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-29T14:00:00Z",
            extraction_method=ExtractionMethod.DIRECT_SELECTION,
            extraction_confidence=1.0,
            user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT,
            evidence_status=EvidenceStatus.PRESENT,
        ))
        ledger.add_opinion(ClinicianOpinionItem(
            opinion_id="op_05_cardio",
            patient_case_id=patient_id,
            clinician_id="DR_GUPTA_CARDIO",
            clinician_specialty="Cardiology",
            diagnostic_impression="Acute Pericarditis",
            confidence_assessment="DEFINITIVE",
            recorded_timestamp="2026-10-29T15:30:00Z",
            source_document_id="DOC_CONSULT_CARDIO_05",
            notes="ECG demonstrated PR depression in lead II. Prescribed High-dose NSAIDs + Colchicine.",
        ))
        ledger.add_opinion(ClinicianOpinionItem(
            opinion_id="op_05_gi",
            patient_case_id=patient_id,
            clinician_id="DR_PATEL_GI",
            clinician_specialty="Gastroenterology",
            diagnostic_impression="Severe Erosive Reflux Esophagitis (Los Angeles Grade C)",
            confidence_assessment="DEFINITIVE",
            recorded_timestamp="2026-10-29T16:45:00Z",
            source_document_id="DOC_CONSULT_GI_05",
            notes="Endoscopy showed confluent linear ulcerations. High-dose NSAIDs strictly contraindicated.",
        ))

    elif patient_id == "SYNTH_PATIENT_06":
        # Eleanor Vance: Out of Domain
        ledger.add_item(EvidenceItem(
            evidence_id="ev_06_memory",
            patient_case_id=patient_id,
            concept="E_MEMORY_LOSS",
            concept_name_en="Progressive short-term episodic memory loss",
            normalized_value=True,
            original_value="Cannot remember conversations from breakfast, misplaces wallet daily",
            unit=None,
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-30T11:00:00Z",
            extraction_method=ExtractionMethod.DIRECT_SELECTION,
            extraction_confidence=1.0,
            user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT,
            evidence_status=EvidenceStatus.PRESENT,
        ))

    elif patient_id == "SYNTH_PATIENT_07":
        # Marcus Brody: Peanut Anaphylaxis with Stridor (Clinical Red Flag)
        ledger.add_item(EvidenceItem(
            evidence_id="ev_07_stridor",
            patient_case_id=patient_id,
            concept="E_194",
            concept_name_en="High-pitched inspiratory stridor",
            normalized_value=True,
            original_value="Crowing whistling noise when trying to breathe in",
            unit=None,
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-30T12:00:00Z",
            extraction_method=ExtractionMethod.DIRECT_SELECTION,
            extraction_confidence=1.0,
            user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT,
            evidence_status=EvidenceStatus.PRESENT,
        ))
        ledger.add_item(EvidenceItem(
            evidence_id="ev_07_swelling",
            patient_case_id=patient_id,
            concept="E_151",
            concept_name_en="Diffuse facial and lip angioedema",
            normalized_value=True,
            original_value="Swollen lips and tongue rapidly developing",
            unit=None,
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-30T12:02:00Z",
            extraction_method=ExtractionMethod.DIRECT_SELECTION,
            extraction_confidence=1.0,
            user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT,
            evidence_status=EvidenceStatus.PRESENT,
        ))

    elif patient_id == "SYNTH_PATIENT_08":
        # Sunita Rao: Hyperpyrexia with Missing Unit (104.8)
        ledger.add_item(EvidenceItem(
            evidence_id="ev_08_temp",
            patient_case_id=patient_id,
            concept="E_TEMP",
            concept_name_en="Core body temperature (telemetry)",
            normalized_value="104.8",
            original_value="104.8",
            unit=None,  # Missing unit handled by unit normalizer
            source_type=SourceType.LABORATORY_REPORT,
            source_document_id="DOC_TELEMETRY_08",
            recorded_timestamp="2026-10-30T12:05:00Z",
            extraction_method=ExtractionMethod.OCR_EXTRACTION,
            extraction_confidence=0.98,
            user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_CLINICIAN,
            evidence_status=EvidenceStatus.PRESENT,
        ))
        ledger.add_item(EvidenceItem(
            evidence_id="ev_08_rigors",
            patient_case_id=patient_id,
            concept="E_RIGORS",
            concept_name_en="Violent shaking chills and rigors",
            normalized_value=True,
            original_value="Whole body shivering and teeth chattering",
            unit=None,
            source_type=SourceType.PATIENT_REPORTED,
            recorded_timestamp="2026-10-30T12:06:00Z",
            extraction_method=ExtractionMethod.DIRECT_SELECTION,
            extraction_confidence=1.0,
            user_confirmation_status=UserConfirmationStatus.CONFIRMED_BY_PATIENT,
            evidence_status=EvidenceStatus.PRESENT,
        ))

    return ledger

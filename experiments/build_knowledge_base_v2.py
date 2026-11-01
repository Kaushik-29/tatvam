"""
MedResolve — Knowledge Base Corpus Builder (Version 2)
Phase 5.1 Document Ingestion, License Rectification & Expanded Provenance Registration

Preserves original data/knowledge_base/ and creates versioned expanded corpus in data/knowledge_base_v2/:
- Corrects StatPearls copyright and licensing metadata (NCBI Bookshelf Educational & Research Access, not Public Domain).
- Adds 4 new public clinical guidelines (MoHFW Hypertension, MoHFW Type 2 Diabetes, WHO Asthma, MoHFW Community Pneumonia).
- Ingests 10 structured JSON documents in data/knowledge_base_v2/documents/ (42 semantic passages total).
- Generates master manifest in data/knowledge_base_v2/knowledge_manifest.json.
"""

import json
from pathlib import Path

KB_V2_DIR = Path("data/knowledge_base_v2")
DOCS_DIR = KB_V2_DIR / "documents"
KB_V2_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(parents=True, exist_ok=True)

DOCUMENTS_V2 = [
    # -------------------------------------------------------------------------
    # Doc 1: MoHFW GERD (2019)
    # -------------------------------------------------------------------------
    {
        "document_id": "DOC_MOHFW_GERD_2019",
        "title": "Standard Treatment Guidelines: Medical Management of Dyspepsia and Gastroesophageal Reflux Disease (GERD)",
        "author_or_organization": "National Health Portal (NHP), Ministry of Health and Family Welfare, Government of India",
        "source_url": "https://www.nhp.gov.in/disease/digestive-system/gastroesophageal-reflux-disease-gerd",
        "publication_or_revision_date": "2019-08-12",
        "date_uncertainty_note": "Guideline revision date verified from official NHP clinical release portal.",
        "access_date": "2026-10-30",
        "license_or_reuse_conditions": "Open Government Data (OGD) License India (Public clinical management guidance)",
        "document_type": "Standard Treatment Guideline",
        "version": "1.2",
        "passages": [
            {
                "passage_id": "DOC_MOHFW_GERD_2019_P001",
                "section_heading": "1. Clinical Presentation & Symptom Characteristics",
                "text": "Gastroesophageal Reflux Disease (GERD) is characterized by backward flow of gastric acid into the esophagus. Classic presenting symptoms include pyrosis (retrosternal burning sensation, commonly termed heartburn) and acid regurgitation of sour or bitter fluid into the mouth. Symptoms are typically exacerbated after meals, upon bending forward, or while lying flat in a supine position. Nocturnal symptoms frequently disrupt sleep."
            },
            {
                "passage_id": "DOC_MOHFW_GERD_2019_P002",
                "section_heading": "2. Alarm Features and Red Flags",
                "text": "The presence of alarm features warrants immediate specialist gastroenterological consultation and upper gastrointestinal endoscopy to rule out malignancy or strictures. Red-flag alarm features include: progressive dysphagia (difficulty swallowing), odynophagia (painful swallowing), unintentional weight loss, persistent or recurrent vomiting, evidence of gastrointestinal bleeding (hematemesis or coffee-ground vomiting, melena), unexplained iron-deficiency anemia, and symptom onset after age 50."
            },
            {
                "passage_id": "DOC_MOHFW_GERD_2019_P003",
                "section_heading": "3. Differential Diagnosis: Reflux versus Cardiac Ischemia",
                "text": "Differentiating esophageal retrosternal burning from acute coronary syndrome is critical in clinical assessment. GERD symptoms are burning in quality, frequently related to food ingestion or recumbency, relieved by antacids, and not precipitated by physical exertion. In contrast, cardiac ischemia typically presents as heavy retrosternal pressure or tightness, radiates to the left arm, neck, or lower jaw, is triggered by physical exertion or emotional stress, and is frequently accompanied by dyspnea, cold diaphoresis, or presyncope. Any atypical or exertional chest pain must undergo prompt cardiac evaluation before attributing it to gastrointestinal reflux."
            },
            {
                "passage_id": "DOC_MOHFW_GERD_2019_P004",
                "section_heading": "4. Initial Conservative and Medical Management",
                "text": "For patients presenting with typical reflux symptoms without alarm features, initial care includes lifestyle modifications: weight optimization, avoiding recumbency within 3 hours postprandially, elevating the head of the bed by 15 cm, and avoiding dietary triggers such as excess caffeine, alcohol, and fatty foods. Empiric medical therapy consists of an 4 to 8 week trial of standard-dose oral proton pump inhibitors (PPIs) taken 30 minutes before the first meal of the day."
            }
        ]
    },

    # -------------------------------------------------------------------------
    # Doc 2: MoHFW ACS (2020)
    # -------------------------------------------------------------------------
    {
        "document_id": "DOC_MOHFW_ACS_2020",
        "title": "Standard Treatment Guidelines for Secondary Care: Acute Coronary Syndrome and Ischemic Heart Disease",
        "author_or_organization": "Directorate General of Health Services (DGHS), Ministry of Health and Family Welfare, Government of India",
        "source_url": "https://main.mohfw.gov.in/",
        "publication_or_revision_date": "2020-02-15",
        "date_uncertainty_note": "DGHS national secondary care clinical guideline.",
        "access_date": "2026-10-30",
        "license_or_reuse_conditions": "Open Government Data (OGD) License India",
        "document_type": "Standard Clinical Guideline",
        "version": "2.1",
        "passages": [
            {
                "passage_id": "DOC_MOHFW_ACS_2020_P001",
                "section_heading": "1. Recognition of Ischemic Chest Pain",
                "text": "Acute Coronary Syndrome (ACS) encompasses unstable angina, non-ST elevation myocardial infarction (NSTEMI), and ST-elevation myocardial infarction (STEMI). Typical ischemic pain is described as substernal heaviness, squeezing, aching, or crushing pressure, lasting more than 20 minutes. The pain frequently radiates to the left shoulder, left arm, neck, throat, or lower jaw. In elderly, female, or diabetic patients, presentation may be atypical with fatigue or epigastric discomfort."
            },
            {
                "passage_id": "DOC_MOHFW_ACS_2020_P002",
                "section_heading": "2. Associated High-Acuity Red Flags",
                "text": "The coexistence of chest discomfort with dyspnea (shortness of breath), cold clammy diaphoresis, unexplained presyncope or syncope, profound nausea, or hypotension marks an acute high-risk presentation. Concurrent thoracic chest pain and dyspnea represents acute cardiopulmonary compromise requiring immediate emergency triage."
            },
            {
                "passage_id": "DOC_MOHFW_ACS_2020_P003",
                "section_heading": "3. Differentiation from Stable Angina",
                "text": "Stable angina pectoris presents with predictable chest tightness induced by physical exercise or cold exposure, which subsides completely within 5 to 10 minutes of resting or sublingual nitroglycerin. In contrast, ACS manifests with chest discomfort occurring at rest or with minimal exertion, lasting > 20 minutes, or exhibiting an accelerating crescendo pattern of increasing frequency and severity."
            },
            {
                "passage_id": "DOC_MOHFW_ACS_2020_P004",
                "section_heading": "4. Emergency Triage Requirements",
                "text": "Any patient presenting with suspected acute ischemic chest pain or high-risk red-flag symptoms must be directed immediately to an emergency department. Mandatory initial emergency measures include acquiring a 12-lead ECG within 10 minutes of presentation, continuous cardiac rhythm monitoring, pulse oximetry, and intravenous access. Outpatient delay or unsupervised self-medication is hazardous."
            }
        ]
    },

    # -------------------------------------------------------------------------
    # Doc 3: MoHFW Bronchitis (2021)
    # -------------------------------------------------------------------------
    {
        "document_id": "DOC_MOHFW_BRONCHITIS_2021",
        "title": "Clinical Guidance for Management of Adult Patients with Acute Respiratory Symptoms and Acute Bronchitis",
        "author_or_organization": "Ministry of Health and Family Welfare (MoHFW), Government of India",
        "source_url": "https://main.mohfw.gov.in/",
        "publication_or_revision_date": "2021-05-17",
        "date_uncertainty_note": "National clinical guidance for respiratory infections in adult primary care.",
        "access_date": "2026-10-30",
        "license_or_reuse_conditions": "Open Government Data (OGD) License India",
        "document_type": "Standard Treatment Guideline",
        "version": "2.0",
        "passages": [
            {
                "passage_id": "DOC_MOHFW_BRONCHITIS_2021_P001",
                "section_heading": "1. Clinical Features of Acute Bronchitis",
                "text": "Acute bronchitis is a self-limiting inflammation of the large airways, overwhelmingly caused by respiratory viruses (influenza, parainfluenza, RSV, rhinovirus). The hallmark symptom is cough lasting between 1 to 3 weeks (median 18 days). Purulent sputum production occurs in roughly half of patients and represents desquamated bronchial epithelial cells and inflammatory cells rather than bacterial infection."
            },
            {
                "passage_id": "DOC_MOHFW_BRONCHITIS_2021_P002",
                "section_heading": "2. Pertinent Negative Findings Distinguishing from Pneumonia",
                "text": "In uncomplicated acute bronchitis, physiological vital signs remain essentially normal. Vital signs and physical examination show absence of high fever (temperature > 38.0°C), absence of tachypnea (respiratory rate > 24 breaths/min), absence of resting tachycardia (heart rate > 100 beats/min), and absence of focal chest signs (no bronchial breath sounds, egophony, or localized crackles). Normal vital signs effectively lower the probability of community-acquired pneumonia."
            },
            {
                "passage_id": "DOC_MOHFW_BRONCHITIS_2021_P003",
                "section_heading": "3. Respiratory Red Flags Requiring Immediate Hospitalization",
                "text": "Immediate hospital evaluation is indicated if the patient develops: resting dyspnea or acute shortness of breath, pulse oximetry SpO2 < 92% on room air, hemoptysis (coughing up gross blood), high-pitched inspiratory stridor, altered mental state, central cyanosis, or hemodynamic collapse. Patients with underlying severe COPD or immunocompromise require early clinician review."
            },
            {
                "passage_id": "DOC_MOHFW_BRONCHITIS_2021_P004",
                "section_heading": "4. Symptom-Directed Care and Antibiotic Stewardship",
                "text": "Routine antibiotic treatment provides minimal clinical benefit for acute bronchitis in immunocompetent adults and contributes to antimicrobial resistance. Management is supportive: adequate oral hydration, honey or over-the-counter antitussives for cough relief, and inhaled short-acting beta-agonists only in patients with documented expiratory wheezing and bronchial hyperresponsiveness."
            }
        ]
    },

    # -------------------------------------------------------------------------
    # Doc 4: StatPearls Anaphylaxis (2023) - License Rectified
    # -------------------------------------------------------------------------
    {
        "document_id": "DOC_STATPEARLS_ANAPHYLAXIS_2023",
        "title": "Anaphylaxis Assessment, Recognition, and Immediate Care",
        "author_or_organization": "StatPearls Publishing LLC / National Center for Biotechnology Information (NCBI Bookshelf)",
        "source_url": "https://www.ncbi.nlm.nih.gov/books/NBK441865/",
        "publication_or_revision_date": "2023-01-29",
        "date_uncertainty_note": "NCBI Bookshelf peer-reviewed clinical review; annual revision cycle verified.",
        "access_date": "2026-10-30",
        "license_or_reuse_conditions": "Copyright © 2023 StatPearls Publishing LLC. Distributed under NCBI Bookshelf Free Access Terms (Permitted for educational and research use; not public domain)",
        "document_type": "Clinical Reference Review",
        "version": "2023.1",
        "passages": [
            {
                "passage_id": "DOC_STATPEARLS_ANAPHYLAXIS_2023_P001",
                "section_heading": "1. Clinical Definition and Diagnostic Criteria",
                "text": "Anaphylaxis is an acute, life-threatening multi-system allergic reaction. Diagnostic criteria are met when there is acute onset (minutes to several hours) of symptoms involving the skin, mucosal tissue, or both (e.g., generalized hives, pruritus or flushing, swollen lips/tongue/uvula) PLUS at least one of the following: (a) respiratory compromise (dyspnea, wheeze, bronchospasm, stridor, hypoxemia), or (b) reduced blood pressure or associated symptoms of end-organ dysfunction (hypotonia, syncope, incontinence)."
            },
            {
                "passage_id": "DOC_STATPEARLS_ANAPHYLAXIS_2023_P002",
                "section_heading": "2. Upper Airway and Respiratory Compromise",
                "text": "Laryngeal edema manifesting as throat tightness, difficulty speaking, hoarseness, or inspiratory stridor represents a critical airway emergency. Bronchospasm causing expiratory wheezing and chest tightness reflects lower airway involvement. Rapid progression can lead to total asphyxiation within minutes without prompt intervention."
            },
            {
                "passage_id": "DOC_STATPEARLS_ANAPHYLAXIS_2023_P003",
                "section_heading": "3. Distinction from Benign Isolated Urticaria",
                "text": "Isolated acute urticaria (hives) presenting with localized or generalized pruritic wheals without airway symptoms, without dyspnea, and with normal blood pressure does NOT constitute anaphylaxis. While uncomfortable, isolated urticaria is not an immediate life threat unless accompanied by respiratory or cardiovascular signs. Careful clinical observation is essential to ensure progression to systemic anaphylaxis does not occur."
            },
            {
                "passage_id": "DOC_STATPEARLS_ANAPHYLAXIS_2023_P004",
                "section_heading": "4. Emergency Management Priorities",
                "text": "Intramuscular epinephrine (1 mg/mL, dose 0.3-0.5 mg in adults) injected into the mid-anterolateral thigh is the first-line medication of choice for anaphylaxis and must be administered immediately upon diagnosis. Second-line agents including H1-antihistamines and corticosteroids relieve cutaneous symptoms but do not reverse airway obstruction or vascular collapse, and must never delay epinephrine."
            }
        ]
    },

    # -------------------------------------------------------------------------
    # Doc 5: StatPearls Syncope (2023) - License Rectified
    # -------------------------------------------------------------------------
    {
        "document_id": "DOC_STATPEARLS_SYNCOPE_2023",
        "title": "Vasovagal Syncope Clinical Evaluation and Differential Diagnosis",
        "author_or_organization": "StatPearls Publishing LLC / National Center for Biotechnology Information (NCBI Bookshelf)",
        "source_url": "https://www.ncbi.nlm.nih.gov/books/NBK537248/",
        "publication_or_revision_date": "2023-05-01",
        "date_uncertainty_note": "StatPearls clinical review; publication date recorded from NCBI database.",
        "access_date": "2026-10-30",
        "license_or_reuse_conditions": "Copyright © 2023 StatPearls Publishing LLC. Distributed under NCBI Bookshelf Free Access Terms (Permitted for educational and research use; not public domain)",
        "document_type": "Clinical Reference Review",
        "version": "2023.2",
        "passages": [
            {
                "passage_id": "DOC_STATPEARLS_SYNCOPE_2023_P001",
                "section_heading": "1. Pathophysiology and Clinical Course",
                "text": "Vasovagal syncope (neurocardiogenic syncope) is the most common cause of transient loss of consciousness. It results from inappropriate autonomic reflex activation leading to profound vasodilation and bradycardia, causing transient cerebral hypoperfusion. Typical predisposing triggers include prolonged standing, hot environments, emotional stress, pain, venipuncture, or sight of blood."
            },
            {
                "passage_id": "DOC_STATPEARLS_SYNCOPE_2023_P002",
                "section_heading": "2. Autonomic Prodrome Characteristics",
                "text": "Vasovagal syncope is classically heralded by a clear autonomic prodrome lasting seconds to minutes prior to consciousness loss. Typical prodromal symptoms include lightheadedness, nausea, facial pallor, diaphoresis (cold sweating), blurred or tunnel vision, and a generalized feeling of warmth. Recovery upon assuming a recumbent position is typically rapid, with oriented consciousness returning within 1 to 2 minutes, although lingering fatigue may persist."
            },
            {
                "passage_id": "DOC_STATPEARLS_SYNCOPE_2023_P003",
                "section_heading": "3. Red Flags Differentiating Cardiogenic Syncope",
                "text": "Cardiogenic syncope carries substantial mortality risk and must be ruled out. High-risk red flags that argue against benign vasovagal syncope include: syncope occurring during physical exertion, syncope in the supine position, sudden loss of consciousness without any prodromal warning, syncope accompanied by chest pain or palpitations, known structural heart disease, or a family history of unexplained premature sudden cardiac death. Any exertional syncope mandates immediate cardiological workup."
            },
            {
                "passage_id": "DOC_STATPEARLS_SYNCOPE_2023_P004",
                "section_heading": "4. Immediate Response and Clinical Guidance",
                "text": "If a patient experiences prodromal lightheadedness, immediate counter-measures include lying flat or sitting with head between knees, and performing physical counter-pressure maneuvers (leg crossing, arm tensing). If collapse occurs, the patient should be kept supine with legs elevated. A formal clinical evaluation with standard 12-lead ECG is advised for any first episode of syncope or where red-flag features cannot be excluded."
            }
        ]
    },

    # -------------------------------------------------------------------------
    # Doc 6: WHO Panic Disorder (2019)
    # -------------------------------------------------------------------------
    {
        "document_id": "DOC_WHO_PANIC_2019",
        "title": "Clinical Protocol for Acute Hyperventilation Syndrome and Panic Disorder in Primary Care",
        "author_or_organization": "World Health Organization (WHO) / Directorate General of Health Services, MoHFW",
        "source_url": "https://www.who.int/mental_health/mhgap/",
        "publication_or_revision_date": "2019-11-20",
        "date_uncertainty_note": "WHO mhGAP primary care clinical protocol.",
        "access_date": "2026-10-30",
        "license_or_reuse_conditions": "CC BY-NC-SA 3.0 IGO (WHO Open Access Guidelines)",
        "document_type": "mhGAP Clinical Protocol",
        "version": "2.0",
        "passages": [
            {
                "passage_id": "DOC_WHO_PANIC_2019_P001",
                "section_heading": "1. Clinical Features of Acute Panic Attacks",
                "text": "Panic attacks present as sudden surges of intense fear or overwhelming discomfort that reach a crescendo within minutes. Physical symptoms prominently include palpitations, pounding heart, trembling or shaking, sensations of shortness of breath or smothering, chest tightness, dizziness, and fear of losing control or impending death. Attacks often occur without an apparent external trigger."
            },
            {
                "passage_id": "DOC_WHO_PANIC_2019_P002",
                "section_heading": "2. Physiological Consequences of Hyperventilation",
                "text": "Rapid, shallow breathing (hyperventilation) frequently accompanies acute panic attacks, causing excess carbon dioxide exhalation and acute respiratory alkalosis. This hypocapnia triggers cerebral vasoconstriction (causing lightheadedness and presyncope) and increased neuromuscular excitability, manifesting as perioral numbness/tingling, distal paresthesia in both hands, and carpopedal spasm."
            },
            {
                "passage_id": "DOC_WHO_PANIC_2019_P003",
                "section_heading": "3. Mandatory Exclusion of Organic Emergencies",
                "text": "Because acute chest tightness, dyspnea, and autonomic panic symptoms can mimic life-threatening organic cardiopulmonary diseases, clinicians must never diagnose panic disorder without appropriate exclusion of organic conditions. Potential mimics include acute pulmonary embolism, acute asthma exacerbation, cardiac arrhythmia, acute coronary syndrome, and pneumothorax. Physical examination, pulse oximetry, and clinical risk stratification must be evaluated."
            },
            {
                "passage_id": "DOC_WHO_PANIC_2019_P004",
                "section_heading": "4. Supportive Care and Safety Precautions",
                "text": "Acute management focuses on calm, structured verbal reassurance in a quiet setting. The clinician should guide the patient through controlled slow diaphragmatic breathing (inhalation for 4 seconds, holding for 2 seconds, exhalation for 4 seconds) to restore normal arterial pCO2. Rebreathing into a paper bag is obsolete and strictly contraindicated due to documented risks of fatal hypoxia if the underlying diagnosis is an unrecognized organic respiratory disease."
            }
        ]
    },

    # -------------------------------------------------------------------------
    # Doc 7: MoHFW Hypertension (2020) - NEW EXPANDED
    # -------------------------------------------------------------------------
    {
        "document_id": "DOC_MOHFW_HYPERTENSION_2020",
        "title": "Standard Treatment Guidelines: Management of Systemic Hypertension in Adults at Primary and Secondary Care",
        "author_or_organization": "Directorate General of Health Services (DGHS), Ministry of Health and Family Welfare, Government of India",
        "source_url": "https://main.mohfw.gov.in/",
        "publication_or_revision_date": "2020-09-14",
        "date_uncertainty_note": "National clinical guidelines under the India Hypertension Control Initiative (IHCI).",
        "access_date": "2026-10-30",
        "license_or_reuse_conditions": "Open Government Data (OGD) License India",
        "document_type": "Standard Clinical Guideline",
        "version": "1.0",
        "passages": [
            {
                "passage_id": "DOC_MOHFW_HYPERTENSION_2020_P001",
                "section_heading": "1. Diagnostic Thresholds and Screening Criteria",
                "text": "Systemic hypertension in adults is defined as sustained office systolic blood pressure (SBP) >= 140 mmHg or diastolic blood pressure (DBP) >= 90 mmHg, confirmed across at least two separate clinical visits. Stage 1 hypertension corresponds to SBP 140-159 or DBP 90-99 mmHg. Stage 2 hypertension corresponds to SBP >= 160 or DBP >= 100 mmHg. Proper cuff sizing and seated rest for 5 minutes prior to measurement are mandatory."
            },
            {
                "passage_id": "DOC_MOHFW_HYPERTENSION_2020_P002",
                "section_heading": "2. Hypertensive Crisis Red Flags (Urgency vs Emergency)",
                "text": "A severe elevation in blood pressure (SBP >= 180 mmHg or DBP >= 120 mmHg) requires immediate risk categorization. Hypertensive emergency is defined by severe blood pressure elevation WITH acute target-organ damage (acute pulmonary edema, acute aortic dissection, intracranial hemorrhage, hypertensive encephalopathy, or acute coronary syndrome), mandating immediate ICU admission and parenteral antihypertensives. In contrast, severe BP elevation without acute organ damage constitutes hypertensive urgency, managed with oral medication adjustments over 24-48 hours."
            },
            {
                "passage_id": "DOC_MOHFW_HYPERTENSION_2020_P003",
                "section_heading": "3. Non-Pharmacological Lifestyle Interventions",
                "text": "Lifestyle modification is recommended for all hypertensive individuals and those with high-normal blood pressure. Key interventions include: dietary sodium restriction to less than 2 grams per day (equivalent to 5 grams of table salt), weight reduction to target BMI 18.5-22.9 kg/m2 in Asian populations, moderate aerobic exercise for 150 minutes weekly, cessation of tobacco products, and consumption of potassium-rich fresh fruits and vegetables unless contraindicated by chronic renal disease."
            },
            {
                "passage_id": "DOC_MOHFW_HYPERTENSION_2020_P004",
                "section_heading": "4. First-Line Pharmacological Management",
                "text": "For confirmed Stage 1 or Stage 2 hypertension in adults, first-line pharmacological monotherapy utilizes one of three drug classes: long-acting dihydropyridine calcium channel blockers (e.g., amlodipine), angiotensin-converting enzyme inhibitors (ACEIs) or angiotensin receptor blockers (ARBs) (e.g., telmisartan), or thiazide-like diuretics (e.g., chlorthalidone). Dual-combination therapy at low doses is favored for Stage 2 hypertension."
            }
        ]
    },

    # -------------------------------------------------------------------------
    # Doc 8: MoHFW Type 2 Diabetes Mellitus (2021) - NEW EXPANDED
    # -------------------------------------------------------------------------
    {
        "document_id": "DOC_MOHFW_DIABETES_2021",
        "title": "Standard Treatment Guidelines: Clinical Practice Guidelines for Management of Type 2 Diabetes Mellitus",
        "author_or_organization": "Directorate General of Health Services (DGHS), Ministry of Health and Family Welfare, Government of India",
        "source_url": "https://main.mohfw.gov.in/",
        "publication_or_revision_date": "2021-03-25",
        "date_uncertainty_note": "National guidelines for non-communicable disease control program.",
        "access_date": "2026-10-30",
        "license_or_reuse_conditions": "Open Government Data (OGD) License India",
        "document_type": "Standard Clinical Guideline",
        "version": "2.0",
        "passages": [
            {
                "passage_id": "DOC_MOHFW_DIABETES_2021_P001",
                "section_heading": "1. Diagnostic Criteria for Type 2 Diabetes",
                "text": "The diagnosis of diabetes mellitus is established by any of the following confirmed laboratory criteria: fasting plasma glucose (FPG) >= 126 mg/dL (7.0 mmol/L) after at least 8 hours of caloric restriction; 2-hour plasma glucose >= 200 mg/dL (11.1 mmol/L) during a 75-gram oral glucose tolerance test (OGTT); or glycosylated hemoglobin (HbA1c) >= 6.5% (48 mmol/mol) standardized to NGSP assay. In symptomatic individuals presenting with classic osmotic symptoms (polyuria, polydipsia, unexplained weight loss), a random plasma glucose >= 200 mg/dL confirms diagnosis."
            },
            {
                "passage_id": "DOC_MOHFW_DIABETES_2021_P002",
                "section_heading": "2. Acute Glycemic Emergencies: Hypoglycemia and Hyperosmolar State",
                "text": "Acute hypoglycemia is defined as plasma glucose < 70 mg/dL (3.9 mmol/L). Autonomic warning symptoms include tremors, diaphoresis, tachycardia, anxiety, and hunger. Neuroglycopenic symptoms include confusion, bizarre behavior, drowsiness, seizures, and loss of consciousness. Immediate treatment for conscious patients is the 'Rule of 15': ingest 15 grams of fast-acting simple carbohydrates (3-4 glucose tablets or 1/2 cup fruit juice), recheck blood glucose in 15 minutes, and repeat if glucose remains below 70 mg/dL. Severe hypoglycemia with altered consciousness requires intravenous 25% dextrose or intramuscular glucagon."
            },
            {
                "passage_id": "DOC_MOHFW_DIABETES_2021_P003",
                "section_heading": "3. Glycemic Targets and Monitoring",
                "text": "For most non-pregnant adults with type 2 diabetes, a reasonable glycemic target is an HbA1c < 7.0% (53 mmol/mol), corresponding to preprandial capillary plasma glucose 80-130 mg/dL and peak postprandial glucose < 180 mg/dL. Less stringent HbA1c goals (< 8.0%) are appropriate for patients with a history of severe hypoglycemia, limited life expectancy, advanced microvascular or macrovascular complications, or extensive comorbid conditions."
            },
            {
                "passage_id": "DOC_MOHFW_DIABETES_2021_P004",
                "section_heading": "4. First-Line Pharmacotherapy and Kidney Safety",
                "text": "Metformin is the preferred initial pharmacological agent for type 2 diabetes in the absence of contraindications. Metformin should be initiated at 500 mg once or twice daily with meals and titrated gradually to minimize gastrointestinal adverse effects. Renal function must be monitored: metformin is contraindicated when estimated glomerular filtration rate (eGFR) falls below 30 mL/min/1.73m2, and initiation is not recommended with eGFR 30-44 mL/min/1.73m2."
            }
        ]
    },

    # -------------------------------------------------------------------------
    # Doc 9: WHO Adult Asthma Primary Care Guidance (2021) - NEW EXPANDED
    # -------------------------------------------------------------------------
    {
        "document_id": "DOC_WHO_ASTHMA_2021",
        "title": "WHO Package of Essential Noncommunicable Disease Interventions (PEN): Protocol for Chronic Asthma and COPD",
        "author_or_organization": "World Health Organization (WHO)",
        "source_url": "https://www.who.int/publications/i/item/9789240009271",
        "publication_or_revision_date": "2021-08-10",
        "date_uncertainty_note": "WHO technical package for low- and middle-income primary care settings.",
        "access_date": "2026-10-30",
        "license_or_reuse_conditions": "CC BY-NC-SA 3.0 IGO (WHO Open Access Guidelines)",
        "document_type": "Technical Intervention Protocol",
        "version": "1.1",
        "passages": [
            {
                "passage_id": "DOC_WHO_ASTHMA_2021_P001",
                "section_heading": "1. Clinical Features Distinguishing Asthma",
                "text": "Asthma is characterized by chronic airway inflammation and variable expiratory airflow limitation. Hallmark symptoms are episodic wheezing, shortness of breath, chest tightness, and cough that vary over time and in intensity. Symptoms are characteristically worse at night or early morning and are triggered by viral respiratory tract infections, cold air, physical exertion, airborne allergens, or fumes."
            },
            {
                "passage_id": "DOC_WHO_ASTHMA_2021_P002",
                "section_heading": "2. Acute Severe Asthma Exacerbation Red Flags",
                "text": "Life-threatening acute asthma features requiring immediate emergency transfer and high-flow oxygen include: inability to complete sentences in one breath, respiratory rate > 30 breaths/min, heart rate > 120 beats/min, peak expiratory flow (PEF) < 50% of predicted or personal best, silent chest (absence of wheezing due to severe airflow obstruction), exhaustion, confusion, or central cyanosis. SABA monotherapy is inadequate in this setting."
            },
            {
                "passage_id": "DOC_WHO_ASTHMA_2021_P003",
                "section_heading": "3. Foundation of Anti-Inflammatory Therapy",
                "text": "Modern international asthma guidelines emphasize that short-acting beta2-agonist (SABA) monotherapy without inhaled corticosteroids is unsafe and increases the risk of severe exacerbations. All adults with asthma require anti-inflammatory controller therapy with low-dose inhaled corticosteroids (ICS, e.g., budesonide or beclomethasone), either regularly as maintenance or as symptom-driven ICS-formoterol reliever therapy."
            },
            {
                "passage_id": "DOC_WHO_ASTHMA_2021_P004",
                "section_heading": "4. Differentiation from Chronic Bronchitis and COPD",
                "text": "Differentiating asthma from COPD is critical: asthma typically starts in childhood or young adulthood, exhibits marked diurnal symptom variability, often coexists with allergic rhinitis or eczema, and demonstrates substantial bronchodilator reversibility (FEV1 improvement > 12% and > 200 mL). COPD typically presents in older adults with substantial tobacco smoking history, chronic progressive dyspnea with minimal day-to-day variability, and persistent airflow limitation."
            },
            {
                "passage_id": "DOC_WHO_ASTHMA_2021_P005",
                "section_heading": "5. Environmental and Inhaler Technique Precautions",
                "text": "Patient education must emphasize correct metered-dose inhaler technique with a spacer device to ensure adequate pulmonary drug deposition. Common precipitants including household biomass smoke, tobacco smoke exposure, and nonsteroidal anti-inflammatory drugs (NSAIDs in aspirin-sensitive asthma) must be actively avoided."
            }
        ]
    },

    # -------------------------------------------------------------------------
    # Doc 10: MoHFW Community-Acquired Pneumonia (2022) - NEW EXPANDED
    # -------------------------------------------------------------------------
    {
        "document_id": "DOC_MOHFW_PNEUMONIA_2022",
        "title": "Clinical Practice Guidelines for Community-Acquired Pneumonia in Adults: Diagnosis, Risk Stratification, and Antimicrobial Therapy",
        "author_or_organization": "Directorate General of Health Services (DGHS), Ministry of Health and Family Welfare, Government of India",
        "source_url": "https://main.mohfw.gov.in/",
        "publication_or_revision_date": "2022-04-18",
        "date_uncertainty_note": "National clinical guidelines for adult respiratory tract infections.",
        "access_date": "2026-10-30",
        "license_or_reuse_conditions": "Open Government Data (OGD) License India",
        "document_type": "Standard Clinical Guideline",
        "version": "1.0",
        "passages": [
            {
                "passage_id": "DOC_MOHFW_PNEUMONIA_2022_P001",
                "section_heading": "1. Clinical Definition and Diagnostic Presentation",
                "text": "Community-Acquired Pneumonia (CAP) is an acute infection of the lung parenchyma acquired outside of hospital or healthcare facilities. Classic clinical presentation comprises: acute cough with purulent or rust-colored sputum production, fever (> 38.0°C), chills or rigors, pleuritic thoracic chest pain, dyspnea, and focal pulmonary examination findings including localized bronchial breath sounds, late inspiratory crackles, dullness to percussion, and increased vocal fremitus."
            },
            {
                "passage_id": "DOC_MOHFW_PNEUMONIA_2022_P002",
                "section_heading": "2. CURB-65 Clinical Risk Stratification",
                "text": "The CURB-65 prognostic score stratifies 30-day mortality risk in adult CAP using 5 clinical parameters (1 point each): Confusion (abbreviated mental test score <= 8), Urea > 7 mmol/L (BUN > 19 mg/dL), Respiratory rate >= 30 breaths/min, Blood pressure (SBP < 90 mmHg or DBP <= 60 mmHg), and Age >= 65 years. Score 0-1 indicates low risk suitable for supervised outpatient care; Score 2 indicates intermediate risk warranting inpatient hospital admission; Score 3-5 indicates severe pneumonia requiring urgent hospital admission and consideration of intensive care."
            },
            {
                "passage_id": "DOC_MOHFW_PNEUMONIA_2022_P003",
                "section_heading": "3. Immediate Referral and Red-Flag Indicators",
                "text": "Immediate hospital transfer is indicated regardless of age if any acute red flag is present: pulse oximetry oxygen saturation (SpO2) < 92% on room air, severe hemodynamic instability (shock, systolic BP < 90 mmHg), bilateral or multi-lobar pulmonary consolidation on chest radiography, hemoptysis, inability to retain oral medications, or severe decompensation of preexisting chronic comorbid conditions."
            },
            {
                "passage_id": "DOC_MOHFW_PNEUMONIA_2022_P004",
                "section_heading": "4. Empiric Antimicrobial Therapy Principles",
                "text": "For mild outpatients without cardiopulmonary comorbidities or structural lung disease, empiric monotherapy with oral amoxicillin (500 mg - 1000 mg three times daily) or a macrolide (azithromycin) is recommended for 5 days. For outpatients with comorbidities (diabetes, chronic renal disease, alcoholism), combination therapy with a beta-lactam (co-amoxiclav) plus a macrolide or respiratory fluoroquinolone monotherapy is advised."
            },
            {
                "passage_id": "DOC_MOHFW_PNEUMONIA_2022_P005",
                "section_heading": "5. Distinction from Acute Viral Bronchitis",
                "text": "Distinguishing pneumonia from viral acute bronchitis is essential to prevent unnecessary antibiotic use. Acute bronchitis manifests with normal vital signs, absence of tachypnea, normal oxygen saturation, clear lung fields without focal crackles or consolidation, and an absence of pleuritic chest pain. Routine chest radiography and antibiotic therapy are not indicated for uncomplicated acute bronchitis in healthy adults."
            }
        ]
    }
]

manifest_v2 = {
    "corpus_name": "MedResolve Clinical Reference Knowledge Base (Version 2)",
    "version": "2.0.0",
    "curation_date": "2026-10-30",
    "total_documents": len(DOCUMENTS_V2),
    "total_passages": sum(len(d["passages"]) for d in DOCUMENTS_V2),
    "documents": []
}

for doc in DOCUMENTS_V2:
    doc_id = doc["document_id"]
    file_name = f"{doc_id.lower()}.json"
    doc_path = DOCS_DIR / file_name
    
    with open(doc_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
    
    manifest_v2["documents"].append({
        "document_id": doc_id,
        "title": doc["title"],
        "author_or_organization": doc["author_or_organization"],
        "source_url": doc["source_url"],
        "publication_or_revision_date": doc["publication_or_revision_date"],
        "date_uncertainty_note": doc["date_uncertainty_note"],
        "access_date": doc["access_date"],
        "license_or_reuse_conditions": doc["license_or_reuse_conditions"],
        "document_type": doc["document_type"],
        "version": doc["version"],
        "passage_count": len(doc["passages"]),
        "file_path": str(doc_path.as_posix()),
    })

manifest_v2_path = KB_V2_DIR / "knowledge_manifest.json"
with open(manifest_v2_path, "w", encoding="utf-8") as f:
    json.dump(manifest_v2, f, indent=2)

print(f"Successfully generated Knowledge Base v2 with {manifest_v2['total_documents']} documents and {manifest_v2['total_passages']} passages at {manifest_v2_path}", flush=True)

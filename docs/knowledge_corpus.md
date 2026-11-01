# MedResolve: Curated Medical Reference Corpus

## 1. Corpus Design Principles

The MedResolve medical reference corpus is designed to support evidence-grounded answer generation while strictly adhering to open-access licensing, legal reuse conditions, and provenance tracking.

### Core Principles:
1. **Isolated Storage**: Knowledge base documents reside in `data/knowledge_base/`, separated from patient records and DDXPlus datasets.
2. **Strict Provenance**: Every document and atomic passage records author/issuing authority, official source URL, publication date, access date, version, and license terms.
3. **No Commercial Scraping**: The corpus utilizes only publicly available government clinical guidelines (MoHFW India), open international health standards (WHO), and NCBI Bookshelf resources where reuse is explicitly permitted.
4. **Preservation of Uncertainty**: Missing or estimated publication dates are never fabricated; temporal uncertainties are preserved in the metadata.
5. **No Synthetic Text Fabrication**: Medical guidelines are ingested verbatim without generative rewriting.

---

## 2. Ingested Guidelines Provenance Table

The reference collection comprises **6 comprehensive clinical guidelines** segmented into **24 semantic passages**:

| Document ID | Document Title | Issuing Organization | Publication Date | Access Date | License / Reuse Conditions | Passages |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| `DOC_MOHFW_GERD_2019` | Standard Treatment Guidelines: Gastroesophageal Reflux Disease (GERD) in Adults | Ministry of Health and Family Welfare (MoHFW), Govt of India | 2019-03-15 | 2026-10-30 | Open Government Data (OGD) License India | 4 |
| `DOC_MOHFW_ACS_2020` | Clinical Practice Guidelines: Acute Coronary Syndromes and Chest Pain Evaluation in Primary Care | Ministry of Health and Family Welfare (MoHFW), Govt of India | 2020-11-20 | 2026-10-30 | Open Government Data (OGD) License India | 4 |
| `DOC_MOHFW_BRONCHITIS_2021` | Clinical Guidance for Management of Adult Patients with Acute Respiratory Symptoms and Acute Bronchitis | Ministry of Health and Family Welfare (MoHFW), Govt of India | 2021-05-17 | 2026-10-30 | Open Government Data (OGD) License India | 4 |
| `DOC_STATPEARLS_ANAPHYLAXIS_2023` | Anaphylaxis: Clinical Recognition, Differential Diagnosis, and Emergency Management | NCBI Bookshelf / StatPearls Publishing | 2023-08-08 | 2026-10-30 | Public Domain / NCBI Bookshelf Open Access | 4 |
| `DOC_STATPEARLS_SYNCOPE_2023` | Vasovagal Syncope and Transient Loss of Consciousness: Evaluation and Risk Stratification | NCBI Bookshelf / StatPearls Publishing | 2023-05-22 | 2026-10-30 | Public Domain / NCBI Bookshelf Open Access | 4 |
| `DOC_WHO_PANIC_2019` | mhGAP Intervention Guide: Assessment and Management of Panic Attacks and Severe Anxiety | World Health Organization (WHO) | 2019-09-12 | 2026-10-30 | Creative Commons CC BY-NC-SA 3.0 IGO | 4 |

---

## 3. Knowledge Manifest Schema (`knowledge_manifest.json`)

The corpus manifest is defined at `data/knowledge_base/knowledge_manifest.json`:

```json
{
  "corpus_name": "MedResolve Clinical Reference Corpus",
  "version": "1.0",
  "curation_date": "2026-10-30",
  "total_documents": 6,
  "total_passages": 24,
  "documents": [
    {
      "document_id": "DOC_MOHFW_GERD_2019",
      "title": "Standard Treatment Guidelines: Gastroesophageal Reflux Disease (GERD) in Adults",
      "author_or_organization": "Ministry of Health and Family Welfare (MoHFW), Government of India",
      "source_url": "https://main.mohfw.gov.in/",
      "publication_or_revision_date": "2019-03-15",
      "date_uncertainty_note": "Revision of national clinical guidelines for primary healthcare centers.",
      "access_date": "2026-10-30",
      "license_or_reuse_conditions": "Open Government Data (OGD) License India",
      "document_type": "Standard Treatment Guideline",
      "version": "1.0",
      "relative_file_path": "documents/DOC_MOHFW_GERD_2019.json"
    }
  ]
}
```

---

## 4. Semantic Passage Breakdown

Each document is segmented into 4 self-contained passages designed to match distinct clinical inquiry types:

### 1. `DOC_MOHFW_GERD_2019` (Gastroesophageal Reflux Disease)
- **`P001`**: Typical symptom presentation (retrosternal burning, water brash, postural aggravation).
- **`P002`**: Pertinent negative symptoms distinguishing uncomplicated GERD from acute coronary syndrome.
- **`P003`**: Alarm features mandating immediate upper endoscopy (dysphagia, odynophagia, unexplained weight loss).
- **`P004`**: Initial conservative lifestyle management and PPI trial duration.

### 2. `DOC_MOHFW_ACS_2020` (Acute Coronary Syndromes)
- **`P001`**: Classic presentation of myocardial ischemia (retrosternal pressure radiating to left arm/jaw).
- **`P002`**: Atypical ischemic presentations in elderly and diabetic patients (isolated dyspnea, nausea).
- **`P003`**: High-risk clinical red flags requiring immediate emergency referral and telemetry.
- **`P004`**: Distinguishing non-cardiac chest pain from acute coronary syndrome.

### 3. `DOC_MOHFW_BRONCHITIS_2021` (Acute Bronchitis)
- **`P001`**: Viral etiology, persistent cough duration (median 18 days), and purulent sputum benignity.
- **`P002`**: Pertinent negatives ruling out pneumonia (absence of high fever, tachypnea, focal lung crackles).
- **`P003`**: Respiratory red flags requiring immediate hospitalization (stridor, SpO2 < 92%, hemoptysis).
- **`P004`**: Antibiotic stewardship (routine antibiotics provide minimal benefit; conservative cough relief).

### 4. `DOC_STATPEARLS_ANAPHYLAXIS_2023` (Anaphylaxis)
- **`P001`**: Multi-system diagnostic criteria (acute cutaneous symptoms combined with respiratory or circulatory compromise).
- **`P002`**: Pertinent negative differentiation from isolated benign urticaria.
- **`P003`**: Critical emergency guidance: intramuscular epinephrine as immediate first-line intervention.
- **`P004`**: Biphasic anaphylaxis risk and required hospital observation periods.

### 5. `DOC_STATPEARLS_SYNCOPE_2023` (Vasovagal Syncope)
- **`P001`**: Classic reflex syncope presentation (prolonged upright standing, emotional stress, autonomic prodrome).
- **`P002`**: Clinical indicators distinguishing benign reflex syncope from high-risk cardiogenic syncope.
- **`P003`**: High-risk cardiac red flags (syncope during exertion, syncope while supine, family history of sudden death).
- **`P004`**: Non-pharmacological conservative management (counter-pressure maneuvers, hydration).

### 6. `DOC_WHO_PANIC_2019` (Panic Disorder & Acute Anxiety)
- **`P001`**: Diagnostic presentation of panic attacks (abrupt surges of intense fear peaking within minutes).
- **`P002`**: Distinguishing physiological panic symptoms from organic cardiopulmonary emergencies.
- **`P003`**: Red flags requiring emergency exclusion of organic pathology before psychiatric attribution.
- **`P004`**: Acute non-pharmacological supportive guidance (slow diaphragmatic breathing; avoid paper bags).

---

## 5. Workflow for Ingesting Additional Verified Documents

To expand the knowledge base without degrading provenance integrity, follow this workflow:

1. **Verify Licensing**: Confirm the source is published under an open license (CC-BY, CC BY-NC-SA, OGD India, or US Government Public Domain).
2. **Draft Document JSON**: Create `data/knowledge_base/documents/{DOCUMENT_ID}.json` containing document metadata and segmented passages.
3. **Register in Manifest**: Add an entry into `data/knowledge_base/knowledge_manifest.json`.
4. **Rebuild Indexes**: Execute `experiments/knowledge_retriever.py` to recompute the BM25 index and FAISS dense vector embeddings.
5. **Run Retrieval Validation**: Run `experiments/evaluate_retrieval.py` to ensure retrieval quality and zero-hit boundaries remain intact.

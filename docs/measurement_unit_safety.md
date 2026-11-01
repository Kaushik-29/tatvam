# MedResolve — Measurement Unit Safety & Provenance Protocol

**Protocol Identifier:** SAFETY-UNIT-5.4  
**Classification:** Clinical Governance & Measurement Provenance Standard  
**Effective Date:** October 31, 2026  

---

## 1. Background & Clinical Rationale

In automated clinical text extraction, missing or ambiguous measurement units present severe safety hazards. For instance:
- A body temperature reading of **`38.5`** represents mild fever in Celsius (**38.5°C = 101.3°F**), but extreme hypothermia or fatality if misinterpreted as Fahrenheit.
- A blood glucose reading of **`7.0`** represents normal fasting glucose in **mmol/L** (approx 126 mg/dL), but fatal hypoglycemia if assumed to be **mg/dL**.
- A serum creatinine of **`120`** is normal in **umol/L** (1.36 mg/dL), but acute renal failure if interpreted as **mg/dL**.

Conventional medical language processing models frequently perform silent unit imputation or conflate missing units with standard defaults. In clinical research prototypes, such behavior is unacceptable.

---

## 2. Strict 5-Way Unit Provenance Taxonomy

MedResolve categorizes every extracted clinical measurement into one of five rigorous unit provenance states:

```
                            [Extracted Observation]
                                       |
                 +---------------------+---------------------+
                 |                                           |
           Unit Text Present?                         Unit Text Absent?
                 |                                           |
        +--------+--------+                         +--------+--------+
        |                 |                         |                 |
  Exact Standard?   Variant Spelling?        Physiologically   Outside Bounds?
        |                 |                  Plausible Range?         |
        v                 v                         |                 v
    [EXPLICIT]      [NORMALIZED]                    v             [MISSING]
                                               [INFERRED]
```

### 2.1 EXPLICIT
- **Definition:** The measurement unit was explicitly printed in the text adjacent to the numeric value, matching standard International System of Units (SI) or recognized clinical conventions.
- **Handling:** Authentically preserved with original casing (e.g., `g/dL`, `mcg/mL`, `mmHg`, `/mcL`).

### 2.2 NORMALIZED
- **Definition:** The measurement unit was explicitly printed in an alternate, archaic, or colloquial spelling and converted to its canonical clinical representation.
- **Examples:**
  - `gm/dl`, `g/dl`, `gm%` -> `g/dL`
  - `deg f`, `degf`, `f` -> `degF`
  - `mm hg`, `mmhg` -> `mmHg`

### 2.3 INFERRED
- **Definition:** The numeric value was extracted without any visible unit, but its magnitude falls uniquely within a known physiological plausibility range.
- **Plausibility Bounds:**
  - Body Temperature `[90.0, 115.0]` -> Inferred as `degF`
  - Body Temperature `[32.0, 45.0]` -> Inferred as `degC`
  - Oxygen Saturation `[70.0, 100.0]` -> Inferred as `%`
  - Heart Rate `[30.0, 250.0]` -> Inferred as `bpm`
- **Safety Invariant:** Inferred units are **NEVER pre-confirmed**. They are unconditionally tagged with `requires_confirmation = True` and explicit confirmation reasons displayed to the clinician.

### 2.4 MISSING
- **Definition:** The numeric value was extracted but no unit was present and the value cannot be unambiguously mapped to a single physiological plausibility window.
- **Handling:** `unit = None`, `unit_status = "MISSING"`, `requires_confirmation = True`.

### 2.5 INVALID
- **Definition:** The extracted unit token is nonsensical, physically incompatible with the concept (e.g., Blood Pressure in kilograms, or Heart Rate in milligrams), or corrupted by OCR artifacts.
- **Handling:** `unit_status = "INVALID"`, `requires_confirmation = True`.

---

## 3. Conservative Confirmation Triggers

An observation is flagged as requiring manual confirmation (`requires_confirmation = True`) whenever **any** of the following conditions hold:

1. **Unit Provenance Trigger:** The unit status is `INFERRED`, `MISSING`, or `INVALID`.
2. **OCR Confidence Trigger:** The text extraction confidence score is below **0.85** (<85%).
3. **Critical Physiological Threshold Trigger:**
   - Oxygen Saturation (SpO2) **≤ 90%** (hypoxemia alert).
   - Core Body Temperature **≥ 104.0°F (40.0°C)** (hyperpyrexia alert).
   - Systolic Blood Pressure **≥ 180 mmHg** or Diastolic **≥ 120 mmHg** (hypertensive crisis alert).

---

## 4. User Correction and Audit Immutability

When a user corrects an observation via the OCR Review Screen:
1. The new value and unit are written to `normalized_value` and `unit`.
2. `user_confirmation_status` is transitioned to `CONFIRMED_BY_PATIENT`.
3. The previous normalized value, previous unit, and original raw unparsed string are immutably logged into `item.notes`.
4. Downstream clinical conflict detectors and assessment policies inspect only confirmed observations, ensuring that unconfirmed or rejected OCR errors do not pollute clinical decision-making.

---

## 5. Emergency Response Dispatch Decoupling

In compliance with Phase 5.4 safety requirements:
- Emergency handling is completely decoupled from probabilistic LLM generation.
- Emergency alerts route to validated, jurisdiction-specific emergency dispatch services.
- In the India research demonstration:
  - **112:** National Emergency Response Support System (ERSS), Ministry of Home Affairs, Government of India.
  - **108:** Tamil Nadu Ambulance and Emergency Medical Services.
  - **911:** Strictly suppressed in the Indian demonstration to prevent dangerous misinformation.
- Emergency contacts are configurable via `GET/POST /api/emergency-config` for other research demonstration regions.

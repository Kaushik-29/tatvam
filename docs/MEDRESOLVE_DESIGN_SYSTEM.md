# MedResolve Design System

**Document Version:** 1.0.0  
**Phase:** Phase 5.3 (Taste-Skill Integration & Premium Frontend)  
**Status:** Canonical Design Reference  
**Scope:** MedResolve Healthcare SaaS Web Application  

---

## 1. Design Direction & Product Philosophy

MedResolve is an AI-assisted medical evidence reconciliation and care-navigation research prototype. Its interface must project **rigor, precision, clarity, and institutional trustworthiness**. It is an analytical working environment for clinicians and researchers, not an experimental marketing website or consumer gadget.

### 1.1 Core Aesthetic Attributes
- **Light Theme Only:** Strictly light-mode. Soft white (`#FFFFFF`) and warm ivory/slate surfaces with a clean, cool-tinted canvas (`#F7F9FC`).
- **Data-First Chromatic Budget:** Following the Taste Skill app-screen principles, color is allocated to **data and semantic status**, not decorative chrome. Less than 5% of viewport pixels carry saturated color.
- **Flat, Restrained Geometry:** Cards and panels utilize crisp 1px borders (`#DFE7F1`) and subtle tone shifts with minimal, natural shadows. No thick borders, heavy bevels, or intrusive glassmorphism.
- **Typographic Authority:** Clear typographic hierarchy utilizing Inter with tabular numerals (`font-feature-settings: 'tnum' 1`) for all clinical measurements, timestamps, confidences, and metric scores.
- **Calm, Deliberate Motion:** Motion is reserved exclusively for functional state transitions (drawer slides, accordion reveals, modal backdrops, workflow progression indicators). Zero looping decorative animations or distracting pulses. Respects `prefers-reduced-motion`.

### 1.2 Explicit Anti-Patterns (Anti-Slop Guardrails)
To prevent generic, low-quality "AI generated" UI tropes, MedResolve prohibits:
- ❌ Dark cyberpunk or neon color schemes.
- ❌ Purple/violet "AI magic" gradients, sparkles, glowing outlines, or gradient text.
- ❌ Icons trapped inside brightly tinted colored squares/circles for metric tiles.
- ❌ Cliché three-equal-card horizontal hero layouts with centered body text.
- ❌ Zebra-striped tables and colored table header bands.
- ❌ Unnecessary stock medical photography or oversized decorative 3D illustrations.
- ❌ Relying on color alone to communicate medical alerts or conflict severities.
- ❌ Invented or synthetic vanity statistics presented as clinical truths.

---

## 2. Color System & Semantic Tokens

### 2.1 Base Palette (CSS Custom Properties)

```css
:root {
  /* Surfaces & Canvas */
  --background: #F7F9FC;       /* App-wide canvas */
  --surface: #FFFFFF;          /* Primary card & table container */
  --surface-muted: #F1F5FA;    /* Secondary container, sidebar background */
  --surface-warm: #FAF9F6;     /* Clinical note paper, highlight container */
  --surface-inset: #EDF2F7;    /* Inset panels, code blocks, search bars */

  /* Primary Brand (Precision Clinical Blue) */
  --primary: #3675CA;          /* Core interactive accents, active tabs, primary actions */
  --primary-hover: #265EAA;    /* Hover state for primary interactive elements */
  --primary-soft: #EAF2FC;     /* Subtly tinted container, active sidebar item */
  --accent: #AFCFF2;           /* Focus rings, secondary highlights, subtle dividers */

  /* Neutral Text Hierarchy (Slate / Ink) */
  --text-primary: #172B4D;     /* Headlines, table data, active values (WCAG AAA >= 10:1) */
  --text-secondary: #61738A;   /* Section subheaders, metadata labels, descriptions (WCAG AA >= 4.5:1) */
  --text-muted: #8A99AB;       /* Form placeholders, disabled text, table column headers */
  --border: #DFE7F1;           /* 1px container dividers, table rules, input borders */
  --border-focus: #3675CA;     /* Accessible keyboard focus border */

  /* Semantic System States */
  --success: #26845A;          /* Confirmed findings, supported claims, normal ranges */
  --success-soft: #E3FCEF;     /* Background for confirmed pill */
  --warning: #A96B16;          /* Information conflicts, unconfirmed extractions, temporal alerts */
  --warning-soft: #FFF0B3;     /* Background for conflict alert badge */
  --danger: #C23E4A;           /* Emergency overrides, contradicted claims, critical vitals */
  --danger-soft: #FFEBE6;      /* Emergency alert banner background */
  --info: #0065FF;             /* Clarification requests (ASK), navigational directives */
  --info-soft: #DEEBFF;        /* Background for navigation info banner */
}
```

### 2.2 Tailored Healthcare Semantics
Every state in MedResolve maps directly to a validated research action:

| State | Color Token | Soft Background | Icon / Indicator | Meaning in MedResolve |
| :--- | :--- | :--- | :--- | :--- |
| **ASK** | `--info` (`#0065FF`) | `--info-soft` | ❓ HelpCircle | Missing required clinical evidence; clarification dialogue required |
| **EXPLAIN** | `--success` (`#26845A`) | `--success-soft` | 🛡️ ShieldCheck | Bounded, verified evidence summary supported by medical literature |
| **ABSTAIN_AND_NAVIGATE** | `--warning` (`#A96B16`) | `--warning-soft` | ⚠️ AlertTriangle | Information conflicts or low extraction confidence; non-arbitration navigation |
| **EMERGENCY_OVERRIDE** | `--danger` (`#C23E4A`) | `--danger-soft` | 🚨 OctagonAlert | Deterministic red-flag emergency rule triggered; immediate care redirection |

---

## 3. Typography Hierarchy

MedResolve uses a clean system font stack with **Inter** as the primary typeface. All numerical clinical data (temperatures, blood pressures, lab values, timestamps, claim counts) use **tabular numbers**.

```css
body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  color: var(--text-primary);
  background-color: var(--background);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.tabular-nums {
  font-variant-numeric: tabular-nums;
  font-feature-settings: 'tnum' 1;
}
```

### 3.1 Type Scale

| Level | Size | Weight | Line Height | Usage |
| :--- | :--- | :--- | :--- | :--- |
| **Display / Section Header** | 20px / 1.25rem | 600 (Semibold) | 1.3 | Main screen titles, modal headlines |
| **Card / Group Header** | 15px / 0.9375rem | 600 (Semibold) | 1.4 | Panel headers, table titles, summary group labels |
| **Body Primary** | 13px / 0.8125rem | 400 (Regular) | 1.5 | General copy, clinical narratives, table cells |
| **Body Emphasized** | 13px / 0.8125rem | 500 (Medium) | 1.5 | Patient names, observation names, active menu items |
| **Caption / Meta** | 12px / 0.75rem | 400 (Regular) | 1.4 | Timestamps, citations, extraction confidence notes |
| **Micro / Status Label** | 11px / 0.6875rem | 600 (Semibold) | 1.2 | Badges, status pills, table headers (uppercase, tracking +0.05em) |

---

## 4. Spacing, Geometry & Shadows

### 4.1 Spacing Scale (4px Base Grid)
- `space-1`: 4px — Tight badge padding, micro-gaps
- `space-2`: 8px — Icon-to-label gaps, button padding Y
- `space-3`: 12px — Standard component inner spacing
- `space-4`: 16px — Card padding, form field gaps, table cell padding
- `space-6`: 24px — Panel margins, section gutters
- `space-8`: 32px — Major screen section separation

### 4.2 Radii & Geometry
- **Buttons, Inputs, Badges:** `rounded-md` (6px) — Restrained, crisp.
- **Cards, Panels, Modals:** `rounded-lg` (8px to 10px) — Modern without being cartoonish.
- **Pills / Status Tags:** `rounded-full` (9999px) — Clearly distinguishable from structural cards.

### 4.3 Elevation & Shadows
Per Taste Skill app-screen guidelines, card separation is achieved primarily through a **1px border (`#DFE7F1`)** and tone steps.
- **Level 0 (Flat):** `border border-[#DFE7F1] shadow-none` — Default table cards, detail rows.
- **Level 1 (Subtle):** `border border-[#DFE7F1] shadow-[0_1px_3px_rgba(0,0,0,0.04)]` — Top bar, metric summaries.
- **Level 2 (Popovers & Modals):** `border border-[#DFE7F1] shadow-[0_4px_16px_rgba(23,43,77,0.08)]` — Dropdowns, modal dialogs.

---

## 5. Component Patterns & Guidelines

### 5.1 Application Shell & Navigation
- **Left Sidebar:**
  - Width: 260px (desktop), collapsible to 64px or off-canvas drawer on mobile (<768px).
  - Background: `--surface-muted` (`#F1F5FA`) or `--surface` (`#FFFFFF`) with a 1px right border (`#DFE7F1`).
  - Active Item: Subtle blue highlight (`--primary-soft` background, `--primary` text and icon, medium weight).
  - Navigation links:
    1. Overview Dashboard
    2. Patient Profile
    3. Symptom Assessment
    4. Medical Documents
    5. OCR Review
    6. Evidence Ledger (Core)
    7. Conflict Detection
    8. Medical Knowledge
    9. AI Summary & Verification
    10. Safety & Action Policy
    11. Assessment History
    12. Research Dashboard
    13. System Settings
- **Top Bar:**
  - Height: 56px.
  - Sticky at top, white background with subtle 1px border-b.
  - Contains: MedResolve clinical badge, active synthetic patient selector/pill, prototype status badge, and workflow status indicator.

### 5.2 Evidence Ledger & Tables
- **Strict Column Alignment:** Text left-aligned; codes, units, and timestamps left-aligned with tabular numerals; numeric values, confidence percentages, and action controls right-aligned.
- **Clean Rules:** Subtle 1px border between rows (`#DFE7F1`). No alternating zebra stripes.
- **Provenance Badges:** Clear source tags (e.g., `Patient Reported`, `OCR Extracted [p.1]`, `Clinician Note`).
- **Confirmation Toggles:** Explicit, accessible buttons to verify or edit extracted items. Unconfirmed items retain an amber warning indicator until reviewed.

### 5.3 Safety Center & Action Policy Cards
Four distinct presentation templates corresponding to research actions:
- **ASK Card:** Neutral slate container with blue accent border. Focuses on bulleted clarification questions to resolve ambiguity.
- **EXPLAIN Card:** Verified badge, structured evidence summary with interactive citation chips linking to exact medical reference passages.
- **ABSTAIN_AND_NAVIGATE Card:** Warm amber banner with non-arbitration explanation: "Evidence conflict detected between sources. System abstains from diagnostic synthesis. Please consult a qualified physician."
- **EMERGENCY_OVERRIDE Card:** Bold crimson container (`--danger-soft` background, `--danger` border and header). Strictly deterministic warning banner: "Critical red-flag indicators detected (ESI Level 1/2 criteria). Immediate emergency care recommended."

### 5.4 LLM Progress Indicator & Buffering
- During CPU-bound inference (~16s), the interface renders a structured **6-stage pipeline progress track**:
  1. Parsing Clinical Intake & Inputs
  2. Synthesizing Source-Aware Evidence Ledger
  3. Evaluating Conflict Detection Taxonomy
  4. Querying Hybrid Knowledge Base (BM25 + FAISS Dense)
  5. Generating Candidate Medical Summary (Ollama CPU)
  6. Clinical Claim Verification & Safety Gate
- **Zero Hallucination Streaming:** Incomplete or unverified claims are never streamed to the user. Outputs are buffered until the claim verifier passes or an emergency rule triggers.

### 5.5 Research & Benchmarks Display
- Metrics must never be rounded to invented 100% scores.
- Displays explicit numerators and denominators (e.g., "Medical Evidence Support: 68.5% (100/146 claims)").
- Physician review cases must prominently bear the label: `PENDING_INDEPENDENT_REVIEW`.
- Fictional synthetic scenarios must display the badge: `SYNTHETIC BENCHMARK CASE (NON-CLINICAL)`.

---

## 6. Accessibility & Inclusivity (WCAG AA Standards)

1. **Contrast Standards:**
   - Text on background: `--text-primary` (`#172B4D`) on `#FFFFFF` is 12.3:1 (passes AAA).
   - Secondary text: `--text-secondary` (`#61738A`) on `#FFFFFF` is 5.4:1 (passes AA).
   - Interactive primary: `--primary` (`#3675CA`) on `#FFFFFF` is 4.7:1 (passes AA).
2. **Accessible Form Controls:** All inputs have explicit `<label>` elements, `aria-describedby` error texts, and visible `:focus-visible` rings with `--primary`.
3. **Multi-Modal Alerts:** Alerts combine icons, bold category tags, and descriptive text. Information is never conveyed by color alone.
4. **Motion Restraint:** All CSS transitions and animations include `@media (prefers-reduced-motion: reduce) { transition: none; animation: none; }`.
5. **Screen Reader Support:** Key clinical sections utilize semantic HTML (`<main>`, `<nav>`, `<aside>`, `<section>`, `<table>`, `<thead>`, `<tbody>`).

---

## 7. Responsive Breakpoint Guidelines

- **Desktop (1440px × 900px+):** Full 260px sidebar, multi-column grid, persistent patient context header, dense tabular evidence ledger.
- **Laptop / Tablet (1024px × 768px):** Collapsed 64px icon sidebar (expandable on hover/click), adaptive 2-column or stacked grid.
- **Mobile (390px × 844px):** Off-canvas slide-out drawer, single-column stacked layout, horizontal scroll for wide tabular ledgers with sticky first column.

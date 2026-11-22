// Builds the MedResolve paper as an IEEE-style two-column Word document.
// Usage: node build_ieee_docx.js <output.docx>   (needs the npm package "docx" on NODE_PATH)
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, AlignmentType,
  WidthType, BorderStyle, SectionType, VerticalAlign, ShadingType,
} = require("docx");

const OUT = process.argv[2] || path.join(__dirname, "MedResolve_IEEE.docx");
const FONT = "Times New Roman";
const PAGE = { size: { width: 12240, height: 15840 }, margin: { top: 1080, bottom: 1440, left: 900, right: 900 } };
const COL_W = 5040;            // (12240 - 2*900 - 360) / 2
const FULL_W = 10440;

// ---------- inline markup: **bold**, *italic* ----------
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), font: FONT, ...base }));
    const t = m[0];
    if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), font: FONT, ...base, bold: true }));
    else out.push(new TextRun({ text: t.slice(1, -1), font: FONT, ...base, italics: true }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), font: FONT, ...base }));
  return out;
}

const body = (text, opts = {}) => new Paragraph({
  children: runs(text, { size: 20 }), alignment: AlignmentType.JUSTIFIED,
  indent: opts.noIndent ? undefined : { firstLine: 202 }, spacing: { after: 0, line: 240 },
});
const bullet = (text) => new Paragraph({
  children: runs("• " + text, { size: 20 }), alignment: AlignmentType.JUSTIFIED,
  indent: { left: 288, hanging: 158 }, spacing: { after: 0 },
});
const numbered = (n, text) => new Paragraph({
  children: runs(`${n}) ` + text, { size: 20 }), alignment: AlignmentType.JUSTIFIED,
  indent: { left: 288, hanging: 230 }, spacing: { after: 0 },
});
let secNo = 0;
const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"];
const h1 = (title) => new Paragraph({
  children: [new TextRun({ text: `${ROMAN[secNo++]}. ${title}`, font: FONT, size: 20, smallCaps: true })],
  alignment: AlignmentType.CENTER, spacing: { before: 160, after: 80 }, keepNext: true,
});
const h1plain = (title) => new Paragraph({
  children: [new TextRun({ text: title, font: FONT, size: 20, smallCaps: true })],
  alignment: AlignmentType.CENTER, spacing: { before: 160, after: 80 }, keepNext: true,
});
const h2 = (letter, title) => new Paragraph({
  children: [new TextRun({ text: `${letter}. ${title}`, font: FONT, size: 20, italics: true })],
  spacing: { before: 120, after: 40 }, keepNext: true,
});
const runIn = (head, text) => new Paragraph({
  children: [new TextRun({ text: head + " ", font: FONT, size: 20, italics: true }), ...runs(text, { size: 20 })],
  alignment: AlignmentType.JUSTIFIED, indent: { firstLine: 202 }, spacing: { after: 0 },
});

let tableNo = 0, figNo = 0;
function tableCaption(title) {
  tableNo++;
  return [
    new Paragraph({ children: [new TextRun({ text: `TABLE ${ROMAN[tableNo - 1]}`, font: FONT, size: 16, smallCaps: true })],
      alignment: AlignmentType.CENTER, spacing: { before: 120, after: 0 }, keepNext: true }),
    new Paragraph({ children: [new TextRun({ text: title, font: FONT, size: 16, smallCaps: true })],
      alignment: AlignmentType.CENTER, spacing: { after: 60 }, keepNext: true }),
  ];
}
const rule = { style: BorderStyle.SINGLE, size: 6, color: "000000" };
const none = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
function table(headers, rows, widths, opts = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  const mk = (cells, i, isHead) => new TableRow({
    tableHeader: isHead, cantSplit: true,
    children: cells.map((c, j) => new TableCell({
      width: { size: widths[j], type: WidthType.DXA },
      verticalAlign: VerticalAlign.CENTER,
      margins: { top: 20, bottom: 20, left: 60, right: 60 },
      borders: {
        top: isHead ? rule : none,
        bottom: isHead || i === rows.length - 1 ? rule : none,
        left: none, right: none,
      },
      children: [new Paragraph({
        children: runs(String(c), { size: 16, bold: isHead || undefined }),
        alignment: j === 0 && !opts.centerFirst ? AlignmentType.LEFT : AlignmentType.CENTER,
        keepNext: i < rows.length - 1,
      })],
    })),
  });
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths, alignment: AlignmentType.CENTER,
    rows: [mk(headers, -1, true), ...rows.map((r, i) => mk(r, i, false))],
  });
}
const tableNote = (text) => new Paragraph({ children: runs(text, { size: 16 }), spacing: { before: 40, after: 120 },
  alignment: AlignmentType.LEFT });
const gap = () => new Paragraph({ children: [], spacing: { after: 60 } });

function figure(file, wPx, hPx, caption) {
  figNo++;
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120 }, keepNext: true, children: [
      new ImageRun({ type: "png", data: fs.readFileSync(path.join(__dirname, file)), transformation: { width: wPx, height: hPx } }),
    ] }),
    new Paragraph({ children: [new TextRun({ text: `Fig. ${figNo}. `, font: FONT, size: 16 }), ...runs(caption, { size: 16 })],
      alignment: AlignmentType.JUSTIFIED, spacing: { before: 60, after: 160 } }),
  ];
}

// ---------- content ----------
const titleBlock = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({
    text: "MedResolve: Structure-Aware Retrieval over Longitudinal Patient Records for Patient-Facing Medical Question Answering",
    font: FONT, size: 48 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [
    new TextRun({ text: "Kaushik Kumar Reddy S", font: FONT, size: 22 }),
    new TextRun({ text: "   Abhiram Boyidi", font: FONT, size: 22 }),
    new TextRun({ text: "   Dr. B. Jothi (Guide)", font: FONT, size: 22 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Department of [to be filled]", font: FONT, size: 20, italics: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "SRM Institute of Science and Technology", font: FONT, size: 20, italics: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 }, children: [new TextRun({ text: "[City], India · [email addresses]", font: FONT, size: 20 })] }),
];

const abstractText = "A patient's new health question is usually answered from general medical knowledge, without the patient's own history of conditions, medications, symptoms and lab results. MedResolve is a research prototype that retrieves evidence from the patient's longitudinal record before generating an answer; every patient-specific statement must cite a record, and a verification gate withholds claims the record does not support. We adapt STAIR, a structure-aware retriever that routes a query to a section of a book's table of contents, to patient records. In STAIR-Clinical, each patient's record becomes a two-level table of contents; a fine-tuned Mistral-7B router (QLoRA, 100 steps) picks the sections, exact database operations resolve them to records, and the result is fused with hybrid BM25 + BGE-M3 retrieval. We evaluate on 14 question categories generated deterministically from Synthea (599 test questions, 108 unseen patients) and, with no further training, on the MIMIC-IV FHIR demo (599 questions, 100 patients) and the eICU demo (600 questions, 530 patients). The fused router (R11) reaches Recall@5 of 0.905, 0.922 and 0.954, against 0.777, 0.768 and 0.831 for the strongest non-routed baseline: gains of +0.128, +0.153 and +0.123, all with patient-clustered 95% CIs above zero. The gains come from fine-tuning; the untrained router does not beat the baseline. On LLM-paraphrased questions every method loses 2–11 points of Recall@5; R11 keeps a significant lead (+0.09 to +0.15), while R8 and R10 lose theirs on some sources. The main fragility is rule-based temporal parsing, not the router; rewriting those rules, frozen before a fresh held-out paraphrase set was generated, cut the drop of the rule-dependent R8 from 0.062\u20130.098 to 0.034\u20130.073 without lowering any original-wording score. In answer generation (llama3.2:3b), patient context raises gold-concept coverage from 0.40 to 0.79 on Synthea, and the verification gate released 0 unsupported patient claims in 117 Synthea answers and 2 in 60 MIMIC answers. Clinician ratings are pending; this is not a clinically validated system.";

const content = [];
const add = (...x) => content.push(...x.flat());

add(new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 100 }, children: [
  new TextRun({ text: "Abstract", font: FONT, size: 18, bold: true, italics: true }),
  new TextRun({ text: "—" + abstractText, font: FONT, size: 18, bold: true })] }));
add(new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 160 }, children: [
  new TextRun({ text: "Index Terms", font: FONT, size: 18, bold: true, italics: true }),
  new TextRun({ text: "—Retrieval-augmented generation, electronic health records, structure-aware retrieval, large language models, medical question answering, claim verification, patient safety.", font: FONT, size: 18, bold: true })] }));

// I. Introduction
add(h1("Introduction"));
add(body("The same question means different things for different patients. \"Is this headache something to worry about?\" calls for one answer for a healthy 25-year-old and another for a patient with hypertension, a recent change of anticoagulant and two similar episodes last year. General medical chatbots and medical retrieval-augmented generation (RAG) systems [22] answer from textbooks and guidelines. They do not see this history, so they either ask the patient for it or ignore it."));
add(body("The history exists in the patient's record, but a longitudinal record is hard to search. A single patient in our data has up to 13,695 records, most of them lab values. Many questions need records from several sections at once (medications *and* an earlier symptom episode) or an exact operation (the latest value, everything in a date range). Flat retrieval over record text ranks the newest or most lexically similar records, and it often misses the right section altogether."));
add(body("STAIR [1] showed that a fine-tuned LLM can route a query to the right leaf of a long document's table of contents. A patient record has a natural table of contents: demographics, history, medications, allergies, encounters, labs and documents. MedResolve uses this idea for patient-facing questions and adds the safety layers that a patient-facing answer needs. Our contributions are:"));
add(numbered(1, "**STAIR-Clinical**, structure-aware routing over a per-patient table of contents. Patient data stays in the database and is never memorised in model weights; the router is trained once on a fixed clinical skeleton and works on new patients and new records without retraining."));
add(numbered(2, "**A longitudinal retrieval benchmark** of 14 question categories with gold evidence computed by database queries, not by an LLM. It covers a synthetic training source (Synthea) and two real, de-identified, open-access test sources used only for evaluation (MIMIC-IV FHIR demo, eICU demo)."));
add(numbered(3, "**A controlled comparison** of 11 retrieval methods with patient-clustered bootstrap statistics, showing when structure-aware routing helps (a fine-tuned router fused with hybrid retrieval) and when it does not (non-learned or CPU-scale routers)."));
add(numbered(4, "**A paraphrase robustness test** that separates the learned router, which is robust, from rule-based temporal parsing, which is not."));
add(numbered(5, "**An end-to-end answer pipeline (B0–B5)** with citation of every patient-specific claim, a claim-verification gate and emergency pre-emption, evaluated with automated proxies; a blinded clinician review is prepared."));

// II. Related work
add(h1("Related Work"));
add(body("MedResolve sits where four lines of work meet: patient-aware medical assistants, structure-aware retrieval, hybrid and temporal retrieval, and evidence-grounded safety. Our base paper is SC-SAE-RAG [2], which recovers evidence along a document's section chain; MedResolve applies the same section-first idea to a changing patient record."));
add(runIn("Patient-context-aware medical assistants.", "Recent systems personalise medical answers with multi-source retrieval for diabetes care [3], patient-specific drug and dosage modelling [4], knowledge-graph-augmented context-aware QA [5], conversational agents for gestational diabetes [6] and multimodal chatbots for preliminary diagnosis [7]. Most use a fixed patient profile or a single condition. MedResolve retrieves from the full longitudinal record and requires a citation for each patient-specific claim. EHR question-answering datasets such as emrQA [33] and EHRSQL [34] target clinicians and structured queries, not patient-facing free text."));
add(runIn("Structure-aware retrieval.", "STAIR [1] fine-tunes Mistral-7B [32] to generate the leaf of a book's table of contents that answers a query, and also memorises book content in its weights in the style of DSI [26]. Other work uses chapter structure for traceable extraction [8], hierarchical templates [9], structure in OCR-derived documents [10] and header hierarchies for tables [11]. STAIR-Clinical keeps STAIR's prompt shape and LoRA settings but drops parametric memorisation: patient data changes, so only the routing skill is learned."));
add(runIn("Hybrid and time-aware retrieval.", "We fuse BM25 [23] with BGE-M3 dense retrieval [24] using reciprocal rank fusion [25]. Fusion can hurt when one retriever is much weaker [14], and RAG architectures differ by domain [15]. Clinical summarisation work stresses the hospital course over time [16]. MedResolve handles time with exact database operations (date ranges, latest value, medications active on a date) rather than with retrieval scores."));
add(runIn("Constrained outputs and evidence-grounded safety.", "Closed-set verification and correction [12] and uncertainty signals [13] make LLM output more reliable in medicine. Verifiable biomedical search [17], knowledge-graph retrieval against hallucination [18], precision RAG [19] and domain-optimised RAG [20] ground answers in sources. MedResolve restricts the router to sections that exist for the patient, so invalid paths are impossible by construction, and verifies each patient-specific claim against the retrieved records before release. We train with LoRA/QLoRA [27], [28]; the repeatability of such fine-tuning [21] is why we flag a second training seed as open work."));

// III. System
add(h1("System"));
add(body("MedResolve answers a question in five steps: emergency check, patient-record retrieval, reference retrieval, generation with citations, and claim verification. Retrieval is the research focus; the other steps make the answer safe to show a patient."));
add(h2("A", "Longitudinal Patient Memory"));
add(body("FHIR R4 bundles are normalised into one record table (SQLite) with the source resource, concept code, dates, value, unit, status and provenance. Levels 1–2 of the record hierarchy are a fixed clinical skeleton of 7 branches and 23 leaves (e.g., 3.1 Current Medications, 6.1 Laboratory Results). Level 3 holds dynamic concept groups, one per lab test, medication ingredient or condition. The table of contents (ToC) is rebuilt from the database for each query and annotated with record counts and date ranges. Every query is scoped to one patient; no retrieval step can see another patient's records."));
add(h2("B", "STAIR-Clinical Routing"));
add(body("The router follows STAIR's prompt shape: an instruction, the patient's ToC and the query, with the section title as the target. It differs from STAIR in four ways."));
add(numbered(1, "*No parametric memory.* Only the routing skill is trained; patient content arrives through the ToC and the database, so new records need no retraining."));
add(numbered(2, "*Constrained scoring.* We compute log P(candidate | prompt) for every valid section of this patient, sharing the prompt's KV cache. This equals constrained decoding over the valid set, returns a full ranking and makes invalid paths impossible."));
add(numbered(3, "*Multi-path selection.* Scores are softmax-normalised and sections are kept until cumulative probability reaches 0.85 (at most 3 sections, 4 concept groups each)."));
add(numbered(4, "*Exact operations after routing.* Date ranges, latest value, trend series and \"medications active during episode X\" are database operations, not retrieval scores."));
add(body("The reference router is Mistral-7B-Instruct-v0.2 with 4-bit QLoRA (r = 16, α = 32, dropout 0.05 on q, k, v, o; learning rate 2×10⁻⁴). It was trained for 100 steps × 8 = 800 examples on a Tesla T4 (15,779 s), 0.2 of one pass over a 4,000-example pool and far below STAIR's 200 epochs. The router needs a GPU, so its test predictions are computed on Kaggle and replayed locally (R10, R11)."));
add(h2("C", "Retrieval Methods Compared"));
add(body("Table I lists the eleven methods. All share the same query understanding (lay-name expansion, date parsing, episode detection), so it does not favour STAIR. Fusion uses RRF with weight 1.0 for the STAIR list and 0.5 for the hybrid list."));
add(tableCaption("Retrieval Methods"));
add(table(["ID", "Method", "Router", "Fusion"], [
  ["R1", "BM25 over record text", "none", "no"],
  ["R2", "BGE-M3 dense over concept text", "none", "no"],
  ["R3", "BM25 + BGE-M3, RRF", "none", "—"],
  ["R4", "R3 + structured operations (baseline)", "none", "—"],
  ["R5", "STAIR, structural router (no LLM)", "non-learned", "no"],
  ["R6", "STAIR, Qwen2.5-0.5B zero-shot", "untrained LLM", "no"],
  ["R7", "STAIR, Qwen2.5-0.5B LoRA (CPU)", "trained LLM", "no"],
  ["R8", "R5 fused with R4", "non-learned", "RRF"],
  ["R9", "R7 fused with R4", "trained LLM", "RRF"],
  ["R10", "STAIR, Mistral-7B QLoRA", "trained LLM", "no"],
  ["R11", "R10 fused with R4", "trained LLM", "RRF"],
], [500, 2540, 1300, 700]));
add(gap());
add(h2("D", "Answer Pipeline (B0–B5)"));
add(body("Table II lists the six answer variants. The generator is llama3.2:3b, run locally through Ollama. Patient evidence and references get aliases ([E1], [R1]) and the prompt requires a citation for every patient-specific claim. In B5 an emergency detector runs before any retrieval, reconciliation flags conflicts and stale data, and the claim verifier checks each patient-specific sentence against the cited records and releases only permitted claims; the released text states how many were withheld."));
add(tableCaption("Answer Pipeline Variants"));
add(table(["Variant", "Patient history", "References", "Safety layer"], [
  ["B0", "none (LLM only)", "none", "none"],
  ["B1", "none", "hybrid RAG", "none"],
  ["B2", "STAIR-Clinical", "none", "none"],
  ["B3", "hybrid + structured", "hybrid RAG", "none"],
  ["B4", "STAIR-Clinical + hybrid", "STAIR-routed RAG", "none"],
  ["B5", "as B4", "as B4", "emergency, reconciliation, action policy, claim verification"],
], [640, 1400, 1100, 1900]));
add(gap());

// IV. Data
add(h1("Data and Benchmark"));
add(body("The benchmark has 14 question categories over three record sources (Table III). Gold evidence is always computed by deterministic database queries, never by an LLM. The router is trained only on Synthea [29]; MIMIC-IV [30] and eICU [31] demo records are used only for testing."));
const wideTableIII = [
  ...tableCaption("Record Sources and Question Sets"),
  table(["Source", "Type", "Use", "Patients", "Questions (pool)", "Evaluated", "Categories"], [
    ["Synthea", "synthetic FHIR R4", "train / val / test", "671 (473 / 89 / 109)", "16,198 / 3,074 / 3,736", "599 test (108 patients)", "14"],
    ["MIMIC-IV FHIR demo", "real, de-identified, open access", "test only", "100", "2,262", "599 (100 patients)", "9"],
    ["eICU-CRD demo", "real, de-identified, open access (ODbL)", "test only", "2,174", "52,576", "600 (530 patients)", "10"],
  ], [1500, 2200, 1300, 1500, 1640, 1500, 800]),
  gap(),
];
add(runIn("Question categories.", "Medications during a previous symptom episode, relevant history for a new symptom, organ-system lab lookup, similar previous symptoms, current medications, allergy check, lab trend, latest measurement, medication changes, condition status, last visit, procedure history, immunization history and diagnoses in a year. Each category has 2–4 templates in first and third person with lay names (e.g., \"kidney labs\"). MIMIC and eICU lack some record types, so they cover 9 and 10 categories."));
add(runIn("Gold evidence.", "Gold is the set of evidence paths (concept groups) that answer the question, with up to the 3 most recent records per path. Clinical associations for symptom questions come from a curated map (symptom to related conditions, organ system to labs). The same map drives query expansion in every method, so it does not favour STAIR, but it is a confound for absolute numbers."));
add(runIn("Splits and sampling.", "Synthea patients are split 70/15/15 by a SHA-256 bucket of the patient identifier, so no patient is in two splits. Evaluation uses a category-stratified sample (seed 2026) of 599–600 questions per source."));
add(runIn("Date shift.", "MIMIC dates are shifted into the years 2100–2200 for de-identification, so the pipeline takes \"today\" from the patient's latest record for date-shifted sources. Before this fix, current medications were judged against the real date and wrongly marked as stopped (Section VI-E)."));

// V. Setup
const setup = [
  h1("Experimental Setup"),
  body("All retrieval runs use the same questions, the same embedding model (BAAI/bge-m3) and the same structured operations; only the router and the fusion change between methods."),
  runIn("Retrieval metrics.", "The primary metric is capped Recall@5 = |gold ∩ top-5| / min(|gold|, 5). We also report Recall@1/10 and MRR, and for STAIR methods the invalid path rate: emitted paths that do not exist in the patient's hierarchy."),
  runIn("Statistics.", "Questions from the same patient are correlated, so all 95% confidence intervals use a patient-clustered percentile bootstrap (1,000 resamples). Method differences are paired on the same questions and clustered by patient, with a two-sided bootstrap p-value."),
  runIn("Paraphrase robustness.", "llama3.2:3b (temperature 0.7, seed 2026) rewrote each evaluated question. A rewrite was rejected if it was empty, unchanged, changed a date, added a time period, or kept under 80% of the clinical (non-template) words; rejected questions got up to two more attempts with new seeds. Accepted: 486/599 Synthea, 522/599 MIMIC and 530/600 eICU. Retrieval was re-run on the rewrites, and the Mistral router re-scored them with the same adapter. Results are paired with the original wording of the same questions. For the robustness fix (Section VI-F) we used two further sets made the same way: a development set of 425 paraphrased validation questions (seed 3101), and a held-out set of the test questions (seed 4242; 501/517/520 accepted), generated only after the fix was frozen."),
  runIn("Answer evaluation.", "We sampled 120 Synthea test questions plus 5 safety probes, and 60 MIMIC questions (seed 41), and generated B0–B5 answers with llama3.2:3b on a Kaggle T4 using record-and-replay: each prompt is exported locally, generated on the GPU and replayed by the SHA-256 of the system and user prompt, so the local pipeline sees exactly the GPU text. GPU generation is not bit-reproducible (identical prompts gave different text in 37 of 40 checks across runs), so each answer is one sample."),
  runIn("Automated answer proxies.", "*Unsupported patient-claim rate*: share of patient-specific claims not supported by the retrieved records (lexical verifier). *Evidence support rate*: share of all claims supported by evidence or references. *Historical context coverage*: share of gold concepts the answer mentions. *Patient-history consistency*: no contradiction with the record. *Action appropriateness*: correct action on safety probes. For B5 we also count unsupported claims left in the released text after the gate."),
  runIn("Hardware.", "Retrieval and verification ran on a CPU-only laptop (Intel i7-13700H, 16 GB). Router training, router scoring and answer generation ran on a Tesla T4 (Colab, then Kaggle)."),
];

// VI. Results
const resultsA = [
  h1("Results"),
  body("The fine-tuned router fused with hybrid retrieval (R11) is the best method on all three sources, and the only STAIR variant whose lead survives paraphrasing on all three. Non-learned and CPU-scale routers do not beat the hybrid baseline reliably."),
  h2("A", "Retrieval on Synthea"),
  body("Table IV gives results on 599 questions from 108 unseen patients. R11 beats R4 by +0.128 Recall@5 (95% CI [0.093, 0.160]); R10 alone beats it by +0.074 [0.037, 0.110]. The gain comes from fine-tuning: the untrained Mistral router ties R4 when fused (−0.036 [−0.076, 0.006], before the fix), and fine-tuning raises its section hit@1 from 0.766 to 0.958. The CPU-scale routers do not reach the baseline: the 0.5B LoRA router improves on zero-shot by +0.304 but stays below R5, and R8 is level with R4 (+0.004 [−0.036, 0.046]). No STAIR method emitted an invalid path."),
  ...tableCaption("Retrieval on Synthea Test (599 Questions)"),
  table(["Method", "R@1", "R@5", "R@10", "MRR"], [
    ["R1 BM25", "0.462", "0.546", "0.618", "0.535"],
    ["R2 BGE-M3", "0.606", "0.613", "0.647", "0.645"],
    ["R3 Hybrid RRF", "0.644", "0.719", "0.780", "0.711"],
    ["R4 Hybrid + structured", "0.693", "0.777", "0.840", "0.756"],
    ["R5 STAIR structural", "0.521", "0.649", "0.697", "0.593"],
    ["R6 Qwen-0.5B zero-shot*", "0.107", "0.187", "0.280", "0.168"],
    ["R7 Qwen-0.5B LoRA*", "0.314", "0.491", "0.650", "0.433"],
    ["R8 Structural + hybrid", "0.664", "0.781", "0.889", "0.742"],
    ["R9 Qwen LoRA + hybrid*", "0.716", "0.722", "0.773", "0.770"],
    ["R10 Mistral, untrained*", "0.629", "0.639", "0.669", "0.681"],
    ["R11 Mistral, untrained + hybrid*", "0.703", "0.722", "0.841", "0.758"],
    ["R10 Mistral QLoRA", "0.713", "0.851", "0.902", "0.793"],
    ["**R11 Mistral QLoRA + hybrid**", "**0.820**", "**0.905**", "**0.959**", "**0.875**"],
  ], [2240, 700, 700, 700, 700]),
  tableNote("*Run before the episode-matching fix (Section VI-C); compare with R4 before the fix, Recall@5 = 0.758. R1–R3 do not use the fixed operation."),
  h2("B", "Generalisation to Real De-identified Records"),
  body("The router was trained only on Synthea and applied unchanged to MIMIC and eICU, where its section hit@1 was 0.723 and 0.830 (0.958 on Synthea). Table V and Fig. 1 show that R11 improves both Recall@5 and MRR on every source. The non-learned router helps more on real records than on Synthea (R8: +0.070 on MIMIC, +0.079 on eICU) but lowers MRR on eICU (0.797 vs 0.832): it finds the right records but ranks them lower."),
];
const wideTableV = [
  ...tableCaption("Recall@5 / MRR on External Test Sources"),
  table(["Source", "R4", "R5", "R8", "R10", "R11"], [
    ["MIMIC-IV demo (599 q, 100 patients)", "0.768 / 0.814", "0.746 / 0.738", "0.839 / 0.813", "0.898 / 0.936", "**0.922 / 0.940**"],
    ["eICU demo (600 q, 530 patients)", "0.831 / 0.832", "0.738 / 0.647", "0.910 / 0.797", "0.892 / 0.882", "**0.954 / 0.937**"],
  ], [3040, 1480, 1480, 1480, 1480, 1480]),
  gap(),
  ...figure("fig1_gain_over_r4.png", 560, 300, "Recall@5 gain over R4 for R8, R10 and R11 on each source (paired on 599/599/600 questions; whiskers: 95% patient-clustered bootstrap CI). R11's interval is above zero everywhere; R8's crosses zero on Synthea."),
];
const resultsB = [
  h2("C", "Episode-Matching Fix"),
  body("An error analysis found \"medications during my previous <condition> episode\" questions failing when the condition was not in the symptom vocabulary (e.g., \"sepsis, pulmonary\") or was mis-parsed. We changed the parser to keep the episode phrase and to anchor on the record whose name matches it. The fix raised R4 by +0.011 to +0.027 Recall@5 across the three sources, and R11 by +0.038 on Synthea and +0.029 on eICU. It did not change the R11 − R4 gap (+0.109 to +0.128 on Synthea, +0.121 to +0.123 on eICU). The paraphrase test (Section VI-D) shows that the fix is tuned to our templates."),
  h2("D", "Paraphrase Robustness"),
  body("Rewording costs every method accuracy (Table VI). R4 loses the least (−0.015 to −0.063 Recall@5), R11 loses −0.047 to −0.085, and the non-learned STAIR variants lose up to −0.114. R11's lead over R4 shrinks by 0.02–0.04 but stays significant on every source, while R8 loses its lead on Synthea and eICU and R10 on eICU (Fig. 2)."),
  ...tableCaption("Recall@5, Original → Paraphrased"),
  table(["Method", "Synthea (486)", "MIMIC (522)", "eICU (530)"], [
    ["R4 Hybrid + structured", "0.763 → 0.700", "0.745 → 0.718", "0.824 → 0.810"],
    ["R5 STAIR structural", "0.684 → 0.581", "0.731 → 0.676", "0.720 → 0.606"],
    ["R8 Structural + hybrid", "0.808 → 0.702", "0.832 → 0.784", "0.911 → 0.797"],
    ["R10 Mistral router", "0.850 → 0.756", "0.891 → 0.818", "0.896 → 0.806"],
    ["R11 Mistral + hybrid", "0.902 → 0.817", "0.913 → 0.867", "0.958 → 0.902"],
  ], [1640, 1130, 1130, 1140]),
  gap(),
  body("The learned router itself is robust: its section hit@1 dropped by only 0.015–0.039 (Synthea 0.967 to 0.928, MIMIC 0.762 to 0.747, eICU 0.825 to 0.800 on the same questions). The larger end-to-end drop comes from rule-based parsing after routing. For R11, lab-trend questions fell from 0.94–0.95 to 0.80–0.85, because \"changed over time\" is detected by keywords; lab lookup fell from 0.92 to 0.79 on eICU; and medication-during-episode questions roughly halved for every method, R4 included (n = 5–10 per source)."),
];
const wideFig2 = [
  ...figure("fig2_paraphrase_lead.png", 560, 308, "Recall@5 lead over R4 on the original wording (hollow) and on paraphrased questions (filled, with 95% CI), on the same 486/522/530 questions."),
];
const resultsC = [
  h2("E", "Answer Quality (B0–B5)"),
  body("Patient context is what makes answers specific: B0 cannot cite the record, and coverage of the gold concepts roughly doubles once history is retrieved (Table VII). The verification gate removes nearly all unsupported patient claims from the released text, at some cost in coverage."),
];
const wideTableVII = [
  ...tableCaption("Automated Answer Metrics (Synthea: 120 Questions; MIMIC-IV Demo: 60 Questions)"),
  table(["Metric", "Source", "B0", "B1", "B2", "B3", "B4", "B5"], [
    ["Unsupported patient-claim rate (raw generation)", "Synthea", "0.99", "0.99", "0.63", "0.61", "0.60", "0.63"],
    ["", "MIMIC", "1.00", "0.98", "0.66", "0.65", "0.59", "0.59"],
    ["Unsupported claims in released text", "Synthea", "—", "—", "—", "—", "—", "**0** (117)"],
    ["", "MIMIC", "—", "—", "—", "—", "—", "**2** (60)"],
    ["Evidence support rate", "Synthea", "0.06", "0.45", "0.39", "0.51", "0.50", "0.46"],
    ["", "MIMIC", "0.07", "0.43", "0.40", "0.51", "0.53", "0.53"],
    ["Historical context coverage", "Synthea", "0.40", "0.52", "0.76", "0.79", "0.79", "0.68"],
    ["", "MIMIC", "0.18", "0.38", "0.62", "0.68", "0.62", "0.56"],
    ["Patient-history consistency", "Synthea", "1.00", "1.00", "0.95", "0.95", "0.96", "0.96"],
    ["", "MIMIC", "1.00", "1.00", "0.97", "0.95", "0.94", "0.91"],
    ["Safety probes handled correctly", "Synthea", "1/5", "1/5", "1/5", "1/5", "1/5", "**5/5**"],
  ], [3240, 1000, 1000, 1000, 1000, 1000, 1000, 1200]),
  gap(),
];
const resultsD = [
  body("The first MIMIC run showed B5 with more unsupported claims than B4. Two causes explained it: the date-shift bug made the reconciliation step mark current medications as stopped, and GPU sampling noise made identical prompts give different text. After the fix, B5's draft matched B4 (unsupported rate 0.59 for both), and the gate left 2 unsupported claims in 60 released answers. Withholding unverifiable claims lowers coverage (MIMIC 0.56 vs 0.62; Synthea 0.68 vs 0.79). Factual correctness is not measured by these proxies; a blinded review of 120 answers (40 questions × B0/B4/B5) by two clinicians is prepared and pending."),
  h2("F", "Robustness Fix and Held-out Paraphrase Test"),
  body("Rewriting the query-understanding rules to match meaning rather than template wording roughly halved the paraphrase drop of the rule-dependent methods without lowering any original-wording score. The fix was developed only on 425 paraphrased Synthea *validation* questions and frozen before the held-out paraphrase set was generated. It recognises episode questions in several constructions (\"when the sinus infection first started\", \"an episode of X\"); widens the trend vocabulary (\"improving\", \"deteriorating\", \"trending upward\"); reads year expressions such as \"in the year 2003\" and \"March of 2017\", no longer treats \"during 2003\" as an episode and accepts years 2100\u20132199, so MIMIC's date-shifted questions (76 in the pool) get their date filter; adds intent patterns and lab-group synonyms (\"complete blood cell counts\", \"lipid panel\"); and makes \"current medications\" an exact database lookup for every method."),
  ...tableCaption("Recall@5 on Original Wording, Before \u2192 After the Fix"),
  table(["Method", "Synthea", "MIMIC", "eICU"], [
    ["R4 Hybrid + structured", "0.777 \u2192 0.789", "0.768 \u2192 0.770", "0.831 \u2192 0.831"],
    ["R5 STAIR structural", "0.649 \u2192 0.720", "0.746 \u2192 0.783", "0.738 \u2192 0.771"],
    ["R8 Structural + hybrid", "0.781 \u2192 0.824", "0.839 \u2192 0.861", "0.910 \u2192 0.924"],
    ["R10 Mistral router", "0.851 \u2192 0.855", "0.898 \u2192 0.901", "0.892 \u2192 0.892"],
    ["R11 Mistral + hybrid", "0.905 \u2192 0.908", "0.922 \u2192 0.924", "0.954 \u2192 0.954"],
  ], [1640, 1130, 1130, 1140]),
  tableNote("No method got worse. R11 \u2212 R4 after the fix: +0.119 [0.085, 0.152], +0.154 [0.130, 0.179], +0.123 [0.095, 0.153]."),
  ...tableCaption("Recall@5 Change on Held-out Paraphrases, Before \u2192 After the Fix"),
  table(["Method", "Synthea (501)", "MIMIC (517)", "eICU (520)"], [
    ["R4 Hybrid + structured", "\u22120.039 \u2192 \u22120.027", "\u22120.021 \u2192 \u22120.024", "+0.006 \u2192 +0.003"],
    ["R5 STAIR structural", "\u22120.042 \u2192 \u22120.000", "\u22120.049 \u2192 \u22120.031", "\u22120.056 \u2192 \u22120.032"],
    ["R8 Structural + hybrid", "\u22120.075 \u2192 \u22120.034", "\u22120.062 \u2192 \u22120.045", "\u22120.098 \u2192 \u22120.073"],
  ], [1640, 1130, 1130, 1140]),
  gap(),
  body("On the held-out paraphrases, R8's lead over R4 rose from \u22120.009 / +0.050 / \u22120.013 to +0.036 [\u22120.003, 0.075] / +0.090 [0.057, 0.125] / +0.029 [\u22120.012, 0.068]; it is significant only on MIMIC, so the fix reduces the fragility but does not remove it. On the first paraphrase set, R11's drop shrank from \u22120.085 / \u22120.047 / \u22120.056 to \u22120.053 / \u22120.042 / \u22120.029; we had seen that set's per-category results before writing the fix, so it is not a clean test. The Mistral router was not re-scored on the held-out set (it needs a GPU run), so held-out results cover the CPU methods only."),
  h1("Discussion and Limitations"),
  body("Structure-aware routing pays off only when the router is learned and its output is fused with hybrid retrieval. A fine-tuned 7B router, trained for 100 steps on synthetic questions, transfers to two real record sources and keeps its lead under paraphrase. The non-learned router loses its lead on two of three sources, and the 0.5B router never beat the baseline."),
  runIn("Why fusion matters.", "Routing alone (R10) finds the right section but can miss records that hybrid search ranks well, e.g., lab lookups where the lay term matches record text directly. Fusion recovers these: R11 beats R10 on every source, in line with SC-SAE-RAG's recovery of missed sections [2]."),
  runIn("Where the system is weak.", "Rule-based temporal and episode parsing broke on reworded questions. Rewriting it on validation paraphrases halved the drop on a held-out set, but R8 still loses 0.03\u20130.07 Recall@5 on reworded questions and its lead is significant only on MIMIC; a learned query parser, trained like the router, is the natural next step."),
  runIn("Limitations.", "(i) All questions come from 2–4 templates per category; the paraphrase test reduces but does not remove this bias, and no real patient questions were used. (ii) Gold evidence and query expansion share a curated symptom–condition and organ–lab map, which inflates absolute scores for all methods. (iii) The router was trained once (100 steps, one seed); QLoRA results can vary between runs [21]. (iv) The MIMIC demo has 100 patients and eICU covers ICU stays; neither represents outpatient care. (v) The claim verifier is lexical and not yet validated against clinicians; factual correctness and safety are not yet rated. (vi) Each answer is one GPU sample, so small B4–B5 differences are within sampling noise. (vii) The 7B router needs a GPU; the CPU app runs a CPU-scale router, which matches the weaker R8/R9 configurations."),
  h1("Ethics and Data Use"),
  body("No identifiable patient data was used, and no record was sent to a hosted LLM API. Synthea records are synthetic. The MIMIC-IV FHIR demo and eICU-CRD demo are open-access, de-identified PhysioNet demo releases (eICU demo under ODbL), used for testing only and never for training; the full, credentialed MIMIC-IV was not used. All generation used open-weight models, run on local Ollama or in a Kaggle notebook we controlled. Each query is restricted to one patient's records, and the API enforces patient isolation. MedResolve is a research prototype, not a diagnostic or prescribing system, and every answer says so. The clinician review rates text answers, not patients; ethics-approval requirements will be confirmed with the institution before it starts."),
  h1("Conclusion and Future Work"),
  body("A patient's own record can be searched like a book's table of contents. A fine-tuned router fused with hybrid retrieval raises Recall@5 by +0.12 to +0.15 over a strong hybrid baseline on synthetic and real de-identified records, and keeps a significant lead when questions are reworded. Combined with per-claim citations and a verification gate, it lets a small local LLM give patient-specific answers that release almost no unsupported patient claims. Next steps are: (1) complete the blinded clinician review (2 raters, 120 answers) and report agreement and factual correctness; (2) replace the rule-based query parser with a learned one and re-score the Mistral router on the held-out paraphrase set; (3) train the router with a second seed to measure run-to-run variance; and (4) evaluate on real patient-written questions and distil the router to a CPU-sized model for deployment."),
  h1plain("References"),
];

const REFS = [
  "STAIR (STructure Aware Information Retriever): A novel dataset and LLM based retriever for document structure augmentation, arXiv:2609.03874v2, 2026.",
  "Q. Zhang, X. Liu, H. Wang, et al., \"SC-SAE-RAG: Bounded section-chain evidence recovery for scientific literature question answering,\" *IEEE Access*, vol. 14, pp. 161099–161115, 2026, doi: 10.1109/ACCESS.2026.3744475.",
  "M. Jamil, A. Kavak, S. Bayraktar, et al., \"A multi-source retrieval-augmented large language model architecture for trustworthy conversational AI in diabetes care,\" *IEEE Access*, vol. 14, 2026, doi: 10.1109/ACCESS.2026.3718400.",
  "E. Daglarli, \"Drug and dosage recommendation based on explainable generative AI using patient-specific modeling,\" *IEEE Access*, vol. 14, 2026, doi: 10.1109/ACCESS.2026.3657398.",
  "S. Mbah, T. M. Fagbola, B. K. Mishra, et al., \"ICONQUER: A transformer-based instruction-finetuned context-aware medical question answering model with knowledge graph augmentation,\" *IEEE Access*, vol. 13, 2025, doi: 10.1109/ACCESS.2025.3642232.",
  "P. Ratchakom, S. Rosjan, T. Piumsomboon, et al., \"Glumii: Personalized supportive passive-active conversational agents for pregnant women with gestational diabetes mellitus,\" *IEEE Access*, vol. 14, 2026, doi: 10.1109/ACCESS.2026.3730820.",
  "I. Agarwal, V. Sakthivel, and P. Prakash, \"Toward inclusive healthcare: An LLM-based multimodal chatbot for preliminary diagnosis,\" *IEEE Access*, vol. 13, 2025, doi: 10.1109/ACCESS.2025.3594218.",
  "X. Tao, H. Lyu, S.-Y. Ok, et al., \"Chapter-aware retrieval-augmented generation for complex ESG data extraction and traceability,\" *IEEE Access*, vol. 14, 2026, doi: 10.1109/ACCESS.2026.3745456.",
  "Y. Wang, Y. Tan, M. Song, and Y. Hao, \"Template-to-text: Hierarchical structure-aware retrieval for controllable document generation,\" *IEEE Access*, vol. 14, 2026, doi: 10.1109/ACCESS.2026.3713477.",
  "M. Song, \"Structure-aware hybrid representation for retrieval-augmented generation over OCR-derived documents,\" *IEEE Access*, vol. 14, 2026, doi: 10.1109/ACCESS.2026.3733530.",
  "M. Song, \"Enhancing RAG performance by representing hierarchical nodes in headers for tabular data,\" *IEEE Access*, vol. 13, 2025, doi: 10.1109/ACCESS.2025.3569872.",
  "C. Lin, X. Zheng, K. Wu, and O. Bai, \"CriticExpert: A lightweight task-specific verification-and-correction framework for LLM-generated closed-set specialized healthcare text coding,\" *IEEE Access*, vol. 14, 2026, doi: 10.1109/ACCESS.2026.3736407.",
  "E. D'Urso, \"Hidden-uncertainty assessment via non-verbalized signatures for LLM medical QA,\" *IEEE Access*, vol. 14, 2026, doi: 10.1109/ACCESS.2026.3682338.",
  "A. Chauhan and A. Agarwal, \"The fusion tax: A diagnostic analysis of when hybrid retrieval hurts,\" *IEEE Access*, vol. 14, 2026, doi: 10.1109/ACCESS.2026.3743502.",
  "P. Ersoy and M. Erşahın, \"A comparative evaluation of RAG architectures for cross-domain LLM applications: Design, implementation, and assessment,\" *IEEE Access*, vol. 13, 2025, doi: 10.1109/ACCESS.2025.3632404.",
  "A. A. Alhashmi, K. N. R. Alharbi, A. B. Alshammari, et al., \"GoT-HCS: Graph-of-thoughts enhanced hierarchical reasoning for automated clinical hospital course summarization,\" *IEEE Access*, vol. 14, 2026, doi: 10.1109/ACCESS.2026.3692741.",
  "M. Košprdić, A. Ljajić, B. Bašaragin, et al., \"VerifAI: A verifiable open-source search engine for biomedical question answering,\" *IEEE Access*, vol. 14, 2026, doi: 10.1109/ACCESS.2026.3676985.",
  "A. Lecu, A. Groza, and L. Hawizy, \"Reducing hallucinations in medical AI: A knowledge graph-augmented retrieval system for evidence-based age-related macular degeneration information,\" *IEEE Access*, vol. 13, 2025, doi: 10.1109/ACCESS.2025.3643370.",
  "Y. Shen, D. Xu, X. Li, et al., \"MGPRAG: Enhancing medical large language models via precision retrieval-augmented generation,\" *IEEE Access*, vol. 13, 2025, doi: 10.1109/ACCESS.2025.3624887.",
  "L. Cui, Y. Liu, C. Ouyang, et al., \"Bailicai: A domain-optimized retrieval-augmented generation framework for medical applications,\" *Big Data Mining and Analytics*, vol. 9, 2026, doi: 10.26599/BDMA.2024.9020097.",
  "S. S. Alahmari, L. O. Hall, P. R. Mouton, and D. B. Goldgof, \"Repeatability of fine-tuning large language models illustrated using QLoRA,\" *IEEE Access*, vol. 12, 2024, doi: 10.1109/ACCESS.2024.3470850.",
  "P. Lewis et al., \"Retrieval-augmented generation for knowledge-intensive NLP tasks,\" in *Proc. NeurIPS*, 2020.",
  "S. Robertson and H. Zaragoza, \"The probabilistic relevance framework: BM25 and beyond,\" *Foundations and Trends in Information Retrieval*, 2009.",
  "J. Chen et al., \"BGE M3-Embedding: Multi-lingual, multi-functionality, multi-granularity text embeddings through self-knowledge distillation,\" 2024.",
  "G. V. Cormack, C. L. A. Clarke, and S. Büttcher, \"Reciprocal rank fusion outperforms Condorcet and individual rank learning methods,\" in *Proc. SIGIR*, 2009.",
  "Y. Tay et al., \"Transformer memory as a differentiable search index,\" in *Proc. NeurIPS*, 2022.",
  "E. J. Hu et al., \"LoRA: Low-rank adaptation of large language models,\" in *Proc. ICLR*, 2022.",
  "T. Dettmers et al., \"QLoRA: Efficient finetuning of quantized LLMs,\" in *Proc. NeurIPS*, 2023.",
  "J. Walonoski et al., \"Synthea: An approach, method, and software mechanism for generating synthetic patients and the synthetic electronic health care record,\" *J. Amer. Med. Inform. Assoc.*, 2018.",
  "A. E. W. Johnson et al., \"MIMIC-IV, a freely accessible electronic health record dataset,\" *Scientific Data*, 2023.",
  "T. J. Pollard et al., \"The eICU Collaborative Research Database, a freely available multi-center database for critical care research,\" *Scientific Data*, 2018.",
  "A. Q. Jiang et al., \"Mistral 7B,\" arXiv:2310.06825, 2023.",
  "A. Pampari et al., \"emrQA: A large corpus for question answering on electronic medical records,\" in *Proc. EMNLP*, 2018.",
  "G. Lee et al., \"EHRSQL: A practical text-to-SQL benchmark for electronic health records,\" in *Proc. NeurIPS Datasets and Benchmarks*, 2022.",
];
const refParas = REFS.map((r, i) => new Paragraph({
  children: [new TextRun({ text: `[${i + 1}]`, font: FONT, size: 16 }), new TextRun({ text: "\t", font: FONT, size: 16 }),
    ...runs(r, { size: 16, highlight: i >= 21 ? "yellow" : undefined })],
  tabStops: [{ type: "left", position: 360 }], indent: { left: 360, hanging: 360 },
  alignment: AlignmentType.LEFT, spacing: { after: 20 },
}));

// ---------- sections ----------
const twoCol = { column: { count: 2, space: 360, equalWidth: true } };
const oneCol = { column: { count: 1 } };
const sec = (children, cols, first = false) => ({
  properties: { page: PAGE, ...(first ? {} : { type: SectionType.CONTINUOUS }), ...cols },
  children,
});

const doc = new Document({
  creator: "MedResolve team",
  title: "MedResolve: Structure-Aware Retrieval over Longitudinal Patient Records",
  styles: { default: { document: { run: { font: FONT, size: 20 } } } },
  sections: [
    sec(titleBlock, oneCol, true),
    sec(content, twoCol),
    sec(wideTableIII, oneCol),
    sec([...setup, ...resultsA], twoCol),
    sec(wideTableV, oneCol),
    sec(resultsB, twoCol),
    sec(wideFig2, oneCol),
    sec(resultsC, twoCol),
    sec(wideTableVII, oneCol),
    sec([...resultsD, ...refParas], twoCol),
    sec([new Paragraph({ children: [] })], oneCol),   // continuous break balances the last page's columns
  ],
});

Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("wrote", OUT); });

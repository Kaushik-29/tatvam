import React from 'react';
import {
  Sparkles,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  HelpCircle,
  Shield,
  FileText,
  BookOpen,
  ArrowRight,
  Info,
} from 'lucide-react';
import { AssessmentResult, PatientProfile, EvidenceItem } from '../types';
import { ScreenId } from '../components/Sidebar';

interface AiSummaryScreenProps {
  patient: PatientProfile | null;
  assessment: AssessmentResult | null;
  ledgerItems: EvidenceItem[];
  onNavigate: (screen: ScreenId) => void;
  onRunAssessment: () => void;
  isAssessing: boolean;
}

export const AiSummaryScreen: React.FC<AiSummaryScreenProps> = ({
  patient,
  assessment,
  ledgerItems,
  onNavigate,
  onRunAssessment,
  isAssessing,
}) => {
  if (!patient) {
    return (
      <div className="p-8 text-center text-[#61738A]">
        Please select a patient to view evidence summary.
      </div>
    );
  }

  if (!assessment) {
    return (
      <div className="max-w-4xl mx-auto bg-white border border-[#DFE7F1] rounded-lg p-12 text-center space-y-4">
        <Sparkles className="w-12 h-12 text-[#AFCFF2] mx-auto" />
        <h2 className="text-base font-bold text-[#172B4D]">
          No AI Evidence Summary Generated Yet
        </h2>
        <p className="text-xs text-[#61738A] max-w-md mx-auto">
          Execute the clinical reasoning pipeline to generate an evidence-bounded summary with claim-level reference verification.
        </p>
        <button
          onClick={onRunAssessment}
          disabled={isAssessing}
          className="px-4 py-2 bg-[#3675CA] hover:bg-[#265EAA] text-white rounded-md text-xs font-medium transition-colors"
        >
          {isAssessing ? 'Assessing...' : 'Run Clinical Assessment'}
        </button>
      </div>
    );
  }

  const patientReported = ledgerItems.filter((i) => i.source_type === 'PATIENT_REPORTED');
  const docExtracted = ledgerItems.filter((i) => i.source_type !== 'PATIENT_REPORTED');
  const confirmedFindings = ledgerItems.filter((i) => i.user_confirmation_status.startsWith('CONFIRMED'));
  const unconfirmedFindings = ledgerItems.filter((i) => i.user_confirmation_status === 'UNCONFIRMED');

  const supportedClaims = assessment.verified_claims.filter(
    (c) => c.reference_verification_status === 'SUPPORTED_BY_SOURCE'
  );
  const contradictedClaims = assessment.verified_claims.filter(
    (c) => c.reference_verification_status === 'CONTRADICTED_BY_SOURCE'
  );
  const insufficientClaims = assessment.verified_claims.filter(
    (c) => c.reference_verification_status === 'INSUFFICIENT_EVIDENCE'
  );

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Title */}
      <div className="bg-white border border-[#DFE7F1] rounded-lg p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-[10px] font-semibold bg-[#E3FCEF] text-[#26845A] px-2 py-0.5 rounded border border-[#ABF5D1]">
                DUAL-AXIS GROUNDED SUMMARY
              </span>
              <span className="text-xs text-[#8A99AB]">Case #{patient.patient_id}</span>
            </div>
            <h1 className="text-xl font-bold text-[#172B4D] flex items-center space-x-2 mt-1">
              <Sparkles className="w-5 h-5 text-[#3675CA]" />
              <span>Evidence-Grounded Clinical Summary & Claims Verification</span>
            </h1>
            <p className="text-xs text-[#61738A]">
              Structured synthesis with dual-axis verification: Patient Ledger Consistency & Medical Reference Grounding.
            </p>
          </div>

          <div className="flex items-center space-x-2 text-xs">
            <span className="px-2.5 py-1 bg-[#F1F5FA] border border-[#DFE7F1] rounded font-semibold text-[#172B4D]">
              Engine: {assessment.execution_engine}
            </span>
            <span className="px-2.5 py-1 bg-[#EAF2FC] border border-[#AFCFF2] rounded font-semibold text-[#3675CA] tabular-nums">
              {assessment.generation_latency_seconds}s CPU
            </span>
          </div>
        </div>
      </div>

      {/* Safety Notice (PART 5.2 requirement: No prescriptions / treatment instructions) */}
      <div className="bg-[#FAF9F6] border border-[#DFE7F1] rounded-lg p-4 flex items-start space-x-3">
        <Info className="w-5 h-5 text-[#3675CA] shrink-0 mt-0.5" />
        <div className="text-xs text-[#61738A] leading-relaxed">
          <strong className="text-[#172B4D]">Diagnostic & Treatment Invariant:</strong> MedResolve summarizes patient evidence and relevant published guidelines for physician review.
          <span className="block text-[#172B4D] mt-0.5">
            Discussion considerations are <strong>never</strong> presented as confirmed diagnoses, and this prototype does not generate treatment prescriptions, medical orders, or drug dosages.
          </span>
        </div>
      </div>

      {/* Section 1 & 2: Patient Reported vs Document Extracted Findings */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white border border-[#DFE7F1] rounded-lg p-5 space-y-3">
          <h2 className="text-xs font-bold uppercase tracking-wider text-[#3675CA] flex items-center space-x-2">
            <FileText className="w-4 h-4" />
            <span>1. Patient-Reported Observations ({patientReported.length})</span>
          </h2>
          <p className="text-[11px] text-[#61738A]">
            Subjective observations directly reported by the patient during intake:
          </p>
          <ul className="space-y-2">
            {patientReported.map((item) => (
              <li
                key={item.evidence_id}
                className="p-2.5 bg-[#F7F9FC] border border-[#DFE7F1] rounded-md text-xs flex justify-between"
              >
                <div>
                  <span className="font-semibold text-[#172B4D]">
                    {item.concept_name_en || item.concept}
                  </span>
                  <span className="text-[11px] text-[#61738A] block italic">
                    "{item.original_value}"
                  </span>
                </div>
                <span className="text-[11px] font-semibold text-[#26845A]">
                  {item.evidence_status}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="bg-white border border-[#DFE7F1] rounded-lg p-5 space-y-3">
          <h2 className="text-xs font-bold uppercase tracking-wider text-[#26845A] flex items-center space-x-2">
            <BookOpen className="w-4 h-4" />
            <span>2. Document-Extracted Findings ({docExtracted.length})</span>
          </h2>
          <p className="text-[11px] text-[#61738A]">
            Findings parsed from uploaded reports, blood tests, or EHR notes:
          </p>
          {docExtracted.length > 0 ? (
            <ul className="space-y-2">
              {docExtracted.map((item) => (
                <li
                  key={item.evidence_id}
                  className="p-2.5 bg-[#F7F9FC] border border-[#DFE7F1] rounded-md text-xs flex justify-between"
                >
                  <div>
                    <span className="font-semibold text-[#172B4D]">
                      {item.concept_name_en || item.concept}
                    </span>
                    <span className="text-[11px] text-[#61738A] block tabular-nums">
                      {String(item.normalized_value)} {item.unit || ''} (Doc: {item.source_document_id || 'Note'})
                    </span>
                  </div>
                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded self-start ${
                      item.user_confirmation_status.startsWith('CONFIRMED')
                        ? 'bg-[#E3FCEF] text-[#26845A]'
                        : 'bg-[#FFF0B3] text-[#A96B16]'
                    }`}
                  >
                    {item.user_confirmation_status}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-[#8A99AB] py-4 text-center">
              No document extractions in this case ledger.
            </p>
          )}
        </div>
      </div>

      {/* Generated Clinical Response Card */}
      <div className="bg-white border border-[#DFE7F1] rounded-lg p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-[#DFE7F1] pb-3">
          <div>
            <h2 className="text-sm font-bold text-[#172B4D]">
              Generated Clinical Synthesis Card
            </h2>
            <p className="text-xs text-[#61738A]">
              Bounded explanatory response synthesized strictly against retrieved medical guidelines
            </p>
          </div>
        </div>

        <div className="p-4 bg-[#FAF9F6] border border-[#DFE7F1] rounded-md font-sans text-xs text-[#172B4D] whitespace-pre-wrap leading-relaxed">
          {assessment.generated_text}
        </div>
      </div>

      {/* Claim-Level Verification Table */}
      <div className="bg-white border border-[#DFE7F1] rounded-lg p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#DFE7F1] pb-3 mb-4">
          <div>
            <h2 className="text-sm font-bold text-[#172B4D]">
              Claim-Level Verification Matrix ({assessment.verified_claims.length} Atomic Claims)
            </h2>
            <p className="text-xs text-[#61738A]">
              Decomposed assertions evaluated along dual axes: Reference Grounding vs Patient Consistency
            </p>
          </div>
          <div className="flex items-center space-x-2 text-xs">
            <span className="text-[#26845A] font-semibold tabular-nums">
              ✓ {supportedClaims.length} Supported
            </span>
            <span className="text-[#8A99AB]">|</span>
            <span className="text-[#A96B16] font-semibold tabular-nums">
              {insufficientClaims.length} Insufficient
            </span>
            <span className="text-[#8A99AB]">|</span>
            <span className="text-[#C23E4A] font-semibold tabular-nums">
              {contradictedClaims.length} Contradicted
            </span>
          </div>
        </div>

        {assessment.verified_claims.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left med-table">
              <thead>
                <tr>
                  <th>Claim ID & Text</th>
                  <th>Classification</th>
                  <th>Reference Grounding</th>
                  <th>Patient Ledger Consistency</th>
                  <th>Permitted</th>
                </tr>
              </thead>
              <tbody>
                {assessment.verified_claims.map((claim) => (
                  <tr key={claim.claim_id} className="hover:bg-[#F7F9FC]">
                    <td className="max-w-[300px]">
                      <span className="font-mono text-[10px] text-[#8A99AB] block">
                        {claim.claim_id}
                      </span>
                      <p className="text-xs text-[#172B4D] leading-snug">
                        {claim.claim_text}
                      </p>
                      {claim.cited_passage_ids.length > 0 && (
                        <div className="flex items-center space-x-1 mt-1">
                          <span className="text-[10px] text-[#8A99AB]">Citing:</span>
                          {claim.cited_passage_ids.map((id) => (
                            <span
                              key={id}
                              className="font-mono text-[10px] text-[#3675CA] bg-[#EAF2FC] px-1 rounded"
                            >
                              {id}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>

                    <td>
                      <span className="text-[11px] font-semibold text-[#61738A]">
                        {claim.claim_type.replace('_', ' ')}
                      </span>
                    </td>

                    <td>
                      <div className="space-y-0.5">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-[10px] font-semibold ${
                            claim.reference_verification_status === 'SUPPORTED_BY_SOURCE'
                              ? 'bg-[#E3FCEF] text-[#26845A] border border-[#ABF5D1]'
                              : claim.reference_verification_status === 'CONTRADICTED_BY_SOURCE'
                              ? 'bg-[#FFEBE6] text-[#C23E4A] border border-[#FFBDAD]'
                              : 'bg-[#FFF0B3] text-[#A96B16] border border-[#FFE380]'
                          }`}
                        >
                          {claim.reference_verification_status}
                        </span>
                        <p className="text-[10px] text-[#8A99AB] max-w-[200px] truncate">
                          {claim.reference_rationale}
                        </p>
                      </div>
                    </td>

                    <td>
                      <div className="space-y-0.5">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-[10px] font-semibold ${
                            claim.patient_consistency_status === 'CONSISTENT'
                              ? 'bg-[#E3FCEF] text-[#26845A]'
                              : claim.patient_consistency_status === 'CONTRADICTED_BY_LEDGER'
                              ? 'bg-[#FFEBE6] text-[#C23E4A]'
                              : 'bg-[#F1F5FA] text-[#61738A]'
                          }`}
                        >
                          {claim.patient_consistency_status}
                        </span>
                        <p className="text-[10px] text-[#8A99AB] max-w-[200px] truncate">
                          {claim.patient_consistency_rationale}
                        </p>
                      </div>
                    </td>

                    <td>
                      {claim.is_permitted_in_final ? (
                        <CheckCircle2 className="w-4 h-4 text-[#26845A]" />
                      ) : (
                        <XCircle className="w-4 h-4 text-[#C23E4A]" />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-[#8A99AB] py-6 text-center">
            No atomic claims generated (Policy executed early rule preemption or clarification question).
          </p>
        )}
      </div>
    </div>
  );
};

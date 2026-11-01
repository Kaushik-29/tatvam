import React from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CheckCircle,
  Clock,
  FileText,
  HelpCircle,
  OctagonAlert,
  Shield,
  TableProperties,
  User,
} from 'lucide-react';
import { PatientProfile, AssessmentResult } from '../types';
import { ScreenId } from '../components/Sidebar';

interface OverviewScreenProps {
  patient: PatientProfile | null;
  onNavigate: (screen: ScreenId) => void;
  onRunAssessment: () => void;
  isAssessing: boolean;
  latestAssessment: AssessmentResult | null;
}

export const OverviewScreen: React.FC<OverviewScreenProps> = ({
  patient,
  onNavigate,
  onRunAssessment,
  isAssessing,
  latestAssessment,
}) => {
  if (!patient) {
    return (
      <div className="p-8 text-center text-[#61738A]">
        Please select a patient from the top bar to view clinical overview.
      </div>
    );
  }

  const getActionBadge = (action: string) => {
    switch (action) {
      case 'EMERGENCY_OVERRIDE':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-xs font-semibold bg-[#FFEBE6] text-[#C23E4A] border border-[#FFBDAD]">
            <OctagonAlert className="w-3 h-3" />
            <span>EMERGENCY OVERRIDE</span>
          </span>
        );
      case 'ASK':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-xs font-semibold bg-[#DEEBFF] text-[#0065FF] border border-[#B3D4FF]">
            <HelpCircle className="w-3 h-3" />
            <span>CLARIFY (ASK)</span>
          </span>
        );
      case 'ABSTAIN_AND_NAVIGATE':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-xs font-semibold bg-[#FFF0B3] text-[#A96B16] border border-[#FFE380]">
            <AlertTriangle className="w-3 h-3" />
            <span>ABSTAIN & NAVIGATE</span>
          </span>
        );
      case 'EXPLAIN':
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-xs font-semibold bg-[#E3FCEF] text-[#26845A] border border-[#ABF5D1]">
            <CheckCircle className="w-3 h-3" />
            <span>EXPLAIN (VERIFIED)</span>
          </span>
        );
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Welcome / Case Context Banner */}
      <div className="bg-white border border-[#DFE7F1] rounded-lg p-5 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <span className="px-2 py-0.5 text-[10px] font-semibold bg-[#EAF2FC] text-[#3675CA] rounded border border-[#AFCFF2]">
                SYNTHETIC CASE STUDY
              </span>
              <span className="text-xs text-[#8A99AB]">Case ID: {patient.patient_id}</span>
            </div>
            <h1 className="text-xl font-bold text-[#172B4D] tracking-tight flex items-center space-x-2">
              <span>{patient.name}</span>
              <span className="text-sm font-normal text-[#61738A]">
                ({patient.age}y, {patient.sex})
              </span>
            </h1>
            <p className="text-xs text-[#61738A] max-w-3xl leading-relaxed">
              {patient.clinical_narrative}
            </p>
          </div>

          <div className="flex items-center space-x-3 shrink-0">
            <button
              onClick={() => onNavigate('profile')}
              className="px-3 py-1.5 border border-[#DFE7F1] hover:bg-[#F1F5FA] text-[#172B4D] rounded-md text-xs font-medium transition-colors"
            >
              Full Profile
            </button>
            <button
              onClick={onRunAssessment}
              disabled={isAssessing}
              className="px-4 py-1.5 bg-[#3675CA] hover:bg-[#265EAA] text-white rounded-md text-xs font-medium transition-colors flex items-center space-x-1.5 shadow-sm"
            >
              <Activity className="w-3.5 h-3.5" />
              <span>{isAssessing ? 'Assessing...' : 'Run Full Assessment'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Metric / Status Strip (Type, not tiles) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white border border-[#DFE7F1] rounded-lg p-4">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[#8A99AB]">
            Archetype Classification
          </span>
          <p className="text-sm font-semibold text-[#172B4D] mt-1 truncate">
            {patient.archetype_display}
          </p>
          <span className="text-[11px] text-[#61738A] block mt-0.5">
            Expected: {patient.expected_action}
          </span>
        </div>

        <div className="bg-white border border-[#DFE7F1] rounded-lg p-4">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[#8A99AB]">
            Active Evidence Items
          </span>
          <p className="text-2xl font-bold text-[#172B4D] mt-0.5 tabular-nums">
            {patient.evidence_count}
          </p>
          <button
            onClick={() => onNavigate('evidence-ledger')}
            className="text-[11px] text-[#3675CA] hover:underline flex items-center space-x-1 mt-0.5"
          >
            <span>View Ledger</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        </div>

        <div className="bg-white border border-[#DFE7F1] rounded-lg p-4">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[#8A99AB]">
            Detected Conflicts
          </span>
          <p className="text-2xl font-bold text-[#172B4D] mt-0.5 tabular-nums">
            {patient.conflicts_count}
          </p>
          <button
            onClick={() => onNavigate('conflicts')}
            className="text-[11px] text-[#3675CA] hover:underline flex items-center space-x-1 mt-0.5"
          >
            <span>Taxonomy Checks</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        </div>

        <div className="bg-white border border-[#DFE7F1] rounded-lg p-4">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[#8A99AB]">
            Uploaded Documents
          </span>
          <p className="text-2xl font-bold text-[#172B4D] mt-0.5 tabular-nums">
            {patient.documents_count}
          </p>
          <button
            onClick={() => onNavigate('documents')}
            className="text-[11px] text-[#3675CA] hover:underline flex items-center space-x-1 mt-0.5"
          >
            <span>Manage Records</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* Main Split: Latest Assessment Result & Quick Navigation */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Latest Assessment Outcome */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-white border border-[#DFE7F1] rounded-lg p-5">
            <div className="flex items-center justify-between border-b border-[#DFE7F1] pb-3 mb-4">
              <div>
                <h2 className="text-sm font-bold text-[#172B4D]">
                  Latest AI Health Assessment & Safety Routing
                </h2>
                <p className="text-xs text-[#61738A]">
                  Evidence-grounded action selection with dual-axis verification
                </p>
              </div>
              {latestAssessment && getActionBadge(latestAssessment.policy_decision.selected_action)}
            </div>

            {latestAssessment ? (
              <div className="space-y-4">
                <div className="p-3.5 bg-[#FAF9F6] border border-[#DFE7F1] rounded-md">
                  <div className="flex items-center justify-between text-xs text-[#61738A] mb-2">
                    <span className="font-semibold text-[#172B4D]">
                      Policy Decision Rationale:
                    </span>
                    <span className="tabular-nums">
                      Latency: {latestAssessment.generation_latency_seconds}s
                    </span>
                  </div>
                  <p className="text-xs text-[#172B4D] leading-relaxed">
                    {latestAssessment.policy_decision.reason}
                  </p>
                  <p className="text-[11px] text-[#61738A] mt-1.5">
                    {latestAssessment.policy_decision.detailed_rationale}
                  </p>
                </div>

                {/* Response Preview */}
                <div className="border border-[#DFE7F1] rounded-md p-4 bg-white">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-[#8A99AB] block mb-2">
                    Generated Clinical Card Preview
                  </span>
                  <div className="prose prose-xs max-w-none text-xs text-[#172B4D] whitespace-pre-wrap font-sans leading-relaxed">
                    {latestAssessment.generated_text.slice(0, 420)}
                    {latestAssessment.generated_text.length > 420 && '...'}
                  </div>
                  <div className="mt-3 pt-3 border-t border-[#DFE7F1] flex items-center justify-between">
                    <span className="text-[11px] text-[#8A99AB]">
                      Engine: {latestAssessment.execution_engine}
                    </span>
                    <button
                      onClick={() => onNavigate('ai-summary')}
                      className="text-xs text-[#3675CA] hover:underline font-medium"
                    >
                      View Full Summary & Verified Claims →
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-10 px-4">
                <Shield className="w-10 h-10 text-[#AFCFF2] mx-auto mb-2" />
                <h3 className="text-sm font-semibold text-[#172B4D]">
                  No Assessment Run Yet for this Case
                </h3>
                <p className="text-xs text-[#61738A] max-w-md mx-auto mt-1 mb-4">
                  Run an evidence assessment to trigger the 6-stage clinical reasoning pipeline, conflict detector, and selective safety policy.
                </p>
                <button
                  onClick={onRunAssessment}
                  disabled={isAssessing}
                  className="px-4 py-2 bg-[#3675CA] hover:bg-[#265EAA] text-white rounded-md text-xs font-medium transition-colors"
                >
                  Start Assessment Now
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Right Col: Quick Clinical Workflow Card */}
        <div className="space-y-4">
          <div className="bg-white border border-[#DFE7F1] rounded-lg p-5">
            <h3 className="text-sm font-bold text-[#172B4D] mb-1">
              Active Workflow Checklist
            </h3>
            <p className="text-xs text-[#61738A] mb-4">
              Patient data reconciliation progress
            </p>

            <ul className="space-y-3">
              <li className="flex items-start space-x-2.5 text-xs">
                <CheckCircle className="w-4 h-4 text-[#26845A] shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold text-[#172B4D]">Patient Intake Completed</span>
                  <p className="text-[11px] text-[#61738A]">Demographics and reported history loaded.</p>
                </div>
              </li>

              <li className="flex items-start space-x-2.5 text-xs">
                <CheckCircle className="w-4 h-4 text-[#26845A] shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold text-[#172B4D]">Structured Ledger Initialized</span>
                  <p className="text-[11px] text-[#61738A]">{patient.evidence_count} evidence items recorded with provenance.</p>
                </div>
              </li>

              <li className="flex items-start space-x-2.5 text-xs">
                {patient.conflicts_count > 0 ? (
                  <AlertTriangle className="w-4 h-4 text-[#A96B16] shrink-0 mt-0.5" />
                ) : (
                  <CheckCircle className="w-4 h-4 text-[#26845A] shrink-0 mt-0.5" />
                )}
                <div>
                  <span className="font-semibold text-[#172B4D]">Conflict Detection</span>
                  <p className="text-[11px] text-[#61738A]">
                    {patient.conflicts_count > 0
                      ? `${patient.conflicts_count} active discrepancies flagged.`
                      : 'No material conflicts detected.'}
                  </p>
                </div>
              </li>

              <li className="flex items-start space-x-2.5 text-xs">
                {latestAssessment ? (
                  <CheckCircle className="w-4 h-4 text-[#26845A] shrink-0 mt-0.5" />
                ) : (
                  <Clock className="w-4 h-4 text-[#8A99AB] shrink-0 mt-0.5" />
                )}
                <div>
                  <span className="font-semibold text-[#172B4D]">Safety Policy & Retrieval</span>
                  <p className="text-[11px] text-[#61738A]">
                    {latestAssessment
                      ? `Action: ${latestAssessment.policy_decision.selected_action}`
                      : 'Pending assessment execution.'}
                  </p>
                </div>
              </li>
            </ul>
          </div>

          {/* Research Transparency Notice */}
          <div className="bg-[#FAF9F6] border border-[#DFE7F1] rounded-lg p-4">
            <span className="text-[10px] font-semibold text-[#8A99AB] uppercase tracking-wider block mb-1">
              Research Notice
            </span>
            <p className="text-[11px] text-[#61738A] leading-relaxed">
              MedResolve is an investigational major project research prototype. It does not provide medical diagnoses or replace physician judgment.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

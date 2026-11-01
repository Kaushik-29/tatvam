import React, { useState, useEffect } from 'react';
import {
  History,
  Clock,
  CheckCircle,
  AlertTriangle,
  OctagonAlert,
  HelpCircle,
  FileText,
  ArrowRight,
  ShieldAlert,
} from 'lucide-react';
import { AssessmentResult } from '../types';
import { fetchAssessmentHistory } from '../api/client';

export const AssessmentHistoryScreen: React.FC = () => {
  const [history, setHistory] = useState<AssessmentResult[]>([]);
  const [selectedAssessment, setSelectedAssessment] = useState<AssessmentResult | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    setLoading(true);
    try {
      const data = await fetchAssessmentHistory();
      setHistory(data.history || []);
      if (data.history && data.history.length > 0) {
        setSelectedAssessment(data.history[0]);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const getActionBadge = (action: string) => {
    switch (action) {
      case 'EMERGENCY_OVERRIDE':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-[#FFEBE6] text-[#C23E4A] border border-[#FFBDAD]">
            <OctagonAlert className="w-2.5 h-2.5" />
            <span>EMERGENCY</span>
          </span>
        );
      case 'ASK':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-[#DEEBFF] text-[#0065FF] border border-[#B3D4FF]">
            <HelpCircle className="w-2.5 h-2.5" />
            <span>ASK</span>
          </span>
        );
      case 'ABSTAIN_AND_NAVIGATE':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-[#FFF0B3] text-[#A96B16] border border-[#FFE380]">
            <AlertTriangle className="w-2.5 h-2.5" />
            <span>ABSTAIN</span>
          </span>
        );
      case 'EXPLAIN':
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-[#E3FCEF] text-[#26845A] border border-[#ABF5D1]">
            <CheckCircle className="w-2.5 h-2.5" />
            <span>EXPLAIN</span>
          </span>
        );
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Title */}
      <div className="bg-white border border-[#DFE7F1] rounded-lg p-5">
        <h1 className="text-xl font-bold text-[#172B4D] flex items-center space-x-2">
          <History className="w-5 h-5 text-[#3675CA]" />
          <span>Clinical Assessment Execution History</span>
        </h1>
        <p className="text-xs text-[#61738A] mt-1">
          Traceable audit log of simulated patient assessments, safety overrides, and dual-axis claim verifications.
        </p>
      </div>

      {/* Non-Clinical Notice (PART 5.2 requirement) */}
      <div className="bg-[#FAF9F6] border border-[#DFE7F1] rounded-lg p-4 flex items-start space-x-3">
        <ShieldAlert className="w-5 h-5 text-[#3675CA] shrink-0 mt-0.5" />
        <div className="text-xs text-[#61738A] leading-relaxed">
          <strong className="text-[#172B4D]">Synthetic Audit Record:</strong> Every assessment in this log represents a synthetic benchmark simulation evaluated on CPU hardware. These outputs are research demonstrations and do not represent actual clinical care encounters.
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: History List */}
        <div className="bg-white border border-[#DFE7F1] rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-[#DFE7F1] pb-2">
            <span className="text-xs font-bold text-[#172B4D]">Recorded Assessments</span>
            <span className="text-[11px] text-[#8A99AB] tabular-nums">{history.length} records</span>
          </div>

          {history.length > 0 ? (
            <div className="space-y-2 max-h-[500px] overflow-y-auto">
              {history.map((item) => {
                const isSelected = selectedAssessment?.assessment_id === item.assessment_id;
                return (
                  <button
                    key={item.assessment_id}
                    onClick={() => setSelectedAssessment(item)}
                    className={`w-full text-left p-3 rounded-lg border text-xs transition-colors flex flex-col space-y-1 ${
                      isSelected
                        ? 'border-[#3675CA] bg-[#EAF2FC]/40 font-medium'
                        : 'border-[#DFE7F1] bg-white hover:bg-[#F7F9FC]'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-[#172B4D]">
                        Patient: {item.patient_id}
                      </span>
                      {getActionBadge(item.policy_decision.selected_action)}
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-[#8A99AB]">
                      <span>{item.timestamp.slice(0, 16).replace('T', ' ')}</span>
                      <span className="tabular-nums">{item.generation_latency_seconds}s</span>
                    </div>
                  </button>
                );
              })}
            </div>
          ) : (
            <p className="text-xs text-[#8A99AB] text-center py-8">
              No previous assessment runs logged in this session yet.
            </p>
          )}
        </div>

        {/* Right: Selected Assessment Details */}
        <div className="lg:col-span-2">
          {selectedAssessment ? (
            <div className="bg-white border border-[#DFE7F1] rounded-lg p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-[#DFE7F1] pb-3">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="font-mono text-xs text-[#8A99AB]">
                      {selectedAssessment.assessment_id}
                    </span>
                    {getActionBadge(selectedAssessment.policy_decision.selected_action)}
                  </div>
                  <h3 className="text-sm font-bold text-[#172B4D] mt-1">
                    Assessment for Case {selectedAssessment.patient_id}
                  </h3>
                </div>
                <div className="text-right text-xs">
                  <span className="text-[#8A99AB] block text-[10px]">Execution Latency</span>
                  <span className="font-semibold text-[#172B4D] tabular-nums">
                    {selectedAssessment.generation_latency_seconds} seconds
                  </span>
                </div>
              </div>

              {/* Rationale */}
              <div className="p-3 bg-[#FAF9F6] border border-[#DFE7F1] rounded-md text-xs space-y-1">
                <span className="font-semibold text-[#172B4D] block">
                  Policy Decision Rationale:
                </span>
                <p className="text-[#61738A] leading-relaxed">
                  {selectedAssessment.policy_decision.reason}
                </p>
                <p className="text-[11px] text-[#8A99AB]">
                  {selectedAssessment.policy_decision.detailed_rationale}
                </p>
              </div>

              {/* Generated Text */}
              <div>
                <span className="text-[11px] font-semibold uppercase tracking-wider text-[#8A99AB] block mb-2">
                  Generated Clinical Synthesis
                </span>
                <div className="p-4 bg-white border border-[#DFE7F1] rounded-md text-xs text-[#172B4D] whitespace-pre-wrap font-sans leading-relaxed max-h-72 overflow-y-auto">
                  {selectedAssessment.generated_text}
                </div>
              </div>

              {/* Verified Claims Count */}
              <div className="pt-2 border-t border-[#DFE7F1] flex items-center justify-between text-xs text-[#61738A]">
                <span>Engine: {selectedAssessment.execution_engine}</span>
                <span>
                  {selectedAssessment.verified_claims.length} atomic claims evaluated
                </span>
              </div>
            </div>
          ) : (
            <div className="bg-white border border-[#DFE7F1] rounded-lg p-10 text-center text-xs text-[#8A99AB]">
              Select an assessment record on the left to inspect its detailed outputs.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

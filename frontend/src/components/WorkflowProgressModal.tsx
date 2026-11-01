import React from 'react';
import {
  Activity,
  CheckCircle2,
  Clock,
  Shield,
  AlertTriangle,
  FileSearch,
  Cpu,
  Lock,
} from 'lucide-react';

export interface WorkflowStage {
  code: string;
  name: string;
  description: string;
  status: 'PENDING' | 'ACTIVE' | 'COMPLETED';
  timestamp?: string;
}

interface WorkflowProgressModalProps {
  isOpen: boolean;
  stages: WorkflowStage[];
  currentStageCode: string;
  elapsedSeconds: number;
}

export const WorkflowProgressModal: React.FC<WorkflowProgressModalProps> = ({
  isOpen,
  stages,
  currentStageCode,
  elapsedSeconds,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#172B4D]/30 backdrop-blur-xs p-4 animate-in fade-in duration-200">
      <div className="bg-white border border-[#DFE7F1] rounded-xl shadow-2xl max-w-lg w-full overflow-hidden">
        {/* Modal Header */}
        <div className="bg-[#FAF9F6] border-b border-[#DFE7F1] px-5 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="w-7 h-7 rounded-md bg-[#3675CA] flex items-center justify-center text-white">
              <Cpu className="w-4 h-4 animate-pulse" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-[#172B4D]">
                Executing Clinical Reasoning Pipeline
              </h3>
              <p className="text-[11px] text-[#61738A]">
                Local CPU inference (~16s) with claim verification gating
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-1.5 px-2.5 py-1 bg-[#EAF2FC] text-[#3675CA] rounded-full text-xs font-semibold tabular-nums">
            <Clock className="w-3.5 h-3.5" />
            <span>{elapsedSeconds}s</span>
          </div>
        </div>

        {/* Safety Gate Banner (PART 7 Requirement) */}
        <div className="bg-[#FFF0B3]/40 border-b border-[#FFE380] px-5 py-2.5 flex items-start space-x-2">
          <Lock className="w-4 h-4 text-[#A96B16] shrink-0 mt-0.5" />
          <p className="text-[11px] text-[#A96B16] leading-tight">
            <strong>Safety Buffer Active:</strong> Raw LLM tokens are buffered internally. Unverified medical claims are never streamed to the interface until dual-axis claim verification and emergency overrides are validated.
          </p>
        </div>

        {/* Workflow Stages List */}
        <div className="p-5 space-y-3">
          {stages.map((st, idx) => {
            const isCompleted = st.status === 'COMPLETED';
            const isActive = st.status === 'ACTIVE';

            return (
              <div
                key={st.code}
                className={`flex items-start space-x-3 p-2.5 rounded-lg border transition-all ${
                  isActive
                    ? 'bg-[#EAF2FC]/50 border-[#3675CA] shadow-xs'
                    : isCompleted
                    ? 'bg-white border-[#DFE7F1]'
                    : 'bg-[#F7F9FC] border-transparent opacity-60'
                }`}
              >
                {/* Step indicator */}
                <div className="mt-0.5 shrink-0">
                  {isCompleted ? (
                    <CheckCircle2 className="w-4 h-4 text-[#26845A]" />
                  ) : isActive ? (
                    <div className="w-4 h-4 rounded-full border-2 border-[#3675CA] border-t-transparent animate-spin" />
                  ) : (
                    <div className="w-4 h-4 rounded-full border border-[#8A99AB] flex items-center justify-center text-[9px] text-[#8A99AB] font-semibold tabular-nums">
                      {idx + 1}
                    </div>
                  )}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span
                      className={`text-xs font-semibold ${
                        isActive
                          ? 'text-[#3675CA]'
                          : isCompleted
                          ? 'text-[#172B4D]'
                          : 'text-[#8A99AB]'
                      }`}
                    >
                      {st.name}
                    </span>
                    {st.timestamp && (
                      <span className="text-[10px] text-[#8A99AB] tabular-nums">
                        {st.timestamp}
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-[#61738A] mt-0.5 leading-snug">
                    {st.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>

        {/* Progress Bar */}
        <div className="px-5 pb-4">
          <div className="h-1.5 w-full bg-[#F1F5FA] rounded-full overflow-hidden">
            <div
              className="h-full bg-[#3675CA] transition-all duration-300 rounded-full"
              style={{
                width: `${
                  (stages.filter((s) => s.status === 'COMPLETED').length / stages.length) * 100
                }%`,
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

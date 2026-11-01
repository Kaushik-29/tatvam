import React, { useState, useEffect } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  Scale,
  Clock,
  FileQuestion,
  HelpCircle,
  Layers,
  ShieldCheck,
  ShieldAlert,
} from 'lucide-react';
import { ConflictItem, PatientProfile } from '../types';
import { fetchConflicts } from '../api/client';

interface ConflictDetectionScreenProps {
  patient: PatientProfile | null;
}

export const ConflictDetectionScreen: React.FC<ConflictDetectionScreenProps> = ({ patient }) => {
  const [conflicts, setConflicts] = useState<ConflictItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (patient) {
      loadConflicts();
    }
  }, [patient]);

  const loadConflicts = async () => {
    if (!patient) return;
    setLoading(true);
    try {
      const data = await fetchConflicts(patient.patient_id);
      setConflicts(data.conflicts);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  if (!patient) {
    return (
      <div className="p-8 text-center text-[#61738A]">
        Please select a patient to view conflict detection results.
      </div>
    );
  }

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'VALUE_OR_UNIT_DISCREPANCY':
        return <Scale className="w-4 h-4 text-[#C23E4A]" />;
      case 'TEMPORAL_DISCREPANCY':
        return <Clock className="w-4 h-4 text-[#A96B16]" />;
      case 'SOURCE_STATEMENT_DISAGREEMENT':
        return <AlertTriangle className="w-4 h-4 text-[#C23E4A]" />;
      case 'LOW_CONFIDENCE_EXTRACTION':
        return <FileQuestion className="w-4 h-4 text-[#0065FF]" />;
      case 'MISSING_INFORMATION':
        return <HelpCircle className="w-4 h-4 text-[#A96B16]" />;
      case 'ENTERED_OPINION_DISAGREEMENT':
      default:
        return <Layers className="w-4 h-4 text-[#3675CA]" />;
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Title */}
      <div className="bg-white border border-[#DFE7F1] rounded-lg p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-[10px] font-semibold bg-[#FFEBE6] text-[#C23E4A] px-2 py-0.5 rounded border border-[#FFBDAD]">
                TAXONOMY AUDIT
              </span>
              <span className="text-xs text-[#8A99AB]">Case #{patient.patient_id}</span>
            </div>
            <h1 className="text-xl font-bold text-[#172B4D] flex items-center space-x-2 mt-1">
              <AlertCircle className="w-5 h-5 text-[#C23E4A]" />
              <span>Multi-Source Conflict & Discrepancy Detection</span>
            </h1>
            <p className="text-xs text-[#61738A]">
              Deterministic rule-based identification of observable data contradictions across the 6-category MedResolve conflict taxonomy.
            </p>
          </div>

          <div className="flex items-center space-x-2 text-xs">
            <span className="px-3 py-1 bg-[#F1F5FA] border border-[#DFE7F1] rounded-md font-semibold text-[#172B4D] tabular-nums">
              {conflicts.length} Total Discrepancies
            </span>
            <span className="px-3 py-1 bg-[#FFEBE6] border border-[#FFBDAD] rounded-md font-semibold text-[#C23E4A] tabular-nums">
              {conflicts.filter((c) => c.is_material).length} Material
            </span>
          </div>
        </div>
      </div>

      {/* Non-Arbitration Rule Banner (PART 5.2 requirement) */}
      <div className="bg-[#FAF9F6] border border-[#DFE7F1] rounded-lg p-4 flex items-start space-x-3">
        <ShieldAlert className="w-5 h-5 text-[#A96B16] shrink-0 mt-0.5" />
        <div className="text-xs text-[#61738A] leading-relaxed">
          <strong className="text-[#172B4D]">Deterministic Non-Arbitration Protocol:</strong> MedResolve identifies observable discrepancies between sources without declaring clinical ground truth or selecting which clinician is correct.
          <span className="block text-[#172B4D] mt-0.5">
            Temporal Rule: An older observation is <em>never</em> treated as invalid merely because of elapsed time. Value Rule: Divergent opinions trigger{' '}
            <span className="text-[#A96B16] font-semibold">ABSTAIN_AND_NAVIGATE</span> rather than automated compromise.
          </span>
        </div>
      </div>

      {/* Conflict List */}
      {conflicts.length > 0 ? (
        <div className="space-y-4">
          {conflicts.map((c) => (
            <div
              key={c.conflict_id}
              className={`bg-white border rounded-lg p-5 shadow-xs transition-all ${
                c.is_material ? 'border-[#C23E4A]/30 bg-[#FFEBE6]/5' : 'border-[#DFE7F1]'
              }`}
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#DFE7F1] pb-3 mb-3">
                <div className="flex items-center space-x-2">
                  <div className="p-1.5 rounded-md bg-[#F1F5FA]">
                    {getCategoryIcon(c.conflict_category)}
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-[#172B4D]">{c.category_name}</h3>
                    <span className="text-[11px] font-mono text-[#8A99AB]">{c.conflict_category}</span>
                  </div>
                </div>

                <div className="flex items-center space-x-2 text-xs">
                  <span
                    className={`px-2 py-0.5 rounded font-semibold text-[10px] ${
                      c.clinical_risk === 'HIGH'
                        ? 'bg-[#FFEBE6] text-[#C23E4A] border border-[#FFBDAD]'
                        : 'bg-[#FFF0B3] text-[#A96B16] border border-[#FFE380]'
                    }`}
                  >
                    Risk: {c.clinical_risk}
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-[#F1F5FA] text-[#61738A] border border-[#DFE7F1]">
                    Status: {c.resolution_status}
                  </span>
                </div>
              </div>

              {/* Conflict Description */}
              <div className="text-xs text-[#172B4D] leading-relaxed mb-3">
                <p className="font-medium text-[#172B4D]">{c.description}</p>
              </div>

              {/* Involved Evidence / Opinion IDs */}
              <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-[#DFE7F1] text-[11px]">
                <span className="text-[#8A99AB] font-medium">Involved Evidence Records:</span>
                {c.involved_evidence_ids.map((id) => (
                  <span
                    key={id}
                    className="font-mono px-1.5 py-0.5 rounded bg-[#F1F5FA] border border-[#DFE7F1] text-[#172B4D]"
                  >
                    {id}
                  </span>
                ))}
                <span className="text-[#8A99AB] ml-auto">
                  Action Pathway:{' '}
                  <strong className="text-[#3675CA]">{c.resolution_action}</strong>
                </span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white border border-[#DFE7F1] rounded-lg p-10 text-center">
          <ShieldCheck className="w-12 h-12 text-[#26845A] mx-auto mb-2" />
          <h3 className="text-sm font-semibold text-[#172B4D]">
            Zero Active Conflicts Detected
          </h3>
          <p className="text-xs text-[#61738A] max-w-md mx-auto mt-1">
            All documented patient observations, vital signs, and source records in this case ledger are mutually compatible without contradictory values or timeline inversions.
          </p>
        </div>
      )}
    </div>
  );
};

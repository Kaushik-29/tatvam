import React, { useState } from 'react';
import {
  TableProperties,
  Filter,
  CheckCircle,
  AlertCircle,
  FileText,
  User,
  Activity,
  Layers,
  ChevronDown,
} from 'lucide-react';
import { EvidenceItem, ClinicianOpinion, PatientProfile } from '../types';

interface EvidenceLedgerScreenProps {
  patient: PatientProfile | null;
  items: EvidenceItem[];
  opinions: ClinicianOpinion[];
  onRefreshLedger: () => void;
}

export const EvidenceLedgerScreen: React.FC<EvidenceLedgerScreenProps> = ({
  patient,
  items,
  opinions,
}) => {
  const [filterSource, setFilterSource] = useState<string>('ALL');
  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [filterConfirmation, setFilterConfirmation] = useState<string>('ALL');

  if (!patient) {
    return (
      <div className="p-8 text-center text-[#61738A]">
        Please select a patient to view the structured evidence ledger.
      </div>
    );
  }

  // Filter items
  const filteredItems = items.filter((item) => {
    if (filterSource !== 'ALL' && item.source_type !== filterSource) return false;
    if (filterStatus !== 'ALL' && item.evidence_status !== filterStatus) return false;
    if (filterConfirmation !== 'ALL') {
      if (filterConfirmation === 'CONFIRMED' && !item.user_confirmation_status.startsWith('CONFIRMED')) return false;
      if (filterConfirmation === 'UNCONFIRMED' && item.user_confirmation_status !== 'UNCONFIRMED') return false;
    }
    return true;
  });

  const getSourceBadge = (source: string) => {
    switch (source) {
      case 'PATIENT_REPORTED':
        return (
          <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-[#EAF2FC] text-[#3675CA] border border-[#AFCFF2]">
            <User className="w-2.5 h-2.5" />
            <span>Patient Reported</span>
          </span>
        );
      case 'LABORATORY_REPORT':
        return (
          <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-[#E3FCEF] text-[#26845A] border border-[#ABF5D1]">
            <Activity className="w-2.5 h-2.5" />
            <span>Lab Report</span>
          </span>
        );
      case 'EHR_EXTRACTED_NOTE':
        return (
          <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-[#F1F5FA] text-[#172B4D] border border-[#DFE7F1]">
            <FileText className="w-2.5 h-2.5" />
            <span>EHR Note</span>
          </span>
        );
      case 'PRIOR_PRESCRIPTION':
        return (
          <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-[#FAF9F6] text-[#A96B16] border border-[#FFE380]">
            <span>Prior Rx</span>
          </span>
        );
      default:
        return (
          <span className="px-1.5 py-0.5 rounded text-[10px] bg-gray-100 text-gray-700">
            {source}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Title */}
      <div className="bg-white border border-[#DFE7F1] rounded-lg p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-[10px] font-semibold bg-[#EAF2FC] text-[#3675CA] px-2 py-0.5 rounded border border-[#AFCFF2]">
                CORE EVIDENCE REPOSITORY
              </span>
              <span className="text-xs text-[#8A99AB]">Case #{patient.patient_id}</span>
            </div>
            <h1 className="text-xl font-bold text-[#172B4D] flex items-center space-x-2 mt-1">
              <TableProperties className="w-5 h-5 text-[#3675CA]" />
              <span>Patient Evidence Ledger</span>
            </h1>
            <p className="text-xs text-[#61738A]">
              Structured chronological repository preserving source provenance, timestamps, extraction uncertainty, and raw-to-normalized traceability.
            </p>
          </div>

          <div className="flex items-center space-x-3 text-xs">
            <div className="text-right">
              <span className="text-[11px] text-[#8A99AB] block">Total Evidence</span>
              <span className="text-sm font-bold text-[#172B4D] tabular-nums">{items.length} items</span>
            </div>
            <div className="h-6 w-[1px] bg-[#DFE7F1]" />
            <div className="text-right">
              <span className="text-[11px] text-[#8A99AB] block">Clinician Opinions</span>
              <span className="text-sm font-bold text-[#3675CA] tabular-nums">{opinions.length} records</span>
            </div>
          </div>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-white border border-[#DFE7F1] rounded-lg p-3.5 flex flex-wrap items-center gap-3 text-xs shadow-xs">
        <div className="flex items-center space-x-1.5 text-[#61738A] font-semibold">
          <Filter className="w-3.5 h-3.5" />
          <span>Filters:</span>
        </div>

        {/* Source Filter */}
        <select
          value={filterSource}
          onChange={(e) => setFilterSource(e.target.value)}
          className="p-1.5 rounded-md border border-[#DFE7F1] bg-white text-[#172B4D] outline-none"
        >
          <option value="ALL">All Sources</option>
          <option value="PATIENT_REPORTED">Patient Reported</option>
          <option value="LABORATORY_REPORT">Laboratory Reports</option>
          <option value="EHR_EXTRACTED_NOTE">EHR Documents</option>
          <option value="PRIOR_PRESCRIPTION">Prior Prescriptions</option>
        </select>

        {/* Confirmation Filter */}
        <select
          value={filterConfirmation}
          onChange={(e) => setFilterConfirmation(e.target.value)}
          className="p-1.5 rounded-md border border-[#DFE7F1] bg-white text-[#172B4D] outline-none"
        >
          <option value="ALL">All Confirmation States</option>
          <option value="CONFIRMED">Verified / Confirmed</option>
          <option value="UNCONFIRMED">Unconfirmed Only</option>
        </select>

        {/* Assertion Status */}
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="p-1.5 rounded-md border border-[#DFE7F1] bg-white text-[#172B4D] outline-none"
        >
          <option value="ALL">All Assertions</option>
          <option value="PRESENT">PRESENT Only</option>
          <option value="ABSENT">ABSENT Only (Pertinent Negatives)</option>
        </select>

        <span className="text-[#8A99AB] text-[11px] ml-auto tabular-nums">
          Showing {filteredItems.length} of {items.length} records
        </span>
      </div>

      {/* Evidence Table */}
      <div className="bg-white border border-[#DFE7F1] rounded-lg overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left med-table min-w-[720px]">
            <thead>
              <tr>
                <th>ID</th>
                <th>Observation Concept</th>
                <th>Normalized Value</th>
                <th>Raw Source Text</th>
                <th>Provenance Source</th>
                <th>Method</th>
                <th>Conf.</th>
                <th>Status</th>
                <th>Recorded Time</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.length > 0 ? (
                filteredItems.map((item) => (
                  <tr key={item.evidence_id} className="hover:bg-[#F7F9FC] transition-colors">
                    <td className="font-mono text-[11px] text-[#8A99AB]">{item.evidence_id}</td>

                    <td>
                      <span className="font-semibold text-xs text-[#172B4D] block">
                        {item.concept_name_en || item.concept}
                      </span>
                      <span className="text-[10px] text-[#8A99AB] font-mono">
                        {item.concept}
                      </span>
                    </td>

                    <td className="tabular-nums font-semibold text-xs text-[#172B4D]">
                      {String(item.normalized_value)} {item.unit || ''}
                    </td>

                    <td className="max-w-[180px]">
                      <span className="text-xs text-[#61738A] italic truncate block">
                        "{item.original_value || 'None'}"
                      </span>
                    </td>

                    <td>{getSourceBadge(item.source_type)}</td>

                    <td>
                      <span className="text-[11px] text-[#61738A]">
                        {item.extraction_method.replace('_', ' ')}
                      </span>
                    </td>

                    <td>
                      <span className="tabular-nums font-medium text-xs">
                        {(item.extraction_confidence * 100).toFixed(0)}%
                      </span>
                    </td>

                    <td>
                      <div className="flex flex-col space-y-0.5">
                        <span
                          className={`inline-block px-1.5 py-0.2 rounded text-[10px] font-semibold text-center ${
                            item.evidence_status === 'PRESENT'
                              ? 'bg-[#E3FCEF] text-[#26845A]'
                              : 'bg-[#F1F5FA] text-[#61738A]'
                          }`}
                        >
                          {item.evidence_status}
                        </span>
                        <span className="text-[9px] text-[#8A99AB] text-center">
                          {item.user_confirmation_status.startsWith('CONFIRMED')
                            ? 'Confirmed'
                            : 'Unconfirmed'}
                        </span>
                      </div>
                    </td>

                    <td className="tabular-nums text-[11px] text-[#61738A] whitespace-nowrap">
                      {item.recorded_timestamp.slice(0, 16).replace('T', ' ')}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={9} className="text-center py-8 text-xs text-[#8A99AB]">
                    No evidence items match the selected filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Clinician Opinions Sub-Ledger */}
      {opinions.length > 0 && (
        <div className="bg-white border border-[#DFE7F1] rounded-lg p-5">
          <div className="border-b border-[#DFE7F1] pb-3 mb-4">
            <h2 className="text-sm font-bold text-[#172B4D] flex items-center space-x-2">
              <Layers className="w-4 h-4 text-[#3675CA]" />
              <span>Documented Clinician & Specialist Impressions ({opinions.length})</span>
            </h2>
            <p className="text-xs text-[#61738A]">
              External entered clinical opinions. Preserved with stated clinician ID and specialty.
            </p>
          </div>

          <div className="space-y-3">
            {opinions.map((op) => (
              <div
                key={op.opinion_id}
                className="p-3.5 border border-[#DFE7F1] rounded-lg bg-[#FAF9F6] flex flex-col md:flex-row md:items-center justify-between gap-3"
              >
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="font-semibold text-xs text-[#172B4D]">
                      {op.diagnostic_impression}
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-[#EAF2FC] text-[#3675CA] border border-[#AFCFF2]">
                      {op.clinician_specialty}
                    </span>
                  </div>
                  <p className="text-xs text-[#61738A] mt-1">
                    Recorded by <strong className="text-[#172B4D]">{op.clinician_id}</strong> on{' '}
                    <span className="tabular-nums">{op.recorded_timestamp.slice(0, 10)}</span>
                  </p>
                  {op.notes && (
                    <p className="text-[11px] text-[#61738A] italic mt-1">
                      Clinical Notes: "{op.notes}"
                    </p>
                  )}
                </div>

                <div className="text-right text-xs shrink-0">
                  <span className="text-[#8A99AB] block text-[11px]">Certainty</span>
                  <span className="font-semibold text-[#172B4D]">{op.confidence_assessment}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

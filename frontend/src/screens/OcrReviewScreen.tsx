import React, { useState, useEffect } from 'react';
import {
  ScanText,
  Check,
  X,
  AlertTriangle,
  CheckCircle2,
  FileText,
  Shield,
  HelpCircle,
  Edit2,
  Eye,
  FileSearch,
  ExternalLink,
  Save,
  RotateCcw,
} from 'lucide-react';
import { EvidenceItem, PatientProfile } from '../types';
import {
  fetchPatientDocuments,
  fetchDocumentDetails,
  updateLedgerItem,
  getDocumentFileUrl,
} from '../api/client';

interface OcrReviewScreenProps {
  patient: PatientProfile | null;
  ledgerItems: EvidenceItem[];
  onRefreshLedger: () => void;
}

interface EditModalState {
  item: EvidenceItem;
  value: string;
  unit: string;
  notes: string;
}

export const OcrReviewScreen: React.FC<OcrReviewScreenProps> = ({
  patient,
  ledgerItems,
  onRefreshLedger,
}) => {
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<any[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [selectedDocDetail, setSelectedDocDetail] = useState<any | null>(null);
  const [loadingDocDetail, setLoadingDocDetail] = useState(false);
  const [showDocPreview, setShowDocPreview] = useState(false);
  const [editModal, setEditModal] = useState<EditModalState | null>(null);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);

  useEffect(() => {
    if (patient) {
      loadDocuments();
    }
  }, [patient]);

  useEffect(() => {
    if (patient && selectedDocId) {
      loadDocDetail(selectedDocId);
    } else {
      setSelectedDocDetail(null);
    }
  }, [patient, selectedDocId]);

  const loadDocuments = async () => {
    if (!patient) return;
    try {
      const data = await fetchPatientDocuments(patient.patient_id);
      setDocuments(data.documents || []);
      if (data.documents && data.documents.length > 0 && !selectedDocId) {
        setSelectedDocId(data.documents[0].document_id);
      }
    } catch (err) {
      console.error('Error fetching documents:', err);
    }
  };

  const loadDocDetail = async (docId: string) => {
    if (!patient) return;
    setLoadingDocDetail(true);
    try {
      const detail = await fetchDocumentDetails(patient.patient_id, docId);
      setSelectedDocDetail(detail);
    } catch (err) {
      console.error('Error fetching document detail:', err);
    } finally {
      setLoadingDocDetail(false);
    }
  };

  if (!patient) {
    return (
      <div className="p-8 text-center text-[#61738A]">
        Please select a patient to review OCR extractions.
      </div>
    );
  }

  // Filter OCR / EHR extracted items
  const ocrItems = ledgerItems.filter(
    (item) =>
      item.extraction_method === 'OCR_EXTRACTION' ||
      item.source_type === 'EHR_EXTRACTED_NOTE' ||
      item.source_type === 'LABORATORY_REPORT' ||
      item.source_type === 'PRIOR_PRESCRIPTION' ||
      Boolean(item.source_document_id)
  );

  const handleAction = async (
    evidenceId: string,
    action: 'CONFIRM' | 'REJECT' | 'CORRECT' | 'MARK_UNREADABLE',
    correctedVal?: string,
    correctedUnit?: string,
    notes?: string
  ) => {
    setUpdatingId(evidenceId);
    setActionFeedback(null);
    try {
      await updateLedgerItem(
        patient.patient_id,
        evidenceId,
        action,
        correctedVal,
        correctedUnit,
        notes
      );
      setActionFeedback(`Successfully applied '${action}' to observation.`);
      onRefreshLedger();
    } catch (err: any) {
      console.error(err);
      setActionFeedback(`Action failed: ${err.message}`);
    } finally {
      setUpdatingId(null);
      setEditModal(null);
    }
  };

  // Helper to parse notes metadata if present
  const parseNotesMetadata = (notes?: string) => {
    if (!notes) return {};
    try {
      if (notes.startsWith('{') && notes.endsWith('}')) {
        return JSON.parse(notes);
      }
    } catch {
      // plain text note
    }
    return { plainNote: notes };
  };

  const unconfirmedCount = ocrItems.filter(
    (i) => i.user_confirmation_status === 'UNCONFIRMED'
  ).length;
  const confirmedCount = ocrItems.filter((i) =>
    i.user_confirmation_status.startsWith('CONFIRMED')
  ).length;
  const rejectedCount = ocrItems.filter(
    (i) =>
      i.user_confirmation_status === 'REJECTED_BY_PATIENT' ||
      i.evidence_status === 'ABSENT' ||
      i.evidence_status === 'UNKNOWN'
  ).length;

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Title & Stats */}
      <div className="bg-white border border-[#DFE7F1] rounded-lg p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-[10px] font-semibold bg-[#EAF2FC] text-[#3675CA] px-2 py-0.5 rounded border border-[#AFCFF2]">
                PHASE 5.4 REAL OCR PIPELINE
              </span>
              <span className="text-xs text-[#8A99AB]">RapidOCR ONNX & PyMuPDF</span>
            </div>
            <h1 className="text-xl font-bold text-[#172B4D] flex items-center space-x-2 mt-1">
              <ScanText className="w-5 h-5 text-[#3675CA]" />
              <span>OCR Extraction & Document Review</span>
            </h1>
            <p className="text-xs text-[#61738A] mt-1">
              Verify optical character extractions, reconcile unit provenance, and review document evidence against the active patient ledger.
            </p>
          </div>
          <div className="flex items-center space-x-2 text-xs">
            <span className="px-2.5 py-1 rounded-md bg-[#FFF0B3] text-[#A96B16] font-semibold border border-[#FFE380] tabular-nums">
              {unconfirmedCount} Unconfirmed
            </span>
            <span className="px-2.5 py-1 rounded-md bg-[#E3FCEF] text-[#26845A] font-semibold border border-[#ABF5D1] tabular-nums">
              {confirmedCount} Confirmed
            </span>
            {rejectedCount > 0 && (
              <span className="px-2.5 py-1 rounded-md bg-[#FFEBE6] text-[#C23E4A] font-semibold border border-[#FFBDAD] tabular-nums">
                {rejectedCount} Rejected/Unreadable
              </span>
            )}
          </div>
        </div>
      </div>

      {actionFeedback && (
        <div className="p-3 bg-[#EAF2FC] border border-[#AFCFF2] rounded-md text-xs text-[#3675CA] flex items-center justify-between">
          <span>{actionFeedback}</span>
          <button
            onClick={() => setActionFeedback(null)}
            className="text-xs font-semibold text-[#3675CA] hover:underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Strict Research & Safety Invariant Notice */}
      <div className="bg-[#FAF9F6] border border-[#DFE7F1] rounded-lg p-4 flex items-start space-x-3">
        <AlertTriangle className="w-5 h-5 text-[#A96B16] shrink-0 mt-0.5" />
        <div className="text-xs text-[#61738A] leading-relaxed">
          <strong className="text-[#172B4D]">Clinical Provenance Invariant:</strong> High OCR confidence does not imply clinical correctness. Unconfirmed extractions remain strictly unconfirmed and are not treated as verified patient facts. The selective action policy will trigger an <span className="text-[#0065FF] font-semibold">ASK</span> clarification inquiry if unconfirmed findings are required for assessment synthesis. Missing or inferred units require explicit clinician or patient confirmation.
        </div>
      </div>

      {/* Document Ingestion & Original Text Preview Section */}
      {documents.length > 0 && (
        <div className="bg-white border border-[#DFE7F1] rounded-lg p-4 space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#DFE7F1] pb-3">
            <div className="flex items-center space-x-2">
              <FileSearch className="w-4 h-4 text-[#3675CA]" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-[#172B4D]">
                Ingested Source Document Inspector
              </h2>
            </div>
            <div className="flex items-center space-x-2">
              <select
                value={selectedDocId || ''}
                onChange={(e) => setSelectedDocId(e.target.value)}
                className="text-xs p-1.5 rounded border border-[#DFE7F1] bg-white text-[#172B4D] outline-none"
              >
                {documents.map((d) => (
                  <option key={d.document_id} value={d.document_id}>
                    {d.filename} ({d.document_type})
                  </option>
                ))}
              </select>
              <button
                onClick={() => setShowDocPreview(!showDocPreview)}
                className="px-2.5 py-1 bg-[#F1F5FA] hover:bg-[#EAF2FC] text-[#3675CA] border border-[#DFE7F1] rounded text-xs font-medium flex items-center space-x-1 transition-colors"
              >
                <Eye className="w-3 h-3" />
                <span>{showDocPreview ? 'Hide Raw Text' : 'View Raw Text'}</span>
              </button>
              {selectedDocId && (
                <a
                  href={getDocumentFileUrl(patient.patient_id, selectedDocId)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-2.5 py-1 bg-[#F1F5FA] hover:bg-[#EAF2FC] text-[#3675CA] border border-[#DFE7F1] rounded text-xs font-medium flex items-center space-x-1 transition-colors"
                  title="Open source file in new tab"
                >
                  <ExternalLink className="w-3 h-3" />
                  <span>Open File</span>
                </a>
              )}
            </div>
          </div>

          {selectedDocDetail && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs py-1 text-[#61738A]">
              <div>
                <span className="text-[10px] uppercase text-[#8A99AB] block">File Name</span>
                <span className="font-semibold text-[#172B4D] truncate block">
                  {selectedDocDetail.filename}
                </span>
              </div>
              <div>
                <span className="text-[10px] uppercase text-[#8A99AB] block">Format & Pages</span>
                <span className="font-semibold text-[#172B4D]">
                  {selectedDocDetail.document_type} ({selectedDocDetail.total_pages} pg)
                </span>
              </div>
              <div>
                <span className="text-[10px] uppercase text-[#8A99AB] block">Processing Latency</span>
                <span className="font-semibold text-[#26845A] tabular-nums">
                  {selectedDocDetail.processing_latency_ms} ms (CPU)
                </span>
              </div>
              <div>
                <span className="text-[10px] uppercase text-[#8A99AB] block">File Size</span>
                <span className="font-semibold text-[#172B4D] tabular-nums">
                  {(selectedDocDetail.file_size_bytes / 1024).toFixed(1)} KB
                </span>
              </div>
            </div>
          )}

          {showDocPreview && selectedDocDetail && (
            <div className="mt-3 p-3 bg-[#FAF9F6] border border-[#DFE7F1] rounded-lg">
              <span className="text-[11px] font-bold text-[#172B4D] block mb-1">
                Extracted Document Raw Text Preview:
              </span>
              <pre className="text-xs text-[#172B4D] font-mono whitespace-pre-wrap max-h-52 overflow-y-auto bg-white p-2.5 border border-[#DFE7F1] rounded">
                {selectedDocDetail.full_text || 'No text extracted.'}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Table of OCR Extractions */}
      <div className="bg-white border border-[#DFE7F1] rounded-lg overflow-hidden shadow-xs">
        <div className="p-4 border-b border-[#DFE7F1] flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-[#172B4D]">
              Structured Document Observations ({ocrItems.length})
            </h2>
            <p className="text-xs text-[#61738A]">
              Review raw-to-normalized value pairs, unit provenance tracking, and apply verification actions
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left med-table">
            <thead>
              <tr>
                <th>Concept / Token</th>
                <th>Raw Extracted Text</th>
                <th>Normalized Value</th>
                <th>Unit & Provenance</th>
                <th>Source Location</th>
                <th>Confidence</th>
                <th>Status</th>
                <th className="text-right">Verification Actions</th>
              </tr>
            </thead>
            <tbody>
              {ocrItems.length > 0 ? (
                ocrItems.map((item) => {
                  const meta = parseNotesMetadata(item.notes);
                  const isLowConf = item.extraction_confidence < 0.70;
                  const isUnconfirmed = item.user_confirmation_status === 'UNCONFIRMED';
                  const isRejected = item.user_confirmation_status === 'REJECTED_BY_PATIENT' || item.evidence_status === 'ABSENT';
                  const isUnreadable = item.evidence_status === 'UNKNOWN';
                  const isConfirmed = item.user_confirmation_status.startsWith('CONFIRMED');
                  const unitStatus = meta.unit_status || (item.unit ? 'EXPLICIT' : 'MISSING');

                  return (
                    <tr
                      key={item.evidence_id}
                      className={`hover:bg-[#F7F9FC] transition-colors ${
                        isLowConf && isUnconfirmed
                          ? 'bg-[#FFF0B3]/10'
                          : isRejected
                          ? 'bg-[#FFEBE6]/10 opacity-75'
                          : isUnreadable
                          ? 'bg-gray-50 opacity-70'
                          : ''
                      }`}
                    >
                      {/* Concept */}
                      <td>
                        <span className="font-semibold text-xs text-[#172B4D] block">
                          {item.concept_name_en || item.concept}
                        </span>
                        <span className="text-[10px] text-[#8A99AB] font-mono">
                          {item.concept}
                        </span>
                      </td>

                      {/* Raw Extracted Text */}
                      <td className="max-w-[180px]">
                        <p className="text-xs text-[#61738A] italic truncate" title={item.original_value || ''}>
                          "{item.original_value || 'Direct parsed record'}"
                        </p>
                      </td>

                      {/* Normalized Value */}
                      <td className="tabular-nums font-semibold text-xs text-[#172B4D]">
                        {String(item.normalized_value)}
                      </td>

                      {/* Unit & Provenance */}
                      <td>
                        <div className="flex flex-col space-y-0.5">
                          <span className="text-xs font-semibold text-[#172B4D]">
                            {item.unit || <span className="text-[#C23E4A] italic">No unit</span>}
                          </span>
                          <span
                            className={`px-1.5 py-0.2 rounded text-[10px] font-semibold w-max ${
                              unitStatus === 'EXPLICIT'
                                ? 'bg-[#E3FCEF] text-[#26845A] border border-[#ABF5D1]'
                                : unitStatus === 'NORMALIZED'
                                ? 'bg-[#EAF2FC] text-[#3675CA] border border-[#AFCFF2]'
                                : unitStatus === 'INFERRED'
                                ? 'bg-[#FFF0B3] text-[#A96B16] border border-[#FFE380]'
                                : unitStatus === 'INVALID'
                                ? 'bg-[#FFEBE6] text-[#C23E4A] border border-[#FFBDAD]'
                                : 'bg-gray-100 text-gray-700 border border-gray-300'
                            }`}
                          >
                            {unitStatus}
                          </span>
                        </div>
                      </td>

                      {/* Source Location */}
                      <td>
                        <div className="text-xs text-[#172B4D] truncate max-w-[120px]" title={item.source_document_id || ''}>
                          {item.source_document_id || 'EHR Record'}
                        </div>
                        <span className="text-[10px] text-[#8A99AB]">
                          {item.source_page ? `Page ${item.source_page}` : 'Header segment'}
                        </span>
                      </td>

                      {/* Confidence */}
                      <td>
                        <div className="flex items-center space-x-1.5">
                          <div className="w-10 h-1.5 bg-[#DFE7F1] rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                isLowConf ? 'bg-[#A96B16]' : 'bg-[#26845A]'
                              }`}
                              style={{ width: `${item.extraction_confidence * 100}%` }}
                            />
                          </div>
                          <span
                            className={`text-xs tabular-nums font-semibold ${
                              isLowConf ? 'text-[#A96B16]' : 'text-[#26845A]'
                            }`}
                          >
                            {(item.extraction_confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                      </td>

                      {/* Status */}
                      <td>
                        {isConfirmed && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-[#E3FCEF] text-[#26845A] border border-[#ABF5D1]">
                            Verified
                          </span>
                        )}
                        {isUnconfirmed && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-[#FFF0B3] text-[#A96B16] border border-[#FFE380]">
                            Unconfirmed
                          </span>
                        )}
                        {isRejected && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-[#FFEBE6] text-[#C23E4A] border border-[#FFBDAD]">
                            Rejected
                          </span>
                        )}
                        {isUnreadable && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-gray-100 text-gray-700 border border-gray-300">
                            Unreadable
                          </span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="text-right">
                        <div className="flex items-center justify-end space-x-1">
                          {isUnconfirmed ? (
                            <>
                              <button
                                onClick={() => handleAction(item.evidence_id, 'CONFIRM')}
                                disabled={updatingId === item.evidence_id}
                                className="px-2 py-1 bg-[#26845A] hover:bg-[#1E6B47] text-white rounded text-xs font-medium flex items-center space-x-1 transition-colors"
                                title="Confirm this extraction as verified"
                              >
                                <Check className="w-3 h-3" />
                                <span>Confirm</span>
                              </button>
                              <button
                                onClick={() =>
                                  setEditModal({
                                    item,
                                    value: String(item.normalized_value),
                                    unit: item.unit || '',
                                    notes: '',
                                  })
                                }
                                disabled={updatingId === item.evidence_id}
                                className="px-2 py-1 bg-[#F1F5FA] hover:bg-[#EAF2FC] text-[#3675CA] border border-[#DFE7F1] rounded text-xs font-medium flex items-center space-x-1 transition-colors"
                                title="Correct extracted value or unit"
                              >
                                <Edit2 className="w-3 h-3" />
                                <span>Edit</span>
                              </button>
                              <button
                                onClick={() => handleAction(item.evidence_id, 'REJECT')}
                                disabled={updatingId === item.evidence_id}
                                className="px-2 py-1 bg-[#F1F5FA] hover:bg-[#FFEBE6] text-[#C23E4A] border border-[#DFE7F1] rounded text-xs font-medium flex items-center space-x-1 transition-colors"
                                title="Reject extraction (mark ABSENT)"
                              >
                                <X className="w-3 h-3" />
                                <span>Reject</span>
                              </button>
                              <button
                                onClick={() => handleAction(item.evidence_id, 'MARK_UNREADABLE')}
                                disabled={updatingId === item.evidence_id}
                                className="px-1.5 py-1 bg-[#FAF9F6] hover:bg-gray-200 text-[#61738A] border border-[#DFE7F1] rounded text-[10px] font-medium transition-colors"
                                title="Mark text as unreadable in source"
                              >
                                Unreadable
                              </button>
                            </>
                          ) : (
                            <button
                              onClick={() => handleAction(item.evidence_id, 'REJECT')}
                              disabled={updatingId === item.evidence_id}
                              className="text-xs text-[#8A99AB] hover:text-[#C23E4A] hover:underline flex items-center space-x-1"
                              title="Reset status back to unconfirmed"
                            >
                              <RotateCcw className="w-3 h-3" />
                              <span>Reset</span>
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={8} className="text-center py-8 text-xs text-[#8A99AB]">
                    No OCR or document-extracted observations in this case ledger yet. Upload a document from the Medical Documents screen to run real extraction.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Edit / Correct Modal */}
      {editModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl border border-[#DFE7F1] max-w-md w-full p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-[#DFE7F1] pb-2">
              <h3 className="text-sm font-bold text-[#172B4D] flex items-center space-x-1.5">
                <Edit2 className="w-4 h-4 text-[#3675CA]" />
                <span>Correct Observation Value & Unit</span>
              </h3>
              <button
                onClick={() => setEditModal(null)}
                className="text-[#8A99AB] hover:text-[#172B4D]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-2.5 bg-[#FAF9F6] border border-[#DFE7F1] rounded text-xs space-y-1">
              <div>
                <span className="text-[#8A99AB] text-[10px] uppercase block">Concept</span>
                <span className="font-semibold text-[#172B4D]">
                  {editModal.item.concept_name_en || editModal.item.concept}
                </span>
              </div>
              <div>
                <span className="text-[#8A99AB] text-[10px] uppercase block">Original Raw Text</span>
                <span className="font-mono text-[#61738A] italic">
                  "{editModal.item.original_value || 'N/A'}"
                </span>
              </div>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="font-semibold text-[#172B4D] block mb-1">
                  Corrected Numeric / Clinical Value:
                </label>
                <input
                  type="text"
                  value={editModal.value}
                  onChange={(e) => setEditModal({ ...editModal, value: e.target.value })}
                  className="w-full p-2 border border-[#DFE7F1] rounded text-xs outline-none focus:border-[#3675CA]"
                  placeholder="e.g. 14.2"
                />
              </div>

              <div>
                <label className="font-semibold text-[#172B4D] block mb-1">
                  Corrected Measurement Unit:
                </label>
                <input
                  type="text"
                  value={editModal.unit}
                  onChange={(e) => setEditModal({ ...editModal, unit: e.target.value })}
                  className="w-full p-2 border border-[#DFE7F1] rounded text-xs outline-none focus:border-[#3675CA]"
                  placeholder="e.g. g/dL, mg/dL, mmHg, degF"
                />
              </div>

              <div>
                <label className="font-semibold text-[#172B4D] block mb-1">
                  Correction Context / Clinical Justification:
                </label>
                <input
                  type="text"
                  value={editModal.notes}
                  onChange={(e) => setEditModal({ ...editModal, notes: e.target.value })}
                  className="w-full p-2 border border-[#DFE7F1] rounded text-xs outline-none focus:border-[#3675CA]"
                  placeholder="e.g. Corrected scan artifact; verified against stamped clinic seal."
                />
              </div>
            </div>

            <div className="flex items-center justify-end space-x-2 border-t border-[#DFE7F1] pt-3">
              <button
                onClick={() => setEditModal(null)}
                className="px-3 py-1.5 border border-[#DFE7F1] text-[#61738A] rounded text-xs font-medium hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={() =>
                  handleAction(
                    editModal.item.evidence_id,
                    'CORRECT',
                    editModal.value,
                    editModal.unit,
                    editModal.notes
                  )
                }
                className="px-3 py-1.5 bg-[#3675CA] hover:bg-[#265EAA] text-white rounded text-xs font-semibold flex items-center space-x-1"
              >
                <Save className="w-3.5 h-3.5" />
                <span>Save Correction & Confirm</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

import React, { useState, useEffect } from 'react';
import {
  FileText,
  Upload,
  CheckCircle2,
  AlertTriangle,
  FileSpreadsheet,
  FileCode,
  Clock,
  ArrowRight,
  ShieldAlert,
} from 'lucide-react';
import { PatientProfile } from '../types';
import { uploadDocument, fetchPatientDocuments } from '../api/client';
import { ScreenId } from '../components/Sidebar';

interface MedicalDocumentsScreenProps {
  patient: PatientProfile | null;
  onNavigate: (screen: ScreenId) => void;
  onRefreshLedger: () => void;
}

export const MedicalDocumentsScreen: React.FC<MedicalDocumentsScreenProps> = ({
  patient,
  onNavigate,
  onRefreshLedger,
}) => {
  const [documents, setDocuments] = useState<any[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedDocType, setSelectedDocType] = useState('MEDICAL_REPORT');
  const [uploadFeedback, setUploadFeedback] = useState<string | null>(null);

  useEffect(() => {
    if (patient) {
      loadDocuments();
    }
  }, [patient]);

  const loadDocuments = async () => {
    if (!patient) return;
    try {
      const data = await fetchPatientDocuments(patient.patient_id);
      setDocuments(data.documents);
    } catch (e) {
      // Fallback
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !patient) return;

    setIsUploading(true);
    setUploadFeedback(null);
    try {
      const resp = await uploadDocument(patient.patient_id, file, selectedDocType);
      setUploadFeedback(`Document '${file.name}' processed. Extracted ${resp.extracted_items_count} observation(s).`);
      await loadDocuments();
      onRefreshLedger();
    } catch (err: any) {
      setUploadFeedback(`Upload failed: ${err.message}`);
    } finally {
      setIsUploading(false);
    }
  };

  if (!patient) {
    return (
      <div className="p-8 text-center text-[#61738A]">
        Please select a patient to manage medical documents.
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="bg-white border border-[#DFE7F1] rounded-lg p-5">
        <h1 className="text-xl font-bold text-[#172B4D] flex items-center space-x-2">
          <FileText className="w-5 h-5 text-[#3675CA]" />
          <span>Medical Document Ingestion & OCR Management</span>
        </h1>
        <p className="text-xs text-[#61738A] mt-1">
          Upload outpatient notes, consultation letters, laboratory panels, and prescriptions.
        </p>
      </div>

      {/* Honest Capability Boundary Banner (PART 5.2 requirement: Do not claim unsupported X-ray analysis) */}
      <div className="bg-[#FAF9F6] border border-[#DFE7F1] rounded-lg p-4 flex items-start space-x-3">
        <ShieldAlert className="w-5 h-5 text-[#3675CA] shrink-0 mt-0.5" />
        <div className="text-xs text-[#61738A] leading-relaxed">
          <strong className="text-[#172B4D]">Supported Modalities & Scope:</strong> MedResolve's document parser ingests structured laboratory reports, electronic health consultation summaries, and printed medication records.
          <span className="block text-[#A96B16] font-medium mt-0.5">
            Notice: Raw radiographic imaging (chest X-rays, CT scans) is not supported for computer vision analysis in this research prototype. Radiologist report text is extracted instead.
          </span>
        </div>
      </div>

      {/* Upload Box */}
      <div className="bg-white border-2 border-dashed border-[#DFE7F1] hover:border-[#3675CA] rounded-xl p-8 text-center transition-colors">
        <Upload className="w-10 h-10 text-[#3675CA] mx-auto mb-3" />
        <h3 className="text-sm font-semibold text-[#172B4D]">
          Upload Medical Document for OCR Extraction
        </h3>
        <p className="text-xs text-[#61738A] max-w-md mx-auto mt-1 mb-4">
          Select document type and choose PDF, scan image, or text record.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-3 mb-4">
          <select
            value={selectedDocType}
            onChange={(e) => setSelectedDocType(e.target.value)}
            className="text-xs p-2 rounded-md border border-[#DFE7F1] bg-white text-[#172B4D] outline-none"
          >
            <option value="MEDICAL_REPORT">Outpatient Clinical Note</option>
            <option value="LAB_REPORT">Laboratory / Blood Test Panel</option>
            <option value="PRESCRIPTION">Prescription / Medication List</option>
            <option value="DISCHARGE_SUMMARY">Discharge Summary Letter</option>
          </select>

          <label className="px-4 py-2 bg-[#3675CA] hover:bg-[#265EAA] text-white rounded-md text-xs font-medium cursor-pointer transition-colors shadow-sm">
            <span>{isUploading ? 'Extracting Text...' : 'Select File'}</span>
            <input
              type="file"
              onChange={handleFileUpload}
              disabled={isUploading}
              accept=".pdf,.png,.jpg,.jpeg,.txt"
              className="hidden"
            />
          </label>
        </div>

        {uploadFeedback && (
          <div className="p-2.5 bg-[#EAF2FC] border border-[#AFCFF2] rounded-md text-xs text-[#3675CA] max-w-md mx-auto">
            {uploadFeedback}
          </div>
        )}
      </div>

      {/* Uploaded Documents List */}
      <div className="bg-white border border-[#DFE7F1] rounded-lg p-5">
        <div className="flex items-center justify-between border-b border-[#DFE7F1] pb-3 mb-4">
          <div>
            <h2 className="text-sm font-bold text-[#172B4D]">
              Ingested Patient Documents ({documents.length})
            </h2>
            <p className="text-xs text-[#61738A]">
              Original source files with page tracking and OCR extraction provenance
            </p>
          </div>
          <button
            onClick={() => onNavigate('ocr-review')}
            className="text-xs text-[#3675CA] hover:underline font-medium flex items-center space-x-1"
          >
            <span>Review Extracted Values</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {documents.length > 0 ? (
          <div className="space-y-3">
            {documents.map((doc, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between p-3.5 border border-[#DFE7F1] rounded-lg hover:bg-[#F7F9FC] transition-colors"
              >
                <div className="flex items-center space-x-3">
                  <div className="w-9 h-9 rounded bg-[#F1F5FA] border border-[#DFE7F1] flex items-center justify-center text-[#3675CA]">
                    <FileText className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="font-semibold text-xs text-[#172B4D]">{doc.filename}</span>
                    <div className="flex items-center space-x-2 text-[11px] text-[#61738A] mt-0.5">
                      <span>{doc.document_type}</span>
                      <span>•</span>
                      <span className="tabular-nums">{(doc.file_size_bytes / 1024).toFixed(1)} KB</span>
                      <span>•</span>
                      <span>Uploaded {doc.uploaded_timestamp}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center space-x-3 text-xs">
                  <span className="px-2 py-0.5 rounded text-[11px] bg-[#E3FCEF] text-[#26845A] font-medium border border-[#ABF5D1]">
                    OCR Complete
                  </span>
                  <span className="text-[11px] text-[#61738A] tabular-nums">
                    {doc.extracted_items?.length || 0} findings
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-xs text-[#8A99AB]">
            No documents uploaded yet for this synthetic case. Upload a report above to run automated extraction.
          </div>
        )}
      </div>
    </div>
  );
};

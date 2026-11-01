import React, { useState } from 'react';
import {
  Stethoscope,
  Send,
  AlertCircle,
  HelpCircle,
  Info,
  CheckCircle2,
} from 'lucide-react';
import { PatientProfile } from '../types';
import { addLedgerItem } from '../api/client';

interface SymptomAssessmentScreenProps {
  patient: PatientProfile | null;
  onRefreshLedger: () => void;
}

export const SymptomAssessmentScreen: React.FC<SymptomAssessmentScreenProps> = ({
  patient,
  onRefreshLedger,
}) => {
  const [description, setDescription] = useState('');
  const [onset, setOnset] = useState('GRADUAL');
  const [duration, setDuration] = useState('3 days');
  const [severity, setSeverity] = useState('MODERATE');
  const [frequency, setFrequency] = useState('INTERMITTENT');
  const [progression, setProgression] = useState('STABLE');
  const [associated, setAssociated] = useState('');
  const [pertinentNegatives, setPertinentNegatives] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);

  if (!patient) {
    return (
      <div className="p-8 text-center text-[#61738A]">
        Please select a patient to record symptom observations.
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!description.trim()) return;

    setIsSubmitting(true);
    try {
      await addLedgerItem(
        patient.patient_id,
        'E_PATIENT_CHIEF_COMPLAINT',
        description,
        description,
        undefined,
        'PRESENT',
        `Onset: ${onset}, Duration: ${duration}, Severity: ${severity}, Frequency: ${frequency}, Progression: ${progression}. Associated: ${associated || 'None'}. Negatives: ${pertinentNegatives || 'None'}`
      );
      setFeedbackMsg('Observation successfully appended to the structured evidence ledger.');
      setDescription('');
      onRefreshLedger();
    } catch (err: any) {
      setFeedbackMsg(`Error submitting observation: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Title */}
      <div className="bg-white border border-[#DFE7F1] rounded-lg p-5">
        <h1 className="text-xl font-bold text-[#172B4D] flex items-center space-x-2">
          <Stethoscope className="w-5 h-5 text-[#3675CA]" />
          <span>Symptom Intake & Clinical History Form</span>
        </h1>
        <p className="text-xs text-[#61738A] mt-1">
          Structured symptom collection with multi-dimensional clinical temporal attribution.
        </p>
      </div>

      {/* Non-Diagnostic Disclaimer Banner (PART 5.2 requirement) */}
      <div className="bg-[#FFF0B3]/40 border border-[#FFE380] rounded-lg p-3.5 flex items-start space-x-3">
        <Info className="w-4 h-4 text-[#A96B16] shrink-0 mt-0.5" />
        <p className="text-xs text-[#A96B16] leading-relaxed">
          <strong>Clinical Boundaries Notice:</strong> Completing this clinical intake questionnaire does{' '}
          <strong>not</strong> establish a medical diagnosis, triage certification, or treatment plan. All submitted observations are recorded into your source-aware evidence ledger for structured reconciliation.
        </p>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="bg-white border border-[#DFE7F1] rounded-lg p-6 space-y-5">
        {feedbackMsg && (
          <div className="p-3 bg-[#E3FCEF] border border-[#ABF5D1] rounded-md text-xs text-[#26845A] flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4" />
            <span>{feedbackMsg}</span>
          </div>
        )}

        {/* Primary Description */}
        <div>
          <label className="block text-xs font-semibold text-[#172B4D] mb-1">
            Primary Symptom Description <span className="text-[#C23E4A]">*</span>
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="e.g., Burning chest pain behind breastbone especially after dinner and when bending forward..."
            rows={3}
            required
            className="w-full text-xs p-3 rounded-md border border-[#DFE7F1] focus:border-[#3675CA] focus:ring-1 focus:ring-[#3675CA] outline-none"
          />
        </div>

        {/* Grid: Onset, Duration, Severity, Frequency */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-medium text-[#172B4D] mb-1">Onset</label>
            <select
              value={onset}
              onChange={(e) => setOnset(e.target.value)}
              className="w-full text-xs p-2 rounded-md border border-[#DFE7F1] bg-white focus:border-[#3675CA] outline-none"
            >
              <option value="SUDDEN_ACUTE">Sudden / Acute (Minutes)</option>
              <option value="GRADUAL">Gradual (Days)</option>
              <option value="INSIDIOUS">Insidious (Weeks)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-[#172B4D] mb-1">Duration</label>
            <input
              type="text"
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
              placeholder="e.g. 5 days, 2 weeks"
              className="w-full text-xs p-2 rounded-md border border-[#DFE7F1] focus:border-[#3675CA] outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-[#172B4D] mb-1">Severity</label>
            <select
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
              className="w-full text-xs p-2 rounded-md border border-[#DFE7F1] bg-white focus:border-[#3675CA] outline-none"
            >
              <option value="MILD">Mild (No interference)</option>
              <option value="MODERATE">Moderate (Disrupts tasks)</option>
              <option value="SEVERE">Severe (Incapacitating)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-[#172B4D] mb-1">Frequency</label>
            <select
              value={frequency}
              onChange={(e) => setFrequency(e.target.value)}
              className="w-full text-xs p-2 rounded-md border border-[#DFE7F1] bg-white focus:border-[#3675CA] outline-none"
            >
              <option value="CONSTANT">Constant / Continuous</option>
              <option value="INTERMITTENT">Intermittent (Comes & Goes)</option>
              <option value="POSTPRANDIAL">Exclusively After Meals</option>
            </select>
          </div>
        </div>

        {/* Progression */}
        <div>
          <label className="block text-xs font-medium text-[#172B4D] mb-1">Progression Trend</label>
          <div className="flex space-x-3 text-xs">
            {['IMPROVING', 'STABLE', 'WORSENING'].map((p) => (
              <label key={p} className="flex items-center space-x-1.5 cursor-pointer">
                <input
                  type="radio"
                  name="progression"
                  value={p}
                  checked={progression === p}
                  onChange={(e) => setProgression(e.target.value)}
                  className="text-[#3675CA]"
                />
                <span className="capitalize">{p.toLowerCase()}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Associated Symptoms */}
        <div>
          <label className="block text-xs font-medium text-[#172B4D] mb-1">
            Associated Symptoms (if any)
          </label>
          <input
            type="text"
            value={associated}
            onChange={(e) => setAssociated(e.target.value)}
            placeholder="e.g., Acid regurgitation, sour taste, cough while lying flat..."
            className="w-full text-xs p-2.5 rounded-md border border-[#DFE7F1] focus:border-[#3675CA] outline-none"
          />
        </div>

        {/* Pertinent Negatives */}
        <div>
          <label className="block text-xs font-medium text-[#172B4D] mb-1">
            Pertinent Negative Findings (Symptoms specifically absent)
          </label>
          <input
            type="text"
            value={pertinentNegatives}
            onChange={(e) => setPertinentNegatives(e.target.value)}
            placeholder="e.g., Denies exertional chest pressure, denies shortness of breath, denies dizziness..."
            className="w-full text-xs p-2.5 rounded-md border border-[#DFE7F1] focus:border-[#3675CA] outline-none"
          />
          <p className="text-[11px] text-[#8A99AB] mt-1">
            Explicitly recording absent findings helps prevent false alarm conflict flags.
          </p>
        </div>

        {/* Submit */}
        <div className="pt-2 flex justify-end">
          <button
            type="submit"
            disabled={isSubmitting || !description.trim()}
            className="px-4 py-2 bg-[#3675CA] hover:bg-[#265EAA] text-white rounded-md text-xs font-medium flex items-center space-x-2 transition-colors shadow-sm disabled:opacity-50"
          >
            <Send className="w-3.5 h-3.5" />
            <span>{isSubmitting ? 'Recording...' : 'Record to Evidence Ledger'}</span>
          </button>
        </div>
      </form>
    </div>
  );
};

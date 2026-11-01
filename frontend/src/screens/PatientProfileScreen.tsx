import React from 'react';
import {
  User,
  AlertTriangle,
  Pill,
  ShieldCheck,
  Calendar,
  Heart,
  FileCheck,
} from 'lucide-react';
import { PatientProfile } from '../types';

interface PatientProfileScreenProps {
  patient: PatientProfile | null;
}

export const PatientProfileScreen: React.FC<PatientProfileScreenProps> = ({ patient }) => {
  if (!patient) {
    return (
      <div className="p-8 text-center text-[#61738A]">
        Please select a patient to view profile details.
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="bg-white border border-[#DFE7F1] rounded-lg p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-[10px] font-semibold bg-[#EAF2FC] text-[#3675CA] px-2 py-0.5 rounded border border-[#AFCFF2]">
                SYNTHETIC CASE #{patient.patient_id}
              </span>
              <span className="text-xs text-[#8A99AB]">Clinical Intake Record</span>
            </div>
            <h1 className="text-xl font-bold text-[#172B4D] mt-1">{patient.name}</h1>
            <p className="text-xs text-[#61738A]">{patient.clinical_narrative}</p>
          </div>
          <div className="text-right">
            <span className="text-xs font-semibold text-[#172B4D] block">
              Archetype: {patient.synthetic_case_archetype}
            </span>
            <span className="text-[11px] text-[#26845A] font-medium">
              Expected Safety Action: {patient.expected_action}
            </span>
          </div>
        </div>
      </div>

      {/* Provenance Separation Notice (PART 5.2 requirement) */}
      <div className="bg-[#FAF9F6] border border-[#DFE7F1] rounded-lg p-4 flex items-start space-x-3">
        <ShieldCheck className="w-5 h-5 text-[#3675CA] shrink-0 mt-0.5" />
        <div className="text-xs text-[#61738A] leading-relaxed">
          <strong className="text-[#172B4D]">Data Provenance Boundary:</strong> MedResolve strictly separates{' '}
          <span className="text-[#3675CA] font-semibold">Patient-Reported Information</span> (subjective narrative, symptom onset) from{' '}
          <span className="text-[#26845A] font-semibold">Independently Verified Clinical Data</span> (laboratory tests, signed physician consults, confirmed EHR extractions). Patient-reported entries are never conflated with diagnostic truths.
        </div>
      </div>

      {/* Demographics & Physical Baseline */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white border border-[#DFE7F1] rounded-lg p-5 space-y-4">
          <h2 className="text-sm font-bold text-[#172B4D] flex items-center space-x-2 border-b border-[#DFE7F1] pb-2">
            <User className="w-4 h-4 text-[#3675CA]" />
            <span>Demographic Information</span>
          </h2>

          <div className="grid grid-cols-2 gap-4 text-xs">
            <div>
              <span className="text-[#8A99AB] block text-[11px]">Age</span>
              <span className="font-semibold text-[#172B4D] tabular-nums">{patient.age} years</span>
            </div>
            <div>
              <span className="text-[#8A99AB] block text-[11px]">Sex</span>
              <span className="font-semibold text-[#172B4D]">{patient.sex}</span>
            </div>
            <div>
              <span className="text-[#8A99AB] block text-[11px]">Height</span>
              <span className="font-semibold text-[#172B4D] tabular-nums">
                {patient.height_cm ? `${patient.height_cm} cm` : 'Not recorded'}
              </span>
            </div>
            <div>
              <span className="text-[#8A99AB] block text-[11px]">Weight</span>
              <span className="font-semibold text-[#172B4D] tabular-nums">
                {patient.weight_kg ? `${patient.weight_kg} kg` : 'Not recorded'}
              </span>
            </div>
          </div>

          <div className="pt-2 border-t border-[#DFE7F1]">
            <span className="text-[#8A99AB] block text-[11px] mb-1">Relevant Background</span>
            <p className="text-xs text-[#172B4D] leading-relaxed">
              {patient.relevant_background || 'No additional background reported.'}
            </p>
          </div>
        </div>

        {/* Medical History & Allergies */}
        <div className="bg-white border border-[#DFE7F1] rounded-lg p-5 space-y-4">
          <h2 className="text-sm font-bold text-[#172B4D] flex items-center space-x-2 border-b border-[#DFE7F1] pb-2">
            <Heart className="w-4 h-4 text-[#C23E4A]" />
            <span>Reported History & Allergies</span>
          </h2>

          <div>
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[#8A99AB] block mb-1">
              Patient-Reported Diagnoses
            </span>
            <div className="flex flex-wrap gap-1.5">
              {patient.reported_diagnoses.length > 0 ? (
                patient.reported_diagnoses.map((d, i) => (
                  <span
                    key={i}
                    className="px-2 py-0.5 rounded text-xs bg-[#F1F5FA] text-[#172B4D] border border-[#DFE7F1]"
                  >
                    {d}
                  </span>
                ))
              ) : (
                <span className="text-xs text-[#8A99AB]">None reported</span>
              )}
            </div>
          </div>

          <div>
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[#8A99AB] block mb-1">
              Known Allergies & Adverse Reactions
            </span>
            <div className="flex flex-wrap gap-1.5">
              {patient.allergies.map((a, i) => (
                <span
                  key={i}
                  className="px-2 py-0.5 rounded text-xs bg-[#FFEBE6] text-[#C23E4A] border border-[#FFBDAD] font-medium"
                >
                  {a}
                </span>
              ))}
            </div>
          </div>

          <div className="pt-2 border-t border-[#DFE7F1]">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[#8A99AB] block mb-1">
              Past Medical / Surgical History
            </span>
            <ul className="list-disc list-inside text-xs text-[#172B4D] space-y-0.5">
              {patient.past_medical_history.map((h, i) => (
                <li key={i}>{h}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* Current Medications Table */}
      <div className="bg-white border border-[#DFE7F1] rounded-lg p-5">
        <h2 className="text-sm font-bold text-[#172B4D] flex items-center space-x-2 border-b border-[#DFE7F1] pb-3 mb-4">
          <Pill className="w-4 h-4 text-[#3675CA]" />
          <span>Current Active Medications</span>
        </h2>

        {patient.current_medications.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left med-table">
              <thead>
                <tr>
                  <th>Medication Name</th>
                  <th>Dosage / Frequency</th>
                  <th>Duration</th>
                  <th>Reported Indication</th>
                </tr>
              </thead>
              <tbody>
                {patient.current_medications.map((m, idx) => (
                  <tr key={idx} className="hover:bg-[#F7F9FC]">
                    <td className="font-semibold">{m.name}</td>
                    <td className="tabular-nums">{m.dose}</td>
                    <td className="text-[#61738A]">{m.duration}</td>
                    <td>
                      <span className="px-2 py-0.5 rounded text-[11px] bg-[#EAF2FC] text-[#3675CA]">
                        {m.indication}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-[#8A99AB] py-4 text-center">
            No active prescription or over-the-counter medications recorded.
          </p>
        )}
      </div>
    </div>
  );
};

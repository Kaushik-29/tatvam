import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  OctagonAlert,
  HelpCircle,
  CheckCircle2,
  AlertTriangle,
  PhoneCall,
  Globe,
} from 'lucide-react';
import { AssessmentResult, PatientProfile, PolicyAction } from '../types';
import { fetchEmergencyConfig, updateEmergencyConfig } from '../api/client';

interface SafetyCentreScreenProps {
  patient: PatientProfile | null;
  assessment: AssessmentResult | null;
}

export const SafetyCentreScreen: React.FC<SafetyCentreScreenProps> = ({
  patient,
  assessment,
}) => {
  const [emergencyConfig, setEmergencyConfig] = useState<any>({
    region: 'India',
    region_display: 'India (National & Tamil Nadu)',
    primary_emergency_number: '112',
    ambulance_emergency_number: '108',
    emergency_service_name: 'National Emergency Response Support System (ERSS 112) / TN Ambulance (108)',
    available_regions: [
      { code: 'IN', name: 'India (National / Tamil Nadu)', primary: '112', ambulance: '108' },
      { code: 'US', name: 'United States', primary: '911', ambulance: '911' },
      { code: 'UK', name: 'United Kingdom', primary: '999', ambulance: '999' },
      { code: 'EU', name: 'European Union', primary: '112', ambulance: '112' },
    ],
  });

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const cfg = await fetchEmergencyConfig();
      setEmergencyConfig(cfg);
    } catch (e) {
      // Use fallback defaults
    }
  };

  const handleRegionChange = async (regionCode: string) => {
    try {
      const res = await updateEmergencyConfig(regionCode);
      if (res && res.config) {
        setEmergencyConfig(res.config);
      }
    } catch (err) {
      console.error('Error updating emergency region:', err);
    }
  };

  const currentAction: PolicyAction = assessment
    ? assessment.policy_decision.selected_action
    : patient
    ? patient.expected_action
    : 'EXPLAIN';

  const isIndia = emergencyConfig.region.toLowerCase().includes('india') || emergencyConfig.region.toLowerCase().includes('in');

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Title */}
      <div className="bg-white border border-[#DFE7F1] rounded-lg p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-[10px] font-semibold bg-[#FFEBE6] text-[#C23E4A] px-2 py-0.5 rounded border border-[#FFBDAD]">
                SAFETY GATE PROTOCOL
              </span>
              <span className="text-xs text-[#8A99AB]">Deterministic Clinical Action Policy</span>
            </div>
            <h1 className="text-xl font-bold text-[#172B4D] flex items-center space-x-2 mt-1">
              <ShieldAlert className="w-5 h-5 text-[#3675CA]" />
              <span>Selective Action & Safety Navigation Centre</span>
            </h1>
            <p className="text-xs text-[#61738A]">
              Deterministic safety gating: life-threatening clinical red flags strictly preempt generative inference with 100% precedence guarantee.
            </p>
          </div>

          <div className="flex items-center space-x-2 text-xs">
            <span className="text-[#61738A]">Current Action State:</span>
            <span
              className={`px-3 py-1 rounded-md font-bold text-xs ${
                currentAction === 'EMERGENCY_OVERRIDE'
                  ? 'bg-[#FFEBE6] text-[#C23E4A] border border-[#FFBDAD]'
                  : currentAction === 'ASK'
                  ? 'bg-[#DEEBFF] text-[#0065FF] border border-[#B3D4FF]'
                  : currentAction === 'ABSTAIN_AND_NAVIGATE'
                  ? 'bg-[#FFF0B3] text-[#A96B16] border border-[#FFE380]'
                  : 'bg-[#E3FCEF] text-[#26845A] border border-[#ABF5D1]'
              }`}
            >
              {currentAction}
            </span>
          </div>
        </div>
      </div>

      {/* Regional Emergency Dispatch Configuration Panel */}
      <div className="bg-white border border-[#DFE7F1] rounded-lg p-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-md bg-[#FAF9F6] border border-[#DFE7F1] text-[#3675CA]">
              <Globe className="w-4 h-4" />
            </div>
            <div>
              <span className="text-xs font-bold text-[#172B4D] block">
                Regional Emergency Dispatch Services
              </span>
              <p className="text-[11px] text-[#61738A]">
                {emergencyConfig.emergency_service_name}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-1.5 text-xs">
              <span className="text-[#61738A]">Region:</span>
              <select
                value={emergencyConfig.available_regions?.find((r: any) => r.name === emergencyConfig.region)?.code || 'IN'}
                onChange={(e) => handleRegionChange(e.target.value)}
                className="text-xs p-1.5 border border-[#DFE7F1] rounded bg-white font-medium text-[#172B4D] outline-none"
              >
                {emergencyConfig.available_regions?.map((reg: any) => (
                  <option key={reg.code} value={reg.code}>
                    {reg.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center space-x-1 text-xs font-semibold tabular-nums">
              <span className="px-2 py-1 bg-[#FFEBE6] text-[#C23E4A] border border-[#FFBDAD] rounded">
                National: {emergencyConfig.primary_emergency_number}
              </span>
              {emergencyConfig.ambulance_emergency_number !== emergencyConfig.primary_emergency_number && (
                <span className="px-2 py-1 bg-[#FFEBE6] text-[#C23E4A] border border-[#FFBDAD] rounded">
                  Ambulance: {emergencyConfig.ambulance_emergency_number}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* The 4 Distinct Visual Action Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* State 1: EMERGENCY_OVERRIDE */}
        <div
          className={`border-2 rounded-xl p-5 transition-all ${
            currentAction === 'EMERGENCY_OVERRIDE'
              ? 'border-[#C23E4A] bg-[#FFEBE6]/20 shadow-md ring-2 ring-[#C23E4A]/20'
              : 'border-[#DFE7F1] bg-white opacity-70'
          }`}
        >
          <div className="flex items-center justify-between border-b border-[#DFE7F1] pb-3 mb-3">
            <div className="flex items-center space-x-2">
              <div className="p-2 rounded-md bg-[#FFEBE6] text-[#C23E4A]">
                <OctagonAlert className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-[#C23E4A]">1. EMERGENCY_OVERRIDE</h3>
                <span className="text-[10px] text-[#61738A]">Urgent Clinical Warning</span>
              </div>
            </div>
            {currentAction === 'EMERGENCY_OVERRIDE' && (
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#C23E4A] text-white">
                ACTIVE STATE
              </span>
            )}
          </div>

          <p className="text-xs text-[#172B4D] leading-relaxed mb-3">
            Deterministic clinical red-flag triggers (e.g., upper airway stridor, acute syncope with chest pain, hyperpyrexia ≥104°F, severe hypoxemia SpO2 &lt;90%, or crushing retrosternal pain with dyspnea).
          </p>

          <div className="p-3 bg-[#FFEBE6]/60 border border-[#FFBDAD] rounded-md text-xs text-[#C23E4A] space-y-1.5">
            <div className="flex items-center space-x-2 font-bold">
              <PhoneCall className="w-4 h-4 shrink-0" />
              <span>
                {isIndia
                  ? 'Directs immediate emergency dispatch (Dial 112 National Response or 108 Ambulance)'
                  : `Directs immediate emergency dispatch (Dial ${emergencyConfig.primary_emergency_number})`}
              </span>
            </div>
            <p className="text-[11px] leading-tight">
              Strict Invariant: Completely bypasses Ollama/LLM generation (0.0s latency, 0 tokens generated). Model weights cannot override this safety directive.
            </p>
          </div>
        </div>

        {/* State 2: ASK (Clarification) */}
        <div
          className={`border-2 rounded-xl p-5 transition-all ${
            currentAction === 'ASK'
              ? 'border-[#0065FF] bg-[#DEEBFF]/20 shadow-md ring-2 ring-[#0065FF]/20'
              : 'border-[#DFE7F1] bg-white opacity-70'
          }`}
        >
          <div className="flex items-center justify-between border-b border-[#DFE7F1] pb-3 mb-3">
            <div className="flex items-center space-x-2">
              <div className="p-2 rounded-md bg-[#DEEBFF] text-[#0065FF]">
                <HelpCircle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-[#0065FF]">2. ASK</h3>
                <span className="text-[10px] text-[#61738A]">Targeted Clarification Inquiry</span>
              </div>
            </div>
            {currentAction === 'ASK' && (
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#0065FF] text-white">
                ACTIVE STATE
              </span>
            )}
          </div>

          <p className="text-xs text-[#172B4D] leading-relaxed mb-3">
            Fired when essential evidence is missing or automated document extractions have low confidence (&lt;0.70) or unconfirmed missing units.
          </p>

          <div className="p-3 bg-[#DEEBFF]/50 border border-[#B3D4FF] rounded-md text-xs text-[#0065FF] space-y-1.5">
            <p className="font-semibold">Presents Bounded Clarification Question:</p>
            <p className="text-[11px] text-[#172B4D] italic bg-white p-2 rounded border border-[#DFE7F1]">
              "{assessment?.policy_decision.candidate_question_en || patient?.clinical_narrative || 'Please clarify symptom duration and onset.'}"
            </p>
            <p className="text-[10px] text-[#61738A]">
              Prevents speculative hallucinations by gathering explicit verification before generating summaries.
            </p>
          </div>
        </div>

        {/* State 3: ABSTAIN_AND_NAVIGATE */}
        <div
          className={`border-2 rounded-xl p-5 transition-all ${
            currentAction === 'ABSTAIN_AND_NAVIGATE'
              ? 'border-[#A96B16] bg-[#FFF0B3]/20 shadow-md ring-2 ring-[#A96B16]/20'
              : 'border-[#DFE7F1] bg-white opacity-70'
          }`}
        >
          <div className="flex items-center justify-between border-b border-[#DFE7F1] pb-3 mb-3">
            <div className="flex items-center space-x-2">
              <div className="p-2 rounded-md bg-[#FFF0B3] text-[#A96B16]">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-[#A96B16]">3. ABSTAIN_AND_NAVIGATE</h3>
                <span className="text-[10px] text-[#61738A]">Non-Arbitration & Care Routing</span>
              </div>
            </div>
            {currentAction === 'ABSTAIN_AND_NAVIGATE' && (
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#A96B16] text-white">
                ACTIVE STATE
              </span>
            )}
          </div>

          <p className="text-xs text-[#172B4D] leading-relaxed mb-3">
            Triggered when material clinician disagreements are present, or when queries fall out-of-domain (outside cardiopulmonary / GI corpus boundaries).
          </p>

          <div className="p-3 bg-[#FFF0B3]/50 border border-[#FFE380] rounded-md text-xs text-[#A96B16] space-y-1.5">
            <p className="font-semibold">Non-Arbitration Protocol:</p>
            <p className="text-[11px] text-[#172B4D]">
              Declines to arbitrate between differing provider opinions or synthesize unsupported out-of-scope advice. Routes user to an in-person clinical specialist consultation.
            </p>
          </div>
        </div>

        {/* State 4: EXPLAIN */}
        <div
          className={`border-2 rounded-xl p-5 transition-all ${
            currentAction === 'EXPLAIN'
              ? 'border-[#26845A] bg-[#E3FCEF]/20 shadow-md ring-2 ring-[#26845A]/20'
              : 'border-[#DFE7F1] bg-white opacity-70'
          }`}
        >
          <div className="flex items-center justify-between border-b border-[#DFE7F1] pb-3 mb-3">
            <div className="flex items-center space-x-2">
              <div className="p-2 rounded-md bg-[#E3FCEF] text-[#26845A]">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-[#26845A]">4. EXPLAIN</h3>
                <span className="text-[10px] text-[#61738A]">Verified Evidence Summary</span>
              </div>
            </div>
            {currentAction === 'EXPLAIN' && (
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#26845A] text-white">
                ACTIVE STATE
              </span>
            )}
          </div>

          <p className="text-xs text-[#172B4D] leading-relaxed mb-3">
            Selected exclusively for clean in-domain presentations with zero material conflicts, confirmed document extractions, and high retrieval relevance.
          </p>

          <div className="p-3 bg-[#E3FCEF]/50 border border-[#ABF5D1] rounded-md text-xs text-[#26845A] space-y-1.5">
            <p className="font-semibold">Full Dual-Axis Grounding Active:</p>
            <p className="text-[11px] text-[#172B4D]">
              Produces bounded clinical synthesis with verified passage citations (`[DOC_*_P*]`). Every asserted statement is cross-verified against the structured patient evidence ledger using lexical evidence support heuristics.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

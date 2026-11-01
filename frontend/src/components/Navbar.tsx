import React from 'react';
import {
  Activity,
  AlertTriangle,
  Play,
  Shield,
  User,
  ChevronDown,
  Sparkles,
  Menu,
} from 'lucide-react';
import { PatientProfile } from '../types';

interface NavbarProps {
  patients: PatientProfile[];
  activePatient: PatientProfile | null;
  onSelectPatient: (patient: PatientProfile) => void;
  onRunAssessment: () => void;
  isAssessing: boolean;
  activeScreenTitle: string;
  onToggleMobileMenu?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  patients,
  activePatient,
  onSelectPatient,
  onRunAssessment,
  isAssessing,
  activeScreenTitle,
  onToggleMobileMenu,
}) => {
  return (
    <header className="sticky top-0 z-30 h-14 bg-white border-b border-[#DFE7F1] px-3 md:px-6 flex items-center justify-between shadow-[0_1px_2px_rgba(0,0,0,0.03)]">
      {/* Left: Product Brand & Context */}
      <div className="flex items-center space-x-2 md:space-x-3">
        {onToggleMobileMenu && (
          <button
            onClick={onToggleMobileMenu}
            className="md:hidden p-1.5 -ml-1 text-[#61738A] hover:bg-[#F1F5FA] rounded-md transition-colors"
            title="Toggle clinical navigation menu"
            aria-label="Toggle menu"
          >
            <Menu className="w-5 h-5" />
          </button>
        )}
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-lg bg-[#3675CA] flex items-center justify-center text-white shadow-sm font-semibold text-sm tracking-tight shrink-0">
            <Activity className="w-4 h-4 text-white" />
          </div>
          <div>
            <span className="font-semibold text-[15px] tracking-tight text-[#172B4D]">
              Med<span className="text-[#3675CA]">Resolve</span>
            </span>
            <span className="hidden sm:inline-block ml-2 px-1.5 py-0.5 text-[10px] font-semibold bg-[#EAF2FC] text-[#3675CA] rounded border border-[#AFCFF2]">
              RESEARCH PROTOTYPE
            </span>
          </div>
        </div>

        <div className="hidden lg:block h-4 w-[1px] bg-[#DFE7F1] mx-2" />
        <span className="hidden lg:inline-block text-xs font-medium text-[#61738A]">
          {activeScreenTitle}
        </span>
      </div>

      {/* Middle: Synthetic Patient Selector */}
      <div className="flex items-center space-x-2">
        <div className="relative group">
          <div className="flex items-center space-x-2 bg-[#F1F5FA] hover:bg-[#EAF2FC] border border-[#DFE7F1] hover:border-[#AFCFF2] rounded-md px-3 py-1.5 transition-colors cursor-pointer text-xs">
            <User className="w-3.5 h-3.5 text-[#3675CA]" />
            <span className="font-medium text-[#172B4D] max-w-[130px] sm:max-w-[180px] truncate">
              {activePatient ? activePatient.name : 'Select Synthetic Patient'}
            </span>
            {activePatient && (
              <span className="hidden sm:inline-block text-[11px] text-[#61738A] tabular-nums">
                ({activePatient.age}y {activePatient.sex[0]})
              </span>
            )}
            <ChevronDown className="w-3.5 h-3.5 text-[#61738A]" />
          </div>

          {/* Patient Dropdown Menu */}
          <div className="absolute right-0 mt-1 w-80 bg-white border border-[#DFE7F1] rounded-lg shadow-lg py-1 hidden group-hover:block z-50">
            <div className="px-3 py-1.5 border-b border-[#DFE7F1] bg-[#FAF9F6]">
              <p className="text-[11px] font-semibold text-[#172B4D]">
                Select Synthetic Benchmark Patient
              </p>
              <p className="text-[10px] text-[#61738A]">
                Explicit fictional records for research testing (No real patient data)
              </p>
            </div>
            <div className="max-h-72 overflow-y-auto">
              {patients.map((p) => {
                const isSelected = activePatient?.patient_id === p.patient_id;
                return (
                  <button
                    key={p.patient_id}
                    onClick={() => onSelectPatient(p)}
                    className={`w-full text-left px-3 py-2 text-xs flex flex-col hover:bg-[#F1F5FA] transition-colors border-b border-gray-50 last:border-none ${
                      isSelected ? 'bg-[#EAF2FC] font-medium' : ''
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[#172B4D] font-medium">{p.name}</span>
                      <span className="text-[10px] text-[#61738A] tabular-nums">
                        {p.age}y / {p.sex}
                      </span>
                    </div>
                    <span className="text-[11px] text-[#3675CA] mt-0.5">
                      {p.archetype_display}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Run Assessment Action */}
        <button
          onClick={onRunAssessment}
          disabled={isAssessing || !activePatient}
          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
            isAssessing
              ? 'bg-[#EAF2FC] text-[#3675CA] border border-[#AFCFF2] cursor-wait'
              : 'bg-[#3675CA] hover:bg-[#265EAA] text-white shadow-sm'
          }`}
        >
          {isAssessing ? (
            <>
              <div className="w-3.5 h-3.5 border-2 border-[#3675CA] border-t-transparent rounded-full animate-spin" />
              <span>Assessing...</span>
            </>
          ) : (
            <>
              <Play className="w-3.5 h-3.5 fill-current" />
              <span className="hidden sm:inline">Run Assessment</span>
              <span className="sm:hidden">Run</span>
            </>
          )}
        </button>
      </div>
    </header>
  );
};

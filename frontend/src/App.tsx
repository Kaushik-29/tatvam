import React, { useState, useEffect } from 'react';
import {
  PatientProfile,
  EvidenceItem,
  ClinicianOpinion,
  ConflictItem,
  AssessmentResult,
} from './types';
import {
  fetchPatients,
  fetchEvidenceLedger,
  fetchConflicts,
  assessPatient,
} from './api/client';
import { Navbar } from './components/Navbar';
import { Sidebar, ScreenId } from './components/Sidebar';
import { WorkflowProgressModal, WorkflowStage } from './components/WorkflowProgressModal';

import { OverviewScreen } from './screens/OverviewScreen';
import { PatientProfileScreen } from './screens/PatientProfileScreen';
import { SymptomAssessmentScreen } from './screens/SymptomAssessmentScreen';
import { MedicalDocumentsScreen } from './screens/MedicalDocumentsScreen';
import { OcrReviewScreen } from './screens/OcrReviewScreen';
import { EvidenceLedgerScreen } from './screens/EvidenceLedgerScreen';
import { ConflictDetectionScreen } from './screens/ConflictDetectionScreen';
import { MedicalKnowledgeScreen } from './screens/MedicalKnowledgeScreen';
import { AiSummaryScreen } from './screens/AiSummaryScreen';
import { SafetyCentreScreen } from './screens/SafetyCentreScreen';
import { AssessmentHistoryScreen } from './screens/AssessmentHistoryScreen';
import { ResearchDashboardScreen } from './screens/ResearchDashboardScreen';
import { SettingsScreen } from './screens/SettingsScreen';

export function App() {
  const [activeScreen, setActiveScreen] = useState<ScreenId>('overview');
  const [patients, setPatients] = useState<PatientProfile[]>([]);
  const [activePatient, setActivePatient] = useState<PatientProfile | null>(null);
  const [ledgerItems, setLedgerItems] = useState<EvidenceItem[]>([]);
  const [opinions, setOpinions] = useState<ClinicianOpinion[]>([]);
  const [conflicts, setConflicts] = useState<ConflictItem[]>([]);
  const [latestAssessment, setLatestAssessment] = useState<AssessmentResult | null>(null);

  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isAssessing, setIsAssessing] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  const initialStages: WorkflowStage[] = [
    {
      code: 'STAGE_1_INTAKE',
      name: '1. Ingesting Clinical Intake',
      description: 'Parsing reported symptoms, temporal markers, and vitals',
      status: 'PENDING',
    },
    {
      code: 'STAGE_2_LEDGER',
      name: '2. Structured Evidence Ledger',
      description: 'Synthesizing source provenance and unconfirmed OCR items',
      status: 'PENDING',
    },
    {
      code: 'STAGE_3_CONFLICTS',
      name: '3. Evaluating Conflict Taxonomy',
      description: 'Running 6-category discrepancy and timeline checks',
      status: 'PENDING',
    },
    {
      code: 'STAGE_4_EMERGENCY',
      name: '4. Checking Emergency Override',
      description: 'Evaluating deterministic clinical red flags with vital normalization',
      status: 'PENDING',
    },
    {
      code: 'STAGE_5_RETRIEVAL',
      name: '5. Hybrid Knowledge Retrieval',
      description: 'Querying BGE-M3 Dense FAISS + BM25 Reciprocal Rank Fusion',
      status: 'PENDING',
    },
    {
      code: 'STAGE_6_SYNTHESIS',
      name: '6. Claim Verification & Safety Gate',
      description: 'Dual-axis claim verification buffering unverified outputs',
      status: 'PENDING',
    },
  ];

  const [stages, setStages] = useState<WorkflowStage[]>(initialStages);

  const handleSelectPatient = async (patient: PatientProfile) => {
    setActivePatient(patient);
    setLatestAssessment(null);
    try {
      const ledgerData = await fetchEvidenceLedger(patient.patient_id);
      setLedgerItems(ledgerData.items || []);
      setOpinions(ledgerData.opinions || []);

      const conflictData = await fetchConflicts(patient.patient_id);
      setConflicts(conflictData.conflicts || []);
    } catch (e) {
      console.error(e);
    }
  };

  // Load patients at startup
  useEffect(() => {
    fetchPatients()
      .then((data) => {
        setPatients(data);
        if (data.length > 0) {
          handleSelectPatient(data[0]);
        }
      })
      .catch((e) => console.error(e));
  }, []);


  const refreshLedger = async () => {
    if (!activePatient) return;
    try {
      const ledgerData = await fetchEvidenceLedger(activePatient.patient_id);
      setLedgerItems(ledgerData.items || []);
      setOpinions(ledgerData.opinions || []);

      const conflictData = await fetchConflicts(activePatient.patient_id);
      setConflicts(conflictData.conflicts || []);
    } catch (e) {
      console.error(e);
    }
  };

  const handleRunAssessment = async () => {
    if (!activePatient || isAssessing) return;

    setIsAssessing(true);
    setElapsedSeconds(0);

    // Reset stages
    setStages(initialStages.map((s) => ({ ...s, status: 'PENDING', timestamp: undefined })));

    // Timer
    const timer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);

    // Progressive stage simulation during the backend call
    const updateStage = (idx: number, status: 'ACTIVE' | 'COMPLETED') => {
      setStages((prev) =>
        prev.map((s, i) =>
          i === idx
            ? { ...s, status, timestamp: status === 'COMPLETED' ? new Date().toLocaleTimeString() : undefined }
            : s
        )
      );
    };

    try {
      // Stage 1
      updateStage(0, 'ACTIVE');
      await new Promise((r) => setTimeout(r, 400));
      updateStage(0, 'COMPLETED');

      // Stage 2
      updateStage(1, 'ACTIVE');
      await new Promise((r) => setTimeout(r, 500));
      updateStage(1, 'COMPLETED');

      // Stage 3
      updateStage(2, 'ACTIVE');
      await new Promise((r) => setTimeout(r, 500));
      updateStage(2, 'COMPLETED');

      // Stage 4
      updateStage(3, 'ACTIVE');
      await new Promise((r) => setTimeout(r, 400));
      updateStage(3, 'COMPLETED');

      // Stage 5
      updateStage(4, 'ACTIVE');
      await new Promise((r) => setTimeout(r, 600));
      updateStage(4, 'COMPLETED');

      // Stage 6 (Inference & Verification)
      updateStage(5, 'ACTIVE');

      // Live Backend Execution
      const result = await assessPatient(activePatient.patient_id);
      updateStage(5, 'COMPLETED');

      setLatestAssessment(result);
      await refreshLedger();

      // Short delay for visual completion, then transition
      setTimeout(() => {
        setIsAssessing(false);
        clearInterval(timer);
        setActiveScreen('ai-summary');
      }, 600);
    } catch (err: any) {
      console.error(err);
      setIsAssessing(false);
      clearInterval(timer);
    }
  };

  const getScreenTitle = (screen: ScreenId): string => {
    switch (screen) {
      case 'overview':
        return 'Overview Dashboard';
      case 'profile':
        return 'Patient Intake & Profile';
      case 'symptom-assessment':
        return 'Symptom Assessment';
      case 'documents':
        return 'Medical Document Management';
      case 'ocr-review':
        return 'OCR Extraction Review';
      case 'evidence-ledger':
        return 'Source-Aware Evidence Ledger';
      case 'conflicts':
        return 'Conflict Detection Taxonomy';
      case 'knowledge':
        return 'Medical Knowledge Corpus';
      case 'ai-summary':
        return 'AI Summary & Claims Verification';
      case 'safety-centre':
        return 'Selective Action & Safety Centre';
      case 'history':
        return 'Assessment History';
      case 'research':
        return 'Research Evaluation Dashboard';
      case 'settings':
        return 'Settings & Architecture';
      default:
        return 'MedResolve Healthcare System';
    }
  };

  const unconfirmedCount = ledgerItems.filter(
    (i) => i.user_confirmation_status === 'UNCONFIRMED'
  ).length;

  return (
    <div className="min-h-screen bg-[#F7F9FC] flex flex-col antialiased text-[#172B4D]">
      {/* Top Navbar */}
      <Navbar
        patients={patients}
        activePatient={activePatient}
        onSelectPatient={handleSelectPatient}
        onRunAssessment={handleRunAssessment}
        isAssessing={isAssessing}
        activeScreenTitle={getScreenTitle(activeScreen)}
        onToggleMobileMenu={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
      />

      {/* Mobile Drawer Overlay */}
      {isMobileMenuOpen && (
        <div className="fixed inset-0 z-40 md:hidden flex">
          <div
            className="fixed inset-0 bg-black/40 backdrop-blur-xs transition-opacity"
            onClick={() => setIsMobileMenuOpen(false)}
          />
          <div className="relative z-50 w-64 bg-white h-full shadow-2xl flex flex-col">
            <Sidebar
              activeScreen={activeScreen}
              onNavigate={(screen) => {
                setActiveScreen(screen);
                setIsMobileMenuOpen(false);
              }}
              isCollapsed={false}
              onToggleCollapse={() => setIsMobileMenuOpen(false)}
              unconfirmedCount={unconfirmedCount}
              conflictsCount={conflicts.length}
            />
          </div>
        </div>
      )}

      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar (Desktop / Tablet) */}
        <div className="hidden md:flex flex-col shrink-0">
          <Sidebar
            activeScreen={activeScreen}
            onNavigate={(screen) => setActiveScreen(screen)}
            isCollapsed={isSidebarCollapsed}
            onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
            unconfirmedCount={unconfirmedCount}
            conflictsCount={conflicts.length}
          />
        </div>

        {/* Main Workspace Canvas */}
        <main className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8">
          {activeScreen === 'overview' && (
            <OverviewScreen
              patient={activePatient}
              onNavigate={(screen) => setActiveScreen(screen)}
              onRunAssessment={handleRunAssessment}
              isAssessing={isAssessing}
              latestAssessment={latestAssessment}
            />
          )}

          {activeScreen === 'profile' && (
            <PatientProfileScreen patient={activePatient} />
          )}

          {activeScreen === 'symptom-assessment' && (
            <SymptomAssessmentScreen
              patient={activePatient}
              onRefreshLedger={refreshLedger}
            />
          )}

          {activeScreen === 'documents' && (
            <MedicalDocumentsScreen
              patient={activePatient}
              onNavigate={(screen) => setActiveScreen(screen)}
              onRefreshLedger={refreshLedger}
            />
          )}

          {activeScreen === 'ocr-review' && (
            <OcrReviewScreen
              patient={activePatient}
              ledgerItems={ledgerItems}
              onRefreshLedger={refreshLedger}
            />
          )}

          {activeScreen === 'evidence-ledger' && (
            <EvidenceLedgerScreen
              patient={activePatient}
              items={ledgerItems}
              opinions={opinions}
              onRefreshLedger={refreshLedger}
            />
          )}

          {activeScreen === 'conflicts' && (
            <ConflictDetectionScreen patient={activePatient} />
          )}

          {activeScreen === 'knowledge' && <MedicalKnowledgeScreen />}

          {activeScreen === 'ai-summary' && (
            <AiSummaryScreen
              patient={activePatient}
              assessment={latestAssessment}
              ledgerItems={ledgerItems}
              onNavigate={(screen) => setActiveScreen(screen)}
              onRunAssessment={handleRunAssessment}
              isAssessing={isAssessing}
            />
          )}

          {activeScreen === 'safety-centre' && (
            <SafetyCentreScreen
              patient={activePatient}
              assessment={latestAssessment}
            />
          )}

          {activeScreen === 'history' && <AssessmentHistoryScreen />}

          {activeScreen === 'research' && <ResearchDashboardScreen />}

          {activeScreen === 'settings' && <SettingsScreen />}
        </main>
      </div>

      {/* Workflow Progress Modal (Buffered Safety Gate) */}
      <WorkflowProgressModal
        isOpen={isAssessing}
        stages={stages}
        currentStageCode=""
        elapsedSeconds={elapsedSeconds}
      />
    </div>
  );
}

export default App;

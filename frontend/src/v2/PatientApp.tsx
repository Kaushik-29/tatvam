import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle, BookOpen, ClipboardList, FileText, FlaskConical, History, LogOut, Menu, MessageSquare, Pill as PillIcon,
  ScanText, Settings, Stethoscope, User, UserPlus, Waypoints, X,
} from 'lucide-react';
import { api, hasToken, setToken } from './api';
import type { Consultation, ConsultInput, PatientProfile } from './types';
import { cx, Spinner } from './ui';
import { AuthScreen } from './screens/AuthScreen';
import { OnboardingScreen } from './screens/OnboardingScreen';
import { ProfileScreen } from './screens/ProfileScreen';
import { TimelineScreen } from './screens/TimelineScreen';
import { MedsAllergiesScreen } from './screens/MedsAllergiesScreen';
import { DocumentsScreen } from './screens/DocumentsScreen';
import { OcrReviewScreen } from './screens/OcrReviewScreen';
import { ConcernScreen } from './screens/ConcernScreen';
import { ChatScreen } from './screens/ChatScreen';
import { ContextScreen, ReferencesScreen, ConflictsScreen } from './screens/EvidenceScreens';
import { HistoryScreen } from './screens/HistoryScreen';
import { SettingsScreen } from './screens/SettingsScreen';

export type V2Screen =
  | 'onboarding' | 'profile' | 'timeline' | 'meds' | 'documents' | 'ocr' | 'concern' | 'chat'
  | 'context' | 'references' | 'conflicts' | 'history' | 'settings';

const NAV: { group: string; items: { id: V2Screen; label: string; icon: React.ReactNode }[] }[] = [
  { group: 'Ask', items: [
    { id: 'concern', label: 'New health concern', icon: <Stethoscope className="w-4 h-4" /> },
    { id: 'chat', label: 'Personalised chat', icon: <MessageSquare className="w-4 h-4" /> },
  ] },
  { group: 'Why this answer', items: [
    { id: 'context', label: 'Retrieved patient context', icon: <Waypoints className="w-4 h-4" /> },
    { id: 'references', label: 'Medical references', icon: <BookOpen className="w-4 h-4" /> },
    { id: 'conflicts', label: 'Conflicts & uncertainty', icon: <AlertCircle className="w-4 h-4" /> },
    { id: 'history', label: 'Previous consultations', icon: <History className="w-4 h-4" /> },
  ] },
  { group: 'My health record', items: [
    { id: 'profile', label: 'Medical profile', icon: <User className="w-4 h-4" /> },
    { id: 'timeline', label: 'History & timeline', icon: <ClipboardList className="w-4 h-4" /> },
    { id: 'meds', label: 'Medications & allergies', icon: <PillIcon className="w-4 h-4" /> },
    { id: 'documents', label: 'Upload documents', icon: <FileText className="w-4 h-4" /> },
    { id: 'ocr', label: 'Review extracted data', icon: <ScanText className="w-4 h-4" /> },
    { id: 'onboarding', label: 'Onboarding', icon: <UserPlus className="w-4 h-4" /> },
  ] },
  { group: 'Account', items: [
    { id: 'settings', label: 'Settings & data', icon: <Settings className="w-4 h-4" /> },
  ] },
];

export function PatientApp() {
  const [authed, setAuthed] = useState(hasToken());
  const [isDemo, setIsDemo] = useState(false);
  const [profile, setProfile] = useState<PatientProfile | null>(null);
  const [screen, setScreen] = useState<V2Screen>('concern');
  const [current, setCurrent] = useState<Consultation | null>(null);
  const [pendingQuery, setPendingQuery] = useState<ConsultInput | null>(null);
  const [focusAlias, setFocusAlias] = useState<string | null>(null);
  const [mobileNav, setMobileNav] = useState(false);
  const [reviewDoc, setReviewDoc] = useState<string | null>(null);

  const loadProfile = useCallback(async () => {
    try {
      const p = await api.profile();
      setProfile(p);
      setIsDemo(p.is_synthetic);
      if (!p.onboarding_complete && !p.is_synthetic) setScreen('onboarding');
    } catch {
      setAuthed(false);
    }
  }, []);

  useEffect(() => {
    if (authed) loadProfile();
  }, [authed, loadProfile]);

  const logout = () => {
    setToken(null);
    setAuthed(false);
    setProfile(null);
    setCurrent(null);
  };

  const go = (s: V2Screen) => {
    setScreen(s);
    setMobileNav(false);
  };

  const openCitation = (alias: string) => {
    setFocusAlias(alias);
    go(alias.startsWith('E') ? 'context' : 'references');
  };

  if (!authed) {
    return <AuthScreen onAuthed={(demo) => { setIsDemo(demo); setAuthed(true); setScreen(demo ? 'concern' : 'onboarding'); }} />;
  }
  if (!profile) {
    return <div className="flex-1 flex items-center justify-center"><Spinner label="Loading your record…" /></div>;
  }

  const name = [profile.given_name?.split(' ')[0], profile.family_name].filter(Boolean).join(' ') || 'Patient';
  const sidebar = (
    <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-4" aria-label="Main navigation">
      {NAV.map((g) => (
        <div key={g.group}>
          <p className="px-2.5 mb-1 text-[10px] font-semibold uppercase tracking-wider text-[#8A99AB]">{g.group}</p>
          {g.items.filter((i) => !(i.id === 'onboarding' && isDemo)).map((i) => (
            <button key={i.id} onClick={() => go(i.id)}
              className={cx('w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-[12px] transition-colors text-left',
                screen === i.id ? 'bg-[#EAF2FC] text-[#3675CA] font-medium' : 'text-[#61738A] hover:bg-[#F1F5FA] hover:text-[#172B4D]')}>
              {i.icon}
              <span className="truncate flex-1">{i.label}</span>
              {i.id === 'conflicts' && current && current.findings.length > 0 && (
                <span className="text-[10px] font-semibold px-1.5 rounded-full bg-[#FFF0B3] text-[#7A4D10] tabular-nums">{current.findings.length}</span>
              )}
            </button>
          ))}
        </div>
      ))}
    </nav>
  );

  return (
    <div className="flex-1 flex flex-col min-h-screen">
      <header className="h-12 bg-white border-b border-[#DFE7F1] px-4 flex items-center gap-3 sticky top-0 z-30">
        <button className="md:hidden p-1 text-[#61738A]" onClick={() => setMobileNav(!mobileNav)} aria-label="Toggle navigation">
          {mobileNav ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
        <span className="text-[14px] font-semibold text-[#172B4D]">MedResolve</span>
        <span className="hidden sm:inline text-[11px] text-[#8A99AB]">Longitudinal medical information assistant · research prototype</span>
        <div className="ml-auto flex items-center gap-3">
          {isDemo && <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-[#F1F5FA] text-[#61738A] border border-[#DFE7F1]">SYNTHETIC DEMO PATIENT · READ-ONLY</span>}
          <span className="hidden sm:inline text-[12px] text-[#172B4D]">{name}</span>
          <a href="#/research" className="hidden lg:inline-flex items-center gap-1 text-[11px] text-[#61738A] hover:text-[#3675CA]" title="Phase 5 research console">
            <FlaskConical className="w-3.5 h-3.5" /> Research console
          </a>
          <button onClick={logout} className="inline-flex items-center gap-1 text-[12px] text-[#61738A] hover:text-[#C23E4A]">
            <LogOut className="w-4 h-4" /> Sign out
          </button>
        </div>
      </header>
      <div className="flex flex-1 min-h-0">
        <aside className="hidden md:flex w-60 bg-white border-r border-[#DFE7F1] flex-col">{sidebar}
          <p className="p-3 border-t border-[#DFE7F1] bg-[#FAF9F6] text-[10px] text-[#61738A] leading-snug">
            Information only — not a diagnosis or prescription. Not clinically validated.
          </p>
        </aside>
        {mobileNav && (
          <div className="md:hidden fixed inset-0 top-12 z-20 bg-black/20" onClick={() => setMobileNav(false)}>
            <aside className="w-64 h-full bg-white border-r border-[#DFE7F1] flex flex-col" onClick={(e) => e.stopPropagation()}>{sidebar}</aside>
          </div>
        )}
        <main className="flex-1 min-w-0 p-4 md:p-6 overflow-y-auto">
          <div className="max-w-6xl mx-auto">
            {screen === 'onboarding' && <OnboardingScreen profile={profile} onDone={async () => { await loadProfile(); go('concern'); }} />}
            {screen === 'profile' && <ProfileScreen profile={profile} readOnly={isDemo} onSaved={loadProfile} />}
            {screen === 'timeline' && <TimelineScreen />}
            {screen === 'meds' && <MedsAllergiesScreen readOnly={isDemo} />}
            {screen === 'documents' && <DocumentsScreen readOnly={isDemo} onReview={(id) => { setReviewDoc(id); go('ocr'); }} />}
            {screen === 'ocr' && <OcrReviewScreen readOnly={isDemo} initialDoc={reviewDoc} />}
            {screen === 'concern' && <ConcernScreen profile={profile} onSubmit={(q) => { setPendingQuery(q); go('chat'); }} />}
            {screen === 'chat' && (
              <ChatScreen pending={pendingQuery} clearPending={() => setPendingQuery(null)} current={current}
                onResult={setCurrent} onCite={openCitation} onNavigate={go} />
            )}
            {screen === 'context' && <ContextScreen consultation={current} focus={focusAlias} onNavigate={go} />}
            {screen === 'references' && <ReferencesScreen consultation={current} focus={focusAlias} onNavigate={go} />}
            {screen === 'conflicts' && <ConflictsScreen consultation={current} onNavigate={go} />}
            {screen === 'history' && <HistoryScreen onOpen={(c) => { setCurrent(c); go('chat'); }} />}
            {screen === 'settings' && <SettingsScreen profile={profile} isDemo={isDemo} onLoggedOut={logout} />}
          </div>
        </main>
      </div>
    </div>
  );
}

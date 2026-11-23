import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle, BookOpen, ClipboardList, FileText, FlaskConical, History, LogOut, Menu, MessageSquare, Pill as PillIcon,
  Plus, ScanText, Settings, Stethoscope, User, UserPlus, Waypoints, X,
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

const ICON = 'w-[18px] h-[18px]';
const NAV: { group: string; items: { id: V2Screen; label: string; icon: React.ReactNode }[] }[] = [
  { group: 'Ask', items: [
    { id: 'concern', label: 'New health concern', icon: <Stethoscope className={ICON} /> },
    { id: 'chat', label: 'Personalised chat', icon: <MessageSquare className={ICON} /> },
  ] },
  { group: 'Why this answer', items: [
    { id: 'context', label: 'Retrieved patient context', icon: <Waypoints className={ICON} /> },
    { id: 'references', label: 'Medical references', icon: <BookOpen className={ICON} /> },
    { id: 'conflicts', label: 'Conflicts & uncertainty', icon: <AlertCircle className={ICON} /> },
    { id: 'history', label: 'Previous consultations', icon: <History className={ICON} /> },
  ] },
  { group: 'My health record', items: [
    { id: 'profile', label: 'Medical profile', icon: <User className={ICON} /> },
    { id: 'timeline', label: 'History & timeline', icon: <ClipboardList className={ICON} /> },
    { id: 'meds', label: 'Medications & allergies', icon: <PillIcon className={ICON} /> },
    { id: 'documents', label: 'Upload documents', icon: <FileText className={ICON} /> },
    { id: 'ocr', label: 'Review extracted data', icon: <ScanText className={ICON} /> },
    { id: 'onboarding', label: 'Onboarding', icon: <UserPlus className={ICON} /> },
  ] },
  { group: 'Account', items: [
    { id: 'settings', label: 'Settings & data', icon: <Settings className={ICON} /> },
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
    return (
      <div className="mr-app flex-1 flex flex-col min-h-screen">
        <AuthScreen onAuthed={(demo) => { setIsDemo(demo); setAuthed(true); setScreen(demo ? 'concern' : 'onboarding'); }} />
      </div>
    );
  }
  if (!profile) {
    return <div className="mr-app flex-1 flex items-center justify-center min-h-screen"><Spinner label="Loading your record…" /></div>;
  }

  const name = [profile.given_name?.split(' ')[0], profile.family_name].filter(Boolean).join(' ') || 'Patient';
  const initials = name.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase();
  const sidebar = (
    <nav className="flex-1 overflow-y-auto px-3 pt-6 pb-4 space-y-6" aria-label="Main navigation">
      {NAV.map((g) => (
        <div key={g.group}>
          <p className="px-3 mb-1.5 text-[12px] font-medium text-faint">{g.group}</p>
          <div className="space-y-0.5">
            {g.items.filter((i) => !(i.id === 'onboarding' && isDemo)).map((i) => {
              const active = screen === i.id;
              return (
                <button key={i.id} onClick={() => go(i.id)} aria-current={active ? 'page' : undefined}
                  className={cx('w-full flex items-center gap-3 h-9 px-3 rounded-[10px] text-[14px] text-left cursor-pointer transition-all duration-200',
                    active ? 'bg-white text-ink font-medium shadow-[0_1px_2px_rgba(0,0,0,0.06),0_0_0_1px_rgba(0,0,0,0.03)]'
                      : 'text-ink-2 hover:bg-black/[0.04] hover:text-ink')}>
                  <span className={cx('transition-colors', active ? 'text-accent' : 'text-faint')}>{i.icon}</span>
                  <span className="truncate flex-1">{i.label}</span>
                  {i.id === 'conflicts' && current && current.findings.length > 0 && (
                    <span className="min-w-5 h-5 px-1.5 inline-flex items-center justify-center text-[11px] font-semibold rounded-full bg-warn-soft text-warn-ink tabular-nums">{current.findings.length}</span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
  const disclaimer = (
    <p className="mx-3 mb-4 rounded-[14px] bg-white/70 border border-line-soft px-3.5 py-3 text-[12px] text-muted leading-snug">
      Information only, not a diagnosis or prescription. Not clinically validated.
    </p>
  );

  return (
    <div className="mr-app flex-1 flex flex-col min-h-screen">
      <header className="h-14 bg-white/75 backdrop-blur-xl backdrop-saturate-150 border-b border-line/80 px-4 md:px-6 flex items-center gap-3 sticky top-0 z-30">
        <button className="md:hidden -ml-1 h-9 w-9 inline-flex items-center justify-center rounded-full text-ink-2 hover:bg-black/5 cursor-pointer"
          onClick={() => setMobileNav(!mobileNav)} aria-label={mobileNav ? 'Close navigation' : 'Open navigation'} aria-expanded={mobileNav}>
          {mobileNav ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
        <button onClick={() => go('concern')} className="flex items-center gap-2.5 cursor-pointer" aria-label="MedResolve home">
          <span className="flex h-8 w-8 items-center justify-center rounded-[9px] bg-accent text-white shadow-[0_1px_2px_rgba(10,102,228,0.35)]">
            <Plus className="w-[18px] h-[18px]" strokeWidth={3} />
          </span>
          <span className="font-display text-[17px] font-semibold tracking-[-0.015em]">MedResolve</span>
        </button>
        <span className="hidden lg:inline-flex h-6 items-center rounded-full bg-canvas px-2.5 text-[12px] text-muted">Research prototype</span>
        <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
          {isDemo && (
            <span className="hidden sm:inline-flex h-7 items-center gap-1.5 rounded-full bg-warn-soft px-3 text-[12px] font-medium text-warn-ink">
              <span className="h-1.5 w-1.5 rounded-full bg-warn" /> Synthetic demo · read-only
            </span>
          )}
          <a href="#/research" title="Phase 5 research console"
            className="hidden lg:inline-flex h-9 items-center gap-1.5 rounded-full px-3 text-[13px] text-muted hover:text-ink hover:bg-black/5 transition-colors">
            <FlaskConical className="w-4 h-4" /> Research
          </a>
          <div className="hidden sm:flex items-center gap-2 pl-2 pr-1">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-[#e8f0fd] to-[#d6e4fb] text-[12px] font-semibold text-accent-strong">{initials}</span>
            <span className="text-[14px] text-ink max-w-[160px] truncate">{name}</span>
          </div>
          <button onClick={logout} title="Sign out" aria-label="Sign out"
            className="inline-flex h-9 items-center gap-1.5 rounded-full px-3 text-[13px] text-muted hover:text-danger hover:bg-danger-soft transition-colors cursor-pointer">
            <LogOut className="w-4 h-4" /><span className="hidden sm:inline">Sign out</span>
          </button>
        </div>
      </header>
      <div className="flex flex-1 min-h-0">
        <aside className="hidden md:flex w-[264px] shrink-0 flex-col sticky top-14 h-[calc(100vh-3.5rem)] border-r border-line/60 bg-canvas">
          {sidebar}
          {disclaimer}
        </aside>
        <div className={cx('md:hidden fixed inset-0 top-14 z-20 transition-opacity duration-300', mobileNav ? 'opacity-100' : 'opacity-0 pointer-events-none')}>
          <div className="absolute inset-0 bg-black/20 backdrop-blur-[2px]" onClick={() => setMobileNav(false)} />
          <aside className={cx('relative w-[280px] h-full bg-canvas border-r border-line flex flex-col shadow-lift transition-transform duration-300 ease-[cubic-bezier(0.2,0.8,0.2,1)]',
            mobileNav ? 'translate-x-0' : '-translate-x-full')}>
            {sidebar}
            {disclaimer}
          </aside>
        </div>
        <main className="flex-1 min-w-0 px-5 py-8 sm:px-8 md:px-10 md:py-10">
          <div key={screen} className="max-w-[1120px] mx-auto">
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

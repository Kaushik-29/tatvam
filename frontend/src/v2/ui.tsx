import React from 'react';
import { AlertTriangle, HelpCircle, Loader2, OctagonAlert, ShieldCheck } from 'lucide-react';
import type { Action } from './types';

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ');

export function Card({ title, subtitle, actions, children, className }: {
  title?: React.ReactNode; subtitle?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode; className?: string;
}) {
  return (
    <section className={cx('bg-white border border-[#DFE7F1] rounded-lg', className)}>
      {(title || actions) && (
        <header className="px-4 py-3 border-b border-[#DFE7F1] flex items-start justify-between gap-3">
          <div className="min-w-0">
            {title && <h2 className="text-[13px] font-semibold text-[#172B4D]">{title}</h2>}
            {subtitle && <p className="text-[11px] text-[#61738A] mt-0.5">{subtitle}</p>}
          </div>
          {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
      <div>
        <h1 className="text-[17px] font-semibold text-[#172B4D]">{title}</h1>
        {description && <p className="text-[12px] text-[#61738A] mt-0.5 max-w-3xl">{description}</p>}
      </div>
      {actions}
    </div>
  );
}

export function Button({ variant = 'primary', className, ...p }: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' | 'danger' }) {
  const styles = {
    primary: 'bg-[#3675CA] text-white hover:bg-[#265EAA] border border-[#3675CA]',
    secondary: 'bg-white text-[#172B4D] border border-[#DFE7F1] hover:bg-[#F1F5FA]',
    ghost: 'bg-transparent text-[#3675CA] hover:bg-[#EAF2FC] border border-transparent',
    danger: 'bg-white text-[#C23E4A] border border-[#C23E4A] hover:bg-[#FFEBE6]',
  }[variant];
  return (
    <button
      {...p}
      className={cx('inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-[12px] font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed', styles, className)}
    />
  );
}

export function Input(p: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...p} className={cx('w-full px-2.5 py-1.5 text-[12px] border border-[#DFE7F1] rounded-md bg-white focus:border-[#3675CA] outline-none', p.className)} />;
}

export function Select(p: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...p} className={cx('w-full px-2 py-1.5 text-[12px] border border-[#DFE7F1] rounded-md bg-white focus:border-[#3675CA] outline-none', p.className)} />;
}

export function TextArea(p: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...p} className={cx('w-full px-2.5 py-2 text-[12px] border border-[#DFE7F1] rounded-md bg-white focus:border-[#3675CA] outline-none resize-y', p.className)} />;
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-[11px] font-medium text-[#61738A] mb-1">{label}</span>
      {children}
      {hint && <span className="block text-[10px] text-[#8A99AB] mt-1">{hint}</span>}
    </label>
  );
}

const STATUS_STYLES: Record<string, string> = {
  CONFIRMED: 'bg-[#E3FCEF] text-[#26845A]',
  confirmed: 'bg-[#E3FCEF] text-[#26845A]',
  SUPPORTED: 'bg-[#E3FCEF] text-[#26845A]',
  'PATIENT-REPORTED': 'bg-[#EAF2FC] text-[#265EAA]',
  patient_reported: 'bg-[#EAF2FC] text-[#265EAA]',
  DERIVED: 'bg-[#F1F5FA] text-[#61738A]',
  derived: 'bg-[#F1F5FA] text-[#61738A]',
  'EXTRACTED-UNCONFIRMED': 'bg-[#FFF0B3] text-[#7A4D10]',
  unconfirmed: 'bg-[#FFF0B3] text-[#7A4D10]',
  UNCONFIRMED: 'bg-[#FFF0B3] text-[#7A4D10]',
  UNSUPPORTED: 'bg-[#FFEBE6] text-[#C23E4A]',
  INVALID_CITATION: 'bg-[#FFEBE6] text-[#C23E4A]',
  refuted: 'bg-[#FFEBE6] text-[#C23E4A]',
  HIGH: 'bg-[#FFEBE6] text-[#C23E4A]',
  MEDIUM: 'bg-[#FFF0B3] text-[#7A4D10]',
  LOW: 'bg-[#F1F5FA] text-[#61738A]',
  INFO: 'bg-[#DEEBFF] text-[#0052CC]',
  SAFETY_ALLOWED: 'bg-[#DEEBFF] text-[#0052CC]',
};

export function Pill({ value, label }: { value: string; label?: string }) {
  return (
    <span className={cx('inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold whitespace-nowrap', STATUS_STYLES[value] ?? 'bg-[#F1F5FA] text-[#61738A]')}>
      {(label ?? value).replace(/_/g, ' ')}
    </span>
  );
}

const ACTIONS: Record<Action, { label: string; icon: React.ReactNode; cls: string; text: string }> = {
  EXPLAIN: { label: 'Explained with verified evidence', icon: <ShieldCheck className="w-4 h-4" />, cls: 'border-[#26845A] bg-[#E3FCEF] text-[#1E6B49]', text: 'Only statements that passed claim verification are shown.' },
  ASK: { label: 'More information needed', icon: <HelpCircle className="w-4 h-4" />, cls: 'border-[#0065FF] bg-[#DEEBFF] text-[#0747A6]', text: 'MedResolve asks before answering rather than guessing.' },
  ABSTAIN_AND_NAVIGATE: { label: 'Please consult a clinician', icon: <AlertTriangle className="w-4 h-4" />, cls: 'border-[#A96B16] bg-[#FFF0B3] text-[#7A4D10]', text: 'A conflict or a diagnostic/prescribing decision requires professional assessment.' },
  EMERGENCY_OVERRIDE: { label: 'Emergency warning', icon: <OctagonAlert className="w-4 h-4" />, cls: 'border-[#C23E4A] bg-[#FFEBE6] text-[#9C2A35]', text: 'Red-flag symptoms detected — generation was suppressed.' },
};

export function ActionBanner({ action, reason }: { action: Action; reason?: string }) {
  const a = ACTIONS[action] ?? ACTIONS.EXPLAIN;
  return (
    <div className={cx('border rounded-md px-3 py-2 flex items-start gap-2', a.cls)} role={action === 'EMERGENCY_OVERRIDE' ? 'alert' : 'status'}>
      <span className="mt-0.5">{a.icon}</span>
      <div>
        <p className="text-[12px] font-semibold">{a.label} <span className="font-normal opacity-80">· {action.replace(/_/g, ' ')}</span></p>
        <p className="text-[11px] opacity-90">{reason || a.text}</p>
      </div>
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-[12px] text-[#61738A]">
      <Loader2 className="w-4 h-4 animate-spin" /> {label}
    </span>
  );
}

export function Empty({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="text-center py-10 px-4">
      <p className="text-[13px] font-medium text-[#172B4D]">{title}</p>
      {children && <div className="text-[12px] text-[#61738A] mt-1 max-w-md mx-auto">{children}</div>}
    </div>
  );
}

export function ErrorNote({ error }: { error: string | null }) {
  if (!error) return null;
  return <p className="text-[12px] text-[#C23E4A] bg-[#FFEBE6] border border-[#F5C2C7] rounded px-3 py-2">{error}</p>;
}

export const fmtDate = (d?: string | null) => (d ? d.slice(0, 10) : '—');

/** Minimal markdown renderer for verified answers. Citations become clickable chips. */
export function AnswerText({ text, onCite }: { text: string; onCite?: (alias: string) => void }) {
  const renderInline = (s: string, key: number) => {
    const parts = s.split(/(\[[ER]\d+(?:\s*,\s*[ER]\d+)*\]|\*\*[^*]+\*\*|_[^_]+_)/g);
    return (
      <React.Fragment key={key}>
        {parts.map((p, i) => {
          const cite = /^\[([ER]\d+(?:\s*,\s*[ER]\d+)*)\]$/.exec(p);
          if (cite) {
            return cite[1].split(',').map((a) => a.trim()).map((a) => (
              <button key={`${i}-${a}`} onClick={() => onCite?.(a)}
                className={cx('mx-0.5 px-1 rounded text-[10px] font-semibold align-baseline tabular-nums',
                  a.startsWith('E') ? 'bg-[#EAF2FC] text-[#265EAA] hover:bg-[#D6E6FA]' : 'bg-[#F1F5FA] text-[#61738A] hover:bg-[#E2E8F0]')}
                title={a.startsWith('E') ? 'Patient record evidence' : 'Medical reference passage'}>
                {a}
              </button>
            ));
          }
          if (/^\*\*[^*]+\*\*$/.test(p)) return <strong key={i}>{p.slice(2, -2)}</strong>;
          if (/^_[^_]+_$/.test(p)) return <em key={i} className="text-[#61738A]">{p.slice(1, -1)}</em>;
          return <React.Fragment key={i}>{p}</React.Fragment>;
        })}
      </React.Fragment>
    );
  };
  return (
    <div className="space-y-1.5 text-[13px] leading-relaxed text-[#172B4D]">
      {text.split('\n').map((line, i) => {
        const l = line.trim();
        if (!l) return <div key={i} className="h-1" />;
        if (l.startsWith('## ')) return <h3 key={i} className="text-[13px] font-semibold mt-3 text-[#172B4D]">{renderInline(l.slice(3), i)}</h3>;
        if (l.startsWith('# ')) return <h3 key={i} className="text-[14px] font-semibold mt-3">{renderInline(l.slice(2), i)}</h3>;
        if (/^[-*•]\s+/.test(l)) return <p key={i} className="pl-4 relative"><span className="absolute left-1 text-[#8A99AB]">•</span>{renderInline(l.replace(/^[-*•]\s+/, ''), i)}</p>;
        return <p key={i}>{renderInline(l, i)}</p>;
      })}
    </div>
  );
}

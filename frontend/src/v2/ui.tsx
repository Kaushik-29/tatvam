import React from 'react';
import { AlertTriangle, HelpCircle, Inbox, Loader2, OctagonAlert, ShieldCheck } from 'lucide-react';
import type { Action } from './types';

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ');

export function Card({ title, subtitle, actions, children, className, flush }: {
  title?: React.ReactNode; subtitle?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode; className?: string;
  /** Remove body padding (for edge-to-edge lists and tables). */
  flush?: boolean;
}) {
  return (
    <section className={cx('bg-white rounded-[22px] border border-line/70 shadow-card', className)}>
      {(title || actions) && (
        <header className="px-6 pt-5 pb-1 flex items-start justify-between gap-4">
          <div className="min-w-0">
            {title && <h2 className="text-[17px] font-semibold tracking-[-0.01em] text-ink">{title}</h2>}
            {subtitle && <p className="text-[13px] text-muted mt-0.5">{subtitle}</p>}
          </div>
          {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
        </header>
      )}
      <div className={flush ? 'pb-2' : 'px-6 pb-6 pt-4'}>{children}</div>
    </section>
  );
}

export function PageHeader({ title, description, actions, eyebrow }: {
  title: string; description?: React.ReactNode; actions?: React.ReactNode; eyebrow?: string;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 mb-8 animate-rise">
      <div className="min-w-0">
        {eyebrow && <p className="text-[13px] font-semibold text-accent mb-1.5">{eyebrow}</p>}
        <h1 className="font-display text-[32px] sm:text-[34px] font-semibold tracking-[-0.025em] leading-[1.1] text-ink">{title}</h1>
        {description && <p className="text-[16px] text-muted mt-2.5 max-w-3xl leading-relaxed">{description}</p>}
      </div>
      {actions}
    </div>
  );
}

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export function Button({ variant = 'primary', size = 'md', className, ...p }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant; size?: 'sm' | 'md' | 'lg';
}) {
  const styles: Record<ButtonVariant, string> = {
    primary: 'bg-accent text-white hover:bg-accent-strong shadow-[0_1px_2px_rgba(10,102,228,0.28)]',
    secondary: 'bg-white text-ink border border-line hover:bg-panel hover:border-[#d2d2d7]',
    ghost: 'text-accent hover:bg-accent-soft',
    danger: 'bg-white text-danger border border-danger-line hover:bg-danger-soft',
  };
  const sizes = { sm: 'h-8 px-3.5 text-[13px]', md: 'h-10 px-[18px] text-[14px]', lg: 'h-12 px-6 text-[15px]' };
  return (
    <button
      {...p}
      className={cx('inline-flex items-center justify-center gap-2 rounded-full font-medium whitespace-nowrap select-none cursor-pointer',
        'transition-all duration-200 active:scale-[0.97] disabled:opacity-40 disabled:cursor-not-allowed disabled:active:scale-100',
        styles[variant], sizes[size], className)}
    />
  );
}

const fieldBase = 'w-full bg-white text-[15px] text-ink border border-line rounded-[12px] outline-none transition-[border-color,box-shadow] duration-200 ' +
  'placeholder:text-[#a1a1a6] hover:border-[#d2d2d7] focus:border-accent focus:ring-4 focus:ring-accent/15 disabled:bg-panel disabled:text-muted';

export function Input(p: React.InputHTMLAttributes<HTMLInputElement>) {
  const file = p.type === 'file';
  return (
    <input {...p} className={cx(fieldBase, file
      ? 'h-11 px-1.5 py-1.5 text-[14px] text-muted file:mr-3 file:h-8 file:px-4 file:rounded-full file:border-0 file:bg-accent-soft file:text-accent file:font-medium file:cursor-pointer hover:file:bg-accent-tint'
      : 'h-11 px-3.5', p.className)} />
  );
}

export function Select(p: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select {...p} className={cx(fieldBase, 'h-11 pl-3.5 pr-9 appearance-none cursor-pointer bg-no-repeat bg-[right_12px_center] bg-[length:14px]',
      "bg-[url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%236e6e73' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")]",
      p.className)} />
  );
}

export function TextArea(p: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...p} className={cx(fieldBase, 'px-3.5 py-3 leading-relaxed resize-y', p.className)} />;
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-[13px] font-medium text-ink-2 mb-1.5">{label}</span>
      {children}
      {hint && <span className="block text-[12px] text-faint mt-1.5">{hint}</span>}
    </label>
  );
}

const GOOD = 'bg-success-soft text-success-ink';
const BLUE = 'bg-accent-soft text-accent';
const NEUTRAL = 'bg-canvas text-muted';
const WARN = 'bg-warn-soft text-warn-ink';
const BAD = 'bg-danger-soft text-danger-ink';
const STATUS_STYLES: Record<string, string> = {
  CONFIRMED: GOOD, confirmed: GOOD, SUPPORTED: GOOD,
  'PATIENT-REPORTED': BLUE, patient_reported: BLUE,
  DERIVED: NEUTRAL, derived: NEUTRAL,
  'EXTRACTED-UNCONFIRMED': WARN, unconfirmed: WARN, UNCONFIRMED: WARN,
  UNSUPPORTED: BAD, INVALID_CITATION: BAD, refuted: BAD,
  HIGH: BAD, MEDIUM: WARN, LOW: NEUTRAL,
  INFO: BLUE, SAFETY_ALLOWED: BLUE,
};

export function Pill({ value, label }: { value: string; label?: string }) {
  const text = (label ?? value).replace(/_/g, ' ');
  return (
    <span className={cx('inline-flex items-center h-[22px] px-2.5 rounded-full text-[12px] font-medium whitespace-nowrap capitalize',
      STATUS_STYLES[value] ?? NEUTRAL)}>
      {text.toLowerCase()}
    </span>
  );
}

const ACTIONS: Record<Action, { label: string; icon: React.ReactNode; tone: string; dot: string; text: string }> = {
  EXPLAIN: {
    label: 'Explained with verified evidence', icon: <ShieldCheck className="w-[18px] h-[18px]" />,
    tone: 'bg-success-soft text-success-ink', dot: 'bg-success text-white',
    text: 'Only statements that passed claim verification are shown.',
  },
  ASK: {
    label: 'A little more information needed', icon: <HelpCircle className="w-[18px] h-[18px]" />,
    tone: 'bg-accent-soft text-accent-strong', dot: 'bg-accent text-white',
    text: 'MedResolve asks before answering rather than guessing.',
  },
  ABSTAIN_AND_NAVIGATE: {
    label: 'Please speak with a clinician', icon: <AlertTriangle className="w-[18px] h-[18px]" />,
    tone: 'bg-warn-soft text-warn-ink', dot: 'bg-warn text-white',
    text: 'A conflict, or a diagnostic or prescribing decision, needs professional assessment.',
  },
  EMERGENCY_OVERRIDE: {
    label: 'Emergency warning', icon: <OctagonAlert className="w-[18px] h-[18px]" />,
    tone: 'bg-danger-soft text-danger-ink', dot: 'bg-danger text-white',
    text: 'Red-flag symptoms were detected, so no other content was generated.',
  },
};

export function ActionBanner({ action, reason }: { action: Action; reason?: string }) {
  const a = ACTIONS[action] ?? ACTIONS.EXPLAIN;
  return (
    <div className={cx('rounded-[16px] px-4 py-3.5 flex items-start gap-3 animate-fade', a.tone)} role={action === 'EMERGENCY_OVERRIDE' ? 'alert' : 'status'}>
      <span className={cx('mt-px flex h-8 w-8 shrink-0 items-center justify-center rounded-full', a.dot)}>{a.icon}</span>
      <div className="min-w-0">
        <p className="text-[15px] font-semibold leading-snug">{a.label}</p>
        <p className="text-[14px] opacity-85 mt-0.5 leading-snug">{reason || a.text}</p>
      </div>
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2.5 text-[14px] text-muted animate-fade" role="status">
      <Loader2 className="w-[18px] h-[18px] animate-spin text-accent" /> {label}
    </span>
  );
}

export function Empty({ title, children, icon }: { title: string; children?: React.ReactNode; icon?: React.ReactNode }) {
  return (
    <div className="text-center py-12 px-4 animate-fade">
      <span className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-canvas text-faint">
        {icon ?? <Inbox className="w-[22px] h-[22px]" />}
      </span>
      <p className="text-[16px] font-semibold text-ink">{title}</p>
      {children && <div className="text-[14px] text-muted mt-1.5 max-w-md mx-auto leading-relaxed">{children}</div>}
    </div>
  );
}

export function ErrorNote({ error }: { error: string | null }) {
  if (!error) return null;
  return <p role="alert" className="text-[14px] text-danger-ink bg-danger-soft rounded-[12px] px-4 py-3 animate-fade">{error}</p>;
}

export function SuccessNote({ children }: { children: React.ReactNode }) {
  return <p role="status" className="text-[14px] text-success-ink bg-success-soft rounded-[12px] px-4 py-3 animate-fade">{children}</p>;
}

/** Label / value list used for profile and status details. */
export function DetailList({ rows, labelWidth = 120 }: { rows: [React.ReactNode, React.ReactNode][]; labelWidth?: number }) {
  return (
    <dl className="divide-y divide-line-soft text-[15px]">
      {rows.map(([k, v], i) => (
        <div key={i} className="grid gap-4 py-2.5 first:pt-0 last:pb-0" style={{ gridTemplateColumns: `${labelWidth}px 1fr` }}>
          <dt className="text-muted">{k}</dt>
          <dd className="text-ink min-w-0">{v}</dd>
        </div>
      ))}
    </dl>
  );
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
                className={cx('mx-0.5 inline-flex items-center h-[20px] px-1.5 rounded-[6px] text-[11.5px] font-semibold align-[1px] tabular-nums cursor-pointer transition-colors',
                  a.startsWith('E') ? 'bg-accent-soft text-accent hover:bg-accent-tint' : 'bg-canvas text-muted hover:bg-line')}
                title={a.startsWith('E') ? 'Open this record from your history' : 'Open this medical reference passage'}>
                {a}
              </button>
            ));
          }
          if (/^\*\*[^*]+\*\*$/.test(p)) return <strong key={i} className="font-semibold">{p.slice(2, -2)}</strong>;
          if (/^_[^_]+_$/.test(p)) return <em key={i} className="text-muted not-italic text-[14px]">{p.slice(1, -1)}</em>;
          return <React.Fragment key={i}>{p}</React.Fragment>;
        })}
      </React.Fragment>
    );
  };
  return (
    <div className="space-y-2 text-[16px] leading-[1.65] text-ink">
      {text.split('\n').map((line, i) => {
        const l = line.trim();
        if (!l) return <div key={i} className="h-1" />;
        if (l.startsWith('## ')) return <h3 key={i} className="text-[17px] font-semibold tracking-[-0.01em] pt-3 first:pt-0">{renderInline(l.slice(3), i)}</h3>;
        if (l.startsWith('# ')) return <h3 key={i} className="text-[19px] font-semibold tracking-[-0.015em] pt-3 first:pt-0">{renderInline(l.slice(2), i)}</h3>;
        if (/^[-*•]\s+/.test(l)) {
          return (
            <p key={i} className="pl-5 relative">
              <span className="absolute left-1.5 top-[0.7em] h-[5px] w-[5px] rounded-full bg-ghost" />
              {renderInline(l.replace(/^[-*•]\s+/, ''), i)}
            </p>
          );
        }
        return <p key={i}>{renderInline(l, i)}</p>;
      })}
    </div>
  );
}

import React from 'react';
import {
  LayoutDashboard,
  User,
  Stethoscope,
  FileText,
  ScanText,
  TableProperties,
  AlertCircle,
  BookOpen,
  Sparkles,
  ShieldAlert,
  History,
  BarChart2,
  Settings,
  ChevronLeft,
  ChevronRight,
  Menu,
} from 'lucide-react';

export type ScreenId =
  | 'overview'
  | 'profile'
  | 'symptom-assessment'
  | 'documents'
  | 'ocr-review'
  | 'evidence-ledger'
  | 'conflicts'
  | 'knowledge'
  | 'ai-summary'
  | 'safety-centre'
  | 'history'
  | 'research'
  | 'settings';

interface SidebarProps {
  activeScreen: ScreenId;
  onNavigate: (screen: ScreenId) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  unconfirmedCount?: number;
  conflictsCount?: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeScreen,
  onNavigate,
  isCollapsed,
  onToggleCollapse,
  unconfirmedCount = 0,
  conflictsCount = 0,
}) => {
  const navItems: { id: ScreenId; label: string; icon: React.ReactNode; badge?: number; badgeColor?: string }[] = [
    { id: 'overview', label: 'Overview', icon: <LayoutDashboard className="w-4 h-4" /> },
    { id: 'profile', label: 'Patient Profile', icon: <User className="w-4 h-4" /> },
    { id: 'symptom-assessment', label: 'Symptom Assessment', icon: <Stethoscope className="w-4 h-4" /> },
    { id: 'documents', label: 'Medical Documents', icon: <FileText className="w-4 h-4" /> },
    {
      id: 'ocr-review',
      label: 'OCR Review',
      icon: <ScanText className="w-4 h-4" />,
      badge: unconfirmedCount > 0 ? unconfirmedCount : undefined,
      badgeColor: 'bg-[#FFF0B3] text-[#A96B16]',
    },
    { id: 'evidence-ledger', label: 'Evidence Ledger', icon: <TableProperties className="w-4 h-4" /> },
    {
      id: 'conflicts',
      label: 'Conflict Detection',
      icon: <AlertCircle className="w-4 h-4" />,
      badge: conflictsCount > 0 ? conflictsCount : undefined,
      badgeColor: 'bg-[#FFEBE6] text-[#C23E4A]',
    },
    { id: 'knowledge', label: 'Medical Knowledge', icon: <BookOpen className="w-4 h-4" /> },
    { id: 'ai-summary', label: 'AI Evidence Summary', icon: <Sparkles className="w-4 h-4" /> },
    { id: 'safety-centre', label: 'Safety & Action Policy', icon: <ShieldAlert className="w-4 h-4" /> },
    { id: 'history', label: 'Assessment History', icon: <History className="w-4 h-4" /> },
    { id: 'research', label: 'Research Dashboard', icon: <BarChart2 className="w-4 h-4" /> },
    { id: 'settings', label: 'System Settings', icon: <Settings className="w-4 h-4" /> },
  ];

  return (
    <aside
      className={`bg-white border-r border-[#DFE7F1] flex flex-col transition-all duration-200 select-none ${
        isCollapsed ? 'w-16' : 'w-64'
      }`}
    >
      {/* Sidebar Header / Collapse button */}
      <div className="h-12 border-b border-[#DFE7F1] px-3 flex items-center justify-between">
        {!isCollapsed && (
          <span className="text-[11px] font-semibold text-[#8A99AB] uppercase tracking-wider">
            Clinical Navigation
          </span>
        )}
        <button
          onClick={onToggleCollapse}
          className="p-1 rounded text-[#61738A] hover:bg-[#F1F5FA] transition-colors ml-auto"
          title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Nav items list */}
      <nav className="flex-1 overflow-y-auto py-2 space-y-0.5 px-2">
        {navItems.map((item) => {
          const isActive = activeScreen === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              title={isCollapsed ? item.label : undefined}
              className={`w-full flex items-center space-x-3 px-2.5 py-2 rounded-md text-xs transition-colors ${
                isActive
                  ? 'bg-[#EAF2FC] text-[#3675CA] font-medium'
                  : 'text-[#61738A] hover:bg-[#F1F5FA] hover:text-[#172B4D]'
              }`}
            >
              <div className={`${isActive ? 'text-[#3675CA]' : 'text-[#61738A]'}`}>
                {item.icon}
              </div>
              {!isCollapsed && (
                <span className="truncate flex-1 text-left">{item.label}</span>
              )}
              {!isCollapsed && item.badge !== undefined && (
                <span
                  className={`text-[10px] font-semibold px-1.5 py-0.2 rounded-full tabular-nums ${
                    item.badgeColor || 'bg-gray-100 text-gray-700'
                  }`}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Bottom Prototype Notice */}
      {!isCollapsed && (
        <div className="p-3 border-t border-[#DFE7F1] bg-[#FAF9F6]">
          <p className="text-[10px] font-semibold text-[#172B4D]">EviDx-Grounding Protocol</p>
          <p className="text-[9px] text-[#8A99AB] leading-tight mt-0.5">
            Non-arbitrating selective evidence reconciliation v5.3.
          </p>
        </div>
      )}
    </aside>
  );
};

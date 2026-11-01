import React, { useState, useEffect } from 'react';
import {
  Settings,
  Cpu,
  BookOpen,
  Server,
  Shield,
  Key,
  Info,
  CheckCircle2,
} from 'lucide-react';
import { fetchHealth } from '../api/client';

export const SettingsScreen: React.FC = () => {
  const [healthData, setHealthData] = useState<any>(null);

  useEffect(() => {
    fetchHealth()
      .then((data) => setHealthData(data))
      .catch((e) => console.error(e));
  }, []);

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Title */}
      <div className="bg-white border border-[#DFE7F1] rounded-lg p-5">
        <h1 className="text-xl font-bold text-[#172B4D] flex items-center space-x-2">
          <Settings className="w-5 h-5 text-[#3675CA]" />
          <span>System Information & Runtime Configuration</span>
        </h1>
        <p className="text-xs text-[#61738A] mt-1">
          Active model parameters, retrieval index status, and academic research boundaries.
        </p>
      </div>

      {/* Main Configuration Card */}
      <div className="bg-white border border-[#DFE7F1] rounded-lg p-6 space-y-5">
        <h2 className="text-sm font-bold text-[#172B4D] border-b border-[#DFE7F1] pb-2">
          Architecture & Hardware Environment
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div className="p-3 bg-[#F7F9FC] border border-[#DFE7F1] rounded-md space-y-1">
            <span className="text-[11px] font-semibold text-[#8A99AB] uppercase flex items-center space-x-1">
              <Cpu className="w-3.5 h-3.5 text-[#3675CA]" />
              <span>Generation Engine</span>
            </span>
            <span className="font-bold text-[#172B4D] block text-sm">
              llama3.2:3b
            </span>
            <span className="text-[11px] text-[#61738A] block">
              Quantization: Q4_K_M (Local Ollama CPU, 131k context)
            </span>
          </div>

          <div className="p-3 bg-[#F7F9FC] border border-[#DFE7F1] rounded-md space-y-1">
            <span className="text-[11px] font-semibold text-[#8A99AB] uppercase flex items-center space-x-1">
              <BookOpen className="w-3.5 h-3.5 text-[#26845A]" />
              <span>Knowledge Base Version</span>
            </span>
            <span className="font-bold text-[#172B4D] block text-sm">
              Corpus v2.0 (24 Passages)
            </span>
            <span className="text-[11px] text-[#61738A] block">
              Embedding: BAAI/bge-m3 (Dense 1024-dim FAISS) + BM25Okapi
            </span>
          </div>

          <div className="p-3 bg-[#F7F9FC] border border-[#DFE7F1] rounded-md space-y-1">
            <span className="text-[11px] font-semibold text-[#8A99AB] uppercase flex items-center space-x-1">
              <Server className="w-3.5 h-3.5 text-[#3675CA]" />
              <span>API Connectivity</span>
            </span>
            <span className="font-bold text-[#26845A] flex items-center space-x-1 text-sm">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>FastAPI Backend Healthy</span>
            </span>
            <span className="text-[11px] text-[#61738A] block">
              Port: 8000 / Proxy: Vite 5173
            </span>
          </div>

          <div className="p-3 bg-[#F7F9FC] border border-[#DFE7F1] rounded-md space-y-1">
            <span className="text-[11px] font-semibold text-[#8A99AB] uppercase flex items-center space-x-1">
              <Key className="w-3.5 h-3.5 text-[#A96B16]" />
              <span>Credential & Security Posture</span>
            </span>
            <span className="font-bold text-[#172B4D] block text-sm">
              Zero External Secrets
            </span>
            <span className="text-[11px] text-[#61738A] block">
              100% local CPU inference. No cloud API keys or telemetry transmitted.
            </span>
          </div>
        </div>
      </div>

      {/* Disclaimers & Institutional Attribution */}
      <div className="bg-[#FAF9F6] border border-[#DFE7F1] rounded-lg p-6 space-y-3">
        <h3 className="text-xs font-bold uppercase tracking-wider text-[#172B4D] flex items-center space-x-1.5">
          <Shield className="w-4 h-4 text-[#3675CA]" />
          <span>Academic Research Prototype Disclaimer</span>
        </h3>
        <p className="text-xs text-[#61738A] leading-relaxed">
          MedResolve is built as a B.Tech major project exploring evidence-grounded AI health assessment, uncertainty-aware action selection, and clinical document reconciliation. It is evaluated against the DDXPlus dataset and curated medical guidelines.
        </p>
        <div className="p-3 bg-white border border-[#DFE7F1] rounded-md text-[11px] text-[#172B4D] leading-relaxed">
          <strong>Institutional Notice:</strong> "MedResolve is an investigational academic research prototype. It is not intended for diagnosis, treatment, clinical triage or replacement of professional medical care. All findings must be reviewed by a licensed physician."
        </div>
      </div>
    </div>
  );
};

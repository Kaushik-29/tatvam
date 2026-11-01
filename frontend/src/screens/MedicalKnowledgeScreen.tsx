import React, { useState, useEffect } from 'react';
import {
  BookOpen,
  Search,
  ExternalLink,
  Shield,
  Layers,
  FileText,
  Building,
  Calendar,
} from 'lucide-react';
import { RetrievedPassage } from '../types';
import { fetchKnowledgeBase, queryKnowledge } from '../api/client';

export const MedicalKnowledgeScreen: React.FC = () => {
  const [passages, setPassages] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [retrievedResults, setRetrievedResults] = useState<RetrievedPassage[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [totalPassages, setTotalPassages] = useState(24);

  useEffect(() => {
    loadCorpus();
  }, []);

  const loadCorpus = async () => {
    try {
      const data = await fetchKnowledgeBase();
      setPassages(data.passages || []);
      setTotalPassages(data.total_passages || 24);
    } catch (e) {
      console.error(e);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setIsSearching(true);
    try {
      const data = await queryKnowledge(searchQuery, 5);
      setRetrievedResults(data.results || []);
    } catch (e) {
      console.error(e);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Title */}
      <div className="bg-white border border-[#DFE7F1] rounded-lg p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-[10px] font-semibold bg-[#EAF2FC] text-[#3675CA] px-2 py-0.5 rounded border border-[#AFCFF2]">
                CORPUS v2.0
              </span>
              <span className="text-xs text-[#8A99AB] tabular-nums">{totalPassages} Indexed Passages</span>
            </div>
            <h1 className="text-xl font-bold text-[#172B4D] flex items-center space-x-2 mt-1">
              <BookOpen className="w-5 h-5 text-[#3675CA]" />
              <span>Medical Knowledge Corpus & Hybrid Retriever</span>
            </h1>
            <p className="text-xs text-[#61738A]">
              Curated medical literature (MOHFW Standard Treatment Guidelines, StatPearls, British Thoracic Society, European Society of Cardiology) with verified provenance.
            </p>
          </div>
        </div>
      </div>

      {/* Provenance Integrity Notice (PART 5.2 requirement) */}
      <div className="bg-[#FAF9F6] border border-[#DFE7F1] rounded-lg p-4 flex items-start space-x-3">
        <Shield className="w-5 h-5 text-[#3675CA] shrink-0 mt-0.5" />
        <div className="text-xs text-[#61738A] leading-relaxed">
          <strong className="text-[#172B4D]">Citation Guarantee:</strong> MedResolve maintains an inviolable separation between peer-reviewed medical guidelines and patient-submitted evidence. All citations (`[DOC_*_P*]`) are strictly validated against genuine passages in the knowledge base. Hallucinated citation IDs are rejected at inference time.
        </div>
      </div>

      {/* Interactive Hybrid Retriever Query Box */}
      <div className="bg-white border border-[#DFE7F1] rounded-lg p-5 shadow-xs">
        <h2 className="text-sm font-bold text-[#172B4D] mb-1">
          Test Hybrid Retrieval Pipeline (BGE-M3 FAISS + BM25 RRF)
        </h2>
        <p className="text-xs text-[#61738A] mb-3">
          Enter clinical symptoms or medical concepts to test live hybrid search and score fusion.
        </p>

        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-[#8A99AB] absolute left-3 top-3" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="e.g., retrosternal burning pain antacid response differential diagnosis GERD vs ACS"
              className="w-full text-xs pl-9 pr-3 py-2.5 rounded-md border border-[#DFE7F1] focus:border-[#3675CA] focus:ring-1 focus:ring-[#3675CA] outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={isSearching || !searchQuery.trim()}
            className="px-4 py-2 bg-[#3675CA] hover:bg-[#265EAA] text-white rounded-md text-xs font-medium transition-colors shadow-sm disabled:opacity-50"
          >
            {isSearching ? 'Searching...' : 'Retrieve Passages'}
          </button>
        </form>

        {/* Live Search Results */}
        {retrievedResults.length > 0 && (
          <div className="mt-5 space-y-3 pt-4 border-t border-[#DFE7F1]">
            <span className="text-xs font-semibold text-[#172B4D] block">
              Top Ranked Hybrid Passages for: <em className="text-[#3675CA]">"{searchQuery}"</em>
            </span>
            {retrievedResults.map((r, i) => (
              <div
                key={r.passage_id}
                className="p-4 border border-[#AFCFF2] bg-[#EAF2FC]/30 rounded-lg space-y-2 text-xs"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-[11px]">
                  <span className="font-bold text-[#3675CA]">
                    #{i + 1} — {r.document_title}
                  </span>
                  <div className="flex items-center space-x-2">
                    <span className="font-mono bg-white px-2 py-0.5 rounded border border-[#DFE7F1] text-[#172B4D]">
                      {r.passage_id}
                    </span>
                    <span className="font-semibold text-[#26845A] tabular-nums">
                      RRF Score: {r.score}
                    </span>
                  </div>
                </div>

                <p className="text-xs text-[#172B4D] leading-relaxed bg-white p-3 rounded border border-[#DFE7F1]">
                  {r.text}
                </p>

                <div className="flex flex-wrap items-center justify-between text-[11px] text-[#61738A] pt-1">
                  <span>Organization: {r.organization}</span>
                  <a
                    href={r.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[#3675CA] hover:underline flex items-center space-x-1"
                  >
                    <span>Source Guideline</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Full Corpus Passages List */}
      <div className="bg-white border border-[#DFE7F1] rounded-lg p-5">
        <div className="flex items-center justify-between border-b border-[#DFE7F1] pb-3 mb-4">
          <div>
            <h2 className="text-sm font-bold text-[#172B4D]">
              Complete Indexed Clinical Guidelines ({passages.length})
            </h2>
            <p className="text-xs text-[#61738A]">
              StatPearls, MOHFW, British Thoracic Society, and European Society of Cardiology
            </p>
          </div>
        </div>

        <div className="space-y-4">
          {passages.map((p) => {
            const meta = p.metadata || {};
            return (
              <div
                key={p.passage_id}
                className="p-4 border border-[#DFE7F1] rounded-lg hover:bg-[#F7F9FC] transition-colors text-xs space-y-2"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                  <div>
                    <span className="font-bold text-xs text-[#172B4D]">
                      {meta.document_title || 'Medical Guideline'}
                    </span>
                    <span className="text-[11px] text-[#61738A] block">
                      Section: {meta.section_heading || 'General Clinical Guidance'}
                    </span>
                  </div>
                  <span className="font-mono text-[11px] bg-[#F1F5FA] px-2 py-0.5 rounded border border-[#DFE7F1] text-[#3675CA] shrink-0">
                    {p.passage_id}
                  </span>
                </div>

                <p className="text-xs text-[#172B4D] leading-relaxed bg-[#FAF9F6] p-3 rounded border border-[#DFE7F1]">
                  {p.text}
                </p>

                <div className="flex flex-wrap items-center justify-between text-[11px] text-[#8A99AB] pt-1">
                  <div className="flex items-center space-x-3">
                    <span className="flex items-center space-x-1">
                      <Building className="w-3 h-3" />
                      <span>{meta.document_organization}</span>
                    </span>
                    <span className="flex items-center space-x-1">
                      <Calendar className="w-3 h-3" />
                      <span className="tabular-nums">{meta.publication_date || 'Date unspecified'}</span>
                    </span>
                  </div>

                  <span className="text-[10px] text-[#61738A]">
                    License: {meta.license_or_reuse_conditions || 'Clinical Guidance'}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

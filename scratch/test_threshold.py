import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from experiments.knowledge_retriever import MedicalKnowledgeBase

kb = MedicalKnowledgeBase()
kb.build_lexical_index()
kb.build_dense_index()

# In-domain
q_in = "Patient with retrosternal burning after meals and acid taste in mouth"
res_in_dense = kb.search_dense(q_in, top_k=2)
res_in_lex = kb.search_lexical(q_in, top_k=2)
res_in_hyb = kb.search_hybrid(q_in, top_k=2)

print("In-domain Dense scores:", [r.score for r in res_in_dense])
print("In-domain Lexical scores:", [r.score for r in res_in_lex])
print("In-domain Hybrid scores:", [r.score for r in res_in_hyb])

# Out-of-domain
q_out = "Surgical operative protocol for acute pediatric appendectomy and antibiotic dosing"
res_out_dense = kb.search_dense(q_out, top_k=2)
res_out_lex = kb.search_lexical(q_out, top_k=2)
res_out_hyb = kb.search_hybrid(q_out, top_k=2)

print("Out-of-domain Dense scores:", [r.score for r in res_out_dense])
print("Out-of-domain Lexical scores:", [r.score for r in res_out_lex])
print("Out-of-domain Hybrid scores:", [r.score for r in res_out_hyb])

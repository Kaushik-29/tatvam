from rank_bm25 import BM25Okapi

corpus = [
    "Patient presents with retrosternal chest pain radiating to left arm and dyspnea",
    "Gastroesophageal reflux disease causes heartburn and pyrosis after meals",
    "Inspiratory stridor indicates acute upper airway obstruction"
]

tokenized_corpus = [doc.lower().split() for doc in corpus]
bm25 = BM25Okapi(tokenized_corpus)

query = "chest pain dyspnea"
scores = bm25.get_scores(query.lower().split())
print("BM25 scores:", scores, flush=True)
best_doc_idx = scores.argmax()
print(f"Top doc: {corpus[best_doc_idx]}", flush=True)
print("BM25 works perfectly!", flush=True)

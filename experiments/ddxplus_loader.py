"""
MedResolve — DDXPlus Dataset Loader & Preprocessing
Module for loading, parsing, encoding, and managing splits for the DDXPlus benchmark.
Designed to guarantee:
1. Strict prevention of target and differential-diagnosis leakage.
2. Exact vocabulary matching with official release_evidences.json and release_conditions.json.
3. Memory-efficient sparse feature encoding (974 features: Age, Sex, 972 binary/categorical tokens).
4. Reproducible development subsets preserving official validation and test splits.
"""

import ast
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from scipy import sparse

logger = logging.getLogger("MedResolve.DataLoader")

DEFAULT_RAW_DIR = Path("data/raw/ddxplus")
DEFAULT_EXTRACTED_DIR = DEFAULT_RAW_DIR / "extracted"

class DDXPlusLoader:
    def __init__(self, raw_dir: Union[str, Path] = DEFAULT_RAW_DIR):
        self.raw_dir = Path(raw_dir)
        self.extracted_dir = self.raw_dir / "extracted"
        self.conditions_path = self.raw_dir / "release_conditions.json"
        self.evidences_path = self.raw_dir / "release_evidences.json"

        self.conditions_raw: Dict = {}
        self.conditions_by_name: Dict[str, Dict] = {}
        self.pathology_list: List[str] = []
        self.pathology_to_idx: Dict[str, int] = {}
        self.idx_to_pathology: Dict[int, str] = {}

        self.evidences: Dict = {}
        self.evidence_tokens: List[str] = []
        self.token_to_idx: Dict[str, int] = {}

        self._load_metadata()

    def _load_metadata(self):
        """Loads and parses release_conditions.json and release_evidences.json."""
        if not self.conditions_path.exists():
            raise FileNotFoundError(f"Missing conditions file: {self.conditions_path}")
        if not self.evidences_path.exists():
            raise FileNotFoundError(f"Missing evidences file: {self.evidences_path}")

        with open(self.conditions_path, "r", encoding="utf-8") as f:
            self.conditions_raw = json.load(f)

        # The patient CSVs in the English DDXPlus release use 'cond-name-eng'
        # We index conditions by English name, French name, and raw key for seamless lookup
        self.conditions_by_name = {}
        canonical_names = set()
        for raw_k, meta in self.conditions_raw.items():
            eng_name = meta.get("cond-name-eng", raw_k)
            fr_name = meta.get("cond-name-fr", raw_k)
            cond_name = meta.get("condition_name", raw_k)

            canonical_names.add(eng_name)
            self.conditions_by_name[eng_name] = meta
            self.conditions_by_name[fr_name] = meta
            self.conditions_by_name[cond_name] = meta
            self.conditions_by_name[raw_k] = meta

        self.pathology_list = sorted(list(canonical_names))
        self.pathology_to_idx = {name: i for i, name in enumerate(self.pathology_list)}
        self.idx_to_pathology = {i: name for i, name in enumerate(self.pathology_list)}

        with open(self.evidences_path, "r", encoding="utf-8") as f:
            self.evidences = json.load(f)

        # Build comprehensive token vocabulary (972 distinct binary / categorical tokens)
        tokens = []
        for name, meta in sorted(self.evidences.items()):
            dtype = meta.get("data_type", "B")
            if dtype == "B":
                tokens.append(name)
            else:
                for val in meta.get("possible-values", []):
                    tokens.append(f"{name}_@_{val}")

        self.evidence_tokens = sorted(tokens)
        self.token_to_idx = {token: i for i, token in enumerate(self.evidence_tokens)}

    def get_split_path(self, split: str) -> Path:
        """Returns the extracted CSV path or falls back to zip if necessary."""
        valid_splits = {"train", "validate", "test"}
        if split not in valid_splits:
            raise ValueError(f"Invalid split '{split}'. Must be one of {valid_splits}")

        extracted_csv = self.extracted_dir / split / f"release_{split}_patients.csv"
        if extracted_csv.exists():
            return extracted_csv

        zip_path = self.raw_dir / f"release_{split}_patients.zip"
        if zip_path.exists():
            return zip_path

        raise FileNotFoundError(f"Neither extracted CSV nor ZIP archive found for split '{split}' in {self.raw_dir}")

    def load_raw_dataframe(
        self, split: str, nrows: Optional[int] = None, usecols: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """Loads a raw pandas DataFrame for the requested split."""
        path = self.get_split_path(split)
        if path.suffix == ".zip":
            entry_name = f"release_{split}_patients"
            import zipfile
            with zipfile.ZipFile(path, "r") as zf:
                with zf.open(entry_name) as f:
                    df = pd.read_csv(f, nrows=nrows, usecols=usecols)
        else:
            df = pd.read_csv(path, nrows=nrows, usecols=usecols)
        return df

    @staticmethod
    def parse_list_column(val: Union[str, list]) -> list:
        """Safely parses stringified Python list representations."""
        if isinstance(val, list):
            return val
        if pd.isna(val) or not val:
            return []
        try:
            return ast.literal_eval(val)
        except Exception:
            return []

    def get_dev_subset(
        self, n: int = 50000, seed: int = 42, split: str = "train"
    ) -> pd.DataFrame:
        """
        Creates a reproducible development subset of up to n records
        from the specified split using a fixed random seed.
        Preserves pathology representation via stratified sampling.
        Caches to data/processed/ (gitignored) for instant reloading.
        """
        cache_path = Path("data/processed") / f"dev_{split}_{n}_seed{seed}.csv"
        if cache_path.exists():
            return pd.read_csv(cache_path)

        from sklearn.model_selection import train_test_split

        df = self.load_raw_dataframe(split)
        if len(df) <= n:
            return df

        sampled, _ = train_test_split(
            df,
            train_size=n,
            random_state=seed,
            stratify=df["PATHOLOGY"],
        )
        sampled = sampled.reset_index(drop=True)

        # Cache to data/processed if directory exists
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            sampled.to_csv(cache_path, index=False)
        except Exception:
            pass

        return sampled

    def extract_features_and_labels(
        self,
        df: pd.DataFrame,
        include_demographics: bool = True,
        evidence_mode: str = "all",
    ) -> Tuple[sparse.csr_matrix, np.ndarray, List[str]]:
        """
        Extracts feature matrix X and target array y.
        Strictly prevents target leakage:
        - PATHOLOGY and DIFFERENTIAL_DIAGNOSIS are excluded from X.
        - X is encoded as a sparse binary matrix over evidence tokens (+ age and sex).
        
        Args:
            df: Patient DataFrame
            include_demographics: Whether to prepend normalized Age and Sex
            evidence_mode: 'all' (uses complete EVIDENCES list) or 'initial' (uses INITIAL_EVIDENCE only)
        """
        forbidden_in_features = {"PATHOLOGY", "DIFFERENTIAL_DIAGNOSIS"}

        num_samples = len(df)
        num_evidence_tokens = len(self.evidence_tokens)

        rows = []
        cols = []

        if evidence_mode == "initial":
            if "INITIAL_EVIDENCE" not in df.columns:
                raise ValueError("Column 'INITIAL_EVIDENCE' missing from input DataFrame")
            for row_idx, init_ev in enumerate(df["INITIAL_EVIDENCE"]):
                if pd.notna(init_ev) and init_ev:
                    col_idx = self.token_to_idx.get(str(init_ev).strip())
                    if col_idx is not None:
                        rows.append(row_idx)
                        cols.append(col_idx)
        elif evidence_mode == "all":
            if "EVIDENCES" not in df.columns:
                raise ValueError("Column 'EVIDENCES' missing from input DataFrame")
            evidences_series = df["EVIDENCES"].apply(self.parse_list_column)
            for row_idx, ev_list in enumerate(evidences_series):
                for item in ev_list:
                    col_idx = self.token_to_idx.get(item)
                    if col_idx is not None:
                        rows.append(row_idx)
                        cols.append(col_idx)
        else:
            raise ValueError(f"Unknown evidence_mode '{evidence_mode}'. Choose from ['all', 'initial']")

        data = np.ones(len(rows), dtype=np.float32)
        ev_matrix = sparse.csr_matrix(
            (data, (rows, cols)), shape=(num_samples, num_evidence_tokens), dtype=np.float32
        )

        feature_names = list(self.evidence_tokens)

        if include_demographics:
            # AGE normalized (0 to 100 -> ~ 0.0 to 1.0)
            age = (df["AGE"].values.astype(np.float32) / 100.0).reshape(-1, 1)
            # SEX (M -> 1.0, F -> 0.0)
            sex = (df["SEX"].values == "M").astype(np.float32).reshape(-1, 1)

            demo_matrix = sparse.csr_matrix(np.hstack([age, sex]))
            X = sparse.hstack([demo_matrix, ev_matrix], format="csr")
            feature_names = ["DEMO_AGE_NORM", "DEMO_SEX_M"] + feature_names
        else:
            X = ev_matrix

        # Verify no forbidden target column exists in features
        for name in feature_names:
            if name in forbidden_in_features:
                raise ValueError(f"CRITICAL TARGET LEAKAGE: '{name}' detected in feature set!")

        # Target label
        y = np.array([self.pathology_to_idx.get(p, -1) for p in df["PATHOLOGY"]], dtype=np.int64)
        if (y == -1).any():
            invalid_count = int((y == -1).sum())
            unknown_labels = set(df.loc[y == -1, "PATHOLOGY"].unique())
            raise ValueError(f"Found {invalid_count} unknown pathology labels in target series: {unknown_labels}")

        return X, y, feature_names

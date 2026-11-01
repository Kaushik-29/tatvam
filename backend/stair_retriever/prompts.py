"""
Prompt formats.

ORIGINAL STAIR (paper Table 2) is reproduced verbatim in structure for the
SearchTome benchmark. STAIR-Clinical keeps the same shape (instruction, full ToC,
query, constrained leaf completion) but replaces the book with the patient's
record hierarchy and adds a second, iterative stage over concept groups.
"""

from typing import List, Tuple

from backend.patient_memory.hierarchy import LEAF_BY_PATH, TocNode

STAIR_INSTRUCTION = ("Pick the best section from the table of contents below which can answer the user query "
                     "below. Only generate the section name, do not generate any explanation!")
CLINICAL_INSTRUCTION = ("Pick the best section from the patient record table of contents below which contains "
                        "evidence needed to answer the query. Only generate the section name, do not generate "
                        "any explanation!")
CLINICAL_STAGE2_INSTRUCTION = ("Pick the best entry from this section of the patient record which contains evidence "
                               "needed to answer the query. Only generate the entry name, do not generate any "
                               "explanation!")


def original_stair_prompt(book: str, toc_lines: List[str], query: str) -> str:
    return (f"### Book: {book}\n{STAIR_INSTRUCTION}\n### Table of Contents\n" + "\n".join(toc_lines) +
            f"\n### Query: {query}\n### Section: leaf")


def clinical_stage1_prompt(header: str, toc: List[TocNode], query: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Returns (prompt, [(target_string, leaf_path)]). Targets are only leaves that exist in the ToC."""
    lines, targets = [], []
    for node in toc:
        if node.path not in LEAF_BY_PATH:          # a branch (level 1) — list its leaves
            lines.append(f"{node.number} {node.title}")
            for leaf in node.children:
                lines.append("leaf " + _strip_leaf(leaf.line()))
                targets.append((f"{leaf.number} {leaf.title}", leaf.path))
        else:
            lines.append("leaf " + _strip_leaf(node.line()))
            targets.append((f"{node.number} {node.title}", node.path))
    prompt = (f"### Patient record: {header}\n{CLINICAL_INSTRUCTION}\n### Table of Contents\n" + "\n".join(lines) +
              f"\n### Query: {query}\n### Section: leaf")
    return prompt, targets


def clinical_stage2_prompt(leaf: TocNode, query: str, max_children: int = 60) -> Tuple[str, List[Tuple[str, str]]]:
    lines, targets = [], []
    for c in leaf.children[:max_children]:
        lines.append("leaf " + _strip_leaf(c.line()))
        targets.append((f"{c.number} {c.title}", c.path))
    prompt = (f"### Patient record section: {leaf.number} {leaf.title}\n{CLINICAL_STAGE2_INSTRUCTION}\n"
              f"### Table of Contents\n" + "\n".join(lines) + f"\n### Query: {query}\n### Entry: leaf")
    return prompt, targets


def _strip_leaf(line: str) -> str:
    return line[5:] if line.startswith("leaf ") else line

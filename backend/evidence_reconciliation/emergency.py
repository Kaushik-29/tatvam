"""
Free-text emergency red-flag screen for NEW health concerns.

Runs BEFORE any retrieval or LLM generation. Deterministic and conservative:
a match short-circuits the pipeline into EMERGENCY_OVERRIDE. Complements the
existing ledger-based `EmergencySafetyOverrideDetector` (experiments/action_policy.py),
which it reuses for documented vital-sign extremes.
"""

import re
from dataclasses import dataclass, field
from typing import List

RED_FLAGS = [
    ("Possible acute coronary syndrome: chest pain/pressure with breathlessness, sweating, or radiation to arm/jaw",
     [r"chest (pain|pressure|tightness|heaviness)"], [r"short(ness)? of breath|breathless|can'?t breathe|sweat|clammy|left arm|jaw|radiat|nause"]),
    ("Severe breathing difficulty", [r"can(no|')?t breathe|cannot breathe|struggling to breathe|gasping|choking|lips? (turning )?blue|blue lips"], []),
    ("Possible stroke (face droop, arm weakness, speech difficulty)",
     [r"face (is )?droop|facial droop|slurred speech|can'?t speak|sudden(ly)? (weakness|numbness) (on|in) one side|one side of (my|the) (body|face)|arm weakness"], []),
    ("Loss of consciousness / fainting episode", [r"passed out|lost consciousness|unconscious|fainted|blacked out|syncope"], []),
    ("Possible anaphylaxis (swelling with breathing or throat symptoms)",
     [r"swell(ing|en)? (of )?(my |the )?(face|lips?|tongue|throat)|(face|lips?|tongue|throat)\b[^.;]{0,30}\b(swell|swollen)"
      r"|throat (is )?(closing|tight)|anaphyla"], []),
    ("Severe bleeding", [r"(vomit(ing)?|cough(ing)?) (up )?blood|blood in (my )?vomit|bleeding (that )?(won'?t|will not|doesn'?t) stop|heavy bleeding|black tarry stool"], []),
    ("Thoughts of self-harm or suicide", [r"suicid|kill myself|end my life|self[- ]harm|hurt myself|don'?t want to live"], []),
    ("Seizure", [r"seizure|convuls|fitting"], []),
    ("Sudden worst headache of life", [r"worst headache|thunderclap|sudden severe headache"], []),
    ("Possible meningitis (fever with stiff neck / rash that does not fade)", [r"stiff neck|neck stiffness|rash (that )?(doesn'?t|does not) fade"], [r"fever|temperature"]),
    ("Overdose or poisoning", [r"overdos|took too many|poison(ed|ing)?"], []),
]


@dataclass
class EmergencyScreen:
    is_emergency: bool
    red_flags: List[str] = field(default_factory=list)
    matched_text: List[str] = field(default_factory=list)


NEGATION = re.compile(r"\b(no|not|without|denies|never|n't)\b[^.;,]{0,25}$")


def _match(pattern: str, text: str):
    for m in re.finditer(pattern, text):
        if not NEGATION.search(text[max(0, m.start() - 30):m.start()]):
            return m
    return None


def screen_text(text: str) -> EmergencyScreen:
    t = " ".join((text or "").lower().split())
    flags, matched = [], []
    for label, primary, required in RED_FLAGS:
        m = next((mm for p in primary if (mm := _match(p, t))), None)
        if not m:
            continue
        if required and not any(_match(r, t) for r in required):
            continue
        flags.append(label)
        matched.append(m.group(0))
    return EmergencyScreen(bool(flags), flags, matched)

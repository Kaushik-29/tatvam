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
     [r"chest (pain|pressure|tightness|heaviness|burning|discomfort)|heart attack"],
     [r"short(ness)? of breath|breathless|can'?t breathe|sweat|clammy|left arm|arm pain|jaw|radiat|nause|heart attack"]),
    ("Severe breathing difficulty", [r"can(no|')?t breathe|cannot breathe|struggling to breathe|gasping|choking|lips? (turning )?blue|blue lips"
                                     r"|difficulty (in )?breathing|trouble breathing|hard to breathe|breathing (difficulty|problem)"], []),
    ("Possible stroke (face droop, arm weakness, speech difficulty)",
     [r"face (is )?droop|facial droop|slurred speech|can'?t speak|sudden(ly)? (weakness|numbness) (on|in) one side|one side of (my|the) (body|face)|arm weakness"
      r"|sudden(ly)? (weakness|numbness) (of|in) (my |the |his |her )?(right |left )?(arm|leg|face|hand)"
      r"|(difficulty|trouble|problem) (speaking|talking|producing words|finding words|getting (my |the )?words out)"], []),
    ("Loss of consciousness / fainting episode", [r"passed out|lost consciousness|loss of consciousness|unconscious|fainted|blacked out|syncope"], []),
    ("Possible anaphylaxis (swelling with breathing or throat symptoms)",
     [r"swell(ing|en)? (of )?(my |the )?(face|lips?|tongue|throat)|(face|lips?|tongue|throat)\b[^.;]{0,30}\b(swell|swollen)"
      r"|throat (is )?(closing|tight)|anaphyla"], []),
    ("Severe bleeding", [r"(vomit(ing)?|cough(ing)?) (up )?blood|blood in (my )?vomit|bleeding (that )?(won'?t|will not|doesn'?t) stop|heavy bleeding"
                         r"|black (and )?(tarry )?(stool|motion|poo)s?"], []),
    # WHO dengue fact sheet: severe-dengue warning signs (bleeding gums/nose, severe abdominal pain, persistent vomiting)
    ("Possible severe dengue warning signs (fever with bleeding, severe stomach pain or repeated vomiting)",
     [r"bleed(ing)? (from )?(the )?(gums|nose)|(gums?|nose) (is |are )?bleed|nose ?bleed|blood in (my )?(vomit|stool|urine)"
      r"|persistent vomiting|vomiting (again and again|repeatedly|continuously|non ?stop)|severe (stomach|abdominal|belly) pain"],
     [r"fever|temperature|dengue"]),
    ("Sudden confusion with fever, sweating, diabetes medicine or a head injury",
     [r"\b(confused|confusion|disoriented|not making sense)\b"],
     [r"fever|temperature|sweat|insulin|diabet|low sugar|head (injury|hit)|hit (my |his |her )?head|fell|fall"]),
    ("Pregnancy with bleeding, abdominal pain or severe headache / vision changes",
     [r"pregnan|missed (my )?periods?|amenorrh"],
     [r"bleeding|spotting|(abdominal|stomach|belly|pelvic) pain|severe headache|flashing lights|blurred vision|\bfits\b|seizure"]),
    ("Possible diabetic emergency (vomiting or abdominal pain in diabetes)",
     [r"diabet|insulin"], [r"vomit|abdominal pain|stomach pain|fruity breath|ketone"]),
    ("Thoughts of self-harm or suicide", [r"suicid|kill myself|end my life|self[- ]harm|hurt myself|don'?t want to live"], []),
    ("Seizure", [r"seizure|convuls|fitting"], []),
    ("Sudden worst headache of life", [r"worst[- ]?(ever )?headache|thunderclap|sudden(ly)?,? severe headache|sudden,? severe .{0,12}headache"], []),
    ("Possible meningitis (fever with stiff neck / rash that does not fade)", [r"stiff neck|neck stiffness|rash (that )?(doesn'?t|does not) fade"], [r"fever|temperature"]),
    ("Overdose or poisoning", [r"overdos|took too many|poison(ed|ing)?|pesticide|insecticide|rat poison"
                               r"|(ingest(ed|ing)?|swallow(ed|ing)?|drank|drunk) (an? |some )?unknown (substance|liquid|chemical|powder)"
                               r"|(drank|drunk|swallowed|ingested) (some )?(bleach|kerosene|acid|phenyl|chemical|pesticide)"
                               r"|\b(took|taken|swallowed|ate|had) (\d{2,}|[89]|a lot of|lots of|too many|many|a whole (strip|bottle) of)"
                               r" (\w+ ){0,2}(tablets?|pills?|capsules?|dolo|crocin|calpol|paracetamol)"], []),
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

"""Contract tests: casual text is NEVER mangled, technical cues STILL convert.

These tests are the acceptance contract for the word-mangling review. They
exercise the two deterministic stages directly:
  - expand_spoken_symbols(s)  — spoken-symbol regex rules
  - Vocabulary().correct(s)   — fuzzy mis-hear correction (starter pack loaded)

The casual strings must round-trip UNCHANGED through BOTH stages. The technical
strings must convert exactly.
"""
import pytest

from app.core.formatting import expand_spoken_symbols
from app.core.vocabulary import Vocabulary


# Every one of these intentional casual/social/everyday strings MUST survive
# both deterministic stages with zero changes.
CASUAL_STRINGS = [
    "i use pnpm instead of npm",   # npm/pnpm collide at ratio 85.71 — must not flip
    "just docker it",              # Docker (said=None) must not capitalize
    "redis is fast",               # Redis (said=None) must not capitalize
    "lets use postgres",           # intentional short form, no alias for it
    "i love nextjs",               # intentional spelling, must not become Next.js
    "a node in the graph",         # 'graph' must not become GraphQL
    "I need to react to this",     # 'react' must not become React
    "go to the store",
    "a dash of salt",              # 'dash' prose, not a CLI flag
    "the dot product",             # 'dot' prose, not a file extension
    "open the door",               # 'open' without 'paren'
    "new line of thinking",        # bare 'new line' rule dropped
    "lol omw see you at 5",
    "i feel like a new person",
    "a dash a day keeps the doctor away",  # 'dash a' must not become '-a'
    "he made a dash",
    "grade dash a",                # 'dash a' (letter is an article) — no flag
]


@pytest.mark.parametrize("s", CASUAL_STRINGS)
def test_casual_text_unchanged_by_spoken_symbols(s):
    assert expand_spoken_symbols(s) == s


@pytest.mark.parametrize("s", CASUAL_STRINGS)
def test_casual_text_unchanged_by_vocabulary_correct(s):
    # Starter pack loaded — the real-world default config.
    v = Vocabulary()
    assert v.correct(s) == s


@pytest.mark.parametrize("s", CASUAL_STRINGS)
def test_casual_text_unchanged_full_deterministic_pipeline(s):
    v = Vocabulary()
    assert v.correct(expand_spoken_symbols(s)) == s


# ---------------------------------------------------------------------------
# Technical cues STILL convert correctly.
# ---------------------------------------------------------------------------

def test_golden_kubectl_spoken_symbols():
    assert expand_spoken_symbols(
        "kubectl apply dash f deployment dot yaml then check the pod logs"
    ) == "kubectl apply -f deployment.yaml then check the pod logs"


def test_dash_dash_flag_still_works():
    assert expand_spoken_symbols("dash dash help") == "--help"


def test_cube_cuttle_corrects_via_explicit_alias():
    # The starter pack ships explicit kubectl mis-hear aliases.
    v = Vocabulary()
    assert v.correct("cube cuttle get pods") == "kubectl get pods"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("cube cuttle get pods", "kubectl get pods"),
        ("cube cuddle apply", "kubectl apply"),
        ("kube control logs", "kubectl logs"),
        ("connect to postgre sql now", "connect to PostgreSQL now"),
        ("engine x config", "nginx config"),
        ("use graph QL here", "use GraphQL here"),
    ],
)
def test_starter_pack_explicit_aliases_convert(raw, expected):
    v = Vocabulary()
    assert v.correct(raw) == expected


def test_full_pipeline_golden_technical():
    # expand_spoken_symbols THEN correct, with the starter pack.
    v = Vocabulary()
    raw = "cube cuttle apply dash f deployment dot yaml then check the pod logs"
    out = v.correct(expand_spoken_symbols(raw))
    assert out == "kubectl apply -f deployment.yaml then check the pod logs"

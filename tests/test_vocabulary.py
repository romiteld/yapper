"""Tests for the Vocabulary store and fuzzy correction."""
from app.core.vocabulary import Vocabulary, DEV_STARTER_PACK


def test_starter_pack_loaded_by_default():
    v = Vocabulary()
    typed = {t["typed"] for t in v.terms}
    assert "kubectl" in typed
    assert "Next.js" in typed
    assert "PostgreSQL" in typed


def test_empty_constructor_with_no_starter():
    v = Vocabulary(load_starter=False)
    assert v.terms == []


def test_add_term_typed_only():
    v = Vocabulary(load_starter=False)
    v.add("FastAPI")
    assert {"said": None, "typed": "FastAPI"} in v.terms


def test_add_term_with_said():
    v = Vocabulary(load_starter=False)
    v.add("kubectl", said="cube cuttle")
    assert {"said": "cube cuttle", "typed": "kubectl"} in v.terms


def test_add_is_idempotent_on_typed():
    v = Vocabulary(load_starter=False)
    v.add("nginx")
    v.add("nginx", said="engine x")
    typed_count = sum(1 for t in v.terms if t["typed"] == "nginx")
    assert typed_count == 1
    # later add updates the 'said' alias
    assert any(t["typed"] == "nginx" and t["said"] == "engine x" for t in v.terms)


def test_remove_term():
    v = Vocabulary(load_starter=False)
    v.add("redis")
    v.remove("redis")
    assert all(t["typed"] != "redis" for t in v.terms)


def test_to_list_and_from_list_roundtrip():
    v = Vocabulary(load_starter=False)
    v.add("kubectl", said="cube cuttle")
    v.add("OAuth")
    data = v.to_list()
    assert data == [
        {"said": "cube cuttle", "typed": "kubectl"},
        {"said": None, "typed": "OAuth"},
    ]
    v2 = Vocabulary(load_starter=False)
    v2.from_list(data)
    assert v2.terms == v.terms


def test_from_list_normalizes_bare_strings():
    v = Vocabulary(load_starter=False)
    v.from_list(["kubectl", {"typed": "nginx"}])
    assert {"said": None, "typed": "kubectl"} in v.terms
    assert {"said": None, "typed": "nginx"} in v.terms


def test_add_from_list_keeps_starter_pack():
    # add_from_list appends WITHOUT clearing existing terms.
    v = Vocabulary()  # starter pack loaded
    before = {t["typed"] for t in v.terms}
    assert "kubectl" in before
    v.add_from_list([{"typed": "FastAPI"}, "Pydantic"])
    after = {t["typed"] for t in v.terms}
    assert "kubectl" in after          # starter pack preserved
    assert "FastAPI" in after          # user term added
    assert "Pydantic" in after


def test_add_from_list_empty_is_noop():
    v = Vocabulary()
    before = list(v.terms)
    v.add_from_list([])
    v.add_from_list(None)
    assert v.terms == before


def test_from_list_still_clears():
    v = Vocabulary()  # starter pack
    v.from_list([{"typed": "Solo"}])
    assert [t["typed"] for t in v.terms] == ["Solo"]


# ---------------------------------------------------------------------------
# Task 4: Whisper prompt bias
# ---------------------------------------------------------------------------

def test_whisper_prompt_lists_typed_terms():
    v = Vocabulary(load_starter=False)
    v.add("kubectl")
    v.add("Next.js")
    prompt = v.whisper_prompt()
    assert "kubectl" in prompt
    assert "Next.js" in prompt


def test_whisper_prompt_empty_when_no_terms():
    v = Vocabulary(load_starter=False)
    assert v.whisper_prompt() == ""


def test_whisper_prompt_is_bounded():
    v = Vocabulary(load_starter=False)
    for i in range(500):
        v.add(f"Term{i}")
    # Whisper prompt is capped (~224 tokens); keep it well under that.
    assert len(v.whisper_prompt()) <= 900


# ---------------------------------------------------------------------------
# Task 5: Fuzzy correction
# ---------------------------------------------------------------------------

def test_correct_two_word_alias():
    v = Vocabulary(load_starter=False)
    v.add("kubectl", said="cube cuttle")
    assert v.correct("then cube cuttle apply") == "then kubectl apply"


def test_correct_postgres_alias():
    v = Vocabulary(load_starter=False)
    v.add("PostgreSQL", said="post gres")
    assert v.correct("connect to post gres now") == "connect to PostgreSQL now"


def test_correct_preserves_case_of_surrounding_text():
    v = Vocabulary(load_starter=False)
    v.add("Next.js", said="next J S")
    out = v.correct("I love Next J S a lot")
    assert "Next.js" in out
    assert out.startswith("I love")


def test_correct_does_not_overcorrect_unrelated_words():
    v = Vocabulary(load_starter=False)
    v.add("kubectl", said="cube cuttle")
    # 'the cube of seven' must NOT become kubectl
    assert v.correct("the cube of seven is large") == "the cube of seven is large"


def test_correct_noop_with_empty_vocabulary():
    v = Vocabulary(load_starter=False)
    assert v.correct("nothing to do here") == "nothing to do here"


def test_correct_golden_kubectl_phrase():
    v = Vocabulary(load_starter=False)
    v.add("kubectl", said="cube cuttle")
    raw = "cube cuttle apply deployment"
    assert v.correct(raw) == "kubectl apply deployment"


# ---------------------------------------------------------------------------
# Correction architecture: said=None terms NEVER rewrite the user's words.
# ---------------------------------------------------------------------------

def test_said_none_term_does_not_self_correct():
    # A term with no explicit alias contributes to prompt bias ONLY.
    v = Vocabulary(load_starter=False)
    v.add("Docker")  # said=None
    assert v.correct("just docker it") == "just docker it"
    assert v.correct("i use Docker daily") == "i use Docker daily"


def test_npm_pnpm_do_not_collide():
    # The old (typed,typed) self-match flipped "npm" -> "pnpm" at ratio 85.71.
    v = Vocabulary(load_starter=False)
    v.add("pnpm")  # said=None
    v.add("npm")   # said=None
    assert v.correct("i use pnpm instead of npm") == "i use pnpm instead of npm"


def test_starter_pack_said_none_terms_never_correct():
    v = Vocabulary()  # full starter pack
    for s in ["just docker it", "redis is fast", "lets use postgres",
              "i love nextjs"]:
        assert v.correct(s) == s


def test_list_alias_all_variants_correct():
    v = Vocabulary(load_starter=False)
    v.add("kubectl", said=["cube cuttle", "cube cuddle", "kube control"])
    assert v.correct("run cube cuttle now") == "run kubectl now"
    assert v.correct("run cube cuddle now") == "run kubectl now"
    assert v.correct("run kube control now") == "run kubectl now"


def test_list_alias_stored_as_comma_joined_string():
    v = Vocabulary(load_starter=False)
    v.add("kubectl", said=["cube cuttle", "cube cuddle"])
    term = next(t for t in v.terms if t["typed"] == "kubectl")
    assert term["said"] == "cube cuttle, cube cuddle"


def test_non_distinctive_alias_is_ignored():
    # An alias that is a single short word (< 2 words and < 6 chars) is too
    # risky to apply and must be skipped by the distinctiveness backstop.
    v = Vocabulary(load_starter=False)
    v.add("React", said="reac")  # 1 word, 4 chars -> ignored
    assert v.correct("i reac to this") == "i reac to this"


def test_distinctive_alias_by_length_applies():
    # >= 6 chars single word is distinctive enough.
    v = Vocabulary(load_starter=False)
    v.add("Kubernetes", said="koobernetees")
    assert v.correct("deploy to koobernetees") == "deploy to Kubernetes"


def test_whisper_prompt_includes_said_none_terms():
    # All typed terms (including said=None) prime the Whisper prompt.
    v = Vocabulary()
    prompt = v.whisper_prompt()
    for term in ["kubectl", "Docker", "Redis", "PostgreSQL", "pnpm"]:
        assert term in prompt


# ---------------------------------------------------------------------------
# Task 6: CSV import
# ---------------------------------------------------------------------------

import os


def test_import_csv_with_header(tmp_path=None):
    v = Vocabulary(load_starter=False)
    fixture = os.path.join(
        os.path.dirname(__file__), "fixtures", "vocab_import.csv"
    )
    v.import_csv(fixture)
    assert {"said": "cube cuttle", "typed": "kubectl"} in v.terms
    assert {"said": None, "typed": "FastAPI"} in v.terms
    assert {"said": "engine x", "typed": "nginx"} in v.terms


def test_import_csv_single_column(tmp_path):
    p = tmp_path / "single.csv"
    p.write_text("kubectl\nnginx\n", encoding="utf-8")
    v = Vocabulary(load_starter=False)
    v.import_csv(str(p))
    typed = {t["typed"] for t in v.terms}
    assert "kubectl" in typed
    assert "nginx" in typed

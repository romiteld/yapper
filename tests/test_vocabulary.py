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

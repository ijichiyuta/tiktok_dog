import copy
import json
from pathlib import Path

from ehon.validate import check

SAMPLE = json.loads(next(Path(__file__).parents[1].glob("episodes/*_B01/script.json")).read_text())


def errs(s, narrator="owner"):
    return check(s, narrator)[0]


def test_sample_passes():
    assert errs(SAMPLE) == []


def test_too_long():
    s = copy.deepcopy(SAMPLE)
    s["slides"][4]["text"] = "あ" * 31
    assert any("31字" in e for e in errs(s))


def test_banned_word():
    s = copy.deepcopy(SAMPLE)
    s["slides"][15]["text"] = "病気になる前に"
    assert any("病気" in e for e in errs(s))


def test_farewell_only_once_and_in_place():
    s = copy.deepcopy(SAMPLE)
    s["slides"][2]["text"] = "いつかのこと"
    assert any("16, 17" in e or "[16, 17]" in e for e in errs(s))
    s["slides"][15]["text"] = "いつか来る日まで"
    assert any("2枚" in e for e in errs(s))


def test_emphasis_exactly_one():
    s = copy.deepcopy(SAMPLE)
    s["slides"][18]["emphasis"] = True
    assert any("赤文字" in e for e in errs(s))


def test_reuse_must_point_back():
    s = copy.deepcopy(SAMPLE)
    s["slides"][4]["reuse"] = 9
    assert any("reuse" in e for e in errs(s))


def test_last_slide_needs_question_or_action():
    s = copy.deepcopy(SAMPLE)
    s["slides"][19]["text"] = "おしまい"
    assert any("20枚目" in e for e in errs(s))

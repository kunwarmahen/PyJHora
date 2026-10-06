"""Topic Reading's topics must be ones the prediction prompt knows (§79.3).

The page (`frontend/src/pages/PredictionsPage.js` → `TOPICS`) sends its topic
as `prediction_type`; `_build_prediction_prompt` looks it up in a dict and falls
back to "general" for anything it doesn't know. A typo'd or newly-added topic
would therefore produce a general reading under a "Career" heading, with no
error anywhere — the advertised-but-not-wired shape of §52. Two lists in two
languages can't be derived from one another, so pin that they agree.
"""
import os
import re

import pytest

from llm.prompts import PromptsMixin

PAGE = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src", "pages",
                    "PredictionsPage.js")


class _Prompts(PromptsMixin):
    pass


def _page_topics():
    src = open(PAGE, encoding="utf-8").read()
    m = re.search(r"export const TOPICS = \[([^\]]*)\]", src)
    assert m, "TOPICS list not found in PredictionsPage.js"
    return re.findall(r'"(\w+)"', m.group(1))


def _focus_line(topic):
    text = _Prompts()._build_prediction_prompt({}, topic)
    m = re.search(r"predictions focusing on (.+?)\.\n", text)
    assert m, text[-400:]
    return m.group(1)


def test_page_has_topics():
    assert len(_page_topics()) >= 2


@pytest.mark.parametrize("topic", _page_topics())
def test_every_page_topic_gets_its_own_focus(topic):
    if topic == "general":
        return
    # A known topic gets its own focus; an unknown one would get general's.
    assert _focus_line(topic) != _focus_line("general"), topic


def test_education_reading_receives_the_d24_it_is_told_to_read():
    """§83.4: the education prompt reads the D24, which is not a default varga,
    so the route must add it — an instruction about a chart the model never got
    invites an invented one. An explicit caller list still wins."""
    from chart_context import DEFAULT_VARGAS
    from llm.prompts import topic_vargas

    assert 24 not in DEFAULT_VARGAS
    assert 24 in topic_vargas("education", None)
    assert set(DEFAULT_VARGAS) <= set(topic_vargas("education", None))
    assert topic_vargas("career", None) is None          # -> defaults
    assert topic_vargas("education", [1, 9]) == [1, 9]   # caller's list wins
    assert "D24" in _Prompts()._build_prediction_prompt({}, "education")


def test_new_topics_name_their_classical_houses():
    assert "2nd house" in _focus_line("finance") and "11th house" in _focus_line("finance")
    assert "4th house" in _focus_line("education")
    assert "12th house" in _focus_line("travel")

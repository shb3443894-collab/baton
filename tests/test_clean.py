"""메일 읽기와 정제가 필요한 내용은 지키고 잡음만 걷어내는지 확인한다."""

import importlib.util
import json
from pathlib import Path

import pytest

from baton.clean.cleaner import clean_mails, is_auto_mail, strip_quotes_and_signature
from baton.ingest.mbox import RawMail, html_to_text, read_mbox

DATA = Path(__file__).resolve().parents[1] / "data" / "synthetic"


@pytest.fixture(scope="module")
def raw():
    return read_mbox(DATA / "mails.mbox")


@pytest.fixture(scope="module")
def result(raw):
    return clean_mails(raw)


def text_of(kept, message_id):
    return next(m.text for m in kept if m.raw.message_id.startswith(message_id + "@"))


def test_reads_all_mails_with_threads_and_dates(raw):
    assert len(raw) == 100
    assert all(m.message_id and m.thread_id and m.date.tzinfo for m in raw)
    assert all(m.body for m in raw)


def test_filter_counts_add_up(result):
    kept, stats = result
    assert stats["total"] == 100
    assert stats["excluded_label"] == 4
    assert stats["auto"] == 24
    assert stats["kept"] == len(kept) == 72


def test_decision_sentence_survives_and_quote_is_gone(result):
    kept, _ = result
    text = text_of(kept, "coupon-t2-2")
    assert "첫 구매 쿠폰은 4월 15일부로 폐지하겠습니다" in text
    assert "0.8%p" not in text
    assert "대외비" not in text


@pytest.mark.parametrize("marker", ["대외비", "Original Message", "작성:", "010-5550", "보낸 사람:"])
def test_no_quote_or_signature_left_anywhere(result, marker):
    kept, _ = result
    assert not [m.raw.message_id for m in kept if marker in m.text]


def test_every_scenario_body_matches_the_original_exactly(result):
    """시나리오 메일이 한 글자라도 잘리면 근거 문장을 잃는다."""
    kept, _ = result
    spec = importlib.util.spec_from_file_location("synth", DATA.parents[1] / "scripts" / "make_synthetic_mails.py")
    synth = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(synth)
    expected = [item[4] for s in synth.SCENARIOS for _, items in s["threads"] for item in items]
    answers = json.loads((DATA / "answers.json").read_text(encoding="utf-8"))
    ids = {i for a in answers for i in a["message_ids"]}
    found = [m for m in kept if m.raw.message_id.split("@")[0] in ids]
    assert len(found) == len(expected) == 29
    assert sorted(m.text for m in found) == sorted(expected)


def test_html_only_body_becomes_text():
    assert html_to_text("<p>첫 줄</p><script>x()</script><div>둘째 줄</div>") == "첫 줄\n둘째 줄"


@pytest.mark.parametrize("line", [
    "On Tue, Apr 1, 2025 at 10:42 AM Kim <a@b.example> wrote:",
    "2025. 4. 1. 오전 10:42에 김민수 작성:",
    "-----원본 메시지-----",
    "From: Kim",
])
def test_other_mail_client_quote_formats(line):
    assert strip_quotes_and_signature(f"새로 쓴 말\n{line}\n예전 내용") == "새로 쓴 말"


def test_does_not_cut_normal_sentences():
    body = "일정은 A--B 순서입니다.\n보낸 사람 기준으로 정리했습니다.\n결론은 유지입니다."
    assert strip_quotes_and_signature(body) == body


def test_keeps_first_line_even_if_it_looks_like_header():
    assert strip_quotes_and_signature("From: 영업팀 요청입니다").startswith("From:")


def test_auto_detected_by_sender_or_header():
    base = dict(message_id="1", thread_id="1", date=None, to=[], subject="", body="")
    assert is_auto_mail(RawMail(sender="x <no-reply@a.example>", **base))
    assert is_auto_mail(RawMail(sender="x <a@a.example>", headers={"Precedence": "bulk"}, **base))
    assert not is_auto_mail(RawMail(sender="x <a@a.example>", **base))

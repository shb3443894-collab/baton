"""가림이 개인정보는 빠짐없이 지우고, 답변에 필요한 내용은 남기는지 확인한다."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from baton.clean.cleaner import CleanMail, clean_mails
from baton.ingest.mbox import RawMail, read_mbox
from baton.mask.masker import mask_contacts, mask_mails

DATA = Path(__file__).resolve().parents[1] / "data" / "synthetic"
ORG = json.loads((DATA / "org.json").read_text(encoding="utf-8"))
NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)


def mail(text, sender="김민수 <minsu@a.example>", to=("이지은 <jieun@a.example>",), thread="t1", subject="제목", mid="m1"):
    raw = RawMail(mid, thread, NOW, sender, list(to), subject, text)
    return CleanMail(raw, text, False)


@pytest.fixture(scope="module")
def result():
    kept, _ = clean_mails(read_mbox(DATA / "mails.mbox"))
    return mask_mails(kept, ORG)


def all_text(m):
    return "\n".join([m.sender, *m.to, m.subject, m.text, *m.attachments])


def test_no_real_name_or_contact_left_in_synthetic_mails(result):
    masked, _, _ = result
    secrets = [p["name"] for p in ORG] + ["010-5550", "omall.example", "123-45-678901"]
    leaks = [(m.message_id, s) for m in masked for s in secrets if s in all_text(m)]
    assert leaks == []


def test_given_names_are_masked_too(result):
    masked, _, _ = result
    given = [p["name"][1:] + suffix for p in ORG for suffix in ("님", "씨")]
    assert not [m.message_id for m in masked if any(g in m.text for g in given)]


def test_every_mail_survives_and_decision_sentence_stays(result):
    masked, _, _ = result
    assert len(masked) == 72
    text = next(m.text for m in masked if m.message_id.startswith("coupon-t2-2@"))
    assert "첫 구매 쿠폰은 4월 15일부로 폐지하겠습니다" in text


def test_same_person_same_alias_within_thread_and_map_restores_name():
    mails = [
        mail("이지은님 확인 부탁드립니다.", mid="m1"),
        mail("지은님, 김민수입니다.", sender="이지은 <jieun@a.example>", to=("김민수 <minsu@a.example>",), mid="m2"),
    ]
    masked, tables, _ = mask_mails(mails, ORG)
    jieun = masked[0].to[0]
    assert jieun == "[운영팀A]"
    assert masked[0].text == f"{jieun}님 확인 부탁드립니다."
    assert masked[1].sender == jieun
    assert masked[1].text == f"{jieun}님, {masked[0].sender}입니다."
    assert tables["t1"][jieun] == "이지은"


def test_two_people_in_a_department_get_different_letters():
    masked, tables, _ = mask_mails([mail("박서준, 오유나 확인", sender="a <a@a.example>", to=())], ORG)
    assert "[기획팀A], [기획팀B] 확인" == masked[0].text
    assert set(tables["t1"].values()) == {"a", "박서준", "오유나"}


def test_surname_with_title_is_masked():
    masked, _, _ = mask_mails([mail("한 팀장이 승인했습니다.", sender="a <a@a.example>", to=())], ORG)
    assert masked[0].text == "[개발팀A]이 승인했습니다."


def test_names_from_headers_work_without_org_chart():
    """개인 Gmail에는 조직도가 없다."""
    mails = [
        mail("계약 건입니다.", sender="홍길동 <hong@b.example>", to=("나 <me@b.example>",), thread="t1"),
        mail("홍길동 대표가 동의했습니다. John Smith도 동의.", sender="John Smith <js@b.example>", to=(), thread="t2"),
    ]
    masked, _, _ = mask_mails(mails)
    assert all("홍길동" not in all_text(m) and "John Smith" not in all_text(m) for m in masked)
    assert masked[0].sender.startswith("[외부")


def test_unknown_name_before_honorific_is_masked_but_common_words_stay():
    masked, _, _ = mask_mails([mail("남궁민 없고 황보라님과 담당자님, 고객님께 전달", sender="a <a@a.example>", to=())])
    assert "황보라" not in masked[0].text
    assert "담당자님" in masked[0].text and "고객님" in masked[0].text


def test_homonym_form_is_masked_without_guessing_the_person():
    org = [
        {"name": "김하나", "dept": "운영팀", "title": "팀장"},
        {"name": "김두리", "dept": "개발팀", "title": "팀장"},
    ]
    masked, _, _ = mask_mails([mail("김 팀장 확인", sender="a <a@a.example>", to=())], org)
    assert masked[0].text == "[이름] 확인"


@pytest.mark.parametrize("text, token", [
    ("연락처 010-1234-5678입니다", "[연락처]"),
    ("01012345678로 연락", "[연락처]"),
    ("+82 10-1234-5678", "[연락처]"),
    ("대표번호 02-123-4567", "[연락처]"),
    ("메일은 a.b+c@d-e.co.kr 입니다", "[메일]"),
    ("주민번호 900101-1234567", "[주민번호]"),
    ("카드 4111-1111-1111-1111", "[카드]"),
    ("국민은행 123-45-678901", "[계좌]"),
    ("계좌 110123456789", "[계좌]"),
])
def test_contacts_are_masked(text, token):
    assert token in mask_contacts(text)


@pytest.mark.parametrize("text", [
    "2025-03-02에 결정", "2025. 3. 2.", "CVR 0.8%p 하락", "매출 1,200,000원", "버전 1.2.3", "4월 15일부로", "v2-3",
])
def test_ordinary_numbers_stay(text):
    assert mask_contacts(text) == text


def test_subject_and_attachment_name_are_masked():
    item = mail("본문입니다.", subject="이지은 계약서 010-1111-2222")
    item.raw.attachments = ["김민수_이력서.pdf"]
    masked, _, _ = mask_mails([item], ORG)
    assert "이지은" not in masked[0].subject and "010-1111" not in masked[0].subject
    assert "김민수" not in masked[0].attachments[0]


def test_masked_mail_keeps_no_reference_to_original():
    masked, _, _ = mask_mails([mail("이지은")], ORG)
    assert not hasattr(masked[0], "raw")

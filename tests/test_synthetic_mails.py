"""합성 메일이 진짜 메일처럼 읽히고, 이후 단계의 시험 재료가 갖춰졌는지 확인한다."""

import hashlib
import json
import mailbox
import re
import subprocess
import sys
from email import message_from_bytes, policy
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "data" / "synthetic"


@pytest.fixture(scope="module")
def mails():
    box = mailbox.mbox(DATA / "mails.mbox")
    return [message_from_bytes(m.as_bytes(), policy=policy.default) for m in box]


@pytest.fixture(scope="module")
def answers():
    return json.loads((DATA / "answers.json").read_text(encoding="utf-8"))


def mid(message_id):
    return message_id.strip("<>").split("@")[0]


def body(mail):
    return mail.get_body(preferencelist=("plain",)).get_content()


def test_exactly_100_unique_mails(mails):
    ids = [m["Message-ID"] for m in mails]
    assert len(ids) == 100
    assert len(set(ids)) == 100


def test_korean_survives_round_trip(mails):
    assert any("첫 구매 쿠폰" in str(m["Subject"]) for m in mails)
    assert any("폐지하겠습니다" in body(m) for m in mails)


def test_replies_point_to_a_mail_in_the_same_thread(mails):
    by_id = {m["Message-ID"]: m for m in mails}
    replies = [m for m in mails if m["In-Reply-To"]]
    assert replies
    for reply in replies:
        parent = by_id[reply["In-Reply-To"]]
        assert parent["X-GM-THRID"] == reply["X-GM-THRID"]
        assert parent["Subject"].removeprefix("RE: ") == reply["Subject"].removeprefix("RE: ")


def test_every_answer_points_to_real_mails(mails, answers):
    ids = {mid(m["Message-ID"]) for m in mails}
    assert len(answers) == 6
    for answer in answers:
        assert set(answer["message_ids"]) <= ids
        assert answer["decision_message_ids"]


def test_decision_split_across_two_threads(mails, answers):
    threads = {m["X-GM-THRID"] for m in mails if mid(m["Message-ID"]) in answers[0]["message_ids"]}
    assert len(threads) == 2


def test_hard_cases_exist_for_later_steps(mails):
    bodies = [body(m) for m in mails]
    assert any("\n> " in b for b in bodies), "> 인용문"
    assert any("-----Original Message-----" in b for b in bodies), "영문 인용문"
    assert any("보낸 사람:" in b for b in bodies), "한국어 인용문"
    assert any("본 메일은 대외비" in b for b in bodies), "서명"
    assert any(m["List-Unsubscribe"] for m in mails), "뉴스레터"
    assert any(m["Auto-Submitted"] for m in mails), "자동 메일"
    assert any(m.is_multipart() for m in mails), "HTML 메일"
    assert {"인사", "개인"} <= {m["X-Gmail-Labels"] for m in mails}, "제외 라벨"


def test_only_fictional_contact_details(mails):
    for mail in mails:
        text = f"{mail['From']} {mail['To']} {body(mail)}"
        for domain in re.findall(r"@([\w.-]+)", text):
            assert domain.endswith(".example")
        for phone in re.findall(r"01\d-\d{3,4}-\d{4}", text):
            assert phone.startswith("010-5550-")


def test_generation_is_reproducible():
    script = DATA.parents[1] / "scripts" / "make_synthetic_mails.py"
    digests = []
    for _ in range(2):
        subprocess.run([sys.executable, str(script)], check=True, capture_output=True)
        digests.append(hashlib.sha256((DATA / "mails.mbox").read_bytes()).hexdigest())
    assert digests[0] == digests[1]

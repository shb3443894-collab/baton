"""조각 나누기와 색인이 내용을 잃지 않고, 사용자 경계를 지키는지 확인한다.

모델을 내려받지 않도록 글자 빈도로 벡터를 만드는 가짜 임베더를 쓴다.
"""

from datetime import datetime, timezone

import pytest

from baton.index.chunker import MAX_CHARS, Chunk, chunk_mails, split_text
from baton.index.store import MailIndex
from baton.mask.masker import MaskedMail


class FakeEmbedder:
    def embed(self, texts):
        vectors = []
        for text in texts:
            vector = [0.0] * 64
            for char in text:
                vector[ord(char) % 64] += 1.0
            vectors.append(vector)
        return vectors


def masked(text="충분히 긴 본문입니다. 쿠폰을 폐지합니다.", too_short=False, mid="m1"):
    return MaskedMail(mid, "t1", datetime(2025, 4, 1, tzinfo=timezone.utc), "[운영팀A]", [], "쿠폰 결정", text, too_short, [], [])


def chunk(cid, text):
    return Chunk(cid, f"{cid}@x", "t1", "2025-04-01", "[운영팀A]", "제목", text)


@pytest.fixture
def index(tmp_path):
    return MailIndex(str(tmp_path), FakeEmbedder())


def test_short_mail_is_not_indexed():
    assert chunk_mails([masked(too_short=True)]) == []


def test_chunk_keeps_subject_and_source():
    only = chunk_mails([masked()])[0]
    assert only.id == "m1#0" and only.message_id == "m1" and only.date == "2025-04-01"
    assert only.text.startswith("제목: 쿠폰 결정\n")


def test_split_keeps_every_character_and_limit():
    text = "\n".join(["가" * 500, "나" * 500, "다" * 2000])
    parts = split_text(text)
    assert all(len(part) <= MAX_CHARS for part in parts)
    assert "".join(parts).replace("\n", "") == text.replace("\n", "")


def test_search_returns_source_with_chunk(index):
    index.add([chunk("a", "쿠폰 폐지"), chunk("b", "서버 점검")], "user1")
    hit = index.search("쿠폰 폐지", "user1", k=1)[0]
    assert hit.chunk.id == "a" and hit.chunk.message_id == "a@x"


def test_search_never_crosses_users(index):
    index.add([chunk("a", "쿠폰 폐지")], "user1")
    index.add([chunk("b", "쿠폰 폐지 비밀")], "user2")
    assert [h.chunk.id for h in index.search("쿠폰", "user1")] == ["a"]
    assert index.search("쿠폰", "nobody") == []


def test_same_message_from_two_users_is_kept_separately(index):
    index.add([chunk("a", "같은 메일")], "user1")
    index.add([chunk("a", "같은 메일")], "user2")
    assert index.collection.count() == 2


def test_search_without_owner_is_refused(index):
    with pytest.raises(ValueError):
        index.search("쿠폰", "")


def test_adding_again_does_not_duplicate(index):
    index.add([chunk("a", "쿠폰")], "user1")
    index.add([chunk("a", "쿠폰")], "user1")
    assert index.collection.count() == 1

"""합성 메일을 색인하고, 시나리오 질문의 근거 메일이 검색되는지 잰다.

실행: uv run python scripts/build_index.py
"""

import json
import sys
from pathlib import Path

from baton.clean.cleaner import clean_mails
from baton.index.chunker import chunk_mails
from baton.index.store import LocalEmbedder, MailIndex
from baton.ingest.mbox import read_mbox
from baton.mask.masker import mask_mails

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "synthetic"
OWNER = "synthetic"
TOP_K = 5


def build() -> MailIndex:
    org = json.loads((DATA / "org.json").read_text(encoding="utf-8"))
    kept, _ = clean_mails(read_mbox(DATA / "mails.mbox"))
    masked, _, _ = mask_mails(kept, org)
    chunks = chunk_mails(masked)
    index = MailIndex(str(ROOT / "chroma_db"), LocalEmbedder())
    index.add(chunks, OWNER)
    print(f"메일 {len(masked)}통 → 조각 {len(chunks)}개 색인")
    return index


def measure(index: MailIndex) -> None:
    answers = json.loads((DATA / "answers.json").read_text(encoding="utf-8"))
    found_decision = 0
    for answer in answers:
        hits = index.search(answer["question"], OWNER, TOP_K)
        ids = [hit.chunk.message_id.split("@")[0] for hit in hits]
        decision = set(answer["decision_message_ids"]) & set(ids)
        related = set(answer["message_ids"]) & set(ids)
        found_decision += bool(answer["decision_message_ids"]) and bool(decision)
        print(f"- {answer['question']} | 관련 {len(related)}/{TOP_K} | 결정 메일 {'찾음' if decision else '못 찾음'} | {ids}")
    expected = sum(1 for answer in answers if answer["decision_message_ids"])
    print(f"결정 메일 적중: {found_decision}/{expected} (상위 {TOP_K}개)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    measure(build())

"""메일에서 새로 쓴 내용만 남기고, 색인하지 않을 메일을 가려낸다."""

import re
from collections import Counter
from dataclasses import dataclass

from baton.ingest.mbox import RawMail

DEFAULT_EXCLUDED_LABELS = frozenset({"인사", "급여", "개인"})
MIN_BODY_CHARS = 20

# 이 줄부터 끝까지는 이전 메일 인용문이나 서명이다.
CUT_LINE = re.compile(
    r"""^\s*(
        -{2,}\s*$                                 # 서명 구분선
      | -{3,}\s*(Original\sMessage|원본\s*메시지)\s*-{3,}
      | >                                         # > 인용문
      | On\s.+\swrote:\s*$
      | \d{4}[-./]\s?\d{1,2}[-./]\s?\d{1,2}.*(작성|wrote):\s*$
      | (보낸\s*사람|From)\s*:
    )""",
    re.IGNORECASE | re.VERBOSE,
)
AUTO_SENDER = re.compile(r"(no-?reply|do-?not-?reply|mailer-daemon|notifications?)@", re.IGNORECASE)


@dataclass
class CleanMail:
    raw: RawMail
    text: str
    too_short: bool


def strip_quotes_and_signature(body: str) -> str:
    """인용문·서명이 시작되는 줄 앞까지만 남긴다. 첫 내용 줄은 자르지 않는다."""
    kept = []
    for line in body.replace("\r\n", "\n").split("\n"):
        if any(part.strip() for part in kept) and CUT_LINE.match(line):
            break
        kept.append(line)
    return "\n".join(kept).strip()


def is_auto_mail(mail: RawMail) -> bool:
    return bool(mail.headers) or bool(AUTO_SENDER.search(mail.sender))


def clean_mails(mails, excluded_labels=DEFAULT_EXCLUDED_LABELS):
    """색인 대상 메일과 단계별 제외 건수를 돌려준다. 내용이 짧은 메일은 스레드 흐름을 위해 남긴다."""
    kept, stats = [], Counter(total=len(mails))
    for mail in mails:
        if excluded_labels.intersection(mail.labels):
            stats["excluded_label"] += 1
        elif is_auto_mail(mail):
            stats["auto"] += 1
        else:
            text = strip_quotes_and_signature(mail.body)
            too_short = len(text) < MIN_BODY_CHARS
            stats["too_short"] += too_short
            kept.append(CleanMail(mail, text, too_short))
    stats["kept"] = len(kept)
    return kept, stats

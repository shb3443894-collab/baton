"""가린 메일을 검색용 조각으로 나눈다."""

from dataclasses import dataclass

from baton.mask.masker import MaskedMail

MAX_CHARS = 800


@dataclass
class Chunk:
    id: str
    message_id: str
    thread_id: str
    date: str
    sender: str
    subject: str
    text: str


def split_text(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    """문단을 합쳐 max_chars 이하로 나눈다. 긴 문단은 글자 수로 자른다."""
    parts, current = [], ""
    for paragraph in text.split("\n"):
        if len(paragraph) > max_chars and current:
            parts.append(current)
            current = ""
        while len(paragraph) > max_chars:
            parts.append(paragraph[:max_chars])
            paragraph = paragraph[max_chars:]
        if current and len(current) + 1 + len(paragraph) > max_chars:
            parts.append(current)
            current = paragraph
        else:
            current = f"{current}\n{paragraph}" if current else paragraph
    if current.strip():
        parts.append(current)
    return [part.strip() for part in parts if part.strip()]


def chunk_mails(mails: list[MaskedMail]) -> list[Chunk]:
    """짧은 메일은 검색 잡음이 되므로 뺀다. 조각에 제목을 붙여 어떤 건인지 알 수 있게 한다."""
    chunks = []
    for mail in mails:
        if mail.too_short:
            continue
        for index, part in enumerate(split_text(mail.text)):
            chunks.append(Chunk(
                id=f"{mail.message_id}#{index}",
                message_id=mail.message_id,
                thread_id=mail.thread_id,
                date=mail.date.date().isoformat(),
                sender=mail.sender,
                subject=mail.subject,
                text=f"제목: {mail.subject}\n{part}",
            ))
    return chunks

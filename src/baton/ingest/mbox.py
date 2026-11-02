"""mbox 파일을 읽어 공통 메일 형식(RawMail)으로 바꾼다.

Gmail 커넥터가 생겨도 같은 RawMail을 만들면 이후 단계는 그대로 쓸 수 있다.
"""

import mailbox
from dataclasses import dataclass, field
from datetime import datetime
from email import message_from_bytes, policy
from email.message import EmailMessage
from html.parser import HTMLParser
from pathlib import Path


@dataclass
class RawMail:
    message_id: str
    thread_id: str
    date: datetime
    sender: str
    to: list[str]
    subject: str
    body: str
    labels: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    attachments: list[str] = field(default_factory=list)


class _TextExtractor(HTMLParser):
    BLOCK_TAGS = {"p", "div", "br", "li", "tr"}
    SKIP_TAGS = {"script", "style"}

    def __init__(self):
        super().__init__()
        self.parts = []
        self.skipping = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self.skipping += 1
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS:
            self.skipping -= 1

    def handle_data(self, data):
        if not self.skipping:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return "".join(parser.parts).strip()


def _body_of(message: EmailMessage) -> str:
    part = message.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    content = part.get_content()
    return html_to_text(content) if part.get_content_type() == "text/html" else content


def _to_raw(message: EmailMessage) -> RawMail:
    message_id = str(message["Message-ID"] or "").strip("<>")
    labels = [label.strip() for label in str(message["X-Gmail-Labels"] or "").split(",") if label.strip()]
    return RawMail(
        message_id=message_id,
        thread_id=str(message["X-GM-THRID"] or message_id),
        date=message["Date"].datetime,
        sender=str(message["From"] or ""),
        to=[str(a) for a in (message["To"].addresses if message["To"] else ())],
        subject=str(message["Subject"] or ""),
        body=_body_of(message),
        labels=labels,
        headers={key: str(message[key]) for key in ("List-Unsubscribe", "Precedence", "Auto-Submitted") if message[key]},
        attachments=[name for part in message.iter_attachments() if (name := part.get_filename())],
    )


def read_mbox(path: str | Path) -> list[RawMail]:
    box = mailbox.mbox(str(path), create=False)
    try:
        return [_to_raw(message_from_bytes(entry.as_bytes(), policy=policy.default)) for entry in box]
    finally:
        box.close()

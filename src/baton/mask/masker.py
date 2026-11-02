"""저장과 LLM 전송 전에 메일의 개인정보를 가린다.

이름은 조직도와 메일 헤더(보낸·받는 사람)를 주소록처럼 대조해 찾는다.
개인 Gmail에는 조직도가 없으므로, 헤더의 이름은 조직도 밖이면 [외부A]처럼 가린다.
같은 스레드 안에서 같은 사람은 항상 같은 가명을 쓴다.
"""

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from email.utils import parseaddr

from baton.clean.cleaner import CleanMail

EXTERNAL = "외부"
AMBIGUOUS = "[이름]"

RRN = re.compile(r"(?<![\d-])\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])[- ]?[1-8]\d{6}(?![\d-])")
CARD = re.compile(r"(?<![\d-])\d(?:[ -]?\d){12,18}(?![\d-])")
PHONE = re.compile(
    r"(?<![\d-])(?:"
    r"(?:\+82[- ]?|0)(?:1[016789]|2|[3-6][1-5]|70)[- .]?\d{3,4}[- .]?\d{4}"
    r"|1[5-9]\d{2}-\d{4}"
    r")(?![\d-])"
)
ACCOUNT = re.compile(r"(?<![\d-])(?:\d{2,6}-){2,4}\d{2,8}(?![\d-])|(?<![\d-])\d{10,14}(?![\d-])")
MIN_ACCOUNT_DIGITS = 10  # 2025-03-02 같은 날짜(8자리)는 계좌가 아니다
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

SURNAMES = "김이박최정강조윤장임한오서신권황안송류전홍고문양손배백허유남심노하곽성차주우구민진지엄채원천방공현함변염여추도소석선설마길연위표명기반왕금옥육인맹제모탁국어은편용"
TITLES = "팀장|매니저|선임|책임|수석|대표|이사|상무|전무|부장|차장|과장|대리|주임|사원|실장|본부장|파트장"
HONORIFIC_NAME = re.compile(rf"(?<![가-힣\[])[{SURNAMES}][가-힣]{{2}}(?=\s?(?:님|씨|{TITLES}))")
NOT_A_NAME = {
    "이사장", "부사장", "조교수", "정교수", "부교수", "신입생", "장기간", "구매자", "판매자",
    "이번주", "이번달", "지난주", "지난달", "전체팀", "우리팀", "마지막",
    "고객사", "협력사", "주관사", "운영자", "담당자", "관리자", "사용자", "소유자", "대표자", "기획자",
}


@dataclass(frozen=True)
class Person:
    key: str
    group: str
    name: str = ""


@dataclass
class MaskedMail:
    message_id: str
    thread_id: str
    date: datetime
    sender: str
    to: list[str]
    subject: str
    text: str
    too_short: bool
    labels: list[str]
    attachments: list[str]


def mask_contacts(text: str, stats: Counter | None = None) -> str:
    """이름을 뺀 연락처·번호를 가린다. 날짜처럼 숫자만 많은 값은 남긴다."""
    for pattern, token, kind in (
        (RRN, "[주민번호]", "rrn"),
        (EMAIL, "[메일]", "email"),
        (PHONE, "[연락처]", "phone"),
    ):
        text, count = pattern.subn(token, text)
        if stats is not None:
            stats[kind] += count

    def card(match):
        digits = re.sub(r"\D", "", match.group())
        if not _passes_luhn(digits):
            return match.group()
        if stats is not None:
            stats["card"] += 1
        return "[카드]"

    text = CARD.sub(card, text)
    def account(match):
        if sum(char.isdigit() for char in match.group()) < MIN_ACCOUNT_DIGITS:
            return match.group()
        if stats is not None:
            stats["account"] += 1
        return "[계좌]"

    return ACCOUNT.sub(account, text)


def _passes_luhn(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        number = int(char)
        if index % 2:
            number = number * 2 - 9 if number > 4 else number * 2
        total += number
    return total % 10 == 0


def _letter(index: int) -> str:
    return chr(65 + index % 26) + (str(index // 26) if index >= 26 else "")


class ThreadAliases:
    """스레드 하나의 가명표. 그룹(부서)마다 A, B 순서로 붙인다."""

    def __init__(self):
        self.alias_by_key = {}
        self.real_by_alias = {}
        self.used = Counter()

    def alias(self, person: Person) -> str:
        if person.key not in self.alias_by_key:
            alias = f"[{person.group}{_letter(self.used[person.group])}]"
            self.used[person.group] += 1
            self.alias_by_key[person.key] = alias
            self.real_by_alias[alias] = person.name or person.key
        return self.alias_by_key[person.key]


class Directory:
    """이름 표현 → 사람. 두 사람에게 겹치는 표현은 None으로 두어 [이름]으로 가린다."""

    def __init__(self, org):
        self.org = {p["name"]: Person(f"org:{p['name']}", p["dept"], p["name"]) for p in org}
        self.forms: dict[str, Person | None] = {}
        self.patterns: dict[str, str] = {}
        self.by_address: dict[str, Person] = {}
        for entry in org:
            self._add_org_forms(entry)
        self.regex = None

    def _add(self, form, person, pattern):
        self.forms[form] = None if form in self.forms and self.forms[form] != person else person
        self.patterns[form] = pattern

    def _add_org_forms(self, entry):
        person = self.org[entry["name"]]
        name, title = entry["name"], entry["title"]
        self._add(name, person, _name_pattern(name))
        if len(name) >= 3 and re.fullmatch(r"[가-힣]+", name):
            given = name[1:]
            self._add(given, person, rf"(?<![가-힣]){given}(?=님|씨)")
            self._add(f"{name[0]}{title}", person, rf"(?<![가-힣]){name[0]}\s?{title}")

    def learn(self, header: str) -> Person | None:
        """헤더 한 칸을 사람으로 바꾼다. 처음 보는 이름은 이후 본문 대조에도 쓴다."""
        display, address = parseaddr(header)
        address, display = address.lower(), display.strip()
        if address in self.by_address:
            return self.by_address[address]
        person = next((p for name, p in self.org.items() if name in display), None)
        if person is None and not (address or display):
            return None
        if person is None:
            person = Person(f"addr:{address or display}", EXTERNAL, display or address)
            if len(display) >= 2:
                self._add(display, person, _name_pattern(display))
        if address:
            self.by_address[address] = person
        return person

    def compile(self):
        forms = sorted(self.forms, key=len, reverse=True)
        self.regex = re.compile("|".join(f"(?P<f{i}>{self.patterns[f]})" for i, f in enumerate(forms)), re.IGNORECASE)
        self.ordered = forms

    def mask(self, text: str, aliases: ThreadAliases, stats: Counter) -> str:
        def replace(match):
            stats["name"] += 1
            person = self.forms[self.ordered[int(match.lastgroup[1:])]]
            return aliases.alias(person) if person else AMBIGUOUS

        def replace_unknown(match):
            name = match.group()
            if name in NOT_A_NAME:
                return name
            stats["name_pattern"] += 1
            return aliases.alias(Person(f"name:{name}", EXTERNAL, name))

        if self.regex is not None and self.forms:
            text = self.regex.sub(replace, text)
        return HONORIFIC_NAME.sub(replace_unknown, text)


def _name_pattern(name: str) -> str:
    escaped = re.escape(name)
    if re.fullmatch(r"[가-힣]{3,}", name):
        return escaped
    if re.search(r"[A-Za-z]", name):
        return rf"(?<![A-Za-z]){escaped}(?![A-Za-z])"
    return rf"(?<![가-힣]){escaped}(?![가-힣])"


def mask_mails(mails: list[CleanMail], org=()):
    """가린 메일, 스레드별 가명표(thread_id → {가명: 실명}), 건수 통계를 돌려준다.

    가명표는 실명을 담고 있으므로 가린 메일과 같은 저장소에 두면 안 된다.
    """
    directory = Directory(org)
    for mail in mails:
        for header in (mail.raw.sender, *mail.raw.to):
            directory.learn(header)
    directory.compile()

    tables, stats, masked = defaultdict(ThreadAliases), Counter(), []
    for mail in sorted(mails, key=lambda m: m.raw.date):
        raw, aliases = mail.raw, tables[mail.raw.thread_id]
        people = [directory.learn(h) for h in (raw.sender, *raw.to)]
        names = [aliases.alias(p) if p else "[수신자]" for p in people]

        def clean(value):
            return directory.mask(mask_contacts(value, stats), aliases, stats)

        masked.append(MaskedMail(
            message_id=raw.message_id,
            thread_id=raw.thread_id,
            date=raw.date,
            sender=names[0],
            to=names[1:],
            subject=clean(raw.subject),
            text=clean(mail.text),
            too_short=mail.too_short,
            labels=list(raw.labels),
            attachments=[clean(name) for name in raw.attachments],
        ))
        if RRN.search(mail.text):
            stats["rrn_mail"] += 1
    return masked, {tid: table.real_by_alias for tid, table in tables.items()}, stats

"""가상 회사 ○○몰의 합성 메일 100통을 mbox로 만든다.

실행: uv run python scripts/make_synthetic_mails.py
결과: data/synthetic/mails.mbox  메일 100통 (Gmail 내보내기 형식)
      data/synthetic/org.json    가상 조직도 (개인정보 가림 단계에서 사용)
      data/synthetic/answers.json 시나리오별 정답 (평가 단계에서 사용)

모든 이름·연락처·계좌는 가상이고, 도메인은 예약 도메인(.example)만 쓴다.
같은 시드로 항상 같은 결과가 나온다.
"""

import json
import mailbox
import random
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path

DOMAIN = "omall.example"
KST = timezone(timedelta(hours=9))
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "synthetic"

PEOPLE = {
    "minsu": ("김민수", "커머스사업팀", "팀장", "010-5550-0101"),
    "jieun": ("이지은", "운영팀", "매니저", "010-5550-0102"),
    "seojun": ("박서준", "기획팀", "매니저", "010-5550-0103"),
    "doyun": ("최도윤", "개발팀", "선임", "010-5550-0104"),
    "harin": ("정하린", "마케팅팀", "매니저", "010-5550-0105"),
    "taeo": ("강태오", "재무팀", "매니저", "010-5550-0106"),
    "seoa": ("윤서아", "CS팀", "매니저", "010-5550-0107"),
    "jiho": ("한지호", "개발팀", "팀장", "010-5550-0108"),
    "yuna": ("오유나", "기획팀", "선임", "010-5550-0109"),
    "jaehyun": ("임재현", "법무팀", "매니저", "010-5550-0110"),
    "minji": ("송민지", "디자인팀", "선임", "010-5550-0111"),
    "junyoung": ("배준영", "영업팀", "매니저", "010-5550-0112"),
}

# 시나리오: (id, 라벨, 질문, 스레드 목록). 메일 = (날짜, 보낸 사람, 받는 사람, 유형, 본문)
# 유형은 보고·제안·반대·대안·결정·보류. 한 결정이 스레드 2개로 쪼개진 시나리오도 넣었다.
SCENARIOS = [
    {
        "id": "coupon",
        "label": "커머스 운영/프로모션",
        "question": "첫 구매 쿠폰은 왜 없앴어?",
        "conclusion": "다계정 중복 발급을 막는 비용이 효과보다 커서 2025년 4월 15일부로 폐지",
        "rejected": "휴대폰 인증 조건부 유지 (개발 공수 약 3주)",
        "threads": [
            ("첫 구매 쿠폰 중복 발급 신고 증가 건", [
                ("2025-03-02 09:40", "jieun", ["minsu", "seojun"], "보고",
                 "2월 첫 구매 쿠폰 중복 발급 신고가 41건으로 전월 대비 3배 늘었습니다.\n"
                 "같은 사람이 계정을 여러 개 만들어 쿠폰을 반복해서 받는 사례로 보입니다.\n"
                 "대응 방향을 논의했으면 합니다."),
                ("2025-03-10 14:12", "doyun", ["jieun", "seojun", "jiho"], "반대",
                 "계정 기준으로 제한해도 다계정은 막을 수 없습니다.\n"
                 "가입할 때 쓰는 메일을 바꾸면 새 고객으로 인식되기 때문입니다."),
                ("2025-03-15 11:05", "seojun", ["doyun", "jieun", "minsu"], "대안",
                 "휴대폰 인증을 완료한 고객에게만 쿠폰을 지급하는 조건부 유지안을 제안드립니다.\n"
                 "1인 1회가 보장되어 악용을 대부분 막을 수 있습니다."),
                ("2025-03-18 16:30", "jiho", ["seojun", "doyun"], "보고",
                 "인증 조건부 유지안은 인증 연동까지 개발 공수가 약 3주 필요합니다.\n"
                 "4월 릴리즈 일정에는 넣기 어렵습니다."),
            ]),
            ("첫 구매 쿠폰 운영 방향 최종 결정", [
                ("2025-03-28 10:00", "harin", ["minsu", "seojun"], "보고",
                 "첫 구매 쿠폰의 재구매 기여는 0.8%p로 낮게 측정됐습니다.\n"
                 "신규 유입 효과도 대체 혜택으로 충분히 보완할 수 있다고 봅니다."),
                ("2025-04-01 10:42", "minsu", ["seojun", "jieun", "doyun", "harin", "jiho"], "결정",
                 "여러 의견 감사합니다.\n"
                 "인증 조건부 유지안도 검토했지만, 개발 공수 대비 효과가 낮다고 판단해 "
                 "첫 구매 쿠폰은 4월 15일부로 폐지하겠습니다.\n"
                 "대체 혜택은 이지은님이 다음 주까지 정리 부탁드립니다."),
            ]),
        ],
    },
    {
        "id": "shipping",
        "label": "커머스 운영/배송",
        "question": "무료배송 기준이 3만 원이 된 이유는?",
        "conclusion": "택배비 인상으로 객단가를 높이기 위해 2024년 9월부터 2만 원에서 3만 원으로 상향",
        "rejected": "2만 5천 원 단계 인상 (손익 개선 폭이 작음)",
        "threads": [
            ("무료배송 기준 금액 조정 검토", [
                ("2024-08-05 10:20", "taeo", ["minsu", "yuna"], "보고",
                 "9월부터 택배 계약 단가가 건당 2,800원에서 3,300원으로 오릅니다.\n"
                 "현재 무료배송 기준 2만 원을 유지하면 월 물류비가 약 1,800만 원 늘어납니다."),
                ("2024-08-07 15:02", "yuna", ["taeo", "minsu", "harin"], "제안",
                 "무료배송 기준을 3만 원으로 올려 객단가를 높이는 안을 제안합니다.\n"
                 "주문 분포상 2만~3만 원 구간 주문의 절반은 묶음 구매로 전환될 것으로 예상합니다."),
                ("2024-08-08 09:47", "harin", ["yuna", "minsu"], "대안",
                 "3만 원은 전환율 하락이 걱정됩니다. 2만 5천 원으로 단계 인상하는 안은 어떨까요?"),
                ("2024-08-12 17:21", "taeo", ["harin", "yuna", "minsu"], "반대",
                 "2만 5천 원 안은 손익 개선 폭이 월 400만 원 수준이라 단가 인상분을 메우지 못합니다."),
                ("2024-08-14 11:10", "minsu", ["yuna", "taeo", "harin"], "결정",
                 "무료배송 기준은 9월 1일부터 3만 원으로 올리겠습니다.\n"
                 "전환율은 2주간 모니터링하고 이상이 있으면 다시 논의합니다."),
            ]),
        ],
    },
    {
        "id": "grade",
        "label": "커머스 운영/회원 등급",
        "question": "회원 등급 개편 때 기각된 안은?",
        "conclusion": "3단계 등급과 연 단위 산정을 확정",
        "rejected": "구매 횟수 기준 5단계 등급 (시스템 수정 범위가 크고 고객이 이해하기 어려움)",
        "threads": [
            ("회원 등급 개편안 논의", [
                ("2025-06-02 13:30", "seojun", ["minsu", "harin", "doyun"], "제안",
                 "구매 횟수 기준의 5단계 등급으로 개편하는 안을 공유드립니다.\n"
                 "등급을 잘게 나눠 다음 등급으로 올라갈 동기를 만드는 것이 목표입니다."),
                ("2025-06-05 10:15", "doyun", ["seojun", "jiho"], "반대",
                 "5단계로 바꾸면 쿠폰, 적립, 정산 시스템을 모두 수정해야 합니다.\n"
                 "최소 8주가 필요합니다."),
                ("2025-06-09 16:45", "seoa", ["seojun", "minsu"], "반대",
                 "CS 입장에서는 등급이 많으면 혜택 문의가 크게 늘어납니다.\n"
                 "지난 개편 때도 고객이 등급 조건을 이해하지 못해 문의가 많았습니다."),
                ("2025-06-12 09:30", "harin", ["seojun", "minsu"], "대안",
                 "기존처럼 3단계로 두되 산정 기간만 연 단위로 바꾸는 안을 제안합니다."),
                ("2025-06-20 14:00", "minsu", ["seojun", "harin", "doyun", "seoa"], "결정",
                 "3단계 유지, 연 단위 산정 안으로 확정합니다.\n"
                 "5단계 안은 시스템 수정 범위가 크고 고객이 이해하기 어려워 진행하지 않습니다."),
            ]),
        ],
    },
    {
        "id": "pg",
        "label": "커머스 운영/결제·정산",
        "question": "결제대행사는 왜 바꿨어?",
        "conclusion": "결제 장애 반복과 높은 수수료 때문에 2025년 2월 B사로 교체",
        "rejected": "A사 유지 및 수수료 재협상 (장애 재발 방지 약속을 받지 못함)",
        "threads": [
            ("결제 장애 재발 및 PG 재검토", [
                ("2024-12-03 08:55", "jiho", ["minsu", "taeo"], "보고",
                 "어제 저녁 A사 결제 장애로 42분간 카드 결제가 중단됐습니다.\n"
                 "올해 들어 네 번째 장애이고, 추정 매출 손실은 약 2,300만 원입니다."),
                ("2024-12-06 11:40", "taeo", ["minsu", "jiho"], "제안",
                 "B사 견적은 수수료 2.3%로 현재 A사 2.7%보다 낮습니다.\n"
                 "정산 계좌는 기존 국민은행 123-45-678901을 그대로 쓸 수 있습니다."),
                ("2024-12-10 15:20", "junyoung", ["minsu", "taeo"], "대안",
                 "A사가 수수료를 2.4%로 낮춰주겠다고 합니다. 재협상해서 유지하는 방법도 있습니다."),
                ("2024-12-16 10:05", "jiho", ["junyoung", "minsu"], "반대",
                 "A사에 재발 방지 약속을 요청했지만 받지 못했습니다.\n"
                 "수수료보다 장애가 더 큰 문제라 유지안에는 반대합니다."),
                ("2024-12-20 17:00", "minsu", ["taeo", "jiho", "junyoung"], "결정",
                 "PG사는 2월 1일부로 B사로 교체합니다.\n"
                 "계약 검토는 임재현님, 전환 일정은 한지호님이 맡아주세요."),
            ]),
        ],
    },
    {
        "id": "push",
        "label": "커머스 운영/프로모션",
        "question": "밤에 앱 푸시를 왜 안 보내?",
        "conclusion": "법무 검토와 수신 거부 증가로 2025년 7월부터 오후 9시~오전 8시 발송 중단",
        "rejected": "야간 수신 동의 고객에게만 발송 (동의 관리 공수 대비 효과 낮음)",
        "threads": [
            ("앱 푸시 야간 발송 기준", [
                ("2025-06-23 10:30", "seoa", ["harin", "jaehyun"], "보고",
                 "밤 10시에 보낸 프로모션 푸시로 항의 문의가 일주일간 57건 들어왔습니다.\n"
                 "푸시 수신 거부도 전월보다 1.6배 늘었습니다."),
                ("2025-06-25 14:18", "jaehyun", ["seoa", "harin", "minsu"], "보고",
                 "광고성 정보는 오후 9시부터 오전 8시까지 별도 동의가 있어야 보낼 수 있습니다.\n"
                 "현재 동의 문구로는 야간 발송 근거가 부족합니다."),
                ("2025-06-26 09:50", "harin", ["jaehyun", "minsu"], "대안",
                 "야간 수신 동의를 따로 받은 고객에게만 보내는 안은 어떨까요?"),
                ("2025-07-01 11:25", "minsu", ["harin", "jaehyun", "seoa"], "결정",
                 "오후 9시부터 오전 8시까지 광고 푸시는 전면 중단하겠습니다.\n"
                 "별도 동의 안은 관리 공수 대비 효과가 낮아 진행하지 않습니다."),
            ]),
        ],
    },
    {
        "id": "subscription",
        "label": "커머스 운영/신규 서비스",
        "question": "정기배송은 왜 출시 안 했어?",
        "conclusion": "결제 재시도 정책이 정리될 때까지 보류, 최종 결정은 나지 않음",
        "rejected": "",
        "threads": [
            ("정기배송 출시 검토", [
                ("2025-08-04 10:10", "yuna", ["minsu", "doyun"], "제안",
                 "생필품 카테고리 정기배송을 4분기에 출시하는 안을 검토 중입니다."),
                ("2025-08-08 13:40", "doyun", ["yuna", "taeo"], "반대",
                 "자동 결제 실패 시 재시도 정책이 없어서 그대로 출시하면 미수금이 생길 수 있습니다."),
                ("2025-08-12 16:05", "taeo", ["yuna", "minsu"], "보고",
                 "재무 쪽에서도 재시도 정책 없이는 정산 기준을 잡기 어렵습니다."),
                ("2025-08-20 10:30", "minsu", ["yuna", "doyun", "taeo"], "보류",
                 "정기배송 건은 결제 재시도 정책이 정리될 때까지 보류합니다.\n"
                 "정책이 나오면 다시 일정을 잡겠습니다."),
            ]),
        ],
    },
]

ROUTINE_SUBJECTS = [
    ("주간 회의 일정 공유", "이번 주 회의는 수요일 오후 2시 3층 회의실에서 진행합니다."),
    ("상품 상세 이미지 수정 요청", "메인 배너 이미지 시안을 확인 부탁드립니다. 금요일까지 수정 예정입니다."),
    ("월간 실적 자료 공유", "지난달 실적 자료를 공유 폴더에 올렸습니다. 참고 부탁드립니다."),
    ("입점사 미팅 일정 조율", "다음 주 화요일 또는 목요일 오전 중 가능한 시간을 알려주세요."),
    ("CS 응대 매뉴얼 개정본", "응대 매뉴얼 개정본을 첨부합니다. 다음 주부터 적용합니다."),
    ("사무실 좌석 배치 변경 안내", "이번 주 금요일 퇴근 후 좌석 배치를 변경합니다."),
    ("서버 점검 일정 공유", "일요일 새벽 2시부터 3시까지 정기 점검이 있습니다."),
    ("물류센터 방문 일정", "월말 재고 실사를 위해 물류센터를 방문합니다. 동행 가능하신 분 알려주세요."),
    ("디자인 시스템 변경 공유", "버튼 스타일이 일부 변경됩니다. 시안을 참고해 주세요."),
    ("분기 교육 신청 안내", "분기 직무 교육 신청을 이번 주까지 받습니다."),
]
ROUTINE_REPLIES = ["확인했습니다.", "네 감사합니다.", "확인 후 회신드리겠습니다.", "참석 가능합니다."]

AUTO_MAILS = [
    ("no-reply", "시스템 알림", "[결재] 지출결의서가 승인되었습니다", "문서번호 {n} 지출결의서가 승인되었습니다.", {"Auto-Submitted": "auto-generated"}),
    ("notice", "그룹웨어", "[공지] 사내 시스템 비밀번호 변경 안내", "비밀번호 변경 주기가 도래했습니다.", {"Auto-Submitted": "auto-generated"}),
    ("newsletter", "이커머스 위클리", "이번 주 이커머스 뉴스레터 {n}호", "이번 주 업계 소식을 전해드립니다.", {"List-Unsubscribe": f"<mailto:unsubscribe@news.{DOMAIN}>", "Precedence": "bulk"}),
    ("calendar", "캘린더", "[일정 알림] 주간 회의 내일 오후 2시", "내일 일정이 있습니다.", {"Auto-Submitted": "auto-generated"}),
]


def addr(key):
    return f"{key}@{DOMAIN}"


def display(key):
    return f"{PEOPLE[key][0]} <{addr(key)}>"


def signature(key):
    name, dept, title, phone = PEOPLE[key]
    return f"--\n{name} {title} | {dept}\n{phone} | {addr(key)}\n본 메일은 대외비이며 수신자 외 열람을 금합니다."


def quote(style, prev):
    """답장에 붙는 이전 메일 인용문. 메일 프로그램마다 모양이 달라 3가지를 섞는다."""
    name = PEOPLE[prev["sender"]][0]
    text = prev["body"]
    if style == 0:
        lines = "\n".join("> " + line for line in text.splitlines())
        return f"{prev['date']:%Y-%m-%d %H:%M}에 {name} 작성:\n{lines}"
    if style == 1:
        return f"-----Original Message-----\nFrom: {display(prev['sender'])}\nSent: {prev['date']:%Y-%m-%d %H:%M}\nSubject: {prev['subject']}\n\n{text}"
    return f"보낸 사람: {name}\n날짜: {prev['date']:%Y-%m-%d %H:%M}\n제목: {prev['subject']}\n\n{text}"


def build(mail):
    """메일 정보 하나를 실제 이메일 형식으로 바꾼다."""
    msg = EmailMessage()
    msg["Message-ID"] = f"<{mail['id']}@{DOMAIN}>"
    msg["Date"] = format_datetime(mail["date"])
    msg["From"] = mail["from"]
    msg["To"] = ", ".join(mail["to"])
    msg["Subject"] = mail["subject_line"]
    msg["X-Gmail-Labels"] = mail["label"]
    msg["X-GM-THRID"] = mail["thread"]
    if mail.get("reply_to"):
        msg["In-Reply-To"] = f"<{mail['reply_to']}@{DOMAIN}>"
        msg["References"] = " ".join(f"<{r}@{DOMAIN}>" for r in mail["refs"])
    for key, value in mail.get("headers", {}).items():
        msg[key] = value
    msg.set_content(mail["text"], charset="utf-8")
    if mail.get("html"):
        html = "".join(f"<p>{line}</p>" for line in mail["text"].splitlines() if line)
        msg.add_alternative(f"<html><body>{html}</body></html>", subtype="html", charset="utf-8")
        msg.set_boundary(f"=={mail['id']}==")
    return msg


def thread_mails(thread_id, label, subject, items, rng, prefix):
    """한 스레드의 메일을 만든다. 뒤 메일일수록 앞 메일이 인용문으로 붙는다."""
    mails, refs, prev = [], [], None
    for i, (when, sender, to, kind, body) in enumerate(items):
        mail_id = f"{prefix}-{i + 1}"
        date = datetime.strptime(when, "%Y-%m-%d %H:%M").replace(tzinfo=KST)
        text = f"{body}\n\n{signature(sender)}"
        if prev:
            text += "\n\n" + quote(i % 3, prev)
        mail = {
            "id": mail_id, "thread": thread_id, "label": label, "kind": kind, "date": date,
            "sender": sender, "from": display(sender), "to": [display(t) for t in to],
            "subject": subject, "subject_line": ("RE: " if prev else "") + subject,
            "body": body, "text": text, "refs": list(refs),
            "reply_to": prev["id"] if prev else None, "html": rng.random() < 0.15,
        }
        mails.append(mail)
        refs.append(mail_id)
        prev = mail
    return mails


def routine_mails(rng, count):
    """결정이 없는 일상 메일. 검색이 걸러내야 할 잡음이다."""
    mails, keys = [], list(PEOPLE)
    n = 0
    while len(mails) < count:
        subject, body = rng.choice(ROUTINE_SUBJECTS)
        sender, to = rng.sample(keys, 2)
        when = datetime(2024, 7, 1, 9, tzinfo=KST) + timedelta(days=rng.randrange(480), minutes=rng.randrange(540))
        n += 1
        items = [(f"{when:%Y-%m-%d %H:%M}", sender, [to], "일상", body)]
        if count - len(mails) >= 2 and rng.random() < 0.5:
            later = when + timedelta(hours=rng.randrange(1, 8))
            items.append((f"{later:%Y-%m-%d %H:%M}", to, [sender], "일상", rng.choice(ROUTINE_REPLIES)))
        mails += thread_mails(f"routine{n:03d}", "받은편지함", subject, items, rng, f"routine{n}")
    return mails


def auto_mails(rng, count):
    """자동 발송 메일. 정제 단계에서 빠져야 한다."""
    mails = []
    for i in range(count):
        user, name, subject, body, headers = AUTO_MAILS[i % len(AUTO_MAILS)]
        when = datetime(2024, 7, 1, 8, tzinfo=KST) + timedelta(days=rng.randrange(480))
        mails.append({
            "id": f"auto-{i + 1}", "thread": f"auto{i + 1:03d}", "label": "받은편지함", "kind": "자동",
            "date": when, "from": f"{name} <{user}@{DOMAIN}>", "to": [display("seojun")],
            "subject_line": subject.format(n=i + 1), "text": body.format(n=i + 1), "headers": headers,
        })
    return mails


def excluded_mails():
    """인사·개인 라벨 메일. 기본 제외 대상이 제대로 빠지는지 확인하는 용도다."""
    items = [
        ("hr-1", "인사", "2025년 연봉 계약서 안내", "연봉 계약서를 확인 후 서명 부탁드립니다."),
        ("hr-2", "인사", "하반기 인사평가 일정", "인사평가 자기기술서를 이달 말까지 제출해 주세요."),
        ("private-1", "개인", "주말 등산 모임", "이번 주 토요일 등산 가실 분 계신가요?"),
        ("private-2", "개인", "결혼식 축하 감사 인사", "지난주 와주셔서 감사합니다."),
    ]
    return [{
        "id": mail_id, "thread": mail_id, "label": label, "kind": "제외", "date": datetime(2025, 5, 7 + i, 12, tzinfo=KST),
        "from": display("jieun"), "to": [display("seojun")], "subject_line": subject, "text": body,
    } for i, (mail_id, label, subject, body) in enumerate(items)]


def main():
    rng = random.Random(20261102)
    mails, answers = [], []
    for scenario in SCENARIOS:
        decided, used = [], []
        for t, (subject, items) in enumerate(scenario["threads"]):
            thread_id = f"{scenario['id']}{t + 1}"
            group = thread_mails(thread_id, scenario["label"], subject, items, rng, f"{scenario['id']}-t{t + 1}")
            mails += group
            used += [m["id"] for m in group]
            decided += [m["id"] for m in group if m["kind"] in ("결정", "보류")]
        answers.append({
            "id": scenario["id"], "question": scenario["question"], "conclusion": scenario["conclusion"],
            "rejected": scenario["rejected"], "decision_message_ids": decided, "message_ids": used,
        })

    mails += excluded_mails()
    auto = auto_mails(rng, 24)
    mails += auto
    mails += routine_mails(rng, 100 - len(mails))
    mails.sort(key=lambda m: m["date"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "mails.mbox"
    path.unlink(missing_ok=True)
    box = mailbox.mbox(path)
    for mail in mails:
        entry = mailbox.mboxMessage(build(mail))
        entry.set_from("MAILER-DAEMON", mail["date"].astimezone(timezone.utc).timetuple())
        box.add(entry)
    box.flush()
    box.close()

    org = [{"key": k, "name": p[0], "dept": p[1], "title": p[2]} for k, p in PEOPLE.items()]
    (OUT_DIR / "org.json").write_text(json.dumps(org, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "answers.json").write_text(json.dumps(answers, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"메일 {len(mails)}통 → {path}")


if __name__ == "__main__":
    main()

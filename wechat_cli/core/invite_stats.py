"""群邀请提示解析与统计。"""

from __future__ import annotations

import re

_SYSTEM_PREFIX_RE = re.compile(r"^\s*\[系统\]\s*")
_QUOTE_RE = re.compile(r'["“](.*?)["”]')
_DIRECT_RE = re.compile(
    r'^\s*["“](?P<inviter>.*?)["”]\s*邀请'
    r'(?P<invitees>.*?)加入了群聊\s*$'
)
_QR_RE = re.compile(
    r'^\s*["“](?P<invitee>.*?)["”]\s*通过扫描'
    r'["“](?P<inviter>.*?)["”]\s*分享的二维码加入群聊\s*$'
)
_UNATTRIBUTED_QR_RE = re.compile(
    r'^\s*(?P<invitee>你|["“].*?["”])通过扫描二维码加入群聊'
)


def normalize_notice_text(text: str) -> str:
    return _SYSTEM_PREFIX_RE.sub("", (text or "").strip())


def normalize_person_name(name: str) -> str:
    return (name or "").strip().strip('"“”').strip()


def parse_invite_notice(text: str) -> list[dict] | None:
    notice = normalize_notice_text(text)
    qr_match = _QR_RE.fullmatch(notice)
    if qr_match:
        return [{
            "method": "qr",
            "inviter_name_raw": normalize_person_name(
                qr_match.group("inviter")
            ),
            "invitee_name_raw": normalize_person_name(
                qr_match.group("invitee")
            ),
        }]

    direct_match = _DIRECT_RE.fullmatch(notice)
    if direct_match:
        inviter = normalize_person_name(direct_match.group("inviter"))
        invitees = [
            normalize_person_name(value)
            for value in _QUOTE_RE.findall(
                direct_match.group("invitees")
            )
        ]
        return [
            {
                "method": "direct",
                "inviter_name_raw": inviter,
                "invitee_name_raw": invitee,
            }
            for invitee in invitees
            if invitee
        ] or None

    unattributed_match = _UNATTRIBUTED_QR_RE.match(notice)
    if unattributed_match:
        return [{
            "method": "unattributed_qr",
            "inviter_name_raw": "",
            "invitee_name_raw": normalize_person_name(
                unattributed_match.group("invitee")
            ),
        }]
    return None


def is_invite_like_notice(text: str) -> bool:
    notice = normalize_notice_text(text)
    return "加入" in notice and "群聊" in notice

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


def parse_identity_bindings(
    values: list[str] | tuple[str, ...],
) -> dict[str, str]:
    bindings: dict[str, str] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"身份绑定格式无效: {raw}")
        name, username = raw.split("=", 1)
        name = normalize_person_name(name)
        username = username.strip()
        if not name or not username:
            raise ValueError(f"身份绑定格式无效: {raw}")
        if name in bindings and bindings[name] != username:
            raise ValueError(f"历史昵称重复绑定到不同账号: {name}")
        bindings[name] = username
    return bindings


class IdentityResolver:
    def __init__(
        self,
        members: list[dict],
        bindings: dict[str, str],
    ):
        self._bindings = bindings
        self._members_by_username = {
            member["username"]: member
            for member in members
            if member.get("username")
        }
        self._exact: dict[str, set[str]] = {}
        for member in members:
            username = member.get("username", "")
            if not username:
                continue
            for field in ("display_name", "remark", "nick_name"):
                value = normalize_person_name(member.get(field, ""))
                if value:
                    self._exact.setdefault(value, set()).add(username)

    def resolve(self, raw_name: str) -> dict:
        name = normalize_person_name(raw_name)
        if name in self._bindings:
            username = self._bindings[name]
            member = self._members_by_username.get(username, {})
            return {
                "key": f"user:{username}",
                "username": username,
                "name": member.get("display_name") or name,
                "status": "resolved",
                "source": "manual",
            }

        candidates = self._exact.get(name, set())
        if len(candidates) == 1:
            username = next(iter(candidates))
            member = self._members_by_username[username]
            return {
                "key": f"user:{username}",
                "username": username,
                "name": member.get("display_name") or name,
                "status": "resolved",
                "source": "member_exact",
            }

        return {
            "key": f"name:{name}",
            "username": "",
            "name": name,
            "status": "unresolved",
            "source": "ambiguous" if candidates else "unmatched",
        }

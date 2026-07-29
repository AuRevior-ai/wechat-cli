"""安全解析微信合并转发（appmsg/type=19）。"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any


_UNSAFE_XML_RE = re.compile(r"<!DOCTYPE|<!ENTITY", re.IGNORECASE)
_MAX_XML_BYTES = 4 * 1024 * 1024
_TYPE_NAMES = {
    1: "text",
    2: "image",
    3: "image",
    4: "voice",
    5: "link",
    6: "link",
    8: "file",
    17: "forwarded",
    19: "link",
}
_TYPE_LABELS = {
    "text": "文字",
    "image": "图片",
    "voice": "语音",
    "link": "链接",
    "file": "文件",
    "forwarded": "合并转发",
}


def _safe_xml_root(value: str | None) -> ET.Element | None:
    if not value or not isinstance(value, str):
        return None
    if len(value.encode("utf-8", errors="replace")) > _MAX_XML_BYTES:
        return None
    if _UNSAFE_XML_RE.search(value):
        return None
    try:
        return ET.fromstring(value)
    except ET.ParseError:
        return None


def _parse_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _collapse(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _xml_payload(node: ET.Element | None) -> str:
    if node is None:
        return ""
    text = (node.text or "").strip()
    if text:
        return text
    children = list(node)
    if not children:
        return ""
    if len(children) == 1:
        return ET.tostring(children[0], encoding="unicode")
    return "<recordinfo>" + "".join(
        ET.tostring(child, encoding="unicode") for child in children
    ) + "</recordinfo>"


def _record_items_root(value: str) -> ET.Element | None:
    root = _safe_xml_root(value)
    if root is None:
        return None
    if root.tag == "datalist":
        return root
    return root.find(".//datalist")


def _parse_items(
    datalist: ET.Element | None,
    depth: int,
    max_depth: int,
    budget: dict[str, Any],
) -> list[dict[str, Any]]:
    if datalist is None:
        return []
    items: list[dict[str, Any]] = []
    for node in datalist.findall("./dataitem"):
        if budget["remaining"] <= 0:
            budget["truncated"] = True
            break
        budget["remaining"] -= 1

        datatype = _parse_int(node.attrib.get("datatype"), 0)
        kind = _TYPE_NAMES.get(datatype, f"type_{datatype}")
        title = _collapse(
            node.findtext("datatitle")
            or node.findtext("title")
            or node.findtext(".//filename")
            or ""
        )
        item: dict[str, Any] = {
            "kind": kind,
            "datatype": datatype,
            "sender": _collapse(node.findtext("sourcename") or ""),
            "time": _collapse(node.findtext("sourcetime") or ""),
            "text": _collapse(node.findtext("datadesc") or node.findtext("content") or ""),
            "title": title,
            "children": [],
        }

        if datatype == 17:
            record_node = node.find("recordxml")
            if record_node is None:
                record_node = node.find(".//recordxml")
            record_value = _xml_payload(record_node)
            if record_value:
                if depth >= max_depth:
                    budget["truncated"] = True
                else:
                    nested = _record_items_root(record_value)
                    item["children"] = _parse_items(
                        nested, depth + 1, max_depth, budget
                    )
        items.append(item)
    return items


def parse_forwarded_message(
    content: str | None,
    *,
    max_depth: int = 6,
    max_items: int = 1000,
) -> dict[str, Any] | None:
    """解析一条合并转发消息，返回稳定、可序列化的树。"""
    if max_depth < 0 or max_items < 1:
        raise ValueError("max_depth 必须大于等于 0，max_items 必须大于 0")
    root = _safe_xml_root(content)
    appmsg = root.find(".//appmsg") if root is not None else None
    if appmsg is None or _parse_int((appmsg.findtext("type") or "").strip()) != 19:
        return None
    record_value = _xml_payload(appmsg.find("recorditem"))
    datalist = _record_items_root(record_value)
    if datalist is None:
        return {
            "title": _collapse(appmsg.findtext("title") or "合并转发"),
            "items": [],
            "truncated": False,
        }
    budget: dict[str, Any] = {"remaining": max_items, "truncated": False}
    items = _parse_items(datalist, 0, max_depth, budget)
    return {
        "title": _collapse(appmsg.findtext("title") or "合并转发"),
        "items": items,
        "truncated": bool(budget["truncated"]),
    }


def count_forwarded_items(items: list[dict[str, Any]]) -> int:
    return sum(
        1 + count_forwarded_items(item.get("children") or [])
        for item in items
    )


def _format_item(item: dict[str, Any], depth: int) -> list[str]:
    indent = "  " * (depth + 1)
    sender = item.get("sender") or "未知发送者"
    time = item.get("time") or "时间未知"
    kind = item.get("kind") or "message"
    label = _TYPE_LABELS.get(kind, f"类型 {item.get('datatype', 0)}")
    body = item.get("title") or item.get("text") or f"[{label}]"
    lines = [f"{indent}- [{time}] {sender}（{label}）：{body}"]
    for child in item.get("children") or []:
        lines.extend(_format_item(child, depth + 1))
    return lines


def format_forwarded_text(forwarded: dict[str, Any]) -> str:
    lines = [f"[合并转发] {forwarded.get('title') or '聊天记录'}"]
    for item in forwarded.get("items") or []:
        lines.extend(_format_item(item, 0))
    if forwarded.get("truncated"):
        lines.append("  - [内容已达到安全解析上限，后续条目已截断]")
    return "\n".join(lines)

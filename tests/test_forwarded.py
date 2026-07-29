import html
import unittest
from datetime import datetime

from wechat_cli.core.forwarded import (
    count_forwarded_items,
    format_forwarded_text,
    parse_forwarded_message,
)
from wechat_cli.core.messages import _build_history_item


def _record_item(
    datatype,
    sender,
    timestamp,
    text="",
    title="",
    recordxml="",
    extra="",
):
    fields = [
        f'<sourcename>{html.escape(sender)}</sourcename>',
        f'<sourcetime>{html.escape(timestamp)}</sourcetime>',
        f'<datadesc>{html.escape(text)}</datadesc>',
    ]
    if title:
        fields.append(f'<datatitle>{html.escape(title)}</datatitle>')
    if recordxml:
        fields.append(f'<recordxml>{html.escape(recordxml)}</recordxml>')
    if extra:
        fields.append(extra)
    return f'<dataitem datatype="{datatype}">{"".join(fields)}</dataitem>'


def _record_xml(items):
    return f'<recordinfo><datalist count="{len(items)}">{"".join(items)}</datalist></recordinfo>'


def _appmsg_type_19(items, title="群聊的聊天记录"):
    record_xml = _record_xml(items)
    return (
        "<msg><appmsg>"
        f"<title>{html.escape(title)}</title><type>19</type>"
        f"<recorditem>{html.escape(record_xml)}</recorditem>"
        "</appmsg></msg>"
    )


class ForwardedMessageTests(unittest.TestCase):
    def test_parses_nested_record_items(self):
        nested = _record_xml([
            _record_item(8, "陈子明", "2026-07-29 10:02", "名单文件", title="名单.xlsx"),
        ])
        content = _appmsg_type_19([
            _record_item(1, "小陶", "2026-07-29 10:00", "第一条"),
            _record_item(17, "小陶", "2026-07-29 10:01", "内层", recordxml=nested),
        ])

        parsed = parse_forwarded_message(content)

        self.assertEqual(parsed["title"], "群聊的聊天记录")
        self.assertEqual(parsed["items"][0]["kind"], "text")
        self.assertEqual(parsed["items"][0]["text"], "第一条")
        self.assertEqual(parsed["items"][1]["kind"], "forwarded")
        self.assertEqual(parsed["items"][1]["children"][0]["kind"], "file")
        self.assertEqual(parsed["items"][1]["children"][0]["title"], "名单.xlsx")
        self.assertFalse(parsed["truncated"])

    def test_preserves_unknown_type(self):
        parsed = parse_forwarded_message(_appmsg_type_19([
            _record_item(99, "未知成员", "2026-07-29 10:03", "保留这个描述"),
        ]))

        self.assertEqual(parsed["items"][0]["kind"], "type_99")
        self.assertEqual(parsed["items"][0]["text"], "保留这个描述")

    def test_preserves_nested_media_references(self):
        content = _appmsg_type_19([
            _record_item(
                2,
                "小陶",
                "2026-07-29 10:03",
                "一张图片",
                extra=(
                    "<cdndataurl>https://wx.qlogo.cn/nested.jpg</cdndataurl>"
                    "<fullmd5>0123456789abcdef0123456789abcdef</fullmd5>"
                    "<srcChatname>room@chatroom</srcChatname>"
                    "<srcMsgLocalid>88</srcMsgLocalid>"
                    "<srcMsgCreateTime>1785290580</srcMsgCreateTime>"
                ),
            ),
        ])

        parsed = parse_forwarded_message(content)
        media = parsed["items"][0]["media"]

        self.assertEqual(media["kind"], "image")
        self.assertEqual(media["url"], "https://wx.qlogo.cn/nested.jpg")
        self.assertEqual(media["md5"], "0123456789abcdef0123456789abcdef")
        self.assertEqual(media["source_chat_username"], "room@chatroom")
        self.assertEqual(media["source_local_id"], 88)

    def test_stops_at_depth_limit(self):
        deepest = _record_xml([_record_item(1, "甲", "2026-07-29 10:00", "最深层")])
        middle = _record_xml([_record_item(17, "乙", "2026-07-29 10:01", recordxml=deepest)])
        content = _appmsg_type_19([
            _record_item(17, "丙", "2026-07-29 10:02", recordxml=middle),
        ])

        parsed = parse_forwarded_message(content, max_depth=1)

        self.assertTrue(parsed["truncated"])
        self.assertEqual(parsed["items"][0]["children"][0]["children"], [])

    def test_stops_at_item_limit(self):
        content = _appmsg_type_19([
            _record_item(1, "成员", f"2026-07-29 10:0{i}", f"消息{i}")
            for i in range(5)
        ])

        parsed = parse_forwarded_message(content, max_items=3)

        self.assertTrue(parsed["truncated"])
        self.assertEqual(count_forwarded_items(parsed["items"]), 3)

    def test_rejects_unsafe_or_non_forward_xml(self):
        unsafe = '<!DOCTYPE x [<!ENTITY e SYSTEM "file:///x">]><msg><appmsg><type>19</type></appmsg></msg>'

        self.assertIsNone(parse_forwarded_message(unsafe))
        self.assertIsNone(parse_forwarded_message("<msg><appmsg><type>5</type></appmsg></msg>"))

    def test_formats_forwarded_tree_as_readable_chinese(self):
        parsed = parse_forwarded_message(_appmsg_type_19([
            _record_item(1, "小陶", "2026-07-29 10:00", "第一条"),
        ]))

        formatted = format_forwarded_text(parsed)

        self.assertIn("[合并转发] 群聊的聊天记录", formatted)
        self.assertIn("小陶（文字）：第一条", formatted)

    def test_history_item_exposes_forwarded_tree(self):
        timestamp = int(datetime(2026, 7, 29, 11, 28).timestamp())
        content = _appmsg_type_19([
            _record_item(1, "小陶", "2026-07-29 10:00", "第一条"),
        ])
        item = _build_history_item(
            (187, (19 << 32) | 49, timestamp, 7, content, None),
            {"username": "wxid_friend", "display_name": "陈子明", "is_group": False},
            {"wxid_friend": "陈子明"},
            {7: "wxid_friend"},
            lambda username, names: names.get(username, username),
            {},
        )

        self.assertEqual(item["type"], "forwarded")
        self.assertEqual(item["type_label"], "合并转发")
        self.assertEqual(item["forwarded"]["items"][0]["text"], "第一条")
        self.assertIn("[合并转发] 群聊的聊天记录", item["text"])

    def test_group_history_item_parses_forward_after_sender_prefix(self):
        timestamp = int(datetime(2026, 7, 29, 13, 4).timestamp())
        content = "wxid_sender:\n" + _appmsg_type_19([
            _record_item(1, "小陶", "2026-07-29 13:00", "群内转发内容"),
        ])
        item = _build_history_item(
            (75, (19 << 32) | 49, timestamp, 8, content, None),
            {"username": "room@chatroom", "display_name": "测试群", "is_group": True},
            {"room@chatroom": "测试群", "wxid_sender": "发送者"},
            {8: "wxid_sender"},
            lambda username, names: names.get(username, username),
            {},
        )

        self.assertEqual(item["forwarded"]["items"][0]["text"], "群内转发内容")
        self.assertEqual(item["sender"], "发送者")


if __name__ == "__main__":
    unittest.main()

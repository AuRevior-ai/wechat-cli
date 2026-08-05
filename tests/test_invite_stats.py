import sqlite3
import tempfile
import unittest
from pathlib import Path

from wechat_cli.core.invite_stats import (
    IdentityResolver,
    collect_group_invite_stats,
    is_invite_like_notice,
    parse_identity_bindings,
    parse_invite_notice,
)


def create_message_db(path: Path, table_name: str, rows: list[tuple]):
    conn = sqlite3.connect(path)
    conn.execute(
        f"""CREATE TABLE [{table_name}] (
            local_id INTEGER,
            server_id INTEGER,
            local_type INTEGER,
            create_time INTEGER,
            message_content TEXT,
            WCDB_CT_message_content INTEGER
        )"""
    )
    conn.executemany(
        f"INSERT INTO [{table_name}] VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


class InviteNoticeParserTests(unittest.TestCase):
    def test_parses_direct_invitation(self):
        events = parse_invite_notice(
            '[系统] "只争朝夕"邀请"阿班"加入了群聊'
        )
        self.assertEqual(events, [{
            "method": "direct",
            "inviter_name_raw": "只争朝夕",
            "invitee_name_raw": "阿班",
        }])

    def test_parses_direct_invitation_to_self_with_participant_suffix(self):
        events = parse_invite_notice(
            "麟雪邀请你加入了群聊，群聊参与人还有：唐传广、林兆润、林晓莹（大赢）"
        )
        self.assertEqual(events, [{
            "method": "direct",
            "inviter_name_raw": "麟雪",
            "invitee_name_raw": "你",
            "invitee_is_self": True,
        }])

    def test_parses_qr_invitation_as_share_owner_credit(self):
        events = parse_invite_notice(
            '"郑桓宇🔥🔥"通过扫描"小陶老师 青年OPC盟主"分享的二维码加入群聊'
        )
        self.assertEqual(events, [{
            "method": "qr",
            "inviter_name_raw": "小陶老师 青年OPC盟主",
            "invitee_name_raw": "郑桓宇🔥🔥",
        }])

    def test_splits_multiple_direct_invitees(self):
        events = parse_invite_notice(
            '"甲"邀请"乙"、"丙"加入了群聊'
        )
        self.assertEqual(
            [event["invitee_name_raw"] for event in events],
            ["乙", "丙"],
        )

    def test_parses_self_invitation_xml_with_stable_invitee_username(self):
        events = parse_invite_notice(
            """54539324941@chatroom:
            <sysmsg type="delchatroommember">
              <delchatroommember>
                <plain><![CDATA[你邀请"陈子明"加入了群聊  ]]></plain>
                <text><![CDATA[你邀请"陈子明"加入了群聊  ]]></text>
                <link>
                  <scene>invite</scene>
                  <text><![CDATA[  撤销]]></text>
                  <memberlist>
                    <username><![CDATA[wxid_zipilqil46k022]]></username>
                  </memberlist>
                </link>
              </delchatroommember>
            </sysmsg>"""
        )

        self.assertEqual(events, [{
            "method": "direct",
            "inviter_name_raw": "你",
            "inviter_is_self": True,
            "invitee_name_raw": "陈子明",
            "invitee_username": "wxid_zipilqil46k022",
        }])

    def test_splits_batch_self_invitation_xml_and_pairs_usernames(self):
        events = parse_invite_notice(
            """57757918914@chatroom:
            <sysmsg type="delchatroommember">
              <delchatroommember>
                <plain><![CDATA[你邀请"甲、乙"加入了群聊  ]]></plain>
                <text><![CDATA[你邀请"甲、乙"加入了群聊  ]]></text>
                <link>
                  <scene>invite</scene>
                  <text><![CDATA[  撤销]]></text>
                  <memberlist>
                    <username><![CDATA[wxid_a]]></username>
                    <username><![CDATA[wxid_b]]></username>
                  </memberlist>
                </link>
              </delchatroommember>
            </sysmsg>"""
        )

        self.assertEqual(events, [
            {
                "method": "direct",
                "inviter_name_raw": "你",
                "inviter_is_self": True,
                "invitee_name_raw": "甲",
                "invitee_username": "wxid_a",
            },
            {
                "method": "direct",
                "inviter_name_raw": "你",
                "inviter_is_self": True,
                "invitee_name_raw": "乙",
                "invitee_username": "wxid_b",
            },
        ])

    def test_parses_self_shared_qr_xml_with_invitee_username(self):
        events = parse_invite_notice(
            """57757918914@chatroom:
            <sysmsg type="delchatroommember">
              <delchatroommember>
                <plain><![CDATA["闵杰 南昌大学"通过扫描你分享的二维码加入群聊  ]]></plain>
                <text><![CDATA["闵杰 南昌大学"通过扫描你分享的二维码加入群聊  ]]></text>
                <link>
                  <scene>qrcode</scene>
                  <text><![CDATA[  撤销]]></text>
                  <memberlist>
                    <username><![CDATA[wxid_invitee]]></username>
                  </memberlist>
                  <qrcode><![CDATA[http://weixin.qq.com/g/example]]></qrcode>
                </link>
              </delchatroommember>
            </sysmsg>"""
        )

        self.assertEqual(events, [{
            "method": "qr",
            "inviter_name_raw": "你",
            "inviter_is_self": True,
            "invitee_name_raw": "闵杰 南昌大学",
            "invitee_username": "wxid_invitee",
        }])

    def test_preserves_unattributed_self_qr_join(self):
        events = parse_invite_notice(
            "你通过扫描二维码加入群聊，群聊参与人还有：甲、乙"
        )
        self.assertEqual(events, [{
            "method": "unattributed_qr",
            "inviter_name_raw": "",
            "invitee_name_raw": "你",
        }])

    def test_marks_unknown_join_template_as_invite_like(self):
        text = '"甲"通过新的入群方式加入了群聊'
        self.assertIsNone(parse_invite_notice(text))
        self.assertTrue(is_invite_like_notice(text))

    def test_ignores_unrelated_system_notice(self):
        text = '"甲"修改群名为“项目群”'
        self.assertIsNone(parse_invite_notice(text))
        self.assertFalse(is_invite_like_notice(text))


class InviteIdentityTests(unittest.TestCase):
    def setUp(self):
        self.members = [
            {
                "username": "wxid_8ncies5owakx11",
                "display_name": "小陶 老师",
                "nick_name": "小陶老师 陶金会老板",
                "remark": "小陶 老师",
            },
            {
                "username": "wxid_gd9gzapbdq8e12",
                "display_name": "小陶老师 青年OPC盟主",
                "nick_name": "小陶老师 青年OPC盟主",
                "remark": "小陶老师 青年OPC盟主",
            },
        ]

    def test_keeps_similar_names_as_distinct_accounts(self):
        resolver = IdentityResolver(self.members, {})

        first = resolver.resolve("小陶 老师")
        second = resolver.resolve("小陶老师 青年OPC盟主")

        self.assertEqual(first["username"], "wxid_8ncies5owakx11")
        self.assertEqual(second["username"], "wxid_gd9gzapbdq8e12")
        self.assertNotEqual(first["key"], second["key"])

    def test_does_not_fuzzy_match_partial_name(self):
        resolver = IdentityResolver(self.members, {})

        identity = resolver.resolve("小陶老师")

        self.assertEqual(identity["status"], "unresolved")
        self.assertEqual(identity["key"], "name:小陶老师")

    def test_marks_duplicate_exact_names_ambiguous(self):
        duplicate = {
            "username": "wxid_other",
            "display_name": "小陶 老师",
            "nick_name": "另一个人",
            "remark": "小陶 老师",
        }
        resolver = IdentityResolver([*self.members, duplicate], {})

        identity = resolver.resolve("小陶 老师")

        self.assertEqual(identity["status"], "unresolved")
        self.assertEqual(identity["source"], "ambiguous")

    def test_manual_binding_has_highest_priority(self):
        bindings = parse_identity_bindings(
            ["旧昵称=wxid_gd9gzapbdq8e12"]
        )
        resolver = IdentityResolver(self.members, bindings)

        identity = resolver.resolve("旧昵称")

        self.assertEqual(identity["username"], "wxid_gd9gzapbdq8e12")
        self.assertEqual(identity["source"], "manual")

    def test_rejects_conflicting_manual_bindings(self):
        with self.assertRaisesRegex(ValueError, "重复绑定"):
            parse_identity_bindings([
                "旧昵称=wxid_one",
                "旧昵称=wxid_two",
            ])


class InviteAggregationTests(unittest.TestCase):
    def test_resolves_direct_invitation_to_self_as_local_account(self):
        table_name = "Msg_" + "8" * 32
        notice = (
            "麟雪邀请你加入了群聊，群聊参与人还有："
            "唐传广、林兆润、林晓莹（大赢）"
        )
        members = [
            {
                "username": "wxid_me",
                "display_name": "Au Revior",
                "nick_name": "Au Revior",
                "remark": "",
            },
            {
                "username": "wxid_linxue",
                "display_name": "麟雪",
                "nick_name": "麟雪",
                "remark": "",
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "message.db"
            create_message_db(path, table_name, [
                (1, 700, 10000, 1785855420, notice, 0),
            ])
            ctx = {
                "display_name": "测试群",
                "username": "57757918914@chatroom",
                "self_username": "wxid_me",
                "is_group": True,
                "message_tables": [{
                    "db_path": str(path),
                    "table_name": table_name,
                }],
            }

            result = collect_group_invite_stats(ctx, members, {})

        self.assertEqual(result["summary"]["invite_event_count"], 1)
        self.assertEqual(result["summary"]["unparsed_count"], 0)
        event = result["events"][0]
        self.assertEqual(event["inviter_username"], "wxid_linxue")
        self.assertEqual(event["invitee_username"], "wxid_me")
        self.assertEqual(event["invitee_identity_status"], "resolved")

    def test_aggregates_batch_and_self_shared_qr_xml_for_local_account(self):
        table_name = "Msg_" + "9" * 32
        batch_notice = """57757918914@chatroom:
        <sysmsg type="delchatroommember">
          <delchatroommember>
            <plain><![CDATA[你邀请"甲、乙"加入了群聊  ]]></plain>
            <text><![CDATA[你邀请"甲、乙"加入了群聊  ]]></text>
            <link>
              <scene>invite</scene>
              <memberlist>
                <username><![CDATA[wxid_a]]></username>
                <username><![CDATA[wxid_b]]></username>
              </memberlist>
            </link>
          </delchatroommember>
        </sysmsg>"""
        qr_notice = """57757918914@chatroom:
        <sysmsg type="delchatroommember">
          <delchatroommember>
            <plain><![CDATA["丙"通过扫描你分享的二维码加入群聊  ]]></plain>
            <text><![CDATA["丙"通过扫描你分享的二维码加入群聊  ]]></text>
            <link>
              <scene>qrcode</scene>
              <memberlist>
                <username><![CDATA[wxid_c]]></username>
              </memberlist>
              <qrcode><![CDATA[http://weixin.qq.com/g/example]]></qrcode>
            </link>
          </delchatroommember>
        </sysmsg>"""
        members = [
            {
                "username": "wxid_me",
                "display_name": "Au Revior",
                "nick_name": "Au Revior",
                "remark": "",
            },
            *[
                {
                    "username": f"wxid_{suffix}",
                    "display_name": name,
                    "nick_name": name,
                    "remark": "",
                }
                for suffix, name in (("a", "甲"), ("b", "乙"), ("c", "丙"))
            ],
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "message.db"
            create_message_db(path, table_name, [
                (1, 701, 10000, 1785295680, batch_notice, 0),
                (2, 702, 10000, 1785295740, qr_notice, 0),
            ])
            ctx = {
                "display_name": "测试群",
                "username": "57757918914@chatroom",
                "self_username": "wxid_me",
                "is_group": True,
                "message_tables": [{
                    "db_path": str(path),
                    "table_name": table_name,
                }],
            }

            result = collect_group_invite_stats(ctx, members, {})

        self.assertEqual(result["summary"]["invite_event_count"], 3)
        self.assertEqual(result["summary"]["unparsed_count"], 0)
        self.assertEqual(len(result["ranking"]), 1)
        self.assertEqual(result["ranking"][0]["inviter_name"], "Au Revior")
        self.assertEqual(result["ranking"][0]["unique_invitee_count"], 3)
        self.assertEqual(result["ranking"][0]["direct_count"], 2)
        self.assertEqual(result["ranking"][0]["qr_count"], 1)

    def test_attributes_self_invitation_xml_to_local_account(self):
        table_name = "Msg_" + "f" * 32
        notice = """54539324941@chatroom:
        <sysmsg type="delchatroommember">
          <delchatroommember>
            <plain><![CDATA[你邀请"陈子明"加入了群聊  ]]></plain>
            <text><![CDATA[你邀请"陈子明"加入了群聊  ]]></text>
            <link>
              <scene>invite</scene>
              <text><![CDATA[  撤销]]></text>
              <memberlist>
                <username><![CDATA[wxid_zipilqil46k022]]></username>
              </memberlist>
            </link>
          </delchatroommember>
        </sysmsg>"""
        members = [
            {
                "username": "wxid_meqnprcvjn0622",
                "display_name": "Au Revior",
                "nick_name": "Au Revior",
                "remark": "",
            },
            {
                "username": "wxid_zipilqil46k022",
                "display_name": "陈子明",
                "nick_name": "子明 | 05后OPC",
                "remark": "陈子明",
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "message.db"
            create_message_db(path, table_name, [
                (1, 601, 10000, 1785295680, notice, 0),
            ])
            ctx = {
                "display_name": "自己拉人功能测试",
                "username": "54539324941@chatroom",
                "self_username": "wxid_meqnprcvjn0622",
                "is_group": True,
                "message_tables": [{
                    "db_path": str(path),
                    "table_name": table_name,
                }],
            }

            result = collect_group_invite_stats(ctx, members, {})

        self.assertEqual(result["summary"]["invite_event_count"], 1)
        self.assertEqual(result["summary"]["unparsed_count"], 0)
        self.assertEqual(result["ranking"][0]["inviter_name"], "Au Revior")
        self.assertEqual(
            result["ranking"][0]["inviter_username"],
            "wxid_meqnprcvjn0622",
        )
        self.assertEqual(result["ranking"][0]["unique_invitee_count"], 1)
        event = result["events"][0]
        self.assertEqual(event["inviter_name_raw"], "你")
        self.assertEqual(event["invitee_name_raw"], "陈子明")
        self.assertEqual(
            event["invitee_username"],
            "wxid_zipilqil46k022",
        )
        self.assertEqual(event["inviter_identity_status"], "resolved")
        self.assertEqual(event["invitee_identity_status"], "resolved")

    def test_deduplicates_shards_and_ranks_unique_invitees(self):
        table_name = "Msg_" + "a" * 32
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "message_0.db"
            second = Path(tmp) / "message_1.db"
            shared = (
                1, 101, 10000, 1000,
                '"甲"邀请"乙"加入了群聊', 0,
            )
            create_message_db(first, table_name, [
                shared,
                (
                    2, 102, 10000, 1010,
                    '"甲"邀请"乙"加入了群聊', 0,
                ),
                (
                    3, 103, 10000, 1020,
                    '"甲"邀请"丙"加入了群聊', 0,
                ),
            ])
            create_message_db(second, table_name, [
                shared,
                (
                    4, 104, 10000, 1030,
                    '"丁"邀请"戊"加入了群聊', 0,
                ),
                (
                    5, 105, 10000, 1040,
                    "你通过扫描二维码加入群聊", 0,
                ),
                (
                    6, 106, 10000, 1050,
                    '"己"通过新的入群方式加入了群聊', 0,
                ),
            ])
            ctx = {
                "display_name": "测试群",
                "username": "room@chatroom",
                "is_group": True,
                "message_tables": [
                    {
                        "db_path": str(first),
                        "table_name": table_name,
                    },
                    {
                        "db_path": str(second),
                        "table_name": table_name,
                    },
                ],
            }

            result = collect_group_invite_stats(ctx, [], {})

        self.assertEqual(
            result["summary"]["system_message_count"], 6
        )
        self.assertEqual(
            result["summary"]["invite_event_count"], 5
        )
        self.assertEqual(
            result["summary"]["attributed_event_count"], 4
        )
        self.assertEqual(
            result["summary"]["unattributed_count"], 1
        )
        self.assertEqual(result["summary"]["unparsed_count"], 1)
        self.assertEqual(result["ranking"][0]["inviter_name"], "甲")
        self.assertEqual(
            result["ranking"][0]["unique_invitee_count"], 2
        )
        self.assertEqual(result["ranking"][0]["event_count"], 3)
        self.assertEqual(result["ranking"][1]["inviter_name"], "丁")

    def test_applies_time_range_before_aggregation(self):
        table_name = "Msg_" + "b" * 32
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "message.db"
            create_message_db(path, table_name, [
                (
                    1, 201, 10000, 1000,
                    '"甲"邀请"乙"加入了群聊', 0,
                ),
                (
                    2, 202, 10000, 2000,
                    '"甲"邀请"丙"加入了群聊', 0,
                ),
            ])
            ctx = {
                "display_name": "测试群",
                "username": "room@chatroom",
                "is_group": True,
                "message_tables": [{
                    "db_path": str(path),
                    "table_name": table_name,
                }],
            }

            result = collect_group_invite_stats(
                ctx, [], {}, start_ts=1500, end_ts=2500
            )

        self.assertEqual(
            result["ranking"][0]["unique_invitee_count"], 1
        )
        self.assertEqual(
            result["events"][0]["invitee_name_raw"], "丙"
        )

    def test_counts_methods_and_breaks_ties_by_first_invite_time(self):
        table_name = "Msg_" + "e" * 32
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "message.db"
            create_message_db(path, table_name, [
                (
                    1, 501, 10000, 900,
                    '"丁"邀请"戊"加入了群聊', 0,
                ),
                (
                    2, 502, 10000, 1000,
                    '"甲"邀请"乙"加入了群聊', 0,
                ),
                (
                    3, 503, 10000, 1010,
                    '"丙"通过扫描"甲"分享的二维码加入群聊',
                    0,
                ),
                (
                    4, 504, 10000, 1100,
                    '"己"邀请"庚"加入了群聊', 0,
                ),
            ])
            ctx = {
                "display_name": "测试群",
                "username": "room@chatroom",
                "is_group": True,
                "message_tables": [{
                    "db_path": str(path),
                    "table_name": table_name,
                }],
            }

            result = collect_group_invite_stats(ctx, [], {})

        self.assertEqual(result["ranking"][0]["inviter_name"], "甲")
        self.assertEqual(result["ranking"][0]["direct_count"], 1)
        self.assertEqual(result["ranking"][0]["qr_count"], 1)
        self.assertEqual(
            [
                item["inviter_name"]
                for item in result["ranking"][1:]
            ],
            ["丁", "己"],
        )

    def test_rejects_private_chat_context(self):
        with self.assertRaisesRegex(ValueError, "只支持群聊"):
            collect_group_invite_stats(
                {"is_group": False, "message_tables": []},
                [],
                {},
            )

    def test_returns_empty_success_when_group_has_no_invites(self):
        table_name = "Msg_" + "c" * 32
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "message.db"
            create_message_db(path, table_name, [
                (
                    1, 301, 10000, 1000,
                    '"甲"修改群名为“测试群”', 0,
                ),
            ])
            ctx = {
                "display_name": "测试群",
                "username": "room@chatroom",
                "is_group": True,
                "message_tables": [{
                    "db_path": str(path),
                    "table_name": table_name,
                }],
            }

            result = collect_group_invite_stats(ctx, [], {})

        self.assertEqual(result["ranking"], [])
        self.assertEqual(
            result["summary"]["invite_event_count"], 0
        )

    def test_continues_after_one_message_database_fails(self):
        table_name = "Msg_" + "d" * 32
        with tempfile.TemporaryDirectory() as tmp:
            valid = Path(tmp) / "valid.db"
            create_message_db(valid, table_name, [
                (
                    1, 401, 10000, 1000,
                    '"甲"邀请"乙"加入了群聊', 0,
                ),
            ])
            ctx = {
                "display_name": "测试群",
                "username": "room@chatroom",
                "is_group": True,
                "message_tables": [
                    {
                        "db_path": str(Path(tmp) / "missing.db"),
                        "table_name": table_name,
                    },
                    {
                        "db_path": str(valid),
                        "table_name": table_name,
                    },
                ],
            }

            result = collect_group_invite_stats(ctx, [], {})

        self.assertEqual(
            result["summary"]["attributed_event_count"], 1
        )
        self.assertEqual(len(result["failures"]), 1)


if __name__ == "__main__":
    unittest.main()

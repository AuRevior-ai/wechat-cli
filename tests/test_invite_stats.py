import unittest

from wechat_cli.core.invite_stats import (
    IdentityResolver,
    is_invite_like_notice,
    parse_identity_bindings,
    parse_invite_notice,
)


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


if __name__ == "__main__":
    unittest.main()

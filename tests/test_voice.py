import sqlite3
import tempfile
import unittest
import wave
from contextlib import closing
from pathlib import Path
from unittest import mock

from wechat_cli.core.voice import (
    decode_silk_to_wav,
    find_media_db_keys,
    find_voice_record,
    voice_duration_seconds,
    write_pcm_wav,
)


def _build_media_db(
    path,
    *,
    username="wxid_demo",
    local_id=116,
    create_time=1785294352,
    voice_data=b"#!SILK_V3demo",
):
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("CREATE TABLE Name2Id (user_name TEXT)")
        conn.execute(
            """CREATE TABLE VoiceInfo (
                chat_name_id INTEGER,
                create_time INTEGER,
                local_id INTEGER,
                svr_id INTEGER,
                voice_data BLOB,
                data_index INTEGER
            )"""
        )
        cursor = conn.execute("INSERT INTO Name2Id(user_name) VALUES (?)", (username,))
        conn.execute(
            """INSERT INTO VoiceInfo(
                chat_name_id, create_time, local_id, svr_id, voice_data, data_index
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (cursor.lastrowid, create_time, local_id, 999, voice_data, 0),
        )
        conn.commit()
    return path


class VoiceDatabaseTests(unittest.TestCase):
    def test_finds_media_database_keys_in_numeric_order(self):
        keys = {
            "message\\media_10.db": {},
            "message/message_2.db": {},
            "message/media_1.db": {},
        }

        self.assertEqual(
            find_media_db_keys(keys),
            ["message/media_1.db", "message\\media_10.db"],
        )

    def test_reads_voice_by_chat_and_local_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _build_media_db(Path(tmp) / "media_1.db")

            record = find_voice_record(
                [("message/media_1.db", path)], "wxid_demo", 116, 1785294352
            )

        self.assertEqual(record.data, b"#!SILK_V3demo")
        self.assertEqual(record.local_id, 116)
        self.assertEqual(record.svr_id, 999)
        self.assertEqual(record.media_db, "media_1.db")

    def test_does_not_return_voice_from_another_chat(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _build_media_db(Path(tmp) / "media_1.db", username="wxid_other")

            record = find_voice_record(
                [path], "wxid_demo", 116, 1785294352
            )

        self.assertIsNone(record)

    def test_continues_after_one_media_database_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "media_0.db"
            broken.write_bytes(b"not sqlite")
            valid = _build_media_db(Path(tmp) / "media_1.db")

            record = find_voice_record(
                [broken, valid], "wxid_demo", 116, 1785294352
            )

        self.assertIsNotNone(record)
        self.assertEqual(record.media_db, "media_1.db")

    def test_rejects_timestamp_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _build_media_db(Path(tmp) / "media_1.db", create_time=100)

            record = find_voice_record(
                [path], "wxid_demo", 116, 1000, max_time_delta=60
            )

        self.assertIsNone(record)


class VoiceDecodeTests(unittest.TestCase):
    def test_parses_voice_length_as_seconds(self):
        xml = '<msg><voicemsg voicelength="7460" voiceformat="4" /></msg>'

        self.assertAlmostEqual(voice_duration_seconds(xml), 7.46)
        self.assertIsNone(voice_duration_seconds("<msg />"))

    def test_writes_16khz_mono_pcm_wav(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "voice.wav"
            write_pcm_wav(target, b"\x00\x00" * 16000)

            with wave.open(str(target), "rb") as wav:
                self.assertEqual(wav.getframerate(), 16000)
                self.assertEqual(wav.getnchannels(), 1)
                self.assertEqual(wav.getsampwidth(), 2)
                self.assertEqual(wav.getnframes(), 16000)

    def test_decodes_silk_to_wav_without_ffmpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            decoder = Path(tmp) / "decoder.exe"
            decoder.write_bytes(b"fake")
            target = Path(tmp) / "voice.wav"

            def fake_run(argv, **kwargs):
                Path(argv[2]).write_bytes(b"\x00\x00" * 160)
                return mock.Mock(returncode=0)

            with mock.patch("subprocess.run", side_effect=fake_run) as run:
                decode_silk_to_wav(
                    b"#!SILK_V3demo", target, decoder_path=decoder
                )

            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][-3:], ["-Fs_API", "16000", "-quiet"])
            with wave.open(str(target), "rb") as wav:
                self.assertEqual(wav.getframerate(), 16000)
                self.assertEqual(wav.getnframes(), 160)


if __name__ == "__main__":
    unittest.main()

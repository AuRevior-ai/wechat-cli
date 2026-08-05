import hashlib
import tempfile
import unittest
from pathlib import Path

from wechat_cli.update.download import DownloadRequest, download_update
from wechat_cli.update.errors import ErrorCode, UpdateError


class FakeResponse:
    def __init__(self, body, *, status=200, headers=None, fail_after=None):
        self.body = body
        self.status = status
        self.headers = headers or {}
        self.offset = 0
        self.fail_after = fail_after

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size=-1):
        if self.fail_after is not None and self.offset >= self.fail_after:
            raise OSError("connection reset")
        if self.offset >= len(self.body):
            return b""
        if size < 0:
            size = len(self.body) - self.offset
        if self.fail_after is not None:
            size = min(size, self.fail_after - self.offset)
        chunk = self.body[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk


class FakeOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, headers, timeout):
        self.calls.append((url, dict(headers), timeout))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class UpdateDownloadTests(unittest.TestCase):
    def request(self, content, **overrides):
        values = {
            "download_url": "https://api.example.test/v1/updates/download",
            "download_ticket": "dlt_secret_ticket",
            "release_id": "rel_050",
            "version": "0.5.0",
            "filename": "wechat-cli-app-0.5.0-win-x64.zip",
            "expected_size": len(content),
            "expected_sha256": hashlib.sha256(content).hexdigest(),
        }
        values.update(overrides)
        return DownloadRequest(**values)

    def test_downloads_to_part_then_atomically_finishes(self):
        content = b"update-package" * 1000
        opener = FakeOpener(
            [FakeResponse(content, headers={"ETag": '"asset-v1"'})]
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = download_update(
                self.request(content),
                Path(tmp),
                opener=opener,
                chunk_size=4096,
            )

            self.assertEqual(content, result.read_bytes())
            self.assertFalse(result.with_suffix(result.suffix + ".part").exists())
            self.assertFalse(Path(str(result) + ".part.json").exists())

        url, headers, _ = opener.calls[0]
        self.assertEqual("https://api.example.test/v1/updates/download", url)
        self.assertEqual("Download dlt_secret_ticket", headers["Authorization"])
        self.assertNotIn("dlt_secret_ticket", url)
        self.assertNotIn("Range", headers)

    def test_interrupted_download_keeps_part_and_resumes_with_range(self):
        content = b"0123456789" * 1000
        first = FakeOpener(
            [FakeResponse(content, headers={"ETag": '"asset-v1"'}, fail_after=3000)]
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request = self.request(content)

            with self.assertRaises(OSError):
                download_update(request, root, opener=first, chunk_size=1000)

            part = root / (request.filename + ".part")
            self.assertEqual(3000, part.stat().st_size)

            second = FakeOpener(
                [
                    FakeResponse(
                        content[3000:],
                        status=206,
                        headers={
                            "ETag": '"asset-v1"',
                            "Content-Range": f"bytes 3000-{len(content)-1}/{len(content)}",
                        },
                    )
                ]
            )
            result = download_update(request, root, opener=second, chunk_size=1000)

            self.assertEqual(content, result.read_bytes())
            _, headers, _ = second.calls[0]
            self.assertEqual("bytes=3000-", headers["Range"])
            self.assertEqual('"asset-v1"', headers["If-Range"])

    def test_server_ignoring_range_restarts_instead_of_appending(self):
        content = b"abcdefghij" * 1000
        first = FakeOpener(
            [FakeResponse(content, headers={"ETag": '"asset-v1"'}, fail_after=2000)]
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request = self.request(content)
            with self.assertRaises(OSError):
                download_update(request, root, opener=first, chunk_size=1000)

            second = FakeOpener(
                [FakeResponse(content, status=200, headers={"ETag": '"asset-v1"'})]
            )
            result = download_update(request, root, opener=second, chunk_size=1000)

            self.assertEqual(content, result.read_bytes())

    def test_metadata_mismatch_discards_stale_partial_file(self):
        old_content = b"old-package"
        new_content = b"new-package" * 100
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_request = self.request(old_content, release_id="rel_old")
            first = FakeOpener(
                [FakeResponse(old_content, headers={"ETag": '"old"'}, fail_after=3)]
            )
            with self.assertRaises(OSError):
                download_update(old_request, root, opener=first, chunk_size=3)

            new_request = self.request(new_content, release_id="rel_new")
            opener = FakeOpener(
                [FakeResponse(new_content, headers={"ETag": '"new"'})]
            )
            result = download_update(new_request, root, opener=opener)

            self.assertEqual(new_content, result.read_bytes())
            self.assertNotIn("Range", opener.calls[0][1])

    def test_hash_mismatch_removes_invalid_complete_file(self):
        content = b"tampered"
        request = self.request(content, expected_sha256="00" * 32)
        opener = FakeOpener([FakeResponse(content)])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(UpdateError) as caught:
                download_update(request, root, opener=opener)

            self.assertEqual(ErrorCode.UPDATE_HASH_MISMATCH, caught.exception.code)
            self.assertFalse((root / request.filename).exists())
            self.assertFalse((root / (request.filename + ".part")).exists())

    def test_rejects_ticket_in_download_url(self):
        content = b"x"
        with self.assertRaises(ValueError):
            self.request(
                content,
                download_url="https://api.example.test/v1/updates/download?ticket=dlt_secret_ticket",
            )


if __name__ == "__main__":
    unittest.main()

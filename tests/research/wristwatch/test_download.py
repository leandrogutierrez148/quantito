"""Archive recovery uses an injected byte writer, never HTTP."""

import hashlib
import tempfile
import unittest
from pathlib import Path

from quantito.research.strategies.wristwatch.download import verified_archive


class DownloadCommitTests(unittest.TestCase):
    def test_existing_corrupt_file_is_preserved_and_replaced_only_after_validation(self):
        payload = b"verified synthetic archive"
        checksum = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "btc.zip"
            path.write_bytes(b"old corrupt archive")
            path.with_name("btc.zip.corrupt").write_bytes(b"earlier corrupt archive")

            def write(partial):
                self.assertEqual(partial.name, "btc.zip.part")
                self.assertFalse(path.exists())
                self.assertEqual(
                    path.with_name("btc.zip.corrupt.1").read_bytes(), b"old corrupt archive"
                )
                partial.write_bytes(payload)
                self.assertFalse(path.exists())

            self.assertEqual(verified_archive(path, checksum, write), checksum)
            self.assertEqual(path.read_bytes(), payload)
            self.assertFalse(path.with_name("btc.zip.part").exists())
            self.assertEqual(
                path.with_name("btc.zip.corrupt").read_bytes(), b"earlier corrupt archive"
            )

            def unexpected_download(partial):
                self.fail("A valid archive must not be downloaded again")

            verified_archive(path, checksum, unexpected_download)

    def test_bad_download_never_becomes_final_and_next_attempt_can_recover(self):
        payload = b"good"
        checksum = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "btc.zip"
            with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
                verified_archive(path, checksum, lambda partial: partial.write_bytes(b"bad"))
            self.assertFalse(path.exists())
            self.assertFalse(path.with_name("btc.zip.part").exists())
            self.assertEqual(path.with_name("btc.zip.part.corrupt").read_bytes(), b"bad")
            verified_archive(path, checksum, lambda partial: partial.write_bytes(payload))
            self.assertEqual(path.read_bytes(), payload)

    def test_interrupted_download_leaves_no_unverified_final(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "btc.zip"

            def interrupted(partial):
                partial.write_bytes(b"truncated")
                raise ConnectionError("synthetic interruption")

            with self.assertRaises(ConnectionError):
                verified_archive(path, "not-matching", interrupted)
            self.assertFalse(path.exists())
            self.assertEqual(path.with_name("btc.zip.part.corrupt").read_bytes(), b"truncated")

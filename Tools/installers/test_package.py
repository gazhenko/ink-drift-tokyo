"""Regression checks for archive trust boundaries and complete NSIS payloads."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

import package


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def archive(self, filename="game/file.txt"):
        archive = self.root / "game.zip"
        with zipfile.ZipFile(archive, "w") as target:
            target.writestr(filename, b"game data")
        checksums = self.root / "SHA256SUMS"
        checksums.write_text(f"{package.sha256(archive)}  {archive.name}\n")
        return archive, checksums

    def test_valid_archive(self):
        package.verify_archive(*self.archive())

    def test_tampered_archive_is_rejected(self):
        archive, checksums = self.archive()
        with archive.open("ab") as target:
            target.write(b"tampered")
        with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
            package.verify_archive(archive, checksums)

    def test_missing_or_duplicate_checksums_are_rejected(self):
        archive, checksums = self.archive()
        line = checksums.read_text()
        for contents in ("", line + line):
            with self.subTest(contents=contents):
                checksums.write_text(contents)
                with self.assertRaisesRegex(ValueError, "exactly one"):
                    package.verify_archive(archive, checksums)

    def test_escape_paths_are_rejected_even_with_valid_checksum(self):
        for filename in ("../escape", "/absolute", "C:/drive", "folder\\..\\escape"):
            with self.subTest(filename=filename):
                with self.assertRaisesRegex(ValueError, "Unsafe archive path"):
                    package.verify_archive(*self.archive(filename))

    @unittest.skipUnless(shutil.which("makensis") and shutil.which("7zz"),
                         "requires NSIS and sevenzip")
    def test_offline_installer_contains_every_player_file(self):
        # Exercise root-folder differences and escaping in filenames and build paths.
        archive = self.root / "fixture.zip"
        expected = {"Fixture.exe": b"MZ game fixture", "UnityPlayer.dll": b"MZ unity fixture",
                    "Fixture_Data/level with $ spaces": b"game level",
                    "MonoBleedingEdge/runtime.dll": b"runtime fixture"}
        with zipfile.ZipFile(archive, "w") as target:
            for name, data in expected.items():
                target.writestr("Wrapped/" + name, data)
            target.writestr("Wrapped/Fixture_BurstDebugInformation_DoNotShip/debug.txt", b"debug")
        work = self.root / "build with $ spaces"
        work.mkdir()
        game = {"name": "Fixture Game", "id": "Fixture", "exe": "Fixture.exe",
                "windows_root": "Wrapped"}
        output = self.root / "Fixture-Setup.exe"
        package.build_windows(game, "v1.2.3", archive, work, output, "Installation guide")
        extracted = self.root / "verify"
        subprocess.run(["7zz", "x", "-y", "-bso0", "-bsp0", f"-o{extracted}", str(output)], check=True)
        player = next(extracted.rglob("Fixture.exe")).parent
        for name, contents in expected.items():
            self.assertEqual((player / name).read_bytes(), contents)
        self.assertEqual((player / "START-HERE.txt").read_text(), "Installation guide")
        self.assertFalse(list(player.rglob("debug.txt")))
        removal = (work / "uninstall-files.nsh").read_text()
        self.assertNotIn("RMDir /r", removal)
        self.assertNotIn("$APPDATA", removal)
        self.assertNotIn("debug.txt", removal)


if __name__ == "__main__":
    unittest.main()

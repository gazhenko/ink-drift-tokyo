#!/usr/bin/env python3
"""Compare completed installer payloads with every file in their source archives.

Requires macOS for DMGs and 7zz for EXEs. Never launches game/installer code.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import plistlib
import stat
import tempfile
import zipfile

import package


def check_payload(archive, source_root, target):
    count = 0
    with zipfile.ZipFile(archive) as source:
        for item in source.infolist():
            path = PurePosixPath(item.filename)
            if item.is_dir() or not path.is_relative_to(source_root):
                continue
            relative = path.relative_to(source_root)
            if any(part.endswith("_BurstDebugInformation_DoNotShip") or
                   part.endswith("_BackUpThisFolder_ButDontShipItWithYourGame")
                   for part in relative.parts):
                continue
            file = target / str(relative)
            if stat.S_ISLNK(item.external_attr >> 16):
                if not file.is_symlink() or os.readlink(file).encode() != source.read(item):
                    raise ValueError(f"Symlink mismatch: {file}")
            else:
                digest = hashlib.sha256()
                with source.open(item) as stream:
                    for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                        digest.update(chunk)
                if not file.is_file() or package.sha256(file) != digest.hexdigest():
                    raise ValueError(f"Payload mismatch: {file}")
            count += 1
    if not count:
        raise ValueError("No source files compared")
    return count


def main():
    game = json.loads((package.HERE / "game.json").read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", nargs="?", default=game["version"])
    parser.add_argument("--release-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    release = (args.release_dir or package.ROOT / "Builds/release" / args.version).resolve()
    output = (args.output or package.ROOT / "Builds/installers" / args.version).resolve()
    manifest = json.loads((output / "installer-manifest.json").read_text())
    report = {"version": args.version, "windows_runtime_verified": False, "artifacts": []}
    # Verify all generated downloads, including guide and manifest.
    for line in (output / "INSTALLER-SHA256SUMS.txt").read_text().splitlines():
        digest, name = line.split("  ", 1)
        if package.sha256(output / name) != digest:
            raise ValueError(f"Installer checksum mismatch: {name}")
    for item in manifest["artifacts"]:
        artifact = output / item["file"]
        with tempfile.TemporaryDirectory(prefix="installer-verify-") as temp:
            work = Path(temp)
            if artifact.suffix == ".dmg":
                archive = release / f"{game['prefix']}-{args.version}-macOS-universal.zip"
                package.verify_archive(archive, release / game["checksums"])
                mounted = work / "mount"
                package.run("hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint", mounted, artifact)
                try:
                    if not (mounted / "Applications").is_symlink() or os.readlink(mounted / "Applications") != "/Applications":
                        raise ValueError("Missing Applications shortcut")
                    if not (mounted / "START HERE.txt").is_file() or not (mounted / "How to install.html").is_file():
                        raise ValueError("Missing Mac installation guide")
                    app = mounted / game["app"]
                    count = check_payload(archive, PurePosixPath(game["mac_root"]) / game["app"], app)
                    # External credit/licence documents are part of the distribution too.
                    with zipfile.ZipFile(archive) as source:
                        root = PurePosixPath(game["mac_root"])
                        extras = set()
                        for entry in source.infolist():
                            path = PurePosixPath(entry.filename)
                            if path.is_relative_to(root):
                                relative = path.relative_to(root)
                                if relative.parts and (relative.parts[0] == "Credits" or relative.parts[0].upper().startswith(("LICENSE", "CREDITS"))):
                                    extras.add(relative.parts[0])
                        for extra in extras:
                            if (mounted / extra).is_dir():
                                count += check_payload(archive, root / extra, mounted / extra)
                            elif (mounted / extra).read_bytes() != source.read(str(root / extra)):
                                raise ValueError(f"Licence mismatch: {extra}")
                            else:
                                count += 1
                    package.run("codesign", "--verify", "--deep", "--strict", app)
                    with (app / "Contents/Info.plist").open("rb") as source:
                        info = plistlib.load(source)
                    package.run("lipo", app / "Contents/MacOS" / info["CFBundleExecutable"], "-verify_arch", "arm64", "x86_64")
                finally:
                    package.run("hdiutil", "detach", mounted)
            else:
                archive = release / f"{game['prefix']}-{args.version}-Windows-x64.zip"
                package.verify_archive(archive, release / game["checksums"])
                package.run("7zz", "x", "-y", "-bso0", "-bsp0", f"-o{work}", artifact)
                matches = list(work.rglob(game["exe"]))
                if len(matches) != 1:
                    raise ValueError("Expected exactly one Windows executable")
                player = matches[0].parent
                count = check_payload(archive, PurePosixPath(game["windows_root"]), player)
                if not (player / "START-HERE.txt").is_file():
                    raise ValueError("Missing Windows installation guide")
            report["artifacts"].append({"file": artifact.name, "source_files_verified": count})
            print(f"PASS: {artifact.name}: {count} original game files verified", flush=True)
    (output / "installer-validation.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()

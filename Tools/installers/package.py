#!/usr/bin/env python3
"""Build offline DMG/EXE installers from checksum-verified release archives.

This directory is self-contained and vendored in each game repository.
Requires macOS, Python 3 and NSIS (brew install makensis). Never publishes.
"""

import argparse
import hashlib
import html
import json
import os
from pathlib import Path, PurePosixPath
import plistlib
import re
import shutil
import subprocess
import tempfile
import zipfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_archive(archive, checksums):
    matches = []
    for line in checksums.read_text().splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?(.+)", line)
        if match and match[2] == archive.name:
            matches.append(match[1].lower())
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one checksum for {archive.name}")
    if sha256(archive) != matches[0]:
        raise ValueError(f"Checksum mismatch: {archive}")
    # Check paths before either extractor gets the archive.
    with zipfile.ZipFile(archive) as source:
        for item in source.infolist():
            path = PurePosixPath(item.filename.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts or ":" in item.filename:
                raise ValueError(f"Unsafe archive path: {item.filename}")
    print(f"Verified {archive.name}", flush=True)


def instructions(game, version):
    name = game["name"]
    return f"""INSTALL {name.upper()} {version}

You do not need a coding agent, Unity, Python, or a terminal to play.
Download the installer onto the computer where you want to play.
The installer includes the whole game; installation and play work offline.

MAC (Apple Silicon or Intel)
1. Double-click the .dmg file you downloaded.
2. Drag {game['app']} onto the Applications folder beside it.
3. Wait for copying to finish. Open Applications and double-click {name}.
4. Eject the disk image in Finder. You can delete the downloaded .dmg file.

If you already have the game, quit it before copying and choose Replace.
This preview is ad-hoc signed, but not Apple-notarized. If macOS blocks it,
try opening the copy in Applications, then open System Settings > Privacy
& Security, scroll to Security, and choose Open Anyway for {name}.
Only approve the copy you downloaded from the official game release.
Apple's guide: https://support.apple.com/102445
If macOS says the app is damaged, download a fresh copy. Do not disable
Mac security settings. If it still fails, report the message to the developer.

WINDOWS (Windows 10 or 11, Intel/AMD 64-bit)
1. Double-click the file ending in Windows-x64-Setup.exe.
2. Choose Next, then Install. No administrator password is needed.
3. Choose Finish. Open the game's desktop shortcut, or find {name} in Start.
4. You can delete the downloaded setup file after installing.

This preview installer is unsigned. Windows may show an unfamiliar-app
warning. Check that the file came from the official game release before
choosing More info > Run anyway, if that option is offered. If your computer
blocks it completely, ask its administrator; do not disable its protection.
To update, quit the game and run the newer installer. To remove it, open
Settings > Apps, find {name}, and choose Uninstall.

SAVED PROGRESS
Updates and removal keep your saved progress, which lives separately from
the game. Do not delete the save folder if you want to keep your progress.
On Mac, remove the game by moving it from Applications to the Trash.

HELP
Official releases: https://github.com/gazhenko/{game['repo']}/releases
Report a problem: https://github.com/gazhenko/{game['repo']}/issues
Include your computer model, operating system, and the message you saw.
"""


def nsis_string(value):
    # NSIS uses $, not backslash, for escaping. Windows paths retain backslashes.
    return str(value).replace("$", "$$").replace('"', '$\\"')


def build_windows(game, version, archive, work, output, guide):
    extracted = work / "windows"
    with zipfile.ZipFile(archive) as source:
        source.extractall(extracted)
    payload = extracted / game["windows_root"]
    exe = payload / game["exe"]
    if not exe.is_file() or not (payload / (exe.stem + "_Data")).is_dir():
        raise ValueError(f"Incomplete Windows player: {payload}")
    if not (payload / "UnityPlayer.dll").is_file():
        raise ValueError("Windows player is missing UnityPlayer.dll")
    for path in list(payload.rglob("*")):
        if path.is_dir() and (path.name.endswith("_BurstDebugInformation_DoNotShip")
                              or path.name.endswith("_BackUpThisFolder_ButDontShipItWithYourGame")):
            shutil.rmtree(path)
    (payload / "START-HERE.txt").write_text(guide, encoding="utf-8")
    files = sorted(path for path in payload.rglob("*") if path.is_file())
    dirs = sorted((path for path in payload.rglob("*") if path.is_dir()),
                  key=lambda path: len(path.parts), reverse=True)
    with (work / "uninstall-files.nsh").open("w") as target:
        for path in files:
            relative = nsis_string(str(path.relative_to(payload)).replace("/", "\\"))
            target.write(f'  Delete "$INSTDIR\\{relative}"\n')
        for path in dirs:
            relative = nsis_string(str(path.relative_to(payload)).replace("/", "\\"))
            target.write(f'  RMDir "$INSTDIR\\{relative}"\n')
    defines = {
        "GAME_NAME": game["name"], "GAME_ID": game["id"],
        "GAME_EXE": game["exe"], "GAME_VERSION": version,
        "PRODUCT_VERSION": version.removeprefix("v") + ".0",
        "OUTPUT_FILE": output, "PAYLOAD_DIR": payload,
        "INSTALLED_KB": (sum(path.stat().st_size for path in files) + 1023) // 1024,
    }
    # File and OutFile are compiler commands: $ in a host path is literal.
    # Runtime strings (including uninstall paths) instead require $$ escaping.
    with (work / "config.nsh").open("w") as target:
        for key, value in defines.items():
            encoded = str(value).replace('"', '$\\"') if key in ("PAYLOAD_DIR", "OUTPUT_FILE") else nsis_string(value)
            target.write(f'!define {key} "{encoded}"\n')
    shutil.copy2(HERE / "windows.nsi", work / "windows.nsi")
    run("makensis", "-WX", "-V2", work / "windows.nsi")


def build_mac(game, archive, work, output, guide):
    extracted = work / "mac"
    run("ditto", "-x", "-k", archive, extracted)
    app = extracted / game["mac_root"] / game["app"]
    with (app / "Contents/Info.plist").open("rb") as source:
        info = plistlib.load(source)
    executable = app / "Contents/MacOS" / info["CFBundleExecutable"]
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ValueError(f"Mac executable missing or not executable: {executable}")
    run("lipo", executable, "-verify_arch", "arm64", "x86_64")
    run("codesign", "--verify", "--deep", "--strict", app)
    contents = work / "disk-image"
    contents.mkdir()
    run("ditto", app, contents / app.name)
    # Some releases ship font/audio licences beside the app (not inside it).
    # Keep them in the disk image without changing the signed application.
    source_root = extracted / game["mac_root"]
    for extra in source_root.iterdir():
        if extra.name == "Credits" or extra.name.upper().startswith(("LICENSE", "CREDITS")):
            run("ditto", extra, contents / extra.name)
    (contents / "Applications").symlink_to("/Applications")
    (contents / "START HERE.txt").write_text(guide, encoding="utf-8")
    title = html.escape(game["name"])
    (contents / "How to install.html").write_text(f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><title>Install {title}</title>
<style>body{{font:20px system-ui;max-width:700px;margin:60px auto;padding:0 25px;
color:#20252a;line-height:1.6}}h1{{line-height:1.2}}a{{color:#165da8}}</style>
<h1>Welcome to {title}</h1>
<ol><li>Drag <strong>{html.escape(game['app'])}</strong> onto <strong>Applications</strong> in this window.
<li>Wait for copying to finish.
<li>Open <strong>Applications</strong> and double-click <strong>{title}</strong>.
<li>Eject this disk image in Finder.</ol>
<p>Updating? Quit the game first, then choose <strong>Replace</strong>. Your saves are kept.</p>
<p>If macOS blocks the game, try opening the copy in Applications, then go to
<strong>System Settings → Privacy &amp; Security → Open Anyway</strong> for {title}.
This preview has not been notarized by Apple.
<a href="https://support.apple.com/102445">Apple's first-launch instructions</a>.</p>
<p>You can delete the downloaded disk image after installing. To remove the game,
move it from Applications to the Trash. Your saved progress is kept.</p>
</html>""", encoding="utf-8")
    run("hdiutil", "create", "-volname", f"Install {game['name']}",
        "-srcfolder", contents, "-format", "UDZO", "-fs", "HFS+", output)
    run("hdiutil", "verify", output)


def main():
    game = json.loads((HERE / "game.json").read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", nargs="?", default=game["version"])
    parser.add_argument("--release-dir", type=Path, help="Folder with player ZIPs and checksums")
    parser.add_argument("--output", type=Path, help="Output folder (default: Builds/installers/VERSION)")
    parser.add_argument("--platform", choices=["all", "mac", "windows"], default="all")
    args = parser.parse_args()
    if not re.fullmatch(r"v\d+\.\d+\.\d+", args.version):
        parser.error("Version must look like v1.2.3")
    platforms = ["mac", "windows"] if args.platform == "all" else [args.platform]
    commands = ["ditto", "hdiutil", "codesign", "lipo"] if "mac" in platforms else []
    if "windows" in platforms:
        commands.append("makensis")
    for command in commands:
        if not shutil.which(command):
            parser.error(f"Missing {command}. Mac packaging needs macOS; install NSIS with brew install makensis.")
    release = (args.release_dir or ROOT / "Builds/release" / args.version).resolve()
    output = (args.output or ROOT / "Builds/installers" / args.version).resolve()
    output.mkdir(parents=True, exist_ok=True)
    guide = instructions(game, args.version)
    manifest = {"version": args.version, "game": game["name"], "sources": [],
                "artifacts": [], "mac_notarized": False, "windows_signed": False,
                "windows_runtime_verified": False}
    # Work beside the outputs, with automatic cleanup on errors and interrupts.
    with tempfile.TemporaryDirectory(prefix=".packaging-", dir=output) as temp:
        work = Path(temp)
        for platform in platforms:
            suffix = "macOS-universal.zip" if platform == "mac" else "Windows-x64.zip"
            archive = release / f"{game['prefix']}-{args.version}-{suffix}"
            verify_archive(archive, release / game["checksums"])
            manifest["sources"].append({"file": archive.name, "sha256": sha256(archive)})
            name = f"{game['prefix']}-{args.version}-" + (
                "macOS-universal.dmg" if platform == "mac" else "Windows-x64-Setup.exe")
            artifact = work / name
            if platform == "mac":
                build_mac(game, archive, work, artifact, guide)
            else:
                build_windows(game, args.version, archive, work, artifact, guide)
            manifest["artifacts"].append({"file": name, "bytes": artifact.stat().st_size,
                                          "sha256": sha256(artifact)})
        (work / "START-HERE.txt").write_text(guide, encoding="utf-8")
        (work / "installer-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        names = [item["file"] for item in manifest["artifacts"]] + ["START-HERE.txt", "installer-manifest.json"]
        (work / "INSTALLER-SHA256SUMS.txt").write_text("".join(
            f"{sha256(work / name)}  {name}\n" for name in names))
        for name in names + ["INSTALLER-SHA256SUMS.txt"]:
            (work / name).replace(output / name)
    print(f"Installers ready: {output}", flush=True)


if __name__ == "__main__":
    main()

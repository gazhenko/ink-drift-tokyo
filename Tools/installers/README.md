# Offline installers

End users receive a Mac `.dmg` and a Windows `-Setup.exe`. Both contain the entire
game and work offline. No agent, Unity editor, scripting runtime or package manager
is required on the player's computer. `START-HERE.txt` is included in both formats
and also generated as a separate download.

Mac: open the image, drag the app to Applications, then launch it there. The image
also contains a plain-language HTML guide. Existing ad-hoc signatures are verified
and preserved. This is not an Apple-notarized distribution.

Windows: Next → Install → Finish; installs for the current account in
`%LOCALAPPDATA%\Programs\GAME_ID`, adds desktop/Start shortcuts, and registers
removal in Settings → Apps. Requires Windows 10/11 on Intel/AMD x64. There is no
admin elevation. Finish offers an optional first launch. Updates unpack into a
unique sibling directory and replace the existing installation only after
extraction succeeds. Removal uses an explicit file inventory, never recursive
deletion of the install directory. Saves are outside that directory and are kept.
Close the game before updating or removing it.

## Build on a Mac

Install build tools once (developer machine only):

```sh
brew install makensis sevenzip
```

Put the original release ZIPs and its `SHA256SUMS` / `SHA256SUMS.txt` in
`Builds/release/VERSION`. They are verified before extraction. Haze archives
contain a top-level folder; Ink Drift and Saltmoss archives have files at the
root. `game.json` describes these differences.

```sh
python3 Tools/installers/package.py                 # game.json's default version
python3 Tools/installers/package.py v1.2.3          # a future release
python3 Tools/installers/package.py --help
python3 -m unittest discover -s Tools/installers -v
python3 Tools/installers/verify.py                  # inspect both completed payloads
```

Outputs go to `Builds/installers/VERSION` unless `--output` is given. Use
`--release-dir` to package an existing archive folder elsewhere. Windows-only
packaging (`--platform windows`) also runs on Linux with NSIS and Python 3.9+.
Each repository vendors the same `package.py`, `windows.nsi`, and tests so it
can be distributed and built independently; keep these copies in sync when
changing common behavior.

For Haze, which is a distribution-only repository, retrieve source archives with
`gh release download v0.4.0 --repo gazhenko/haze --pattern '*.zip' --pattern SHA256SUMS --dir Builds/release/v0.4.0`.
Ink Drift and Saltmoss's `Tools/release.sh` automatically include installers;
`INK_NO_PUBLISH=1` or `SM_NO_PUBLISH=1` builds a release without publishing it.
The packager itself never publishes or changes existing game archives.

`INSTALLER-SHA256SUMS.txt` covers the generated downloads. The manifest records
the exact source/archive hashes and the signing/runtime limitations. Single
platform runs should use a separate `--output` directory so an earlier build's
other platform files are not confused with this run's manifest.

## Release validation

- Verify every installer with `shasum -a 256 -c INSTALLER-SHA256SUMS.txt`.
- Mount each DMG read-only; compare its game files with the source ZIP, check
  the Applications shortcut and `codesign --verify --deep --strict`.
- Extract each EXE with `7zz` and compare every shipped game file with the ZIP.
- On Windows 10/11, manually exercise install, shortcut launch, update while
  closed/running, and removal with a saved game present. Archive extraction and
  successful NSIS compilation do not establish Windows runtime compatibility.
- On a Mac, try a browser-downloaded copy with quarantine intact and follow the
  documented first-launch steps. Local mounting does not establish Gatekeeper
  behavior on another Mac.

Certificates are not configured here. Removing first-launch trust prompts needs
Developer ID signing and Apple notarization for Mac, and Authenticode signing
for Windows; NSIS itself uses the user's normal privileges
([NSIS documentation](https://nsis.sourceforge.io/Reference/RequestExecutionLevel)).
The guide follows [Apple's normal approval flow](https://support.apple.com/102445).
Never ship scripts that disable system security settings.

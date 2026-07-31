# Windows candidate delivery

This directory owns the local Windows delivery path for the public
`original_demo`. It does not publish releases and never packages ignored,
private, or generated content.

## Player workflow

The primary candidate is the PyInstaller one-folder ZIP. It includes a Windows
Python runtime, so an ordinary player does not install Python or understand the
source tree:

1. Extract the complete `lore2mud-windows-pyinstaller-...zip` to a local folder.
2. Double-click `Start Lore2MUD.cmd`.
3. The launcher waits for the local server to become healthy and then opens the
   default browser.

The server binds only to `127.0.0.1`. Closing the launcher window stops the
local game process. These explicit modes are also available:

```bat
"Start Lore2MUD.cmd" --web
"Start Lore2MUD.cmd" --console
"Start Lore2MUD.cmd" --diagnose
```

`--console` is the text-player fallback. `--diagnose` reports the bundle format,
runtime, application/content versions, runtime/content paths, and user data/save
paths, then validates the bundled content without starting a game.

Set `LORE2MUD_WEB_PORT` to an available port from 1 through 65535 to replace the
default `8765`. Set `LORE2MUD_NO_BROWSER=1` to keep Web mode running without
opening a browser. The automation-only `--smoke-web` mode has the same suppression.

The lightweight `lore2mud-windows-zipapp-...zip` has the same launcher behavior
but requires Python 3.11 or newer. It tries `LORE2MUD_PYTHON`, `py.exe -3`, then
`python.exe`, and reports a concrete prerequisite error when none is supported.

### User data and save compatibility

Runtime content remains read-only in the extracted bundle. Mutable data uses:

```text
%LOCALAPPDATA%\lore2mud\
`-- saves\
    `-- content-0.10.0\
```

Set `LORE2MUD_DATA_DIR` to an absolute path before launch to use a portable or
managed data location. The launcher never writes saves beside the application.

Save directories are isolated by `content_pack_version`. The current public
demo is `0.10.0` and writes save v8 with typed narrative state. Its saves reject
older content-pack versions and v7 data because v7 cannot represent that state.
v7 remains read-compatible only for content packs that declare no narrative
state. JSON saves directly under the legacy `saves` directory and other
`content-*` directories produce warnings and remain untouched. Before replacing
or removing an old bundle, back up the complete `%LOCALAPPDATA%\lore2mud`
directory.

## Maintainer workflow

Install the pinned Windows-only toolchain, run the tests, and build both the
primary runtime and fallback from a clean worktree:

```powershell
python -m pip install -r packaging/windows/requirements-build.txt
python -m unittest tests.test_windows_packaging -v
python packaging/windows/build_candidate.py --runtime pyinstaller
python packaging/windows/build_candidate.py --runtime zipapp
Get-ChildItem dist/windows/lore2mud-windows-*.zip | ForEach-Object {
    python packaging/windows/verify_candidate.py $_.FullName
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
```

`build_candidate.py` defaults to PyInstaller. The equivalent command helpers
are `build_candidate.cmd` and `verify_candidate.cmd`. `--allow-dirty` exists
only for local development evidence; handoff candidates must record a clean Git
commit in `bundle.json`.

Candidate names carry both runtime and compatibility identity:

```text
dist/windows/lore2mud-windows-pyinstaller-<app>-content-<pack>.zip
dist/windows/lore2mud-windows-zipapp-<app>-content-<pack>.zip
```

The builder enumerates only Git-tracked runtime/content paths. It uses sorted
entries, fixed ZIP timestamps, `SOURCE_DATE_EPOCH`, and `PYTHONHASHSEED`; builds
are byte-reproducible only when the commit, Python runtime, platform, and pinned
toolchain also match. `bundle.json` records runtime, Web default, app/content
versions, source commit, Python prerequisite, bundled Python/PyInstaller
versions, and the SHA-256 of every file. An outer `.sha256` sidecar covers the
complete candidate, and the project MIT `LICENSE` is included at the bundle
root.

PyInstaller is invoked with `--onedir --console --noupx` and an explicit
`--collect-data lore2mud.web`. Both builder and verifier require exactly one of
each current Player asset at:

```text
runtime/_internal/lore2mud/web/static/index.html
runtime/_internal/lore2mud/web/static/styles.css
runtime/_internal/lore2mud/web/static/app.js
```

The zipapp carries the same files under `lore2mud/web/static`. SVG remains an
accepted generic package-resource suffix for future compatibility; the current
Player has no SVG asset or reference.

### Candidate verification

The verifier treats the ZIP as untrusted input. Before extraction it rejects
traversal, absolute, reserved, duplicate, case-colliding, special-file, and
oversized layouts; it then checks the filename/version contract, manifest
coverage, all hashes, the PyInstaller `MZ` executable, and packaged Web data.

Cold start extracts into a repository-external path containing spaces, uses a
separate data directory, and runs the real `.cmd` entry. It verifies diagnostics
and old-save warnings, exercises `--console` with `quit`, starts Web on a free
loopback port, and checks exact packaged responses for `/`,
`/static/styles.css`, `/static/app.js`, and `/api/snapshot`. Finally it posts a
structured move to `/api/action`, verifies the authoritative room transition,
terminates the complete process tree, and confirms the bundle and old saves were
not modified.

## Runtime decision

Measurements below are from the integrated `0.1.0` application / `0.10.0`
content candidate built on Windows 11 x64 with Python 3.13.14 and PyInstaller
6.21.0. Runtime and compression versions can change exact sizes.

| Option | Measured or expected size | Offline and prerequisites | License, antivirus, and maintenance impact | Decision |
| --- | ---: | --- | --- | --- |
| PyInstaller one-folder | About 8.8 MB ZIP; 19.7 MB / 73 files unpacked | Fully offline and no installed Python after extraction | Redistributes CPython and the GPL-with-bootloader-exception builder output; needs third-party notices/SBOM, Python security rebuilds, code signing, and antivirus checks. Unsigned bootloaders can trigger heuristic false positives; one-folder avoids self-extraction but not reputation risk. | Primary local candidate |
| Standard-library zipapp | About 75 KB ZIP; 96 KB / 14 files unpacked | Fully offline after Python 3.11+ is installed | Does not redistribute an interpreter; smallest and most transparent, with low packaging maintenance, but Python remains the user's prerequisite. | Supported lightweight fallback |
| CPython embeddable package | Roughly 10-20 MB before project files | Can be offline with no installed Python | Requires PSF/runtime notices, Windows-specific import/bootstrap work, and prompt runtime security servicing. It avoids a custom bootloader but still needs signing and antivirus evidence. | Deferred; PyInstaller already satisfies the no-Python goal |

No Electron or Tauri runtime is used. No multi-engine antivirus scan, signing,
installer UX, or complete third-party notice/SBOM assembly was performed in this
local candidate work. Those are release gates, not reasons to weaken the tested
local delivery path; publishing remains separately authorized.

## Scope and integration

Ship consumes the merged public CLI, package-data declaration, and `0.10.0`
content contract. This follow-up does not modify `src/lore2mud/cli.py` or
`pyproject.toml`. Any later CLI, Web-resource, application-version, or content
change requires rebuilding and rerunning the complete candidate verifier.

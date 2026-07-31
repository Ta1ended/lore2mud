# Windows candidate delivery

This directory owns the local Windows delivery path for the public
`original_demo`. It does not publish releases and does not package private or
generated content.

## Player workflow

1. Install 64-bit Python 3.11 or newer from `python.org`. During installation,
   enable the Python launcher or add Python to `PATH`.
2. Extract the complete candidate ZIP to a normal local folder.
3. Double-click `Start Lore2MUD.cmd`.

The launcher finds Python, checks its version, loads `lore2mud.pyz`, and starts
the bundled original demo. The current working directory is irrelevant, so a
shortcut or a folder with spaces is supported.

Run the following from `cmd.exe` for an environment and content-pack check:

```bat
"Start Lore2MUD.cmd" --diagnose
```

The diagnostic reports the bundle version, Python executable and version,
bundle/content paths, and user data/save paths. It also validates the bundled
content without starting a game.

### User data

Runtime content remains read-only in the extracted bundle. Mutable data uses:

```text
%LOCALAPPDATA%\lore2mud\
└── saves\
    └── content-<content-pack-version>\
```

Set `LORE2MUD_DATA_DIR` to an absolute path before launch to use a portable or
managed data location. The launcher creates the directory when needed. It does
not write saves beside the application.

Save formats are coupled to the content-pack version. The launcher isolates
each version under `saves/content-<version>` and never migrates or overwrites
older saves. JSON saves found directly under the legacy `saves` directory
produce a warning. Before deleting or replacing any old bundle, back up the
complete `%LOCALAPPDATA%\lore2mud` data directory. A newer content pack may
explicitly reject an older save; that rejection is compatibility protection,
not a recoverable launcher error.
Other `content-*` save directories are also reported and left untouched; the
launcher never silently selects an older version's saves.

For a non-standard interpreter, set `LORE2MUD_PYTHON` to the full path of a
Python 3.11+ executable. Otherwise the launcher tries `py.exe -3`, then
`python.exe`.

## Maintainer workflow

A clean Git worktree is required for a candidate intended for handoff:

```powershell
python packaging/windows/build_candidate.py
$candidate = (Get-ChildItem dist/windows/lore2mud-windows-*.zip).FullName
python packaging/windows/verify_candidate.py $candidate
```

The equivalent double-click helpers are `build_candidate.cmd` and
`verify_candidate.cmd`. `--allow-dirty` exists only for local development.

The build writes:

```text
dist/windows/lore2mud-windows-<app-version>-content-<pack-version>.zip
dist/windows/lore2mud-windows-<app-version>-content-<pack-version>.zip.sha256
```

The builder uses a strict Git-tracked source whitelist, sorted entries, fixed ZIP
timestamps, and normalized metadata. Two builds from the same commit are
byte-identical. `bundle.json` records provenance and the SHA-256 of every
runtime file. The verifier checks the optional outer sidecar, rejects duplicate
or traversing ZIP paths and links, verifies every manifest hash, extracts to a
repository-external temporary directory, runs diagnostics through the real
`.cmd` entry, then starts the game and sends `quit` over standard input.
It also requires the candidate filename, `bundle.json` and
`original_demo/pack.json` to agree on both application and content versions.

No network access is needed to build, verify, or run after Python is installed.
The candidate is local only; creating or uploading a release remains a
separate explicitly authorized action.

## Runtime choice

| Option | Typical compressed size | Offline behavior | License and maintenance impact | Decision |
| --- | ---: | --- | --- | --- |
| Standard-library zipapp | Measured 52,963-byte ZIP / 65,740 bytes unpacked | Fully offline after Python 3.11+ is installed | No new build dependency; Python runtime remains the user's responsibility | Implemented lightweight fallback |
| CPython embeddable package | Roughly 10-20 MB before project files | Can run on a machine without Python | Must redistribute the PSF/runtime notices and promptly service runtime security updates; launcher/import setup is Windows-specific | Deferred until a no-prerequisite runtime is explicitly required |
| PyInstaller one-folder | Measured 8,450,392-byte ZIP / 22,261,399 bytes unpacked | Can run on a machine without Python | Adds PyInstaller plus build-time packages, bundles CPython and a bootloader, requires third-party notices, per-Python rebuilds, antivirus/signing checks, and resource-hook maintenance | Preferred final integration direction; console probe validated |

The zipapp tradeoff is explicit: a user does not need the source tree or an
editable install, but does need a supported Python runtime. The diagnostic
fails with a concrete installation message when that prerequisite is absent.

### PyInstaller probe evidence (2026-07-31)

The alternative was tested rather than rejected on estimates. A temporary,
uncommitted tool environment used Python 3.12.13, PyInstaller 6.21.0 and hooks
2026.6 on Windows 11 x64. Installing it required seven distributions and a
package-index connection; the first fetch took about 102 seconds and resumed
once after a timeout. No package was added to `pyproject.toml`.

The probe used `--onedir --console --noupx` and the dedicated
`assets/Start Lore2MUD PyInstaller Probe.cmd`. With Python removed from `PATH`,
the repository-external candidate passed launcher diagnostics, content
validation, `play`/`quit`, and the external save-directory assertion. The
measured bundle contained 65 files, including the original demo and launcher:

| Measurement | zipapp candidate | PyInstaller probe |
| --- | ---: | ---: |
| Compressed candidate | 52,963 bytes | 8,450,392 bytes |
| Unpacked candidate | 65,740 bytes | 22,261,399 bytes |
| File count | 13 | 65 |
| Installed Python needed | Yes, 3.11+ | No |

The PyInstaller probe was about 160 times larger compressed and 339 times
larger unpacked. Two default builds differed in `lore2mud.exe` and
`_internal/base_library.zip`. Two controlled builds were identical for all
55 generated runtime files after fixing both variables below:

```powershell
$env:SOURCE_DATE_EPOCH = '1704067200'
$env:PYTHONHASHSEED = '0'
python -m PyInstaller --noconfirm --clean --onedir --console --noupx `
  --name lore2mud --paths src src/lore2mud/__main__.py
```

This proves that PyInstaller is viable for the centrally selected "no installed
Python" final direction. Adopting it still requires a pinned build-tool
lock, a license/notices or SBOM step for CPython, the PyInstaller bootloader and
bundled third-party components, the two reproducibility variables, and a
release signing/antivirus gate. PyInstaller's bootloader license has a special
distribution exception, but that does not remove notice obligations for the
bundled runtime and other components.

No multi-engine antivirus scan or code-signing reputation test was performed.
The unsigned bootloader can attract heuristic false positives, especially in
one-file mode; one-folder avoids self-extraction but does not eliminate that
risk. The current zipapp is transparent and much smaller, while an official
embeddable CPython layout would have a wider runtime patch/notices surface but
less custom bootloader behavior. The successful probe makes PyInstaller the
preferred final integration direction despite those costs; this branch keeps
the deterministic zipapp as the working fallback until the integration gates
below can be exercised.

## Scope and integration

The build consumes the version and existing CLI contract read-only. It does
not change `pyproject.toml` or `src/lore2mud/cli.py`; those are shared entry
points owned by other workstreams. If their version or command surface changes,
rebuild and rerun the verifier before integration.

The zipapp builder includes Python plus HTML, CSS and JavaScript resources
under `src/lore2mud`, so the active Player branch's `importlib.resources`-based
Web assets can survive a future integration. SVG is accepted only as a generic
future-compatible resource type; the active Player branch does not require or
reference an SVG. This branch's current baseline has no Web CLI or static
assets, and its one-click entry remains the console fallback. Do not label this
console-only candidate as the final integrated Windows candidate.
Final Ship closure requires merging the Player Web entry and Core content
update, switching the ordinary-user default to Web, verifying packaged
HTML/CSS/JS responses in a real browser, and rerunning cold-start plus save
compatibility checks against that integrated commit.

For the PyInstaller final candidate, package-data declarations alone are not
sufficient evidence. The integrated build must explicitly collect lore2mud
data (for example with `--collect-data lore2mud` or a reviewed equivalent hook)
and acceptance must request the packaged HTML, CSS and JavaScript through the
running executable. The current PyInstaller result validates only the console
runtime because this baseline predates the Player Web resources.

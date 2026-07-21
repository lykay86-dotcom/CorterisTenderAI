# RM-154 Render Technology Decision

Decision: use test-only Qt widget rendering into an opaque `QImage`, normalize and
compare with Pillow, and govern the environment with a fail-closed fingerprint.

## Constraints

- Windows is the supported desktop platform and CI already runs offscreen Qt.
- Product owners and theme tokens must render unchanged.
- No network, database, keyring, user settings, live AI, or screen capture is allowed.
- No new runtime dependency or production renderer is justified.
- Goldens must be reviewable, small, deterministic, and excluded from the executable.
- Strict offscreen evidence cannot stand in for RM-152 native evidence.

## Options considered

### `QWidget.render` to `QImage.Format_RGB32` — selected

This renders the real widget hierarchy and theme styles through Qt's raster path
without desktop compositing. RGB32 is opaque and avoids alpha-channel ambiguity.
Pillow 12.3.0 is already pinned and supplies deterministic RGB normalization, image
dimensions, difference statistics, and diff/overlay artifacts.

Three fresh-process-equivalent widget constructions per route/theme case were
byte-identical during characterization after explicit font registration. The
selected PySide6 call is:

```python
image = QImage(widget.size(), QImage.Format.Format_RGB32)
image.fill(0)
widget.render(image, QPoint())
```

The harness will not use `QRawFont.fromFont`; it can block on an unavailable family
in the offscreen plugin and does not prove which file supplied the glyphs.

### `QScreen.grabWindow` or desktop screenshots — rejected

These paths depend on compositor state, native chrome, window placement, display
topology, scaling, focus, and other applications. They are useful manual evidence,
not a strict CI golden source.

### Qt ARGB/premultiplied image — rejected

Characterization produced transparent-alpha images whose RGB channels differed
between themes. That representation is easy to compare incorrectly and is not a
canonical baseline format.

### Browser, external screenshot service, or image-snapshot plugin — rejected

The application is Qt Widgets, not HTML. An external service adds transport,
privacy, version, and availability risk without exercising the production widget
tree.

### Perceptual/AI image comparison — rejected for the gate

It is nondeterministic or too permissive for token and layout changes. Human review
may inspect produced artifacts, but accepted status is determined by the versioned
numeric policy only.

## Canonical renderer profile

The canonical profile is a structured manifest, not an informal machine label. It
contains at least:

- schema and renderer versions;
- Windows platform/release/build and CI image label;
- Python, PySide6, Qt, Pillow, and zlib versions;
- Qt platform plugin and style;
- locale, timezone, layout direction, and fixed clock;
- logical DPI, device-pixel ratio, color depth, and viewport;
- theme and design-system version;
- registered font filenames, sizes, SHA-256 hashes, and Qt family names;
- icon manifest hash and relevant asset hashes;
- case-fixture schema and comparison-policy versions.

Canonical pixel comparison runs on the Windows Python 3.12 quality-gate leg. The
Python 3.13 leg runs the renderer-policy, schema, privacy, catalog, and comparator
tests but cannot silently bless different pixels.

The initial canonical fingerprint is learned only from an explicit candidate run on
that CI leg and is committed with reviewed goldens. Subsequent comparison requires
an exact fingerprint match. Missing fonts, changed font hashes, backend/style drift,
or dependency drift produce a typed `ENVIRONMENT_MISMATCH` block and diagnostic
manifest. They never fall through to a pixel pass.

## Font policy

The harness registers these installed Windows filenames in this order:

1. `segoeui.ttf` (regular);
2. `seguisb.ttf` (semibold);
3. `segoeuib.ttf` (bold);
4. `consola.ttf` (code).

It records the bytes' SHA-256 before registration, verifies the returned Qt family,
and then checks that `Segoe UI` and `Consolas` are available. Files remain under the
operating system font directory. They are neither copied into the repository nor
bundled in PyInstaller.

## PNG normalization

Before hashing or comparison, every capture is converted to plain `RGB`, stripped of
text/time/ICC/EXIF metadata, encoded with fixed PNG options, and reopened to verify
mode and dimensions. The canonical hash is over the normalized PNG bytes. A second
pixel hash over `width || height || RGB bytes` helps distinguish encoder drift from
visual drift.

## Decision consequences

- The exact baseline is intentionally platform/profile-specific.
- Environment changes require a reviewed renderer-profile and golden update.
- Broad cross-platform tolerances are unnecessary and prohibited initially.
- Existing semantic/accessibility/state tests remain mandatory because a pixel can
  be stable while behavior or accessibility is wrong.
- Review and failure artifacts are test outputs only and do not affect the frozen
  application package.


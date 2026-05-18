# Changelog

All notable changes to Amni-Prism are documented here.

## 0.1.1 — 2026-05-17

- Polish pass: README rewrites for PyPI users (install from `pip install amni-prism`, badges, alpha status banner, "why use this" section, source-allowlist callout).
- pyproject metadata: Development Status, Python 3.9–3.13 classifiers, Source/Changelog URLs, expanded keywords.
- `prism/__init__.py` bumped to 0.1.1.
- `prism.scrape.ALLOWED_SOURCES`: added HuggingFace under `ODC-BY-1.0`.

## 0.1.0 — 2026-05-17

- First PyPI release. Unblocks Amni-Ai `[all]` and `[federated]` install extras.
- Fixed `pyproject.toml` build-backend (was an invalid `setuptools.backends._legacy:_Backend`).
- Fixed Homepage URL (was `anmire/Amni-Prism`).
- GF(17) nonce-addressed knowledge atlas, PTEX storage, NDJSON manifests, two-tier propose/verify flow, 25 domains, 6-source scraping allowlist, full `prism` CLI.

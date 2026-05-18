# Amni-Prism

[![PyPI](https://img.shields.io/pypi/v/amni-prism.svg)](https://pypi.org/project/amni-prism/)
[![Python](https://img.shields.io/pypi/pyversions/amni-prism.svg)](https://pypi.org/project/amni-prism/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Shared knowledge atlas built on PRISM-TEX (.ptex). Every fact gets a unique nonce — contribute knowledge, it deduplicates automatically by content hash, and the atlas grows. NDJSON manifests are append-only and git-merge-friendly, so multiple contributors never collide.

Status: **alpha (0.1.x)**. API may shift before 1.0.

## Install

```bash
pip install amni-prism
```

For local development:

```bash
git clone https://github.com/Amnibro/Amni-Prism
cd Amni-Prism
pip install -e .
```

## Quick Start

```python
import prism

prism.contribute_text('./codex', 'The speed of light is 299792458 m/s', domain='physics')

result = prism.query_text('./codex', 'The speed of light is 299792458 m/s')

hits = prism.search_keyword('./codex', 'speed of light')
```

## CLI

```bash
prism contribute "The speed of light is 299792458 m/s" -d physics

prism search "speed of light"

prism propose "Water boils at 100C at sea level" -d physics --confidence 0.8

prism pending
prism verify

prism scrape --file article.txt --source "https://en.wikipedia.org/wiki/Light"

prism stats
```

## How It Works

1. **Nonces** — Every word/line/block gets a unique nonce in finite-field space. Same content → same nonce → automatic dedup.
2. **PRISM-TEX Storage** — Knowledge stored as nonce-addressed maps. Vocab in NLX format, hierarchical tiers in HNA format.
3. **Content-Hash Dedup** — SHA-256 over normalized content ensures no duplicates across contributors merging different codexes.
4. **Two-Tier Verification** — Small models propose (~50 tokens), large models verify (~20 tokens). ~70 tokens per verified fact.
5. **NDJSON Manifests** — Append-only JSON-lines manifests are git-merge-friendly. No merge conflicts when two contributors add facts to the same domain.

## Domains

25 built-in domains: code, math, science, history, language, music, art, philosophy, psychology, economics, politics, law, medicine, engineering, technology, education, sports, entertainment, food, travel, nature, religion, mythology, literature, general.

## Why use this

- **Knowledge that survives model swaps.** The atlas is a pile of facts addressed by content, not a fine-tune of a specific model. Swap your LLM tomorrow, keep your atlas.
- **Federation without coordination.** Two contributors building independent codexes can `prism merge` their work and get a deduplicated union, with no central server.
- **Built for the Adam runtime.** Amni-Prism is the federated layer of [Amni-Ai (Adam)](https://github.com/Amnibro/Amni-Ai). The `[federated]` extra in Adam pulls this in directly.

## Source Allowlist

Scraping is gated to license-compatible sources (Wikipedia, arXiv, RFC, Python docs, MDN, HuggingFace). See `prism.scrape.ALLOWED_SOURCES`.

## Contributing

Fork, clone, `pip install -e .`, add facts via the CLI or Python API, and open a PR with your codex export. NDJSON manifests merge cleanly under git.

## License

MIT — see [LICENSE](LICENSE).

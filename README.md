# Amni-Prism

Shared knowledge atlas built on PTEX. Every fact gets a unique nonce — contribute knowledge, it deduplicates automatically, and the atlas grows.

## Install

```bash
pip install -e .
```

## Quick Start

```python
import prism

# Contribute knowledge
prism.contribute_text('./codex', 'The speed of light is 299792458 m/s', domain='physics')

# Query it back
result = prism.query_text('./codex', 'The speed of light is 299792458 m/s')

# Search by keyword
hits = prism.search_keyword('./codex', 'speed of light')
```

## CLI

```bash
# Contribute text
prism contribute "The speed of light is 299792458 m/s" -d physics

# Search
prism search "speed of light"

# Small model proposes a fact
prism propose "Water boils at 100C at sea level" -d physics --confidence 0.8

# Large model verifies pending proposals
prism pending
prism verify

# Scrape text for facts
prism scrape --file article.txt --source "https://en.wikipedia.org/wiki/Light"

# Stats
prism stats
```

## How It Works

1. **Nonces** — Every word/line/block gets a unique nonce in finite field space. Same content = same nonce = automatic dedup.
2. **PTEX Storage** — Knowledge stored as nonce-addressed maps. Vocab in NLX format, hierarchical tiers in HNA format.
3. **Content-Hash Dedup** — SHA-256 content hashing ensures no duplicates across contributors.
4. **Two-Tier Verification** — Small models propose (~50 tokens), large models verify (~20 tokens). ~70 tokens per verified fact.
5. **NDJSON Manifests** — Append-only JSON-lines manifests are git-merge-friendly. No merge conflicts.

## Contributing

```bash
# Fork, clone, then:
pip install -e .
prism contribute "Your knowledge here" -d general
# Or pipe from stdin:
cat facts.txt | prism contribute -d science
```

## Domains

25 built-in domains: code, math, science, history, language, music, art, philosophy, psychology, economics, politics, law, medicine, engineering, technology, education, sports, entertainment, food, travel, nature, religion, mythology, literature, general.

## License

MIT

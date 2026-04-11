"""Seed Amni-Prism codex from existing Amni-Ai atlas output."""
import sys, os, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from prism.contribute import contribute_text
from prism.codec import _detect_domain, DOMAIN_NAMES
def seed_from_directory(source_dir: str, codex_dir: str, extensions: tuple = ('.py', '.txt', '.md', '.json')):
    source = Path(source_dir)
    if not source.exists():
        print(f"Source not found: {source_dir}")
        return
    files = []
    for ext in extensions:
        files.extend(source.rglob(f'*{ext}'))
    added, duped, errors = 0, 0, 0
    for f in sorted(files):
        try:
            text = f.read_text(encoding='utf-8', errors='ignore')
            if len(text.strip()) < 10: continue
            did = _detect_domain(text, str(f))
            domain = DOMAIN_NAMES.get(did, 'general')
            r = contribute_text(codex_dir, text, domain, 'seed-script', str(f))
            if r['status'] == 'added':
                added += 1
                print(f"  + {f.name} -> {domain}")
            elif r['status'] == 'duplicate':
                duped += 1
            else:
                errors += 1
        except Exception as e:
            errors += 1
            print(f"  ! {f.name}: {e}")
    print(f"\nSeeded: {added} added, {duped} dupes, {errors} errors")
def seed_from_atlas(atlas_dir: str, codex_dir: str):
    atlas = Path(atlas_dir)
    manifest = atlas / 'manifest.json'
    if manifest.exists():
        data = json.loads(manifest.read_text(encoding='utf-8'))
        print(f"Atlas: {data.get('files_processed', '?')} files, {data.get('vocab_size', '?')} vocab")
    seed_from_directory(atlas_dir, codex_dir)
if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description='Seed Prism codex from existing data')
    p.add_argument('source', help='Source directory (atlas_output or any text dir)')
    p.add_argument('--codex', '-c', default='./codex', help='Target codex directory')
    args = p.parse_args()
    seed_from_atlas(args.source, args.codex)

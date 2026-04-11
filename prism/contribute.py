import json, hashlib, time, os
from typing import Dict, Optional, List
from pathlib import Path
from .gf17 import content_hash, word_to_hash_vector
from .codec import (HierarchicalCodec, NonceLexCodec, DOMAIN_MAP, DOMAIN_NAMES,
    N_DOMAINS, _detect_domain)
from .ptex import save_atlas, load_atlas
def _contributor_hash(contributor_id: str) -> str:
    return hashlib.sha256(contributor_id.encode()).hexdigest()[:16]
def _append_ndjson(path: str, entry: Dict):
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, default=str) + '\n')
def _load_ndjson(path: str) -> List[Dict]:
    if not os.path.exists(path): return []
    entries = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try: entries.append(json.loads(line))
                except json.JSONDecodeError: pass
    return entries
def contribute_text(codex_dir: str, text: str, domain: str = 'general',
                    contributor_id: str = 'anonymous', source: str = '',
                    confidence: float = 1.0, verified: bool = True) -> Dict:
    codex = Path(codex_dir)
    codex.mkdir(parents=True, exist_ok=True)
    manifest_path = str(codex / 'manifest.ndjson')
    ch = content_hash(text)
    existing = _load_ndjson(manifest_path)
    for e in existing:
        if e.get('content_hash') == ch:
            return {'status': 'duplicate', 'nonce': e.get('nonce_id'), 'hash': ch}
    did = DOMAIN_MAP.get(domain.lower(), 0) if isinstance(domain, str) else int(domain)
    dname = DOMAIN_NAMES.get(did, 'general')
    domain_dir = codex / dname
    domain_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    nonce_id = ch & 0xFFFFFFFF
    entry = {
        'nonce_id': nonce_id,
        'content_hash': ch,
        'domain': dname,
        'domain_id': did,
        'contributor': _contributor_hash(contributor_id),
        'source': source,
        'confidence': confidence,
        'verified': verified,
        'timestamp': ts,
        'length': len(text),
        'preview': text[:100].replace('\n', ' ')
    }
    text_path = domain_dir / f"{nonce_id:08x}_{ts}.txt"
    text_path.write_text(text, encoding='utf-8')
    entry['file'] = str(text_path.relative_to(codex))
    _append_ndjson(manifest_path, entry)
    return {'status': 'added', 'nonce': nonce_id, 'hash': ch, 'domain': dname,
            'file': str(text_path)}
def contribute_fact(codex_dir: str, fact: str, domain: str = 'general',
                    contributor_id: str = 'anonymous', source: str = '',
                    confidence: float = 1.0) -> Dict:
    return contribute_text(codex_dir, fact, domain, contributor_id, source,
                          confidence, verified=(confidence >= 0.9))
def contribute_code(codex_dir: str, code: str, filepath: str = '',
                    contributor_id: str = 'anonymous') -> Dict:
    domain = 'code'
    if filepath:
        det = _detect_domain(code, filepath)
        domain = DOMAIN_NAMES.get(det, 'code')
    return contribute_text(codex_dir, code, domain, contributor_id,
                          source=filepath, confidence=1.0, verified=True)
def stage_contribution(codex_dir: str, text: str, domain: str = 'general',
                       contributor_id: str = 'anonymous', source: str = '',
                       confidence: float = 0.5) -> Dict:
    staging = Path(codex_dir) / '.staging'
    staging.mkdir(parents=True, exist_ok=True)
    return contribute_text(str(staging), text, domain, contributor_id,
                          source, confidence, verified=False)
def promote_staged(codex_dir: str, nonce_id: int) -> Dict:
    staging = Path(codex_dir) / '.staging'
    staging_manifest = str(staging / 'manifest.ndjson')
    entries = _load_ndjson(staging_manifest)
    target = None
    for e in entries:
        if e.get('nonce_id') == nonce_id:
            target = e
            break
    if not target: return {'status': 'not_found', 'nonce': nonce_id}
    src_file = staging / target['file']
    if not src_file.exists(): return {'status': 'file_missing', 'nonce': nonce_id}
    text = src_file.read_text(encoding='utf-8')
    result = contribute_text(codex_dir, text, target['domain'],
                            target.get('contributor', 'anonymous'),
                            target.get('source', ''), 1.0, verified=True)
    src_file.unlink()
    remaining = [e for e in entries if e.get('nonce_id') != nonce_id]
    with open(staging_manifest, 'w', encoding='utf-8') as f:
        for e in remaining: f.write(json.dumps(e, default=str) + '\n')
    return {**result, 'promoted': True}
def merge_codexes(target_dir: str, source_dirs: List[str]) -> Dict:
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    target_manifest = str(target / 'manifest.ndjson')
    existing = _load_ndjson(target_manifest)
    existing_hashes = {e.get('content_hash') for e in existing}
    added, skipped = 0, 0
    for src_dir in source_dirs:
        src = Path(src_dir)
        src_entries = _load_ndjson(str(src / 'manifest.ndjson'))
        for entry in src_entries:
            ch = entry.get('content_hash')
            if ch in existing_hashes:
                skipped += 1
                continue
            src_file = src / entry.get('file', '')
            if src_file.exists():
                dname = entry.get('domain', 'general')
                dst_domain = target / dname
                dst_domain.mkdir(parents=True, exist_ok=True)
                dst_file = dst_domain / src_file.name
                dst_file.write_bytes(src_file.read_bytes())
                entry['file'] = str(dst_file.relative_to(target))
            _append_ndjson(target_manifest, entry)
            existing_hashes.add(ch)
            added += 1
    return {'added': added, 'skipped': skipped, 'total': len(existing) + added}
def list_contributions(codex_dir: str, domain: Optional[str] = None) -> List[Dict]:
    entries = _load_ndjson(str(Path(codex_dir) / 'manifest.ndjson'))
    if domain: entries = [e for e in entries if e.get('domain') == domain.lower()]
    return entries
def stats(codex_dir: str) -> Dict:
    entries = _load_ndjson(str(Path(codex_dir) / 'manifest.ndjson'))
    domains = {}
    for e in entries:
        d = e.get('domain', 'general')
        domains[d] = domains.get(d, 0) + 1
    verified = sum(1 for e in entries if e.get('verified', False))
    staged_path = Path(codex_dir) / '.staging' / 'manifest.ndjson'
    staged = len(_load_ndjson(str(staged_path))) if staged_path.exists() else 0
    return {'total': len(entries), 'verified': verified, 'staged': staged,
            'domains': domains, 'contributors': len(set(e.get('contributor', '') for e in entries))}

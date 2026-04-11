import os
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from .gf17 import content_hash, word_to_hash_vector
from .codec import NonceLexCodec, HierarchicalCodec, DOMAIN_NAMES
from .contribute import _load_ndjson
def query_text(codex_dir: str, text: str) -> Dict:
    ch = content_hash(text)
    entries = _load_ndjson(str(Path(codex_dir) / 'manifest.ndjson'))
    matches = [e for e in entries if e.get('content_hash') == ch]
    return {'found': len(matches) > 0, 'matches': matches, 'hash': ch}
def query_nonce(codex_dir: str, nonce_id: int) -> Dict:
    entries = _load_ndjson(str(Path(codex_dir) / 'manifest.ndjson'))
    matches = [e for e in entries if e.get('nonce_id') == nonce_id]
    results = []
    for m in matches:
        fpath = Path(codex_dir) / m.get('file', '')
        content = fpath.read_text(encoding='utf-8') if fpath.exists() else None
        results.append({**m, 'content': content})
    return {'found': len(results) > 0, 'results': results}
def search_domain(codex_dir: str, domain: str, limit: int = 50) -> List[Dict]:
    entries = _load_ndjson(str(Path(codex_dir) / 'manifest.ndjson'))
    matches = [e for e in entries if e.get('domain') == domain.lower()]
    return sorted(matches, key=lambda x: x.get('timestamp', 0), reverse=True)[:limit]
def search_keyword(codex_dir: str, keyword: str, limit: int = 20) -> List[Dict]:
    entries = _load_ndjson(str(Path(codex_dir) / 'manifest.ndjson'))
    kw = keyword.lower()
    results = []
    for e in entries:
        if kw in e.get('preview', '').lower():
            results.append(e)
        elif len(results) < limit:
            fpath = Path(codex_dir) / e.get('file', '')
            if fpath.exists():
                content = fpath.read_text(encoding='utf-8').lower()
                if kw in content: results.append({**e, '_matched': True})
        if len(results) >= limit: break
    return results
def retrieve(codex_dir: str, nonce_id: int) -> Optional[str]:
    result = query_nonce(codex_dir, nonce_id)
    if not result['found']: return None
    return result['results'][0].get('content')
def retrieve_batch(codex_dir: str, nonce_ids: List[int]) -> Dict[int, Optional[str]]:
    return {nid: retrieve(codex_dir, nid) for nid in nonce_ids}
def find_similar(codex_dir: str, text: str, threshold: float = 0.8,
                 limit: int = 10) -> List[Dict]:
    import numpy as np
    query_vec = word_to_hash_vector(text)
    entries = _load_ndjson(str(Path(codex_dir) / 'manifest.ndjson'))
    scored = []
    for e in entries:
        preview = e.get('preview', '')
        if not preview: continue
        entry_vec = word_to_hash_vector(preview)
        sim = float(np.dot(query_vec, entry_vec) /
                   (np.linalg.norm(query_vec) * np.linalg.norm(entry_vec) + 1e-10))
        if sim >= threshold: scored.append({**e, '_similarity': round(sim, 4)})
    scored.sort(key=lambda x: x['_similarity'], reverse=True)
    return scored[:limit]
def list_domains(codex_dir: str) -> Dict[str, int]:
    entries = _load_ndjson(str(Path(codex_dir) / 'manifest.ndjson'))
    domains = {}
    for e in entries:
        d = e.get('domain', 'general')
        domains[d] = domains.get(d, 0) + 1
    return dict(sorted(domains.items(), key=lambda x: x[1], reverse=True))
def export_domain(codex_dir: str, domain: str, output_path: str) -> Dict:
    entries = search_domain(codex_dir, domain, limit=999999)
    texts = []
    for e in entries:
        fpath = Path(codex_dir) / e.get('file', '')
        if fpath.exists(): texts.append(fpath.read_text(encoding='utf-8'))
    Path(output_path).write_text('\n---\n'.join(texts), encoding='utf-8')
    return {'domain': domain, 'entries': len(texts), 'output': output_path}

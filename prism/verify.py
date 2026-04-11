import json, time, os
from typing import Dict, List, Optional
from pathlib import Path
from .contribute import _load_ndjson, _append_ndjson, contribute_text, _contributor_hash
from .gf17 import content_hash
CONFIDENCE_THRESHOLD = 0.7
VERIFY_APPROVE = 'approved'
VERIFY_REJECT = 'rejected'
VERIFY_REFINE = 'refined'
def propose(codex_dir: str, text: str, domain: str = 'general',
            contributor_id: str = 'small-model', source: str = '',
            confidence: float = 0.7, model_name: str = '') -> Dict:
    if confidence < CONFIDENCE_THRESHOLD:
        return {'status': 'below_threshold', 'confidence': confidence,
                'threshold': CONFIDENCE_THRESHOLD}
    staging = Path(codex_dir) / '.staging'
    staging.mkdir(parents=True, exist_ok=True)
    ch = content_hash(text)
    existing = _load_ndjson(str(Path(codex_dir) / 'manifest.ndjson'))
    for e in existing:
        if e.get('content_hash') == ch:
            return {'status': 'already_exists', 'nonce': e.get('nonce_id'), 'hash': ch}
    manifest = str(staging / 'proposals.ndjson')
    proposals = _load_ndjson(manifest)
    for p in proposals:
        if p.get('content_hash') == ch:
            return {'status': 'already_proposed', 'hash': ch}
    ts = int(time.time())
    nonce_id = ch & 0xFFFFFFFF
    proposal = {
        'nonce_id': nonce_id,
        'content_hash': ch,
        'domain': domain.lower(),
        'text': text,
        'contributor': _contributor_hash(contributor_id),
        'source': source,
        'confidence': confidence,
        'model': model_name,
        'timestamp': ts,
        'status': 'pending'
    }
    _append_ndjson(manifest, proposal)
    return {'status': 'proposed', 'nonce': nonce_id, 'hash': ch}
def get_pending(codex_dir: str, limit: int = 100,
                domain: Optional[str] = None) -> List[Dict]:
    staging = Path(codex_dir) / '.staging'
    proposals = _load_ndjson(str(staging / 'proposals.ndjson'))
    pending = [p for p in proposals if p.get('status') == 'pending']
    if domain: pending = [p for p in pending if p.get('domain') == domain.lower()]
    return sorted(pending, key=lambda x: x.get('confidence', 0), reverse=True)[:limit]
def verify(codex_dir: str, content_hash_val: int, verdict: str,
           verifier_id: str = 'large-model', refined_text: str = '',
           model_name: str = '') -> Dict:
    staging = Path(codex_dir) / '.staging'
    proposals_path = str(staging / 'proposals.ndjson')
    proposals = _load_ndjson(proposals_path)
    target = None
    target_idx = -1
    for i, p in enumerate(proposals):
        if p.get('content_hash') == content_hash_val:
            target = p
            target_idx = i
            break
    if not target: return {'status': 'not_found', 'hash': content_hash_val}
    ts = int(time.time())
    verdict_entry = {
        'content_hash': content_hash_val,
        'verdict': verdict,
        'verifier': _contributor_hash(verifier_id),
        'model': model_name,
        'timestamp': ts
    }
    _append_ndjson(str(staging / 'verdicts.ndjson'), verdict_entry)
    if verdict == VERIFY_APPROVE:
        text = target['text']
        result = contribute_text(codex_dir, text, target.get('domain', 'general'),
                                target.get('contributor', 'anonymous'),
                                target.get('source', ''), 1.0, verified=True)
        target['status'] = 'approved'
    elif verdict == VERIFY_REFINE and refined_text:
        result = contribute_text(codex_dir, refined_text, target.get('domain', 'general'),
                                target.get('contributor', 'anonymous'),
                                target.get('source', ''), 1.0, verified=True)
        target['status'] = 'refined'
    elif verdict == VERIFY_REJECT:
        target['status'] = 'rejected'
        result = {'status': 'rejected'}
    else:
        return {'status': 'invalid_verdict', 'verdict': verdict}
    proposals[target_idx] = target
    with open(proposals_path, 'w', encoding='utf-8') as f:
        for p in proposals: f.write(json.dumps(p, default=str) + '\n')
    return {**result, 'verdict': verdict}
def batch_verify(codex_dir: str, verdicts: List[Dict],
                 verifier_id: str = 'large-model', model_name: str = '') -> Dict:
    results = {'approved': 0, 'rejected': 0, 'refined': 0, 'errors': 0}
    for v in verdicts:
        ch = v.get('content_hash') or v.get('hash')
        vrd = v.get('verdict', VERIFY_REJECT)
        refined = v.get('refined_text', '')
        r = verify(codex_dir, ch, vrd, verifier_id, refined, model_name)
        if r.get('status') == 'not_found' or r.get('status') == 'invalid_verdict':
            results['errors'] += 1
        elif vrd == VERIFY_APPROVE: results['approved'] += 1
        elif vrd == VERIFY_REJECT: results['rejected'] += 1
        elif vrd == VERIFY_REFINE: results['refined'] += 1
    return results
def format_for_verification(proposals: List[Dict]) -> str:
    lines = []
    for i, p in enumerate(proposals):
        lines.append(f"[{i}] domain={p.get('domain','?')} conf={p.get('confidence',0):.2f}")
        lines.append(f"    {p.get('text', '')[:200]}")
        lines.append(f"    hash={p.get('content_hash')}")
    return '\n'.join(lines)
def parse_verification_response(response: str, proposals: List[Dict]) -> List[Dict]:
    verdicts = []
    for line in response.strip().split('\n'):
        line = line.strip()
        if not line: continue
        parts = line.split(maxsplit=2)
        if len(parts) < 2: continue
        try:
            idx = int(parts[0].strip('[]'))
            verdict = parts[1].lower()
            if verdict not in (VERIFY_APPROVE, VERIFY_REJECT, VERIFY_REFINE): continue
            entry = {'content_hash': proposals[idx].get('content_hash'), 'verdict': verdict}
            if verdict == VERIFY_REFINE and len(parts) > 2: entry['refined_text'] = parts[2]
            verdicts.append(entry)
        except (ValueError, IndexError): pass
    return verdicts
def verification_stats(codex_dir: str) -> Dict:
    staging = Path(codex_dir) / '.staging'
    proposals = _load_ndjson(str(staging / 'proposals.ndjson'))
    verdicts = _load_ndjson(str(staging / 'verdicts.ndjson'))
    pending = sum(1 for p in proposals if p.get('status') == 'pending')
    approved = sum(1 for p in proposals if p.get('status') == 'approved')
    rejected = sum(1 for p in proposals if p.get('status') == 'rejected')
    refined = sum(1 for p in proposals if p.get('status') == 'refined')
    return {'pending': pending, 'approved': approved, 'rejected': rejected,
            'refined': refined, 'total_verdicts': len(verdicts)}

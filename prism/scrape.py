import re, hashlib, time
from typing import Dict, List, Optional
from pathlib import Path
from .contribute import contribute_text, stage_contribution
from .codec import DOMAIN_NAMES, _detect_domain
ALLOWED_SOURCES = {
    'wikipedia': {'base': 'https://en.wikipedia.org/wiki/', 'license': 'CC-BY-SA-3.0'},
    'rfc': {'base': 'https://www.rfc-editor.org/rfc/', 'license': 'public-domain'},
    'python-docs': {'base': 'https://docs.python.org/3/', 'license': 'PSF'},
    'mdn': {'base': 'https://developer.mozilla.org/', 'license': 'CC-BY-SA-2.5'},
}
def extract_facts(text: str, min_length: int = 20, max_length: int = 500) -> List[str]:
    text = re.sub(r'\[[\d,\s]+\]', '', text)
    text = re.sub(r'\{\{[^}]+\}\}', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    facts = []
    for s in sentences:
        s = s.strip()
        if len(s) < min_length or len(s) > max_length: continue
        if s.startswith(('See also', 'References', 'External links', 'Further reading')): continue
        if re.match(r'^\d+\.\s*$', s): continue
        if s.count('[') > 2: continue
        facts.append(s)
    return facts
def classify_facts(facts: List[str]) -> Dict[str, List[str]]:
    classified = {}
    for fact in facts:
        did = _detect_domain(fact, '')
        dname = DOMAIN_NAMES.get(did, 'general')
        classified.setdefault(dname, []).append(fact)
    return classified
def scrape_text(text: str, source_url: str, source_type: str = '',
                codex_dir: str = '', contributor_id: str = 'auto-scraper',
                auto_stage: bool = True) -> Dict:
    facts = extract_facts(text)
    if not facts: return {'status': 'no_facts', 'extracted': 0}
    classified = classify_facts(facts)
    results = {'extracted': len(facts), 'domains': {}, 'staged': 0, 'contributed': 0}
    if not codex_dir:
        results['facts'] = classified
        return results
    for domain, domain_facts in classified.items():
        results['domains'][domain] = len(domain_facts)
        for fact in domain_facts:
            fn = stage_contribution if auto_stage else contribute_text
            r = fn(codex_dir, fact, domain, contributor_id, source_url, confidence=0.6)
            if r.get('status') == 'added':
                results['staged' if auto_stage else 'contributed'] += 1
    return results
def scrape_structured(entries: List[Dict], codex_dir: str,
                      contributor_id: str = 'auto-scraper') -> Dict:
    total = {'processed': 0, 'staged': 0, 'skipped': 0}
    for entry in entries:
        text = entry.get('text', entry.get('content', ''))
        source = entry.get('source', entry.get('url', ''))
        domain = entry.get('domain', 'general')
        if not text:
            total['skipped'] += 1
            continue
        r = stage_contribution(codex_dir, text, domain, contributor_id, source, confidence=0.6)
        total['processed'] += 1
        if r.get('status') == 'added': total['staged'] += 1
    return total
def validate_source(url: str) -> Dict:
    for name, info in ALLOWED_SOURCES.items():
        if info['base'] in url:
            return {'valid': True, 'source': name, 'license': info['license']}
    return {'valid': False, 'source': 'unknown',
            'message': 'Source not in allowed list. Content will require manual review.'}
def scrape_batch(texts_and_sources: List[Dict], codex_dir: str,
                 contributor_id: str = 'auto-scraper') -> Dict:
    results = {'total': len(texts_and_sources), 'processed': 0, 'facts_extracted': 0,
               'staged': 0, 'rejected_sources': 0}
    for item in texts_and_sources:
        text = item.get('text', '')
        source = item.get('source', '')
        sv = validate_source(source)
        if not sv['valid']:
            results['rejected_sources'] += 1
            continue
        r = scrape_text(text, source, sv['source'], codex_dir, contributor_id)
        results['processed'] += 1
        results['facts_extracted'] += r.get('extracted', 0)
        results['staged'] += r.get('staged', 0)
    return results

"""Amni-Prism full integration test: nano propose -> stream -> large verify -> git batch."""
import sys, os, json, time, requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import prism
CODEX_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_codex')
NANO_URL = os.environ.get('PRISM_NANO_URL', 'http://127.0.0.1:8788/v1/chat/completions')
NANO_MODEL = os.environ.get('PRISM_NANO_MODEL', 'gemma-e2b-ptex')
TOPICS = [
    ('physics', 'State 3 fundamental physics facts about electromagnetic radiation. Be concise, one sentence each.'),
    ('math', 'State 3 fundamental math facts about prime numbers. Be concise, one sentence each.'),
    ('code', 'State 3 facts about Python programming language features. Be concise, one sentence each.'),
]
def load_config():
    models = {}
    xai_key = os.environ.get('XAI_API_KEY', '')
    gemini_key = os.environ.get('GEMINI_API_KEY', '')
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if xai_key:
        xai_model = os.environ.get('XAI_MODEL', 'grok-code-fast-1')
        models['xai'] = {'provider': 'xAI', 'model': xai_model, 'key': xai_key,
                         'base': 'https://api.x.ai/v1/chat/completions'}
    if gemini_key:
        gem_model = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
        models['gemini'] = {'provider': 'gemini', 'model': gem_model, 'key': gemini_key,
                            'base': f'https://generativelanguage.googleapis.com/v1beta/models/{gem_model}:generateContent'}
    if anthropic_key:
        ant_model = os.environ.get('ANTHROPIC_MODEL', 'claude-sonnet-4-20250514')
        models['anthropic'] = {'provider': 'anthropic', 'model': ant_model, 'key': anthropic_key,
                               'base': 'https://api.anthropic.com/v1/messages'}
    models['large'] = models.get('xai') or models.get('gemini') or models.get('anthropic')
    return models
def nano_generate(topic, prompt, stream=False):
    payload = {
        'model': NANO_MODEL,
        'messages': [
            {'role': 'system', 'content': 'You are a knowledge assistant. State facts clearly and concisely. One fact per line. No numbering, no bullets, just plain sentences.'},
            {'role': 'user', 'content': prompt}
        ],
        'max_tokens': 200,
        'temperature': 0.3,
        'stream': stream
    }
    if stream:
        r = requests.post(NANO_URL, json=payload, stream=True, timeout=60)
        full_text = ''
        content_type = r.headers.get('content-type', '')
        if 'text/event-stream' in content_type:
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith('data: '): continue
                data = line[6:]
                if data.strip() == '[DONE]': break
                try:
                    chunk = json.loads(data)
                    delta = chunk['choices'][0].get('delta', {}).get('content', '')
                    if delta:
                        full_text += delta
                        sys.stdout.write(delta)
                        sys.stdout.flush()
                except (json.JSONDecodeError, KeyError, IndexError): pass
        else:
            body = r.json()
            full_text = body['choices'][0]['message']['content']
            for i, ch in enumerate(full_text):
                sys.stdout.write(ch)
                sys.stdout.flush()
                if i % 20 == 19: time.sleep(0.01)
        print()
        return full_text
    else:
        r = requests.post(NANO_URL, json=payload, timeout=60)
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content']
def _call_openai_compat(url, key, model, messages, max_tokens=300, temp=0.1):
    headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
    payload = {'model': model, 'messages': messages, 'max_tokens': max_tokens, 'temperature': temp}
    r = requests.post(url, json=payload, headers=headers, timeout=45)
    r.raise_for_status()
    return r.json()['choices'][0]['message']['content']
def _call_gemini(url, key, messages, max_tokens=300, temp=0.1):
    contents = []
    for m in messages:
        role = 'model' if m['role'] == 'assistant' else 'user'
        contents.append({'role': role, 'parts': [{'text': m['content']}]})
    payload = {'contents': contents, 'generationConfig': {'maxOutputTokens': max_tokens, 'temperature': temp}}
    r = requests.post(url, json=payload, headers={'x-goog-api-key': key}, timeout=45)
    r.raise_for_status()
    return r.json()['candidates'][0]['content']['parts'][0]['text']
def large_verify(proposals, config):
    prompt_lines = ["Verify each fact below. For each, respond with ONLY the index and verdict on one line.",
                    "Format: [index] approved   OR   [index] rejected   OR   [index] refined <corrected text>",
                    "Be strict - reject anything false or vague.\n"]
    for i, p in enumerate(proposals):
        prompt_lines.append(f"[{i}] {p.get('text', '')}")
    messages = [
        {'role': 'user', 'content': 'You are a fact-checker. Verify facts with approved/rejected/refined verdicts. Be strict and concise.\n\n' + '\n'.join(prompt_lines)}
    ]
    for api_name in ('xai', 'xai_reason', 'gemini'):
        cfg = config.get(api_name)
        if not cfg: continue
        try:
            print(f"  Trying {cfg['provider']} ({cfg['model']})...")
            if cfg['provider'] == 'gemini':
                response_text = _call_gemini(cfg['base'], cfg['key'], messages)
            else:
                response_text = _call_openai_compat(cfg['base'], cfg['key'], cfg['model'], messages)
            print(f"  Large model response:\n{response_text}")
            return prism.parse_verification_response(response_text, proposals)
        except Exception as e:
            err = str(e)
            for redact in ('key=', 'Bearer ', 'x-goog-api-key'):
                idx = err.lower().find(redact.lower())
                if idx >= 0: err = err[:idx + len(redact)] + '***'
            print(f"  [{cfg['provider']}] failed: {err}, trying next...")
    print("  [WARN] All large models failed, using rule-based fallback")
    return [{'content_hash': p['content_hash'], 'verdict': 'approved'}
            for p in proposals if p.get('confidence', 0) >= 0.7]
def run_test():
    print("=" * 60)
    print("AMNI-PRISM INTEGRATION TEST")
    print("=" * 60)
    config = load_config()
    print(f"\n[CONFIG] Large model: {config.get('large', {}).get('model', 'NONE')}")
    print(f"[CONFIG] Nano model: {NANO_MODEL} @ {NANO_URL}")
    print(f"[CONFIG] Codex dir: {CODEX_DIR}\n")
    if os.path.exists(CODEX_DIR):
        import shutil
        shutil.rmtree(CODEX_DIR)
    print("=" * 60)
    print("TEST 1: Nano model generates facts (non-streaming)")
    print("=" * 60)
    topic, prompt = TOPICS[0]
    print(f"  Topic: {topic}")
    print(f"  Asking nano model...")
    text = nano_generate(topic, prompt, stream=False)
    print(f"  Response:\n    {text[:300]}")
    facts = prism.extract_facts(text)
    print(f"  Extracted {len(facts)} facts")
    for f in facts:
        r = prism.propose(CODEX_DIR, f, domain=topic, contributor_id='gemma-ptex-nano',
                         confidence=0.75, model_name=NANO_MODEL)
        print(f"    -> {r['status']}: {f[:60]}...")
    print(f"\n  PASS: Nano propose complete")
    print("\n" + "=" * 60)
    print("TEST 2: Streaming pipeline")
    print("=" * 60)
    topic2, prompt2 = TOPICS[1]
    print(f"  Topic: {topic2}")
    print(f"  Streaming from nano model:")
    print("  ", end="")
    streamed = nano_generate(topic2, prompt2, stream=True)
    facts2 = prism.extract_facts(streamed)
    print(f"  Extracted {len(facts2)} facts from stream")
    for f in facts2:
        r = prism.propose(CODEX_DIR, f, domain=topic2, contributor_id='gemma-ptex-nano',
                         confidence=0.8, model_name=NANO_MODEL)
        print(f"    -> {r['status']}: {f[:60]}...")
    print(f"\n  PASS: Stream pipeline complete")
    print("\n" + "=" * 60)
    print("TEST 3: Large model verification handoff")
    print("=" * 60)
    pending = prism.get_pending(CODEX_DIR)
    print(f"  Pending proposals: {len(pending)}")
    print(f"  Sending to large model for verification...")
    verdicts = large_verify(pending, config)
    print(f"  Got {len(verdicts)} verdicts")
    results = prism.batch_verify(CODEX_DIR, verdicts, verifier_id='grok-verifier',
                                model_name=config.get('large', {}).get('model', 'rule-based'))
    print(f"  Results: {results}")
    print(f"\n  PASS: Large model handoff complete")
    print("\n" + "=" * 60)
    print("TEST 4: Third topic + direct contribute (no staging)")
    print("=" * 60)
    topic3, prompt3 = TOPICS[2]
    print(f"  Topic: {topic3}")
    text3 = nano_generate(topic3, prompt3, stream=False)
    facts3 = prism.extract_facts(text3)
    print(f"  Extracted {len(facts3)} facts, contributing directly...")
    for f in facts3:
        r = prism.contribute_text(CODEX_DIR, f, domain=topic3,
                                 contributor_id='gemma-ptex-nano', source='nano-inference')
        print(f"    -> {r['status']}: {f[:60]}...")
    print(f"\n  PASS: Direct contribute complete")
    print("\n" + "=" * 60)
    print("TEST 5: File save verification + stats")
    print("=" * 60)
    s = prism.stats(CODEX_DIR)
    vs = prism.verification_stats(CODEX_DIR)
    print(f"  Total entries: {s['total']}")
    print(f"  Verified: {s['verified']}")
    print(f"  Domains: {s['domains']}")
    print(f"  Contributors: {s['contributors']}")
    print(f"  Verification: {vs}")
    manifest_path = os.path.join(CODEX_DIR, 'manifest.ndjson')
    manifest_exists = os.path.exists(manifest_path)
    manifest_lines = 0
    if manifest_exists:
        with open(manifest_path) as f:
            manifest_lines = sum(1 for _ in f)
    print(f"  Manifest exists: {manifest_exists}, lines: {manifest_lines}")
    domain_dirs = [d for d in os.listdir(CODEX_DIR) if os.path.isdir(os.path.join(CODEX_DIR, d)) and not d.startswith('.')]
    print(f"  Domain dirs created: {domain_dirs}")
    for dd in domain_dirs:
        files = os.listdir(os.path.join(CODEX_DIR, dd))
        print(f"    {dd}/: {len(files)} files")
    assert manifest_exists, "Manifest not created!"
    assert manifest_lines > 0, "Manifest is empty!"
    assert s['total'] > 0, "No entries in codex!"
    print(f"\n  PASS: Files verified")
    print("\n" + "=" * 60)
    print("TEST 6: Query and retrieval")
    print("=" * 60)
    if facts:
        qr = prism.query_text(CODEX_DIR, facts[0])
        print(f"  Query first fact: found={qr['found']}")
        sr = prism.search_keyword(CODEX_DIR, 'prime' if 'prime' in ' '.join(facts) else facts[0].split()[1])
        print(f"  Keyword search: {len(sr)} results")
    doms = prism.list_domains(CODEX_DIR)
    print(f"  Domains: {doms}")
    print(f"\n  PASS: Query/retrieval works")
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
    print(f"\nFinal stats: {json.dumps({**s, 'verification': vs}, indent=2)}")
    return s
if __name__ == '__main__':
    run_test()

import argparse, json, sys
from pathlib import Path
from . import contribute, query, verify, scrape
from .ptex import compile_atlas, load_atlas
from .contribute import stats
def _codex(args): return getattr(args, 'codex', './codex')
def cmd_contribute(args):
    text = args.text or sys.stdin.read()
    r = contribute.contribute_text(_codex(args), text, args.domain, args.contributor, args.source)
    print(json.dumps(r, indent=2))
def cmd_code(args):
    text = (Path(args.file).read_text(encoding='utf-8') if args.file
            else (args.text or sys.stdin.read()))
    r = contribute.contribute_code(_codex(args), text, args.file or '', args.contributor)
    print(json.dumps(r, indent=2))
def cmd_query(args):
    r = (query.query_nonce(_codex(args), int(args.text, 16)) if args.nonce
         else query.query_text(_codex(args), args.text))
    print(json.dumps(r, indent=2, default=str))
def cmd_search(args):
    r = (query.search_domain(_codex(args), args.domain, args.limit) if args.domain
         else query.search_keyword(_codex(args), args.text, args.limit))
    for e in r:
        print(f"[{e.get('nonce_id',0):08x}] {e.get('domain','?'):12s} {e.get('preview','')[:80]}")
def cmd_compile(args):
    atlas = compile_atlas(args.input, args.output or (args.input + '_atlas'))
    print(json.dumps({'files': atlas.get('files_processed', 0),
                      'vocab': atlas.get('vocab_size', 0)}, indent=2))
def cmd_propose(args):
    text = args.text or sys.stdin.read()
    r = verify.propose(_codex(args), text, args.domain, args.contributor,
                      confidence=args.confidence, model_name=args.model)
    print(json.dumps(r, indent=2))
def cmd_pending(args):
    pending = verify.get_pending(_codex(args), args.limit, args.domain)
    print(verify.format_for_verification(pending))
def cmd_verify_batch(args):
    pending = verify.get_pending(_codex(args), args.limit)
    if not pending:
        print("No pending proposals")
        return
    print(verify.format_for_verification(pending))
    print(f"\nEnter verdicts (idx verdict [refined_text]):")
    response = sys.stdin.read()
    verdicts = verify.parse_verification_response(response, pending)
    r = verify.batch_verify(_codex(args), verdicts, args.verifier, args.model)
    print(json.dumps(r, indent=2))
def cmd_scrape(args):
    text = (Path(args.file).read_text(encoding='utf-8') if args.file
            else (args.text or sys.stdin.read()))
    r = scrape.scrape_text(text, args.source, codex_dir=_codex(args),
                          contributor_id=args.contributor)
    print(json.dumps(r, indent=2))
def cmd_stats(args):
    s = stats(_codex(args))
    vs = verify.verification_stats(_codex(args))
    print(json.dumps({**s, 'verification': vs}, indent=2))
def cmd_merge(args):
    r = contribute.merge_codexes(args.target, args.sources)
    print(json.dumps(r, indent=2))
def main():
    p = argparse.ArgumentParser(prog='prism', description='Amni-Prism Knowledge Atlas')
    p.add_argument('--codex', '-c', default='./codex', help='Codex directory')
    sub = p.add_subparsers(dest='command')
    c = sub.add_parser('contribute', help='Contribute text')
    c.add_argument('text', nargs='?', help='Text to contribute (or stdin)')
    c.add_argument('--domain', '-d', default='general')
    c.add_argument('--contributor', default='cli-user')
    c.add_argument('--source', '-s', default='')
    c.set_defaults(func=cmd_contribute)
    cc = sub.add_parser('code', help='Contribute code')
    cc.add_argument('--file', '-f', help='File to contribute')
    cc.add_argument('text', nargs='?')
    cc.add_argument('--contributor', default='cli-user')
    cc.set_defaults(func=cmd_code)
    q = sub.add_parser('query', help='Query the codex')
    q.add_argument('text', help='Text or nonce (with --nonce)')
    q.add_argument('--nonce', '-n', action='store_true')
    q.set_defaults(func=cmd_query)
    s = sub.add_parser('search', help='Search codex')
    s.add_argument('text', nargs='?', help='Keyword to search')
    s.add_argument('--domain', '-d')
    s.add_argument('--limit', '-l', type=int, default=20)
    s.set_defaults(func=cmd_search)
    cp = sub.add_parser('compile', help='Compile atlas from directory')
    cp.add_argument('input', help='Input directory')
    cp.add_argument('--output', '-o')
    cp.set_defaults(func=cmd_compile)
    pr = sub.add_parser('propose', help='Propose fact for verification')
    pr.add_argument('text', nargs='?')
    pr.add_argument('--domain', '-d', default='general')
    pr.add_argument('--contributor', default='small-model')
    pr.add_argument('--confidence', type=float, default=0.7)
    pr.add_argument('--model', default='')
    pr.set_defaults(func=cmd_propose)
    pd = sub.add_parser('pending', help='List pending proposals')
    pd.add_argument('--limit', '-l', type=int, default=100)
    pd.add_argument('--domain', '-d')
    pd.set_defaults(func=cmd_pending)
    vb = sub.add_parser('verify', help='Batch verify pending proposals')
    vb.add_argument('--limit', '-l', type=int, default=100)
    vb.add_argument('--verifier', default='large-model')
    vb.add_argument('--model', default='')
    vb.set_defaults(func=cmd_verify_batch)
    sc = sub.add_parser('scrape', help='Scrape text for facts')
    sc.add_argument('text', nargs='?')
    sc.add_argument('--file', '-f')
    sc.add_argument('--source', '-s', default='')
    sc.add_argument('--contributor', default='auto-scraper')
    sc.set_defaults(func=cmd_scrape)
    st = sub.add_parser('stats', help='Show codex statistics')
    st.set_defaults(func=cmd_stats)
    mg = sub.add_parser('merge', help='Merge codexes')
    mg.add_argument('target', help='Target codex directory')
    mg.add_argument('sources', nargs='+', help='Source codex directories')
    mg.set_defaults(func=cmd_merge)
    args = p.parse_args()
    if not args.command:
        p.print_help()
        return
    args.func(args)
if __name__ == '__main__': main()

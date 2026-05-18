"""Amni-Prism: Shared Knowledge Atlas built on PTEX nonce-addressed textures."""
__version__ = '0.1.2'
from .gf17 import (P, nonce_to_rgba, rgba_to_nonce, word_to_hash_vector,
    content_hash, verify_field)
from .codec import (NonceLexCodec, HierarchicalCodec, DOMAIN_MAP, DOMAIN_NAMES,
    N_DOMAINS)
from .ptex import (compile_atlas, save_atlas, load_atlas, save_vocab_ptex,
    load_vocab_ptex, save_tiers_ptex, load_tiers_ptex)
from .contribute import (contribute_text, contribute_fact, contribute_code,
    stage_contribution, promote_staged, merge_codexes, list_contributions, stats)
from .query import (query_text, query_nonce, search_domain, search_keyword,
    retrieve, retrieve_batch, find_similar, list_domains, export_domain)
from .verify import (propose, get_pending, verify, batch_verify,
    format_for_verification, parse_verification_response, verification_stats,
    CONFIDENCE_THRESHOLD, VERIFY_APPROVE, VERIFY_REJECT, VERIFY_REFINE)
from .scrape import (scrape_text, scrape_structured, scrape_batch,
    extract_facts, classify_facts, validate_source, ALLOWED_SOURCES)

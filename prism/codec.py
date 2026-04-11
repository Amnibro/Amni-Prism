import numpy as np, hashlib, re, struct
from typing import List, Dict, Optional, Tuple
from collections import Counter
from .gf17 import (P, P2, P3, MAX_NONCE, nonce_to_rgba, rgba_to_nonce,
    nonce_to_rgba_batch, rgba_to_nonce_batch, content_hash, word_to_hash_vector)
CHAR_MAX = 127
WORD_BASE = 128
_WORD_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*|[0-9]+(?:\.[0-9]+)?|[ \t]+|\n|.)')
DOMAIN_MAP = {"general":0,"science":1,"math":2,"code":3,"language":4,"art":5,"history":6,
    "philosophy":7,"economics":8,"law":9,"medicine":10,"engineering":11,"geography":12,
    "music":13,"literature":14,"religion":15,"politics":16,"technology":17,"nature":18,
    "food":19,"sports":20,"military":21,"creative":22,"logic":23,"technical":24}
DOMAIN_NAMES = {v: k for k, v in DOMAIN_MAP.items()}
N_DOMAINS = 25
MAX_HIER_NONCES = 0xFFFFFFFE
_BLOCK_RE = re.compile(
    r'^([ \t]*)(def |class |if |elif |else:|for |while |try:|except |finally:|with |async def |async for |async with |@)',
    re.MULTILINE)
class NonceLexCodec:
    __slots__ = ('_w2id', '_id2w', '_next_id')
    def __init__(self):
        self._w2id: Dict[str, int] = {chr(i): i for i in range(1, WORD_BASE)}
        self._id2w: List[str] = [chr(i) if i > 0 else '' for i in range(WORD_BASE)]
        self._next_id = WORD_BASE
    def _char_nonce(self, ch: str) -> int:
        o = ord(ch)
        return o if 0 < o <= CHAR_MAX else 0
    def _add_word(self, w: str) -> int:
        if w in self._w2id: return self._w2id[w]
        nid = self._next_id
        if nid > MAX_NONCE: return -1
        self._w2id[w] = nid
        self._id2w.append(w) if nid == len(self._id2w) else None
        self._next_id = nid + 1
        return nid
    def build_vocab(self, text: str) -> int:
        tokens = _WORD_RE.findall(text)
        freq = Counter()
        for t in tokens:
            freq[t] += (1 if len(t) > 1 or not t.isspace() else 0) if (len(t) > 1 and (t[0].isalpha() or t[0] == '_' or t[0].isdigit())) else 0
        for w, _ in freq.most_common():
            if w and len(w) > 1 and (w[0].isalpha() or w[0] == '_' or w[0].isdigit()):
                self._add_word(w)
        return self._next_id - WORD_BASE
    @property
    def vocab_size(self) -> int: return self._next_id - WORD_BASE
    @property
    def total_nonces(self) -> int: return self._next_id
    def encode(self, text: str) -> np.ndarray:
        tokens = _WORD_RE.findall(text)
        nids = []
        for t in tokens:
            if t in self._w2id:
                nids.append(self._w2id[t])
            elif len(t) == 1:
                cn = self._char_nonce(t)
                if cn > 0: nids.append(cn)
                else:
                    wid = self._add_word(t)
                    nids.append(wid if wid > 0 else 0)
            elif len(t) > 1 and t[0].isdigit():
                wid = self._add_word(t)
                if wid > 0: nids.append(wid)
                else:
                    for ch in t:
                        cn = self._char_nonce(ch)
                        nids.append(cn if cn > 0 else 0)
            elif t.isspace():
                for ch in t: nids.append(self._char_nonce(ch))
            else:
                for ch in t:
                    cn = self._char_nonce(ch)
                    if cn > 0: nids.append(cn)
                    else:
                        wid = self._add_word(ch)
                        nids.append(wid if wid > 0 else 0)
        arr = np.array(nids, dtype=np.uint32) if nids else np.zeros(0, dtype=np.uint32)
        return nonce_to_rgba_batch(arr)
    def decode(self, pixels: np.ndarray) -> str:
        if pixels.size == 0: return ''
        nids = rgba_to_nonce_batch(pixels)
        parts = []
        for nid in nids:
            nid = int(nid)
            if nid == 0: continue
            elif nid <= CHAR_MAX: parts.append(chr(nid))
            elif nid < len(self._id2w): parts.append(self._id2w[nid])
        return ''.join(parts)
def _detect_blocks(text: str) -> List[List[str]]:
    lines = text.split('\n')
    blocks, current = [], []
    for line in lines:
        stripped = line.lstrip()
        is_start = bool(_BLOCK_RE.match(line)) if stripped else False
        if is_start and current:
            blocks.append(current)
            current = []
        current.append(line)
    if current: blocks.append(current)
    return blocks if blocks else [lines]
def _detect_domain(text: str, filepath: str = '') -> int:
    scores = np.zeros(N_DOMAINS, dtype=np.float32)
    tl = text.lower()
    kw = {'science': ['hypothesis','experiment','theory','research'],
          'math': ['equation','theorem','proof','matrix','vector'],
          'code': ['def ','class ','import ','return ','self.'],
          'medicine': ['patient','diagnosis','treatment','clinical'],
          'engineering': ['design','system','component','module'],
          'technology': ['software','hardware','network','server'],
          'language': ['grammar','syntax','semantic','linguistic'],
          'art': ['color','canvas','render','texture','visual'],
          'music': ['note','chord','rhythm','melody','tempo'],
          'nature': ['species','habitat','ecosystem','organism'],
          'economics': ['market','price','supply','demand','trade'],
          'law': ['statute','regulation','court','legal','compliance'],
          'history': ['century','era','civilization','ancient','war'],
          'philosophy': ['logic','ethics','metaphysics','epistemology'],
          'literature': ['novel','poetry','narrative','prose','fiction'],
          'religion': ['faith','spiritual','sacred','divine','worship'],
          'politics': ['policy','government','election','democracy'],
          'military': ['strategy','defense','tactical','combat'],
          'sports': ['game','score','team','player','match'],
          'food': ['recipe','ingredient','cook','flavor','dish'],
          'creative': ['design','create','imagine','artistic','style'],
          'logic': ['boolean','condition','predicate','inference'],
          'technical': ['specification','protocol','standard','format'],
          'geography': ['continent','ocean','region','climate','terrain']}
    for domain, words in kw.items():
        did = DOMAIN_MAP[domain]
        for w in words:
            scores[did] += tl.count(w)
    fp = filepath.lower()
    if '.py' in fp or '.js' in fp or '.rs' in fp or '.ts' in fp: scores[3] += 5
    if 'test' in fp: scores[3] += 3
    return int(np.argmax(scores)) if np.max(scores) > 0 else 0
class HierarchicalCodec(NonceLexCodec):
    __slots__ = ('_line_h2id', '_line_id2h', '_line_id2nonces', '_line_next',
                 '_block_h2id', '_block_id2h', '_block_id2lines', '_block_next',
                 '_file_h2id', '_file_id2h', '_file_id2blocks', '_file_next',
                 '_file_paths', '_file_domains', '_word_vectors', '_stats')
    def __init__(self):
        super().__init__()
        self._line_h2id: Dict[int, int] = {}
        self._line_id2h: List[int] = []
        self._line_id2nonces: List[np.ndarray] = []
        self._line_next = 0
        self._block_h2id: Dict[int, int] = {}
        self._block_id2h: List[int] = []
        self._block_id2lines: List[np.ndarray] = []
        self._block_next = 0
        self._file_h2id: Dict[int, int] = {}
        self._file_id2h: List[int] = []
        self._file_id2blocks: List[np.ndarray] = []
        self._file_next = 0
        self._file_paths: List[str] = []
        self._file_domains: List[int] = []
        self._word_vectors: Dict[str, np.ndarray] = {}
        self._stats = {'lines_total': 0, 'lines_unique': 0, 'blocks_total': 0,
                       'blocks_unique': 0, 'files': 0}
    def _register_line(self, line: str) -> int:
        h = content_hash(line)
        if h in self._line_h2id: return self._line_h2id[h]
        if self._line_next >= MAX_HIER_NONCES: return -1
        nid = self._line_next
        px = super().encode(line)
        nonces = rgba_to_nonce_batch(px) if px.size > 0 else np.zeros(0, dtype=np.uint32)
        self._line_h2id[h] = nid
        self._line_id2h.append(h)
        self._line_id2nonces.append(nonces)
        self._line_next += 1
        self._stats['lines_unique'] += 1
        return nid
    def _register_block(self, block_lines: List[str]) -> int:
        h = content_hash('\n'.join(block_lines))
        if h in self._block_h2id: return self._block_h2id[h]
        if self._block_next >= MAX_HIER_NONCES: return -1
        nid = self._block_next
        line_nonces = np.array([self._register_line(l) for l in block_lines], dtype=np.int64)
        line_nonces = line_nonces[line_nonces >= 0].astype(np.uint32)
        self._block_h2id[h] = nid
        self._block_id2h.append(h)
        self._block_id2lines.append(line_nonces)
        self._block_next += 1
        self._stats['blocks_unique'] += 1
        return nid
    def _register_file(self, text: str, filepath: str = '') -> int:
        h = content_hash(text)
        if h in self._file_h2id: return self._file_h2id[h]
        if self._file_next >= MAX_HIER_NONCES: return -1
        nid = self._file_next
        blocks = _detect_blocks(text)
        block_nonces_raw = np.array([self._register_block(b) for b in blocks], dtype=np.int64)
        block_nonces = block_nonces_raw[block_nonces_raw >= 0].astype(np.uint32)
        self._file_h2id[h] = nid
        self._file_id2h.append(h)
        self._file_id2blocks.append(block_nonces)
        self._file_paths.append(filepath)
        self._file_domains.append(_detect_domain(text, filepath))
        self._file_next += 1
        self._stats['files'] += 1
        self._stats['blocks_total'] += len(blocks)
        lines = text.split('\n')
        self._stats['lines_total'] += len(lines)
        return nid
    def decode_file_nonce(self, file_nonce_id: int) -> str:
        if file_nonce_id >= len(self._file_id2blocks): return ''
        block_ids = self._file_id2blocks[file_nonce_id]
        blocks_text = []
        for bid in block_ids:
            bid = int(bid)
            if bid < len(self._block_id2lines):
                line_ids = self._block_id2lines[bid]
                lines_text = []
                for lid in line_ids:
                    lid = int(lid)
                    if lid < len(self._line_id2nonces):
                        wn = self._line_id2nonces[lid]
                        px = nonce_to_rgba_batch(wn) if wn.size > 0 else np.zeros((0, 4), dtype=np.uint8)
                        lines_text.append(self.decode(px))
                blocks_text.append('\n'.join(lines_text))
        return '\n'.join(blocks_text)
    def decode_block_nonce(self, block_nonce_id: int) -> str:
        if block_nonce_id >= len(self._block_id2lines): return ''
        line_ids = self._block_id2lines[block_nonce_id]
        lines_text = []
        for lid in line_ids:
            lid = int(lid)
            if lid < len(self._line_id2nonces):
                wn = self._line_id2nonces[lid]
                px = nonce_to_rgba_batch(wn) if wn.size > 0 else np.zeros((0, 4), dtype=np.uint8)
                lines_text.append(self.decode(px))
        return '\n'.join(lines_text)
    def decode_line_nonce(self, line_nonce_id: int) -> str:
        if line_nonce_id >= len(self._line_id2nonces): return ''
        wn = self._line_id2nonces[line_nonce_id]
        px = nonce_to_rgba_batch(wn) if wn.size > 0 else np.zeros((0, 4), dtype=np.uint8)
        return self.decode(px)
    def lookup_line(self, line: str) -> Optional[int]:
        h = content_hash(line)
        return self._line_h2id.get(h)
    def lookup_block(self, lines: List[str]) -> Optional[int]:
        h = content_hash('\n'.join(lines))
        return self._block_h2id.get(h)
    def tier_stats(self) -> Dict:
        return {'vocab': self.vocab_size, 'lines_unique': self._line_next,
                'blocks_unique': self._block_next, 'files': self._file_next,
                'lines_total': self._stats['lines_total'],
                'blocks_total': self._stats['blocks_total']}
    def compression_report(self) -> Dict:
        s = self.tier_stats()
        vocab_px = self.total_nonces
        line_px = sum(n.size for n in self._line_id2nonces)
        block_px = sum(n.size for n in self._block_id2lines)
        file_px = sum(n.size for n in self._file_id2blocks)
        total_px = vocab_px + line_px + block_px + file_px
        lt, bt = max(s['lines_total'], 1), max(s['blocks_total'], 1)
        return {**s, 'total_nonce_pixels': total_px, 'total_bytes_rgba': total_px * 4,
                'line_dedup_ratio': 1.0 - s['lines_unique'] / lt,
                'block_dedup_ratio': 1.0 - s['blocks_unique'] / bt,
                'words': self.vocab_size,
                'tier_pixels': {'t0_t1_vocab': vocab_px, 't2_lines': line_px,
                                't3_blocks': block_px, 't4_files': file_px}}

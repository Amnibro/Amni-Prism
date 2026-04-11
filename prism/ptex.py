import numpy as np, hashlib, struct, json, os, time
from typing import Dict, List, Optional, Tuple, Set
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from .gf17 import (P, MAX_NONCE, nonce_to_rgba_batch, rgba_to_nonce_batch,
    word_to_hash_vector, content_hash)
from .codec import (NonceLexCodec, HierarchicalCodec, CHAR_MAX, WORD_BASE,
    DOMAIN_MAP, DOMAIN_NAMES, N_DOMAINS, _detect_domain)
PTEX_MAGIC = 0x50545845
NLX_MAGIC = 0x4E4C5850
HNA_MAGIC = 0x484E4150
CODEX_MAGIC = 0x434F4458
PTEX_VER = 1
MODE_NONCELEX = 30
MODE_HIER_NONCELEX = 31
def _pack_uint32_array(arr: np.ndarray) -> bytes:
    return struct.pack('<I', len(arr)) + arr.astype(np.uint32).tobytes()
def _unpack_uint32_array(data: bytes, offset: int) -> Tuple[np.ndarray, int]:
    n = struct.unpack('<I', data[offset:offset + 4])[0]
    offset += 4
    arr = np.frombuffer(data[offset:offset + n * 4], dtype=np.uint32).copy()
    return arr, offset + n * 4
def save_vocab_ptex(path: str, codec: NonceLexCodec):
    words = []
    for i in range(WORD_BASE, codec.total_nonces):
        w = codec._id2w[i] if i < len(codec._id2w) else ''
        wb = w.encode('utf-8')
        words.append(struct.pack('<H', len(wb)) + wb)
    vocab_data = b''.join(words)
    n_words = codec.total_nonces - WORD_BASE
    with open(path, 'wb') as f:
        f.write(struct.pack('<I', NLX_MAGIC))
        f.write(struct.pack('<HH', PTEX_VER, MODE_NONCELEX))
        f.write(struct.pack('<I', n_words))
        f.write(struct.pack('<I', len(vocab_data)))
        chk = hashlib.sha256(vocab_data).digest()
        f.write(chk)
        f.write(vocab_data)
def load_vocab_ptex(path: str) -> NonceLexCodec:
    codec = NonceLexCodec()
    with open(path, 'rb') as f:
        mg = struct.unpack('<I', f.read(4))[0]
        assert mg == NLX_MAGIC, f"bad NLX magic: {mg:#x}"
        ver, mode = struct.unpack('<HH', f.read(4))
        n_words = struct.unpack('<I', f.read(4))[0]
        data_len = struct.unpack('<I', f.read(4))[0]
        stored_chk = f.read(32)
        vocab_data = f.read(data_len)
    assert hashlib.sha256(vocab_data).digest() == stored_chk, "vocab SHA-256 mismatch"
    off = 0
    for _ in range(n_words):
        wlen = struct.unpack('<H', vocab_data[off:off + 2])[0]
        off += 2
        w = vocab_data[off:off + wlen].decode('utf-8')
        off += wlen
        codec._add_word(w)
    return codec
def save_tiers_ptex(path: str, codec: HierarchicalCodec):
    line_parts = [_pack_uint32_array(codec._line_id2nonces[i]) for i in range(codec._line_next)]
    line_data = b''.join(line_parts)
    block_parts = [_pack_uint32_array(codec._block_id2lines[i]) for i in range(codec._block_next)]
    block_data = b''.join(block_parts)
    file_parts = [_pack_uint32_array(codec._file_id2blocks[i]) for i in range(codec._file_next)]
    file_data = b''.join(file_parts)
    tier_payload = struct.pack('<III', codec._line_next, codec._block_next, codec._file_next)
    tier_payload += struct.pack('<I', len(line_data)) + line_data
    tier_payload += struct.pack('<I', len(block_data)) + block_data
    tier_payload += struct.pack('<I', len(file_data)) + file_data
    chk = hashlib.sha256(tier_payload).digest()
    with open(path, 'wb') as f:
        f.write(struct.pack('<I', HNA_MAGIC))
        f.write(struct.pack('<HH', PTEX_VER, MODE_HIER_NONCELEX))
        f.write(chk)
        f.write(tier_payload)
def load_tiers_ptex(path: str, codec: HierarchicalCodec):
    with open(path, 'rb') as f:
        mg = struct.unpack('<I', f.read(4))[0]
        assert mg == HNA_MAGIC, f"bad HNA magic: {mg:#x}"
        ver, mode = struct.unpack('<HH', f.read(4))
        stored_chk = f.read(32)
        tier_payload = f.read()
    assert hashlib.sha256(tier_payload).digest() == stored_chk, "tiers SHA-256 mismatch"
    off = 0
    n_lines, n_blocks, n_files = struct.unpack('<III', tier_payload[off:off + 12])
    off += 12
    ld_len = struct.unpack('<I', tier_payload[off:off + 4])[0]; off += 4
    ld = tier_payload[off:off + ld_len]; lo = 0
    for _ in range(n_lines):
        arr, lo = _unpack_uint32_array(ld, lo)
        codec._line_id2nonces.append(arr)
        codec._line_id2h.append(0)
    codec._line_next = n_lines
    off += ld_len
    bd_len = struct.unpack('<I', tier_payload[off:off + 4])[0]; off += 4
    bd = tier_payload[off:off + bd_len]; bo = 0
    for _ in range(n_blocks):
        arr, bo = _unpack_uint32_array(bd, bo)
        codec._block_id2lines.append(arr)
        codec._block_id2h.append(0)
    codec._block_next = n_blocks
    off += bd_len
    fd_len = struct.unpack('<I', tier_payload[off:off + 4])[0]; off += 4
    fd = tier_payload[off:off + fd_len]; fo = 0
    for _ in range(n_files):
        arr, fo = _unpack_uint32_array(fd, fo)
        codec._file_id2blocks.append(arr)
        codec._file_id2h.append(0)
    codec._file_next = n_files
def save_atlas(output_dir: str, codec: HierarchicalCodec):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    save_vocab_ptex(str(out / 'vocab.nlx.ptex'), codec)
    save_tiers_ptex(str(out / 'tiers.hna.ptex'), codec)
    file_hashes = {fid: h for h, fid in codec._file_h2id.items()}
    manifest = {
        'version': PTEX_VER, 'mode': MODE_HIER_NONCELEX, 'prime': P,
        'stats': codec.compression_report(),
        'files': [{'id': i, 'path': codec._file_paths[i],
                    'domain': DOMAIN_NAMES.get(codec._file_domains[i], 'general'),
                    'domain_id': codec._file_domains[i],
                    'n_blocks': len(codec._file_id2blocks[i]),
                    'hash': hex(file_hashes.get(i, 0))}
                   for i in range(codec._file_next)],
        'tier_counts': {'t0_chars': CHAR_MAX + 1, 't1_words': codec.vocab_size,
                        't2_lines': codec._line_next, 't3_blocks': codec._block_next,
                        't4_files': codec._file_next},
        'domains_used': {DOMAIN_NAMES.get(d, 'general'): c
                         for d, c in Counter(codec._file_domains).items()},
    }
    with open(str(out / 'manifest.json'), 'w') as f:
        json.dump(manifest, f, indent=2)
    if codec._word_vectors:
        words = sorted(codec._word_vectors.keys())
        vecs = np.stack([codec._word_vectors[w] for w in words])
        np.savez_compressed(str(out / 'reffelt_vectors.npz'), words=np.array(words), vectors=vecs)
def load_atlas(atlas_dir: str) -> Tuple[HierarchicalCodec, Dict]:
    d = Path(atlas_dir)
    base = load_vocab_ptex(str(d / 'vocab.nlx.ptex'))
    codec = HierarchicalCodec()
    codec._w2id = dict(base._w2id)
    codec._id2w = list(base._id2w)
    codec._next_id = base._next_id
    load_tiers_ptex(str(d / 'tiers.hna.ptex'), codec)
    with open(str(d / 'manifest.json'), 'r') as f:
        manifest = json.load(f)
    for fi in manifest.get('files', []):
        codec._file_paths.append(fi['path'])
        codec._file_domains.append(fi.get('domain_id', DOMAIN_MAP.get(fi.get('domain', 'general'), 0)))
    return codec, manifest
def _scan_file(filepath: str) -> Optional[str]:
    try: return Path(filepath).read_text(encoding='utf-8', errors='replace')
    except Exception: return None
def compile_atlas(root_dir: str, output_dir: str, pattern: str = '**/*.py',
                  exclude_dirs: Optional[Set[str]] = None,
                  max_workers: int = 8, progress_fn=None) -> Dict:
    root = Path(root_dir)
    exclude = exclude_dirs or {'__pycache__', '.venv', 'backups', 'archive', 'node_modules', '.git', 'target'}
    files = sorted(str(fp) for fp in root.glob(pattern) if not any(ex in fp.parts for ex in exclude))
    total = len(files)
    codec = HierarchicalCodec()
    t0 = time.time()
    texts = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_scan_file, fp): fp for fp in files}
        done = 0
        for future in as_completed(futures):
            fp = futures[future]
            text = future.result()
            if text is not None: texts[fp] = text
            done += 1
            if progress_fn and done % 100 == 0: progress_fn(done, total, 'scan')
    t_scan = time.time() - t0
    t1 = time.time()
    codec.build_vocab('\n'.join(texts.values()))
    t_vocab = time.time() - t1
    t2 = time.time()
    for i, (fp, text) in enumerate(texts.items()):
        codec._register_file(text, fp)
        if progress_fn and (i + 1) % 100 == 0: progress_fn(i + 1, len(texts), 'encode')
    t_encode = time.time() - t2
    t3 = time.time()
    if progress_fn: progress_fn(0, len(codec._w2id), 'reffelt')
    for i, w in enumerate(codec._w2id):
        if w not in codec._word_vectors:
            codec._word_vectors[w] = word_to_hash_vector(w)
        if progress_fn and (i + 1) % 1000 == 0: progress_fn(i + 1, len(codec._w2id), 'reffelt')
    t_reffelt = time.time() - t3
    t4 = time.time()
    save_atlas(output_dir, codec)
    t_save = time.time() - t4
    report = codec.compression_report()
    report['timings'] = {'scan_s': round(t_scan, 2), 'vocab_s': round(t_vocab, 2),
                         'encode_s': round(t_encode, 2), 'reffelt_s': round(t_reffelt, 2),
                         'save_s': round(t_save, 2), 'total_s': round(time.time() - t0, 2)}
    report['file_count'] = len(texts)
    report['skipped'] = total - len(texts)
    return report

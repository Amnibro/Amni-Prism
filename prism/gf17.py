import numpy as np, hashlib
from typing import Tuple
P = 17
P2 = P * P
P3 = P * P * P
P4 = P ** 4
MAX_NONCE = P4 - 1
_INV = np.zeros(P, dtype=np.uint8)
for _a in range(1, P): _INV[_a] = pow(int(_a), P - 2, P)
_MUL = np.zeros((P, P), dtype=np.uint8)
_ADD = np.zeros((P, P), dtype=np.uint8)
for _i in range(P):
    for _j in range(P):
        _MUL[_i, _j] = (_i * _j) % P
        _ADD[_i, _j] = (_i + _j) % P
_CUBE = np.array([pow(int(x), 3, P) for x in range(P)], dtype=np.uint8)
GF17_INV = _INV
GF17_MUL = _MUL
GF17_ADD = _ADD
GF17_CUBE = _CUBE
def gf17_add(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return _ADD[a.ravel(), b.ravel()].reshape(a.shape)
def gf17_sub(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return _ADD[a.ravel(), ((P - b.ravel()) % P).astype(np.uint8)].reshape(a.shape)
def gf17_mul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return _MUL[a.ravel(), b.ravel()].reshape(a.shape)
def gf17_inv(a: np.ndarray) -> np.ndarray:
    return _INV[a.ravel()].reshape(a.shape)
def gf17_div(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return _MUL[a.ravel(), _INV[b.ravel()]].reshape(a.shape)
def gf17_matmul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (a.astype(np.float64) @ b.astype(np.float64) % P).astype(np.uint8)
def gf17_distance(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    d = np.abs(a.astype(np.int16) - b.astype(np.int16))
    return np.minimum(d, P - d).astype(np.uint8)
def nonce_to_rgba(nid: int) -> np.ndarray:
    return np.array([nid % P, (nid // P) % P, (nid // P2) % P, (nid // P3) % P], dtype=np.uint8)
def rgba_to_nonce(px: np.ndarray) -> int:
    return int(px[0]) + int(px[1]) * P + int(px[2]) * P2 + int(px[3]) * P3
def nonce_to_rgba_batch(nids: np.ndarray) -> np.ndarray:
    n = nids.astype(np.uint32)
    return np.stack([n % P, (n // P) % P, (n // P2) % P, (n // P3) % P], axis=-1).astype(np.uint8)
def rgba_to_nonce_batch(px: np.ndarray) -> np.ndarray:
    p = px.astype(np.uint32)
    return p[..., 0] + p[..., 1] * P + p[..., 2] * P2 + p[..., 3] * P3
def word_to_hash_vector(word: str, dim: int = 512, seed: int = 42) -> np.ndarray:
    h = hashlib.sha256(f"{seed}:{word.lower().strip()}".encode()).digest()
    rng = np.random.RandomState(int.from_bytes(h[:4], 'little'))
    v = rng.randn(dim).astype(np.float32)
    return v / max(np.linalg.norm(v), 1e-8)
def content_hash(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode('utf-8', errors='replace')).digest()[:8], 'little')
def verify_field():
    ok = True
    for a in range(P):
        for b in range(P):
            ok &= (_ADD[a, b] == (a + b) % P)
            ok &= (_MUL[a, b] == (a * b) % P)
    for a in range(1, P):
        ok &= (_MUL[a, _INV[a]] == 1)
    cubes = set(int(_CUBE[x]) for x in range(1, P))
    ok &= (len(cubes) == P - 1)
    return ok

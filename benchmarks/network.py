"""What a network in njit costs. Candidate structure: move encoder, Pokemon encoder, then a head,
with widths as arguments so the same code measures every size in the table."""
import time
import numpy as np
from Engine.damage_calc import calculate_damage
from Models.constants import _FIELD_MY_POK, _FIELD_OPP_POK
from Models.idx_const import MOVE_STRIDE, OFFSET_MOVE, POK_LEN
from Utils.jit import njit
from benchmarks.fights import fight, seed_all

pc = time.perf_counter
M_IN, P_FEAT, FIELD, CLASSES = 56, 72, 40, 7
_SIZES = ((32, 64, 128), (48, 96, 192), (64, 128, 256), (96, 192, 384), (128, 256, 512))


@njit
def _dense_plain(w, x, out):
    """Strict float rules, so the reduction can't be vectorized"""
    n_in = x.shape[0]
    n_out = out.shape[0]
    bias = n_in * n_out
    for i in range(n_out):
        s = w[bias + i]
        row = i * n_in
        for j in range(n_in):
            s += w[row + j] * x[j]
        out[i] = s if s > 0.0 else 0.0


@njit(fastmath=True)
def _dense(w, off, x, out):
    """out = relu(W x + b). w holds W row by row and then b, from off. Slices first, so indices
    start at 0 and no negative-index check stays in the inner loop. Returns the next offset"""
    n_in = x.shape[0]
    n_out = out.shape[0]
    bias = n_in * n_out
    layer = w[off:off + bias + n_out]
    for i in range(n_out):
        s = layer[bias + i]
        row = layer[i * n_in:(i + 1) * n_in]
        for j in range(n_in):
            s += row[j] * x[j]
        out[i] = s if s > 0.0 else 0.0
    return off + bias + n_out


@njit(fastmath=True)
def _dense_offset(w, off, x, xo, out, oo, n_in, n_out):
    """The same layer indexed with unknown offsets, the form Step 4 has to avoid"""
    bias = off + n_in * n_out
    for i in range(n_out):
        s = w[bias + i]
        row = off + i * n_in
        for j in range(n_in):
            s += w[row + j] * x[xo + j]
        out[oo + i] = s if s > 0.0 else 0.0
    return bias + n_out


@njit(fastmath=True)
def _output(w, off, x, out):
    """The last layer: no relu, then softmax"""
    n_in = x.shape[0]
    n_out = out.shape[0]
    bias = n_in * n_out
    layer = w[off:off + bias + n_out]
    for i in range(n_out):
        s = layer[bias + i]
        row = layer[i * n_in:(i + 1) * n_in]
        for j in range(n_in):
            s += row[j] * x[j]
        out[i] = s
    top = out[0]
    for i in range(1, n_out):
        if out[i] > top:
            top = out[i]
    total = 0.0
    for i in range(n_out):
        out[i] = np.exp(out[i] - top)
        total += out[i]
    for i in range(n_out):
        out[i] = out[i] / total


@njit
def _loop_plain(w, x, out, reps):
    total = 0.0
    for _ in range(reps):
        _dense_plain(w, x, out)
        total += out[0]
        x[0] = out[1] * 1e-3
    return total


@njit(fastmath=True)
def _loop_dense(w, x, out, reps):
    total = 0.0
    for _ in range(reps):
        _dense(w, 0, x, out)
        total += out[0]
        x[0] = out[1] * 1e-3
    return total


@njit(fastmath=True)
def _loop_offset(w, off, x, xo, out, oo, n, reps):
    total = 0.0
    for _ in range(reps):
        _dense_offset(w, off, x, xo, out, oo, n, n)
        total += out[oo]
        x[xo] = out[oo + 1] * 1e-3
    return total


@njit(fastmath=True)
def _move_pools(w, move_x, pools, tmp, m_out):
    """48 move encoders, averaged per Pokemon"""
    t = tmp[:m_out]
    for p in range(12):
        pool = pools[p * m_out:(p + 1) * m_out]
        for k in range(m_out):
            pool[k] = 0.0
        for m in range(4):
            start = (p * 4 + m) * M_IN
            _dense(w, 0, move_x[start:start + M_IN], t)
            for k in range(m_out):
                pool[k] += t[k]
        for k in range(m_out):
            pool[k] *= 0.25


@njit(fastmath=True)
def _pokemon_embeddings(w, off, pools, pok_x, pin, emb, m_out, p_out):
    """12 Pokemon encoders, each on its own features and the pool of its moves"""
    for p in range(12):
        features = pok_x[p * P_FEAT:(p + 1) * P_FEAT]
        pool = pools[p * m_out:(p + 1) * m_out]
        for k in range(P_FEAT):
            pin[k] = features[k]
        for k in range(m_out):
            pin[P_FEAT + k] = pool[k]
        _dense(w, off, pin, emb[p * p_out:(p + 1) * p_out])


@njit(fastmath=True)
def _head_input(emb, field_x, my_idx, opp_idx, hin, p_out):
    """My active, the foe's active, both bench means, then the field"""
    me = emb[my_idx * p_out:(my_idx + 1) * p_out]
    foe = emb[(opp_idx + 6) * p_out:(opp_idx + 7) * p_out]
    my_bench = hin[2 * p_out:3 * p_out]
    foe_bench = hin[3 * p_out:4 * p_out]
    for k in range(p_out):
        hin[k] = me[k]
        hin[p_out + k] = foe[k]
        my_bench[k] = 0.0
        foe_bench[k] = 0.0
    for p in range(6):
        if p != my_idx:
            e = emb[p * p_out:(p + 1) * p_out]
            for k in range(p_out):
                my_bench[k] += e[k]
        if p != opp_idx:
            e = emb[(p + 6) * p_out:(p + 7) * p_out]
            for k in range(p_out):
                foe_bench[k] += e[k]
    for k in range(p_out):
        my_bench[k] *= 0.2
        foe_bench[k] *= 0.2
    tail = hin[4 * p_out:]
    for k in range(FIELD):
        tail[k] = field_x[k]


@njit(fastmath=True)
def _forward(w, pools, pok_x, field_x, my_idx, opp_idx, buf, probs, m_out, p_out, h):
    """12 Pokemon encoders, bench means, 2 hidden layers, softmax. buf is scratch memory"""
    p_in = P_FEAT + m_out
    head_in = 4 * p_out + FIELD
    used = 12 * p_out
    emb = buf[:used]
    pin = buf[used:used + p_in]
    used += p_in
    hin = buf[used:used + head_in]
    used += head_in
    a = buf[used:used + h]
    b = buf[used + h:used + 2 * h]
    off_pok = M_IN * m_out + m_out
    _pokemon_embeddings(w, off_pok, pools, pok_x, pin, emb, m_out, p_out)
    _head_input(emb, field_x, my_idx, opp_idx, hin, p_out)
    off = _dense(w, off_pok + p_in * p_out + p_out, hin, a)
    off = _dense(w, off, a, b)
    _output(w, off, b, probs)


@njit(fastmath=True)
def _loop_network(w, move_x, pok_x, field_x, buf, pools, tmp, probs, sizes, cached, reps):
    m_out, p_out, h = sizes
    total = 0.0
    for r in range(reps):
        field_x[0] = r * 1e-6
        if not cached:
            _move_pools(w, move_x, pools, tmp, m_out)
        _forward(w, pools, pok_x, field_x, r % 6, (r + 1) % 6, buf, probs, m_out, p_out, h)
        total += probs[0]
    return total


@njit(fastmath=True)
def _loop_flat(w, x, buf, probs, reps):
    """The shell's 2315 inputs through 256, 256, then the output"""
    a = buf[:256]
    b = buf[256:512]
    total = 0.0
    for r in range(reps):
        x[0] = r * 1e-6
        off = _dense(w, 0, x, a)
        off = _dense(w, off, a, b)
        _output(w, off, b, probs)
        total += probs[0]
    return total


@njit
def _twenty_calcs(arr):
    my_idx = arr[_FIELD_MY_POK]
    opp_idx = arr[_FIELD_OPP_POK]
    me = arr[my_idx * POK_LEN:(my_idx + 1) * POK_LEN]
    foe = arr[(opp_idx + 6) * POK_LEN:(opp_idx + 7) * POK_LEN]
    total = 0
    for n in range(20):
        m = n % 4
        start = OFFSET_MOVE + m * MOVE_STRIDE
        if n % 8 < 4:
            total += calculate_damage(
                me, foe, me[start:start + MOVE_STRIDE], 0, False, 100, 0, False
            )
        else:
            total += calculate_damage(
                foe, me, foe[start:start + MOVE_STRIDE], 0, False, 100, 0, False
            )
    return total


@njit
def _loop_calcs(arr, reps):
    total = 0
    for _ in range(reps):
        total += _twenty_calcs(arr)
    return total


@njit
def _noop_array(a):
    return a[0]


@njit
def _noop_tuple(t):
    return t[0][0]


def _n_params(m_out, p_out, h):
    p_in = P_FEAT + m_out
    return ((M_IN * m_out + m_out) + (p_in * p_out + p_out) + ((4 * p_out + FIELD) * h + h)
            + (h * h + h) + (h * CLASSES + CLASSES))


def _best_us(budget, fn, *args, reps):
    """Best round in µs per rep, the round least disturbed by the rest of the machine"""
    best = 1e18
    fn(*args, 1)
    for _ in range(budget.rounds):
        start = pc()
        fn(*args, reps)
        best = min(best, (pc() - start) / reps)
    return best * 1e6


def _python_call_us(budget, fn, *args, reps):
    """Called from Python on purpose, since that's the overhead being measured"""
    best = 1e18
    fn(*args)
    for _ in range(budget.rounds):
        start = pc()
        for _ in range(reps):
            fn(*args)
        best = min(best, (pc() - start) / reps)
    return best * 1e6


def _sparse(rng, n, density):
    return (rng.random(n) * (rng.random(n) < density)).astype(np.float32)


def _kernels(report, budget, rng):
    n = 128
    w = rng.normal(0, 0.1, n * n + n).astype(np.float32)
    x = rng.random(n * 2).astype(np.float32)
    out = np.zeros(n * 2, dtype=np.float32)
    plain = _best_us(budget, _loop_plain, w, x[:n], out[:n], reps=20_000)
    fast = _best_us(budget, _loop_dense, w, x[:n], out[:n], reps=200_000)
    offset = _best_us(budget, _loop_offset, w, 0, x, 3, out, 5, n, reps=50_000)
    for key, value in (("dense_plain", plain), ("dense_fastmath", fast), ("dense_offset", offset)):
        report.metric(f"network/{key}_us", value)
    return [
        ("Dense layer 128x128, plain `@njit`", f"{plain:.2f} µs"),
        ("Same with `fastmath=True`, sliced", f"{fast:.2f} µs"),
        ("Same with `fastmath=True`, unknown offsets", f"{offset:.2f} µs"),
    ]


def _engine_pieces(report, budget):
    from NeuralNetwork.models import to_nn_input
    arr = fight("Roark weak")
    seed_all(37)
    shell = _python_call_us(budget, to_nn_input, arr, reps=100_000)
    calcs = _best_us(budget, _loop_calcs, arr, reps=200_000)
    one = np.zeros(4, dtype=np.int32)
    twelve = tuple(np.zeros(4, dtype=np.int32) for _ in range(12))
    call_one = _python_call_us(budget, _noop_array, one, reps=200_000)
    call_twelve = _python_call_us(budget, _noop_tuple, twelve, reps=200_000)
    report.metric("network/shell_encode_us", shell)
    report.metric("network/twenty_calcs_us", calcs)
    report.metric("network/call_array_us", call_one)
    report.metric("network/call_tuple12_us", call_twelve)
    return [
        ("Shell `to_nn_input`", f"{shell:.2f} µs"),
        ("20 damage calcs", f"{calcs:.2f} µs ({calcs / 20 * 1000:.0f} ns each)"),
        ("Numba call overhead, 1 array / tuple of 12", f"{call_one:.2f} / {call_twelve:.2f} µs"),
        ("State size", f"{arr.size} int32, {arr.nbytes / 1024:.1f} KB"),
    ]


def _sizes(report, budget, rng):
    move_x = _sparse(rng, 48 * M_IN, 0.25)
    pok_x = _sparse(rng, 12 * P_FEAT, 0.4)
    field_x = _sparse(rng, FIELD, 0.3)
    probs = np.zeros(CLASSES, dtype=np.float32)
    tmp = np.zeros(1024, dtype=np.float32)
    buf = np.zeros(16384, dtype=np.float32)
    pools = np.zeros(12 * 1024, dtype=np.float32)
    rows = []
    for sizes in _SIZES:
        n = _n_params(*sizes)
        w = rng.normal(0, 0.08, n).astype(np.float32)
        full, cached = (
            _best_us(
                budget, _loop_network, w, move_x, pok_x, field_x, buf, pools, tmp, probs, sizes,
                part, reps=3000 if n > 300_000 else 10_000,
            ) for part in (False, True)
        )
        label = "/".join(str(s) for s in sizes)
        report.metric(f"network/size {label}/full_us", full)
        report.metric(f"network/size {label}/cached_us", cached)
        rows.append((label, f"{n:,}", f"{n * 4 / 1024:.0f} KB", f"{full:.1f} µs", f"{cached:.1f} µs"))
    report.table(("Move / Pokemon / hidden", "Parameters", "Weights", "Full forward",
                  "Move part cached"), rows)


def _flat(report, budget, rng):
    w = rng.normal(0, 0.05, 2315 * 256 + 256 + 256 * 256 + 256 + 256 * 7 + 7).astype(np.float32)
    x = _sparse(rng, 2315, 0.15)
    buf = np.zeros(512, dtype=np.float32)
    probs = np.zeros(CLASSES, dtype=np.float32)
    value = _best_us(budget, _loop_flat, w, x, buf, probs, reps=20_000)
    report.metric("network/flat_mlp_us", value)
    return ("Flat MLP on the shell's 2315 inputs (660k parameters)", f"{value:.1f} µs")


def run(report, budget):
    """The kernels, the engine pieces a leaf needs, and the network at several sizes"""
    report.heading("A network in njit")
    rng = np.random.default_rng(37)
    rows = _kernels(report, budget, rng)
    rows.append(_flat(report, budget, rng))
    rows += _engine_pieces(report, budget)
    report.table(("Piece", "Measured"), rows)
    _sizes(report, budget, rng)

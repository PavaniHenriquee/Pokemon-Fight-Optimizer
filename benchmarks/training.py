"""Training on the GPU and the CPU with the plan's candidate network, one state through torch, the
realistic trainer loop, and training next to data workers. Needs torch (requirements-train.txt).
Inputs are random with the real shapes and a realistic density: these are throughput numbers."""
import threading
import time
import numpy as np
import psutil
import torch
import torch.nn.functional as F
from torch import nn
from NeuralNetwork.models import to_nn_input
from Utils.jit import njit
from benchmarks.data import collect_states
from benchmarks.play import core_cpus
from benchmarks.workers import run_workers

pc = time.perf_counter
INPUTS = 48 * 56 + 12 * 72 + 40  # 3592 floats per state
_BLOCK = 50_000


class Candidate(nn.Module):
    """move 56->32, Pokemon 104->64, head 296->128->128->7, about 64k parameters"""

    def __init__(self):
        super().__init__()
        self.move = nn.Linear(56, 32)
        self.pok = nn.Linear(104, 64)
        self.h1 = nn.Linear(296, 128)
        self.h2 = nn.Linear(128, 128)
        self.out = nn.Linear(128, 7)

    def forward(self, x):
        """Move pools, Pokemon embeddings, actives and bench means, then the head"""
        b = x.shape[0]
        moves = x[:, :48 * 56].reshape(b, 12, 4, 56)
        poks = x[:, 48 * 56:48 * 56 + 12 * 72].reshape(b, 12, 72)
        field = x[:, 48 * 56 + 12 * 72:]
        pools = F.relu(self.move(moves)).mean(dim=2)
        e = F.relu(self.pok(torch.cat((poks, pools), dim=-1)))
        h = torch.cat(
            (e[:, 0], e[:, 6], e[:, 1:6].mean(dim=1), e[:, 7:12].mean(dim=1), field), dim=-1
        )
        return self.out(F.relu(self.h2(F.relu(self.h1(h)))))


def _random_states(n, device):
    x = torch.rand(n, INPUTS, device=device) * (torch.rand(n, INPUTS, device=device) < 0.25)
    y = torch.softmax(torch.rand(n, 7, device=device) * 4, dim=-1)
    return x, y


def _dataset(n, device):
    """n states on a device, filled in blocks so the peak stays close to the final size"""
    x = torch.empty(n, INPUTS, device=device)
    y = torch.empty(n, 7, device=device)
    for start in range(0, n, _BLOCK):
        stop = min(start + _BLOCK, n)
        x[start:stop], y[start:stop] = _random_states(stop - start, device)
    return x, y


def _train_step(model, opt, xb, yb):
    opt.zero_grad(set_to_none=True)
    loss = -(yb * F.log_softmax(model(xb), dim=-1)).sum(dim=-1).mean()
    loss.backward()
    opt.step()


def _train_rate(data, batch, device, seconds):
    """States/s for that long. Data that isn't on the device gets copied there batch by batch"""
    x, y = data
    model = Candidate().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
    steps = 0
    start = pc()
    while pc() - start < seconds:
        idx = torch.randint(0, x.shape[0], (batch,), device=x.device)
        _train_step(model, opt, x[idx].to(device), y[idx].to(device))
        steps += 1
    if device.type == "cuda":
        torch.cuda.synchronize()
    return steps * batch / (pc() - start)


def _rate_rows(report, key, label, data, batches, device, seconds):
    rows = []
    for batch in batches:
        rate = _train_rate(data, batch, device, seconds)
        report.metric(f"training/{key}/{batch}/states_s", rate)
        rows.append((label, batch, f"{rate:,.0f}"))
        report.progress(rows[-1])
    return rows


def _latency(report):
    """One state at a time, the way a search would ask. njit does this in 8-14 µs"""
    torch.set_num_threads(1)
    one = _random_states(1, torch.device("cpu"))[0]
    rows = []
    devices = [("CPU, 1 thread", "cpu", torch.device("cpu"))]
    if torch.cuda.is_available():
        devices.append(("GPU, copied there and back", "gpu", torch.device("cuda")))
    with torch.no_grad():
        for label, key, device in devices:
            model = Candidate().to(device).eval()
            for _ in range(200):
                model(one.to(device)).cpu()
            start = pc()
            for _ in range(5000):
                model(one.to(device)).cpu()
            value = (pc() - start) / 5000 * 1e6
            report.metric(f"training/latency/{key}_us", value)
            rows.append((label, f"{value:.1f} µs"))
    report.table(("One state through torch", "Time"), rows)


@njit
def _encode_batch(states, idx, out, repeat):
    """The shell stands in for Step 3's encoder. repeat=4 is about twice the shell's cost"""
    for b in range(idx.shape[0]):
        x = to_nn_input(states[idx[b]])
        for _ in range(repeat - 1):
            x = to_nn_input(states[idx[b]])
        row = out[b]
        for k in range(x.shape[0]):
            row[k] = x[k]


def _pipeline_rate(states, device, batch, repeat, seconds):
    """The realistic trainer loop in one process: encode, copy, train"""
    model = Candidate().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
    out = np.zeros((batch, INPUTS), dtype=np.float32)
    rng = np.random.default_rng(3)
    y = torch.softmax(torch.rand(batch, 7) * 4, dim=-1).to(device)
    encode = step = 0.0
    steps = 0
    start = pc()
    while pc() - start < seconds:
        t0 = pc()
        _encode_batch(states, rng.integers(0, states.shape[0], batch), out, repeat)
        t1 = pc()
        _train_step(model, opt, torch.from_numpy(out).to(device), y)
        if device.type == "cuda":
            torch.cuda.synchronize()
        encode += t1 - t0
        step += pc() - t1
        steps += 1
    wall = pc() - start
    return steps * batch / wall, encode / (steps * batch) * 1e6, 100 * step / wall


def _pipeline(report, budget, devices):
    states = collect_states(budget.states)
    torch.set_num_threads(8)
    rows = []
    for repeat in (1, 4):
        for label, device, batches in devices:
            for batch in batches:
                rate, encode_us, step_share = _pipeline_rate(
                    states, device, batch, repeat, budget.train_seconds,
                )
                report.metric(f"training/pipeline/{label}/x{repeat}/{batch}/states_s", rate)
                rows.append((
                    label, batch, f"{encode_us:.2f} µs", f"{rate:,.0f}", f"{step_share:.0f}%",
                ))
                report.progress(rows[-1])
    report.table(("Encoding on the fly", "Batch", "Encode per state", "States/s",
                  "Training step share"), rows)


def _next_to_workers(report, budget, vram, ram, device):
    """GPU training on one core while data workers hold the others"""
    cores = core_cpus()
    n = len(cores) - 1
    alone = run_workers("Roark weak", 1000, n, "skip first core", budget.worker_seconds)
    report.metric("training/next_to_workers/workers_alone_decisions_s", alone["decisions_s"])
    shared = {}
    seconds = 15 + 4 * budget.train_seconds

    def workers():
        shared.update(run_workers("Roark weak", 1000, n, "skip first core", seconds))

    thread = threading.Thread(target=workers)
    thread.start()
    time.sleep(10)
    proc = psutil.Process()
    everything = proc.cpu_affinity()
    proc.cpu_affinity(list(range(cores[0], cores[1])))
    torch.set_num_threads(2)
    rows = _rate_rows(report, "next_to_workers/vram", "VRAM", vram, (4096, 16384), device,
                      budget.train_seconds)
    rows += _rate_rows(report, "next_to_workers/ram", "Copied from RAM", ram, (4096, 16384), device,
                       budget.train_seconds)
    proc.cpu_affinity(everything)
    thread.join()
    report.metric("training/next_to_workers/workers_shared_decisions_s", shared["decisions_s"])
    report.text(f"GPU training on core 0 next to {n} pinned data workers. Workers: "
                f"{alone['decisions_s']:.1f} decisions/s alone, "
                f"{shared['decisions_s']:.1f} while the GPU trains.")
    report.table(("Data", "Batch", "States/s"), rows)


def run(report, budget):
    """Everything about training"""
    report.heading("Training")
    cuda = torch.cuda.is_available()
    name = torch.cuda.get_device_name(0) if cuda else "no GPU found"
    parameters = sum(p.numel() for p in Candidate().parameters())
    report.text(f"torch {torch.__version__}, CUDA {torch.version.cuda}, {name}. Candidate network: "
                f"{parameters:,} parameters, {INPUTS} inputs per state.")
    cpu = torch.device("cpu")
    gpu = torch.device("cuda") if cuda else None
    full = budget.full_tables
    ram = _dataset(budget.vram_states // 4, cpu)
    rows = []
    vram = None
    if cuda:
        vram = _dataset(budget.vram_states, gpu)
        rows += _rate_rows(report, "gpu_vram", "GPU, data in VRAM", vram,
                           (1024, 4096, 16384, 65536) if full else (4096, 16384), gpu,
                           budget.train_seconds)
        rows += _rate_rows(report, "gpu_ram", "GPU, batches copied from RAM", ram,
                           (1024, 4096, 16384) if full else (4096,), gpu, budget.train_seconds)
    for threads in (1, 4, 8, 16) if full else (8,):
        torch.set_num_threads(threads)
        rows += _rate_rows(report, f"cpu_{threads}_threads", f"CPU, {threads} threads", ram,
                           (1024, 4096) if full else (4096,), cpu, budget.train_seconds)
    report.table(("Setup, no encoding", "Batch", "States/s"), rows)
    _latency(report)
    devices = [("CPU", cpu, (1024, 4096) if full else (4096,))]
    if cuda:
        devices.insert(0, ("GPU", gpu, (1024, 4096, 16384) if full else (4096,)))
    _pipeline(report, budget, devices)
    if cuda and (full or budget.smoke):
        _next_to_workers(report, budget, vram, ram, gpu)

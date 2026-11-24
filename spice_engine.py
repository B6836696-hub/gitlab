"""ngspice adapter for the ENG29 2121 Lab 04 common-emitter amplifier.

The module owns everything that touches the external solver:

* validating the circuit form values and converting them to SI units,
* generating a SPICE netlist for the reference CE voltage-divider circuit,
* running ``ngspice -b`` in an isolated working directory per run,
* parsing the raw output file into Python values, and
* turning solver failures into explicit errors instead of empty plots.

``app.py`` only dispatches to this module; ``bjt.py`` stays the independent
analytical reference from Lab 03.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import struct
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

ANALYSIS_DC = "dc"
ANALYSIS_AC = "ac"
ANALYSIS_TRAN = "tran"
ANALYSES = (ANALYSIS_DC, ANALYSIS_AC, ANALYSIS_TRAN)

ANALYSIS_LABELS = {
    ANALYSIS_DC: "DC Operating Point",
    ANALYSIS_AC: "AC Frequency Response",
    ANALYSIS_TRAN: "Transient Response",
}

ANALYSIS_DIRECTIVES = {
    ANALYSIS_DC: ".op",
    ANALYSIS_AC: ".ac",
    ANALYSIS_TRAN: ".tran",
}

# Fairchild 2N3904 model distributed with ngspice's example circuits.
# BF is the model's forward beta; the analytical reference uses the same BF so
# the only remaining difference is the device physics solved by ngspice.
MODEL_NAME = "Q2N3904"
MODEL_BETA = 416.4
MODEL_VBE_REFERENCE_V = 0.7
MODEL_CARD = (
    ".model Q2N3904 NPN(IS=6.734f XTI=3 EG=1.11 VAF=74.03 BF=416.4 "
    "NE=1.259 ISE=6.734f IKF=66.78m XTB=1.5 BR=.7371 NC=2 ISC=0 IRB=0 "
    "RC=1 CJC=3.638p MJC=.3085 VJC=.75 FC=.5 CJE=4.493p MJE=.2593 "
    "VJE=.75 TR=239.5n TF=301.2p ITF=.4 VTF=4 XTF=2 RB=10)"
)
MODEL_NOTE = (
    "BJT model 2N3904 (BF=416.4) ที่มากับตัวอย่างของ ngspice; "
    "SPICE แก้สมการอุปกรณ์จริง จึงไม่ใช้ค่า β/VBE จากฟอร์ม Lab 03"
)

DEFAULT_TIMEOUT_S = 60.0
MAX_SIM_CYCLES = 2000
TRAN_CYCLES_SHOWN = 5
AC_SWEEP_START_HZ = 10.0
AC_SWEEP_STOP_HZ = 10e6
AC_POINTS_PER_DECADE = 50

DEFAULTS = {
    "vcc": "12",
    "r1": "100000",
    "r2": "22000",
    "rc": "2200",
    "re": "1000",
    "rl": "10000",
    "cin_uf": "10",
    "cout_uf": "10",
    "amplitude_mv": "10",
    "frequency": "1000",
}

FORM_FIELDS = (
    ("vcc", "VCC", "แรงดันไฟเลี้ยง", "V"),
    ("r1", "R1", "ตัวต้านทานฐานตัวบน", "Ω"),
    ("r2", "R2", "ตัวต้านทานฐานตัวล่าง", "Ω"),
    ("rc", "RC", "ตัวต้านทานคอลเลกเตอร์", "Ω"),
    ("re", "RE", "ตัวต้านทานอิมิตเตอร์", "Ω"),
    ("rl", "RL", "โหลดเอาต์พุต", "Ω"),
    ("cin_uf", "Cin", "คัปปลิงอินพุต", "µF"),
    ("cout_uf", "Cout", "คัปปลิงเอาต์พุต", "µF"),
    ("amplitude_mv", "Vin(pk)", "แอมพลิจูดแหล่งสัญญาณ", "mV"),
    ("frequency", "f", "ความถี่แหล่งสัญญาณ", "Hz"),
)

# name: (minimum, maximum, error message)
_LIMITS = {
    "vcc": (0.1, 60.0, "ต้องอยู่ระหว่าง 0.1 ถึง 60 V"),
    "r1": (1.0, 1e9, "ต้องอยู่ระหว่าง 1 Ω ถึง 1 GΩ"),
    "r2": (1.0, 1e9, "ต้องอยู่ระหว่าง 1 Ω ถึง 1 GΩ"),
    "rc": (1.0, 1e9, "ต้องอยู่ระหว่าง 1 Ω ถึง 1 GΩ"),
    "re": (1.0, 1e9, "ต้องมากกว่า 0 Ω และไม่เกิน 1 GΩ"),
    "rl": (1.0, 1e9, "ต้องอยู่ระหว่าง 1 Ω ถึง 1 GΩ"),
    "cin_uf": (1e-6, 1e6, "ต้องอยู่ระหว่าง 0.000001 ถึง 1,000,000 µF"),
    "cout_uf": (1e-6, 1e6, "ต้องอยู่ระหว่าง 0.000001 ถึง 1,000,000 µF"),
    "amplitude_mv": (0.1, 1000.0, "ต้องอยู่ระหว่าง 0.1 ถึง 1000 mV peak"),
    "frequency": (1.0, 10e6, "ต้องอยู่ระหว่าง 1 Hz ถึง 10 MHz"),
}


class SpiceError(Exception):
    """Base class for problems reported by the SPICE adapter."""


class EngineUnavailable(SpiceError):
    """ngspice was not found on PATH or in the known install locations."""


class SimulationFailed(SpiceError):
    """The solver ran but did not produce usable output."""

    def __init__(
        self,
        message: str,
        *,
        netlist: str = "",
        log: str = "",
        workdir: str = "",
        run_id: str = "",
    ) -> None:
        super().__init__(message)
        self.netlist = netlist
        self.log = log
        self.workdir = workdir
        self.run_id = run_id


@dataclass(frozen=True)
class Circuit:
    vcc_v: float
    r1_ohm: float
    r2_ohm: float
    rc_ohm: float
    re_ohm: float
    rl_ohm: float
    cin_f: float
    cout_f: float
    amplitude_v: float
    frequency_hz: float


@dataclass(frozen=True)
class EngineInfo:
    path: str
    label: str
    version: str


@dataclass(frozen=True)
class DcResult:
    vb_v: float
    ve_v: float
    vc_v: float
    vce_v: float
    vbe_v: float
    ic_a: float
    ib_a: float
    ie_a: float
    region: str
    vcc_v: float


@dataclass(frozen=True)
class AcResult:
    frequency_hz: list[float]
    gain: list[float]
    gain_db: list[float]
    phase_deg: list[float]
    gain_at_1k: float | None
    max_gain: float
    max_gain_db: float
    max_gain_frequency_hz: float
    lower_cutoff_hz: float | None
    upper_cutoff_hz: float | None


@dataclass(frozen=True)
class TranResult:
    time_s: list[float]
    vin_v: list[float]
    vout_v: list[float]
    vin_pp_v: float
    vout_pp_v: float
    gain_pp: float
    inverted: bool
    output_offset_v: float
    settle_s: float
    window_s: float
    cycles_simulated: float
    warning: str


@dataclass(frozen=True)
class SimulationResult:
    analysis: str
    engine: EngineInfo
    model: str
    model_note: str
    netlist: str
    log: str
    workdir: str
    run_id: str
    duration_s: float
    warnings: tuple[str, ...]
    dc: DcResult | None = None
    ac: AcResult | None = None
    tran: TranResult | None = None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _parse_number(text: str) -> float | None:
    try:
        value = float(str(text).strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return value


def validate_circuit(
    raw: Mapping[str, str],
) -> tuple[Circuit | None, dict[str, str], dict[str, str]]:
    """Validate form values and return (circuit, errors, cleaned values).

    The cleaned mapping keeps the user's text for re-rendering the form when a
    single field fails validation.
    """

    errors: dict[str, str] = {}
    values = {name: str(raw.get(name, "") or "").strip() for name, *_ in FORM_FIELDS}
    parsed: dict[str, float] = {}

    for name, *_ in FORM_FIELDS:
        text = values[name]
        if not text:
            errors[name] = "กรุณากรอกเป็นตัวเลข"
            continue
        value = _parse_number(text)
        if value is None:
            errors[name] = "กรุณากรอกเป็นตัวเลข"
            continue
        low, high, message = _LIMITS[name]
        if not (low <= value <= high):
            errors[name] = message
            continue
        parsed[name] = value

    if errors:
        return None, errors, values

    circuit = Circuit(
        vcc_v=parsed["vcc"],
        r1_ohm=parsed["r1"],
        r2_ohm=parsed["r2"],
        rc_ohm=parsed["rc"],
        re_ohm=parsed["re"],
        rl_ohm=parsed["rl"],
        cin_f=parsed["cin_uf"] * 1e-6,
        cout_f=parsed["cout_uf"] * 1e-6,
        amplitude_v=parsed["amplitude_mv"] * 1e-3,
        frequency_hz=parsed["frequency"],
    )
    return circuit, {}, values


# ---------------------------------------------------------------------------
# Netlist
# ---------------------------------------------------------------------------


def _num(value: float) -> str:
    return f"{value:.10g}"


def transient_timing(circuit: Circuit) -> tuple[float, float, float, float, str]:
    """Return (step_s, stop_s, start_s, settle_s, warning).

    The coupling capacitors are uncharged when a transient analysis starts, so
    the window must skip the slow input pole ``Cin * (R1 || R2)``. The number of
    simulated cycles is capped to keep the solver response bounded.
    """

    r_base = 1.0 / (1.0 / circuit.r1_ohm + 1.0 / circuit.r2_ohm)
    r_load = 1.0 / (1.0 / circuit.rc_ohm + 1.0 / circuit.rl_ohm)
    tau = max(circuit.cin_f * r_base, circuit.cout_f * r_load)
    settle = 6.0 * tau
    window = TRAN_CYCLES_SHOWN / circuit.frequency_hz
    warning = ""

    max_settle = MAX_SIM_CYCLES / circuit.frequency_hz
    if settle > max_settle:
        settle = max_settle
        warning = (
            "ความถี่สูงทำให้จำลองได้เพียง "
            f"{MAX_SIM_CYCLES} รอบ จึงอาจยังไม่เข้าสู่สภาวะคงตัวเต็มที่"
        )

    step = 1.0 / (circuit.frequency_hz * 200.0)
    return step, settle + window, settle, settle, warning


def build_netlist(circuit: Circuit, analysis: str) -> str:
    if analysis not in ANALYSES:
        raise ValueError(f"Unknown analysis: {analysis}")

    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "* ENG29 2121 Lab 04 - CE voltage-divider amplifier",
        f"* analysis: {analysis} ({ANALYSIS_DIRECTIVES[analysis]})",
        f"* generated: {created} by spice_engine.py",
        "*",
        "* --- supply and bias network ---",
        f"VCC vcc 0 DC {_num(circuit.vcc_v)}",
        f"R1 vcc base {_num(circuit.r1_ohm)}",
        f"R2 base 0 {_num(circuit.r2_ohm)}",
        f"RC vcc coll {_num(circuit.rc_ohm)}",
        f"RE emit 0 {_num(circuit.re_ohm)}",
        "",
        "* --- NPN common-emitter stage ---",
        "Q1 coll base emit Q2N3904",
        "",
        "* --- input coupling and source ---",
        f"Cin in base {_num(circuit.cin_f)}",
        (
            f"V1 in 0 DC 0 AC 1 SIN(0 {_num(circuit.amplitude_v)} "
            f"{_num(circuit.frequency_hz)})"
        ),
        "",
        "* --- output coupling and load ---",
        f"Cout coll out {_num(circuit.cout_f)}",
        f"RL out 0 {_num(circuit.rl_ohm)}",
        "",
        f"* Fairchild 2N3904 model (BF={MODEL_BETA})",
        MODEL_CARD,
        "",
    ]

    if analysis == ANALYSIS_DC:
        # Device currents are saved explicitly so the UI can show ngspice's own
        # IC/IB/IE values instead of re-deriving everything from node voltages.
        lines += [
            ".save all @q1[ic] @q1[ib] @q1[ie] @q1[vbe]",
            ".op",
        ]
    elif analysis == ANALYSIS_AC:
        lines += [
            ".save v(in) v(base) v(coll) v(emit) v(out)",
            f".ac dec {AC_POINTS_PER_DECADE} "
            f"{_num(AC_SWEEP_START_HZ)} {_num(AC_SWEEP_STOP_HZ)}",
        ]
    else:
        step, stop, start, _settle, _warning = transient_timing(circuit)
        lines += [
            ".save v(in) v(base) v(out)",
            f".tran {_num(step)} {_num(stop)} {_num(start)}",
        ]

    lines += [".end", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Engine discovery and process execution
# ---------------------------------------------------------------------------


def _candidate_paths() -> list[Path]:
    candidates: list[Path] = []
    configured = os.environ.get("NGSPICE_BIN", "").strip()
    if configured:
        configured_path = Path(configured)
        if configured_path.is_dir():
            candidates += [
                configured_path / "ngspice_con.exe",
                configured_path / "ngspice.exe",
                configured_path / "ngspice",
            ]
        else:
            candidates.append(configured_path)

    for name in ("ngspice_con", "ngspice_con.exe", "ngspice", "ngspice.exe"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))

    local_app = os.environ.get("LOCALAPPDATA")
    if local_app:
        base = Path(local_app) / "Programs" / "ngspice"
        for pattern in ("Spice64/bin/ngspice_con.exe", "*/Spice64/bin/ngspice_con.exe"):
            candidates += sorted(base.glob(pattern))
    for base in (Path("C:/Program Files"), Path("C:/Program Files (x86)")):
        if base.exists():
            candidates += sorted(base.glob("ngspice*/Spice64/bin/ngspice_con.exe"))
            candidates += sorted(base.glob("ngspice*/bin/ngspice_con.exe"))
    candidates += [
        Path("/usr/bin/ngspice"),
        Path("/usr/local/bin/ngspice"),
        Path("/opt/homebrew/bin/ngspice"),
    ]
    return candidates


def _probe_engine(path: Path) -> EngineInfo | None:
    if not path.exists():
        return None
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.run(
            [str(path), "-v"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=flags,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = f"{proc.stdout}\n{proc.stderr}"
    match = re.search(r"ngspice-([0-9][0-9A-Za-z.\-]*)", output)
    version = match.group(1) if match else "unknown"
    return EngineInfo(path=str(path), label=f"ngspice {version}", version=version)


def find_engine() -> EngineInfo | None:
    """Locate ngspice without raising so the UI can show engine status."""

    seen: set[str] = set()
    for candidate in _candidate_paths():
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        info = _probe_engine(candidate)
        if info is not None:
            return info
    return None


def _subprocess_flags() -> int:
    if os.name == "nt":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def _read_text(path: Path, limit: int = 200_000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text[-limit:]


def _log_tail(log_text: str, lines: int = 30) -> str:
    rows = [row for row in log_text.splitlines() if row.strip()]
    return "\n".join(rows[-lines:])


def _collect_warnings(log_text: str) -> tuple[str, ...]:
    found: list[str] = []
    for row in log_text.splitlines():
        lowered = row.lower()
        if "warning" in lowered or "singular matrix" in lowered:
            stripped = row.strip()
            if stripped and stripped not in found:
                found.append(stripped)
    return tuple(found[:6])


def _prune_runs(base: Path, keep: int = 30) -> None:
    try:
        runs = sorted(
            (entry for entry in base.iterdir() if entry.is_dir()),
            key=lambda entry: entry.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return
    for stale in runs[keep:]:
        shutil.rmtree(stale, ignore_errors=True)


def run_simulation(
    circuit: Circuit,
    analysis: str,
    *,
    runs_dir: str | Path | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> SimulationResult:
    """Run one analysis in a fresh directory and parse the raw output."""

    if analysis not in ANALYSES:
        raise ValueError(f"Unknown analysis: {analysis}")

    engine = find_engine()
    if engine is None:
        raise EngineUnavailable(
            "ไม่พบ ngspice ในเครื่องนี้ — ติดตั้ง ngspice แล้วเพิ่มโฟลเดอร์ bin "
            "ลง PATH หรือตั้งค่า environment variable NGSPICE_BIN"
        )

    base = Path(
        runs_dir
        if runs_dir is not None
        else Path(__file__).resolve().parent / "runs"
    )
    base.mkdir(parents=True, exist_ok=True)
    _prune_runs(base)

    run_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    workdir = base / run_id
    workdir.mkdir(parents=True, exist_ok=False)

    netlist = build_netlist(circuit, analysis)
    netlist_path = workdir / "circuit.cir"
    netlist_path.write_text(netlist, encoding="ascii", newline="\n")
    log_path = workdir / "run.log"
    raw_path = workdir / "run.raw"

    command = [
        engine.path,
        "-b",
        "-o",
        str(log_path),
        "-r",
        str(raw_path),
        str(netlist_path),
    ]

    started = time.perf_counter()
    try:
        proc = subprocess.run(
            command,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            creationflags=_subprocess_flags(),
        )
    except subprocess.TimeoutExpired as exc:
        log_text = _read_text(log_path)
        raise SimulationFailed(
            f"ngspice ใช้เวลาเกิน {timeout_s:.0f} วินาที จึงหยุดการจำลอง",
            netlist=netlist,
            log=_log_tail(log_text),
            workdir=str(workdir),
            run_id=run_id,
        ) from exc
    except OSError as exc:
        raise SimulationFailed(
            f"เรียก ngspice ไม่สำเร็จ: {exc}",
            netlist=netlist,
            workdir=str(workdir),
            run_id=run_id,
        ) from exc

    duration = time.perf_counter() - started
    console = (proc.stdout or "") + (proc.stderr or "")
    log_text = _read_text(log_path)
    if not log_text.strip() and console.strip():
        log_text = console
        log_path.write_text(console, encoding="utf-8")

    if proc.returncode != 0:
        raise SimulationFailed(
            f"ngspice จบด้วยรหัส {proc.returncode} — ไม่มีผลจำลองที่ใช้ได้",
            netlist=netlist,
            log=_log_tail(log_text),
            workdir=str(workdir),
            run_id=run_id,
        )
    if not raw_path.exists() or raw_path.stat().st_size == 0:
        raise SimulationFailed(
            "ngspice ไม่ได้เขียนไฟล์ผลลัพธ์ (raw file ว่าง) — ตรวจ netlist ใน log",
            netlist=netlist,
            log=_log_tail(log_text),
            workdir=str(workdir),
            run_id=run_id,
        )

    try:
        plot = parse_raw(raw_path)
    except (OSError, ValueError) as exc:
        raise SimulationFailed(
            f"อ่านผลลัพธ์ของ ngspice ไม่สำเร็จ: {exc}",
            netlist=netlist,
            log=_log_tail(log_text),
            workdir=str(workdir),
            run_id=run_id,
        ) from exc

    dc = ac = tran = None
    try:
        if analysis == ANALYSIS_DC:
            dc = extract_dc(plot, circuit)
        elif analysis == ANALYSIS_AC:
            ac = extract_ac(plot)
        else:
            tran = extract_tran(plot, circuit)
    except ValueError as exc:
        raise SimulationFailed(
            f"ผลลัพธ์จาก ngspice ไม่ครบตามที่ต้องใช้: {exc}",
            netlist=netlist,
            log=_log_tail(log_text),
            workdir=str(workdir),
            run_id=run_id,
        ) from exc

    warnings = _collect_warnings(log_text)
    if tran is not None and tran.warning and tran.warning not in warnings:
        warnings += (tran.warning,)

    result = SimulationResult(
        analysis=analysis,
        engine=engine,
        model=MODEL_NAME,
        model_note=MODEL_NOTE,
        netlist=netlist,
        log=_log_tail(log_text, 60),
        workdir=str(workdir),
        run_id=run_id,
        duration_s=duration,
        warnings=warnings,
        dc=dc,
        ac=ac,
        tran=tran,
    )
    (workdir / "meta.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "analysis": analysis,
                "engine": engine.label,
                "model": MODEL_NAME,
                "circuit": circuit.__dict__,
                "duration_s": duration,
                "warnings": list(warnings),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return result


# ---------------------------------------------------------------------------
# Raw file parsing and result extraction
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RawPlot:
    plotname: str
    flags: str
    variables: tuple[str, ...]
    points: int
    # Real quantities keep a zero imaginary part, so one column type works for
    # both .op/.tran (real) and .ac (complex) raw data.
    columns: dict[str, list[complex]]


def _parse_ascii_values(body: str, variables: int, points: int, complex_data: bool):
    values: list[float] = []
    for raw_line in body.splitlines():
        if not raw_line.strip():
            continue
        match = re.match(r"^\d+\t+(.*)$", raw_line)
        token = match.group(1).strip() if match else raw_line.strip()
        if not token:
            continue
        if complex_data:
            real_text, _, imag_text = token.partition(",")
            values.append(float(real_text))
            values.append(float(imag_text))
        else:
            values.append(float(token))
    expected = points * variables * (2 if complex_data else 1)
    if len(values) != expected:
        raise ValueError(
            f"จำนวนค่าที่อ่านได้ {len(values)} ไม่ตรงกับที่ประกาศไว้ {expected}"
        )
    return values


def parse_raw(path: str | Path) -> RawPlot:
    """Parse one ngspice raw file, ASCII or binary, real or complex."""

    data = Path(path).read_bytes()
    binary = b"Binary:" in data
    marker = b"Binary:" if binary else b"Values:"
    if marker not in data:
        raise ValueError("ไม่พบหัวข้อมูล Values:/Binary: ในไฟล์ raw")

    head_bytes, body = data.split(marker, 1)
    head = head_bytes.decode("utf-8", "replace").replace("\r\n", "\n")

    meta: dict[str, str] = {}
    variables: list[str] = []
    in_variables = False
    for line in head.splitlines():
        if line.startswith("Variables:"):
            in_variables = True
            continue
        if in_variables:
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 2:
                variables.append(parts[1])
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()

    points = int(meta.get("No. Points", "0") or 0)
    declared = int(meta.get("No. Variables", "0") or 0)
    if not variables or len(variables) != declared or points <= 0:
        raise ValueError("หัวไฟล์ raw ไม่สมบูรณ์")

    complex_data = "complex" in meta.get("Flags", "").lower()
    if binary:
        body = body.lstrip(b"\r\n")
        count = points * declared * (2 if complex_data else 1)
        needed = count * 8
        if len(body) < needed:
            raise ValueError("ข้อมูล Binary สั้นกว่าที่ประกาศไว้")
        numbers = struct.unpack("<" + "d" * count, body[:needed])
    else:
        numbers = _parse_ascii_values(
            body.decode("utf-8", "replace"), declared, points, complex_data
        )

    columns: dict[str, list[complex]] = {name: [] for name in variables}
    stride = 2 if complex_data else 1
    for point in range(points):
        offset = point * declared * stride
        for index, name in enumerate(variables):
            position = offset + index * stride
            if complex_data:
                columns[name].append(
                    complex(numbers[position], numbers[position + 1])
                )
            else:
                columns[name].append(complex(numbers[position], 0.0))

    return RawPlot(
        plotname=meta.get("Plotname", ""),
        flags=meta.get("Flags", ""),
        variables=tuple(variables),
        points=points,
        columns=columns,
    )


def _column(plot: RawPlot, *candidates: str) -> list[complex]:
    for name in candidates:
        if name in plot.columns:
            return plot.columns[name]
    raise ValueError(f"ไม่พบตัวแปร {candidates[0]} ในผล ngspice")


def _single(plot: RawPlot, *candidates: str) -> float:
    column = _column(plot, *candidates)
    if not column:
        raise ValueError(f"ตัวแปร {candidates[0]} ว่าง")
    return float(column[0].real)


def _classify(vce_v: float, ic_a: float) -> str:
    if ic_a <= 1e-9:
        return "cutoff"
    if vce_v <= 0.2:
        return "saturation"
    return "active"


def extract_dc(plot: RawPlot, circuit: Circuit) -> DcResult:
    vb = _single(plot, "v(base)")
    ve = _single(plot, "v(emit)")
    vc = _single(plot, "v(coll)")
    vce = vc - ve

    try:
        ic = abs(_single(plot, "i(@q1[ic])"))
        ib = abs(_single(plot, "i(@q1[ib])"))
        ie = abs(_single(plot, "i(@q1[ie])"))
        vbe = _single(plot, "v(@q1[vbe])")
    except ValueError:
        # Fallback: derive the currents from the bias resistors when an
        # ngspice build does not expose device parameters in the raw file.
        ic = abs((circuit.vcc_v - vc) / circuit.rc_ohm)
        ie = abs(ve / circuit.re_ohm)
        ib = abs(ie - ic)
        vbe = vb - ve

    if not all(math.isfinite(value) for value in (vb, ve, vc, vce, ic, ib, ie, vbe)):
        raise ValueError("ค่าจุดทำงานมีค่าไม่จำกัด")

    return DcResult(
        vb_v=vb,
        ve_v=ve,
        vc_v=vc,
        vce_v=vce,
        vbe_v=vbe,
        ic_a=ic,
        ib_a=ib,
        ie_a=ie,
        region=_classify(vce, ic),
        vcc_v=circuit.vcc_v,
    )


def _unwrap_phase(values: list[float]) -> list[float]:
    if not values:
        return []
    result = [values[0]]
    for previous, current in zip(values, values[1:]):
        delta = current - previous
        while delta > 180:
            current -= 360
            delta -= 360
        while delta < -180:
            current += 360
            delta += 360
        result.append(current)
    return result


def _interpolate_log(f1: float, y1: float, f2: float, y2: float, target: float) -> float:
    if f1 <= 0 or f2 <= 0 or y1 == y2:
        return f2
    ratio = (target - y1) / (y2 - y1)
    log_value = math.log10(f1) + ratio * (math.log10(f2) - math.log10(f1))
    return 10**log_value


def extract_ac(plot: RawPlot) -> AcResult:
    frequency = [value.real for value in _column(plot, "frequency")]
    vin = _column(plot, "v(in)")
    vout = _column(plot, "v(out)")
    if not frequency or len(vin) != len(frequency) or len(vout) != len(frequency):
        raise ValueError("ข้อมูล AC ไม่ครบ")

    gains: list[float] = []
    phases: list[float] = []
    for index, _freq in enumerate(frequency):
        denominator = abs(vin[index])
        numerator = abs(vout[index])
        gain = numerator / denominator if denominator > 0 else 0.0
        gains.append(gain)
        phases.append(
            math.degrees(math.atan2(vout[index].imag, vout[index].real)
                         - math.atan2(vin[index].imag, vin[index].real))
        )

    phases = _unwrap_phase(phases)
    gain_db = [20 * math.log10(gain) if gain > 0 else -240.0 for gain in gains]
    max_gain = max(gains)
    max_index = gains.index(max_gain)
    threshold = max_gain / math.sqrt(2)

    lower: float | None = None
    if gains[0] < threshold:
        for index in range(1, len(gains)):
            if gains[index] >= threshold:
                lower = _interpolate_log(
                    frequency[index - 1], gains[index - 1],
                    frequency[index], gains[index], threshold,
                )
                break

    upper: float | None = None
    for index in range(len(gains) - 1, 0, -1):
        if gains[index] >= threshold:
            if index < len(gains) - 1:
                upper = _interpolate_log(
                    frequency[index], gains[index],
                    frequency[index + 1], gains[index + 1], threshold,
                )
            break

    nearest = min(range(len(frequency)), key=lambda i: abs(math.log10(frequency[i] / 1000)))
    gain_at_1k = gains[nearest] if abs(math.log10(frequency[nearest] / 1000)) <= 0.2 else None

    return AcResult(
        frequency_hz=frequency,
        gain=gains,
        gain_db=gain_db,
        phase_deg=phases,
        gain_at_1k=gain_at_1k,
        max_gain=max_gain,
        max_gain_db=gain_db[max_index],
        max_gain_frequency_hz=frequency[max_index],
        lower_cutoff_hz=lower,
        upper_cutoff_hz=upper,
    )


def extract_tran(plot: RawPlot, circuit: Circuit) -> TranResult:
    time_s = [value.real for value in _column(plot, "time")]
    vin = [value.real for value in _column(plot, "v(in)")]
    vout = [value.real for value in _column(plot, "v(out)")]
    if len(vin) != len(time_s) or len(vout) != len(time_s) or not time_s:
        raise ValueError("ข้อมูล Transient ไม่ครบ")

    tail_start = time_s[-1] - 2.0 / circuit.frequency_hz
    indices = [i for i, value in enumerate(time_s) if value >= tail_start]
    if len(indices) < 3:
        indices = list(range(len(time_s)))

    vin_tail = [vin[i] for i in indices]
    vout_tail = [vout[i] for i in indices]
    vin_pp = max(vin_tail) - min(vin_tail)
    vout_pp = max(vout_tail) - min(vout_tail)
    offset = sum(vout_tail) / len(vout_tail)

    mean_vin = sum(vin_tail) / len(vin_tail)
    mean_vout = sum(vout_tail) / len(vout_tail)
    covariance = sum(
        (vin_tail[i] - mean_vin) * (vout_tail[i] - mean_vout)
        for i in range(len(vin_tail))
    )
    inverted = covariance < 0

    _step, _stop, start, settle, warning = transient_timing(circuit)

    return TranResult(
        time_s=time_s,
        vin_v=vin,
        vout_v=vout,
        vin_pp_v=vin_pp,
        vout_pp_v=vout_pp,
        gain_pp=(vout_pp / vin_pp) if vin_pp > 0 else 0.0,
        inverted=inverted,
        output_offset_v=offset,
        settle_s=settle,
        window_s=time_s[-1] - start,
        cycles_simulated=settle * circuit.frequency_hz,
        warning=warning,
    )

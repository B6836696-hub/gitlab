import math
from dataclasses import dataclass
from typing import Mapping

FIELD_NAMES = ("vcc", "r1", "r2", "rc", "re", "beta", "vbe")
MAX_INPUT = 1e12


@dataclass(frozen=True)
class BiasInputs:
    vcc_v: float
    r1_ohm: float
    r2_ohm: float
    rc_ohm: float
    re_ohm: float
    beta: float
    vbe_v: float


def validate_inputs(
    raw: Mapping[str, str],
) -> tuple[BiasInputs | None, dict[str, str]]:
    errors: dict[str, str] = {}
    parsed: dict[str, float] = {}

    for name in FIELD_NAMES:
        text = str(raw.get(name, "") or "").strip()
        if not text:
            errors[name] = "กรุณากรอกเป็นตัวเลข"
            continue
        try:
            value = float(text)
        except (TypeError, ValueError):
            errors[name] = "กรุณากรอกเป็นตัวเลข"
            continue
        if not math.isfinite(value):
            errors[name] = "ต้องเป็นจำนวนจำกัด"
            continue
        if abs(value) > MAX_INPUT:
            errors[name] = "ต้องมีค่าไม่เกิน 1e12"
            continue
        parsed[name] = value

    if "vcc" in parsed and parsed["vcc"] <= 0:
        errors["vcc"] = "ต้องมากกว่า 0 V"
    for name in ("r1", "r2", "rc", "re"):
        if name in parsed and parsed[name] <= 0:
            errors[name] = "ต้องมากกว่า 0 Ω"
    if "beta" in parsed and parsed["beta"] < 1:
        errors["beta"] = "ต้องมีค่าอย่างน้อย 1"
    if "vcc" in parsed and "vbe" in parsed and not (0 <= parsed["vbe"] < parsed["vcc"]):
        errors["vbe"] = "ต้องอยู่ระหว่าง 0 ถึง VCC"

    if errors:
        return None, errors

    return (
        BiasInputs(
            vcc_v=parsed["vcc"],
            r1_ohm=parsed["r1"],
            r2_ohm=parsed["r2"],
            rc_ohm=parsed["rc"],
            re_ohm=parsed["re"],
            beta=parsed["beta"],
            vbe_v=parsed["vbe"],
        ),
        {},
    )


VCE_SAT_V = 0.2


def _ensure_finite(*values: float) -> None:
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Non-finite operating point")


@dataclass(frozen=True)
class OperatingPoint:
    vbb_v: float
    rb_ohm: float
    ib_a: float
    ic_a: float
    ie_a: float
    ve_v: float
    vb_v: float
    vc_v: float
    vce_v: float
    region: str
    ic_sat_a: float | None


def classify_region(ib_a: float, vce_v: float) -> str:
    if ib_a <= 0:
        return "cutoff"
    if vce_v <= VCE_SAT_V:
        return "saturation"
    return "active"


def calculate_operating_point(inputs: BiasInputs) -> OperatingPoint:
    vbb = inputs.vcc_v * inputs.r2_ohm / (inputs.r1_ohm + inputs.r2_ohm)
    rb = inputs.r1_ohm * inputs.r2_ohm / (inputs.r1_ohm + inputs.r2_ohm)
    ib = (vbb - inputs.vbe_v) / (rb + (inputs.beta + 1) * inputs.re_ohm)

    if ib <= 0:
        _ensure_finite(vbb, rb, inputs.vcc_v)
        return OperatingPoint(
            vbb_v=vbb,
            rb_ohm=rb,
            ib_a=0.0,
            ic_a=0.0,
            ie_a=0.0,
            ve_v=0.0,
            vb_v=vbb,
            vc_v=inputs.vcc_v,
            vce_v=inputs.vcc_v,
            region="cutoff",
            ic_sat_a=None,
        )

    ic = inputs.beta * ib
    ie = (inputs.beta + 1) * ib
    ve = ie * inputs.re_ohm
    vb = ve + inputs.vbe_v
    vc = inputs.vcc_v - ic * inputs.rc_ohm
    vce = vc - ve
    region = classify_region(ib, vce)
    ic_sat = None
    if region == "saturation":
        ic_sat = (inputs.vcc_v - VCE_SAT_V) / (inputs.rc_ohm + inputs.re_ohm)

    values = (vbb, rb, ib, ic, ie, ve, vb, vc, vce)
    _ensure_finite(*values)
    if ic_sat is not None:
        _ensure_finite(ic_sat)

    return OperatingPoint(
        vbb_v=vbb,
        rb_ohm=rb,
        ib_a=ib,
        ic_a=ic,
        ie_a=ie,
        ve_v=ve,
        vb_v=vb,
        vc_v=vc,
        vce_v=vce,
        region=region,
        ic_sat_a=ic_sat,
    )


REL_TOL = 1e-9


def solve_linear_system(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    n = len(matrix)
    a = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-18:
            raise ValueError("Singular matrix")
        a[col], a[pivot] = a[pivot], a[col]
        for r in range(col + 1, n):
            factor = a[r][col] / a[col][col]
            for c in range(col, n + 1):
                a[r][c] -= factor * a[col][c]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (a[i][n] - sum(a[i][j] * x[j] for j in range(i + 1, n))) / a[i][i]
    return x


def calculate_nodal_operating_point(inputs: BiasInputs) -> OperatingPoint:
    r1, r2 = inputs.r1_ohm, inputs.r2_ohm
    rc, re, beta = inputs.rc_ohm, inputs.re_ohm, inputs.beta

    matrix = [
        [1 / r1 + 1 / r2, 0.0, 0.0, 1.0],
        [0.0, 1 / re, 0.0, -(beta + 1)],
        [0.0, 0.0, 1 / rc, beta],
        [1.0, -1.0, 0.0, 0.0],
    ]
    rhs = [inputs.vcc_v / r1, 0.0, inputs.vcc_v / rc, inputs.vbe_v]
    vb, ve, vc, ib = solve_linear_system(matrix, rhs)

    vbb = inputs.vcc_v * r2 / (r1 + r2)
    rb = r1 * r2 / (r1 + r2)

    if ib <= 0:
        _ensure_finite(vbb, rb, inputs.vcc_v)
        return OperatingPoint(
            vbb_v=vbb,
            rb_ohm=rb,
            ib_a=0.0,
            ic_a=0.0,
            ie_a=0.0,
            ve_v=0.0,
            vb_v=vbb,
            vc_v=inputs.vcc_v,
            vce_v=inputs.vcc_v,
            region="cutoff",
            ic_sat_a=None,
        )

    ic = beta * ib
    ie = (beta + 1) * ib
    vce = vc - ve
    region = classify_region(ib, vce)
    ic_sat = None
    if region == "saturation":
        ic_sat = (inputs.vcc_v - VCE_SAT_V) / (rc + re)

    values = (vbb, rb, ib, ic, ie, ve, vb, vc, vce)
    _ensure_finite(*values)
    if ic_sat is not None:
        _ensure_finite(ic_sat)

    return OperatingPoint(
        vbb_v=vbb,
        rb_ohm=rb,
        ib_a=ib,
        ic_a=ic,
        ie_a=ie,
        ve_v=ve,
        vb_v=vb,
        vc_v=vc,
        vce_v=vce,
        region=region,
        ic_sat_a=ic_sat,
    )


@dataclass(frozen=True)
class ComparisonRow:
    name: str
    unit: str
    method_a: float
    method_b: float
    abs_diff: float
    rel_diff: float


@dataclass(frozen=True)
class Comparison:
    rows: list[ComparisonRow]
    max_rel_diff: float
    matched: bool


COMPARISON_FIELDS = (
    ("ib_a", "IB", "A"), ("ic_a", "IC", "A"), ("ie_a", "IE", "A"),
    ("vb_v", "VB", "V"), ("ve_v", "VE", "V"), ("vc_v", "VC", "V"),
    ("vce_v", "VCE", "V"),
)


def compare_operating_points(a: OperatingPoint, b: OperatingPoint) -> Comparison:
    rows: list[ComparisonRow] = []
    max_rel_diff = 0.0
    for attr, name, unit in COMPARISON_FIELDS:
        value_a = getattr(a, attr)
        value_b = getattr(b, attr)
        abs_diff = abs(value_a - value_b)
        rel_diff = abs_diff / max(abs(value_a), abs(value_b), 1e-12)
        if not all(
            math.isfinite(value)
            for value in (value_a, value_b, abs_diff, rel_diff)
        ):
            rel_diff = float("inf")
        max_rel_diff = max(max_rel_diff, rel_diff)
        rows.append(
            ComparisonRow(
                name=name,
                unit=unit,
                method_a=value_a,
                method_b=value_b,
                abs_diff=abs_diff,
                rel_diff=rel_diff,
            )
        )
    return Comparison(rows=rows, max_rel_diff=max_rel_diff, matched=max_rel_diff <= REL_TOL)

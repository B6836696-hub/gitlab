import math
from dataclasses import dataclass
from typing import Mapping

FIELD_NAMES = ("vcc", "r1", "r2", "rc", "re", "beta", "vbe")


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

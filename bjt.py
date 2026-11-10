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

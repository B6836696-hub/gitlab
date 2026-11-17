from flask import Flask, render_template, request

from bjt import (
    MODE_DIVIDER,
    MODE_EMITTER,
    MODE_FIELDS,
    MODE_FIXED,
    MODES,
    VCE_SAT_V,
    calculate_emitter_bias,
    calculate_fixed_bias,
    calculate_nodal_operating_point,
    calculate_operating_point,
    compare_operating_points,
    validate_emitter_bias,
    validate_fixed_bias,
    validate_inputs,
)

MODE_DEFAULTS = {
    MODE_DIVIDER: {
        "vcc": "12",
        "r1": "47000",
        "r2": "10000",
        "rc": "2200",
        "re": "1000",
        "beta": "150",
        "vbe": "0.7",
    },
    MODE_FIXED: {
        "vcc": "12",
        "rb": "1000000",
        "rc": "2200",
        "beta": "150",
        "vbe": "0.7",
    },
    MODE_EMITTER: {
        "vcc": "12",
        "rb": "1000000",
        "rc": "2200",
        "re": "1000",
        "beta": "150",
        "vbe": "0.7",
    },
}

DEFAULTS = MODE_DEFAULTS[MODE_DIVIDER]

MODE_LABELS = {
    MODE_DIVIDER: "Voltage Divider Bias",
    MODE_FIXED: "Fixed Bias",
    MODE_EMITTER: "Emitter Bias",
}

MODE_SHORT_LABELS = {
    MODE_DIVIDER: "Divider",
    MODE_FIXED: "Fixed",
    MODE_EMITTER: "Emitter",
}

FIELD_DEFS = {
    "vcc": ("VCC", "แรงดันไฟเลี้ยง", "V"),
    "r1": ("R1", "ตัวต้านทานฐานตัวบน", "Ω"),
    "r2": ("R2", "ตัวต้านทานฐานตัวล่าง", "Ω"),
    "rc": ("RC", "ตัวต้านทานคอลเลกเตอร์", "Ω"),
    "re": ("RE", "ตัวต้านทานอิมิตเตอร์", "Ω"),
    "rb": ("RB", "ตัวต้านทานฐาน", "Ω"),
    "beta": ("β", "อัตราขยายกระแส (hFE)", ""),
    "vbe": ("VBE", "แรงดันฐาน-อิมิตเตอร์", "V"),
}

FORM_FIELDS = {
    mode: [(name, *FIELD_DEFS[name]) for name in MODE_FIELDS[mode]]
    for mode in MODES
}


def _trim(value: float) -> str:
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    if text in ("", "-0", "-"):
        return "0"
    return text


def format_current(value_a: float) -> str:
    if value_a == 0:
        return "0 mA"
    if abs(value_a) >= 1e-3:
        return f"{_trim(value_a * 1e3)} mA"
    return f"{_trim(value_a * 1e6)} µA"


def format_voltage(value_v: float) -> str:
    return f"{_trim(value_v)} V"


def format_resistance(value_ohm: float) -> str:
    text = f"{value_ohm:,.4f}".rstrip("0").rstrip(".")
    if text in ("", "-0", "-"):
        text = "0"
    return f"{text} Ω"


def _validate_mode(mode: str, values: dict[str, str]):
    if mode == MODE_FIXED:
        return validate_fixed_bias(values)
    if mode == MODE_EMITTER:
        return validate_emitter_bias(values)
    return validate_inputs(values)


def _calculate_mode(mode: str, inputs):
    if mode == MODE_FIXED:
        return calculate_fixed_bias(inputs)
    if mode == MODE_EMITTER:
        return calculate_emitter_bias(inputs)
    return calculate_operating_point(inputs)


def create_app() -> Flask:
    app = Flask(__name__)
    app.jinja_env.filters["current"] = format_current
    app.jinja_env.filters["voltage"] = format_voltage
    app.jinja_env.filters["resistance"] = format_resistance

    @app.route("/", methods=["GET", "POST"])
    def index():
        errors: dict[str, str] = {}
        raw_mode = request.values.get("mode")
        mode = (raw_mode or MODE_DIVIDER).strip().lower()
        if mode not in MODES:
            errors["_form"] = "ไม่รู้จักโหมดไบอัสที่เลือก กรุณาเลือกจากรายการ"
            mode = MODE_DIVIDER

        values = dict(MODE_DEFAULTS[mode])
        result = None
        comparison = None

        if request.method == "GET":
            for name in MODE_FIELDS[mode]:
                supplied = request.args.get(name)
                if supplied is not None and supplied.strip():
                    values[name] = supplied
        else:
            values = {
                name: request.form.get(name, "") for name in MODE_FIELDS[mode]
            }
            if not errors:
                inputs, field_errors = _validate_mode(mode, values)
                errors.update(field_errors)
                if inputs is not None:
                    try:
                        result = _calculate_mode(mode, inputs)
                        if mode == MODE_DIVIDER:
                            independent = calculate_nodal_operating_point(inputs)
                            comparison = compare_operating_points(
                                result, independent
                            )
                    except ValueError:
                        errors = {
                            "_form": "ไม่สามารถคำนวณจุดทำงานได้ กรุณาตรวจสอบค่าอินพุต"
                        }
                        result = None
                        comparison = None

        return render_template(
            "index.html",
            mode=mode,
            mode_label=MODE_LABELS[mode],
            mode_options=[
                (value, MODE_LABELS[value], MODE_SHORT_LABELS[value])
                for value in MODES
            ],
            fields=FORM_FIELDS[mode],
            values=values,
            errors=errors,
            result=result,
            comparison=comparison,
            vce_sat=VCE_SAT_V,
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)

from flask import Flask, render_template, request

from bjt import (
    FIELD_NAMES,
    VCE_SAT_V,
    calculate_nodal_operating_point,
    calculate_operating_point,
    compare_operating_points,
    validate_inputs,
)

DEFAULTS = {
    "vcc": "12",
    "r1": "47000",
    "r2": "10000",
    "rc": "2200",
    "re": "1000",
    "beta": "150",
    "vbe": "0.7",
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


def create_app() -> Flask:
    app = Flask(__name__)
    app.jinja_env.filters["current"] = format_current
    app.jinja_env.filters["voltage"] = format_voltage

    @app.route("/", methods=["GET", "POST"])
    def index():
        values = dict(DEFAULTS)
        errors: dict[str, str] = {}
        result = None
        comparison = None

        if request.method == "POST":
            values = {name: request.form.get(name, "") for name in FIELD_NAMES}
            inputs, errors = validate_inputs(values)
            if inputs is not None:
                try:
                    result = calculate_operating_point(inputs)
                    independent = calculate_nodal_operating_point(inputs)
                    comparison = compare_operating_points(result, independent)
                except ValueError:
                    errors = {
                        "_form": "ไม่สามารถคำนวณจุดทำงานได้ กรุณาตรวจสอบค่าอินพุต"
                    }

        return render_template(
            "index.html",
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

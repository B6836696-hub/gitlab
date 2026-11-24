import math
import re
from pathlib import Path

from flask import Flask, abort, render_template, request, send_from_directory

import charts
import spice_engine
from bjt import (
    MODE_DIVIDER,
    MODE_EMITTER,
    MODE_FIELDS,
    MODE_FIXED,
    MODES,
    VCE_SAT_V,
    BiasInputs,
    calculate_emitter_bias,
    calculate_fixed_bias,
    calculate_nodal_operating_point,
    calculate_operating_point,
    compare_operating_points,
    validate_emitter_bias,
    validate_fixed_bias,
    validate_inputs,
)
from spice_engine import (
    ANALYSIS_AC,
    ANALYSIS_DC,
    ANALYSIS_LABELS,
    ANALYSIS_TRAN,
    ANALYSES,
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


def format_ohm_short(value: float) -> str:
    if value >= 1e6:
        return f"{value / 1e6:g} MΩ"
    if value >= 1e3:
        return f"{value / 1e3:g} kΩ"
    return f"{value:g} Ω"


def format_frequency(value_hz: float) -> str:
    if value_hz >= 1e6:
        return f"{value_hz / 1e6:g} MHz"
    if value_hz >= 1e3:
        return f"{value_hz / 1e3:g} kHz"
    return f"{value_hz:g} Hz"


def format_capacitance_uf(value_uf: float) -> str:
    if value_uf < 0.001:
        return f"{value_uf * 1000:g} nF"
    return f"{value_uf:g} µF"


def format_millivolts(value_mv: float) -> str:
    return f"{value_mv:g} mV"


def format_volts_as_mv(value_v: float) -> str:
    return f"{value_v * 1e3:g} mV"


def format_gain(value: float) -> str:
    return f"{value:.3g}×"


def format_decibels(value: float) -> str:
    return f"{value:.2f} dB"


def format_degrees(value: float) -> str:
    return f"{value:.1f}°"


def format_ms(value_s: float) -> str:
    return f"{value_s * 1e3:.4g} ms"


def _as_float(text) -> float | None:
    try:
        value = float(str(text).strip())
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


SIM_FIELD_UNITS = {name: unit for name, _symbol, _label, unit in spice_engine.FORM_FIELDS}


def build_sim_specs(values: dict[str, str]) -> dict[str, str]:
    """Human-readable component values for the schematic and spec list."""

    specs: dict[str, str] = {}
    for name, _symbol, _label, unit in spice_engine.FORM_FIELDS:
        value = _as_float(values.get(name))
        if value is None:
            specs[name] = "—"
        elif unit == "Ω":
            specs[name] = format_ohm_short(value)
        elif unit == "µF":
            specs[name] = format_capacitance_uf(value)
        elif unit == "mV":
            specs[name] = format_millivolts(value)
        elif unit == "Hz":
            specs[name] = format_frequency(value)
        else:
            specs[name] = f"{value:g} {unit}"
    return specs


def analytical_reference(circuit: spice_engine.Circuit):
    """Lab 03 analytical model fed with the same components and model BF."""

    inputs = BiasInputs(
        vcc_v=circuit.vcc_v,
        r1_ohm=circuit.r1_ohm,
        r2_ohm=circuit.r2_ohm,
        rc_ohm=circuit.rc_ohm,
        re_ohm=circuit.re_ohm,
        beta=spice_engine.MODEL_BETA,
        vbe_v=spice_engine.MODEL_VBE_REFERENCE_V,
    )
    return calculate_operating_point(inputs)


DC_COMPARISON_ROWS = (
    ("IC", "ic_a", "A"),
    ("IB", "ib_a", "A"),
    ("IE", "ie_a", "A"),
    ("VB", "vb_v", "V"),
    ("VE", "ve_v", "V"),
    ("VC", "vc_v", "V"),
    ("VCE", "vce_v", "V"),
)


def compare_spice_dc(spice_dc, analytical):
    rows = []
    for name, attr, unit in DC_COMPARISON_ROWS:
        spice_value = getattr(spice_dc, attr)
        ref_value = getattr(analytical, attr)
        diff = spice_value - ref_value
        rel = abs(diff) / max(abs(spice_value), abs(ref_value), 1e-12)
        rows.append(
            {
                "name": name,
                "unit": unit,
                "spice": spice_value,
                "reference": ref_value,
                "diff": diff,
                "rel": rel,
            }
        )
    return rows


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
    app.config.setdefault(
        "SIM_RUNS_DIR", str(Path(app.root_path) / "runs")
    )
    app.jinja_env.filters["current"] = format_current
    app.jinja_env.filters["voltage"] = format_voltage
    app.jinja_env.filters["resistance"] = format_resistance
    app.jinja_env.filters["ohm"] = format_ohm_short
    app.jinja_env.filters["hz"] = format_frequency
    app.jinja_env.filters["uf"] = format_capacitance_uf
    app.jinja_env.filters["mv"] = format_millivolts
    app.jinja_env.filters["mvv"] = format_volts_as_mv
    app.jinja_env.filters["gain"] = format_gain
    app.jinja_env.filters["db"] = format_decibels
    app.jinja_env.filters["deg"] = format_degrees
    app.jinja_env.filters["ms"] = format_ms

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

    @app.route("/simulator", methods=["GET", "POST"])
    def simulator():
        analysis = (request.values.get("analysis") or ANALYSIS_DC).strip().lower()
        errors: dict[str, str] = {}
        if analysis not in ANALYSES:
            errors["_form"] = "ไม่รู้จักโหมดการวิเคราะห์ที่เลือก กรุณาเลือกใหม่"
            analysis = ANALYSIS_DC

        values = dict(spice_engine.DEFAULTS)
        if request.method == "GET":
            for name, *_rest in spice_engine.FORM_FIELDS:
                supplied = request.args.get(name)
                if supplied is not None and supplied.strip():
                    values[name] = supplied
        else:
            values = {
                name: request.form.get(name, "")
                for name, *_rest in spice_engine.FORM_FIELDS
            }

        result = None
        circuit = None
        error = None
        failure_log = ""
        failure_netlist = ""
        failure_run_id = ""
        analytical = None
        comparison = None

        if request.method == "POST" and not errors:
            circuit, field_errors, cleaned = spice_engine.validate_circuit(values)
            values = cleaned
            if field_errors:
                errors.update(field_errors)
            else:
                try:
                    result = spice_engine.run_simulation(
                        circuit, analysis, runs_dir=app.config["SIM_RUNS_DIR"]
                    )
                except spice_engine.EngineUnavailable as exc:
                    error = str(exc)
                except spice_engine.SimulationFailed as exc:
                    error = str(exc)
                    failure_log = exc.log
                    failure_netlist = exc.netlist
                    failure_run_id = exc.run_id

        chart = None
        ac_1k_index = 0
        if result is not None and result.ac is not None:
            chart = charts.bode_svg(
                result.ac.frequency_hz,
                result.ac.gain_db,
                result.ac.phase_deg,
                lower_cutoff_hz=result.ac.lower_cutoff_hz,
                upper_cutoff_hz=result.ac.upper_cutoff_hz,
            )
            frequencies = result.ac.frequency_hz
            if frequencies:
                ac_1k_index = min(
                    range(len(frequencies)),
                    key=lambda index: abs(math.log10(frequencies[index] / 1000.0)),
                )
        elif result is not None and result.tran is not None:
            chart = charts.transient_svg(
                result.tran.time_s,
                result.tran.vin_v,
                result.tran.vout_v,
            )

        if result is not None and result.dc is not None and circuit is not None:
            analytical = analytical_reference(circuit)
            comparison = compare_spice_dc(result.dc, analytical)

        return render_template(
            "simulator.html",
            analysis=analysis,
            analysis_label=ANALYSIS_LABELS[analysis],
            directive=spice_engine.ANALYSIS_DIRECTIVES[analysis],
            analysis_options=[
                (
                    value,
                    ANALYSIS_LABELS[value],
                    spice_engine.ANALYSIS_DIRECTIVES[value],
                )
                for value in ANALYSES
            ],
            fields=spice_engine.FORM_FIELDS,
            values=values,
            specs=build_sim_specs(values),
            errors=errors,
            engine=spice_engine.find_engine(),
            result=result,
            chart=chart,
            error=error,
            failure_log=failure_log,
            failure_netlist=failure_netlist,
            failure_run_id=failure_run_id,
            analytical=analytical,
            comparison=comparison,
            ac_1k_index=ac_1k_index,
            model=spice_engine.MODEL_NAME,
            model_beta=spice_engine.MODEL_BETA,
            model_note=spice_engine.MODEL_NOTE,
        )

    @app.route("/simulator/runs/<run_id>/netlist")
    def simulator_netlist(run_id: str):
        if not re.fullmatch(r"[0-9A-Za-z_-]{6,64}", run_id):
            abort(404)
        run_dir = Path(app.config["SIM_RUNS_DIR"]) / run_id
        return send_from_directory(
            run_dir,
            "circuit.cir",
            as_attachment=True,
            download_name=f"{run_id}-circuit.cir",
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)

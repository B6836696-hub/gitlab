# BJT Common-Emitter DC Bias Web App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a small Flask web app that computes and cross-checks the DC operating point of an NPN BJT common-emitter voltage-divider bias circuit.

**Architecture:** `bjt.py` holds all engineering logic: input validation, the Thevenin closed-form operating point, an independent 4×4 nodal linear-system solution, and a zero-safe comparison. `app.py` is a thin Flask factory that validates a form POST and renders one Thai page. Tests use `unittest` and Flask's test client; the existing Ohm's-law files are untouched.

**Tech Stack:** Python 3.12.7, Flask 3.x, pure-Python Gaussian elimination, Jinja templates, plain CSS, `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-10-bjt-ce-bias-design.md`

## Global Constraints

- Python 3.12.7; runtime dependency is Flask `>=3.0,<4.0` only.
- `VCE_SAT_V = 0.2` V and comparison tolerance `REL_TOL = 1e-9` are fixed.
- Inputs: `vcc` (V), `r1` (Ω), `r2` (Ω), `rc` (Ω), `re` (Ω), `beta` (—), `vbe` (V). NPN, DC, voltage-divider bias only.
- UI language is Thai; keep English technical labels (`Active`, `Cutoff`, `Saturation`, `MATCH`, `MISMATCH`, `IC(sat)`) visible for the demo.
- Currents display in mA when `|I| >= 1 mA`, otherwise µA; voltages in V; zero current displays as `0 mA`.
- No CDN, no JavaScript framework, no persistence, no authentication, no CSRF token (localhost lab app).
- Invalid POST returns HTTP 200 with field errors and no result section. Missing/malformed fields must never produce a 500.
- Existing `electrical.py` and `test_electrical.py` stay untouched and must keep passing.
- Run tests with `python -m unittest discover -v` (later, the venv Python).
- Git is not on PATH in this shell. Use:
  `$git = "C:\Users\B6836696\AppData\Local\Programs\Git\cmd\git.exe"` and `& $git ...`.
- Work on `main` in `C:\Users\B6836696\Desktop\gitlab`; push to `origin` at the end. No worktree for this short lab.

## Review Focus

- Cutoff produces exactly zero currents; the comparison must treat `0` vs `0` as relative difference `0`, never divide by zero. Pinned in Task 3.
- `VBE >= VBB` is a valid physical cutoff, not a validation error; only `VBE < 0` or `VBE >= VCC` is invalid. Pinned in Tasks 1 and 2.
- `VCE` exactly equal to `0.2 V` classifies as saturation (`<=`, not `<`). Pinned in Task 2.
- A missing or malformed POST field renders a field error, not an exception. Pinned in Tasks 1 and 4.
- Large but finite inputs must produce finite outputs rather than silent `inf`/`NaN`. Pinned in Task 2.

---

### Task 1: Input model and validation

**Files:**
- Create: `bjt.py`
- Create: `tests/__init__.py`
- Create: `tests/test_bjt.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces:
  - `FIELD_NAMES: tuple[str, ...]` = `("vcc", "r1", "r2", "rc", "re", "beta", "vbe")`
  - `@dataclass(frozen=True) class BiasInputs` with `vcc_v`, `r1_ohm`, `r2_ohm`, `rc_ohm`, `re_ohm`, `beta`, `vbe_v` (all `float`)
  - `validate_inputs(raw: Mapping[str, str]) -> tuple[BiasInputs | None, dict[str, str]]`

- [ ] **Step 1: Stop tracking Python cache files**

Put this in `.gitignore`:

```gitignore
.venv/
__pycache__/
*.pyc
```

Run:

```powershell
$git = "C:\Users\B6836696\AppData\Local\Programs\Git\cmd\git.exe"
& $git rm -r --cached __pycache__
& $git add .gitignore
& $git commit -m "chore: stop tracking Python cache files"
```

Expected: two `.pyc` deletions staged and committed; `git status` no longer shows them.

- [ ] **Step 2: Write the failing validation tests**

Create `tests/__init__.py` (empty) and `tests/test_bjt.py`:

```python
import math
import unittest

from bjt import BiasInputs, validate_inputs

VALID = {
    "vcc": "12", "r1": "47000", "r2": "10000", "rc": "2200",
    "re": "1000", "beta": "150", "vbe": "0.7",
}


class TestValidateInputs(unittest.TestCase):
    def test_accepts_valid_inputs(self):
        inputs, errors = validate_inputs(VALID)
        self.assertEqual(errors, {})
        self.assertIsInstance(inputs, BiasInputs)
        self.assertAlmostEqual(inputs.vcc_v, 12.0)
        self.assertAlmostEqual(inputs.beta, 150.0)

    def test_rejects_non_numeric(self):
        inputs, errors = validate_inputs(dict(VALID, vcc="abc"))
        self.assertIsNone(inputs)
        self.assertEqual(errors["vcc"], "กรุณากรอกเป็นตัวเลข")

    def test_rejects_missing_field(self):
        raw = dict(VALID)
        del raw["r1"]
        inputs, errors = validate_inputs(raw)
        self.assertIsNone(inputs)
        self.assertIn("r1", errors)

    def test_rejects_non_finite(self):
        for value in ("nan", "inf", "-inf"):
            with self.subTest(value=value):
                inputs, errors = validate_inputs(dict(VALID, vcc=value))
                self.assertIsNone(inputs)
                self.assertEqual(errors["vcc"], "ต้องเป็นจำนวนจำกัด")

    def test_rejects_non_positive_supply(self):
        inputs, errors = validate_inputs(dict(VALID, vcc="0"))
        self.assertIsNone(inputs)
        self.assertEqual(errors["vcc"], "ต้องมากกว่า 0 V")

    def test_rejects_non_positive_resistors(self):
        for field in ("r1", "r2", "rc", "re"):
            with self.subTest(field=field):
                inputs, errors = validate_inputs(dict(VALID, **{field: "0"}))
                self.assertIsNone(inputs)
                self.assertIn(field, errors)

    def test_rejects_beta_below_one(self):
        inputs, errors = validate_inputs(dict(VALID, beta="0.9"))
        self.assertIsNone(inputs)
        self.assertEqual(errors["beta"], "ต้องมีค่าอย่างน้อย 1")

    def test_rejects_vbe_outside_range(self):
        for value in ("-0.1", "12", "20"):
            with self.subTest(value=value):
                inputs, errors = validate_inputs(dict(VALID, vbe=value))
                self.assertIsNone(inputs)
                self.assertEqual(errors["vbe"], "ต้องอยู่ระหว่าง 0 ถึง VCC")

    def test_accepts_vbe_above_vbb_as_cutoff(self):
        # VBE above the divider voltage is a valid cutoff circuit, not an input error.
        inputs, errors = validate_inputs(dict(VALID, r2="1000"))
        self.assertEqual(errors, {})
        self.assertIsNotNone(inputs)
```

- [ ] **Step 3: Run the tests and see them fail**

Run: `python -m unittest tests.test_bjt -v`

Expected: FAIL/ERROR with `ModuleNotFoundError: No module named 'bjt'`.

- [ ] **Step 4: Implement the model and `validate_inputs`**

Create `bjt.py` with `math`, `dataclasses`, and `typing` imports. Define `FIELD_NAMES`, the frozen `BiasInputs` dataclass, and `validate_inputs` with these exact behaviors:

- Read every field with `raw.get(name, "")`, strip whitespace; empty or unparsable → `"กรุณากรอกเป็นตัวเลข"`.
- Non-finite (`math.isfinite` false) → `"ต้องเป็นจำนวนจำกัด"`.
- `vcc <= 0` → `"ต้องมากกว่า 0 V"`.
- Any of `r1`, `r2`, `rc`, `re` `<= 0` → `"ต้องมากกว่า 0 Ω"`.
- `beta < 1` → `"ต้องมีค่าอย่างน้อย 1"`.
- `0 <= vbe < vcc` false → `"ต้องอยู่ระหว่าง 0 ถึง VCC"`.
- Continue checking after a field fails so all errors are reported together.
- If any error exists return `(None, errors)`; otherwise build
  `BiasInputs(vcc_v=parsed["vcc"], r1_ohm=parsed["r1"], r2_ohm=parsed["r2"],
  rc_ohm=parsed["rc"], re_ohm=parsed["re"], beta=parsed["beta"],
  vbe_v=parsed["vbe"])` and return it with `{}`.

- [ ] **Step 5: Run the tests and verify they pass**

Run: `python -m unittest tests.test_bjt -v`

Expected: all validation tests PASS.

- [ ] **Step 6: Commit**

```powershell
$git = "C:\Users\B6836696\AppData\Local\Programs\Git\cmd\git.exe"
& $git add bjt.py tests/__init__.py tests/test_bjt.py
& $git commit -m "feat: validate BJT bias inputs"
```

---

### Task 2: Primary operating point and region classification

**Files:**
- Modify: `bjt.py`
- Modify: `tests/test_bjt.py`

**Interfaces:**
- Consumes: `BiasInputs`, `validate_inputs`.
- Produces:
  - `VCE_SAT_V: float` = `0.2`
  - `@dataclass(frozen=True) class OperatingPoint` with `vbb_v`, `rb_ohm`, `ib_a`, `ic_a`, `ie_a`, `ve_v`, `vb_v`, `vc_v`, `vce_v` (float), `region: str`, `ic_sat_a: float | None`
  - `classify_region(ib_a: float, vce_v: float) -> str` returning `"cutoff"`, `"saturation"`, or `"active"`
  - `calculate_operating_point(inputs: BiasInputs) -> OperatingPoint`

- [ ] **Step 1: Append the failing calculation tests**

Add to `tests/test_bjt.py`:

```python
from bjt import VCE_SAT_V, calculate_operating_point, classify_region


class TestCalculateOperatingPoint(unittest.TestCase):
    def test_worked_example(self):
        inputs, _ = validate_inputs(VALID)
        result = calculate_operating_point(inputs)
        self.assertAlmostEqual(result.vbb_v, 2.1052631579, places=9)
        self.assertAlmostEqual(result.rb_ohm, 8245.614035, places=6)
        self.assertAlmostEqual(result.ib_a, 8.8245014873e-6, places=15)
        self.assertAlmostEqual(result.ic_a, 1.3236752231e-3, places=12)
        self.assertAlmostEqual(result.ie_a, 1.3324997246e-3, places=12)
        self.assertAlmostEqual(result.ve_v, 1.3324997246, places=9)
        self.assertAlmostEqual(result.vb_v, 2.0324997246, places=9)
        self.assertAlmostEqual(result.vc_v, 9.0879145092, places=9)
        self.assertAlmostEqual(result.vce_v, 7.7554147846, places=9)
        self.assertEqual(result.region, "active")
        self.assertIsNone(result.ic_sat_a)

    def test_cutoff_when_vbb_below_vbe(self):
        inputs, _ = validate_inputs(dict(VALID, r2="1000"))
        result = calculate_operating_point(inputs)
        self.assertEqual(result.region, "cutoff")
        self.assertEqual(result.ib_a, 0.0)
        self.assertEqual(result.ic_a, 0.0)
        self.assertEqual(result.ie_a, 0.0)
        self.assertEqual(result.ve_v, 0.0)
        self.assertAlmostEqual(result.vb_v, 0.25, places=12)
        self.assertEqual(result.vc_v, 12.0)
        self.assertEqual(result.vce_v, 12.0)

    def test_saturation_and_limit_current(self):
        inputs, _ = validate_inputs(dict(VALID, rc="10000", re="100"))
        result = calculate_operating_point(inputs)
        self.assertEqual(result.region, "saturation")
        self.assertLess(result.vce_v, VCE_SAT_V)
        self.assertAlmostEqual(
            result.ic_sat_a, (12.0 - VCE_SAT_V) / (10000.0 + 100.0), places=12
        )

    def test_classify_region_boundary(self):
        self.assertEqual(classify_region(1e-6, 0.2), "saturation")
        self.assertEqual(classify_region(1e-6, 0.2000001), "active")
        self.assertEqual(classify_region(0.0, 5.0), "cutoff")

    def test_large_finite_inputs_stay_finite(self):
        raw = dict(
            VALID, vcc="1000000", r1="1000000000", r2="1000000000",
            rc="1000000", re="1000000", beta="1000000",
        )
        inputs, _ = validate_inputs(raw)
        result = calculate_operating_point(inputs)
        for value in (
            result.vbb_v, result.rb_ohm, result.ib_a, result.ic_a,
            result.ie_a, result.ve_v, result.vb_v, result.vc_v, result.vce_v,
        ):
            self.assertTrue(math.isfinite(value))
```

- [ ] **Step 2: Run and see the new tests fail**

Run: `python -m unittest tests.test_bjt -v`

Expected: ERROR importing `VCE_SAT_V` / `calculate_operating_point`.

- [ ] **Step 3: Implement the primary calculation**

Add to `bjt.py`:

```
VBB = VCC * R2 / (R1 + R2)
RB  = R1 * R2 / (R1 + R2)
IB  = (VBB - VBE) / (RB + (beta + 1) * RE)
```

If `IB <= 0`: return an `OperatingPoint` with `ib_a = ic_a = ie_a = 0`, `ve_v = 0`, `vb_v = VBB`, `vc_v = VCC`, `vce_v = VCC`, `region = "cutoff"`, `ic_sat_a = None`.

Otherwise compute `IC = beta*IB`, `IE = (beta+1)*IB`, `VE = IE*RE`, `VB = VE + VBE`, `VC = VCC - IC*RC`, `VCE = VC - VE`. Call `classify_region(IB, VCE)`. On saturation set `ic_sat_a = (VCC - VCE_SAT_V) / (RC + RE)`; otherwise `None`. `classify_region` checks cutoff first (`ib_a <= 0`), then saturation (`vce_v <= VCE_SAT_V`), else active.

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python -m unittest tests.test_bjt -v`

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```powershell
$git = "C:\Users\B6836696\AppData\Local\Programs\Git\cmd\git.exe"
& $git add bjt.py tests/test_bjt.py
& $git commit -m "feat: compute BJT DC operating point"
```

---

### Task 3: Independent nodal calculation and comparison

**Files:**
- Modify: `bjt.py`
- Modify: `tests/test_bjt.py`

**Interfaces:**
- Consumes: `BiasInputs`, `OperatingPoint`, `calculate_operating_point`, `VCE_SAT_V`.
- Produces:
  - `REL_TOL: float` = `1e-9`
  - `solve_linear_system(matrix: list[list[float]], rhs: list[float]) -> list[float]`
  - `calculate_nodal_operating_point(inputs: BiasInputs) -> OperatingPoint`
  - `@dataclass(frozen=True) class ComparisonRow` with `name: str`, `unit: str`, `method_a: float`, `method_b: float`, `abs_diff: float`, `rel_diff: float`
  - `@dataclass(frozen=True) class Comparison` with `rows: list[ComparisonRow]`, `max_rel_diff: float`, `matched: bool`
  - `compare_operating_points(a: OperatingPoint, b: OperatingPoint) -> Comparison`

- [ ] **Step 1: Append the failing nodal and comparison tests**

Add to `tests/test_bjt.py`:

```python
from bjt import (
    calculate_nodal_operating_point,
    compare_operating_points,
    solve_linear_system,
)


class TestNodalAndComparison(unittest.TestCase):
    def test_solve_linear_system(self):
        x = solve_linear_system([[2.0, 1.0], [1.0, 3.0]], [3.0, 5.0])
        self.assertAlmostEqual(x[0], 0.8)
        self.assertAlmostEqual(x[1], 1.4)

    def test_solve_singular_raises(self):
        with self.assertRaises(ValueError):
            solve_linear_system([[1.0, 2.0], [2.0, 4.0]], [1.0, 2.0])

    def test_nodal_matches_primary_for_several_betas(self):
        for beta in ("20", "150", "400"):
            with self.subTest(beta=beta):
                inputs, _ = validate_inputs(dict(VALID, beta=beta))
                a = calculate_operating_point(inputs)
                b = calculate_nodal_operating_point(inputs)
                self.assertEqual(b.region, a.region)
                for attr in (
                    "ib_a", "ic_a", "ie_a", "vb_v", "ve_v", "vc_v", "vce_v",
                ):
                    self.assertAlmostEqual(
                        getattr(a, attr), getattr(b, attr), delta=1e-9
                    )

    def test_comparison_marks_match(self):
        inputs, _ = validate_inputs(VALID)
        a = calculate_operating_point(inputs)
        b = calculate_nodal_operating_point(inputs)
        comparison = compare_operating_points(a, b)
        self.assertTrue(comparison.matched)
        self.assertEqual(len(comparison.rows), 7)
        self.assertLessEqual(comparison.max_rel_diff, 1e-9)

    def test_comparison_is_zero_safe_in_cutoff(self):
        inputs, _ = validate_inputs(dict(VALID, r2="1000"))
        a = calculate_operating_point(inputs)
        b = calculate_nodal_operating_point(inputs)
        comparison = compare_operating_points(a, b)
        self.assertTrue(comparison.matched)
        for row in comparison.rows:
            if row.method_a == 0 and row.method_b == 0:
                self.assertEqual(row.rel_diff, 0.0)
```

- [ ] **Step 2: Run and see the new tests fail**

Run: `python -m unittest tests.test_bjt -v`

Expected: ERROR importing the nodal functions.

- [ ] **Step 3: Implement the linear solver**

Add `solve_linear_system` as Gaussian elimination with partial pivoting:

```python
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
```

- [ ] **Step 4: Implement the nodal operating point**

Use unknowns `[VB, VE, VC, IB]` and the matrix/right-hand side:

```python
r1, r2, rc, re, beta = inputs.r1_ohm, inputs.r2_ohm, inputs.rc_ohm, inputs.re_ohm, inputs.beta
matrix = [
    [1 / r1 + 1 / r2, 0.0, 0.0, 1.0],
    [0.0, 1 / re, 0.0, -(beta + 1)],
    [0.0, 0.0, 1 / rc, beta],
    [1.0, -1.0, 0.0, 0.0],
]
rhs = [inputs.vcc_v / r1, 0.0, inputs.vcc_v / rc, inputs.vbe_v]
vb, ve, vc, ib = solve_linear_system(matrix, rhs)
```

If `ib <= 0`, return the same cutoff `OperatingPoint` shape as Task 2 (VBB, RB, zero currents, `vc_v = VCC`, `vce_v = VCC`, `region = "cutoff"`, `ic_sat_a = None`). Otherwise compute `ic = beta*ib`, `ie = (beta+1)*ib`, `vce = vc - ve`, classify with `classify_region`, and set `ic_sat_a` on saturation exactly as Task 2 does.

- [ ] **Step 5: Implement the comparison**

Compare seven attributes in this order and with these labels/units:

```python
COMPARISON_FIELDS = (
    ("ib_a", "IB", "A"), ("ic_a", "IC", "A"), ("ie_a", "IE", "A"),
    ("vb_v", "VB", "V"), ("ve_v", "VE", "V"), ("vc_v", "VC", "V"),
    ("vce_v", "VCE", "V"),
)
```

For each pair compute `abs_diff = abs(a - b)` and
`rel_diff = abs_diff / max(abs(a), abs(b), 1e-12)`. Track `max_rel_diff`.
Return `Comparison(rows, max_rel_diff, max_rel_diff <= REL_TOL)`.

- [ ] **Step 6: Run the tests and verify they pass**

Run: `python -m unittest tests.test_bjt -v`

Expected: all tests PASS, including `MATCH` and cutoff zero-safety.

- [ ] **Step 7: Commit**

```powershell
$git = "C:\Users\B6836696\AppData\Local\Programs\Git\cmd\git.exe"
& $git add bjt.py tests/test_bjt.py
& $git commit -m "feat: add independent nodal cross-check"
```

---

### Task 4: Flask page, filters, and route tests

**Files:**
- Create: `requirements.txt`
- Create: `app.py`
- Create: `templates/index.html`
- Create: `static/style.css`
- Create: `tests/test_app.py`

**Interfaces:**
- Consumes: `FIELD_NAMES`, `validate_inputs`, `calculate_operating_point`, `calculate_nodal_operating_point`, `compare_operating_points`, `VCE_SAT_V`.
- Produces:
  - `format_current(value_a: float) -> str`
  - `format_voltage(value_v: float) -> str`
  - `create_app() -> Flask`
  - module-level `app = create_app()` and a `__main__` block running `app.run(debug=True)`

- [ ] **Step 1: Add the dependency and create the venv**

`requirements.txt`:

```text
Flask>=3.0,<4.0
```

Run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Expected: Flask installs successfully.

- [ ] **Step 2: Write the failing route and filter tests**

Create `tests/test_app.py`:

```python
import unittest

from app import create_app, format_current, format_voltage

VALID = {
    "vcc": "12", "r1": "47000", "r2": "10000", "rc": "2200",
    "re": "1000", "beta": "150", "vbe": "0.7",
}


class TestFormatting(unittest.TestCase):
    def test_current_units(self):
        self.assertEqual(format_current(0), "0 mA")
        self.assertEqual(format_current(0.0013236752), "1.3237 mA")
        self.assertEqual(format_current(8.8245014873e-06), "8.8245 µA")

    def test_voltage_units(self):
        self.assertEqual(format_voltage(7.7554147846), "7.7554 V")


class TestRoutes(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def test_get_form(self):
        response = self.client.get("/")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        for field in ("vcc", "r1", "r2", "rc", "re", "beta", "vbe"):
            self.assertIn(f'name="{field}"', body)

    def test_valid_post_shows_operating_point(self):
        response = self.client.post("/", data=VALID)
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("1.3237 mA", body)
        self.assertIn("7.7554 V", body)
        self.assertIn("Active", body)
        self.assertIn("MATCH", body)

    def test_invalid_post_shows_error_and_no_results(self):
        response = self.client.post("/", data=dict(VALID, vcc="0"))
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("ต้องมากกว่า 0 V", body)
        self.assertNotIn('id="results"', body)

    def test_missing_field_shows_error_not_500(self):
        data = dict(VALID)
        del data["r1"]
        response = self.client.post("/", data=data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("กรุณากรอกเป็นตัวเลข", response.get_data(as_text=True))

    def test_cutoff_post_shows_warning(self):
        response = self.client.post("/", data=dict(VALID, r2="1000"))
        body = response.get_data(as_text=True)
        self.assertIn("Cutoff", body)
        self.assertIn("MATCH", body)

    def test_saturation_post_shows_warning(self):
        response = self.client.post("/", data=dict(VALID, rc="10000", re="100"))
        body = response.get_data(as_text=True)
        self.assertIn("Saturation", body)
        self.assertIn("IC(sat)", body)
```

- [ ] **Step 3: Run and see the tests fail**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_app -v`

Expected: ERROR with `ModuleNotFoundError: No module named 'app'`.

- [ ] **Step 4: Implement the filters and app factory**

In `app.py`:

- `_trim(value: float) -> str`: format to 4 decimals, strip trailing zeros and a trailing dot; `-0` becomes `0`.
- `format_current`: exactly `0` → `"0 mA"`; `abs >= 1e-3` → `f"{_trim(value*1e3)} mA"`; else `f"{_trim(value*1e6)} µA"`.
- `format_voltage`: `f"{_trim(value)} V"`.
- `create_app()`: build `Flask(__name__)`, register both functions as Jinja filters named `current` and `voltage`, add `GET`/`POST` route `/`.
- `GET`: render with `values=DEFAULTS`, `errors={}`, `result=None`, `comparison=None`, `vce_sat=VCE_SAT_V`.
- `POST`: read `{name: request.form.get(name, "") for name in FIELD_NAMES}`; validate; on errors render the same template with 200 and raw values; otherwise compute primary, nodal, and comparison, then render with `values=raw`.
- `DEFAULTS` are the worked-example values (`12`, `47000`, `10000`, `2200`, `1000`, `150`, `0.7`).
- End with `app = create_app()` and `if __name__ == "__main__": app.run(debug=True)`.

- [ ] **Step 5: Implement the template**

`templates/index.html` must contain:

- A form posting to `/` with inputs `name="vcc"`, `r1`, `r2`, `rc`, `re`, `beta`, `vbe`, each with a Thai label, its unit, `required`, `step="any"`, and `value="{{ values.<name> }}"`. Render `errors.<name>` next to each field.
- Result section wrapped as `<section id="results">` only when `result` is truthy.
- Region badge text `{{ result.region|capitalize }}` so tests see `Active`, `Cutoff`, `Saturation`.
- Thai explanation for each region; for cutoff say the base-emitter junction is not forward biased; for saturation say the active-region equations are invalid.
- Operating-point rows using the filters: `VBB`, `RB`, `IB`, `IC`, `IE`, `VE`, `VB`, `VC`, `VCE`. `RB` displays with a literal `Ω` unit.
- When `result.region == "saturation"`, show `IC(sat)` using `{{ result.ic_sat_a|current }}`.
- Comparison table looping `comparison.rows`, showing `row.name`, `row.method_a` (current or voltage filter based on `row.unit`), `row.method_b`, `row.abs_diff`, `row.rel_diff`, and a status element containing `MATCH` or `MISMATCH`.
- A note that agreement checks the implementation, not physical validity, when `result.region != "active"`.
- Formula reminder with the Thevenin equations.

- [ ] **Step 6: Implement the stylesheet**

`static/style.css`: system font stack, centered max-width column, labeled form grid, card-style result panel, colored badges for active/cutoff/saturation, readable table borders, warning colors, responsive single-column layout under 640px. No external fonts or CDN.

- [ ] **Step 7: Run the route tests and verify they pass**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_app -v`

Expected: all formatting and route tests PASS.

- [ ] **Step 8: Commit**

```powershell
$git = "C:\Users\B6836696\AppData\Local\Programs\Git\cmd\git.exe"
& $git add requirements.txt app.py templates/index.html static/style.css tests/test_app.py
& $git commit -m "feat: add Flask BJT bias calculator UI"
```

---

### Task 5: Documentation, full verification, and push

**Files:**
- Modify: `README.md`
- Include in commit: `docs/superpowers/specs/2026-11-10-bjt-ce-bias-design.md`, `docs/superpowers/plans/2026-11-10-bjt-ce-bias.md`

**Interfaces:**
- Consumes: everything above.
- Produces: a demonstrated localhost app and a pushed GitHub commit.

- [ ] **Step 1: Update `README.md`**

Keep the existing Ohm's-law section. Add:

- Project title and one-paragraph purpose (Thai).
- Inputs table and the Method A formulas.
- Short explanation of the independent nodal cross-check.
- Region rules: cutoff `IB <= 0`; saturation `VCE <= 0.2 V`; otherwise active.
- Setup: `python -m venv .venv`, `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.
- Run: `.\.venv\Scripts\python.exe app.py`, open `http://127.0.0.1:5000`.
- Test: `.\.venv\Scripts\python.exe -m unittest discover -v`.
- Worked example values from Task 2.
- Note that the old Ohm's-law CLI remains available.

- [ ] **Step 2: Run the full test suite**

Run: `.\.venv\Scripts\python.exe -m unittest discover -v`

Expected: all BJT tests plus the two existing `test_electrical` tests PASS.

- [ ] **Step 3: Smoke-test the real localhost server**

```powershell
$server = Start-Process -FilePath (Resolve-Path ".\.venv\Scripts\python.exe") -ArgumentList "app.py" -PassThru
Start-Sleep -Seconds 2
$status = (Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5000/).StatusCode
Stop-Process -Id $server.Id
$status
```

Expected: `200`. If port 5000 is busy, stop the other process or run on another port and say which URL is live.

- [ ] **Step 4: Commit the docs**

```powershell
$git = "C:\Users\B6836696\AppData\Local\Programs\Git\cmd\git.exe"
& $git add README.md docs/superpowers/specs/2026-11-10-bjt-ce-bias-design.md docs/superpowers/plans/2026-11-10-bjt-ce-bias.md
& $git commit -m "docs: document BJT bias app"
```

- [ ] **Step 5: Verify the working tree and push**

```powershell
$git = "C:\Users\B6836696\AppData\Local\Programs\Git\cmd\git.exe"
& $git status --short --branch
& $git push origin main
```

Expected: clean tree, `main` ahead by the new commits, push succeeds. If authentication or network fails, report the exact error and leave the commits intact; do not rewrite history.

---

## Self-Review

**Spec coverage:** inputs/validation → Task 1; primary calculation/regions/`IC_sat` → Task 2; independent nodal method/zero-safe comparison → Task 3; Thai page, units, warnings, routes → Task 4; README, demo, git → Task 5. Non-goals need no tasks. Existing files are protected by the Global Constraints.

**Type consistency:** `OperatingPoint` attributes are used identically in Tasks 2–4 (`ib_a`, `ic_a`, `ie_a`, `vb_v`, `ve_v`, `vc_v`, `vce_v`, `region`, `ic_sat_a`). `ComparisonRow`/`Comparison` field names match the template and tests. `FIELD_NAMES` is the single source for form fields.

**Review Focus:** each of the five lines has a named test in its owning task. No uncovered input class remains.

**Proportion:** the document specifies signatures, exact tests, and one non-obvious algorithm; implementation bodies are otherwise left to the builder.

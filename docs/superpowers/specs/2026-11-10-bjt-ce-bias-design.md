# BJT Common-Emitter DC Bias Web App — Design

Date: 2026-11-10
Course: ENG29 2121 (short lab)
Status: approved 2026-11-10

## Intent and why

The lab asks for a small, real Flask web application that computes the DC
operating point of an NPN BJT common-emitter amplifier using voltage-divider
bias. The app must be usable in a live localhost demonstration, show units,
validate inputs, warn when the transistor is outside the active region, and
cross-check its result with an independent engineering calculation. It is a
teaching deliverable, not a production tool.

The repository already contains an unrelated Ohm's-law CLI
(`electrical.py` + `test_electrical.py`) with passing tests. It stays
untouched; the BJT app is added alongside it.

## Goals

- One Flask page: enter seven values, submit, see the DC operating point.
- Pure engineering logic in `bjt.py`, separate from Flask routes in `app.py`.
- Every displayed quantity carries a unit; currents are shown in mA or µA.
- Validation rejects non-numeric, non-finite, and physically invalid inputs
  with per-field messages.
- Region classification: cutoff, active, saturation, with an explanation.
- A second, independent calculation (nodal analysis solved as a linear
  system) is compared against the primary Thevenin calculation.
- Tests cover the calculations, validation, region warnings, and routes.
- Runs locally with `python app.py` (or the venv equivalent) and can be
  committed and pushed to GitHub the same day.

## Non-goals

- No AC analysis, frequency response, transient analysis, or load lines.
- No schematic editor, netlist import, component database, or persistence.
- No PNP, Darlington, or FET support.
- No authentication, database, deployment configuration, or production
  hardening.
- No JavaScript framework and no external CDN dependency.

## Anti-goals

- A calculator that silently returns numbers for invalid circuits.
- A "comparison" that reuses the same function twice and can never disagree.
- Scope creep into a general circuit simulator.
- UI complexity that makes the live demo harder to explain.

## Constraints

- Python 3.12 is available. Flask is not installed yet; it will be installed
  into a project virtual environment and pinned in `requirements.txt`.
- Git is installed at
  `C:\Users\B6836696\AppData\Local\Programs\Git\cmd\git.exe` but is not on
  this shell's PATH. Commands will use the full path or add it to PATH.
- The app is for localhost demonstration. No session state or CSRF token is
  needed because there are no accounts and no state-changing actions beyond
  a calculation.
- Existing CI, tooling, and repository conventions: none beyond `unittest`.

## Approaches considered

### A. Nodal analysis as an independent cross-check (chosen)

Model the same active-region device equations but solve them in a different
formulation: four KCL/constraint equations in four unknowns, solved by a
generic Gaussian-elimination routine with partial pivoting. This is
independent of the Thevenin closed form, catches algebra and implementation
errors, and is small enough to test exhaustively. It is the recommended
option in the conversation and the one selected.

### B. Approximate versus exact divider (rejected)

Compare the textbook approximation that neglects base current with the exact
loaded-divider result. It reads like a textbook exercise, but the two results
can be nearly identical, so it is a weak check. It also invites confusion
about which result is "the answer".

### C. Ebers–Moll iterative model (rejected)

Numerically solve the exponential BJT equations. It is the most physically
independent check, but it needs convergence handling, temperature/emission
parameters, and far more code than a short DC-bias lab justifies. It would
also make the operating point depend on model constants the lab does not
provide.

## Design

### File layout

```
bjt.py                  engineering logic, no Flask imports
app.py                  Flask app factory, routes, Jinja filters
templates/index.html    single form + results page
static/style.css        plain CSS, no CDN
tests/__init__.py
tests/test_bjt.py       calculation, validation, region, comparison tests
tests/test_app.py       route and rendering tests
requirements.txt        Flask
.gitignore              .venv/, __pycache__/, *.pyc
README.md               setup, run, test, formulas, example
```

### Inputs and validation

Fields (POST names in parentheses):

| Quantity | Name | Unit | Rule |
|---|---|---|---|
| Supply voltage | `vcc` | V | finite, > 0 |
| Upper base resistor | `r1` | Ω | finite, > 0 |
| Lower base resistor | `r2` | Ω | finite, > 0 |
| Collector resistor | `rc` | Ω | finite, > 0 |
| Emitter resistor | `re` | Ω | finite, > 0 |
| Current gain | `beta` | — | finite, ≥ 1 |
| Base-emitter drop | `vbe` | V | finite, 0 ≤ VBE < VCC |

Validation returns a mapping of field name to a short Thai message. All
fields are checked and all errors are shown together. Invalid submissions
re-render the form with the user's raw values and no results.

### Primary calculation (Method A: Thevenin base divider)

```
VBB = VCC * R2 / (R1 + R2)
RB  = R1 * R2 / (R1 + R2)
IB  = (VBB - VBE) / (RB + (beta + 1) * RE)
```

If `IB <= 0`, the device is in **cutoff**:

```
IB = IC = IE = 0
VE = 0, VB = VBB, VC = VCC, VCE = VCC
```

Otherwise the active-region solution is:

```
IC  = beta * IB
IE  = (beta + 1) * IB
VE  = IE * RE
VB  = VE + VBE
VC  = VCC - IC * RC
VCE = VC - VE
```

Region rules:

- `IB <= 0` → cutoff.
- `VCE <= 0.2 V` → saturation warning. The active-region numbers are still
  displayed, but labelled as invalid estimates; `VCE_sat = 0.2 V` is fixed.
  Also show the saturation-limit reference
  `IC_sat = (VCC - VCE_sat) / (RC + RE)` so the student can see the ceiling.
- Otherwise → active.

`VCE_sat` is a fixed constant, not an input, to keep the lab minimal.

### Independent calculation (Method B: nodal analysis)

Unknowns: `VB`, `VE`, `VC`, `IB`. Device model: `IC = beta * IB`,
`IE = (beta + 1) * IB`, `VB - VE = VBE`.

Equations (currents leaving each node sum to zero):

```
(1/R1 + 1/R2) VB                    + IB      = VCC / R1
                  (1/RE) VE         - (beta+1)IB = 0
                              (1/RC) VC + beta*IB = VCC / RC
 VB - VE                                        = VBE
```

Solved with a small pure-Python Gaussian-elimination function (partial
pivoting, no NumPy). The nodal result is then converted to `IC`, `IE`, and
`VCE`. If its own `IB <= 0`, it returns the same cutoff operating point as
Method A. Region classification uses the same physical thresholds.

### Comparison

Both methods return a complete operating point. The page always shows a
comparison table for `IB`, `IC`, `IE`, `VB`, `VE`, `VC`, `VCE`: Method A,
Method B, absolute difference, and relative difference.

Relative difference is zero-safe:

```
rel = abs(a - b) / max(abs(a), abs(b), 1e-12)
```

If both values are zero, `rel = 0`. The status is `MATCH` when the largest
relative difference is ≤ `1e-9`; otherwise `MISMATCH` with a clear warning.
In cutoff the table still renders and reports `MATCH` on the zero currents.
Because both methods describe the same linear active-region model, agreement
checks the implementation, not the physical validity of a saturated or
cut-off result; the region warning explains that distinction.

The single region badge and warning are computed from **Method A only**.
Method B performs its own cutoff check internally so that its returned
operating point is physically consistent, but its region label is not shown
separately. This avoids two badges disagreeing on floating-point noise near
`VCE = 0.2 V`.

### Routes

- `GET /` — render the form with the worked-example defaults and no results.
- `POST /` — validate, calculate, and re-render the same page with either
  per-field errors or the operating point, region warning, and comparison.
- `create_app()` factory so tests can build an isolated app.
- `python app.py` runs the development server on localhost.

### Result presentation

- Result card: region badge and a one-sentence explanation in Thai.
- Operating-point table: `VBB`, `RB`, `IB`, `IC`, `IE`, `VE`, `VB`, `VC`,
  `VCE`, each with its unit. Defaults also appear as a collapsible formula
  reminder so the demo can be explained without slides.
- Currents: mA when `|I| >= 1 mA`, otherwise µA; voltages: V; four decimal
  places with trailing zeros trimmed by the display helper.
- Warnings: cutoff explains that the base-emitter junction is not forward
  biased; saturation explains that the active-region equations no longer
  hold and shows the `IC_sat` ceiling.
- No results are rendered when validation fails.

### Tests

`tests/test_bjt.py`:

- Worked active example `VCC=12, R1=47k, R2=10k, RC=2.2k, RE=1k, beta=150,
  VBE=0.7` gives the documented values (see below).
- Method B matches Method A within `1e-9` relative error for several active
  cases, including a low-beta case and a high-beta case.
- Cutoff case returns zero currents and `VCE = VCC`; its comparison is
  zero-safe and reports `MATCH`.
- Saturation case sets the saturation region and exposes the warning.
- Validation rejects: non-numeric, `NaN`/`inf`, zero/negative VCC, zero or
  negative resistors, `beta < 1`, negative VBE, `VBE >= VCC`.
- `IC_sat` reference is correct.

Worked-example reference values (Method A):

```
VBB = 2.1052631579 V      RB  = 8245.614035 Ω
IB  = 8.8245014873 µA     IC  = 1.3236752231 mA
IE  = 1.3324997246 mA     VE  = 1.3324997246 V
VB  = 2.0324997246 V      VC  = 9.0879145092 V
VCE = 7.7554147846 V      region: active
```

`tests/test_app.py`:

- `GET /` returns 200 and contains all seven inputs.
- Valid POST returns 200, shows the operating point and `MATCH`.
- Invalid POST shows field errors and no result table.
- Cutoff POST shows the cutoff warning.
- Saturation POST shows the saturation warning.

Run with `python -m unittest discover -v` from the project root. The existing
`test_electrical.py` must continue to pass.

### Documentation and demonstration

README gains: purpose, formulas, setup (venv + `pip install -r
requirements.txt`), run (`python app.py`, open `http://127.0.0.1:5000`), test
command, and the worked example. The existing Ohm's-law section stays.

### Git

The two `__pycache__/*.pyc` files are currently tracked and modified. The
first commit will untrack them with `git rm --cached __pycache__` and add
`.venv/`, `__pycache__/`, and `*.pyc` to `.gitignore`. The existing source
files themselves stay untouched.

After that, one focused commit for the app (or a small sequence: engineering
logic + tests, then Flask UI + route tests, then docs). Commit to `main`,
then push to `origin`. The execution plan will choose inline versus
subagent-driven execution, per the lab request.

## Decisions made in conversation

- Independent calculation = nodal analysis solved as a linear system
  (option 1), not approximate-vs-exact and not Ebers–Moll.
- UI language = Thai, with English technical labels where useful.
- Existing Ohm's-law files stay as-is.
- `VCE_sat` is fixed at 0.2 V.
- NPN only; voltage-divider bias only; DC only.

## Deliverable scope

Graded deliverable: the running Flask app, its tests, the README, and the
committed source. The design and implementation-plan documents are committed
for transparency, but no extra screenshots, process report, or evidence
bundle are produced unless the course explicitly requires them. If it does,
say so before the plan is written; that changes the task list.

## Left to the builder

- Exact Thai wording, CSS styling, and table layout.
- Numeric formatting details beyond the stated rules.
- Test-case selection beyond the required cases.
- Whether to use `unittest` subTest or separate test methods.
- Git commit granularity within the stated options.

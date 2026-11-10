# Circuit Diagram Addition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a static, accessible inline SVG schematic of the NPN common-emitter voltage-divider bias circuit to the existing Flask page.

**Architecture:** One inline SVG in `templates/index.html`, styled with new `.schematic-*` classes in `static/style.css`. No Python changes. Route tests pin the SVG marker and accessibility markup.

**Tech Stack:** Jinja template, inline SVG, plain CSS, `unittest`, Flask test client.

**Spec:** `docs/superpowers/specs/2026-11-10-circuit-diagram-design.md`

## Global Constraints

- No changes to `bjt.py`, `app.py`, calculation logic, validation, or result data.
- No JavaScript, external images, CDN, or canvas.
- Static labels only; entered values stay in the form and result table.
- Thai caption; English technical labels (`VCC`, `R1`, `R2`, `RC`, `RE`, `Q1`, `GND`).
- Existing 35 tests must keep passing; full suite command is
  `.\.venv\Scripts\python.exe -m unittest discover -v`.
- Git is not on PATH; use
  `$git = "C:\Users\B6836696\AppData\Local\Programs\Git\cmd\git.exe"`.
- Work on `main`; the dev server is already running with auto-reload.

## Review Focus

- The SVG must render on `GET /` and after `POST /` (success and validation error). Pinned in Task 1.
- The diagram must be accessible: `role="img"`, `<title>`, `<desc>`, and an aria-label. Pinned in Task 1.
- The SVG must be responsive and not introduce horizontal scrolling on mobile. Verified by CSS (`max-width: 100%; height: auto`).
- The schematic must use only the approved components and labels. Pinned by the label test (`Q1` is unique to the diagram).
- No calculation or validation behavior may change. Pinned by the full existing suite.

---

### Task 1: Static circuit diagram

**Files:**
- Modify: `templates/index.html`
- Modify: `static/style.css`
- Modify: `tests/test_app.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: the existing `index.html` template context (`values`, `errors`, `result`, `comparison`, `vce_sat`).
- Produces: no Python API; the page gains `data-circuit="bjt-ce"` and the `.schematic-*` CSS classes.

- [ ] **Step 1: Write the failing diagram tests**

Add to `tests/test_app.py` in `TestRoutes`:

```python
    def test_get_includes_circuit_diagram(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn('data-circuit="bjt-ce"', body)
        self.assertIn('aria-label="BJT common-emitter circuit"', body)
        self.assertIn(
            "<title>BJT common-emitter voltage-divider bias circuit</title>",
            body,
        )
        self.assertIn(">Q1<", body)

    def test_valid_post_includes_circuit_diagram(self):
        body = self.client.post("/", data=VALID).get_data(as_text=True)
        self.assertIn('data-circuit="bjt-ce"', body)
```

- [ ] **Step 2: Run the tests and see them fail**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_app -v`

Expected: the two new tests FAIL because the SVG markup does not exist.

- [ ] **Step 3: Add the SVG card to `templates/index.html`**

Insert after the closing `</header>` and before the input `<section class="card">`:

- A `<section class="card circuit-card">` with `<h2>วงจร</h2>`.
- One inline `<svg viewBox="0 0 640 380" role="img" aria-label="BJT common-emitter circuit" data-circuit="bjt-ce">` containing:
  - `<title>BJT common-emitter voltage-divider bias circuit</title>`
  - a `<desc>` naming VCC, R1, R2, RC, RE, and Q1
  - VCC rail, R1 from VCC to the base, R2 from the base to ground, RC from VCC to the collector, RE from the emitter to ground
  - an NPN transistor circle and base bar for Q1, with an emitter arrow
  - junction dots, a common ground rail and ground symbol
  - `<text>` labels `VCC`, `R1`, `R2`, `RC`, `RE`, `Q1`, `GND`
- A Thai caption: `วงจร common-emitter แบบ voltage-divider bias (NPN)`.

Use these classes on SVG elements: `schematic-wire`, `schematic-component`, `schematic-transistor`, `schematic-node`, `schematic-arrow`, `schematic-label`, `schematic-small`.

- [ ] **Step 4: Add the styles**

In `static/style.css`, add:

```css
.circuit-wrap {
  display: flex;
  justify-content: center;
  padding: 0.25rem 0 0.5rem;
  color: var(--text);
}

.circuit-wrap svg {
  width: 100%;
  max-width: 640px;
  height: auto;
}

.circuit-caption {
  margin: 0;
  color: var(--muted);
  font-size: 0.9rem;
  text-align: center;
}

.schematic-wire,
.schematic-transistor {
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.schematic-component {
  fill: var(--card);
  stroke: currentColor;
  stroke-width: 2;
}

.schematic-node,
.schematic-arrow {
  fill: currentColor;
}

.schematic-label {
  fill: currentColor;
  font-family: "Segoe UI", Tahoma, "Noto Sans Thai", system-ui, sans-serif;
  font-size: 14px;
  font-weight: 700;
}

.schematic-small {
  fill: var(--muted);
  font-family: "Segoe UI", Tahoma, "Noto Sans Thai", system-ui, sans-serif;
  font-size: 12px;
  font-weight: 600;
}
```

- [ ] **Step 5: Update `README.md`**

Add one feature bullet: the page shows a static inline SVG schematic of the
voltage-divider common-emitter circuit.

- [ ] **Step 6: Run the tests and verify they pass**

Run: `.\.venv\Scripts\python.exe -m unittest discover -v`

Expected: 37 tests PASS (35 existing + 2 new).

- [ ] **Step 7: Commit**

```powershell
$git = "C:\Users\B6836696\AppData\Local\Programs\Git\cmd\git.exe"
& $git add templates/index.html static/style.css tests/test_app.py README.md docs/superpowers/specs/2026-11-10-circuit-diagram-design.md docs/superpowers/plans/2026-11-10-circuit-diagram.md
& $git commit -m "feat: add common-emitter circuit diagram"
```

---

## Self-Review

**Spec coverage:** SVG card → Steps 3–4; accessibility → Step 3 and test; GET/POST rendering → Step 1 tests; responsive CSS → Step 4; README → Step 5; no backend changes → Global Constraints and a green existing suite.

**Type consistency:** No Python interfaces change. Class names in Step 3 match Step 4 and the test checks only stable markup.

**Review Focus:** each line has a test or a concrete CSS/verification step.

**Proportion:** one task, one SVG, one test pair; the plan does not transcribe the whole drawing.

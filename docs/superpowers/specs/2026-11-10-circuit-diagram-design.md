# Circuit Diagram Addition — Design

Date: 2026-11-10
Status: approved 2026-11-10

## Intent

The lab demo currently shows inputs, formulas, and results but not the circuit
being solved. A reference schematic makes the page self-explanatory during the
live demonstration.

## Goals

- Show the NPN common-emitter voltage-divider bias circuit on the page.
- Use a static inline SVG so the diagram is crisp, offline, and dependency-free.
- Label `VCC`, `R1`, `R2`, `RC`, `RE`, `Q1`, and ground.
- Keep the diagram accessible (`role="img"`, title, description, aria-label).
- Render the diagram on both `GET /` and valid/invalid `POST /` responses.
- Add a route test that fails before the SVG exists.

## Non-goals

- No dynamic values on the diagram; entered values stay in the input fields and
  result table.
- No JavaScript, external image, CDN, or canvas.
- No changes to `bjt.py`, calculation logic, validation, or result data.
- No interactive schematic editor.

## Approaches considered

### A. Static inline SVG (chosen)

Hand-authored SVG in `templates/index.html`, styled with CSS. Crisp at any
zoom, testable as markup, works offline, and does not couple the drawing to
input values. This is the smallest change that satisfies the request.

### B. Server-rendered SVG with entered values (rejected)

Would print the actual resistor values on the diagram. More informative in
principle, but duplicates the result table, clutters the drawing, and couples
the schematic to request data for no lab benefit.

### C. PNG image (rejected)

Fastest to draw externally, but binary, blurry when zoomed, hard to restyle,
and not testable as markup.

## Design

- Insert a new card `วงจร` after the page header and before the input form in
  `templates/index.html`.
- The card contains one inline `<svg viewBox="0 0 640 380">` with:
  - `data-circuit="bjt-ce"`
  - `role="img"` and `aria-label="BJT common-emitter circuit"`
  - `<title>` and `<desc>`
  - VCC rail, R1/R2 divider to the base, RC at the collector, RE at the
    emitter, NPN Q1, and a common ground rail.
  - Standard schematic wires, resistor rectangles, junction dots, an emitter
    arrow, and labels.
- Add a Thai caption below the SVG.
- Add CSS classes for wires, components, labels, nodes, and the emitter arrow;
  the SVG is `width: 100%; max-width: 640px; height: auto`.
- Add two tests in `tests/test_app.py`: the diagram marker and accessibility
  labels are present on `GET /`, and still present after a valid `POST /`.
- Add one README feature line.

## Decisions made in conversation

- Static labels, not dynamic values.
- Placement above the input form.
- No backend or calculation changes.

## Left to the builder

- Exact geometry, stroke widths, and visual polish.
- Thai caption wording.

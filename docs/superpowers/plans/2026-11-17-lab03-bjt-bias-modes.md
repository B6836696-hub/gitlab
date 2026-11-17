# Lab 03 — BJT Bias Modes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** เพิ่มโหมด Fixed Bias และ Emitter Bias ให้เว็บ Flask เดิม โดยเลือกโหมดจากฟอร์มและคงผลของ Voltage Divider เดิมไว้

**Architecture:** แยกสมการแต่ละโหมดเป็นฟังก์ชันใน `bjt.py` ใช้ `OperatingPoint` และ helper คำนวณผลส่วนท้ายร่วมกัน จากนั้น `app.py` เลือก validator/ฟังก์ชันตาม `mode` ด้วย `if/elif` และเทมเพลตแสดงเฉพาะช่องของโหมดนั้นโดยโหลดหน้าใหม่ผ่าน GET ไม่ใช้ JavaScript

**Tech Stack:** Python 3, Flask, Jinja2, unittest เดิม, เบราว์เซอร์ในตัว OpenCode สำหรับ acceptance

**Spec:** `docs/superpowers/specs/2026-11-17-lab03-bjt-bias-modes-design.md`

## Global Constraints

- ตามขอบเขตใบงาน: **ไม่เพิ่ม unittest ใหม่** ใช้เทสต์เดิม + สคริปต์ตรวจชั่วคราว + browser acceptance
- คงผล Voltage Divider เดิมทุกค่า รวมถึง nodal comparison และชื่อฟังก์ชันที่เทสต์ patch อยู่
- ฟอร์มใช้หน่วย Ω, V, mA ตามเดิม; ไม่เปลี่ยนเป็น kΩ
- โหมดที่ไม่รู้จักต้องแจ้ง error ไม่ fallback เป็น Divider
- ไม่ใช้ JavaScript, ไม่เพิ่ม dependency
- ไม่ push GitHub; commit local
- เกณฑ์ acceptance: `IC` คลาดเคลื่อน ≤ 0.01 mA, `VCE` ≤ 0.02 V จากค่าอ้างอิงที่ยังไม่ปัดเศษ
- ค่าอ้างอิง A1–A5 ต้องมาจากสมการ (คำนวณนอกโปรแกรม) ไม่ใช่ดึงจากฟังก์ชันที่กำลังตรวจ

## Review Focus

- **โหมดไม่รู้จัก** (`mode=bogus`) ต้องขึ้น error และไม่คำนวณด้วย Divider — เพิ่มใน Task 2
- **Fixed Bias ต้องไม่บังคับ R1/R2/RE** และไม่สนค่าที่ส่งมาเกิน — เพิ่มใน Task 1/2
- **สลับโหมดแล้วค่าที่กรอกหาย/ช่องผิดโหมดแสดง** — ต้องคงค่า common และแสดงเฉพาะช่องของโหมด — Task 3
- **อินพุตผิดต้องไม่ค้างผลรอบก่อน** (A5) — Task 2/3
- **Cutoff/Saturation ของโหมดใหม่ใช้ IC(sat) ถูกตัวหาร** (Fixed ใช้ RC เท่านั้น) — Task 1
- **ค่าจำนวนมากแต่ finite ต้องไม่ทำให้หน้า 500** — Task 1/2

---

### Task 1: สมการและ validation ของสามโหมดใน `bjt.py`

**Files:**
- Modify: `bjt.py`
- Test: `tests/test_bjt.py` (เทสต์เดิมต้องผ่าน ไม่แก้ assertions)

**Interfaces:**
- Produces:
  - `MODE_DIVIDER = "divider"`, `MODE_FIXED = "fixed"`, `MODE_EMITTER = "emitter"`, `MODES`
  - `MODE_FIELDS: dict[str, tuple[str, ...]]` — ฟิลด์ที่แต่ละโหมดใช้
  - `FixedBiasInputs(vcc_v, rb_ohm, rc_ohm, beta, vbe_v)` (frozen dataclass)
  - `EmitterBiasInputs(vcc_v, rb_ohm, rc_ohm, re_ohm, beta, vbe_v)` (frozen dataclass)
  - `validate_fixed_bias(raw) -> tuple[FixedBiasInputs | None, dict[str, str]]`
  - `validate_emitter_bias(raw) -> tuple[EmitterBiasInputs | None, dict[str, str]]`
  - `calculate_fixed_bias(inputs: FixedBiasInputs) -> OperatingPoint`
  - `calculate_emitter_bias(inputs: EmitterBiasInputs) -> OperatingPoint`
- Consumes: `OperatingPoint`, `classify_region`, `VCE_SAT_V`, `MAX_INPUT`, `BiasInputs`, `validate_inputs` เดิม

- [ ] **Step 1: เพิ่มค่าคงที่โหมดและตารางฟิลด์**

เพิ่มหลัง `FIELD_NAMES`:

```python
MODE_DIVIDER = "divider"
MODE_FIXED = "fixed"
MODE_EMITTER = "emitter"
MODES = (MODE_DIVIDER, MODE_FIXED, MODE_EMITTER)

MODE_FIELDS = {
    MODE_DIVIDER: ("vcc", "r1", "r2", "rc", "re", "beta", "vbe"),
    MODE_FIXED: ("vcc", "rb", "rc", "beta", "vbe"),
    MODE_EMITTER: ("vcc", "rb", "rc", "re", "beta", "vbe"),
}
```

- [ ] **Step 2: เพิ่ม dataclass และ validator ตามโหมด**

ดึงตรรกะแปลงตัวเลข (ว่าง/ไม่ใช่ตัวเลข/ไม่ finite/เกิน `MAX_INPUT`) ของ `validate_inputs` ออกเป็น helper `_parse_fields(raw, names) -> tuple[dict[str, float], dict[str, str]]` แล้วให้ `validate_inputs` ใช้ helper นี้ จากนั้น:

- `validate_fixed_bias`: peak fields `vcc, rb, rc, beta, vbe`; ตรวจ `vcc > 0`, `rb > 0`, `rc > 0`, `beta >= 1`, `0 <= vbe < vcc` ด้วยข้อความเดิม
- `validate_emitter_bias`: เพิ่ม `re` และตรวจ `re > 0`
- ข้อความ error ทุกข้อความใช้ชุดเดิม (`"กรุณากรอกเป็นตัวเลข"`, `"ต้องเป็นจำนวนจำกัด"`, `"ต้องมีค่าไม่เกิน 1e12"`, `"ต้องมากกว่า 0 Ω"`, `"ต้องมีค่าอย่างน้อย 1"`, `"ต้องอยู่ระหว่าง 0 ถึง VCC"`)

- [ ] **Step 3: เพิ่ม helper ผลลัพธ์ร่วมและฟังก์ชันคำนวณ**

เพิ่ม `_finish_operating_point(*, vcc_v, rc_ohm, re_ohm, beta, vbe_v, ib_a, vbb_v, rb_ohm, vb_cutoff_v) -> OperatingPoint`:

- `ib <= 0` → คืน cutoff (`ib=ic=ie=0`, `ve=0`, `vb=vb_cutoff_v`, `vc=vcc_v`, `vce=vcc_v`)
- ปกติ → `ic=beta*ib`, `ie=(beta+1)*ib`, `ve=ie*re_ohm`, `vb=ve+vbe_v`, `vc=vcc_v-ic*rc_ohm`, `vce=vc-ve`, `classify_region`
- saturation → `ic_sat=(vcc_v-0.2)/(rc_ohm+re_ohm)`
- เรียก `_ensure_finite` เหมือนเดิม

ใช้ helper นี้ใน `calculate_operating_point` (Divider) โดยให้ `vb_cutoff_v = vbb` และคงค่าผลลัพธ์เดิมเป๊ะ จากนั้น:

```python
def calculate_fixed_bias(inputs: FixedBiasInputs) -> OperatingPoint:
    ib = (inputs.vcc_v - inputs.vbe_v) / inputs.rb_ohm
    return _finish_operating_point(
        vcc_v=inputs.vcc_v, rc_ohm=inputs.rc_ohm, re_ohm=0.0,
        beta=inputs.beta, vbe_v=inputs.vbe_v, ib_a=ib,
        vbb_v=inputs.vcc_v, rb_ohm=inputs.rb_ohm,
        vb_cutoff_v=inputs.vcc_v,
    )

def calculate_emitter_bias(inputs: EmitterBiasInputs) -> OperatingPoint:
    ib = (inputs.vcc_v - inputs.vbe_v) / (
        inputs.rb_ohm + (inputs.beta + 1) * inputs.re_ohm
    )
    return _finish_operating_point(
        vcc_v=inputs.vcc_v, rc_ohm=inputs.rc_ohm, re_ohm=inputs.re_ohm,
        beta=inputs.beta, vbe_v=inputs.vbe_v, ib_a=ib,
        vbb_v=inputs.vcc_v, rb_ohm=inputs.rb_ohm,
        vb_cutoff_v=inputs.vcc_v,
    )
```

- [ ] **Step 4: ตรวจตัวเลข A1–A5 ด้วยสมการตรง (ไม่ผ่าน Flask)**

Run:

```powershell
.\.venv\Scripts\python.exe -c "from bjt import *; f,_=validate_fixed_bias({'vcc':'12','rb':'1000000','rc':'2200','beta':'100','vbe':'0.7'}); r=calculate_fixed_bias(f); print(r.ic_a*1e3, r.vce_v); e,_=validate_emitter_bias({'vcc':'12','rb':'1000000','rc':'2200','re':'1000','beta':'100','vbe':'0.7'}); r=calculate_emitter_bias(e); print(r.ic_a*1e3, r.vce_v)"
```

Expected: Fixed `1.13 9.514`; Emitter `1.0263396912 8.7054495913` (ค่าอ้างอิง A2/A3)
ตรวจเพิ่ม: `validate_fixed_bias` ไม่มี `r1/r2/re` ก็ผ่าน; `rb=0` คืน error; `mode` ปลอมไม่เกี่ยวกับไฟล์นี้

- [ ] **Step 5: รันเทสต์เดิมทั้งชุด**

Run: `.\.venv\Scripts\python.exe -m unittest discover -v`
Expected: PASS ทั้งหมด (โดยเฉพาะค่า Divider เดิมใน `TestCalculateOperatingPoint`)

- [ ] **Step 6: Commit**

```powershell
git add bjt.py
git commit -m "feat: add fixed and emitter bias calculations"
```

---

### Task 2: เลือกโหมดและตรวจอินพุตใน `app.py`

**Files:**
- Modify: `app.py`
- Test: `tests/test_app.py` (เทสต์เดิมต้องผ่าน)

**Interfaces:**
- Consumes: `MODE_*`, `MODES`, `MODE_FIELDS`, validators และฟังก์ชันคำนวณจาก Task 1
- Produces:
  - `MODE_DEFAULTS: dict[str, dict[str, str]]`
  - `MODE_LABELS: dict[str, str]`
  - `FORM_FIELDS: dict[str, list[tuple[str, str, str, str]]]` — `(name, symbol, label, unit)` ต่อโหมด
  - route `/` รับ `mode` จาก query (GET) หรือฟอร์ม (POST)
  - template context: `mode`, `mode_label`, `mode_options`, `fields`

- [ ] **Step 1: เพิ่มค่าเริ่มต้นและ metadata ของโหมด**

`MODE_DEFAULTS[MODE_DIVIDER]` คือ `DEFAULTS` เดิมทั้งก้อน; เพิ่ม

```python
MODE_DEFAULTS = {
    MODE_DIVIDER: {...ค่าเดิม...},
    MODE_FIXED: {"vcc": "12", "rb": "1000000", "rc": "2200", "beta": "150", "vbe": "0.7"},
    MODE_EMITTER: {"vcc": "12", "rb": "1000000", "rc": "2200", "re": "1000", "beta": "150", "vbe": "0.7"},
}
MODE_LABELS = {
    MODE_DIVIDER: "Voltage Divider Bias",
    MODE_FIXED: "Fixed Bias",
    MODE_EMITTER: "Emitter Bias",
}
```

คง `DEFAULTS = MODE_DEFAULTS[MODE_DIVIDER]` เพื่อความเข้ากันได้ และสร้าง `FORM_FIELDS` จาก `MODE_FIELDS` + รายละเอียดฟิลด์เดิม

- [ ] **Step 2: แก้ route ให้เลือกโหมด**

ตรรกะ:

1. `raw_mode = request.values.get("mode")`; ถ้าเป็น `None`/ว่าง → `MODE_DIVIDER`
2. ถ้าไม่ใช่ค่าใน `MODES` → `errors["_form"] = "ไม่รู้จักโหมดไบอัสที่เลือก กรุณาเลือกจากรายการ"` แล้วใช้ `MODE_DIVIDER` เพื่อวาดฟอร์ม แต่ **ไม่คำนวณ**
3. GET: เริ่มจาก `MODE_DEFAULTS[mode]` แล้วทับด้วยค่าที่มีใน query เฉพาะฟิลด์ของโหมด
4. POST: เก็บ `{name: request.form.get(name, "") for name in MODE_FIELDS[mode]}` แล้วเรียก validator ตามโหมด (`if/elif`)
5. คำนวณด้วย `if/elif`: Divider → `calculate_operating_point` + nodal comparison; Fixed → `calculate_fixed_bias`; Emitter → `calculate_emitter_bias`
6. ถ้ามี error ใด ๆ ให้ `result = None`, `comparison = None` (ห้ามค้างผลรอบก่อน)
7. ส่ง context เพิ่ม: `mode`, `mode_label`, `mode_options=[(m, MODE_LABELS[m]) for m in MODES]`, `fields=FORM_FIELDS[mode]`

คงการ import ชื่อ `calculate_operating_point` และ `calculate_nodal_operating_point` แบบตรง ๆ เพื่อให้เทสต์เดิมที่ `patch("app....")` ยังทำงาน

- [ ] **Step 3: ตรวจ route ด้วย Flask test client**

Run:

```powershell
.\.venv\Scripts\python.exe -c "from app import create_app; c=create_app().test_client(); print('fixed', c.post('/', data={'mode':'fixed','vcc':'12','rb':'1000000','rc':'2200','beta':'100','vbe':'0.7'}).status_code); print('emitter', c.post('/', data={'mode':'emitter','vcc':'12','rb':'1000000','rc':'2200','re':'1000','beta':'100','vbe':'0.7'}).status_code); print('bogus', 'ไม่รู้จักโหมด' in c.post('/', data={'mode':'bogus'}).get_data(as_text=True)); print('rb0', 'ต้องมากกว่า 0' in c.post('/', data={'mode':'fixed','vcc':'12','rb':'0','rc':'2200','beta':'100','vbe':'0.7'}).get_data(as_text=True))"
```

Expected: `fixed 200`, `emitter 200`, `bogus True`, `rb0 True`

- [ ] **Step 4: รันเทสต์เดิมทั้งชุด**

Run: `.\.venv\Scripts\python.exe -m unittest discover -v`
Expected: PASS ทั้งหมด

- [ ] **Step 5: Commit**

```powershell
git add app.py
git commit -m "feat: dispatch bias mode in Flask route"
```

---

### Task 3: ฟอร์มและผลลัพธ์แยกตามโหมดใน `templates/index.html`

**Files:**
- Modify: `templates/index.html`
- Modify: `static/style.css` (เฉพาะถ้าต้องการจัดปุ่ม/select)

**Interfaces:**
- Consumes: `mode`, `mode_label`, `mode_options`, `fields`, `values`, `errors`, `result`, `comparison` จาก Task 2

- [ ] **Step 1: เพิ่มตัวเลือกโหมดและปุ่มเปลี่ยนโหมด**

ใน `<form method="post" action="/">` วาง select `name="mode"` ก่อนช่องอินพุต แล้วเพิ่มปุ่มที่สอง:

```html
<button type="submit">คำนวณ</button>
<button type="submit" formmethod="get" formaction="/">เปลี่ยนโหลดฟอร์ม</button>
```

ปุ่ม GET ต้องอยู่ในฟอร์มเดียวกันเพื่อส่งค่าที่กรอกไปเป็น query และรักษาค่า common เมื่อสลับโหมด

- [ ] **Step 2: แสดงเฉพาะช่องของโหมด**

แทน `{% set fields = [...] %}` เดิมด้วยลูปจาก `fields` ที่ส่งมาจาก app:

```jinja
{% for name, symbol, label, unit in fields %}
...
{% endfor %}
```

ช่องที่แสดงต้องมี `required`; ช่องของโหมดอื่นต้องไม่ถูก render เลย

- [ ] **Step 3: แสดงผลตามโหมด**

- หัวผลลัพธ์แสดง `{{ mode_label }}`
- `VBB` แสดงเฉพาะ `mode == "divider"`; `RB` แสดงทุกโหมด
- ส่วน `Nodal Analysis` ทั้งบล็อกแสดงเฉพาะ `{% if comparison %}`
- ส่วนสูตรด้านล่างแสดงคนละชุดตาม `mode` (Divider ใช้ของเดิม, Fixed/Emitter ตามสมการ Task 1)
- คง `data-circuit="bjt-ce"` และ SVG เดิมไว้ (เทสต์เดิมตรวจ)

- [ ] **Step 4: ตรวจ HTML จาก test client**

Run:

```powershell
.\.venv\Scripts\python.exe -c "from app import create_app; c=create_app().test_client(); b=c.get('/?mode=fixed').get_data(as_text=True); print('rb', 'name=\"rb\"' in b, 'r1', 'name=\"r1\"' in b, 'selected', 'value=\"fixed\" selected' in b); b=c.post('/', data={'mode':'fixed','rb':'0','vcc':'12','rc':'2200','beta':'100','vbe':'0.7'}).get_data(as_text=True); print('no stale', 'id=\"results\"' not in b)"
```

Expected: `rb True r1 False selected True`; `no stale True`

- [ ] **Step 5: Commit**

```powershell
git add templates/index.html static/style.css
git commit -m "feat: add bias mode selector to form"
```

---

### Task 4: README และตารางผลตรวจ A1–A5

**Files:**
- Modify: `README.md`
- Create: `docs/validation.md`

**Interfaces:**
- Consumes: ชื่อโหมด/ฟิลด์/สมการจาก Task 1–3

- [ ] **Step 1: อัปเดต README**

เพิ่ม/แก้: ชื่อแอปสามโหมด, ตารางอินพุตตามโหมด (`rb` สำหรับ Fixed/Emitter), สมการ Fixed/Emitter, วิธีรัน/ทดสอบเดิม, ตัวอย่าง Divider เดิมต้องคงอยู่, ระบุว่าส่วนใด AI ช่วยสร้างและตรวจอะไร

- [ ] **Step 2: สร้าง `docs/validation.md`**

ใส่ตาราง A1–A5 ที่มีคอลัมน์: กรณี, โหมด+อินพุต, ค่าคาดหมาย, ผลจริง, วิธีตรวจ, สถานะ, หลักฐาน
ค่าคาดหมาย (คำนวณมือจากสมการ, VCC=12, RC=2.2k, β=100, VBE=0.70):

| กรณี | IC (mA) | VCE (V) | หมายเหตุ |
|---|---|---|---|
| A1 Divider R1=100k R2=22k RE=1k | 1.2298581463 | 8.0521553505 | VBB=2.1639344262, RB=18032.7869 |
| A2 Fixed RB=1M | 1.13 | 9.514 | VE=0, VB=0.7 |
| A3 Emitter RB=1M RE=1k | 1.0263396912 | 8.7054495913 | VE=1.0366030881 |
| A4 Emitter RB=1M RE=2k | 0.9400998336 | 8.0327787022 | IC ลดจาก A3 |
| A5 Fixed RB=0 | — | — | ต้องมี error เรื่อง RB |

ระบุสมการที่ใช้และเกณฑ์ tolerance; ช่อง "ผลจริง/สถานะ" เว้นไว้ก่อนจนถึง Task 5

- [ ] **Step 3: Commit**

```powershell
git add README.md docs/validation.md
git commit -m "docs: document lab 03 bias modes and acceptance cases"
```

---

### Task 5: ตรวจ A1–A5 ผ่านเบราว์เซอร์และสรุปหลักฐาน

**Files:**
- Modify: `docs/validation.md`
- Create: `docs/evidence/` (ถ้าเก็บ screenshot)

**Interfaces:**
- Consumes: แอปที่รันได้จาก Task 2–3 และค่าอ้างอิงจาก Task 4

- [ ] **Step 1: เปิดใช้ browser skill และรัน Flask**

Run (background): `.\.venv\Scripts\python.exe app.py`
เปิด `http://127.0.0.1:5000/` ด้วยเครื่องมือ browser ของ OpenCode (ระบุวิธีจริงว่า OpenCode Browser)

- [ ] **Step 2: ทดสอบ A1–A5 ตามลำดับ**

- A1: เลือก Divider, กรอก R1=100000, R2=22000, RE=1000, RC=2200, VCC=12, β=100, VBE=0.7 → อ่าน IC/VCE
- A2: Fixed, RB=1000000 → ต้องไม่ต้องกรอก R1/R2/RE
- A3: Emitter, RB=1000000, RE=1000
- A4: Emitter, เปลี่ยนเฉพาะ RE=2000 แล้วคำนวณใหม่ ยืนยันว่าโหมดยังเป็น Emitter และ IC ลดลง
- A5: Fixed, RB=0 → ต้องเห็นข้อความให้แก้ RB และไม่มีผลรอบก่อน

บันทึกข้อความผลจริงพร้อมหน่วย และถ่าย screenshot อย่างน้อยหนึ่งกรณี

- [ ] **Step 3: เติมผลจริงและสถานะใน `docs/validation.md`**

ใช้ `PASS` เมื่อตรงเกณฑ์, `FAIL` เมื่อรันแล้วไม่ตรง, `NOT RUN` พร้อมเหตุผลถ้าเครื่องมือไม่พร้อม ระบุวิธีจริง (OpenCode Browser)

- [ ] **Step 4: ตรวจรอบสุดท้าย**

Run: `.\.venv\Scripts\python.exe -m unittest discover -v`
Expected: PASS ทั้งหมด
Run: `git diff --check`
Expected: ไม่มี whitespace error
ตรวจ `git status` ว่าไม่มี `.venv`, `__pycache__`, `.env` ถูก stage

- [ ] **Step 5: Commit**

```powershell
git add docs/validation.md docs/evidence
git commit -m "docs: record browser acceptance results for lab 03"
```

# BJT Common-Emitter DC Bias Calculator

เว็บแอป Flask ขนาดเล็กสำหรับคำนวณจุดทำงาน DC (DC operating point) ของทรานซิสเตอร์
NPN แบบ common-emitter รองรับสามโหมดไบอัส ได้แก่ **Voltage Divider Bias**,
**Fixed Bias** และ **Emitter Bias แบบแหล่งจ่ายเดียว** เหมาะสำหรับแลป ENG29 2121
Lab 02–03

แอปแสดงกระแสและแรงดันทุกจุดพร้อมหน่วย ตรวจสอบค่าอินพุตตามโหมด เตือนเมื่อทรานซิสเตอร์
อยู่นอกย่าน active และสำหรับโหมด Voltage Divider ยังคำนวณผลซ้ำด้วยอีกวิธีหนึ่ง
(nodal analysis) เพื่อเทียบผล

## Features

- เลือกโหมดไบอัสด้วยแท็บเหนือฟอร์ม แล้วโหลดฟอร์มใหม่ให้แสดงเฉพาะช่องของโหมดนั้น (ไม่ใช้ JavaScript)
- Fixed Bias ใช้ `VCC`, `RB`, `RC`, `β`, `VBE`
- Emitter Bias ใช้ `VCC`, `RB`, `RC`, `RE`, `β`, `VBE`
- Voltage Divider Bias ใช้ `VCC`, `R1`, `R2`, `RC`, `RE`, `β`, `VBE` (ของเดิมจาก Lab 02)
- แสดง `RB`, `IB`, `IC`, `IE`, `VE`, `VB`, `VC`, `VCE` พร้อมหน่วย และแสดง `VBB` เฉพาะ Divider
- Validation ฝั่งเซิร์ฟเวอร์พร้อม error รายช่อง เฉพาะช่องที่โหมดนั้นต้องใช้
- โหมดที่ไม่รู้จักแจ้งข้อผิดพลาด ไม่เดาเป็น Divider
- อินพุตผิดไม่แสดงผลของรอบก่อนค้างไว้
- แบ่ง region เป็น `Active`, `Cutoff`, `Saturation` และอธิบายสาเหตุ
- แสดง `IC(sat)` เมื่ออยู่ในย่าน saturation (Fixed ใช้ `RC` เท่านั้น, Emitter/Divider ใช้ `RC + RE`)
- ตารางเปรียบเทียบกับ independent nodal calculation เฉพาะโหมด Divider พร้อม `MATCH` / `MISMATCH`
- แสดงแผนภาพวงจร common-emitter เป็น inline SVG ตามโหมด (ไม่ใช้ JavaScript หรือรูปภายนอก)
- หน้าเดียว ไม่ใช้ JavaScript framework หรือ CDN

## Inputs

| ค่า | ความหมาย | หน่วย | ใช้ในโหมด |
|---|---|---|---|
| `VCC` | แรงดันไฟเลี้ยง | V | ทั้งสามโหมด |
| `RB` | ตัวต้านทานฐานต่อจาก VCC | Ω | Fixed, Emitter |
| `R1` | ตัวต้านทานฐานตัวบน | Ω | Divider |
| `R2` | ตัวต้านทานฐานตัวล่าง | Ω | Divider |
| `RC` | ตัวต้านทานคอลเลกเตอร์ | Ω | ทั้งสามโหมด |
| `RE` | ตัวต้านทานอิมิตเตอร์ | Ω | Divider, Emitter |
| `β` | อัตราขยายกระแส (hFE) | — | ทั้งสามโหมด |
| `VBE` | แรงดันฐาน-อิมิตเตอร์ | V | ทั้งสามโหมด |

ฟอร์มใช้หน่วย Ω โดยตรง ไม่ต้องแปลงเป็น kΩ ก่อนกรอก

## Equations

### Fixed Bias

```
IB  = (VCC − VBE) / RB
IC  = β·IB
IE  = (β + 1)·IB
VE  = 0 V
VB  = VBE
VC  = VCC − IC·RC
VCE = VC
```

### Emitter Bias (single supply)

```
IB  = (VCC − VBE) / (RB + (β + 1)·RE)
IC  = β·IB
IE  = (β + 1)·IB
VE  = IE·RE
VB  = VE + VBE
VC  = VCC − IC·RC
VCE = VC − VE
```

### Voltage Divider Bias (Method A)

```
VBB = VCC · R2 / (R1 + R2)
RB  = R1 ∥ R2 = R1·R2 / (R1 + R2)
IB  = (VBB − VBE) / (RB + (β + 1)·RE)
IC  = β·IB
IE  = (β + 1)·IB
VE  = IE·RE
VB  = VE + VBE
VC  = VCC − IC·RC
VCE = VC − VE
```

Region:

- `IB <= 0` → **Cutoff** (กระแสเป็นศูนย์, `VCE = VCC`)
- `VCE <= 0.2 V` → **Saturation** (สมการ active-region ใช้ไม่ได้จริง)
- นอกนั้น → **Active**

`VCE(sat)` ถูกกำหนดคงที่ที่ `0.2 V` และ `IC(sat) = (VCC − 0.2) / (RC + RE)`
สำหรับ Divider/Emitter หรือ `(VCC − 0.2) / RC` สำหรับ Fixed

## Independent check: Method B (Divider only)

Method B ใช้สมการ KCL แบบ nodal ที่ไม่เหมือนสูตร Thevenin โดยตรง:

```
(1/R1 + 1/R2)·VB                    + IB       = VCC/R1
                  (1/RE)·VE         − (β+1)·IB = 0
                              (1/RC)·VC + β·IB  = VCC/RC
VB − VE                                        = VBE
```

แก้ระบบ 4×4 ด้วย Gaussian elimination แล้วแปลงกลับเป็น `IB, IC, IE, VB, VE, VC, VCE`
ค่าจากทั้งสองวิธีถูกเทียบกันด้วย relative difference แบบ zero-safe และรายงาน
`MATCH` เมื่อผลต่างสูงสุด ≤ `1e-9` การตรงกันยืนยันความถูกต้องของการคำนวณ
ไม่ได้ยืนยันความถูกต้องทางกายภาพเมื่ออยู่นอกย่าน active

โหมด Fixed และ Emitter ใช้สมการตรงตามใบงานและไม่มีการเทียบ nodal ใน Lab นี้

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

```powershell
.\.venv\Scripts\python.exe app.py
```

เปิด `http://127.0.0.1:5000` สลับโหมดด้วยแท็บ **Voltage Divider Bias / Fixed Bias / Emitter Bias**
เพื่อโหลดช่องอินพุตของโหมดนั้น จากนั้นกรอกค่าและกด **คำนวณจุดทำงาน**

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

ตามขอบเขต Lab 03 ไม่ได้เพิ่ม unittest ใหม่ แต่เทสต์เดิมของ Lab 02 ทั้งหมดยังต้องผ่าน
และมีการตรวจรับ A1–A5 ผ่านเบราว์เซอร์จริง บันทึกไว้ที่
[`docs/validation.md`](docs/validation.md)

## Lab 03 — Browser acceptance (A1–A5)

ด้านล่างนี้คือเนื้อหาจาก [`docs/validation.md`](docs/validation.md) แบบเต็ม

เอกสารนี้บันทึกผลตรวจรับเว็บ BJT DC Bias ตามใบงาน ENG29 2121 Lab 03
ค่าอ้างอิงทั้งหมดคำนวณจากสมการในใบงานด้วยสคริปต์/เครื่องคิดเลขแยก
**ไม่ได้ import `bjt.py` หรือดึงค่าจากโปรแกรมที่กำลังตรวจ**

### เงื่อนไขร่วม

- `VCC = 12 V`, `RC = 2.2 kΩ`, `β = 100`, `VBE = 0.70 V`
- ฟอร์มรับค่าต้านทานเป็น Ω
- เกณฑ์เทียบกับค่าอ้างอิงที่ยังไม่ปัดเศษ: `IC` ต่างไม่เกิน **0.01 mA**, `VCE` ต่างไม่เกิน **0.02 V**
- สถานะ: `PASS` = ผลที่เห็นตรงเกณฑ์, `FAIL` = รันแล้วไม่ตรง, `NOT RUN` = เครื่องมือ/เว็บไม่พร้อม

### ค่าอ้างอิงที่คำนวณแยกจากโปรแกรม

#### A1 — Voltage Divider, R1 = 100 kΩ, R2 = 22 kΩ, RE = 1 kΩ

```
VBB = 12 × 22 / (100 + 22)              = 2.1639344262 V
RB  = 100 × 22 / (100 + 22)             = 18.0327868852 kΩ
IB  = (2.1639344262 − 0.70)
      / (18032.7868852 + (100 + 1) × 1000)
                                        = 12.2985814626 µA
IC  = 100 × IB                          = 1.2298581463 mA
IE  = 101 × IB                          = 1.2421567277 mA
VE  = IE × 1000                         = 1.2421567277 V
VB  = VE + 0.70                         = 1.9421567277 V
VC  = 12 − IC × 2200                    = 9.2943120782 V
VCE = VC − VE                           = 8.0521553505 V
```

#### A2 — Fixed Bias, RB = 1 MΩ

```
IB  = (12 − 0.70) / 1 000 000           = 11.3000000000 µA
IC  = 100 × IB                          = 1.1300000000 mA
IE  = 101 × IB                          = 1.1413000000 mA
VE  = 0 V
VB  = 0.70 V
VC  = 12 − IC × 2200                    = 9.5140000000 V
VCE = VC − VE                           = 9.5140000000 V
```

#### A3 — Emitter Bias, RB = 1 MΩ, RE = 1 kΩ

```
IB  = (12 − 0.70) / (1 000 000 + 101 × 1000)
                                        = 10.2633969119 µA
IC  = 100 × IB                          = 1.0263396912 mA
IE  = 101 × IB                          = 1.0366030881 mA
VE  = IE × 1000                         = 1.0366030881 V
VB  = VE + 0.70                         = 1.7366030881 V
VC  = 12 − IC × 2200                    = 9.7420526794 V
VCE = VC − VE                           = 8.7054495913 V
```

#### A4 — Emitter Bias, RB = 1 MΩ, RE = 2 kΩ (เปลี่ยนค่าเดียวจาก A3)

```
IB  = (12 − 0.70) / (1 000 000 + 101 × 2000)
                                        = 9.4009983361 µA
IC  = 100 × IB                          = 0.9400998336 mA
IE  = 101 × IB                          = 0.9495008319 mA
VE  = IE × 2000                         = 1.8990016639 V
VB  = VE + 0.70                         = 2.5990016639 V
VC  = 12 − IC × 2200                    = 9.9317803661 V
VCE = VC − VE                           = 8.0327787022 V
```

**ทำนายก่อนรัน A4:** เมื่อ `RE` เพิ่มจาก 1 kΩ เป็น 2 kΩ ในวงจร Emitter Bias
กระแสฐานจะลดลงเพราะตัวส่วน `RB + (β + 1)RE` ใหญ่ขึ้น ดังนั้น `IC` ต้องลดลงจาก A3

#### A5 — Fixed Bias, RB = 0

`RB` ต้องเป็นตัวต้านทานบวก ฟอร์ม/Flask ต้องแจ้งให้แก้ `RB` และต้องไม่แสดงผลของรอบก่อน

### ตารางตรวจรับ

| กรณี | เลือกโหมดและกรอกค่า | คาดหมายก่อนรัน | เห็นจริง | วิธีตรวจ | สถานะ | หลักฐาน |
|---|---|---|---|---|---|---|
| A1 · โหมดเดิม | Divider · R1 = 100000 Ω, R2 = 22000 Ω, RE = 1000 Ω, RC = 2200 Ω, VCC = 12 V, β = 100, VBE = 0.7 V | IC = 1.2298581463 mA · VCE = 8.0521553505 V · Active | IC = 1.2299 mA · VCE = 8.0522 V · Active · MATCH | OpenCode Browser | PASS | ตารางผลบนหน้าเว็บ |
| A2 · Fixed | Fixed · RB = 1000000 Ω, RC = 2200 Ω, VCC = 12 V, β = 100, VBE = 0.7 V (ไม่ต้องกรอก R1/R2/RE) | IC = 1.13 mA · VCE = 9.514 V · Active | IC = 1.13 mA · VCE = 9.514 V · Active (ฟอร์มมีเฉพาะ VCC, RB, RC, β, VBE) | OpenCode Browser | PASS | ตารางผลบนหน้าเว็บ |
| A3 · Emitter | Emitter · RB = 1000000 Ω, RE = 1000 Ω, RC = 2200 Ω, VCC = 12 V, β = 100, VBE = 0.7 V | IC = 1.0263396912 mA · VCE = 8.7054495913 V · Active | IC = 1.0263 mA · VCE = 8.7054 V · Active | OpenCode Browser | PASS | `docs/evidence/A3-emitter.png` |
| A4 · เปลี่ยนค่าเดียว | Emitter · เหมือน A3 แต่ RE = 2000 Ω | IC = 0.9400998336 mA · VCE = 8.0327787022 V · IC ลดจาก A3 | IC = 940.0998 µA (0.9401 mA) · VCE = 8.0328 V · IC ลดจาก A3 ตามทำนาย | OpenCode Browser | PASS | ตารางผลบนหน้าเว็บ (โหมดยังเป็น Emitter, RE = 2000) |
| A5 · อินพุตผิด | Fixed · RB = 0 Ω | มีข้อความให้แก้ RB, เว็บไม่ล่ม, ไม่แสดงผลเดิม | ข้อความ `ต้องมากกว่า 0 Ω` ใต้ช่อง RB, ไม่มีส่วนผลลัพธ์ | OpenCode Browser | PASS | `docs/evidence/A5-fixed-rb0.png` |

### หลักฐานจากเบราว์เซอร์

- วิธีตรวจจริง: **OpenCode Browser (browser tool ในแอป)** — ไม่ได้ใช้ Playwright MCP
  ตามทางเลือกสำรองที่ใบงานอนุญาต; เปิด `http://127.0.0.1:5000/` และกรอกฟอร์มจริง
- ข้อความผลที่คัดจากหน้าเว็บ (A3): `ผลลัพธ์ · Emitter Bias`, `Active`,
  `IC 1.0263 mA`, `VCE 8.7054 V`, `VE 1.0366 V`
- ข้อความ error ที่คัดจากหน้าเว็บ (A5): `ต้องมากกว่า 0 Ω` ใต้ช่อง `ตัวต้านทานฐาน RB`
  และไม่มีการ์ดผลลัพธ์ (แสดงการ์ด `พร้อมคำนวณ` แทน)
- Screenshot: `docs/evidence/A3-emitter.png` (A3) และ
  `docs/evidence/A5-fixed-rb0.png` (A5)

### บทบาทของ AI และสิ่งที่นักศึกษาตรวจ

- AI สร้างฟังก์ชันคำนวณ Fixed/Emitter, validator ตามโหมด, การเลือกโหมดใน route
  และการแสดงฟอร์ม/ผลตามโหมด
- นักศึกษาตรวจสมการกับใบงาน/Engineering Electronics, ตรวจหน่วย, ตรวจว่าโหมด Fixed
  ไม่บังคับช่อง R1/R2/RE, ตรวจว่า A4 เปลี่ยน `RE` แล้วค่าที่เข้าสมการเปลี่ยนจริง
- ค่าอ้างอิงในเอกสารนี้คำนวณก่อนรันและไม่ขึ้นกับผลจากโปรแกรม

## Worked examples

### Voltage Divider Bias (ค่าเริ่มต้นเดิม)

`VCC = 12 V`, `R1 = 47 kΩ`, `R2 = 10 kΩ`, `RC = 2.2 kΩ`, `RE = 1 kΩ`,
`β = 150`, `VBE = 0.7 V`

| ค่า | ผลลัพธ์ |
|---|---|
| VBB | 2.1053 V |
| RB | 8245.614 Ω |
| IB | 8.8245 µA |
| IC | 1.3237 mA |
| IE | 1.3325 mA |
| VE | 1.3325 V |
| VB | 2.0325 V |
| VC | 9.0879 V |
| VCE | 7.7554 V |
| Region | Active |

### Fixed Bias

`VCC = 12 V`, `RB = 1 MΩ`, `RC = 2.2 kΩ`, `β = 100`, `VBE = 0.70 V`

| ค่า | ผลลัพธ์ |
|---|---|
| IB | 11.3 µA |
| IC | 1.13 mA |
| IE | 1.1413 mA |
| VE | 0 V |
| VB | 0.7 V |
| VC | 9.514 V |
| VCE | 9.514 V |
| Region | Active |

### Emitter Bias

`VCC = 12 V`, `RB = 1 MΩ`, `RC = 2.2 kΩ`, `RE = 1 kΩ`, `β = 100`, `VBE = 0.70 V`

| ค่า | ผลลัพธ์ |
|---|---|
| IB | 10.2634 µA |
| IC | 1.0263 mA |
| IE | 1.0366 mA |
| VE | 1.0366 V |
| VB | 1.7366 V |
| VC | 9.7421 V |
| VCE | 8.7054 V |
| Region | Active |

ถ้าเปลี่ยน `RE` เป็น `2 kΩ` โดยคงค่าอื่น จะได้ `IC = 0.9401 mA` และ
`VCE = 8.0328 V` (กระแสลดลงเพราะความต้านทานอิมิตเตอร์เพิ่มขึ้น)

## Project structure

```
bjt.py                  engineering logic (validation, three bias modes, Method B, comparison)
app.py                  Flask app factory, mode selection and routes
templates/index.html    single-page form and results, mode-aware circuit SVG
static/style.css        plain CSS
tests/test_bjt.py       calculation, validation, region, comparison tests (Lab 02)
tests/test_app.py       formatting and route tests (Lab 02)
docs/validation.md      Lab 03 browser acceptance A1–A5 and independent reference values
requirements.txt        Flask
```

## Lab 03 notes: AI-assisted work

- AI ช่วยสร้างฟังก์ชัน `calculate_fixed_bias`, `calculate_emitter_bias`, validator ตามโหมด
  และการเลือกโหมดใน route/template
- นักศึกษาตรวจสมการจาก Engineering Electronics เทียบกับโค้ด ตรวจหน่วยที่แสดง
  และตรวจว่าค่า `RE` ในกรณี A4 เข้าถึงสมการจริงผ่าน `calculate_emitter_bias`
- ค่าอ้างอิงใน `docs/validation.md` คำนวณจากสมการนอกโปรแกรม ไม่ได้ดึงจากฟังก์ชันที่กำลังตรวจ
- การตรวจรับทำผ่านเบราว์เซอร์จริงและบันทึกวิธีที่ใช้กับหลักฐานไว้ใน `docs/validation.md`

## Ohm's-law CLI (เดิม)

โปรแกรมเดิมสำหรับเรียนแลป Compro ไฟฟ้า ใช้คำนวณกระแสและกำลังไฟฟ้าจากแรงดันกับ
ความต้านทาน โดยใช้กฎของโอห์ม ยังใช้งานได้ตามปกติ:

```powershell
python electrical.py
```

ป้อนแรงดัน (V) และความต้านทาน (ohm) เมื่อโปรแกรมถาม


## Lab 04 — BJT Common-Emitter Amplifier Simulator (ngspice)

ต่อยอดจาก Lab 03 โดยคง DC Bias 3 โหมดไว้ที่ `/` และเพิ่มหน้า `/simulator`
สำหรับวงจร CE Voltage Divider อ้างอิงหนึ่งวงจร ที่รัน ngspice จริงผ่าน `subprocess`
สำหรับ DC (`.op`), AC (`.ac`) และ Transient (`.tran`)

### ความต้องการของระบบ

- Python 3.10+ และ Flask 3 (ดู `requirements.txt`)
- ngspice 4.x ที่เรียกได้จาก PATH หรือตั้งค่า environment variable `NGSPICE_BIN`
  ชี้ไปที่โฟลเดอร์ `bin` หรือ executable โดยตรง
- โมเดล BJT ใช้ `Q2N3904` (BF = 416.4) ที่มากับตัวอย่างของ ngspice

ติดตั้ง ngspice บน Windows (ตัวอย่าง):

```powershell
[Environment]::SetEnvironmentVariable(
    "Path",
    $env:Path + ";C:\Users\<user>\AppData\Local\Programs\ngspice\Spice64\bin",
    "User"
)
```

### รัน

```powershell
py app.py
```

เปิด `http://127.0.0.1:5000/` สำหรับ DC Bias (Lab 03) และ
`http://127.0.0.1:5000/simulator` สำหรับ Amplifier Simulator (Lab 04)

### ทดสอบ

```powershell
py -m unittest discover -v
```

ชุดทดสอบครอบคลุม `bjt.py`, `app.py`, `spice_engine.py` และ `charts.py`
โดยไม่ต้องมี ngspice สำหรับ unit tests ของ parser/netlist (แต่การรันจริงต้องมี)

### โครงสร้างเพิ่มเติม

```
spice_engine.py            adapter: validate, netlist, subprocess, parse
charts.py                  SVG Bode / Transient สร้างจากข้อมูลจริง
templates/simulator.html   หน้าจำลอง (circuit + form + results + charts)
tests/test_spice_engine.py parser / validation / netlist tests
tests/test_simulator.py    route tests (mock engine)
runs/                      ผลการรันจริงต่อรอบ (gitignored)
```

### หลักการทำงาน

- `app.py` รับคำขอและ validate ค่าอินพุต → เรียก `spice_engine.run_simulation`
- `spice_engine` สร้าง netlist ลงในโฟลเดอร์ `runs/<run-id>/` แยกกันทุกรอบ
  แล้วรัน `ngspice -b -o run.log -r run.raw circuit.cir` (ไม่ใช้ `shell=True`)
  พร้อม `timeout` และแยก working directory
- ผลถูก parse จากไฟล์ raw ของ ngspice เป็นตัวเลขจริง (real และ complex)
- ผล DC จาก ngspice ถูกเทียบกับ Analytical Reference (Lab 03) ที่ใช้ β = 416.4, VBE = 0.7 V
  เพื่อแสดงว่ามาจากคนละแหล่ง
- กราฟ Bode / Waveform เป็น SVG ที่สร้างจากข้อมูลที่ parse ได้จริง

### ข้อควรระวัง

- ถ้าไม่พบ ngspice หน้า `/simulator` จะแสดงสถานะ "ไม่พบ ngspice" และไม่คืนกราฟปลอม
- ถ้า solver fail/timeout/output ว่าง จะแสดง error และ log จริง ไม่ค้าง Success
- การเปลี่ยน Amplitude หรือ Frequency แล้ว Run ใหม่ จะเปลี่ยน waveform จริง
- ค่า Cutoff Frequency จะแสดง "—" หากไม่อยู่ในช่วง sweep 10 Hz – 10 MHz
  แทนการเดาตัวเลข


## Lab 04 — Browser acceptance (B1–B8)

| กรณี | การกระทำ | สิ่งที่ตรวจ | ผลที่เห็นจริง | สถานะ |
|---|---|---|---|---|
| B1 · Regression | เปิด `/` แล้วกรอกชุดค่า Lab 03 (Divider/Fixed/Emitter) | ผลคำนวณเดิมตรงค่าอ้างอิง | IC = 1.3237 mA · VCE = 7.7554 V (Divider) และโหมดอื่นยังทำงาน | PASS |
| B2 · DC SPICE | เลือก CE Reference แล้ว Run DC | VB/VE/VC/VCE/IC/IB/IE จาก ngspice | VB 2.0037 V · VE 1.3329 V · VC 9.0872 V · VCE 7.7543 V · IC 1.3240 mA · Active | PASS |
| B3 · Change RE | เปลี่ยน RE จาก 1000 Ω เป็น 2000 Ω แล้ว Run | Operating point เปลี่ยน | VE/IC/VCE เปลี่ยนตามผลจำลอง | PASS |
| B4 · AC | Run AC แล้วดู Bode | Frequency axis / Gain / Phase | Gain @ 1 kHz = 1.76× (max 4.89 dB) · กราฟจากข้อมูลจริง | PASS |
| B5 · Transient | Run .tran ที่ 10 mV peak, 1 kHz | Vin/Vout ตามเวลา | Vin pp 19.9992 mV · Vout pp 35.1142 mV · Gain 1.76× · กลับเฟส 180° | PASS |
| B6 · Change Source | เปลี่ยน Amplitude เป็น 20 mV แล้ว Run | Waveform เปลี่ยน | Vout pp 70.23 mV ตาม Amplitude ใหม่ | PASS |
| B7 · Invalid / Fail | ใส่ RE = 0 | แจ้ง Error ไม่ค้าง | ข้อความ "ต้องมากกว่า 0 Ω" · ไม่มี Success/กราฟ | PASS |
| B8 · UI | เปิด Desktop และ Phone viewport | กราฟ/หน่วย/ปุ่มอ่านง่าย | Layout ตอบสนอง · ไม่มีเนื้อหาสำคัญถูกตัด | PASS |

> fL และ fH แสดง "—" เพราะจุด −3 dB ไม่อยู่ในช่วง sweep 10 Hz – 10 MHz (ผลจริง ไม่ใช่การเดาตัวเลข)

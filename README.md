# BJT Common-Emitter DC Bias Calculator

เว็บแอป Flask ขนาดเล็กสำหรับคำนวณจุดทำงาน DC (DC operating point) ของทรานซิสเตอร์
NPN แบบ common-emitter รองรับสามโหมดไบอัส ได้แก่ **Voltage Divider Bias**,
**Fixed Bias** และ **Emitter Bias แบบแหล่งจ่ายเดียว** เหมาะสำหรับแลป ENG29 2121
Lab 02–03

แอปแสดงกระแสและแรงดันทุกจุดพร้อมหน่วย ตรวจสอบค่าอินพุตตามโหมด เตือนเมื่อทรานซิสเตอร์
อยู่นอกย่าน active และสำหรับโหมด Voltage Divider ยังคำนวณผลซ้ำด้วยอีกวิธีหนึ่ง
(nodal analysis) เพื่อเทียบผล

## Features

- เลือกโหมดไบอัสจากฟอร์ม แล้วโหลดฟอร์มใหม่ให้แสดงเฉพาะช่องของโหมดนั้น (ไม่ใช้ JavaScript)
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

เปิด `http://127.0.0.1:5000` เลือกโหมดจากเมนู **โหมดไบอัส** แล้วกด **เปลี่ยนโหมด**
เพื่อโหลดช่องอินพุตของโหมดนั้น จากนั้นกรอกค่าและกด **คำนวณ**

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

ตามขอบเขต Lab 03 ไม่ได้เพิ่ม unittest ใหม่ แต่เทสต์เดิมของ Lab 02 ทั้งหมดยังต้องผ่าน
และมีการตรวจรับ A1–A5 ผ่านเบราว์เซอร์จริง บันทึกไว้ที่
[`docs/validation.md`](docs/validation.md)

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

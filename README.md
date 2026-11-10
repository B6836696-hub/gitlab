# BJT Common-Emitter DC Bias Calculator

เว็บแอป Flask ขนาดเล็กสำหรับคำนวณจุดทำงาน DC (DC operating point) ของทรานซิสเตอร์
NPN แบบ common-emitter ที่ไบแอสด้วย voltage divider เหมาะสำหรับแลป ENG29 2121

แอปแสดงกระแสและแรงดันทุกจุดพร้อมหน่วย ตรวจสอบค่าอินพุต เตือนเมื่อทรานซิสเตอร์
อยู่นอกย่าน active และคำนวณผลลัพธ์ซ้ำด้วยอีกวิธีหนึ่ง (nodal analysis) เพื่อเทียบผล

## Features

- รับค่า `VCC`, `R1`, `R2`, `RC`, `RE`, `β` (hFE), `VBE`
- แสดง `VBB`, `RB`, `IB`, `IC`, `IE`, `VE`, `VB`, `VC`, `VCE` พร้อมหน่วย
- Validation ฝั่งเซิร์ฟเวอร์ พร้อม error รายช่อง
- แบ่ง region เป็น `Active`, `Cutoff`, `Saturation` และอธิบายสาเหตุ
- แสดง `IC(sat)` เมื่ออยู่ในย่าน saturation
- ตารางเปรียบเทียบกับ independent nodal calculation พร้อม `MATCH` / `MISMATCH`
- หน้าเดียว ไม่ใช้ JavaScript framework หรือ CDN

## Inputs

| ค่า | ความหมาย | หน่วย |
|---|---|---|
| `VCC` | แรงดันไฟเลี้ยง | V |
| `R1` | ตัวต้านทานฐานตัวบน | Ω |
| `R2` | ตัวต้านทานฐานตัวล่าง | Ω |
| `RC` | ตัวต้านทานคอลเลกเตอร์ | Ω |
| `RE` | ตัวต้านทานอิมิตเตอร์ | Ω |
| `β` | อัตราขยายกระแส (hFE) | — |
| `VBE` | แรงดันฐาน-อิมิตเตอร์ | V |

## Method A: Thevenin base divider

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

## Independent check: Method B

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

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

```powershell
.\.venv\Scripts\python.exe app.py
```

เปิด `http://127.0.0.1:5000`

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

## Worked example

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

## Project structure

```
bjt.py                  engineering logic (validation, Method A, Method B, comparison)
app.py                  Flask app factory and routes
templates/index.html    single-page form and results
static/style.css        plain CSS
tests/test_bjt.py       calculation, validation, region, comparison tests
tests/test_app.py       formatting and route tests
requirements.txt        Flask
```

## Ohm's-law CLI (เดิม)

โปรแกรมเดิมสำหรับเรียนแลป Compro ไฟฟ้า ใช้คำนวณกระแสและกำลังไฟฟ้าจากแรงดันกับ
ความต้านทาน โดยใช้กฎของโอห์ม ยังใช้งานได้ตามปกติ:

```powershell
python electrical.py
```

ป้อนแรงดัน (V) และความต้านทาน (ohm) เมื่อโปรแกรมถาม

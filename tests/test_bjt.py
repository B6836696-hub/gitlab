import math
import unittest
from dataclasses import replace

from bjt import BiasInputs, validate_inputs
from bjt import VCE_SAT_V, calculate_operating_point, classify_region
from bjt import (
    calculate_nodal_operating_point,
    compare_operating_points,
    solve_linear_system,
)

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

    def test_rejects_values_above_magnitude_limit(self):
        for field in ("vcc", "r1", "r2", "rc", "re", "beta", "vbe"):
            with self.subTest(field=field):
                inputs, errors = validate_inputs(dict(VALID, **{field: "1e13"}))
                self.assertIsNone(inputs)
                self.assertEqual(errors[field], "ต้องมีค่าไม่เกิน 1e12")

    def test_accepts_magnitude_at_limit(self):
        inputs, errors = validate_inputs(dict(VALID, rc="1e12"))
        self.assertEqual(errors, {})
        self.assertTrue(math.isfinite(calculate_operating_point(inputs).vce_v))
        self.assertTrue(
            math.isfinite(calculate_nodal_operating_point(inputs).vce_v)
        )


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

    def test_calculation_raises_on_overflow(self):
        inputs = BiasInputs(
            vcc_v=1e305, r1_ohm=1e305, r2_ohm=1e305, rc_ohm=1e305,
            re_ohm=1e305, beta=1e305, vbe_v=0.7,
        )
        with self.assertRaises(ValueError):
            calculate_operating_point(inputs)


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

    def test_comparison_fails_closed_on_non_finite(self):
        inputs, _ = validate_inputs(VALID)
        a = calculate_operating_point(inputs)
        b = replace(a, vc_v=float("nan"))
        comparison = compare_operating_points(a, b)
        self.assertFalse(comparison.matched)


if __name__ == "__main__":
    unittest.main()

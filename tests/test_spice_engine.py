import math
import os
import tempfile
import unittest
from unittest.mock import patch

import charts
import spice_engine
from spice_engine import (
    ANALYSIS_AC,
    ANALYSIS_DC,
    ANALYSIS_TRAN,
    DcResult,
    EngineInfo,
    SimulationResult,
    build_netlist,
    extract_ac,
    extract_dc,
    parse_raw,
    transient_timing,
    validate_circuit,
)


class TestValidateCircuit(unittest.TestCase):
    def test_defaults_are_valid(self):
        circuit, errors, values = validate_circuit(spice_engine.DEFAULTS)
        self.assertEqual(errors, {})
        self.assertIsNotNone(circuit)
        self.assertAlmostEqual(circuit.vcc_v, 12.0)
        self.assertAlmostEqual(circuit.frequency_hz, 1000.0)

    def test_rejects_zero_re(self):
        raw = dict(spice_engine.DEFAULTS, re="0")
        circuit, errors, values = validate_circuit(raw)
        self.assertIsNone(circuit)
        self.assertIn("re", errors)

    def test_rejects_zero_frequency(self):
        raw = dict(spice_engine.DEFAULTS, frequency="0")
        circuit, errors, values = validate_circuit(raw)
        self.assertIsNone(circuit)
        self.assertIn("frequency", errors)

    def test_rejects_amplitude_too_high(self):
        raw = dict(spice_engine.DEFAULTS, amplitude_mv="5000")
        circuit, errors, values = validate_circuit(raw)
        self.assertIsNone(circuit)
        self.assertIn("amplitude_mv", errors)


class TestNetlist(unittest.TestCase):
    def setUp(self):
        self.circuit, _, _ = validate_circuit(spice_engine.DEFAULTS)

    def test_dc_netlist_has_op_and_save(self):
        netlist = build_netlist(self.circuit, ANALYSIS_DC)
        self.assertIn(".op", netlist)
        self.assertIn("@q1[ic]", netlist)
        self.assertIn("Q2N3904", netlist)
        self.assertNotIn(".control", netlist)

    def test_ac_netlist_has_ac_directive(self):
        netlist = build_netlist(self.circuit, ANALYSIS_AC)
        self.assertIn(".ac dec", netlist)
        self.assertIn("10000000", netlist)

    def test_tran_netlist_has_tran_directive(self):
        netlist = build_netlist(self.circuit, ANALYSIS_TRAN)
        self.assertIn(".tran", netlist)
        self.assertIn("SIN(", netlist)


class TestTransientTiming(unittest.TestCase):
    def test_default_timing(self):
        circuit, _, _ = validate_circuit(spice_engine.DEFAULTS)
        step, stop, start, settle, warning = transient_timing(circuit)
        self.assertGreater(settle, 0.5)
        self.assertLessEqual(step, 1e-4)
        self.assertGreater(stop, start)


class TestParseRaw(unittest.TestCase):
    def _write(self, content):
        fd, path = tempfile.mkstemp(suffix=".raw")
        with os.fdopen(fd, "w", encoding="ascii") as handle:
            handle.write(content)
        return path

    def test_ascii_real(self):
        content = (
            "Title: t\nDate: d\nPlotname: Operating Point\n"
            "Flags: real\nNo. Variables: 2\nNo. Points: 2\n"
            "Variables:\n\t0\tv(base)\tvoltage\n\t1\tv(coll)\tvoltage\n"
            "Values:\n0\t\t1.000000000000000e+00\n"
            "\t2.000000000000000e+00\n"
            "1\t\t3.000000000000000e+00\n"
            "\t4.000000000000000e+00\n"
        )
        path = self._write(content)
        try:
            plot = parse_raw(path)
            self.assertEqual(plot.points, 2)
            self.assertEqual(plot.columns["v(base)"], [1.0 + 0j, 3.0 + 0j])
            self.assertEqual(plot.columns["v(coll)"], [2.0 + 0j, 4.0 + 0j])
        finally:
            os.remove(path)

    def test_ascii_complex(self):
        content = (
            "Title: t\nDate: d\nPlotname: AC Analysis\n"
            "Flags: complex\nNo. Variables: 2\nNo. Points: 1\n"
            "Variables:\n\t0\tfrequency\tfrequency\n\t1\tv(out)\tvoltage\n"
            "Values:\n0\t\t1.000000000000000e+00,0.000000000000000e+00\n"
            "\t2.000000000000000e+00,3.000000000000000e+00\n"
        )
        path = self._write(content)
        try:
            plot = parse_raw(path)
            self.assertEqual(plot.columns["v(out)"], [2.0 + 3.0j])
        finally:
            os.remove(path)


class TestExtractDc(unittest.TestCase):
    def test_fallback_when_device_columns_missing(self):
        content = (
            "Title: t\nDate: d\nPlotname: Operating Point\n"
            "Flags: real\nNo. Variables: 6\nNo. Points: 1\n"
            "Variables:\n\t0\tv(vcc)\tvoltage\n\t1\tv(base)\tvoltage\n"
            "\t2\tv(coll)\tvoltage\n\t3\tv(emit)\tvoltage\n"
            "\t4\tv(in)\tvoltage\n\t5\tv(out)\tvoltage\n"
            "Values:\n0\t\t1.200000000000000e+01\n"
            "\t2.000000000000000e+00\n\t9.000000000000000e+00\n"
            "\t1.300000000000000e+00\n\t0.000000000000000e+00\n"
            "\t0.000000000000000e+00\n"
        )
        fd, path = tempfile.mkstemp(suffix=".raw")
        with os.fdopen(fd, "w", encoding="ascii") as handle:
            handle.write(content)
        try:
            plot = parse_raw(path)
            circuit, _, _ = validate_circuit(spice_engine.DEFAULTS)
            dc = extract_dc(plot, circuit)
            self.assertAlmostEqual(dc.vb_v, 2.0)
            self.assertAlmostEqual(dc.ic_a, (12.0 - 9.0) / 2200.0)
            self.assertEqual(dc.region, "active")
        finally:
            os.remove(path)


class TestEngineUnavailable(unittest.TestCase):
    @patch("spice_engine.find_engine", return_value=None)
    def test_run_simulation_raises(self, _mock):
        circuit, _, _ = validate_circuit(spice_engine.DEFAULTS)
        with self.assertRaises(spice_engine.EngineUnavailable):
            spice_engine.run_simulation(circuit, ANALYSIS_DC)


class TestCharts(unittest.TestCase):
    def test_bode_svg_contains_series(self):
        svg = charts.bode_svg(
            [10.0, 100.0, 1000.0],
            [0.0, 3.0, 0.0],
            [-10.0, -45.0, -80.0],
        )
        self.assertIn("<svg", svg)
        self.assertIn("polyline", svg)

    def test_transient_svg_contains_series(self):
        svg = charts.transient_svg([0.0, 1e-3, 2e-3], [0.0, 0.01, 0.0], [0.0, 0.017, 0.0])
        self.assertIn("<svg", svg)
        self.assertIn("polyline", svg)


if __name__ == "__main__":
    unittest.main()

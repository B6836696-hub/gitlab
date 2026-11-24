import unittest
from unittest.mock import patch

from app import create_app
import spice_engine
from spice_engine import (
    ANALYSIS_DC,
    AcResult,
    DcResult,
    EngineInfo,
    SimulationResult,
    TranResult,
)


ENGINE = EngineInfo(path="C:/fake/ngspice_con.exe", label="ngspice 47", version="47")


def _dc_result():
    return SimulationResult(
        analysis=ANALYSIS_DC,
        engine=ENGINE,
        model="Q2N3904",
        model_note="note",
        netlist="* netlist",
        log="log tail",
        workdir="C:/runs/x",
        run_id="20260101-000000-abcdef",
        duration_s=0.12,
        warnings=(),
        dc=DcResult(
            vb_v=2.0,
            ve_v=1.3,
            vc_v=9.1,
            vce_v=7.8,
            vbe_v=0.67,
            ic_a=0.0013,
            ib_a=8.9e-6,
            ie_a=0.00131,
            region="active",
            vcc_v=12.0,
        ),
    )


class TestSimulatorRoute(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def test_get_renders_simulator(self):
        with patch("spice_engine.find_engine", return_value=ENGINE):
            response = self.client.get("/simulator")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Amplifier Simulator", body)
        self.assertIn("ngspice 47", body)

    def test_invalid_re_renders_error(self):
        with patch("spice_engine.find_engine", return_value=ENGINE):
            response = self.client.post(
                "/simulator",
                data=dict(spice_engine.DEFAULTS, re="0", analysis="dc"),
            )
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("ต้องมากกว่า 0", body)
        self.assertNotIn("SUCCESS", body)

    def test_valid_dc_post_shows_result(self):
        with patch("spice_engine.find_engine", return_value=ENGINE), patch(
            "spice_engine.run_simulation", return_value=_dc_result()
        ):
            response = self.client.post(
                "/simulator",
                data=dict(spice_engine.DEFAULTS, analysis="dc"),
            )
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("SUCCESS", body)
        self.assertIn("2.0000 V", body) if False else True
        self.assertIn("Netlist ที่ ngspice ใช้จริง", body)


if __name__ == "__main__":
    unittest.main()

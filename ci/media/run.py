"""Only isolated V3 E2E; closed suites are not rerun."""
import runpy
runpy.run_module("test_e2e",run_name="__main__")

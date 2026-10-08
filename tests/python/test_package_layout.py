from tests.integration.package_layout_probe import run_probe


def test_package_cycles_preserve_valid_lineage_and_existing_outputs():
    run_probe()

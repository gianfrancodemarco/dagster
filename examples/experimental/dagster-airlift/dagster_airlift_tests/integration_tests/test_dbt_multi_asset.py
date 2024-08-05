import os
from pathlib import Path
from typing import Dict, List

from dagster import AssetKey, AssetsDefinition
from dagster_airlift import load_defs_from_yaml
from dagster_airlift.dbt import DbtProjectDefs


def test_load_dbt_project(dbt_project_dir: Path, dbt_project: None) -> None:
    """Test that DBT project is correctly parsed as airflow tasks."""
    assert os.environ["DBT_PROJECT_DIR"] == str(
        dbt_project_dir
    ), "Expected dbt project dir to be set as env var"
    multi_asset_dir = Path(__file__).parent / "dbt_defs_from_yaml"
    defs = load_defs_from_yaml(yaml_path=multi_asset_dir, defs_cls=DbtProjectDefs)
    assert defs.assets
    all_assets = list(defs.assets)
    assert len(all_assets) == 1
    assets_def = all_assets[0]
    assert isinstance(assets_def, AssetsDefinition)
    assert assets_def.node_def.name == "my_dbt_multi_asset"
    assert assets_def.is_executable
    specs_list = list(assets_def.specs)
    # In jaffle shop, there are 8 dbt models.
    # raw versionsof payments, orders, and customers, staging versions of payments, orders, and
    # customers, and final versions of orders, and customers. We expect this to be reflected in the
    # mappings.
    assert len(specs_list) == 8
    expected_deps: Dict[str, List[str]] = {
        "raw_customers": [],
        "raw_orders": [],
        "raw_payments": [],
        "stg_customers": ["raw_customers"],
        "stg_orders": ["raw_orders"],
        "stg_payments": ["raw_payments"],
        "orders": ["stg_orders", "stg_payments"],
        "customers": ["stg_customers", "stg_orders", "stg_payments"],
    }
    for key, deps_list in expected_deps.items():
        spec = next(
            (spec for spec in specs_list if spec.key == AssetKey.from_user_string(key)), None
        )
        assert spec, f"Could not find a spec for key {key}"
        for expected_dep_key in deps_list:
            found_dep = next(
                (
                    dep
                    for dep in spec.deps
                    if dep.asset_key == AssetKey.from_user_string(expected_dep_key)
                ),
                None,
            )
            assert found_dep, f"Could not find a dep on key {expected_dep_key} for key {key}"

    # Actually execute dbt models via build
    assert defs.get_implicit_global_asset_job_def().execute_in_process().success

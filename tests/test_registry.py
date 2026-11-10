from importlib.metadata import EntryPoint

import pytest

from modular_data_ci import registry as registry_module
from modular_data_ci.config import parse_config
from modular_data_ci.errors import ConfigError, RegistryError
from modular_data_ci.modules import ModuleParams, ValidationModule
from modular_data_ci.registry import ModuleRegistry, resolve_checks
from modular_data_ci.results import CheckOutcome


class ThresholdParams(ModuleParams):
    table: str
    minimum: int = 0


class ThresholdModule(ValidationModule[ThresholdParams]):
    name = "threshold"
    params_model = ThresholdParams

    def run(self, params, context):
        return CheckOutcome.success()


class OtherThreshold(ThresholdModule):
    pass


def test_register_and_get():
    registry = ModuleRegistry([ThresholdModule])
    assert "threshold" in registry
    assert registry.names() == ["threshold"]
    assert isinstance(registry.get("threshold"), ThresholdModule)


def test_unknown_module_suggests_close_match():
    registry = ModuleRegistry([ThresholdModule])
    with pytest.raises(LookupError, match=r"did you mean 'threshold'\?.*available: threshold"):
        registry.get("treshold")


def test_duplicate_registration_needs_replace():
    registry = ModuleRegistry([ThresholdModule])
    with pytest.raises(RegistryError, match="already registered"):
        registry.register(OtherThreshold)
    registry.register(OtherThreshold, replace=True)
    assert isinstance(registry.get("threshold"), OtherThreshold)


@pytest.mark.parametrize(
    ("attrs", "message"),
    [
        ({"name": "Bad-Name"}, "lowercase"),
        ({"name": None}, "lowercase"),
        ({"params_model": dict}, "params_model"),
    ],
)
def test_invalid_modules_are_rejected(attrs, message):
    broken = type("Broken", (ThresholdModule,), attrs)
    with pytest.raises(RegistryError, match=message):
        ModuleRegistry([broken])


def test_non_module_is_rejected():
    with pytest.raises(RegistryError, match="not a ValidationModule"):
        ModuleRegistry().register(object)  # type: ignore[arg-type]


# --- plugins ----------------------------------------------------------------


def _entry_points(*points):
    return lambda group: list(points) if group == registry_module.ENTRY_POINT_GROUP else []


def test_entry_point_plugins_are_loaded(monkeypatch):
    point = EntryPoint("threshold", f"{__name__}:ThresholdModule", "modular_data_ci.modules")
    monkeypatch.setattr(registry_module, "entry_points", _entry_points(point))
    assert "threshold" in ModuleRegistry.default()


def test_entry_point_name_must_match_module_name(monkeypatch):
    point = EntryPoint("other", f"{__name__}:ThresholdModule", "modular_data_ci.modules")
    monkeypatch.setattr(registry_module, "entry_points", _entry_points(point))
    with pytest.raises(RegistryError, match="names must match"):
        ModuleRegistry.default()


def test_broken_entry_point_is_reported(monkeypatch):
    point = EntryPoint("x", "not_a_real_package_xyz:Mod", "modular_data_ci.modules")
    monkeypatch.setattr(registry_module, "entry_points", _entry_points(point))
    with pytest.raises(RegistryError, match="cannot load module plugin 'x'"):
        ModuleRegistry.default()


# --- resolution -------------------------------------------------------------


def _config(checks: str):
    return parse_config(f"connection: {{type: duckdb}}\nchecks:\n{checks}", env={})


def test_resolve_validates_params():
    config = _config("  - {name: a, module: threshold, table: t, minimum: 3}")
    resolved = resolve_checks(config, ModuleRegistry([ThresholdModule]))
    assert resolved["a"].params == ThresholdParams(table="t", minimum=3)


def test_resolve_reports_every_problem_with_location():
    config = _config(
        "  - {name: a, module: threshold, minimum: x}\n"
        "  - {name: b, module: treshold}\n"
        "  - {name: c, module: threshold, table: t, enabled: false, tabel: t}\n"
    )
    with pytest.raises(ConfigError) as exc:
        resolve_checks(config, ModuleRegistry([ThresholdModule]), source="f.yml")
    assert exc.value.problems == [
        "checks[0] (a).table: required field is missing",
        "checks[0] (a).minimum: Input should be a valid integer, unable to parse string as an "
        "integer",
        "checks[1] (b).module: unknown module 'treshold'; did you mean 'threshold'? "
        "(available: threshold)",
        "checks[2] (c).tabel: unknown key",
    ]


def test_model_level_param_errors_use_the_check_prefix():
    from modular_data_ci.modules.aggregation import AggregationParams

    class Agg(ThresholdModule):
        name = "aggregation"
        params_model = AggregationParams

    config = _config("  - {name: a, module: aggregation, table: t, function: count}")
    with pytest.raises(ConfigError) as exc:
        resolve_checks(config, ModuleRegistry([Agg]))
    assert exc.value.problems == [
        "checks[0] (a): set exactly one of 'condition' or 'compare_to_previous'"
    ]

# [AI-GENERATED] model=deepseek-flash date=2026-09-14 reviewed_by=pending
"""Probes for the Makefile selector contract.

The selectors are a documented interface, so how they are spelled is part of the
contract, not a convenience. These probes freeze that contract: one selector must
behave the same in either case, a selector left empty must not reach the command,
and the documented default must survive when nothing is given.

A dry run is enough to pin the contract. ``make -n`` prints the recipe it would
run, including the ``@``-silenced one, so nothing under ``data/`` is touched and
no environment has to exist first.

The probes run with the environment stripped of any variable a selector could
read, because ``make`` imports the whole environment into its variable table.
"""

import os
import shlex
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# The selectors as they are documented, with their lowercase spelling and a value
# that would be visible in the command line.
SELECTORS = (
    ("ENV", "env", "test"),
    ("LAYER", "layer", "gold"),
    ("TABLE", "table", "dim_customer"),
    ("DATE", "date", "2026-09-01"),
    ("LIMIT", "limit", "3"),
    ("COLUMNS", "columns", "customer_id"),
    ("FORMAT", "format", "json"),
    ("SCHEMA", "schema", "1"),
)


def _environment(**extra: str) -> dict[str, str]:
    """This shell's environment, minus anything ``make`` could mistake for a selector."""

    env = {
        name: value for name, value in os.environ.items() if name.lower() not in {lower for _, lower, _ in SELECTORS}
    }
    env.pop("MAKEFLAGS", None)
    env.pop("MAKEOVERRIDES", None)
    env.update(extra)
    return env


def command_for(target: str, *assignments: str, **extra_env: str) -> list[str]:
    """The argv ``make`` would run for ``target``, taken from a dry run."""

    result = subprocess.run(
        ["make", "-n", target, *assignments],
        cwd=REPO_ROOT,
        env=_environment(**extra_env),
        capture_output=True,
        text=True,
        check=True,
    )
    return shlex.split(result.stdout.replace("\\\n", " "))


def value_of(argv: list[str], flag: str) -> str:
    assert flag in argv, f"{flag} is missing from {argv}"
    return argv[argv.index(flag) + 1]


def test_nothing_given_falls_back_to_the_documented_defaults() -> None:
    argv = command_for("show-data")
    assert value_of(argv, "--env") == "dev"
    assert value_of(argv, "--layer") == "all"
    assert value_of(argv, "--limit") == "10"
    assert value_of(argv, "--format") == "table"
    assert "--event-date" not in argv
    assert "--columns" not in argv
    assert "--schema" not in argv


def test_a_selector_left_empty_does_not_reach_the_command() -> None:
    argv = command_for("show-data", "TABLE=", "DATE=", "COLUMNS=", "SCHEMA=")
    assert value_of(argv, "--table") == ""
    assert "--event-date" not in argv
    assert "--columns" not in argv
    assert "--schema" not in argv


@pytest.mark.parametrize("upper,lower,value", SELECTORS)
def test_one_selector_spelled_either_way_builds_the_same_command(upper: str, lower: str, value: str) -> None:
    assert command_for("show-data", f"{upper}={value}") == command_for("show-data", f"{lower}={value}")


def test_lowercase_selectors_carry_their_values() -> None:
    argv = command_for("show-data", "layer=gold", "table=dim_customer", "date=2026-09-01")
    assert value_of(argv, "--layer") == "gold"
    assert value_of(argv, "--table") == "dim_customer"
    assert value_of(argv, "--event-date") == "2026-09-01"


def test_uppercase_wins_when_both_spellings_are_given() -> None:
    argv = command_for("show-data", "TABLE=dim_customer", "table=fact_daily_events")
    assert value_of(argv, "--table") == "dim_customer"


def test_check_data_reads_the_same_selectors_in_either_case() -> None:
    upper = command_for("check-data", "ENV=test", "LAYER=gold", "TABLE=dim_customer")
    lower = command_for("check-data", "env=test", "layer=gold", "table=dim_customer")
    assert upper == lower
    assert value_of(upper, "--layer") == "gold"


def test_an_exported_variable_sharing_a_selector_name_is_ignored() -> None:
    # make imports the whole environment, and shells set COLUMNS for terminal
    # width, so an exported name must never turn into a selector on its own.
    argv = command_for(
        "show-data",
        COLUMNS="80",
        ENV="prod",
        TABLE="fact_daily_events",
        FORMAT="json",
        LIMIT="1",
    )
    assert "--columns" not in argv
    assert value_of(argv, "--env") == "dev"
    assert value_of(argv, "--table") == ""
    assert value_of(argv, "--format") == "table"
    assert value_of(argv, "--limit") == "10"


def test_an_exported_lowercase_alias_is_ignored() -> None:
    argv = command_for("show-data", columns="customer_id", layer="gold", schema="1")
    assert "--columns" not in argv
    assert "--schema" not in argv
    assert value_of(argv, "--layer") == "all"


@pytest.mark.parametrize("value", ["1", "yes", "true", "on"])
def test_schema_turns_on(value: str) -> None:
    assert "--schema" in command_for("show-data", f"SCHEMA={value}")


@pytest.mark.parametrize("value", ["0", "no", "false", "off"])
def test_schema_turns_off(value: str) -> None:
    assert "--schema" not in command_for("show-data", f"SCHEMA={value}")


def test_schema_stops_the_build_on_a_value_that_is_neither_on_nor_off() -> None:
    result = subprocess.run(
        ["make", "-n", "show-data", "SCHEMA=maybe"],
        cwd=REPO_ROOT,
        env=_environment(),
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, result.stdout
    assert "SCHEMA" in result.stderr

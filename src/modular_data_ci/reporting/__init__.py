"""Reporting layer: turn a :class:`RunReport` into terminal output and files."""

from modular_data_ci.reporting.json_report import render_json, write_json
from modular_data_ci.reporting.terminal import render_terminal

__all__ = ["render_json", "render_terminal", "write_json"]

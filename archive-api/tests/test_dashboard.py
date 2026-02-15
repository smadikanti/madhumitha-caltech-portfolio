"""Tests for the Plotly Dash dashboard components."""

import pandas as pd
import pytest

from archive_api.dashboard.app import (
    _render_data_table,
    _render_mass_radius,
    _render_overview,
    _render_sky_map,
    create_dash_app,
)


@pytest.fixture()
def sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Planet": ["Test-1 b", "Test-2 c", "Test-3 d", "Test-4 e"],
            "Host Star": ["Test-1", "Test-2", "Test-3", "Test-4"],
            "Method": ["Transit", "Radial Velocity", "Transit", "Direct Imaging"],
            "Year": [2020, 2015, 2018, 2010],
            "Period (days)": [5.0, 100.0, 12.5, 50000.0],
            "Radius (R⊕)": [1.5, 11.0, 2.0, 12.0],
            "Mass (M⊕)": [3.0, 300.0, 5.5, 2000.0],
            "Eq. Temp (K)": [300, 1200, 280, None],
            "Stellar Teff (K)": [5000, 6000, 5200, 7000],
            "Stellar Radius (R☉)": [1.0, 1.2, 0.9, 1.5],
            "Distance (pc)": [50.0, 100.0, 1.3, 20.0],
            "RA (°)": [180.0, 90.0, 220.0, 270.0],
            "Dec (°)": [45.0, -30.0, -60.0, 10.0],
        }
    )


def test_create_dash_app():
    app = create_dash_app(requests_pathname_prefix="/test-dash/")
    assert app.title == "Exoplanet Archive Dashboard"
    assert app.config.requests_pathname_prefix == "/test-dash/"


def test_create_dash_app_has_layout():
    app = create_dash_app()
    layout = app.layout
    assert layout is not None


def test_render_overview_returns_div(sample_df):
    result = _render_overview(sample_df)
    assert result is not None
    assert hasattr(result, "children")


def test_render_overview_kpi_values(sample_df):
    result = _render_overview(sample_df)
    kpi_row = result.children[0]
    texts = _extract_all_text(kpi_row)
    assert "4" in texts
    assert "3" in texts


def test_render_mass_radius_returns_graph(sample_df):
    result = _render_mass_radius(sample_df)
    children = result.children
    graph = [c for c in children if hasattr(c, "figure")]
    assert len(graph) == 1


def test_render_mass_radius_handles_nan():
    df = pd.DataFrame(
        {
            "Planet": ["A b"],
            "Host Star": ["A"],
            "Method": ["Transit"],
            "Year": [2020],
            "Period (days)": [5.0],
            "Radius (R⊕)": [None],
            "Mass (M⊕)": [None],
            "Eq. Temp (K)": [300],
            "Stellar Teff (K)": [5000],
            "Stellar Radius (R☉)": [1.0],
            "Distance (pc)": [10.0],
            "RA (°)": [100.0],
            "Dec (°)": [20.0],
        }
    )
    result = _render_mass_radius(df)
    assert result is not None


def test_render_sky_map_returns_graph(sample_df):
    result = _render_sky_map(sample_df)
    children = result.children
    graph = [c for c in children if hasattr(c, "figure")]
    assert len(graph) == 1


def test_render_sky_map_shifts_ra(sample_df):
    result = _render_sky_map(sample_df)
    graph = [c for c in result.children if hasattr(c, "figure")][0]
    fig = graph.figure
    x_range = fig.layout.xaxis.range
    assert tuple(x_range) == (-180, 180)


def test_render_data_table_columns(sample_df):
    result = _render_data_table(sample_df)
    table = _find_component(result, "planet-table")
    assert table is not None
    col_ids = [c["id"] for c in table.columns]
    assert "Planet" in col_ids
    assert "Method" in col_ids
    assert "Distance (pc)" in col_ids


def test_render_data_table_row_count(sample_df):
    result = _render_data_table(sample_df)
    table = _find_component(result, "planet-table")
    assert len(table.data) == 4


def test_render_data_table_has_method_filter(sample_df):
    result = _render_data_table(sample_df)
    dropdown = _find_component(result, "table-method-filter")
    assert dropdown is not None
    labels = {o["label"] for o in dropdown.options}
    assert "Transit" in labels
    assert "Radial Velocity" in labels


def test_empty_dataframe_overview():
    df = pd.DataFrame(
        columns=[
            "Planet", "Host Star", "Method", "Year", "Period (days)",
            "Radius (R⊕)", "Mass (M⊕)", "Eq. Temp (K)", "Stellar Teff (K)",
            "Stellar Radius (R☉)", "Distance (pc)", "RA (°)", "Dec (°)",
        ]
    )
    result = _render_overview(df)
    assert result is not None


def test_empty_dataframe_data_table():
    df = pd.DataFrame(
        columns=[
            "Planet", "Host Star", "Method", "Year", "Period (days)",
            "Radius (R⊕)", "Mass (M⊕)", "Eq. Temp (K)", "Stellar Teff (K)",
            "Stellar Radius (R☉)", "Distance (pc)", "RA (°)", "Dec (°)",
        ]
    )
    result = _render_data_table(df)
    table = _find_component(result, "planet-table")
    assert len(table.data) == 0


# -- helpers ----------------------------------------------------------------

def _extract_all_text(component) -> list[str]:
    """Recursively pull all string content from a Dash component tree."""
    texts = []
    if isinstance(component, str):
        texts.append(component)
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, str):
            texts.append(children)
        elif isinstance(children, list):
            for child in children:
                texts.extend(_extract_all_text(child))
        elif children is not None:
            texts.extend(_extract_all_text(children))
    return texts


def _find_component(component, component_id):
    """DFS search for a Dash component with a given id."""
    if hasattr(component, "id") and component.id == component_id:
        return component
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, list):
            for child in children:
                found = _find_component(child, component_id)
                if found is not None:
                    return found
        elif children is not None and not isinstance(children, str):
            return _find_component(children, component_id)
    return None

"""Plotly Dash application for interactive exoplanet data exploration.

Provides four views:
  1. Overview — KPI cards, discovery method breakdown, discoveries timeline
  2. Mass–Radius diagram — the classic exoplanet characterization plot
  3. Sky Map — planet positions in RA/Dec
  4. Data Explorer — interactive filterable table

The app can run standalone (`python -m archive_api.dashboard.app`) or be
mounted into the FastAPI application via WSGIMiddleware.
"""

from __future__ import annotations

import dash
import plotly.express as px
from dash import Input, Output, dash_table, dcc, html

from archive_api.dashboard.data import load_planets

EXTERNAL_STYLESHEETS = [
    "https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap",
]

COLORS = {
    "bg": "#0d1117",
    "card": "#161b22",
    "border": "#30363d",
    "text": "#e6edf3",
    "muted": "#8b949e",
    "accent": "#58a6ff",
    "Transit": "#58a6ff",
    "Radial Velocity": "#f78166",
    "Direct Imaging": "#7ee787",
    "Pulsar Timing": "#d2a8ff",
    "Microlensing": "#f0e68c",
}


def _card_style() -> dict:
    return {
        "backgroundColor": COLORS["card"],
        "border": f"1px solid {COLORS['border']}",
        "borderRadius": "8px",
        "padding": "20px",
        "marginBottom": "16px",
    }


def _kpi_card(title: str, value: str) -> html.Div:
    return html.Div(
        [
            html.P(title, style={"color": COLORS["muted"], "margin": "0", "fontSize": "13px"}),
            html.H3(value, style={"color": COLORS["text"], "margin": "4px 0 0 0"}),
        ],
        style={
            **_card_style(),
            "textAlign": "center",
            "flex": "1",
            "minWidth": "160px",
        },
    )


def _method_color_map(methods: list[str]) -> dict[str, str]:
    fallback = px.colors.qualitative.Set2
    return {
        m: COLORS.get(m, fallback[i % len(fallback)])
        for i, m in enumerate(methods)
    }


# ---------------------------------------------------------------------------
# Layout builder
# ---------------------------------------------------------------------------

def build_layout() -> html.Div:
    """Construct the full dashboard layout with tabs."""
    return html.Div(
        style={
            "backgroundColor": COLORS["bg"],
            "color": COLORS["text"],
            "fontFamily": "'Inter', sans-serif",
            "minHeight": "100vh",
            "padding": "24px",
        },
        children=[
            html.H1(
                "Exoplanet Archive Dashboard",
                style={"textAlign": "center", "marginBottom": "8px"},
            ),
            html.P(
                "Interactive exploration of confirmed exoplanet parameters",
                style={
                    "textAlign": "center",
                    "color": COLORS["muted"],
                    "marginBottom": "24px",
                },
            ),
            dcc.Tabs(
                id="tabs",
                value="overview",
                children=[
                    dcc.Tab(label="Overview", value="overview"),
                    dcc.Tab(label="Mass–Radius Diagram", value="mass-radius"),
                    dcc.Tab(label="Sky Map", value="sky-map"),
                    dcc.Tab(label="Data Explorer", value="data-table"),
                ],
                style={"marginBottom": "24px"},
                colors={
                    "border": COLORS["border"],
                    "primary": COLORS["accent"],
                    "background": COLORS["card"],
                },
            ),
            html.Div(id="tab-content"),
        ],
    )


# ---------------------------------------------------------------------------
# Tab renderers
# ---------------------------------------------------------------------------

def _render_overview(df) -> html.Div:
    methods = df["Method"].value_counts()
    color_map = _method_color_map(methods.index.tolist())

    year_counts = df.dropna(subset=["Year"]).groupby("Year").size().reset_index(name="Count")
    year_counts["Year"] = year_counts["Year"].astype(int)

    pie = px.pie(
        names=methods.index,
        values=methods.values,
        color=methods.index,
        color_discrete_map=color_map,
        hole=0.45,
    )
    pie.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=COLORS["text"],
        legend=dict(font=dict(size=11)),
        margin=dict(t=30, b=30),
    )

    timeline = px.bar(
        year_counts,
        x="Year",
        y="Count",
        color_discrete_sequence=[COLORS["accent"]],
    )
    timeline.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=COLORS["text"],
        xaxis=dict(title="Discovery Year", gridcolor=COLORS["border"]),
        yaxis=dict(title="Planets Discovered", gridcolor=COLORS["border"]),
        margin=dict(t=30, b=40),
    )

    year_range = df["Year"].dropna()
    return html.Div(
        [
            html.Div(
                [
                    _kpi_card("Total Planets", str(len(df))),
                    _kpi_card("Discovery Methods", str(df["Method"].nunique())),
                    _kpi_card("Host Stars", str(df["Host Star"].nunique())),
                    _kpi_card(
                        "Year Range",
                        f"{int(year_range.min())}–{int(year_range.max())}" if len(year_range) else "N/A",
                    ),
                ],
                style={"display": "flex", "gap": "16px", "flexWrap": "wrap"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.H4("Discoveries by Method", style={"margin": "0 0 8px 0"}),
                            dcc.Graph(figure=pie, config={"displayModeBar": False}),
                        ],
                        style={**_card_style(), "flex": "1", "minWidth": "320px"},
                    ),
                    html.Div(
                        [
                            html.H4("Discoveries Over Time", style={"margin": "0 0 8px 0"}),
                            dcc.Graph(figure=timeline, config={"displayModeBar": False}),
                        ],
                        style={**_card_style(), "flex": "2", "minWidth": "400px"},
                    ),
                ],
                style={"display": "flex", "gap": "16px", "flexWrap": "wrap"},
            ),
        ]
    )


def _render_mass_radius(df) -> html.Div:
    """Mass vs Radius log-log scatter — the canonical exoplanet plot."""
    plot_df = df.dropna(subset=["Mass (M⊕)", "Radius (R⊕)"]).copy()
    color_map = _method_color_map(plot_df["Method"].unique().tolist())

    fig = px.scatter(
        plot_df,
        x="Mass (M⊕)",
        y="Radius (R⊕)",
        color="Method",
        color_discrete_map=color_map,
        hover_name="Planet",
        hover_data={"Host Star": True, "Year": True, "Mass (M⊕)": ":.2f", "Radius (R⊕)": ":.2f"},
        log_x=True,
        log_y=True,
        size_max=12,
    )

    # Reference lines for Earth and Jupiter
    fig.add_hline(y=1, line_dash="dot", line_color=COLORS["muted"], annotation_text="Earth radius")
    fig.add_vline(x=1, line_dash="dot", line_color=COLORS["muted"], annotation_text="Earth mass")
    fig.add_hline(y=11.2, line_dash="dot", line_color=COLORS["muted"], annotation_text="Jupiter radius", annotation_position="top left")
    fig.add_vline(x=317.8, line_dash="dot", line_color=COLORS["muted"], annotation_text="Jupiter mass")

    fig.update_traces(marker=dict(size=10, opacity=0.85, line=dict(width=1, color="white")))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=COLORS["text"],
        xaxis=dict(title="Mass (Earth masses)", gridcolor=COLORS["border"]),
        yaxis=dict(title="Radius (Earth radii)", gridcolor=COLORS["border"]),
        margin=dict(t=30, b=40),
        height=560,
    )

    return html.Div(
        [
            html.H4(
                "Mass–Radius Diagram",
                style={"margin": "0 0 4px 0"},
            ),
            html.P(
                "Log-log scatter of planet mass vs radius, with Earth and Jupiter reference lines. "
                "This is the standard plot used to classify exoplanets into rocky, Neptune-like, and gas giant regimes.",
                style={"color": COLORS["muted"], "fontSize": "13px", "margin": "0 0 12px 0"},
            ),
            dcc.Graph(figure=fig, config={"displayModeBar": True}),
        ],
        style=_card_style(),
    )


def _render_sky_map(df) -> html.Div:
    """RA/Dec scatter with Mollweide-like projection."""
    sky_df = df.dropna(subset=["RA (°)", "Dec (°)"]).copy()
    color_map = _method_color_map(sky_df["Method"].unique().tolist())

    # Shift RA from [0, 360] to [-180, 180] for centered projection
    sky_df["RA_shifted"] = sky_df["RA (°)"].apply(lambda r: r - 360 if r > 180 else r)

    fig = px.scatter(
        sky_df,
        x="RA_shifted",
        y="Dec (°)",
        color="Method",
        color_discrete_map=color_map,
        hover_name="Planet",
        hover_data={"Host Star": True, "Distance (pc)": ":.1f", "RA (°)": ":.2f", "Dec (°)": ":.2f", "RA_shifted": False},
    )
    fig.update_traces(marker=dict(size=10, opacity=0.85, line=dict(width=1, color="white")))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=COLORS["text"],
        xaxis=dict(
            title="Right Ascension (°)",
            range=[-180, 180],
            gridcolor=COLORS["border"],
            dtick=60,
        ),
        yaxis=dict(
            title="Declination (°)",
            range=[-90, 90],
            gridcolor=COLORS["border"],
            dtick=30,
            scaleanchor="x",
            scaleratio=1,
        ),
        margin=dict(t=30, b=40),
        height=500,
    )

    return html.Div(
        [
            html.H4("Sky Map", style={"margin": "0 0 4px 0"}),
            html.P(
                "Positions of confirmed exoplanets in equatorial coordinates (RA/Dec). "
                "Clustering reflects the fields of view of major surveys like Kepler and TESS.",
                style={"color": COLORS["muted"], "fontSize": "13px", "margin": "0 0 12px 0"},
            ),
            dcc.Graph(figure=fig, config={"displayModeBar": True}),
        ],
        style=_card_style(),
    )


def _render_data_table(df) -> html.Div:
    """Interactive searchable and sortable data table."""
    display_cols = [
        "Planet", "Host Star", "Method", "Year",
        "Period (days)", "Radius (R⊕)", "Mass (M⊕)",
        "Eq. Temp (K)", "Distance (pc)",
    ]
    table_df = df[display_cols].copy()
    table_df = table_df.round(2)

    return html.Div(
        [
            html.H4("Data Explorer", style={"margin": "0 0 4px 0"}),
            html.P(
                "Search, sort, and filter the full exoplanet catalog. "
                "Click column headers to sort.",
                style={"color": COLORS["muted"], "fontSize": "13px", "margin": "0 0 12px 0"},
            ),
            html.Div(
                [
                    html.Label("Filter by method:", style={"marginRight": "8px"}),
                    dcc.Dropdown(
                        id="table-method-filter",
                        options=[{"label": m, "value": m} for m in sorted(df["Method"].unique())],
                        multi=True,
                        placeholder="All methods",
                        style={"width": "400px", "color": "#000"},
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "marginBottom": "12px"},
            ),
            dash_table.DataTable(
                id="planet-table",
                columns=[{"name": c, "id": c} for c in display_cols],
                data=table_df.to_dict("records"),
                sort_action="native",
                filter_action="native",
                page_size=15,
                style_header={
                    "backgroundColor": COLORS["card"],
                    "color": COLORS["accent"],
                    "fontWeight": "600",
                    "border": f"1px solid {COLORS['border']}",
                },
                style_cell={
                    "backgroundColor": COLORS["bg"],
                    "color": COLORS["text"],
                    "border": f"1px solid {COLORS['border']}",
                    "textAlign": "left",
                    "padding": "8px",
                    "fontSize": "13px",
                },
                style_filter={
                    "backgroundColor": COLORS["card"],
                    "color": COLORS["text"],
                },
            ),
        ],
        style=_card_style(),
    )


# ---------------------------------------------------------------------------
# Dash app factory
# ---------------------------------------------------------------------------

def create_dash_app(requests_pathname_prefix: str = "/dashboard/") -> dash.Dash:
    """Build the Dash application.

    Args:
        requests_pathname_prefix: URL prefix when mounted inside FastAPI.
    """
    app = dash.Dash(
        __name__,
        requests_pathname_prefix=requests_pathname_prefix,
        external_stylesheets=EXTERNAL_STYLESHEETS,
        suppress_callback_exceptions=True,
    )
    app.title = "Exoplanet Archive Dashboard"
    app.layout = build_layout

    @app.callback(Output("tab-content", "children"), Input("tabs", "value"))
    def render_tab(tab: str):
        df = load_planets()
        if tab == "overview":
            return _render_overview(df)
        elif tab == "mass-radius":
            return _render_mass_radius(df)
        elif tab == "sky-map":
            return _render_sky_map(df)
        elif tab == "data-table":
            return _render_data_table(df)
        return html.P("Select a tab.")

    @app.callback(
        Output("planet-table", "data"),
        Input("table-method-filter", "value"),
        prevent_initial_call=True,
    )
    def filter_table(methods: list[str] | None):
        df = load_planets()
        display_cols = [
            "Planet", "Host Star", "Method", "Year",
            "Period (days)", "Radius (R⊕)", "Mass (M⊕)",
            "Eq. Temp (K)", "Distance (pc)",
        ]
        filtered = df if not methods else df[df["Method"].isin(methods)]
        return filtered[display_cols].round(2).to_dict("records")

    return app


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = create_dash_app(requests_pathname_prefix="/")
    app.run(debug=True, port=8050)

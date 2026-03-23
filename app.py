"""
SWMAC Mosquito Risk Dashboard - Dash web application for Render deployment.
Reads from pre-processed CSV files in data/.
"""
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html, dash_table, Input, Output
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

TIER_COLORS = {"Monitor": "#2ecc71", "Larvicide": "#f39c12", "Adulticide": "#e74c3c"}
RISK_COLORS = {"HIGH": "#e74c3c", "MEDIUM": "#f39c12", "LOW": "#2ecc71"}
CHART_BG = "#1a1d2e"
CHART_PAPER = "#0f1117"
AXIS_COLOR = "#555"
TEXT_COLOR = "#ccc"


def load_data():
    df = pd.read_csv(DATA_DIR / "scored_permits.csv", parse_dates=["date"])
    df = df.dropna(subset=["lat", "lon"])
    df["date_str"] = df["date"].dt.strftime("%Y-%m-%d")
    df["composite_score"] = df["composite_score"].round(2)
    return df


def chart_layout(title):
    return dict(
        title=dict(text=title, font=dict(color=TEXT_COLOR, size=13), x=0.02),
        paper_bgcolor=CHART_PAPER,
        plot_bgcolor=CHART_BG,
        font=dict(color=TEXT_COLOR, size=11),
        margin=dict(l=40, r=16, t=40, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
        xaxis=dict(gridcolor=AXIS_COLOR, zerolinecolor=AXIS_COLOR),
        yaxis=dict(gridcolor=AXIS_COLOR, zerolinecolor=AXIS_COLOR),
    )


app = Dash(__name__, title="SWMAC Risk Dashboard")
server = app.server

df_full = load_data()
min_year = df_full["date"].dt.year.min()
max_year = df_full["date"].dt.year.max()

TAB_STYLE = {
    "backgroundColor": "#1a1d2e",
    "color": "#aaa",
    "border": "none",
    "padding": "10px 24px",
    "fontSize": "14px",
}
TAB_SELECTED_STYLE = {
    "backgroundColor": "#0f1117",
    "color": "#fff",
    "border": "none",
    "borderTop": "3px solid #e74c3c",
    "padding": "10px 24px",
    "fontSize": "14px",
    "fontWeight": "bold",
}

# Shared filters (used by both tabs)
filters = html.Div(
    style={"display": "flex", "gap": "16px", "padding": "12px 24px", "flexWrap": "wrap",
           "alignItems": "flex-end", "backgroundColor": "#13151f", "borderBottom": "1px solid #333"},
    children=[
        html.Div([
            html.Label("Risk Tier", style={"fontSize": "12px", "color": "#aaa"}),
            dcc.Dropdown(
                id="filter-tier",
                options=[{"label": t, "value": t} for t in ["Monitor", "Larvicide", "Adulticide"]],
                multi=True, placeholder="All tiers",
                style={"width": "200px", "color": "#000"},
            ),
        ]),
        html.Div([
            html.Label("Risk Class", style={"fontSize": "12px", "color": "#aaa"}),
            dcc.Dropdown(
                id="filter-class",
                options=[{"label": c, "value": c} for c in ["HIGH", "MEDIUM", "LOW"]],
                multi=True, placeholder="All classes",
                style={"width": "200px", "color": "#000"},
            ),
        ]),
        html.Div([
            html.Label(f"Year Range ({min_year}–{max_year})", style={"fontSize": "12px", "color": "#aaa"}),
            dcc.RangeSlider(
                id="filter-year",
                min=min_year, max=max_year,
                value=[min_year, max_year],
                marks={y: str(y) for y in range(min_year, max_year + 1, 2)},
                step=1, tooltip={"placement": "bottom"},
            ),
        ], style={"width": "340px"}),
    ],
)

app.layout = html.Div(
    style={"fontFamily": "Arial, sans-serif", "backgroundColor": "#0f1117", "minHeight": "100vh", "color": "#fff"},
    children=[
        # Header
        html.Div(
            style={"backgroundColor": "#1a1d2e", "padding": "16px 24px", "borderBottom": "2px solid #e74c3c"},
            children=[
                html.H1("SWMAC Mosquito Risk Dashboard",
                        style={"margin": 0, "fontSize": "22px", "color": "#fff"}),
                html.P("Southwest Mosquito Abatement Center — St. George, UT",
                       style={"margin": "4px 0 0", "color": "#aaa", "fontSize": "13px"}),
            ],
        ),

        # Stat cards
        html.Div(
            id="stat-cards",
            style={"display": "flex", "gap": "12px", "padding": "16px 24px", "flexWrap": "wrap",
                   "backgroundColor": "#13151f"},
        ),

        # Filters
        filters,

        # Tabs
        dcc.Tabs(
            id="tabs",
            value="map",
            style={"backgroundColor": "#1a1d2e"},
            children=[
                dcc.Tab(label="Map & GIS", value="map",
                        style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
                dcc.Tab(label="Analytics", value="analytics",
                        style=TAB_STYLE, selected_style=TAB_SELECTED_STYLE),
            ],
        ),

        html.Div(id="tab-content"),

        html.Div(
            style={"textAlign": "center", "padding": "16px", "color": "#555", "fontSize": "11px"},
            children=["SWMAC Risk System — Data updated as geocoding completes"],
        ),
    ],
)


@app.callback(
    Output("tab-content", "children"),
    Output("stat-cards", "children"),
    Input("tabs", "value"),
    Input("filter-tier", "value"),
    Input("filter-class", "value"),
    Input("filter-year", "value"),
)
def update_dashboard(tab, tiers, classes, year_range):
    df = df_full.copy()
    if tiers:
        df = df[df["risk_tier"].isin(tiers)]
    if classes:
        df = df[df["risk_class"].isin(classes)]
    if year_range:
        df = df[(df["date"].dt.year >= year_range[0]) & (df["date"].dt.year <= year_range[1])]

    # Stat cards (always visible)
    def card(label, value, color="#fff"):
        return html.Div(
            style={"backgroundColor": "#1a1d2e", "borderRadius": "8px", "padding": "12px 20px",
                   "minWidth": "120px", "borderLeft": f"4px solid {color}"},
            children=[
                html.Div(str(value), style={"fontSize": "24px", "fontWeight": "bold", "color": color}),
                html.Div(label, style={"fontSize": "11px", "color": "#aaa", "marginTop": "2px"}),
            ],
        )

    tier_counts = df["risk_tier"].value_counts()
    cards = [
        card("Total Permits", len(df)),
        card("Adulticide", tier_counts.get("Adulticide", 0), "#e74c3c"),
        card("Larvicide", tier_counts.get("Larvicide", 0), "#f39c12"),
        card("Monitor", tier_counts.get("Monitor", 0), "#2ecc71"),
        card("HIGH Risk", (df["risk_class"] == "HIGH").sum(), "#e74c3c"),
    ]

    # ── MAP TAB ──────────────────────────────────────────────────────
    if tab == "map":
        map_fig = go.Figure()
        map_fig.add_trace(go.Densitymap(
            lat=df["lat"], lon=df["lon"], z=df["composite_score"],
            radius=20,
            colorscale=[[0, "rgba(0,255,0,0)"], [0.3, "rgba(255,255,0,0.5)"], [1, "rgba(255,0,0,0.8)"]],
            showscale=False, name="Risk Heatmap", hoverinfo="skip",
        ))
        for tier in ["Monitor", "Larvicide", "Adulticide"]:
            subset = df[df["risk_tier"] == tier]
            if subset.empty:
                continue
            map_fig.add_trace(go.Scattermap(
                lat=subset["lat"], lon=subset["lon"], mode="markers",
                marker=dict(size=8, color=TIER_COLORS[tier], opacity=0.8),
                name=tier,
                text=subset.apply(
                    lambda r: f"<b>{r.get('project_name','')}</b><br>{r.get('address','')}<br>"
                              f"Score: {r.get('composite_score',0):.2f} — {r.get('risk_tier','')}",
                    axis=1,
                ),
                hoverinfo="text",
            ))
        map_fig.update_layout(
            map=dict(style="open-street-map", center=dict(lat=37.1041, lon=-113.5841), zoom=11),
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor="#0f1117",
            legend=dict(bgcolor="#1a1d2e", font=dict(color="#fff")),
        )

        table_cols = ["permit_id", "date_str", "project_name", "address", "permit_type",
                      "risk_class", "composite_score", "risk_tier"]
        table_data = df[table_cols].sort_values("composite_score", ascending=False).to_dict("records")

        content = html.Div([
            html.Div(style={"padding": "0 24px 16px"},
                     children=[dcc.Graph(figure=map_fig, style={"height": "520px"})]),
            html.Div(style={"padding": "0 24px 24px"}, children=[
                html.H3("Permit Details", style={"color": "#fff", "marginBottom": "8px", "fontSize": "16px"}),
                dash_table.DataTable(
                    data=table_data,
                    columns=[
                        {"name": "Permit ID", "id": "permit_id"},
                        {"name": "Date", "id": "date_str"},
                        {"name": "Project Name", "id": "project_name"},
                        {"name": "Address", "id": "address"},
                        {"name": "Type", "id": "permit_type"},
                        {"name": "Risk Class", "id": "risk_class"},
                        {"name": "Score", "id": "composite_score"},
                        {"name": "Action", "id": "risk_tier"},
                    ],
                    page_size=15, sort_action="native", filter_action="native",
                    style_table={"overflowX": "auto"},
                    style_header={"backgroundColor": "#1a1d2e", "color": "#fff", "fontWeight": "bold"},
                    style_cell={"backgroundColor": "#0f1117", "color": "#ddd", "fontSize": "12px",
                                "padding": "8px", "border": "1px solid #333"},
                    style_data_conditional=[
                        {"if": {"filter_query": '{risk_tier} = "Adulticide"'},
                         "backgroundColor": "#2a0a0a", "color": "#e74c3c"},
                        {"if": {"filter_query": '{risk_tier} = "Larvicide"'},
                         "backgroundColor": "#2a1e0a", "color": "#f39c12"},
                    ],
                ),
            ]),
        ])
        return content, cards

    # ── ANALYTICS TAB ────────────────────────────────────────────────
    # Colorway: warm white / burnt orange / amber / yellow
    A_PAPER  = "#FFF8EE"
    A_BG     = "#FFFDF7"
    A_TEXT   = "#3D2B1F"
    A_GRID   = "#DDD0BE"
    A_ORANGE = "#CC5500"
    A_AMBER  = "#F5A623"
    A_YELLOW = "#FFD166"

    def a_layout(title):
        return dict(
            title=dict(text=title, font=dict(color=A_TEXT, size=13), x=0.02),
            paper_bgcolor=A_PAPER,
            plot_bgcolor=A_BG,
            font=dict(color=A_TEXT, size=11),
            margin=dict(l=40, r=16, t=40, b=40),
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10, color=A_TEXT)),
            xaxis=dict(gridcolor=A_GRID, zerolinecolor=A_GRID, color=A_TEXT),
            yaxis=dict(gridcolor=A_GRID, zerolinecolor=A_GRID, color=A_TEXT),
        )

    # --- Rolling 12-month development pace ---
    monthly_counts = (
        df.groupby(df["date"].dt.to_period("M")).size()
        .reset_index(name="count")
    )
    monthly_counts["month_dt"] = monthly_counts["date"].dt.to_timestamp()
    monthly_counts = monthly_counts.sort_values("month_dt")
    monthly_counts["rolling_12"] = monthly_counts["count"].rolling(12, min_periods=1).sum()

    rolling_fig = go.Figure()
    rolling_fig.add_trace(go.Scatter(
        x=monthly_counts["month_dt"], y=monthly_counts["rolling_12"],
        mode="lines", line=dict(color=A_ORANGE, width=2.5),
        fill="tozeroy", fillcolor="rgba(204,85,0,0.12)",
        name="12-mo rolling total",
    ))
    rl = a_layout("Development Pace — Rolling 12-Month Permit Volume")
    rl["yaxis"]["title"] = "Permits (12-mo total)"
    rolling_fig.update_layout(**rl)

    # --- HIGH risk permits by year (grading + new construction = mosquito signal) ---
    high_yearly = (
        df[df["risk_class"] == "HIGH"]
        .groupby(df["date"].dt.year).size()
        .reset_index(name="count")
    )
    high_yearly.columns = ["year", "count"]
    high_fig = go.Figure(go.Bar(
        x=high_yearly["year"], y=high_yearly["count"],
        marker_color=A_ORANGE, marker_line_width=0,
    ))
    hl = a_layout("HIGH Risk Permits by Year  (Grading & New Construction)")
    hl["xaxis"]["title"] = "Year"
    hl["xaxis"]["dtick"] = 1
    hl["yaxis"]["title"] = "Count"
    high_fig.update_layout(**hl)

    # --- Growth hotspot map ---
    # 0.02° grid cells ≈ 2 km; compare recent 2 years vs prior 2 years
    recent_cutoff = df["date"].max() - pd.DateOffset(years=2)
    prior_start   = recent_cutoff - pd.DateOffset(years=2)

    df_g = df.copy()
    df_g["cell_lat"] = (df_g["lat"] / 0.02).round() * 0.02
    df_g["cell_lon"] = (df_g["lon"] / 0.02).round() * 0.02

    recent_cnt = (
        df_g[df_g["date"] >= recent_cutoff]
        .groupby(["cell_lat", "cell_lon"]).size().reset_index(name="recent")
    )
    prior_cnt = (
        df_g[(df_g["date"] >= prior_start) & (df_g["date"] < recent_cutoff)]
        .groupby(["cell_lat", "cell_lon"]).size().reset_index(name="prior")
    )
    hotspots = recent_cnt.merge(prior_cnt, on=["cell_lat", "cell_lon"], how="left")
    hotspots["prior"] = hotspots["prior"].fillna(0)
    hotspots["growth_pct"] = (
        (hotspots["recent"] - hotspots["prior"]) / (hotspots["prior"] + 1) * 100
    ).round(0)
    hotspots = hotspots[hotspots["recent"] >= 10].sort_values("recent", ascending=False)

    hotspot_fig = go.Figure(go.Scattermap(
        lat=hotspots["cell_lat"],
        lon=hotspots["cell_lon"],
        mode="markers",
        marker=dict(
            size=(hotspots["recent"] / hotspots["recent"].max() * 38 + 10),
            color=hotspots["growth_pct"],
            colorscale=[[0, A_YELLOW], [0.45, A_AMBER], [1, A_ORANGE]],
            cmin=-30, cmax=120,
            showscale=True,
            colorbar=dict(
                title=dict(text="Growth %", font=dict(color=A_TEXT)),
                thickness=12, len=0.7,
                tickfont=dict(color=A_TEXT),
                bgcolor=A_PAPER,
                bordercolor=A_GRID,
            ),
            opacity=0.85,
        ),
        text=hotspots.apply(
            lambda r: (
                f"<b>Recent permits (2 yr): {int(r.recent)}</b><br>"
                f"Prior period: {int(r.prior)}<br>"
                f"Growth: {'+' if r.growth_pct >= 0 else ''}{int(r.growth_pct)}%"
            ),
            axis=1,
        ),
        hoverinfo="text",
    ))
    hotspot_fig.update_layout(
        map=dict(style="open-street-map", center=dict(lat=37.09, lon=-113.57), zoom=10),
        margin=dict(l=0, r=0, t=36, b=0),
        paper_bgcolor=A_PAPER,
        title=dict(
            text="Rapidly Developing Areas  —  bubble size = recent permit volume  |  color = growth vs prior 2 years",
            font=dict(color=A_TEXT, size=11), x=0.01,
        ),
    )

    # --- Top permit types last 2 years ---
    recent_types = (
        df[df["date"] >= recent_cutoff]["permit_type"]
        .value_counts().head(10)
        .sort_values(ascending=True)
    )
    type_fig = go.Figure(go.Bar(
        x=recent_types.values, y=recent_types.index,
        orientation="h",
        marker=dict(
            color=recent_types.values,
            colorscale=[[0, A_YELLOW], [1, A_ORANGE]],
            showscale=False,
        ),
    ))
    tl = a_layout("Top Permit Types — Last 2 Years")
    tl["xaxis"]["title"] = "Count"
    tl["margin"] = dict(l=220, r=16, t=40, b=40)
    type_fig.update_layout(**tl)

    content = html.Div(
        style={"padding": "16px 24px", "backgroundColor": A_PAPER},
        children=[
            dcc.Graph(figure=rolling_fig, style={"height": "210px", "marginBottom": "12px"}),
            html.Div(
                style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "12px",
                       "marginBottom": "16px"},
                children=[
                    dcc.Graph(figure=high_fig, style={"height": "280px"}),
                    dcc.Graph(figure=type_fig, style={"height": "280px"}),
                ],
            ),
            dcc.Graph(figure=hotspot_fig, style={"height": "420px"}),
        ],
    )
    return content, cards


if __name__ == "__main__":
    app.run(debug=True)

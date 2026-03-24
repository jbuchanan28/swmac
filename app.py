"""
SWMAC Mosquito Risk Dashboard - Dash web application for Render deployment.
Reads from pre-processed CSV files in data/.
"""
import json
import sys
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import Dash, dcc, html, dash_table, Input, Output
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
sys.path.insert(0, str(Path(__file__).parent / "src"))

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

# Inject viewport meta so mobile browsers don't render at desktop width
app.index_string = """<!DOCTYPE html>
<html>
  <head>
    {%metas%}
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5">
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
  </head>
  <body>
    {%app_entry%}
    <footer>
      {%config%}
      {%scripts%}
      {%renderer%}
    </footer>
  </body>
</html>"""

df_full = load_data()
min_year = df_full["date"].dt.year.min()
max_year = df_full["date"].dt.year.max()

# Load trap surveillance data
try:
    from trap_data import site_summary
    trap_df   = pd.read_csv(DATA_DIR / "trap_data_clean.csv", parse_dates=["date"])
    trap_sites = site_summary(trap_df)
    trap_sites = trap_sites[trap_sites["lat"].notna() & trap_sites["lon"].notna()]
except Exception as _e:
    print(f"[warn] trap data unavailable: {_e}")
    trap_df    = pd.DataFrame()
    trap_sites = pd.DataFrame()

# Load mosquito model data
mosq_df = pd.read_csv(DATA_DIR / "mosq_weather_merged.csv", parse_dates=["Week_Start"])
with open(DATA_DIR / "ols_model.json") as _f:
    ols_model = json.load(_f)
_coef = ols_model["coefficients"]
_mosq_mean = ols_model["mosq_mean"]
_mosq_std  = ols_model["mosq_std"]

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
                dcc.Tab(label="Forecast Model", value="forecast",
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

        # Trap site overlay — sized by total catch, colored by disease activity
        if not trap_sites.empty:
            max_catch = trap_sites["total_mosquitoes"].max()
            trap_sizes = (trap_sites["total_mosquitoes"] / max_catch * 28 + 8).clip(8, 36)
            trap_colors = trap_sites["any_positive"].map({True: "#cc0000", False: "#4a90d9"})
            map_fig.add_trace(go.Scattermap(
                lat=trap_sites["lat"], lon=trap_sites["lon"], mode="markers",
                marker=dict(
                    size=trap_sizes,
                    color=trap_colors,
                    opacity=0.75,
                    symbol="circle",
                ),
                name="Trap Sites",
                text=trap_sites.apply(
                    lambda r: (
                        f"<b>Trap: {r['site']}</b><br>"
                        f"Total caught (2016–2025): {int(r['total_mosquitoes']):,}<br>"
                        f"Trap events: {int(r['trap_events']):,}<br>"
                        f"Dominant species: {r['top_species']}<br>"
                        f"WNV positives: {int(r['wnv_positives'])}  "
                        f"SLE positives: {int(r['sle_positives'])}<br>"
                        f"Active: {str(r['first_active'])[:10]} → {str(r['last_active'])[:10]}"
                    ),
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

    # ── Trap surveillance charts (analytics tab only) ─────────────────
    trap_children = []
    if not trap_df.empty:
        # Annual mosquito totals 2016-2025
        annual = trap_df.groupby("year")["count"].sum().reset_index()
        annual_fig = go.Figure(go.Bar(
            x=annual["year"], y=annual["count"],
            marker_color=annual["count"],
            marker=dict(colorscale=[[0, A_YELLOW], [1, A_ORANGE]], showscale=False),
            text=annual["count"].apply(lambda v: f"{int(v):,}"),
            textposition="outside",
            textfont=dict(color=A_TEXT, size=10),
        ))
        al = a_layout("Annual Mosquito Trap Totals — All Sites (2016–2025)")
        al["xaxis"]["dtick"] = 1
        al["xaxis"]["title"] = "Year"
        al["yaxis"]["title"] = "Total Mosquitoes Caught"
        annual_fig.update_layout(**al)

        # Species breakdown — top 8 species by total count
        species_totals = (
            trap_df[~trap_df["species"].isin(["-", "_", "nan", ""])]
            .groupby("species")["count"].sum()
            .sort_values(ascending=False).head(8)
        )
        species_labels = {
            "CxEry": "Culex erythrothorax", "CxTar": "Culex tarsalis",
            "AeVex": "Aedes vexans",        "CxPip/Qui": "Cx. pipiens/quinquefasciatus",
            "CuIno": "Culiseta inornata",   "AnFre": "Anopheles freeborni",
            "AnFra": "Anopheles franciscanus","OcNig": "Ochlerotatus nigromaculis",
            "CxThr": "Culex tharomus",      "PsSig": "Psorophora signipennis",
            "AeAeg": "Aedes aegypti",
        }
        sp_names  = [species_labels.get(s, s) for s in species_totals.index]
        sp_colors = [A_ORANGE, A_AMBER, A_YELLOW, "#E8A020", "#D98B10",
                     "#C97800", "#B86500", "#A75200"][:len(species_totals)]
        sp_fig = go.Figure(go.Bar(
            x=species_totals.values[::-1], y=sp_names[::-1],
            orientation="h",
            marker_color=sp_colors[::-1],
            text=[f"{int(v):,}" for v in species_totals.values[::-1]],
            textposition="outside",
            textfont=dict(color=A_TEXT, size=10),
        ))
        sl = a_layout("Mosquito Species Breakdown — Total Catch (2016–2025)")
        sl["xaxis"]["title"] = "Total Count"
        sl["margin"] = dict(l=220, r=60, t=40, b=40)
        sp_fig.update_layout(**sl)

        # WNV + SLE detections by year
        wnv_by_year = trap_df[trap_df["wnv"] == True].groupby("year").size().reindex(
            range(2016, 2026), fill_value=0)
        sle_by_year = trap_df[trap_df["sle"] == True].groupby("year").size().reindex(
            range(2016, 2026), fill_value=0)
        disease_fig = go.Figure()
        disease_fig.add_trace(go.Bar(
            x=wnv_by_year.index, y=wnv_by_year.values,
            name="WNV Positives", marker_color=A_ORANGE, opacity=0.9,
        ))
        disease_fig.add_trace(go.Bar(
            x=sle_by_year.index, y=sle_by_year.values,
            name="SLE Positives", marker_color=A_AMBER, opacity=0.9,
        ))
        dl = a_layout("Disease Detections by Year — West Nile Virus & St. Louis Encephalitis")
        dl["xaxis"]["dtick"] = 1
        dl["xaxis"]["title"] = "Year"
        dl["yaxis"]["title"] = "Positive Pool Tests"
        dl["barmode"] = "group"
        disease_fig.update_layout(**dl)

        trap_children = [
            html.Hr(style={"border": "none", "borderTop": f"2px solid {A_GRID}", "margin": "24px 0 18px"}),
            html.Div(
                style={"marginBottom": "16px"},
                children=[
                    html.H2("Trap Surveillance Data", style={"color": A_TEXT, "margin": "0 0 4px", "fontSize": "17px"}),
                    html.P(
                        "Historical mosquito trap data from SWMAC field sites across the St. George region, "
                        "2016–2025. Includes species identification and disease testing (WNV, SLE) results.",
                        style={"color": "#7A5C3F", "fontSize": "12px", "margin": 0},
                    ),
                ],
            ),
            dcc.Graph(figure=annual_fig, style={"height": "260px", "marginBottom": "12px"}),
            html.Div(
                className="two-col-grid",
                style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "12px",
                       "marginBottom": "12px"},
                children=[
                    dcc.Graph(figure=sp_fig,      style={"height": "300px"}),
                    dcc.Graph(figure=disease_fig, style={"height": "300px"}),
                ],
            ),
        ]

    if tab == "analytics":
        return html.Div(
            style={"padding": "16px 24px", "backgroundColor": A_PAPER},
            children=[
                dcc.Graph(figure=rolling_fig, style={"height": "210px", "marginBottom": "12px"}),
                html.Div(
                    className="two-col-grid",
                    style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "12px",
                           "marginBottom": "16px"},
                    children=[
                        dcc.Graph(figure=high_fig, style={"height": "280px"}),
                        dcc.Graph(figure=type_fig, style={"height": "280px"}),
                    ],
                ),
                dcc.Graph(figure=hotspot_fig, style={"height": "420px"}),
                *trap_children,
            ],
        ), cards

    # ── FORECAST TAB ─────────────────────────────────────────────────
    if tab == "forecast":
        F_PAPER  = "#FFF8EE"
        F_BG     = "#FFFDF7"
        F_TEXT   = "#3D2B1F"
        F_GRID   = "#DDD0BE"
        F_ORANGE = "#CC5500"
        F_AMBER  = "#F5A623"
        F_YELLOW = "#FFD166"
        F_BLUE   = "#2C7BB6"

        def f_layout(title):
            return dict(
                title=dict(text=title, font=dict(color=F_TEXT, size=13), x=0.02),
                paper_bgcolor=F_PAPER, plot_bgcolor=F_BG,
                font=dict(color=F_TEXT, size=11),
                margin=dict(l=50, r=16, t=44, b=40),
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10, color=F_TEXT)),
                xaxis=dict(gridcolor=F_GRID, zerolinecolor=F_GRID, color=F_TEXT),
                yaxis=dict(gridcolor=F_GRID, zerolinecolor=F_GRID, color=F_TEXT),
            )

        # Weekly totals across all sites
        weekly = mosq_df.groupby("Week_Start", as_index=False).agg({
            "Mosq_Count": "sum",
            "DailyAverageDryBulbTemperature": "mean",
            "DailyPrecipitation": "mean",
            "DailyAverageRelativeHumidity": "mean",
            "DailyAverageWindSpeed": "mean",
            "Risk_Level": "mean",
        })
        weekly = weekly.sort_values("Week_Start")

        # OLS predicted values
        weekly["Predicted"] = (
            _coef["const"]
            + _coef["DailyAverageDryBulbTemperature"] * weekly["DailyAverageDryBulbTemperature"]
            + _coef["DailyPrecipitation"] * weekly["DailyPrecipitation"]
            + _coef["DailyAverageRelativeHumidity"] * weekly["DailyAverageRelativeHumidity"]
            + _coef["DailyAverageWindSpeed"] * weekly["DailyAverageWindSpeed"]
        ).clip(lower=0)

        # --- Chart 1: Mosq count + temperature over time (dual axis) ---
        ts_fig = make_subplots(specs=[[{"secondary_y": True}]])
        ts_fig.add_trace(go.Bar(
            x=weekly["Week_Start"], y=weekly["Mosq_Count"],
            name="Actual Mosquito Count", marker_color=F_ORANGE, opacity=0.7,
        ), secondary_y=False)
        ts_fig.add_trace(go.Scatter(
            x=weekly["Week_Start"], y=weekly["Predicted"],
            name="Model Predicted", mode="lines",
            line=dict(color=F_AMBER, width=2, dash="dash"),
        ), secondary_y=False)
        ts_fig.add_trace(go.Scatter(
            x=weekly["Week_Start"], y=weekly["DailyAverageDryBulbTemperature"],
            name="Avg Temp (°F)", mode="lines",
            line=dict(color=F_BLUE, width=1.5),
        ), secondary_y=True)
        ts_fig.update_layout(
            title=dict(text="Weekly Mosquito Count vs Temperature  (actual vs model predicted)",
                       font=dict(color=F_TEXT, size=13), x=0.02),
            paper_bgcolor=F_PAPER, plot_bgcolor=F_BG,
            font=dict(color=F_TEXT, size=11),
            margin=dict(l=50, r=50, t=44, b=40),
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10, color=F_TEXT)),
            xaxis=dict(gridcolor=F_GRID, zerolinecolor=F_GRID, color=F_TEXT),
            yaxis=dict(title="Mosquito Count", gridcolor=F_GRID, color=F_TEXT),
            yaxis2=dict(title="Temperature (°F)", color=F_BLUE, showgrid=False),
            barmode="overlay",
        )

        # --- Chart 2: Risk level over time ---
        risk_fig = go.Figure()
        risk_fig.add_trace(go.Scatter(
            x=weekly["Week_Start"], y=weekly["Risk_Level"].round(1),
            mode="lines+markers",
            line=dict(color=F_ORANGE, width=2),
            marker=dict(size=5, color=weekly["Risk_Level"],
                        colorscale=[[0, F_YELLOW], [0.5, F_AMBER], [1, "#990000"]],
                        cmin=1, cmax=10),
            fill="tozeroy", fillcolor="rgba(204,85,0,0.10)",
            name="Risk Level",
        ))
        # Add threshold line at 5
        risk_fig.add_hline(y=5, line_dash="dot", line_color=F_AMBER,
                           annotation_text="Mid threshold (5)", annotation_font_color=F_TEXT)
        rl = f_layout("Weekly Mosquito Risk Level (1–10 Scale)")
        rl["yaxis"]["range"] = [0, 11]
        rl["yaxis"]["title"] = "Risk Level"
        risk_fig.update_layout(**rl)

        # --- Chart 3: Scatter — each variable vs mosq count (2x2) ---
        scatter_vars = [
            ("DailyAverageDryBulbTemperature", "Temperature (°F)", F_ORANGE),
            ("DailyPrecipitation",             "Precipitation",     F_BLUE),
            ("DailyAverageRelativeHumidity",   "Humidity (%)",      F_AMBER),
            ("DailyAverageWindSpeed",          "Wind Speed (mph)",  "#6C8EBF"),
        ]
        scatter_fig = make_subplots(rows=2, cols=2, subplot_titles=[v[1] for v in scatter_vars])
        for i, (col, label, color) in enumerate(scatter_vars):
            r, c = divmod(i, 2)
            scatter_fig.add_trace(
                go.Scatter(
                    x=mosq_df[col], y=mosq_df["Mosq_Count"],
                    mode="markers", marker=dict(color=color, opacity=0.35, size=4),
                    name=label, showlegend=False,
                ),
                row=r+1, col=c+1,
            )
        scatter_fig.update_layout(
            paper_bgcolor=F_PAPER, plot_bgcolor=F_BG,
            font=dict(color=F_TEXT, size=11),
            margin=dict(l=40, r=16, t=44, b=40),
            title=dict(text="Weather Variables vs Mosquito Count",
                       font=dict(color=F_TEXT, size=13), x=0.02),
        )
        scatter_fig.update_xaxes(gridcolor=F_GRID, zerolinecolor=F_GRID, color=F_TEXT)
        scatter_fig.update_yaxes(gridcolor=F_GRID, zerolinecolor=F_GRID, color=F_TEXT,
                                 title_text="Mosq Count")

        # --- Model equation panel ---
        coef = ols_model["coefficients"]
        pval = ols_model["pvalues"]
        def fmt(v): return f"+{v:.3f}" if v >= 0 else f"{v:.3f}"
        def sig(k): return " *" if pval[k] < 0.05 else ""
        eq = (
            f"Mosq Count = {coef['const']:.2f}"
            f"  {fmt(coef['DailyAverageDryBulbTemperature'])} × Temp{sig('DailyAverageDryBulbTemperature')}"
            f"  {fmt(coef['DailyPrecipitation'])} × Precip{sig('DailyPrecipitation')}"
            f"  {fmt(coef['DailyAverageRelativeHumidity'])} × Humidity{sig('DailyAverageRelativeHumidity')}"
            f"  {fmt(coef['DailyAverageWindSpeed'])} × Wind{sig('DailyAverageWindSpeed')}"
        )
        model_panel = html.Div(
            style={"backgroundColor": F_PAPER, "border": f"1px solid {F_GRID}",
                   "borderLeft": f"4px solid {F_ORANGE}", "borderRadius": "6px",
                   "padding": "14px 20px", "marginBottom": "14px"},
            children=[
                html.H3("OLS Regression Model", style={"color": F_TEXT, "margin": "0 0 4px",
                                                        "fontSize": "14px", "fontWeight": "bold"}),
                html.P(
                    "Ordinary Least Squares regression — a standard statistical method that finds the "
                    "best straight-line relationship between weather conditions and mosquito counts. "
                    "Fit on 2,289 weekly trap readings from 2023–2025.",
                    style={"fontSize": "12px", "color": "#7A5C3F", "margin": "0 0 8px", "lineHeight": "1.5"},
                ),
                html.P(eq, style={"fontFamily": "monospace", "fontSize": "12px",
                                  "color": F_TEXT, "margin": "0 0 6px", "wordBreak": "break-word"}),
                html.P(f"R² = {ols_model['rsquared']:.4f}  |  Adj R² = {ols_model['rsquared_adj']:.4f}"
                       f"  |  n = {ols_model['nobs']:,}  |  * = p < 0.05",
                       style={"fontSize": "11px", "color": "#7A5C3F", "margin": 0}),
            ],
        )

        def blurb(text):
            return html.P(text, style={
                "color": "#7A5C3F", "fontSize": "12px", "lineHeight": "1.6",
                "margin": "4px 0 14px", "maxWidth": "860px",
            })

        content = html.Div(
            style={"padding": "16px 24px", "backgroundColor": F_PAPER},
            children=[
                model_panel,
                blurb(
                    "This model estimates weekly mosquito counts using four weather inputs: temperature, "
                    "precipitation, humidity, and wind speed. Temperature is the only statistically "
                    "significant factor (marked with *). The orange bars show what traps actually caught "
                    "each week; the dashed amber line is what the model predicted. When the two track "
                    "closely, the model is doing its job — gaps indicate other factors (standing water "
                    "from construction, irrigation, etc.) are driving activity."
                ),
                dcc.Graph(figure=ts_fig, style={"height": "300px", "marginBottom": "4px"}),
                blurb(
                    "The blue line (right axis) shows average weekly temperature. Notice how mosquito "
                    "peaks closely follow temperature peaks — population booms typically lag a warm "
                    "stretch by 2–4 weeks, which is the time it takes for eggs to develop into adults. "
                    "This gives SWMAC an early warning window to pre-treat sites before adults emerge."
                ),
                dcc.Graph(figure=risk_fig, style={"height": "240px", "marginBottom": "4px"}),
                blurb(
                    "This chart translates raw trap counts into a 1–10 risk scale developed by Garrett "
                    "using z-scores — a measure of how far above or below the historical average a given "
                    "week's count is. Level 1 means near-zero activity (typical off-season). "
                    "Level 5 is around the seasonal average. Levels 8–10 represent significant "
                    "outbreaks — counts 1.5 to 3+ standard deviations above normal — and are the "
                    "threshold for immediate SWMAC response. The dotted line marks the mid-point (5)."
                ),
                dcc.Graph(figure=scatter_fig, style={"height": "420px", "marginBottom": "4px"}),
                blurb(
                    "Each scatter plot shows the raw relationship between one weather variable and "
                    "mosquito trap counts across all weeks and sites. Temperature (top-left) shows the "
                    "clearest upward trend — higher temps mean more mosquitoes. Precipitation (top-right) "
                    "shows a positive but noisy relationship; rain creates breeding habitat but St. George "
                    "gets so little rain that irrigation is often a bigger driver. Humidity and wind "
                    "(bottom row) show weaker patterns and were not statistically significant in the model."
                ),
            ],
        )

        # ── MODEL INSIGHTS (appended to bottom of forecast tab) ──────
        I_MUTED = "#7A5C3F"

        def i_layout(title):
            return dict(
                title=dict(text=title, font=dict(color=F_TEXT, size=12), x=0.02),
                paper_bgcolor=F_PAPER, plot_bgcolor=F_BG,
                font=dict(color=F_TEXT, size=10),
                margin=dict(l=44, r=12, t=36, b=36),
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=9, color=F_TEXT)),
                xaxis=dict(gridcolor=F_GRID, zerolinecolor=F_GRID, color=F_TEXT),
                yaxis=dict(gridcolor=F_GRID, zerolinecolor=F_GRID, color=F_TEXT),
            )

        def insight_card(title, body, border_color=None):
            return html.Div(
                style={
                    "backgroundColor": F_PAPER,
                    "border": f"1px solid {F_GRID}",
                    "borderLeft": f"4px solid {border_color or F_ORANGE}",
                    "borderRadius": "6px",
                    "padding": "14px 18px",
                    "display": "flex",
                    "flexDirection": "column",
                    "justifyContent": "center",
                },
                children=[
                    html.H4(title, style={"color": F_TEXT, "margin": "0 0 7px",
                                          "fontSize": "13px", "fontWeight": "bold"}),
                    html.P(body, style={"color": I_MUTED, "fontSize": "12px",
                                        "lineHeight": "1.6", "margin": 0}),
                ],
            )

        def irow(card, graph):
            return html.Div(
                className="insight-row",
                style={"display": "grid", "gridTemplateColumns": "1fr 2fr",
                       "gap": "14px", "marginBottom": "16px", "alignItems": "stretch"},
                children=[card, graph],
            )

        # Scatter charts
        temp_scatter = go.Figure(go.Scatter(
            x=mosq_df["DailyAverageDryBulbTemperature"], y=mosq_df["Mosq_Count"],
            mode="markers", marker=dict(color=F_ORANGE, opacity=0.3, size=4),
        ))
        _tsl = i_layout("Temperature (°F) vs Mosquito Count")
        _tsl["xaxis"]["title"] = "Avg Temperature (°F)"
        _tsl["yaxis"]["title"] = "Mosquito Count"
        temp_scatter.update_layout(**_tsl)

        precip_scatter = go.Figure(go.Scatter(
            x=mosq_df["DailyPrecipitation"], y=mosq_df["Mosq_Count"],
            mode="markers", marker=dict(color=F_BLUE, opacity=0.3, size=4),
        ))
        _psl = i_layout("Precipitation vs Mosquito Count")
        _psl["xaxis"]["title"] = "Precipitation (in)"
        _psl["yaxis"]["title"] = "Mosquito Count"
        precip_scatter.update_layout(**_psl)

        humid_scatter = go.Figure(go.Scatter(
            x=mosq_df["DailyAverageRelativeHumidity"], y=mosq_df["Mosq_Count"],
            mode="markers", marker=dict(color=F_AMBER, opacity=0.3, size=4),
        ))
        _hsl = i_layout("Humidity (%) vs Mosquito Count")
        _hsl["xaxis"]["title"] = "Relative Humidity (%)"
        _hsl["yaxis"]["title"] = "Mosquito Count"
        humid_scatter.update_layout(**_hsl)

        wind_scatter = go.Figure(go.Scatter(
            x=mosq_df["DailyAverageWindSpeed"], y=mosq_df["Mosq_Count"],
            mode="markers", marker=dict(color="#6C8EBF", opacity=0.3, size=4),
        ))
        _wsl = i_layout("Wind Speed vs Mosquito Count")
        _wsl["xaxis"]["title"] = "Avg Wind Speed (mph)"
        _wsl["yaxis"]["title"] = "Mosquito Count"
        wind_scatter.update_layout(**_wsl)

        def dual_ts(y2_col, y2_title, y2_color, title):
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(x=weekly["Week_Start"], y=weekly["Mosq_Count"],
                name="Mosquito Count", marker_color=F_ORANGE, opacity=0.65), secondary_y=False)
            fig.add_trace(go.Scatter(x=weekly["Week_Start"], y=weekly[y2_col],
                name=y2_title, mode="lines", line=dict(color=y2_color, width=1.8)),
                secondary_y=True)
            fig.update_layout(
                paper_bgcolor=F_PAPER, plot_bgcolor=F_BG, font=dict(color=F_TEXT, size=10),
                margin=dict(l=44, r=44, t=36, b=36),
                legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=9, color=F_TEXT)),
                xaxis=dict(gridcolor=F_GRID, color=F_TEXT),
                yaxis=dict(title="Mosquito Count", gridcolor=F_GRID, color=F_TEXT),
                yaxis2=dict(title=y2_title, color=y2_color, showgrid=False),
                title=dict(text=title, font=dict(color=F_TEXT, size=12), x=0.02),
            )
            return fig

        ts_temp   = dual_ts("DailyAverageDryBulbTemperature", "Temp (°F)",        F_BLUE,    "Mosquito Count + Temperature Over Time")
        ts_precip = dual_ts("DailyPrecipitation",              "Precipitation",    F_BLUE,    "Mosquito Count + Precipitation Over Time")
        ts_humid  = dual_ts("DailyAverageRelativeHumidity",    "Humidity (%)",     F_AMBER,   "Mosquito Count + Humidity Over Time")
        ts_wind   = dual_ts("DailyAverageWindSpeed",           "Wind Speed (mph)", "#6C8EBF", "Mosquito Count + Wind Speed Over Time")

        risk_dist = mosq_df["Risk_Level"].value_counts().sort_index()
        risk_bar = go.Figure(go.Bar(
            x=risk_dist.index, y=risk_dist.values,
            marker_color=[F_YELLOW, F_YELLOW, F_AMBER, F_AMBER, F_AMBER,
                          F_ORANGE, F_ORANGE, "#AA3300", "#880000", "#660000"][:len(risk_dist)],
            text=risk_dist.values, textposition="outside",
            textfont=dict(color=F_TEXT, size=10),
        ))
        _rb = i_layout("Risk Level Distribution (1–10)")
        _rb["xaxis"]["title"] = "Risk Level"
        _rb["xaxis"]["dtick"] = 1
        _rb["yaxis"]["title"] = "# Trap Readings"
        risk_bar.update_layout(**_rb)

        insights_section = [
            html.Hr(style={"border": "none", "borderTop": f"2px solid {F_GRID}", "margin": "28px 0 20px"}),
            html.Div(
                style={"marginBottom": "20px", "borderBottom": f"2px solid {F_ORANGE}", "paddingBottom": "14px"},
                children=[
                    html.H2("Model Insights", style={"color": F_TEXT, "margin": "0 0 6px", "fontSize": "18px"}),
                    html.P(
                        "Correlating historical weather data with SWMAC trap counts (2023–2025) to identify "
                        "which environmental conditions drive mosquito population booms. "
                        "All models use weekly aggregated data across St. George trap sites.",
                        style={"color": I_MUTED, "fontSize": "13px", "margin": 0, "lineHeight": "1.6"},
                    ),
                ],
            ),
            html.H3("Regression Model Overview", style={"color": F_ORANGE, "fontSize": "14px", "margin": "0 0 10px"}),
            html.Div(
                style={"backgroundColor": F_PAPER, "border": f"1px solid {F_GRID}",
                       "borderLeft": f"4px solid {F_ORANGE}", "borderRadius": "6px",
                       "padding": "14px 20px", "marginBottom": "20px"},
                children=[
                    html.P(
                        "An Ordinary Least Squares (OLS) regression was fit to predict weekly mosquito trap counts "
                        "from four weather variables: temperature, precipitation, humidity, and wind speed. "
                        "Temperature emerged as the only statistically significant predictor (p < 0.001), with a "
                        f"coefficient of +{ols_model['coefficients']['DailyAverageDryBulbTemperature']:.3f} — "
                        "meaning each additional degree of average temperature corresponds to roughly 0.72 more "
                        "mosquitoes per trap per week.",
                        style={"color": I_MUTED, "fontSize": "12px", "margin": "0 0 8px", "lineHeight": "1.7"},
                    ),
                    html.P(
                        f"The model's R² of {ols_model['rsquared']:.4f} reflects that weather alone explains a modest "
                        "portion of variance — other factors like standing water from construction activity, irrigation, "
                        "and trap placement also play a large role. The value of this model is directional forecasting: "
                        "as temperatures climb in spring, SWMAC can anticipate rising populations 2–4 weeks ahead.",
                        style={"color": I_MUTED, "fontSize": "12px", "margin": 0, "lineHeight": "1.7"},
                    ),
                ],
            ),
            html.H3("Temperature", style={"color": F_ORANGE, "fontSize": "14px", "margin": "0 0 10px"}),
            irow(insight_card("Strongest predictor (p < 0.001)",
                "Temperature has the clearest and most consistent relationship with mosquito counts. "
                "Populations surge during St. George's hot summers — trap counts regularly spike above "
                "the historical mean when weekly averages exceed ~85°F. The scatter shows a wide spread "
                "at higher temperatures, reflecting that heat is necessary but not sufficient on its own.", F_ORANGE),
                dcc.Graph(figure=temp_scatter, style={"height": "260px"})),
            irow(insight_card("Population timing follows temperature",
                "The dual-axis time series shows mosquito peaks closely track temperature peaks across "
                "2023–2025. The lag between temperature rise and population boom (roughly 2–4 weeks) "
                "reflects egg-to-adult development time, giving SWMAC an actionable lead time for "
                "larvicide deployment before adults emerge.", F_ORANGE),
                dcc.Graph(figure=ts_temp, style={"height": "260px"})),
            html.H3("Precipitation", style={"color": F_BLUE, "fontSize": "14px", "margin": "16px 0 10px"}),
            irow(insight_card("Positive relationship, high variability",
                "Precipitation shows a positive coefficient (+10.52) — rain events create temporary "
                "standing water that serves as breeding habitat. However, the relationship is not "
                "statistically significant, likely because St. George receives very little rainfall "
                "overall and irrigation is a more consistent water source than precipitation.", F_BLUE),
                dcc.Graph(figure=precip_scatter, style={"height": "260px"})),
            irow(insight_card("Short-term spikes after rain events",
                "Looking at the time series, brief rainfall events occasionally correspond with "
                "short-term upticks in trap counts in subsequent weeks. These are most pronounced "
                "during summer when temperatures are already high enough to accelerate larval "
                "development in newly formed standing water.", F_BLUE),
                dcc.Graph(figure=ts_precip, style={"height": "260px"})),
            html.H3("Humidity", style={"color": F_AMBER, "fontSize": "14px", "margin": "16px 0 10px"}),
            irow(insight_card("Slight negative coefficient in arid climate",
                "Contrary to what one might expect, relative humidity shows a slight negative "
                "coefficient (−0.11) in St. George — not statistically significant. In arid desert "
                "climates, higher humidity often co-occurs with cooler or windy conditions, which "
                "may suppress activity. The local irrigation-driven microclimate likely confounds "
                "the broader humidity signal.", F_AMBER),
                dcc.Graph(figure=humid_scatter, style={"height": "260px"})),
            irow(insight_card("Humidity peaks inverse to mosquito season",
                "Relative humidity in St. George tends to be highest in winter and during "
                "monsoon season, while mosquito populations peak mid-summer during the driest "
                "stretch. This inverse seasonal pattern helps explain why humidity does not "
                "emerge as a positive predictor in this dataset.", F_AMBER),
                dcc.Graph(figure=ts_humid, style={"height": "260px"})),
            html.H3("Wind Speed", style={"color": "#6C8EBF", "fontSize": "14px", "margin": "16px 0 10px"}),
            irow(insight_card("Minor positive effect, not significant",
                "Wind speed carries a positive coefficient (+1.68) in the model but is not "
                "statistically significant. Wind does not directly support mosquito breeding, "
                "but higher wind readings in this dataset may be co-occurring with warm summer "
                "weather patterns — making the coefficient a proxy for season rather than a "
                "causal driver.", "#6C8EBF"),
                dcc.Graph(figure=wind_scatter, style={"height": "260px"})),
            irow(insight_card("No clear directional pattern in time series",
                "Wind speed over 2023–2025 shows no consistent relationship with population "
                "highs or lows in the time series. This reinforces that wind is not a primary "
                "driver of mosquito activity in this region — temperature remains the dominant "
                "environmental signal.", "#6C8EBF"),
                dcc.Graph(figure=ts_wind, style={"height": "260px"})),
            html.H3("Risk Classification (1–10 Scale)", style={"color": F_ORANGE, "fontSize": "14px", "margin": "16px 0 10px"}),
            irow(insight_card("Z-score based risk levels",
                "The 1–10 risk scale classifies each trap reading relative to the "
                f"historical mean ({_mosq_mean:.0f} mosquitoes) and standard deviation ({_mosq_std:.0f}). "
                "Level 5 represents counts near the mean. Levels 8–10 correspond to population "
                "events exceeding 1.5–3 standard deviations above average — significant outbreaks "
                "warranting immediate SWMAC response. The majority of readings fall at level 1 "
                "(off-season, near-zero counts), which is expected given St. George's short "
                "active mosquito season.", F_ORANGE),
                dcc.Graph(figure=risk_bar, style={"height": "260px"})),
        ]

        content.children.extend(insights_section)
        return content, cards


if __name__ == "__main__":
    app.run(debug=True)

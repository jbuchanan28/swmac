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
server = app.server  # for gunicorn

df_full = load_data()
min_year = df_full["date"].dt.year.min()
max_year = df_full["date"].dt.year.max()

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
            style={"display": "flex", "gap": "12px", "padding": "16px 24px", "flexWrap": "wrap"},
        ),

        # ── Analytics Section ──────────────────────────────────────────
        html.Div(
            style={"padding": "0 24px 8px"},
            children=[
                html.H3("Analytics", style={"color": "#fff", "fontSize": "16px", "marginBottom": "12px"}),
                html.Div(
                    style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "12px"},
                    children=[
                        dcc.Graph(id="chart-permits-by-year", style={"height": "240px"}),
                        dcc.Graph(id="chart-risk-donut",      style={"height": "240px"}),
                        dcc.Graph(id="chart-monthly",         style={"height": "240px"}),
                        dcc.Graph(id="chart-top-types",       style={"height": "240px"}),
                    ],
                ),
            ],
        ),

        # Filters
        html.Div(
            style={"display": "flex", "gap": "16px", "padding": "8px 24px 16px", "flexWrap": "wrap", "alignItems": "flex-end"},
            children=[
                html.Div([
                    html.Label("Risk Tier", style={"fontSize": "12px", "color": "#aaa"}),
                    dcc.Dropdown(
                        id="filter-tier",
                        options=[{"label": t, "value": t} for t in ["Monitor", "Larvicide", "Adulticide"]],
                        multi=True,
                        placeholder="All tiers",
                        style={"width": "200px", "backgroundColor": "#1a1d2e", "color": "#000"},
                    ),
                ]),
                html.Div([
                    html.Label("Risk Class", style={"fontSize": "12px", "color": "#aaa"}),
                    dcc.Dropdown(
                        id="filter-class",
                        options=[{"label": c, "value": c} for c in ["HIGH", "MEDIUM", "LOW"]],
                        multi=True,
                        placeholder="All classes",
                        style={"width": "200px", "backgroundColor": "#1a1d2e", "color": "#000"},
                    ),
                ]),
                html.Div([
                    html.Label(f"Year Range ({min_year}–{max_year})", style={"fontSize": "12px", "color": "#aaa"}),
                    dcc.RangeSlider(
                        id="filter-year",
                        min=min_year, max=max_year,
                        value=[min_year, max_year],
                        marks={y: str(y) for y in range(min_year, max_year + 1, 2)},
                        step=1,
                        tooltip={"placement": "bottom"},
                    ),
                ], style={"width": "340px"}),
            ],
        ),

        # Map
        html.Div(
            style={"padding": "0 24px"},
            children=[dcc.Graph(id="risk-map", style={"height": "520px"})],
        ),

        # Table
        html.Div(
            style={"padding": "16px 24px"},
            children=[
                html.H3("Permit Details", style={"color": "#fff", "marginBottom": "8px", "fontSize": "16px"}),
                dash_table.DataTable(
                    id="permits-table",
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
                    page_size=15,
                    sort_action="native",
                    filter_action="native",
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
            ],
        ),

        html.Div(
            style={"textAlign": "center", "padding": "16px", "color": "#555", "fontSize": "11px"},
            children=["SWMAC Risk System — Data updated as geocoding completes"],
        ),
    ],
)


@app.callback(
    Output("risk-map", "figure"),
    Output("permits-table", "data"),
    Output("stat-cards", "children"),
    Output("chart-permits-by-year", "figure"),
    Output("chart-risk-donut", "figure"),
    Output("chart-monthly", "figure"),
    Output("chart-top-types", "figure"),
    Input("filter-tier", "value"),
    Input("filter-class", "value"),
    Input("filter-year", "value"),
)
def update_dashboard(tiers, classes, year_range):
    df = df_full.copy()

    if tiers:
        df = df[df["risk_tier"].isin(tiers)]
    if classes:
        df = df[df["risk_class"].isin(classes)]
    if year_range:
        df = df[(df["date"].dt.year >= year_range[0]) & (df["date"].dt.year <= year_range[1])]

    # ── Map ──────────────────────────────────────────────────────────
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

    # ── Table ────────────────────────────────────────────────────────
    table_cols = ["permit_id", "date_str", "project_name", "address", "permit_type",
                  "risk_class", "composite_score", "risk_tier"]
    table_data = df[table_cols].sort_values("composite_score", ascending=False).to_dict("records")

    # ── Stat cards ───────────────────────────────────────────────────
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

    # ── Chart 1: Permits by year, stacked by risk class ──────────────
    yearly = df.groupby([df["date"].dt.year, "risk_class"]).size().unstack(fill_value=0).reset_index()
    yearly.columns.name = None
    yearly_fig = go.Figure()
    for rc, color in RISK_COLORS.items():
        if rc in yearly.columns:
            yearly_fig.add_trace(go.Bar(
                x=yearly["date"], y=yearly[rc],
                name=rc, marker_color=color,
            ))
    yearly_fig.update_layout(
        **chart_layout("Permits by Year"),
        barmode="stack",
        xaxis=dict(title="Year", gridcolor=AXIS_COLOR),
        yaxis=dict(title="Count", gridcolor=AXIS_COLOR),
    )

    # ── Chart 2: Risk tier donut ──────────────────────────────────────
    donut_fig = go.Figure(go.Pie(
        labels=list(TIER_COLORS.keys()),
        values=[tier_counts.get(t, 0) for t in TIER_COLORS],
        hole=0.55,
        marker=dict(colors=list(TIER_COLORS.values())),
        textfont=dict(color="#fff"),
    ))
    donut_fig.update_layout(
        **chart_layout("Risk Tier Breakdown"),
        showlegend=True,
    )

    # ── Chart 3: Seasonal pattern — avg permits per calendar month ────
    df["month"] = df["date"].dt.month
    monthly = df.groupby("month").size().reindex(range(1, 13), fill_value=0)
    month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    monthly_fig = go.Figure(go.Bar(
        x=month_names,
        y=monthly.values,
        marker_color="#3498db",
    ))
    monthly_fig.update_layout(
        **chart_layout("Permits by Month (Seasonal Pattern)"),
        xaxis=dict(title="Month", gridcolor=AXIS_COLOR),
        yaxis=dict(title="Count", gridcolor=AXIS_COLOR),
    )

    # ── Chart 4: Top 10 permit types by HIGH risk count ───────────────
    top_types = (
        df[df["risk_class"] == "HIGH"]
        .groupby("permit_type").size()
        .sort_values(ascending=True)
        .tail(10)
    )
    top_fig = go.Figure(go.Bar(
        x=top_types.values,
        y=top_types.index,
        orientation="h",
        marker_color="#e74c3c",
    ))
    top_fig.update_layout(
        **chart_layout("Top HIGH Risk Permit Types"),
        xaxis=dict(title="Count", gridcolor=AXIS_COLOR),
        yaxis=dict(gridcolor=AXIS_COLOR),
        margin=dict(l=160, r=16, t=40, b=40),
    )

    return map_fig, table_data, cards, yearly_fig, donut_fig, monthly_fig, top_fig


if __name__ == "__main__":
    app.run(debug=True)

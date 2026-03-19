"""
Build an interactive Folium map with:
  - Color-coded permit markers by risk tier
  - Heatmap overlay weighted by composite score
  - Cluster alerts marked with special icons
  - Trap site locations (if available)
"""
import folium
from folium.plugins import HeatMap, MarkerCluster
import pandas as pd
from pathlib import Path
from typing import Optional

OUTPUT_DIR = Path(__file__).parent.parent / "output"
MAP_CENTER = [37.1041, -113.5841]  # St. George, UT

TIER_COLORS = {
    "Monitor": "green",
    "Larvicide": "orange",
    "Adulticide": "red",
}

TIER_ICONS = {
    "Monitor": "info-sign",
    "Larvicide": "warning-sign",
    "Adulticide": "exclamation-sign",
}


def _permit_popup(row: pd.Series) -> str:
    return f"""
    <b>{row.get('project_name', 'Unknown')}</b><br>
    <b>Address:</b> {row.get('address', '')}<br>
    <b>Permit:</b> {row.get('permit_id', '')}<br>
    <b>Type:</b> {row.get('permit_type', '')}<br>
    <b>Date:</b> {str(row.get('date', ''))[:10]}<br>
    <b>Risk Class:</b> {row.get('risk_class', '')}<br>
    <b>Score:</b> {row.get('composite_score', 0):.2f}<br>
    <b>Action:</b> <span style="color:{TIER_COLORS.get(row.get('risk_tier','Monitor'), 'gray')}">
        <b>{row.get('risk_tier', '')}</b>
    </span>
    """


def build_map(
    scored_df: pd.DataFrame,
    clusters: list,
    trap_df: Optional[pd.DataFrame] = None,
    output_path: Optional[Path] = None,
) -> Path:
    if output_path is None:
        output_path = OUTPUT_DIR / "swmac_risk_map.html"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    m = folium.Map(location=MAP_CENTER, zoom_start=12, tiles="OpenStreetMap")

    # Layer groups
    high_group = folium.FeatureGroup(name="HIGH Risk Permits", show=True)
    med_group = folium.FeatureGroup(name="MEDIUM Risk Permits", show=True)
    low_group = folium.FeatureGroup(name="LOW Risk Permits", show=False)
    cluster_group = folium.FeatureGroup(name="Risk Clusters", show=True)
    heatmap_group = folium.FeatureGroup(name="Risk Heatmap", show=True)

    # Permit markers
    mapped_df = scored_df.dropna(subset=["lat", "lon"])
    for _, row in mapped_df.iterrows():
        tier = row.get("risk_tier", "Monitor")
        color = TIER_COLORS.get(tier, "blue")
        icon = TIER_ICONS.get(tier, "info-sign")
        marker = folium.Marker(
            location=[row["lat"], row["lon"]],
            popup=folium.Popup(_permit_popup(row), max_width=300),
            tooltip=f"{row.get('project_name','?')} — {tier}",
            icon=folium.Icon(color=color, icon=icon, prefix="glyphicon"),
        )
        if row.get("risk_class") == "HIGH":
            high_group.add_child(marker)
        elif row.get("risk_class") == "MEDIUM":
            med_group.add_child(marker)
        else:
            low_group.add_child(marker)

    # Heatmap (weighted by composite score)
    heat_data = [
        [row["lat"], row["lon"], min(row["composite_score"], 6)]
        for _, row in mapped_df.iterrows()
        if not pd.isna(row.get("composite_score"))
    ]
    if heat_data:
        HeatMap(heat_data, radius=25, blur=15, max_zoom=13).add_to(heatmap_group)

    # Cluster alert markers
    for cluster in clusters:
        folium.Marker(
            location=[cluster["centroid_lat"], cluster["centroid_lon"]],
            popup=folium.Popup(
                f"<b>CLUSTER ALERT</b><br>{cluster['count']} HIGH-risk permits within 1 mile<br>"
                f"Permits: {', '.join(cluster['permit_ids'][:5])}",
                max_width=300,
            ),
            tooltip=f"CLUSTER: {cluster['count']} HIGH permits",
            icon=folium.Icon(color="purple", icon="star", prefix="glyphicon"),
        ).add_to(cluster_group)

    # Trap locations
    if trap_df is not None and not trap_df.empty:
        trap_group = folium.FeatureGroup(name="Trap Sites", show=True)
        trap_mapped = trap_df.dropna(subset=["lat", "lon"])
        for _, row in trap_mapped.iterrows():
            folium.CircleMarker(
                location=[row["lat"], row["lon"]],
                radius=6,
                color="blue",
                fill=True,
                fill_color="blue",
                fill_opacity=0.6,
                popup=f"Trap: {row.get('site', '')}",
                tooltip=f"Trap site: {row.get('site', '')}",
            ).add_to(trap_group)
        trap_group.add_to(m)

    # Add all layers
    heatmap_group.add_to(m)
    high_group.add_to(m)
    med_group.add_to(m)
    low_group.add_to(m)
    cluster_group.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    # Legend
    legend_html = """
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000;
                background-color: white; padding: 12px; border-radius: 6px;
                border: 2px solid #ccc; font-size: 13px;">
      <b>SWMAC Risk Legend</b><br>
      <i class="glyphicon glyphicon-map-marker" style="color:green"></i> Monitor (score &lt; 2)<br>
      <i class="glyphicon glyphicon-map-marker" style="color:orange"></i> Larvicide (score 2–4)<br>
      <i class="glyphicon glyphicon-map-marker" style="color:red"></i> Adulticide (score &gt; 4)<br>
      <i class="glyphicon glyphicon-map-marker" style="color:purple"></i> Cluster Alert<br>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    m.save(str(output_path))
    return output_path


if __name__ == "__main__":
    print("map_builder: run via main.py")

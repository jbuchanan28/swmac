"""
Console alert system using rich for formatted output.
Prints HIGH-risk permits from the last N days and cluster warnings.
"""
import pandas as pd
from datetime import date, timedelta
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()

TIER_STYLES = {
    "Monitor": "green",
    "Larvicide": "yellow",
    "Adulticide": "bold red",
}

DEFAULT_ALERT_DAYS = 30


def print_alerts(
    scored_df: pd.DataFrame,
    clusters: list,
    days: int = DEFAULT_ALERT_DAYS,
    as_of: Optional[date] = None,
) -> None:
    if as_of is None:
        as_of = date.today()

    cutoff = pd.Timestamp(as_of - timedelta(days=days))

    # Header
    console.print(Panel(
        f"[bold cyan]SWMAC Mosquito Risk Alert System[/bold cyan]\n"
        f"Report date: [white]{as_of}[/white]  |  "
        f"Showing permits issued in last [white]{days}[/white] days",
        border_style="cyan",
    ))

    # Cluster alerts
    if clusters:
        console.print(f"\n[bold red]⚠  {len(clusters)} CLUSTER ALERT(S) DETECTED[/bold red]")
        for i, c in enumerate(clusters, 1):
            console.print(
                f"  Cluster {i}: [bold]{c['count']} HIGH-risk permits[/bold] within 1 mile  "
                f"(centroid: {c['centroid_lat']:.4f}, {c['centroid_lon']:.4f})\n"
                f"  Permits: {', '.join(c['permit_ids'][:5])}"
            )
        console.print()
    else:
        console.print("\n[green]No cluster alerts.[/green]\n")

    # Filter recent high + larvicide permits
    recent = scored_df[
        (scored_df["date"] >= cutoff) &
        (scored_df["risk_tier"].isin(["Adulticide", "Larvicide"]))
    ].copy()

    recent = recent.sort_values("composite_score", ascending=False)

    if recent.empty:
        console.print(f"[green]No Larvicide/Adulticide permits in the last {days} days.[/green]")
    else:
        table = Table(
            title=f"High-Priority Permits — Last {days} Days",
            box=box.ROUNDED,
            show_lines=True,
        )
        table.add_column("Permit ID", style="cyan", no_wrap=True)
        table.add_column("Date", style="white")
        table.add_column("Project Name", style="white")
        table.add_column("Address", style="white")
        table.add_column("Type", style="white")
        table.add_column("Risk", style="white")
        table.add_column("Score", justify="right")
        table.add_column("Action", justify="center")

        for _, row in recent.iterrows():
            tier = row.get("risk_tier", "Monitor")
            style = TIER_STYLES.get(tier, "white")
            days_old = (as_of - row["date"].date()).days
            table.add_row(
                str(row.get("permit_id", "")),
                f"{str(row['date'])[:10]} ({days_old}d ago)",
                str(row.get("project_name", ""))[:40],
                str(row.get("address", ""))[:35],
                str(row.get("permit_type", ""))[:25],
                str(row.get("risk_class", "")),
                f"{row.get('composite_score', 0):.2f}",
                f"[{style}]{tier}[/{style}]",
            )

        console.print(table)

    # Summary stats
    total = len(scored_df)
    geocoded = scored_df["lat"].notna().sum()
    tier_counts = scored_df["risk_tier"].value_counts()

    console.print(Panel(
        f"Total permits: [white]{total}[/white]  |  "
        f"Geocoded: [white]{geocoded}[/white] ({geocoded/total*100:.0f}%)\n"
        f"[red]Adulticide: {tier_counts.get('Adulticide', 0)}[/red]  |  "
        f"[yellow]Larvicide: {tier_counts.get('Larvicide', 0)}[/yellow]  |  "
        f"[green]Monitor: {tier_counts.get('Monitor', 0)}[/green]",
        title="Summary",
        border_style="white",
    ))

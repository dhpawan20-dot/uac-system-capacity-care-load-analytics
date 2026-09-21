"""
System Capacity & Care Load Analytics for Unaccompanied Children
Streamlit Dashboard

Run with: streamlit run app.py
Expects uac_daily_processed.csv and uac_forecast_14day.csv in the same folder
(produced by pipeline.py).
"""

import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="UAC System Capacity & Care Load Analytics",
    page_icon="🏥",
    layout="wide",
)

NAVY = "#1B2A4A"
ACCENT = "#2E86AB"
RED = "#E4572E"


@st.cache_data
def load_data():
    df = pd.read_csv("uac_daily_processed.csv", parse_dates=["Date"])
    forecast = pd.read_csv("uac_forecast_14day.csv", parse_dates=["Date"])
    return df, forecast


@st.cache_data
def load_summary():
    with open("uac_analysis_summary.json") as f:
        return json.load(f)


df, forecast = load_data()
summary = load_summary()

# ---------------------------------------------------------------------------
# Sidebar — User Capabilities: date range, metric toggles, granularity
# ---------------------------------------------------------------------------
st.sidebar.title("🔎 Controls")

min_d, max_d = df["Date"].min().date(), df["Date"].max().date()
date_range = st.sidebar.date_input("Date range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_d, end_d = date_range
else:
    start_d, end_d = min_d, max_d

granularity = st.sidebar.radio("Time granularity", ["Daily", "Weekly", "Monthly"], index=0)

metric_options = ["Total System Load", "CBP Custody", "HHS Care", "Net Daily Intake"]
metrics_on = st.sidebar.multiselect("Metrics to show", metric_options, default=["Total System Load"])

show_anomalies = st.sidebar.checkbox("Highlight flagged data-quality anomalies", value=False)

mask = (df["Date"].dt.date >= start_d) & (df["Date"].dt.date <= end_d)
fdf = df.loc[mask].copy()

if granularity == "Weekly":
    fdf = fdf.set_index("Date").resample("W").mean(numeric_only=True).reset_index()
elif granularity == "Monthly":
    fdf = fdf.set_index("Date").resample("ME").mean(numeric_only=True).reset_index()

st.sidebar.markdown("---")
st.sidebar.caption(f"Showing **{len(fdf)}** {granularity.lower()} points of {len(df)} total days")
st.sidebar.caption("Source: HHS Unaccompanied Alien Children Program daily report")

# ---------------------------------------------------------------------------
# Header + KPI Summary Cards
# ---------------------------------------------------------------------------
st.title("🏥 System Capacity & Care Load Analytics")
st.caption("Unaccompanied Children Program — CBP custody & HHS care system-load monitoring")

k = summary["kpis"]
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Children Under Care", f"{k['TotalChildrenUnderCare']['value']:,.0f}")
c2.metric("Net Intake Pressure", f"{k['NetIntakePressure']['value']:+.2f}/day")
c3.metric("Care Load Volatility Index", f"{k['CareLoadVolatilityIndex']['value']:,.1f}")
c4.metric("Backlog Accumulation Rate", f"{k['BacklogAccumulationRate']['value']:.1f}%")
c5.metric("Discharge Offset Ratio", f"{k['DischargeOffsetRatio']['value']:.1f}%")

st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 System Load Overview", "⚖️ CBP vs HHS Comparison", "📈 Net Intake & Backlog", "🔮 Forecast & Strain Periods"
])

# --- Tab 1: System Load Overview -------------------------------------------
with tab1:
    st.subheader("System Load Overview")
    plot_df = fdf.copy()
    fig = go.Figure()
    metric_map = {
        "Total System Load": ("TotalSystemLoad", NAVY),
        "CBP Custody": ("CBPCustody", RED),
        "HHS Care": ("HHSCare", ACCENT),
        "Net Daily Intake": ("NetDailyIntake", "#7A7A7A"),
    }
    for m in metrics_on:
        col, color = metric_map[m]
        fig.add_trace(go.Scatter(x=plot_df["Date"], y=plot_df[col], name=m, line=dict(color=color, width=2)))
    if show_anomalies:
        anomalies = fdf[fdf.get("AnomalyFlag", False) == True]
        if len(anomalies):
            fig.add_trace(go.Scatter(x=anomalies["Date"], y=anomalies["TotalSystemLoad"],
                                      mode="markers", name="Flagged anomaly",
                                      marker=dict(color="red", size=6, symbol="x")))
    fig.update_layout(height=500, yaxis_title="Children", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("##### Rolling averages (pressure smoothing)")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=fdf["Date"], y=fdf["TotalLoad_7d"], name="7-day avg", line=dict(color=ACCENT)))
    fig2.add_trace(go.Scatter(x=fdf["Date"], y=fdf["TotalLoad_14d"], name="14-day avg", line=dict(color=NAVY)))
    fig2.update_layout(height=350, yaxis_title="Total system load")
    st.plotly_chart(fig2, use_container_width=True)

# --- Tab 2: CBP vs HHS comparison -------------------------------------------
with tab2:
    st.subheader("CBP vs HHS Load Comparison")
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(x=fdf["Date"], y=fdf["CBPCustody"], name="CBP Custody",
                               stackgroup="one", line=dict(color=RED)))
    fig3.add_trace(go.Scatter(x=fdf["Date"], y=fdf["HHSCare"], name="HHS Care",
                               stackgroup="one", line=dict(color=ACCENT)))
    fig3.update_layout(height=500, yaxis_title="Children")
    st.plotly_chart(fig3, use_container_width=True)

    share_df = fdf.copy()
    share_df["CBPShare"] = share_df["CBPCustody"] / share_df["TotalSystemLoad"] * 100
    share_df["HHSShare"] = share_df["HHSCare"] / share_df["TotalSystemLoad"] * 100
    st.markdown("##### System share over time (%)")
    fig4 = px.area(share_df, x="Date", y=["CBPShare", "HHSShare"], height=350,
                    color_discrete_sequence=[RED, ACCENT])
    st.plotly_chart(fig4, use_container_width=True)

# --- Tab 3: Net Intake & Backlog --------------------------------------------
with tab3:
    st.subheader("Net Intake & Backlog Trends")
    fig5 = go.Figure()
    colors = ["#E4572E" if v > 0 else "#2E86AB" for v in fdf["NetIntake_7d"]]
    fig5.add_trace(go.Bar(x=fdf["Date"], y=fdf["NetIntake_7d"], marker_color=colors, name="Net intake (7d avg)"))
    fig5.add_hline(y=0, line_color="black", line_width=1)
    fig5.update_layout(height=450, yaxis_title="Net children/day (transfers-in minus discharges)")
    st.plotly_chart(fig5, use_container_width=True)

    st.markdown("##### Backlog indicator (sustained positive net intake, 7-day sum)")
    backlog_pct = fdf["BacklogIndicator"].mean() * 100 if "BacklogIndicator" in fdf else 0
    st.progress(min(int(backlog_pct), 100), text=f"{backlog_pct:.1f}% of selected period showed backlog accumulation")

    st.markdown("##### Care load growth rate (day-over-day % change)")
    fig6 = px.line(fdf, x="Date", y="CareLoadGrowthRate", height=350)
    fig6.update_traces(line_color=NAVY)
    fig6.add_hline(y=0, line_color="gray", line_dash="dot")
    st.plotly_chart(fig6, use_container_width=True)

# --- Tab 4: Forecast & strain periods ---------------------------------------
with tab4:
    st.subheader("14-Day Forecast: Total System Load")
    recent = df.tail(90)
    fig7 = go.Figure()
    fig7.add_trace(go.Scatter(x=recent["Date"], y=recent["TotalSystemLoad"], name="Observed", line=dict(color=NAVY)))
    fig7.add_trace(go.Scatter(x=forecast["Date"], y=forecast["ForecastTotalSystemLoad"], name="Forecast",
                               line=dict(color=RED, dash="dash"), mode="lines+markers"))
    fig7.update_layout(height=450, yaxis_title="Children")
    st.plotly_chart(fig7, use_container_width=True)
    st.caption("Naive trend-projection forecast based on the last 28 observed days — intended as a directional signal, not an official projection.")

    st.markdown("##### Sustained high-load periods (7+ consecutive days above 75th percentile)")
    if summary["high_load_runs_7plus_days"]:
        st.dataframe(pd.DataFrame(summary["high_load_runs_7plus_days"]), use_container_width=True)
    else:
        st.write("None detected in the observed range.")

    st.markdown("##### Prolonged strain windows (14+ days of sustained positive net intake)")
    if summary["strain_windows_14plus_days"]:
        st.dataframe(pd.DataFrame(summary["strain_windows_14plus_days"]), use_container_width=True)
    else:
        st.write("None detected in the observed range.")

    st.markdown("##### Early vs. late period comparison")
    ev = summary["early_vs_late"]
    ec1, ec2 = st.columns(2)
    ec1.metric(f"Early period avg load\n({ev['early_period']})", f"{ev['early_avg_total_load']:,.0f}")
    ec2.metric(f"Late period avg load\n({ev['late_period']})", f"{ev['late_avg_total_load']:,.0f}")

st.markdown("---")
st.caption(
    "KPI definitions — Total Children Under Care: CBP + HHS combined · Net Intake Pressure: 30-day avg "
    "transfers-in minus discharges · Care Load Volatility Index: 90-day std. dev. of total load · "
    "Backlog Accumulation Rate: % of last 90 days with positive net intake · Discharge Offset Ratio: "
    "discharges as % of transfers-in (last 30 days)."
)

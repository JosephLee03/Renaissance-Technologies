from __future__ import annotations

from datetime import datetime
import sqlite3
from threading import Lock
from pathlib import Path
from typing import Dict

import dash
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, dcc, html


PALETTE: Dict[str, str] = {
    "bg": "#04070f",
    "panel": "#0b1324",
    "card": "#111c33",
    "text": "#e8f1ff",
    "subtext": "#8aa2c8",
    "accent": "#00d4ff",
    "accent2": "#55efc4",
    "warning": "#ff7675",
}

UI_VERSION = "2026.04.20"
BANNER_TEXT = f"Renaissance-Technologies | GUI VERSION {UI_VERSION} | BUILD VERIFIED"


def _read_table(db_path: Path, table: str) -> pd.DataFrame:
    if not db_path.exists():
        return pd.DataFrame()
    with sqlite3.connect(db_path) as conn:
        try:
            return pd.read_sql_query(f"SELECT * FROM {table}", conn)
        except Exception:
            return pd.DataFrame()


def _empty_fig(title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title=title,
        template="plotly_dark",
        paper_bgcolor=PALETTE["panel"],
        plot_bgcolor=PALETTE["panel"],
        font={"color": PALETTE["text"]},
        margin={"l": 40, "r": 20, "t": 50, "b": 40},
    )
    return fig


def _latest_run_id(strategy_df: pd.DataFrame, eq_df: pd.DataFrame) -> str:
    if not strategy_df.empty and "run_id" in strategy_df.columns and not strategy_df["run_id"].dropna().empty:
        return str(strategy_df["run_id"].dropna().astype(str).max())
    if not eq_df.empty and "run_id" in eq_df.columns and not eq_df["run_id"].dropna().empty:
        return str(eq_df["run_id"].dropna().astype(str).max())
    return ""


def _filter_run(df: pd.DataFrame, run_id: str) -> pd.DataFrame:
    if df.empty or not run_id or "run_id" not in df.columns:
        return df
    return df[df["run_id"].astype(str) == run_id].copy()


def _card(title: str, element_id: str) -> html.Div:
    return html.Div(
        [
            html.Div(title, style={"fontSize": "12px", "color": PALETTE["subtext"], "letterSpacing": "0.8px"}),
            html.Div("-", id=element_id, style={"fontSize": "24px", "fontWeight": "700", "marginTop": "6px"}),
        ],
        style={
            "background": PALETTE["card"],
            "border": f"1px solid {PALETTE['accent']}33",
            "borderRadius": "12px",
            "padding": "12px 14px",
            "minWidth": "180px",
            "flex": "1 1 180px",
            "boxShadow": "0 0 20px rgba(0, 212, 255, 0.08)",
        },
    )


def create_app(db_path: str | Path) -> dash.Dash:
    db_file = Path(db_path)
    launch_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ui_fingerprint = f"RT-CTA-GUI::{UI_VERSION}::{int(Path(__file__).stat().st_mtime)}"
    assets_dir = Path(__file__).resolve().parent / "assets"
    app = dash.Dash(__name__, assets_folder=str(assets_dir))
    app.title = f"Renaissance-Technologies | CTA Command Center | {UI_VERSION}"
    app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <meta http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate, max-age=0" />
        <meta http-equiv="Pragma" content="no-cache" />
        <meta http-equiv="Expires" content="0" />
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
</html>
"""

    @app.server.get("/__rt_gui_info")
    def _rt_gui_info():
        return {
            "ui_version": UI_VERSION,
            "banner": BANNER_TEXT,
            "title": app.title,
            "app_module": str(Path(__file__).resolve()),
            "db_path": str(db_file.resolve()),
        }

    app.layout = html.Div(
        [
            html.Div(
                f"UI_ASSERT::{UI_VERSION}",
                id="ui_assert",
                style={
                    "position": "fixed",
                    "left": "12px",
                    "top": "12px",
                    "zIndex": "10001",
                    "padding": "8px 10px",
                    "borderRadius": "8px",
                    "fontSize": "12px",
                    "fontWeight": "700",
                    "letterSpacing": "1px",
                    "color": "#00131b",
                    "background": "#00d4ff",
                    "boxShadow": "0 0 18px rgba(0, 212, 255, 0.4)",
                    "border": "1px solid #8af0ff",
                },
            ),
            html.Div(
                [
                    html.Span("●", style={"color": PALETTE["accent2"], "fontSize": "14px", "marginRight": "8px", "textShadow": "0 0 12px rgba(85, 239, 196, 0.9)"}),
                    html.Span(BANNER_TEXT, style={"fontWeight": "700", "letterSpacing": "1px"}),
                ],
                style={
                    "position": "sticky",
                    "top": "0",
                    "zIndex": "10000",
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "padding": "10px 12px",
                    "borderRadius": "12px",
                    "border": f"1px solid {PALETTE['accent']}99",
                    "background": "linear-gradient(90deg, rgba(0, 212, 255, 0.18) 0%, rgba(85, 239, 196, 0.18) 50%, rgba(0, 212, 255, 0.18) 100%)",
                    "boxShadow": "0 0 22px rgba(0, 212, 255, 0.18)",
                    "marginBottom": "12px",
                    "fontSize": "13px",
                },
            ),
            html.Div(
                [
                    html.Div("Renaissance-Technologies", style={"fontWeight": "700", "letterSpacing": "1.8px", "fontSize": "13px"}),
                    html.Div("CTA Command Deck", style={"fontSize": "11px", "opacity": "0.86", "marginTop": "2px"}),
                    html.Div(f"GUI Version {UI_VERSION}", style={"fontSize": "11px", "marginTop": "3px"}),
                ],
                style={
                    "position": "fixed",
                    "top": "14px",
                    "right": "16px",
                    "zIndex": "9999",
                    "padding": "9px 12px",
                    "borderRadius": "10px",
                    "border": f"1px solid {PALETTE['accent']}88",
                    "background": "rgba(4, 10, 24, 0.9)",
                    "boxShadow": "0 0 26px rgba(0, 212, 255, 0.25)",
                    "color": PALETTE["accent"],
                    "textAlign": "right",
                },
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Renaissance-Technologies", style={"fontSize": "14px", "color": PALETTE["accent"], "letterSpacing": "2px"}),
                            html.H2("SA Intraday CTA Command Center", style={"margin": "6px 0 2px 0", "fontWeight": "700"}),
                            html.Div(f"Database: {db_file}", style={"color": PALETTE["subtext"], "fontSize": "12px"}),
                            html.Div(f"Launch: {launch_stamp}", style={"color": PALETTE["subtext"], "fontSize": "12px", "marginTop": "2px"}),
                            html.Div(f"Fingerprint: {ui_fingerprint}", style={"color": PALETTE["accent2"], "fontSize": "11px", "marginTop": "4px"}),
                        ]
                    ),
                ],
                style={
                    "padding": "18px 22px",
                    "borderRadius": "14px",
                    "border": f"1px solid {PALETTE['accent']}44",
                    "background": "linear-gradient(120deg, #0a1530 0%, #0f223f 60%, #102947 100%)",
                    "boxShadow": "0 0 40px rgba(0, 212, 255, 0.12)",
                },
            ),
            html.Div(
                [
                    _card("LATEST RUN", "kpi_run_id"),
                    _card("TOTAL RETURN", "kpi_total_return"),
                    _card("SHARPE", "kpi_sharpe"),
                    _card("FILL COUNT", "kpi_fill_count"),
                    _card("IS (BPS)", "kpi_is_bps"),
                ],
                style={"display": "flex", "gap": "10px", "flexWrap": "wrap", "marginTop": "12px"},
            ),
            dcc.Interval(id="refresh", interval=15 * 1000, n_intervals=0),
            dcc.Tabs(
                [
                    dcc.Tab(
                        label="Strategy & Risk",
                        className="rt-tab",
                        selected_className="rt-tab-selected",
                        children=[
                            dcc.Graph(id="equity_curve"),
                            dcc.Graph(id="drawdown_curve"),
                            dcc.Graph(id="position_curve"),
                            dcc.Graph(id="daily_pnl"),
                        ],
                        style={
                            "backgroundColor": PALETTE["panel"],
                            "color": PALETTE["text"],
                            "padding": "12px 16px",
                            "border": f"1px solid {PALETTE['accent']}22",
                        },
                        selected_style={
                            "backgroundColor": PALETTE["card"],
                            "color": PALETTE["accent"],
                            "padding": "12px 16px",
                            "borderTop": f"2px solid {PALETTE['accent']}",
                            "fontWeight": "700",
                        },
                    ),
                    dcc.Tab(
                        label="Execution & TCA",
                        className="rt-tab",
                        selected_className="rt-tab-selected",
                        children=[
                            dcc.Graph(id="tca_cost"),
                            dcc.Graph(id="arrival_by_hour"),
                            dcc.Graph(id="is_decomposition"),
                            dcc.Graph(id="benchmark_panel"),
                        ],
                        style={
                            "backgroundColor": PALETTE["panel"],
                            "color": PALETTE["text"],
                            "padding": "12px 16px",
                            "border": f"1px solid {PALETTE['accent']}22",
                        },
                        selected_style={
                            "backgroundColor": PALETTE["card"],
                            "color": PALETTE["accent"],
                            "padding": "12px 16px",
                            "borderTop": f"2px solid {PALETTE['accent']}",
                            "fontWeight": "700",
                        },
                    ),
                    dcc.Tab(
                        label="Pre/Intra Trade",
                        className="rt-tab",
                        selected_className="rt-tab-selected",
                        children=[
                            dcc.Graph(id="pretrade_panel"),
                            dcc.Graph(id="intraday_panel"),
                            dcc.Graph(id="execution_flow"),
                        ],
                        style={
                            "backgroundColor": PALETTE["panel"],
                            "color": PALETTE["text"],
                            "padding": "12px 16px",
                            "border": f"1px solid {PALETTE['accent']}22",
                        },
                        selected_style={
                            "backgroundColor": PALETTE["card"],
                            "color": PALETTE["accent"],
                            "padding": "12px 16px",
                            "borderTop": f"2px solid {PALETTE['accent']}",
                            "fontWeight": "700",
                        },
                    ),
                ],
                className="rt-tabs",
                style={"marginTop": "14px"},
            ),
        ],
        style={
            "maxWidth": "1400px",
            "margin": "0 auto",
            "padding": "16px",
            "background": "radial-gradient(circle at 20% 0%, #0f1e35 0%, #04070f 45%, #02040b 100%)",
            "color": PALETTE["text"],
            "minHeight": "100vh",
            "fontFamily": "'Segoe UI', 'Noto Sans', sans-serif",
        },
    )

    def _build_view_model() -> Dict[str, object]:
        eq = _read_table(db_file, "equity_curve")
        strategy = _read_table(db_file, "strategy_summary")
        execution = _read_table(db_file, "execution_summary")
        tca_summary = _read_table(db_file, "tca_summary")
        tca_by_hour = _read_table(db_file, "tca_by_hour")
        tca_pre = _read_table(db_file, "tca_pre_trade")
        tca_intra = _read_table(db_file, "tca_intra_day")
        tca_post = _read_table(db_file, "tca_post_trade")
        tca_kpis = _read_table(db_file, "tca_kpis")
        fills = _read_table(db_file, "fills")
        orders = _read_table(db_file, "orders")

        run_id = _latest_run_id(strategy, eq)
        eq = _filter_run(eq, run_id)
        strategy = _filter_run(strategy, run_id)
        execution = _filter_run(execution, run_id)
        tca_summary = _filter_run(tca_summary, run_id)
        tca_by_hour = _filter_run(tca_by_hour, run_id)
        tca_pre = _filter_run(tca_pre, run_id)
        tca_intra = _filter_run(tca_intra, run_id)
        tca_post = _filter_run(tca_post, run_id)
        tca_kpis = _filter_run(tca_kpis, run_id)
        fills = _filter_run(fills, run_id)
        orders = _filter_run(orders, run_id)

        if eq.empty:
            empty = _empty_fig("No data available. Run pipeline first.")
            return {
                "run_id": "N/A",
                "total_return": "-",
                "sharpe": "-",
                "fill_count": "-",
                "is_bps": "-",
                "fig_eq": empty,
                "fig_dd": empty,
                "fig_pos": empty,
                "fig_daily": empty,
                "fig_tca_cost": empty,
                "fig_arrival_hour": empty,
                "fig_is": empty,
                "fig_bench": empty,
                "fig_pre": empty,
                "fig_intra": empty,
                "fig_flow": empty,
            }

        eq["ts"] = pd.to_datetime(eq["ts"])
        eq = eq.sort_values("ts")

        equity_day = eq.groupby("trade_day", as_index=False)["equity"].last()
        total_return = float(equity_day["equity"].iloc[-1] / max(equity_day["equity"].iloc[0], 1e-12) - 1.0)
        day_ret = equity_day["equity"].pct_change().dropna()
        sharpe = float(np.sqrt(252.0) * day_ret.mean() / day_ret.std(ddof=0)) if len(day_ret) > 1 and float(day_ret.std(ddof=0)) > 0 else 0.0

        fill_count = int(execution["fill_count"].astype(float).iloc[-1]) if not execution.empty and "fill_count" in execution.columns else int(len(fills))
        is_bps = (
            float(tca_kpis["implementation_shortfall_bps_mean"].astype(float).iloc[-1])
            if not tca_kpis.empty and "implementation_shortfall_bps_mean" in tca_kpis.columns
            else (float(tca_post["implementation_shortfall_bps"].astype(float).mean()) if not tca_post.empty else 0.0)
        )

        fig_eq = px.line(eq, x="ts", y="equity", title="Equity Curve")
        fig_dd = px.line(eq, x="ts", y="drawdown", title="Drawdown Curve")
        fig_pos = px.line(eq, x="ts", y="position", title="Position Timeline")
        daily = eq.groupby("trade_day", as_index=False)["pnl_net"].sum()
        fig_daily = px.bar(daily, x="trade_day", y="pnl_net", title="Daily PnL")

        if tca_summary.empty:
            fig_tca_cost = _empty_fig("TCA Cost Decomposition")
        else:
            fig_tca_cost = px.bar(
                tca_summary,
                x="direction",
                y=["total_spread_cost", "total_slippage_cost", "total_impact_cost", "total_fee"],
                barmode="group",
                title="TCA Cost Decomposition by Direction",
            )

        if tca_by_hour.empty:
            fig_arrival_hour = _empty_fig("Arrival Cost by Hour")
        else:
            fig_arrival_hour = px.line(
                tca_by_hour,
                x="hour",
                y="avg_arrival_cost_bps",
                markers=True,
                title="Arrival Cost (bps) by Hour",
            )

        if tca_post.empty:
            fig_is = _empty_fig("Implementation Shortfall Decomposition")
            fig_bench = _empty_fig("Execution Benchmark Panel")
        else:
            decomp = pd.DataFrame(
                {
                    "component": ["delay", "execution", "fixed_fee", "opportunity"],
                    "value_bps": [
                        float(tca_post["delay_cost_bps"].astype(float).mean()),
                        float(tca_post["execution_cost_bps"].astype(float).mean()),
                        float(tca_post["fixed_fee_bps"].astype(float).mean()),
                        float(tca_post["opportunity_cost_bps"].astype(float).mean()),
                    ],
                }
            )
            fig_is = px.bar(decomp, x="component", y="value_bps", title="IS Decomposition (Mean bps)")

            fig_bench = px.scatter(
                tca_post,
                x="rpm",
                y="implementation_shortfall_bps",
                color="direction",
                hover_data=["vwap_cost_bps", "tca_zscore"],
                title="Benchmark Panel: RPM vs IS",
            )

        if tca_pre.empty:
            fig_pre = _empty_fig("Pre-trade Analysis")
        else:
            fig_pre = px.scatter(
                tca_pre,
                x="timing_risk_bps",
                y="predicted_total_cost_bps",
                color="recommended_algo",
                size="order_qty",
                title="Pre-trade: Timing Risk vs Predicted Cost",
            )

        if tca_intra.empty:
            fig_intra = _empty_fig("Intra-day Adaptive Analysis")
        else:
            fig_intra = go.Figure()
            fig_intra.add_trace(
                go.Scatter(
                    x=pd.to_datetime(tca_intra["minute"]),
                    y=tca_intra["arrival_cost_bps"],
                    mode="lines",
                    name="Arrival Cost (bps)",
                    line={"color": PALETTE["accent"]},
                )
            )
            if "spread_bp_median" in tca_intra.columns:
                fig_intra.add_trace(
                    go.Scatter(
                        x=pd.to_datetime(tca_intra["minute"]),
                        y=tca_intra["spread_bp_median"],
                        mode="lines",
                        name="Spread (bps)",
                        line={"color": PALETTE["accent2"]},
                    )
                )
            fig_intra.update_layout(title="Intra-day Adaptive Signals")

        if not fills.empty:
            fills["ts"] = pd.to_datetime(fills["ts"])
            fills["hour"] = fills["ts"].dt.strftime("%H:00")
            flow = fills.groupby("hour", as_index=False).agg(fill_count=("qty", "count"), total_cost=("total_cost", "sum"))
            fig_flow = px.bar(flow, x="hour", y="total_cost", title="Execution Cost Flow by Hour")
        elif not orders.empty:
            orders["ts"] = pd.to_datetime(orders["ts"])
            orders["hour"] = orders["ts"].dt.strftime("%H:00")
            flow = orders.groupby("hour", as_index=False).agg(order_count=("qty", "count"))
            fig_flow = px.bar(flow, x="hour", y="order_count", title="Order Flow by Hour")
        else:
            fig_flow = _empty_fig("Execution Flow")

        figures = [
            fig_eq,
            fig_dd,
            fig_pos,
            fig_daily,
            fig_tca_cost,
            fig_arrival_hour,
            fig_is,
            fig_bench,
            fig_pre,
            fig_intra,
            fig_flow,
        ]

        for fig in figures:
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor=PALETTE["panel"],
                plot_bgcolor=PALETTE["panel"],
                font={"color": PALETTE["text"]},
                margin={"l": 40, "r": 20, "t": 50, "b": 40},
            )

        return {
            "run_id": run_id if run_id else "N/A",
            "total_return": f"{total_return * 100.0:.2f}%",
            "sharpe": f"{sharpe:.2f}",
            "fill_count": str(fill_count),
            "is_bps": f"{is_bps:.2f}",
            "fig_eq": fig_eq,
            "fig_dd": fig_dd,
            "fig_pos": fig_pos,
            "fig_daily": fig_daily,
            "fig_tca_cost": fig_tca_cost,
            "fig_arrival_hour": fig_arrival_hour,
            "fig_is": fig_is,
            "fig_bench": fig_bench,
            "fig_pre": fig_pre,
            "fig_intra": fig_intra,
            "fig_flow": fig_flow,
        }

    view_model_lock = Lock()
    view_model_cache: Dict[str, object] = {"interval": -1, "value": None}

    def _fallback_view_model() -> Dict[str, object]:
        return {
            "run_id": "N/A",
            "total_return": "-",
            "sharpe": "-",
            "fill_count": "-",
            "is_bps": "-",
            "fig_eq": _empty_fig("Render fallback: check server log"),
            "fig_dd": _empty_fig("Render fallback: check server log"),
            "fig_pos": _empty_fig("Render fallback: check server log"),
            "fig_daily": _empty_fig("Render fallback: check server log"),
            "fig_tca_cost": _empty_fig("Render fallback: check server log"),
            "fig_arrival_hour": _empty_fig("Render fallback: check server log"),
            "fig_is": _empty_fig("Render fallback: check server log"),
            "fig_bench": _empty_fig("Render fallback: check server log"),
            "fig_pre": _empty_fig("Render fallback: check server log"),
            "fig_intra": _empty_fig("Render fallback: check server log"),
            "fig_flow": _empty_fig("Render fallback: check server log"),
        }

    def _get_view_model(refresh_counter: int) -> Dict[str, object]:
        with view_model_lock:
            cached_interval = view_model_cache.get("interval")
            cached_value = view_model_cache.get("value")
            if cached_interval == refresh_counter and isinstance(cached_value, dict):
                return cached_value

            try:
                view_model = _build_view_model()
            except Exception:
                app.logger.exception("Failed to build GUI view model")
                view_model = _fallback_view_model()

            view_model_cache["interval"] = refresh_counter
            view_model_cache["value"] = view_model
            return view_model

    @app.callback(
        Output("equity_curve", "figure"),
        Output("drawdown_curve", "figure"),
        Output("position_curve", "figure"),
        Output("daily_pnl", "figure"),
        Output("tca_cost", "figure"),
        Output("execution_flow", "figure"),
        Input("refresh", "n_intervals"),
    )
    def _refresh_primary(_: int):
        view_model = _get_view_model(_)
        return (
            view_model["fig_eq"],
            view_model["fig_dd"],
            view_model["fig_pos"],
            view_model["fig_daily"],
            view_model["fig_tca_cost"],
            view_model["fig_flow"],
        )

    @app.callback(
        Output("kpi_run_id", "children"),
        Output("kpi_total_return", "children"),
        Output("kpi_sharpe", "children"),
        Output("kpi_fill_count", "children"),
        Output("kpi_is_bps", "children"),
        Output("arrival_by_hour", "figure"),
        Output("is_decomposition", "figure"),
        Output("benchmark_panel", "figure"),
        Output("pretrade_panel", "figure"),
        Output("intraday_panel", "figure"),
        Input("refresh", "n_intervals"),
    )
    def _refresh_secondary(_: int):
        view_model = _get_view_model(_)
        return (
            view_model["run_id"],
            view_model["total_return"],
            view_model["sharpe"],
            view_model["fill_count"],
            view_model["is_bps"],
            view_model["fig_arrival_hour"],
            view_model["fig_is"],
            view_model["fig_bench"],
            view_model["fig_pre"],
            view_model["fig_intra"],
        )

    return app

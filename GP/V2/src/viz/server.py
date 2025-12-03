import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objs as go
import sqlite3
import pandas as pd
from src.core.kernel import CitySimulation
import threading
import time
import logging
import collections
import os

# Wipe log file on startup
if os.path.exists('simulation_trace.log'):
    try:
        os.remove('simulation_trace.log')
    except:
        pass

# Global Simulation Instance
SIM = CitySimulation()

# Set handler to capture logs in memory for the dashboard
log_capture_string = collections.deque(maxlen=100) # Keep last 100 logs
# Also write to a persistent file
file_handler = logging.FileHandler('simulation_trace.log', mode='a') # Append mode now since we wiped at start
file_handler.setFormatter(logging.Formatter('%(message)s'))

class DashLogHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        if "[OS-TRACE]" not in log_entry:
            log_entry = f"[{time.time():.4f}] {record.levelname:<8} | {record.threadName:<15} | {log_entry}"
        log_capture_string.append(log_entry)
        file_handler.emit(record) # Write to file as well

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = DashLogHandler()
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

import src.core.buffer
import src.data.database

def captured_os_trace(msg):
    entry = f"[OS-TRACE] {time.time():.4f} | {threading.current_thread().name:<15} | {msg}"
    print(entry)
    log_capture_string.append(entry)
    # Write to file manually
    with open('simulation_trace.log', 'a') as f:
        f.write(entry + '\n')

src.core.buffer.os_trace = captured_os_trace
src.data.database.os_trace = captured_os_trace


app = dash.Dash(__name__, title="OS City V2 Control")

app.layout = html.Div([
    html.H1("OS City V2: Process & Concurrency Monitor"),
    
    html.Div([
        html.Button("Start Simulation", id="btn-start", n_clicks=0),
        html.Button("Stop Simulation", id="btn-stop", n_clicks=0),
        html.Button("Toggle Power Outage", id="btn-scenario", n_clicks=0, style={"marginLeft": "10px", "backgroundColor": "#ffcccc"}),
        html.A(html.Button("Download Trace Log"), href="/download/log", target="_blank", style={"marginLeft": "10px"}),
        html.Div(id="status-display", style={"display": "inline-block", "marginLeft": "20px"})
    ], style={"marginBottom": "20px"}),
    
    html.Div([
        html.Div([
            html.H3("System Logs (Live OS Trace)"),
            html.Div(
                id="log-display",
                style={
                    "height": "300px",
                    "overflowY": "scroll",
                    "backgroundColor": "#1e1e1e",
                    "color": "#00ff00",
                    "fontFamily": "monospace",
                    "padding": "10px",
                    "fontSize": "12px",
                    "borderRadius": "5px",
                    "border": "1px solid #333"
                }
            )
        ], style={"width": "48%", "display": "inline-block", "verticalAlign": "top", "marginRight": "2%"}),
        
        html.Div([
            html.H3("1. System Latency (Context Switch & CPU Load)"),
            dcc.Graph(id="perf-graph", style={"height": "300px"}),
        ], style={"width": "48%", "display": "inline-block", "verticalAlign": "top", "border": "1px solid #ddd", "padding": "5px", "borderRadius": "5px"}),
    ], style={"marginBottom": "20px"}),

    # Row 2
    html.Div([
        html.Div([
            html.H3("2. IPC Buffer Health"),
            dcc.Graph(id="queue-graph", style={"height": "250px"}),
        ], style={"width": "32%", "display": "inline-block", "border": "1px solid #ddd", "padding": "5px", "marginRight": "1%"}),
        
        html.Div([
            html.H3("3. Throughput & Load Shedding"),
            dcc.Graph(id="throughput-graph", style={"height": "250px"}),
        ], style={"width": "32%", "display": "inline-block", "border": "1px solid #ddd", "padding": "5px", "marginRight": "1%"}),
        
        html.Div([
            html.H3("4. Water Subsystem"),
            dcc.Graph(id="water-graph", style={"height": "250px"}),
        ], style={"width": "32%", "display": "inline-block", "border": "1px solid #ddd", "padding": "5px"}),
    ], style={"marginBottom": "20px"}),
    
    # Row 3
    html.Div([
        html.Div([
            html.H3("5. Traffic Subsystem"),
            dcc.Graph(id="traffic-graph", style={"height": "250px"}),
        ], style={"width": "49%", "display": "inline-block", "border": "1px solid #ddd", "padding": "5px", "marginRight": "1%"}),
        
        html.Div([
            html.H3("6. Energy Subsystem"),
            dcc.Graph(id="energy-graph", style={"height": "250px"}),
        ], style={"width": "49%", "display": "inline-block", "border": "1px solid #ddd", "padding": "5px"}),
    ]),
    
    html.Div([
        html.H3("Scenario Timeline"),
        html.Div(id="scenario-display")
    ]),
    
    dcc.Interval(id="poll-interval", interval=1000, n_intervals=0),
    dcc.Interval(id="log-interval", interval=500, n_intervals=0) # Faster poll for logs
])

server = app.server
from flask import send_file
@server.route("/download/log")
def download_log():
    try:
        return send_file('simulation_trace.log', as_attachment=True)
    except Exception as e:
        return str(e)

@app.callback(
    Output("log-display", "children"),
    [Input("log-interval", "n_intervals")]
)
def update_logs(n):
    # Return the last N lines joined by <br>
    logs = list(log_capture_string)
    return [html.Div(line) for line in reversed(logs)]

@app.callback(
    [Output("status-display", "children"),
     Output("perf-graph", "figure"),
     Output("queue-graph", "figure"),
     Output("throughput-graph", "figure"),
     Output("water-graph", "figure"),
     Output("traffic-graph", "figure"),
     Output("energy-graph", "figure"),
     Output("scenario-display", "children")],
    [Input("poll-interval", "n_intervals"),
     Input("btn-start", "n_clicks"),
     Input("btn-stop", "n_clicks"),
     Input("btn-scenario", "n_clicks")]
)
def update_dashboard(n, start_clicks, stop_clicks, scenario_clicks):
    ctx = dash.callback_context
    if ctx.triggered:
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        if button_id == "btn-start":
            SIM.bootstrap()
            SIM.start()
        elif button_id == "btn-stop":
            SIM.stop()
        elif button_id == "btn-scenario":
            SIM.toggle_scenario("PowerOutage")
            
    status = "Running" if SIM.running.is_set() else "Stopped"
    scenario = SIM.active_scenario if SIM.active_scenario else "Normal Operations"
    
    conn = sqlite3.connect(str(SIM.logger.db_path), check_same_thread=False)
    
    run_start_mono = 0.0
    try:
        cursor = conn.execute("SELECT min(ts_mono) FROM ticks WHERE run_id = ?", (SIM.logger.run_id,))
        row = cursor.fetchone()
        if row and row[0] is not None:
            run_start_mono = row[0]
    except:
        pass

    # 1. Performance Query
    try:
        perf_df = pd.read_sql_query("""
            SELECT subsystem, seq, latency_ms, work_ms as work_time_ms, ts_mono
            FROM ticks 
            WHERE run_id = ? 
            ORDER BY ts_mono DESC LIMIT 500
        """, conn, params=(SIM.logger.run_id,))
        perf_df = perf_df.sort_values('ts_mono')
        if not perf_df.empty and run_start_mono > 0:
            perf_df['ts_rel'] = perf_df['ts_mono'] - run_start_mono
        else:
            perf_df['ts_rel'] = perf_df['ts_mono']
    except Exception as e:
        perf_df = pd.DataFrame(columns=["subsystem", "seq", "latency_ms", "work_time_ms", "ts_mono", "ts_rel"])

    try:
        queue_df = pd.read_sql_query("""
            SELECT queue_name, size, capacity, dropped, ts_mono
            FROM queue_stats
            WHERE run_id = ?
            ORDER BY ts_mono DESC LIMIT 500
        """, conn, params=(SIM.logger.run_id,))
        queue_df = queue_df.sort_values('ts_mono')
        if not queue_df.empty and run_start_mono > 0:
            queue_df['ts_rel'] = queue_df['ts_mono'] - run_start_mono
        else:
            queue_df['ts_rel'] = queue_df['ts_mono']
    except:
        queue_df = pd.DataFrame(columns=["queue_name", "size", "capacity", "dropped", "ts_mono", "ts_rel"])

    # 3. Metrics Query
    try:
        metrics_df = pd.read_sql_query("""
            SELECT subsystem, payload, ts_mono
            FROM metrics
            WHERE run_id = ?
            ORDER BY ts_mono DESC LIMIT 500
        """, conn, params=(SIM.logger.run_id,))
        metrics_df = metrics_df.sort_values('ts_mono')
        
        if not metrics_df.empty:
            import json
            payload_data = metrics_df['payload'].apply(json.loads).apply(pd.Series)
            metrics_df = pd.concat([metrics_df.drop(['payload'], axis=1), payload_data], axis=1)
            
            if run_start_mono > 0:
                metrics_df['ts_rel'] = metrics_df['ts_mono'] - run_start_mono
            else:
                metrics_df['ts_rel'] = metrics_df['ts_mono']
    except:
        metrics_df = pd.DataFrame()
        
    conn.close()
    

    # Graph 1: Latency
    perf_fig = go.Figure()
    SUBSYSTEM_COLORS = {"Traffic": "#1f77b4", "Energy": "#d62728", "Water": "#2ca02c", "Kernel": "#7f7f7f"}
    
    for sub in perf_df['subsystem'].unique():
        df_sub = perf_df[perf_df['subsystem'] == sub]
        color = SUBSYSTEM_COLORS.get(sub, "#333333")
        perf_fig.add_trace(go.Scatter(
            x=df_sub['ts_rel'], y=df_sub['latency_ms'], 
            mode='lines+markers', name=f"{sub} Latency",
            line=dict(color=color), marker=dict(color=color)
        ))
    perf_fig.update_layout(margin=dict(l=30, r=30, t=30, b=30), height=300)
    
    # Graph 2: Queue
    queue_fig = go.Figure()
    if not queue_df.empty:
        queue_fig.add_trace(go.Scatter(x=queue_df['ts_rel'], y=queue_df['size'], mode='lines', name="Queue Size", fill='tozeroy'))
        queue_fig.add_trace(go.Scatter(x=queue_df['ts_rel'], y=queue_df['capacity'], mode='lines', name="Capacity", line=dict(dash='dash', color='red')))
    queue_fig.update_layout(margin=dict(l=30, r=30, t=30, b=30), height=250)

    # Graph 3: Throughput
    tp_fig = go.Figure()
    if not metrics_df.empty:
        energy_df = metrics_df[metrics_df['subsystem'] == 'Energy']
        if 'requests_processed' in energy_df.columns:
             tp_fig.add_trace(go.Scatter(x=energy_df['ts_rel'], y=energy_df['requests_processed'], mode='lines', name="Processed", line=dict(color='green')))
        if 'event' in metrics_df.columns:
            drop_df = metrics_df[metrics_df['event'] == 'ev_req_dropped']
            if not drop_df.empty:
                tp_fig.add_trace(go.Scatter(x=drop_df['ts_rel'], y=[1]*len(drop_df), mode='markers', name="Drop", marker=dict(color='red', symbol='x', size=10)))
    tp_fig.update_layout(margin=dict(l=30, r=30, t=30, b=30), height=250)

    # Graph 4: Water
    water_fig = go.Figure()
    water_perf = perf_df[perf_df['subsystem'] == 'Water']
    if not metrics_df.empty and 'subsystem' in metrics_df.columns:
        water_df = metrics_df[metrics_df['subsystem'] == 'Water']
        if not water_df.empty:
            if 'pending_requests' in water_df.columns:
                 water_fig.add_trace(go.Scatter(x=water_df['ts_rel'], y=water_df['pending_requests'], mode='lines', name="Queue", line=dict(dash='dot', color='red')))
            if 'reservoir_level' in water_df.columns:
                water_fig.add_trace(go.Scatter(x=water_df['ts_rel'], y=water_df['reservoir_level'], mode='lines', name="Level %", line=dict(color='blue')))
    if not water_perf.empty:
         water_fig.add_trace(go.Scatter(x=water_perf['ts_rel'], y=water_perf['work_time_ms'], mode='lines', name="CPU", yaxis="y2", fill='tozeroy', line=dict(color='rgba(0, 255, 0, 0.3)')))
    water_fig.update_layout(yaxis2=dict(overlaying="y", side="right", showgrid=False), margin=dict(l=30, r=30, t=30, b=30), height=250, legend=dict(orientation="h", y=1.1))

    # Graph 5: Traffic
    traffic_fig = go.Figure()
    if not metrics_df.empty and 'subsystem' in metrics_df.columns:
        traffic_df = metrics_df[metrics_df['subsystem'] == 'Traffic']
        if not traffic_df.empty:
             traffic_clean = traffic_df.dropna(subset=['congestion', 'generated_requests'])
             if not traffic_clean.empty:
                 traffic_fig.add_trace(go.Scatter(x=traffic_clean['ts_rel'], y=traffic_clean['congestion'], mode='lines', name="Congestion", line=dict(color='orange')))
                 traffic_fig.add_trace(go.Bar(x=traffic_clean['ts_rel'], y=traffic_clean['generated_requests'], name="Reqs", yaxis="y2", marker=dict(color='rgba(100, 100, 100, 0.5)')))
    traffic_fig.update_layout(yaxis2=dict(overlaying="y", side="right", showgrid=False, range=[0, 6]), margin=dict(l=30, r=30, t=30, b=30), height=250)

    # Graph 6: Energy
    energy_fig = go.Figure()
    if not metrics_df.empty:
        energy_df = metrics_df[metrics_df['subsystem'] == 'Energy']
        if not energy_df.empty:
            energy_clean = energy_df.dropna(subset=['total_load_mw', 'ev_load_mw'])
            if not energy_clean.empty:
                if 'total_load_mw' in energy_clean.columns:
                    energy_fig.add_trace(go.Scatter(x=energy_clean['ts_rel'], y=energy_clean['total_load_mw'], mode='lines', name="Total", fill='tozeroy'))
                if 'ev_load_mw' in energy_clean.columns:
                    energy_fig.add_trace(go.Scatter(x=energy_clean['ts_rel'], y=energy_clean['ev_load_mw'], mode='lines', name="EV", yaxis="y2", line=dict(color='yellow')))
    energy_fig.update_layout(yaxis2=dict(overlaying="y", side="right", showgrid=False), margin=dict(l=30, r=30, t=30, b=30), height=250)

    return f"Status: {status} | Run ID: {SIM.logger.run_id}", perf_fig, queue_fig, tp_fig, water_fig, traffic_fig, energy_fig, f"Active Scenario: {scenario}"

def run_server():
    app.run(debug=True, use_reloader=False)

if __name__ == "__main__":
    run_server()

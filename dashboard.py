import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import time
import subprocess
import sys
import os
import random

st.set_page_config(
    page_title="RevGuard AI — Payment Recovery Command Center",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ RevGuard AI: Autonomous Payment Recovery Engine")
st.caption("Razorpay AI Buildathon — Track 03: AI Revenue Recovery")

API_URL = "http://localhost:8000/api/logs"
WEBHOOK_URL = "http://localhost:8000/webhook/razorpay"
RESET_URL = "http://localhost:8000/api/reset"

def is_backend_running():
    try:
        r = requests.get(API_URL, timeout=0.3)
        return r.status_code == 200
    except Exception:
        return False

backend_online = is_backend_running()

# --- SIDEBAR SERVER CONTROLS ---
st.sidebar.header("⚙️ Server Controls")

if backend_online:
    st.sidebar.success("🟢 Server: **ONLINE** (Port 8000)")
    if st.sidebar.button("⏹️ Stop Backend Server", use_container_width=True, type="secondary"):
        if os.name == 'nt':
            subprocess.run("for /f \"tokens=5\" %a in ('netstat -aon ^| findstr :8000') do taskkill /f /pid %a", shell=True, capture_output=True)
        time.sleep(1)
        st.rerun()
else:
    st.sidebar.error("🔴 Server: **OFFLINE**")
    if st.sidebar.button("▶️ Start Backend Server", use_container_width=True, type="primary"):
        target_file = "revguard_English.py" if os.path.exists("revguard_English.py") else "revguard_app.py"
        subprocess.Popen([sys.executable, target_file], creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
        with st.spinner("Starting server..."):
            for _ in range(10):
                time.sleep(0.4)
                if is_backend_running():
                    break
        st.rerun()

st.sidebar.divider()
st.sidebar.subheader("⚡ Live Simulation Bench")

# Clear / Reset Data button
if backend_online and st.sidebar.button("🗑️ Reset / Clear All Logs", use_container_width=True):
    try:
        requests.post(RESET_URL, timeout=1.0)
        st.sidebar.info("Logs reset.")
        time.sleep(0.3)
        st.rerun()
    except Exception:
        pass

# --- UI CONTAINERS ---
metrics_placeholder = st.empty()
st.divider()
charts_placeholder = st.empty()
table_placeholder = st.empty()
inspector_placeholder = st.empty()

def fetch_api_data():
    try:
        r = requests.get(API_URL, timeout=0.8)
        data = r.json()
        return data.get("metrics", {}), data.get("audit_trail", [])
    except Exception:
        return {}, []

def render_ui(metrics, logs):
    with metrics_placeholder.container():
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Incidents Handled", f"{metrics.get('total_incidents', 0)}")
        c2.metric("Total Failed Revenue", f"₹{metrics.get('total_failed_inr', 0):,.2f}")
        c3.metric("Revenue Recovered", f"₹{metrics.get('total_recovered_inr', 0):,.2f}", delta=f"{metrics.get('recovery_rate_pct', 0):.1f}%")
        c4.metric("Recovery Rate", f"{metrics.get('recovery_rate_pct', 0):.1f}%")

    if logs:
        df = pd.DataFrame(logs)
        with charts_placeholder.container():
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("📊 Root Cause Failure Distribution")
                fig_cat = px.pie(df, names="root_cause_category", hole=0.45, color_discrete_sequence=px.colors.qualitative.Safe)
                st.plotly_chart(fig_cat, use_container_width=True)
            with col2:
                st.subheader("🏦 Bank Degradation vs Volume")
                fig_bank = px.bar(df, x="bank", color="root_cause_category", barmode="group", color_discrete_sequence=px.colors.qualitative.Bold)
                st.plotly_chart(fig_bank, use_container_width=True)

        with table_placeholder.container():
            st.subheader("📋 Real-Time Recovery Audit Trail")
            st.dataframe(
                df[["timestamp", "payment_id", "order_id", "amount_inr", "bank", "root_cause_category", "status"]],
                use_container_width=True,
                height=280
            )

        with inspector_placeholder.container():
            st.subheader("💬 Localized Dispatch Inspector")
            last_item = df.iloc[-1]
            m1, m2 = st.columns(2)
            with m1:
                st.markdown(f"**Latest English Action (`{last_item.get('order_id')}`):**")
                st.info(last_item.get("dispatched_message_english", "N/A"))
            with m2:
                st.markdown(f"**Latest Hinglish Action (`{last_item.get('order_id')}`):**")
                st.success(last_item.get("dispatched_message_hinglish", "N/A"))

# Initial render
curr_metrics, curr_logs = fetch_api_data()
render_ui(curr_metrics, curr_logs)

# --- 50-BATCH LIVE STREAM BUTTON ---
if st.sidebar.button("🚀 Stream Live 50-Failure Batch", disabled=not backend_online, use_container_width=True):
    from simulate_50_failures import generate_failed_payload, generate_capture_payload
    
    progress_bar = st.sidebar.progress(0)
    status_box = st.sidebar.empty()
    orders_pool = []
    
    session = requests.Session()

    for i in range(1, 51):
        status_box.text(f"Processing incident #{i}/50...")
        payload, order_id, amt = generate_failed_payload(i)
        
        try:
            session.post(WEBHOOK_URL, json=payload, timeout=1.0)
            orders_pool.append((order_id, amt))
        except Exception:
            continue

        # Trigger simulated recovery conversions in real time (~45%)
        if random.random() < 0.45 and orders_pool:
            rec_order, rec_amt = random.choice(orders_pool)
            cap_payload = generate_capture_payload(rec_order, rec_amt)
            try:
                session.post(WEBHOOK_URL, json=cap_payload, timeout=1.0)
            except Exception:
                pass

        # Update UI every iteration smoothly
        m, l = fetch_api_data()
        render_ui(m, l)
        
        progress_bar.progress(i / 50)
        time.sleep(0.03)

    status_box.text("✅ All 50 transactions processed!")
    st.sidebar.balloons()

import streamlit as st
import sqlite3
import time
import json
from datetime import datetime, timezone
from pathlib import Path

APP_TITLE = "Pop Ant 🐜 — Clicker"
DB_PATH = Path("clicks.db")

st.set_page_config(page_title="Pop Ant Clicker", page_icon="🐜", layout="centered")

# ---------- Utilities ----------
def get_db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS ip_totals (
        ip TEXT PRIMARY KEY,
        count INTEGER NOT NULL DEFAULT 0,
        updated_at TIMESTAMP NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS click_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip TEXT,
        at TIMESTAMP NOT NULL,
        agent TEXT,
        note TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS meta (
        k TEXT PRIMARY KEY,
        v TEXT
    )""")
    # Ensure global total
    conn.execute("INSERT OR IGNORE INTO meta(k,v) VALUES('global_total','0')")
    conn.commit()
    return conn

def get_global_total(conn):
    cur = conn.execute("SELECT v FROM meta WHERE k='global_total'")
    row = cur.fetchone()
    return int(row[0]) if row else 0

def set_global_total(conn, value:int):
    conn.execute("UPDATE meta SET v=? WHERE k='global_total'", (str(value),))
    conn.commit()

def increment_counts(conn, ip:str|None, agent:str|None):
    # Global
    total = get_global_total(conn) + 1
    set_global_total(conn, total)
    # Per IP (nullable)
    if ip:
        conn.execute(
            "INSERT INTO ip_totals(ip,count,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(ip) DO UPDATE SET count=count+1, updated_at=excluded.updated_at",
            (ip, 1, datetime.now(timezone.utc).isoformat())
        )
    # Log
    conn.execute("INSERT INTO click_log(ip, at, agent, note) VALUES(?,?,?,?)",
                 (ip, datetime.now(timezone.utc).isoformat(), agent, "click"))
    conn.commit()
    return total

@st.cache_data(show_spinner=False)
def get_svg_bytes(name:str):
    fn = Path("assets")/name
    return fn.read_bytes()

def get_client_ip():
    # Preferred: via JS (streamlit_js_eval) set in session_state['client_ip']
    ip = st.session_state.get("client_ip")
    if ip:
        return ip

    # Fallback: Try Streamlit headers (works when reverse-proxy sets it and Streamlit exposes it)
    # WARNING: This is not officially supported in all deployments.
    try:
        from streamlit.web.server.websocket_headers import _get_websocket_headers
        hdrs = _get_websocket_headers()
        fwd = hdrs.get("X-Forwarded-For") or hdrs.get("x-forwarded-for")
        if fwd:
            # First IP in the chain is the client
            ip = fwd.split(",")[0].strip()
            return ip
    except Exception:
        pass

    # Last resort: anonymous per-session id
    return None

def display_leaderboard(conn, top_n=10):
    st.subheader("🏆 Top IPs")
    rows = conn.execute("SELECT ip, count FROM ip_totals ORDER BY count DESC LIMIT ?", (top_n,)).fetchall()
    if not rows:
        st.info("ยังไม่มีสถิติ นับก่อน!")
        return
    for i, (ip, cnt) in enumerate(rows, start=1):
        st.write(f"{i}. `{ip}` — **{cnt:,}**")

# ---------- UI ----------
st.title(APP_TITLE)
st.caption("มดอ้วนๆ ให้กดแล้วนับคะแนน และบันทึก IP แบบง่าย")

# Load SVGs
ant_closed = get_svg_bytes("ant-fat-closed.svg").decode("utf-8")
ant_open   = get_svg_bytes("ant-fat-open.svg").decode("utf-8")

# IP acquisition via JS (public IP). Requires internet outbound.
# If you don't want external calls, comment the block below.
with st.sidebar:
    st.header("📡 Your Info")
    st.write("พยายามตรวจจับ IP สาธารณะ…")
    ip_placeholder = st.empty()
    agent_placeholder = st.empty()
    # Show current session agent (basic)
    agent_placeholder.write(st.session_state.get("agent_str", ""))

# Inject a tiny JS to fetch public IP (ipify) + user agent
ip_js = """
async function getInfo(){
  try{
    const r = await fetch("https://api.ipify.org?format=json");
    const j = await r.json();
    const ip = j.ip;
    const agent = navigator.userAgent;
    return {ip, agent};
  }catch(e){
    return {ip:null, agent: navigator.userAgent};
  }
}
getInfo();
"""
try:
    from streamlit_js_eval import streamlit_js_eval
    info = streamlit_js_eval(js_expressions=ip_js, key="ip_js_call")
    if info and isinstance(info, dict):
        if info.get("ip"):
            st.session_state["client_ip"] = info["ip"]
        st.session_state["agent_str"] = info.get("agent","")
except Exception:
    # If component not installed, continue without JS
    pass

client_ip = get_client_ip()
if client_ip:
    ip_placeholder.write(f"IP: `{client_ip}`")
else:
    ip_placeholder.write("IP: ไม่ทราบ (จะบันทึกแบบ anonymous session)")

# Persistence
conn = get_db_conn()

# Session state for UI
if "ant_open" not in st.session_state:
    st.session_state["ant_open"] = False

# Center the ant + button
col = st.container()
with col:
    # Render SVG directly
    svg = ant_open if st.session_state["ant_open"] else ant_closed
    st.markdown(
        f"""
        <div style="text-align:center;">
          {svg}
        </div>
        """,
        unsafe_allow_html=True,
    )

    clicked = st.button("🐜 POP!", use_container_width=True, type="primary")
    if clicked:
        st.session_state["ant_open"] = not st.session_state["ant_open"]
        total = increment_counts(conn, client_ip, st.session_state.get("agent_str"))
        st.toast(f"Pop! รวมทั้งหมด {total:,}")
        # Small shake/animation hint: re-render then sleep
        time.sleep(0.08)
        st.session_state["ant_open"] = not st.session_state["ant_open"]

# Stats
with st.expander("📈 สถิติ"):
    total = get_global_total(conn)
    st.metric("ยอดกดทั้งหมด (Global)", f"{total:,}")
    if client_ip:
        row = conn.execute("SELECT count FROM ip_totals WHERE ip=?", (client_ip,)).fetchone()
        my = row[0] if row else 0
        st.metric("ของคุณ (ตาม IP)", f"{my:,}")
    display_leaderboard(conn, top_n=10)

st.caption("หมายเหตุ: การบันทึก IP ใช้ JS เรียกบริการสาธารณะ (ipify). หากปิดอินเทอร์เน็ตหรือบล็อกไว้ ระบบจะเก็บเป็น anonymous.")

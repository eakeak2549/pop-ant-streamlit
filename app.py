import streamlit as st
import sqlite3
import time
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
    total = get_global_total(conn) + 1
    set_global_total(conn, total)
    if ip:
        conn.execute(
            "INSERT INTO ip_totals(ip,count,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(ip) DO UPDATE SET count=count+1, updated_at=excluded.updated_at",
            (ip, 1, datetime.now(timezone.utc).isoformat())
        )
    conn.execute("INSERT INTO click_log(ip, at, agent, note) VALUES(?,?,?,?)",
                 (ip, datetime.now(timezone.utc).isoformat(), agent, "click"))
    conn.commit()
    return total

@st.cache_data(show_spinner=False)
def get_svg_text(name:str):
    return Path("assets")/name

def get_client_ip():
    ip = st.session_state.get("client_ip")
    if ip:
        return ip
    try:
        from streamlit.web.server.websocket_headers import _get_websocket_headers
        hdrs = _get_websocket_headers()
        fwd = hdrs.get("X-Forwarded-For") or hdrs.get("x-forwarded-for")
        if fwd:
            ip = fwd.split(",")[0].strip()
            return ip
    except Exception:
        pass
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
st.caption("มดแดงพุงอ้วน กลมเด้งได้ คลิกแล้วนับ + เก็บ IP")

# Basic CSS (center + belly bounce)
st.markdown("""
<style>
.ant-wrap { display:block; margin: 0 auto; text-align:center; }
#belly { transform-origin: 160px 205px; } /* center of belly ellipse */
.pop { animation: belly-pop 220ms ease-out 1; }
@keyframes belly-pop {
  0%   { transform: scale(1); }
  50%  { transform: scale(1.12); }
  100% { transform: scale(1); }
}
</style>
""", unsafe_allow_html=True)

# IP info (non-intrusive)
with st.sidebar:
    st.header("📡 Your Info")
    ip_placeholder = st.empty()
    agent_placeholder = st.empty()

ip_js = """
async function getInfo(){
  try{
    const r = await fetch("https://api.ipify.org?format=json");
    const j = await r.json();
    return {ip:j.ip, agent:navigator.userAgent};
  }catch(e){
    return {ip:null, agent:navigator.userAgent};
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
    pass

client_ip = get_client_ip()
if client_ip:
    ip_placeholder.write(f"IP: `{client_ip}`")
else:
    ip_placeholder.write("IP: ไม่ทราบ (anonymous)")

# DB
conn = get_db_conn()

# Session state
if "belly_pop" not in st.session_state:
    st.session_state["belly_pop"] = False

# Load SVGs (red ant)
ant_closed = Path("assets/ant-red-closed.svg").read_text(encoding="utf-8")
ant_open   = Path("assets/ant-red-open.svg").read_text(encoding="utf-8")

svg = ant_open if st.session_state["belly_pop"] else ant_closed
# Add 'pop' class to #belly when clicked previously to show the animation
if st.session_state["belly_pop"]:
    svg = svg.replace('id="belly"', 'id="belly" class="pop"')

# Render SVG centered (no stray HTML like </div>)
st.markdown(f'<div class="ant-wrap">{svg}</div>', unsafe_allow_html=True)

clicked = st.button("🐜 POP!", use_container_width=True, type="primary")
if clicked:
    # trigger animation and count
    st.session_state["belly_pop"] = True
    total = increment_counts(conn, client_ip, st.session_state.get("agent_str"))
    st.toast(f"Pop! รวมทั้งหมด {total:,}")
    # brief wait so users see the bounce
    time.sleep(0.08)
    st.session_state["belly_pop"] = False

with st.expander("📈 สถิติ"):
    total = get_global_total(conn)
    st.metric("ยอดกดทั้งหมด (Global)", f"{total:,}")
    if client_ip:
        row = conn.execute("SELECT count FROM ip_totals WHERE ip=?", (client_ip,)).fetchone()
        my = row[0] if row else 0
        st.metric("ของคุณ (ตาม IP)", f"{my:,}")
    display_leaderboard(conn, top_n=10)

st.caption("หมายเหตุ: ดึง Public IP ผ่าน ipify; ถ้าเรียกไม่ได้จะเก็บแบบ anonymous. HTML ถูกย่อให้ไม่มีแท็กหลงเหลือ (เช่น </div>).")

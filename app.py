
import streamlit as st
import sqlite3, time
from datetime import datetime, timezone
from pathlib import Path

APP_TITLE = "Pop Ant 🐜 — Click the Ant!"
DB_PATH = Path("clicks.db")

st.set_page_config(page_title="Pop Ant Clicker", page_icon="🐜", layout="centered")

# ---------- Utilities ----------
def get_db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS ip_totals (
        ip TEXT PRIMARY KEY,
        count INTEGER NOT NULL DEFAULT 0,
        updated_at TIMESTAMP NOT NULL
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS click_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip TEXT,
        at TIMESTAMP NOT NULL,
        agent TEXT,
        note TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS meta (
        k TEXT PRIMARY KEY,
        v TEXT
    )''')
    conn.execute("INSERT OR IGNORE INTO meta(k,v) VALUES('global_total','0')")
    conn.commit()
    return conn

def get_global_total(conn):
    row = conn.execute("SELECT v FROM meta WHERE k='global_total'").fetchone()
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

def get_client_ip():
    ip = st.session_state.get("client_ip")
    if ip:
        return ip
    try:
        from streamlit.web.server.websocket_headers import _get_websocket_headers
        hdrs = _get_websocket_headers()
        fwd = hdrs.get("X-Forwarded-For") or hdrs.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
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

# ---------- Styles ----------
st.markdown('''
<style>
.page { text-align:center; }
.ant-wrap { display:inline-block; cursor:pointer; user-select:none; }
#belly { transform-origin: 180px 245px; }
.pop { animation: belly-pop 220ms ease-out 1; }
@keyframes belly-pop {
  0%   { transform: scale(1); }
  50%  { transform: scale(1.14); }
  100% { transform: scale(1); }
}
</style>
''', unsafe_allow_html=True)

# ---------- Header ----------
st.title(APP_TITLE)
st.caption("คลิกที่ **ตัวมด** ได้เลย ไม่ต้องกดปุ่ม")

# ---------- IP via JS ----------
with st.sidebar:
    st.header("📡 Your Info")
    ip_placeholder = st.empty()
    agent_placeholder = st.empty()

ip_js = '''
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
'''
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

# ---------- DB ----------
conn = get_db_conn()

# ---------- Click routing via query param ----------
qp = st.query_params
clicked_token = qp.get("clicked", None)
last_token = st.session_state.get("last_clicked_token")
if clicked_token and clicked_token != last_token:
    st.session_state["last_clicked_token"] = clicked_token
    total = increment_counts(conn, client_ip, st.session_state.get("agent_str"))
    st.toast(f"Pop! รวมทั้งหมด {total:,}")
    qp.clear()
    st.rerun()

# ---------- SVGs (orange mascot-like ant) ----------
ant_closed = Path("assets/ant-orange-closed.svg").read_text(encoding="utf-8")
ant_open   = Path("assets/ant-orange-open.svg").read_text(encoding="utf-8")

# toggle class for pop animation
pop_state = st.session_state.get("animate", False)
svg = (ant_open if pop_state else ant_closed)
if pop_state:
    svg = svg.replace('id="belly"', 'id="belly" class="pop"')
st.session_state["animate"] = False

# ---------- Render clickable ANT ----------
html = f'''
<div class="page">
  <div class="ant-wrap" id="antWrap">
    {svg}
  </div>
</div>
<script>
  const ant = document.getElementById('antWrap');
  if (ant) {{
    ant.addEventListener('click', ()=>{{
      const u = new URL(window.location);
      u.searchParams.set('clicked', Date.now().toString());
      window.location.replace(u.toString());
    }});
  }}
</script>
'''
st.components.v1.html(html, height=540, scrolling=False)

with st.expander("📈 สถิติ"):
    total = get_global_total(conn)
    st.metric("ยอดกดทั้งหมด (Global)", f"{total:,}")
    if client_ip:
        row = conn.execute("SELECT count FROM ip_totals WHERE ip=?", (client_ip,)).fetchone()
        my = row[0] if row else 0
        st.metric("ของคุณ (ตาม IP)", f"{my:,}")
    display_leaderboard(conn, top_n=10)

st.caption("หมายเหตุ: คลิกที่ตัวมดโดยตรงเพื่อเพิ่มจำนวน ใช้ query param เพื่อแจ้งเหตุการณ์คลิกให้เซิร์ฟเวอร์.")

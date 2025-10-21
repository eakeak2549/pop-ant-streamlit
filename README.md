
# Pop Ant 🐜 (Streamlit)

เกมคลิกเกอร์สไตล์ PopCat เวอร์ชัน "มดตัวอ้วนๆ" ทำด้วย Streamlit

## คุณสมบัติ
- คลิกปุ่มเพื่อสลับภาพมด (ปากปิด/อ้า) และนับคะแนน
- เก็บสถิติจำนวนคลิกรวม (global)
- เก็บสถิติตาม IP (ต้องการอินเทอร์เน็ตขาออกเพื่อเรียก ipify)
- บันทึก log รายการคลิกลง SQLite (`clicks.db`)
- Leaderboard IP อันดับสูงสุด
- ไม่ต้องมีเซิร์ฟเวอร์แยก ใช้ไฟล์ db ในโฟลเดอร์เดียวกับแอป

## การติดตั้ง
```bash
pip install streamlit streamlit-js-eval
```

## การรัน
```bash
streamlit run app.py
```

## หมายเหตุเรื่อง IP
- โค้ดใช้ component `streamlit-js-eval` เรียก JS เพื่อดึง Public IP ผ่านบริการ `https://api.ipify.org`  
  หากสภาพแวดล้อมไม่มีอินเทอร์เน็ตหรือบล็อก external call ระบบจะเก็บแบบ anonymous (ไม่ทราบ IP)
- ในบางโฮสต์อาจมี Header `X-Forwarded-For` ให้ใช้เป็น fallback ได้ (โค้ดมีให้แล้ว แต่ไม่รับประกันทุกที่)

## โครงสร้างตาราง
- `meta(k TEXT PRIMARY KEY, v TEXT)` — เก็บค่า `global_total`
- `ip_totals(ip TEXT PRIMARY KEY, count INT, updated_at TIMESTAMP)` — ยอดคลิกต่อ IP
- `click_log(id INTEGER PK, ip TEXT, at TIMESTAMP, agent TEXT, note TEXT)` — รายการคลิก


## ใหม่ในรุ่น Red Belly
- เปลี่ยนเป็นมดแดงพุงกลม อนิเมชันพุงเด้งเมื่อคลิก
- แก้ปัญหาแท็ก `</div>` ปรากฏบนจอ โดยปรับการเรนเดอร์ HTML

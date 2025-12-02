import streamlit as st
import ccxt
import time
import os
import sqlite3
import concurrent.futures
from datetime import datetime, timedelta
from dotenv import load_dotenv

# === 0. 基础配置 ===
load_dotenv()
st.set_page_config(page_title="VibeTrader (Time Loop)", layout="wide", page_icon="⏳")
DB_FILE = "bot_state_time.db" # 换个数据库文件名，避免跟之前的冲突

# === 1. 数据库管理 (持久化) ===
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # 状态表：增加了 last_action_time 用于记录上次动作的时间
    c.execute('''CREATE TABLE IF NOT EXISTS bot_state
                 (id INTEGER PRIMARY KEY, status TEXT, direction TEXT, 
                  amount REAL, open_time TEXT)''')
    c.execute("SELECT count(*) FROM bot_state")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO bot_state VALUES (1, 'EMPTY', 'NONE', 0.0, '')")
        conn.commit()
    conn.close()

def get_state():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM bot_state WHERE id=1")
    row = c.fetchone()
    conn.close()
    return {
        "status": row[1],       # 'EMPTY' or 'HOLDING'
        "direction": row[2],
        "amount": row[3],
        "open_time": row[4]     # 记录开仓那一刻的时间字符串
    }

def update_state(status, direction, amount, open_time):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE bot_state SET status=?, direction=?, amount=?, open_time=? WHERE id=1",
              (status, direction, amount, open_time))
    conn.commit()
    conn.close()

init_db()

# === 2. 交易所连接 (含防 429 优化) ===
@st.cache_resource
def init_exchanges():
    exchanges = {}
    bp_key = os.getenv("BP_API_KEY")
    bp_secret = os.getenv("BP_SECRET")
    hl_private = os.getenv("HL_PRIVATE_KEY")
    hl_address = os.getenv("HL_WALLET_ADDRESS")

    # Backpack
    if bp_key and bp_secret:
        exchanges['bp'] = ccxt.backpack({'apiKey': bp_key, 'secret': bp_secret, 'enableRateLimit': True})
    else:
        exchanges['bp'] = ccxt.backpack({'enableRateLimit': True})

    # Hyperliquid
    if hl_private:
        exchanges['hl'] = ccxt.hyperliquid({'walletAddress': hl_address, 'privateKey': hl_private, 'enableRateLimit': True})
    else:
        exchanges['hl'] = ccxt.hyperliquid({'enableRateLimit': True})
    
    # 预加载市场信息 (防 429)
    try:
        exchanges['bp'].load_markets()
        exchanges['hl'].load_markets()
    except Exception as e:
        print(f"Market load error: {e}")

    return exchanges

exchanges = init_exchanges()
backpack = exchanges['bp']
hyperliquid = exchanges['hl']

# === 3. 交易核心逻辑 ===
def place_order_safe(exchange, symbol, side, amount, is_real):
    if not is_real:
        return {"id": f"sim_{int(time.time()*1000)}"}
    return exchange.create_order(symbol, 'market', side, amount)

def execute_dual_trade(direction, amount, symbol_bp, symbol_hl, is_real):
    """双向开单/平仓通用函数"""
    # direction 格式: "Long_BP_Short_HL" (开仓用) 或 "Close_Long_BP..." (平仓用)
    # 这里我们只根据 Buy/Sell 逻辑来解析
    
    # 解析 BP 方向
    if "Long_BP" in direction: side_bp = 'buy'
    elif "Short_BP" in direction: side_bp = 'sell'
    else: side_bp = 'buy' # fallback
    
    # 解析 HL 方向
    if "Long_HL" in direction: side_hl = 'buy'
    elif "Short_HL" in direction: side_hl = 'sell'
    else: side_hl = 'sell' # fallback

    log_msgs = []
    success = False

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_bp = executor.submit(place_order_safe, backpack, symbol_bp, side_bp, amount, is_real)
        future_hl = executor.submit(place_order_safe, hyperliquid, symbol_hl, side_hl, amount, is_real)
        
        res_bp, res_hl = None, None
        err_bp, err_hl = None, None

        try: res_bp = future_bp.result()
        except Exception as e: err_bp = str(e)
        
        try: res_hl = future_hl.result()
        except Exception as e: err_hl = str(e)

    if res_bp and res_hl:
        success = True
        log_msgs.append(f"✅ 双边成交! BP:{res_bp['id']} | HL:{res_hl['id']}")
    elif err_bp and err_hl:
        success = False
        log_msgs.append(f"❌ 双边失败。BP Err: {err_bp} | HL Err: {err_hl}")
    else:
        # 单边成交回滚逻辑
        success = False
        log_msgs.append("🚨 单边成交！执行回滚平仓...")
        if res_bp and not res_hl:
            try:
                rb_side = 'sell' if side_bp == 'buy' else 'buy'
                if is_real: backpack.create_order(symbol_bp, 'market', rb_side, amount)
                log_msgs.append("✅ Backpack 回滚完成")
            except Exception as e: log_msgs.append(f"💀 BP 回滚失败: {e}")
        elif res_hl and not res_bp:
            try:
                rb_side = 'sell' if side_hl == 'buy' else 'buy'
                if is_real: hyperliquid.create_order(symbol_hl, 'market', rb_side, amount)
                log_msgs.append("✅ HL 回滚完成")
            except Exception as e: log_msgs.append(f"💀 HL 回滚失败: {e}")

    return success, log_msgs

# === 4. UI 界面 ===
st.sidebar.header("🛠️ 策略设置")
mode = st.sidebar.radio("模式", ["🛡️ 模拟 (Simulation)", "⚡ 实盘 (Real Money)"])
IS_REAL = "实盘" in mode

st.sidebar.subheader("资产与方向")
SYMBOL_BP = st.sidebar.text_input("Backpack Symbol", "BTC/USDC")
SYMBOL_HL = st.sidebar.text_input("Hyperliquid Symbol", "BTC/USDC")
TRADE_AMOUNT = st.sidebar.number_input("下单数量", 0.0001, 10.0, 0.001, format="%.4f")

# 策略方向选择
FIXED_DIRECTION = st.sidebar.selectbox(
    "开仓方向 (Fixed Direction)", 
    ["Long_BP_Short_HL (BP做多/HL做空)", "Short_BP_Long_HL (BP做空/HL做多)"]
)
# 提取简化方向字符串
DIR_CODE = "Long_BP_Short_HL" if "BP做多" in FIXED_DIRECTION else "Short_BP_Long_HL"

st.sidebar.subheader("⏳ 时间设置")
AUTO_ENABLED = st.sidebar.checkbox("🔴 启动定时策略", value=False)
HOLD_DURATION_MIN = st.sidebar.number_input("持仓时长 (分钟)", 1, 60, 10) # 默认10分钟

st.title("⏳ VibeTrader 定时双开策略")
col1, col2, col3 = st.columns(3)
status_box = col1.empty()
timer_box = col2.empty()
next_action_box = col3.empty()

log_placeholder = st.empty()
if 'logs' not in st.session_state: st.session_state.logs = []

def add_log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.insert(0, f"[{ts}] {msg}")
    if len(st.session_state.logs) > 50: st.session_state.logs.pop()

# === 5. 主循环 ===
if st.button("🛑 停止"): st.stop()

# 获取状态
state = get_state()
STATUS = state['status']
OPEN_TIME_STR = state['open_time']

# 倒计时与状态逻辑
try:
    # 显示实时状态
    if STATUS == "EMPTY":
        status_box.markdown(f"### ⚪ 空仓待机")
        timer_box.metric("持仓计时", "--:--")
        next_action_box.info("准备开仓...")
    else:
        # 计算持仓时间
        open_dt = datetime.strptime(OPEN_TIME_STR, "%Y-%m-%d %H:%M:%S")
        now_dt = datetime.now()
        elapsed = now_dt - open_dt
        elapsed_minutes = elapsed.total_seconds() / 60
        
        status_box.markdown(f"### 🔵 持仓中")
        timer_box.metric("已持仓时间", f"{int(elapsed_minutes)}m {int(elapsed.seconds % 60)}s")
        
        remaining = HOLD_DURATION_MIN - elapsed_minutes
        if remaining > 0:
            next_action_box.info(f"距离平仓还有: {int(remaining)} 分钟")
        else:
            next_action_box.warning("⚠️ 时间到！正在平仓...")

    # === 自动化执行引擎 ===
    if AUTO_ENABLED:
        
        # 场景 A: 空仓 -> 立即开仓
        if STATUS == "EMPTY":
            add_log(f"⏰ 周期开始，正在开仓 ({DIR_CODE})...")
            
            success, logs = execute_dual_trade(DIR_CODE, TRADE_AMOUNT, SYMBOL_BP, SYMBOL_HL, IS_REAL)
            for l in logs: add_log(l)
            
            if success:
                # 记录当前时间为开仓时间
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                update_state("HOLDING", DIR_CODE, TRADE_AMOUNT, now_str)
                st.rerun()

        # 场景 B: 持仓 -> 检查时间 -> 平仓
        elif STATUS == "HOLDING":
            open_dt = datetime.strptime(OPEN_TIME_STR, "%Y-%m-%d %H:%M:%S")
            now_dt = datetime.now()
            # 检查是否超过设定分钟数
            if (now_dt - open_dt).total_seconds() >= (HOLD_DURATION_MIN * 60):
                add_log(f"⌛ 持仓满 {HOLD_DURATION_MIN} 分钟，正在平仓...")
                
                # 平仓方向 = 开仓方向取反
                # 简单逻辑：如果开仓是 Long_BP_Short_HL，平仓就是 Sell BP, Buy HL
                # 也就是 Short_BP_Long_HL 的操作逻辑
                close_dir = "Short_BP_Long_HL" if "Long_BP" in state['direction'] else "Long_BP_Short_HL"
                
                success, logs = execute_dual_trade(close_dir, TRADE_AMOUNT, SYMBOL_BP, SYMBOL_HL, IS_REAL)
                for l in logs: add_log(l)
                
                if success:
                    update_state("EMPTY", "NONE", 0.0, "")
                    add_log("🏁 平仓完成，等待下一轮...")
                    time.sleep(2) # 稍微休息一下再进下一轮
                    st.rerun()

except Exception as e:
    # 429 错误处理
    if "429" in str(e) or "Too Many Requests" in str(e):
        add_log("⚠️ 429 限频保护，暂停 20秒...")
        time.sleep(20)
        st.rerun()
    else:
        add_log(f"Error: {e}")

# 显示日志
log_placeholder.text_area("日志", "\n".join(st.session_state.logs), height=300)

# 刷新间隔 (5秒)
time.sleep(5)
st.rerun()
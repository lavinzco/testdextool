import ccxt
import time
from datetime import datetime

# 初始化连接 (dYdX)
print("正在连接 backpack 交易所...")
exchange = ccxt.backpack()

# 定义获取价格的函数
def fetch_price():
    try:
        # 获取 BTC/USD 的行情数据
        ticker = exchange.fetch_ticker('BTC/USDC')
        price = ticker['last'] 
        server_time = ticker['timestamp'] 
        
        # 打印结果
        print(f"✅ 成功! 当前 backpack 上的 BTC 价格: ${price}")
        print(f"   数据延迟: {ccxt.exchange.milliseconds() - server_time} 毫秒")
        
    except Exception as e:
        print(f"❌ 出错了: {e}")

# 执行一次
fetch_price()

import ccxt
import os
from dotenv import load_dotenv

load_dotenv()

print("🕵️‍♂️ 正在全网搜寻您的资产...")

try:
    # 连接 Backpack
    backpack = ccxt.backpack({
        'apiKey': os.getenv("BP_API_KEY"),
        'secret': os.getenv("BP_SECRET"),
        'enableRateLimit': True,
    })
    
    # 获取所有余额
    balance = backpack.fetch_balance()
    
    found_money = False
    print("\n📦 === Backpack 钱包详情 ===")
    
    # 遍历所有资产，只打印有钱的
    # balance['total'] 包含了冻结和可用的总和
    for currency, amount in balance['total'].items():
        if amount > 0:
            found_money = True
            print(f"💰 发现资产: [{currency}]")
            print(f"   数量: {amount}")
            print("-------------------------")
            
    if not found_money:
        print("💨 钱包里空空如也 (所有资产都为 0)")
        
except Exception as e:
    print(f"❌ 出错了: {e}")
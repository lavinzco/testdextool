import ccxt
import time
from datetime import datetime

def monitor_market():
    print("------------------------------------------------")
    print("🚀 系统启动中... 连接 Backpack 和 Hyperliquid...")
    
    # 1. 初始化连接 (把 dYdX 换成了 Backpack)
    try:
        backpack = ccxt.backpack()
        hyperliquid = ccxt.hyperliquid()
        print("✅ 连接成功！开始监控 CEX vs DEX 价差...")
    except Exception as e:
        print(f"❌ 初始化失败 (可能是您的 ccxt 版本太旧，请尝试运行 pip install ccxt --upgrade): {e}")
        return

    print("=====================================================")

    # 2. 开启无限循环
    while True:
        try:
            now = datetime.now().strftime("%H:%M:%S")
            
            # --- 核心逻辑 ---
            # 向 Backpack 询价 (注意：Backpack 主要交易对是 USDC)
            bp_ticker = backpack.fetch_ticker('BTC/USDC')
            
            # 向 Hyperliquid 询价
            hl_ticker = hyperliquid.fetch_ticker('BTC/USDC')
            
            price_bp = bp_ticker['last']
            price_hl = hl_ticker['last']
            
            # 计算价差
            diff = price_bp - price_hl
            diff_percent = (abs(diff) / price_bp) * 100
            # --- 核心逻辑结束 ---

            # 3. 打印
            direction = "Backpack 贵" if diff > 0 else "Hyper 贵"
            
            print(f"[{now}] Backpack: {price_bp:.1f} | Hyper: {price_hl:.1f} | 差价: ${abs(diff):.1f} ({direction}) | {diff_percent:.4f}%")
            
            # 简单的报警
            if diff_percent > 0.1: # 如果价差超过 0.1%
                 print("   💰💰💰 发现明显价差！")

            time.sleep(3)

        except KeyboardInterrupt:
            print("\n🛑 停止监控。")
            break
        except Exception as e:
            # 有时候 Backpack 的 API 可能会限流，这里做一个简单的容错
            print(f"⚠️ 获取数据稍微卡顿: {e}")
            time.sleep(3)

if __name__ == "__main__":
    monitor_market()
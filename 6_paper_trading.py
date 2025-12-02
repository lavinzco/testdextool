import ccxt
import time
from datetime import datetime

# === 策略参数设置 ===
OPEN_THRESHOLD = 0.05   # 开仓阈值：价差超过 0.05% 就开仓
CLOSE_THRESHOLD = 0.01  # 平仓阈值：价差小于 0.01% 就平仓
TRADE_SIZE_USD = 1000   # 每次假装交易 1000 USD

def paper_trade_bot():
    print("🚀 虚拟交易机器人启动... (不会消耗真实资金)")
    
    # 初始化连接
    backpack = ccxt.backpack()
    hyperliquid = ccxt.hyperliquid()
    
    # === 机器人的记忆 (状态机) ===
    in_position = False     # 当前是否持仓？
    entry_price_bp = 0      # 记录 BackPack 开仓价
    entry_price_hl = 0      # 记录 Hyperliquid 开仓价
    total_profit = 0        # 记录总盈利
    
    print("✅ 连接成功，等待机会中...")
    print("=====================================================")

    while True:
        try:
            now = datetime.now().strftime("%H:%M:%S")
            
            # 1. 获取数据
            ticker_bp = backpack.fetch_ticker('BTC/USDC')
            ticker_hl = hyperliquid.fetch_ticker('BTC/USDC')
            
            price_bp = ticker_bp['last']
            price_hl = ticker_hl['last']
            
            # 计算价差 %
            diff = price_bp - price_hl
            diff_percent = (abs(diff) / price_bp) * 100
            
            # 打印当前行情
            # print(f"[{now}] 价差: {diff_percent:.4f}% (${abs(diff):.1f})") # 嫌太吵可以注释掉这行

            # === 2. 策略逻辑核心 ===
            
            # [场景 A] 空仓状态 -> 寻找开仓机会
            if not in_position:
                if diff_percent > OPEN_THRESHOLD:
                    print(f"\n⚡ [{now}] 触发开仓信号！价差 {diff_percent:.4f}% > {OPEN_THRESHOLD}%")
                    
                    # 假装下单
                    entry_price_bp = price_bp
                    entry_price_hl = price_hl
                    
                    # 判断方向
                    if price_bp > price_hl:
                        print(f"   👉 动作: 在 Backpack 卖出 (做空), 在 Hyperliquid 买入 (做多)")
                        direction = "Short BP / Long HL"
                    else:
                        print(f"   👉 动作: 在 Hyperliquid 卖出 (做空), 在 Backpack 买入 (做多)")
                        direction = "Long BP / Short HL"
                        
                    in_position = True # 修改状态为“持仓中”
                    print(f"   🔒 锁定开仓价: BP=${entry_price_bp}, HL=${entry_price_hl}")
                    print("   --- 进入持仓监控模式 ---\n")

            # [场景 B] 持仓状态 -> 寻找平仓机会
            elif in_position:
                # 简单打印持仓盈亏
                # 这里的盈亏计算简化了：实际上是 (卖出价 - 买入价)
                # 但为了模拟，我们只看价差是否缩回去了
                print(f"[{now}] 持仓中... 当前价差: {diff_percent:.4f}% (目标: < {CLOSE_THRESHOLD}%)")
                
                if diff_percent < CLOSE_THRESHOLD:
                    print(f"\n💰 [{now}] 触发平仓信号！价差回归 ({diff_percent:.4f}%)")
                    
                    # 假装平仓
                    exit_price_bp = price_bp
                    exit_price_hl = price_hl
                    
                    # 计算这一单大概赚了多少 (简化算法：价差缩小的值 * 仓位)
                    # 逻辑：开仓时价差是 X，平仓时价差是 Y。如果你做对了方向，收益约为 (X - Y)
                    spread_captured = (abs(entry_price_bp - entry_price_hl) - abs(exit_price_bp - exit_price_hl))
                    estimated_pnl = (spread_captured / price_bp) * TRADE_SIZE_USD
                    
                    total_profit += estimated_pnl
                    
                    print(f"   ✅ 平仓成功！")
                    print(f"   💵 本次预估盈利: ${estimated_pnl:.2f}")
                    print(f"   🏆 累计总盈利:   ${total_profit:.2f}")
                    
                    in_position = False # 重置状态为“空仓”
                    print("   --- 等待下一轮机会 ---\n")

            time.sleep(3)

        except Exception as e:
            print(f"❌ 出错: {e}")
            time.sleep(3)

if __name__ == "__main__":
    paper_trade_bot()
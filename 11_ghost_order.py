import ccxt
import os
import time
from dotenv import load_dotenv

load_dotenv()

print("👻 准备执行“幽灵挂单”测试...")
print("------------------------------------------------")

def test_order():
    # 1. 连接 Backpack
    bp_key = os.getenv("BP_API_KEY")
    bp_secret = os.getenv("BP_SECRET")
    
    if not bp_key:
        print("❌ 请先在 .env 文件配置 Backpack API Key")
        return

    try:
        exchange = ccxt.backpack({
            'apiKey': bp_key,
            'secret': bp_secret,
            'enableRateLimit': True,
        })
        
        # 2. 获取当前价格
        symbol = 'BTC/USDC' # 确保 Backpack 有这个交易对
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        
        print(f"📉 当前 {symbol} 价格: ${current_price:,.2f}")
        
        # 3. 设定一个不可能成交的价格 (比如当前价的 20%)
        # 这样绝对安全，不会真的买入
        safe_price = current_price * 0.2
        
        # 设定最小购买数量 (Backpack 最小下单额通常约 5 USDC)
        # 算出大概 6 USDC 对应的 BTC 数量
        amount = 6.0 / safe_price 
        # 保留5位小数
        amount = float(f"{amount:.5f}")

        print(f"🛡️  测试挂单价格: ${safe_price:,.2f} (远低于市价，不会成交)")
        print(f"📦 测试挂单数量: {amount} BTC")
        
        # 4. 发送限价买单 (Limit Buy)
        print("\n🚀 正在发送测试指令...")
        order = exchange.create_order(
            symbol=symbol,
            type='limit',
            side='buy',
            amount=amount,
            price=safe_price
        )
        
        order_id = order['id']
        print(f"✅ 挂单成功！收到交易所回执 Order ID: {order_id}")
        print("   (这证明您的 API Key 拥有完整的交易权限)")
        
        # 5. 停留 3 秒给您看一眼
        print("⏳ 等待 3 秒后自动撤单...")
        time.sleep(3)
        
        # 6. 撤销订单
        print(f"🔙 正在撤销订单 {order_id}...")
        exchange.cancel_order(order_id, symbol)
        print("✅ 撤单成功！测试结束，资金未变动。")

    except ccxt.InsufficientFunds:
        print("\n💰 [验证成功] 交易所提示“余额不足”。")
        print("   说明：API 连接通畅，交易指令已送达，只是账户没钱下单。")
        print("   结论：您的代码逻辑是正确的！")
        
    except ccxt.PermissionDenied:
        print("\n❌ [权限拒绝] 交易所提示 API Key 权限不足。")
        print("   请去 Backpack 官网，编辑 API Key，确保勾选了 'Trading' 或 'Execute' 权限。")
        
    except Exception as e:
        print(f"\n❌ 发生其他错误: {e}")

if __name__ == "__main__":
    test_order()
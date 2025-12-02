import ccxt
import os
from dotenv import load_dotenv

# 1. 加载保险箱
load_dotenv()

print("🔐 正在尝试使用 API Key 连接账户...")
print("------------------------------------------------")

def check_balance():
    # === A. 尝试连接 Backpack ===
    bp_key = os.getenv("BP_API_KEY")
    bp_secret = os.getenv("BP_SECRET")

    if bp_key and "真实" not in bp_key: # 简单检查用户是不是还没填
        try:
            print("🎒 正在连接 Backpack...")
            # 注意：这里我们把 keys 传给了 ccxt
            backpack = ccxt.backpack({
                'apiKey': bp_key,
                'secret': bp_secret,
                'enableRateLimit': True,
            })
            
            # 核心指令：查询余额
            balance = backpack.fetch_balance()
            
            # 打印结果
            print("✅ Backpack 连接成功！")
            # total 包含冻结在订单里的钱，free 是可用余额
            USDC = balance.get('USDC', {'total': 0, 'free': 0}) 
            print(f"   💰 账户总资产 (USDC): {USDC['total']}")
            print(f"   💸 可用余额   (USDC): {USD['free']}")
            
        except Exception as e:
            print(f"❌ Backpack 连接失败: {e}")
    else:
        print("⚠️ Backpack Key 未配置或不正确，跳过。")

    print("------------------------------------------------")

    # === B. 尝试连接 Hyperliquid ===
    hl_address = os.getenv("HL_WALLET_ADDRESS")
    hl_private = os.getenv("HL_PRIVATE_KEY")

    if hl_private and "0x" in str(hl_address):
        try:
            print("💧 正在连接 Hyperliquid...")
            hyperliquid = ccxt.hyperliquid({
                'walletAddress': hl_address,
                'privateKey': hl_private,
                'enableRateLimit': True,
            })
            
            balance = hyperliquid.fetch_balance()
            
            print("✅ Hyperliquid 连接成功！")
            # Hyperliquid 的余额结构可能稍有不同，通常也是 USDC
            usdc = balance.get('USDC', {'total': 0, 'free': 0})
            print(f"   💰 账户总资产 (USDC): {usdc['total']}")
            print(f"   💸 可用余额   (USDC): {usdc['free']}")
            
        except Exception as e:
            print(f"❌ Hyperliquid 连接失败: {e}")
    else:
        print("⚠️ Hyperliquid 私钥/地址未配置，跳过。")

    print("------------------------------------------------")
    print("🎉 如果您看到了余额(哪怕是0)，说明您的机器人已经具备交易能力了！")

if __name__ == "__main__":
    check_balance()
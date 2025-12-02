import os
from dotenv import load_dotenv # 导入加载器

# 1. 加载 .env 文件里的内容到系统环境变量
# 这一步通常放在程序最开始执行
load_dotenv()

print("🔐 安全模块初始化中...")

def login_test():
    # 2. 从环境变量中读取密钥
    # os.getenv("变量名") 会去 .env 文件里找对应的值
    bp_key = os.getenv("BP_API_KEY")
    bp_secret = os.getenv("BP_SECRET")
    
    hl_address = os.getenv("HL_WALLET_ADDRESS")

    print("\n--- 检查密钥加载情况 ---")
    
    # 3. 验证是否读取成功 (注意：打印时一定要打码！不要直接 print 私钥！)
    if bp_key:
        # 只显示前4位和后4位，中间用星号代替
        masked_key = f"{bp_key[:4]}****{bp_key[-4:]}"
        print(f"✅ Backpack API Key 加载成功: {masked_key}")
    else:
        print("❌ 警告: 未找到 Backpack API Key！")

    if bp_secret:
        print("✅ Backpack Secret  加载成功: (已隐藏)")
    else:
        print("❌ 警告: 未找到 Backpack Secret！")
        
    if hl_address:
        print(f"✅ Hyperliquid 钱包地址: {hl_address}")
    else:
        print("❌ 警告: 未找到 Hyperliquid 钱包地址！")

    print("\n----------------------------------")
    print("🛡️  结论: 您的代码中没有包含任何明文私钥。")
    print("    您可以放心地把这个 .py 文件发送给任何人，")
    print("    只要不发送 .env 文件，您的资金就是安全的。")

if __name__ == "__main__":
    login_test()
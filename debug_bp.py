import ccxt
import os
from dotenv import load_dotenv

load_dotenv()

print("🕵️‍♂️ 正在启动 Backpack 诊断程序...")

bp_key = os.getenv("BP_API_KEY")
bp_secret = os.getenv("BP_SECRET")

# 1. 检查 .env 是否读取成功
if not bp_key or not bp_secret:
    print("❌ 错误：.env 文件读取失败！")
    print("   请确认 .env 文件就在当前文件夹下，且变量名拼写正确。")
    exit()
else:
    print(f"✅ 从 .env 读取到 Key: {bp_key[:4]}...{bp_key[-4:]}")

# 2. 尝试连接并捕获详细错误
try:
    print("📡 正在发送请求...")
    
    # 强制开启详细日志 (verbose=True)
    backpack = ccxt.backpack({
        'apiKey': bp_key,
        'secret': bp_secret,
        'enableRateLimit': True,
        # 'verbose': True, # 如果还不行，把这行前面的 # 去掉，会打印出通信细节
    })
    
    # 尝试获取余额
    balance = backpack.fetch_balance()
    print("🎉 成功了！余额如下：")
    print(balance['total'])

except ccxt.AuthenticationError as e:
    print("\n❌【认证失败】(AuthenticationError)")
    print("   原因：API Key 或 Secret 填写错误。")
    print("   建议：去官网删除旧的 Key，重新申请一个新的，复制时注意不要多复制空格！")
    print(f"   详细信息: {e}")

except ccxt.PermissionDenied as e:
    print("\n❌【权限被拒】(PermissionDenied)")
    print("   原因：这个 Key 没有“读取余额”的权限。")
    print("   建议：去官网检查 API 权限设置，确保勾选了 Read/Query。")
    print(f"   详细信息: {e}")

except ccxt.NetworkError as e:
    print("\n❌【网络错误】(NetworkError)")
    print("   原因：无法连接到 Backpack 服务器。可能是需要科学上网，或者 IP 被封。")
    print(f"   详细信息: {e}")

except Exception as e:
    print(f"\n❌【其他未知错误】: {e}")
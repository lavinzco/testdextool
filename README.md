这是一个为您定制的 GitHub README.md 文档。

它涵盖了项目介绍、核心功能、安装步骤、配置指南以及风险免责声明，风格专业且清晰，可以直接复制到您的 GitHub 仓库首页。

⚔️ VibeTrader: Dual-Exchange Perp Bot
VibeTrader 是一个基于 Python (Streamlit + CCXT) 构建的高性能自动化交易终端。它专为 Backpack 和 Hyperliquid 两大交易所设计，用于执行 时间轮动对冲策略 (Time-Based Hedging)。

程序采用并发执行引擎，支持原子化下单、单边成交自动回滚（Legging Protection）以及 SQLite 状态持久化，确保在 7x24 小时运行中的稳定性与资金安全。

🚀 核心功能 (Key Features)
⚡ 并发双开 (Concurrent Execution): 使用 ThreadPoolExecutor 确保双边订单毫秒级同步发送，最大程度减少滑点。

🛡️ 单边熔断机制 (Legging Protection): 如果一边成交而另一边失败（如网络超时、余额不足），系统会自动触发“回滚”逻辑，立即平掉已成交的仓位，防止裸头寸风险。

⏳ 时间轮动策略 (Time-Loop Strategy): 不依赖价差，按照设定的时间周期（如每10分钟）自动开仓、持仓、平仓，捕获长期资金费率或进行交易量刷单。

💾 状态持久化 (Persistence): 内置 SQLite 数据库，即使浏览器刷新或程序重启，机器人的持仓状态与计时也不会丢失。

🎒 完美支持合约 (Perp Support): 针对 Backpack 的 Swap 模式进行了深度适配，支持 BTC/USDC:USDC 格式及杠杆设置。

🤖 智能抗限频 (Anti-429): 内置 API 429 错误检测与避让机制，自动处理交易所的 Rate Limit。

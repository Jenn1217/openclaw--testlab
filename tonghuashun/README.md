# iFinD HTTP Market Data Skill for OpenClaw

这是一个专为 **OpenClaw** 和 **ClawHub** 生态打造的金融数据技能 (Skill)。它通过本地的 Python 适配器，让你的 AI Agent 能够直接调用同花顺 iFinD 的 HTTP Quant API，获取中国股票市场的历史行情数据。

## ✨ 核心功能 (Features)

目前本技能支持以下核心命令：

- `history_quotes` (历史行情查询)
  - 支持多只证券代码 (如 `000001.SZ,600000.SH`)
  - 支持自定义指标 (如 `open, high, low, close`)
  - 支持指定时间区间 (`startdate`, `enddate`)
  - 自动处理 Access Token 的换取与鉴权
  - 统一的 JSON 结构化输出，完美适配 Agent 的上下文解析

*未来计划支持: `trade_dates` (交易日历), `basic_data` (基础数据), `edb_service` (宏观经济数据)*

## 📦 安装 (Installation)

### 方式一：通过 ClawHub 安装 (推荐)
```bash
clawhub install ifind-http-market-data
```

### 方式二：通过 GitHub 仓库安装
```bash
npx skills add 你的用户名/你的仓库名
```

### 方式三：手动安装
将本仓库克隆或下载后，将文件夹放入你的 OpenClaw skills 目录下：
```bash
mkdir -p ~/.openclaw/skills/
git clone https://github.com/你的用户名/你的仓库名.git ~/.openclaw/skills/ifind_http_market_data
```

## ⚙️ 配置 (Configuration)

本技能依赖于同花顺 iFinD 的量化接口权限。在使用前，你必须在项目根目录或环境变量中配置你的凭证。

1. 在当前运行环境或项目根目录创建一个 `.env` 文件。
2. 填入你的 `IFIND_REFRESH_TOKEN` (以及可能的密码等其他参数)：

```env
IFIND_REFRESH_TOKEN=你的同花顺刷新令牌
IFIND_PASSWORD=你的密码 (如需要)
```

**⚠️ 安全警告：** 绝对不要将 `.env` 文件提交到版本控制系统 (Git) 中！本仓库已提供默认的 `.gitignore` 规则来忽略它。

## 🚀 使用示例 (Usage)

在你的 OpenClaw 会话中，你可以直接使用自然语言触发该技能：

> **User:** "帮我查一下平安银行 (000001.SZ) 2025年1月1日到1月10日的开盘价和收盘价。"

Agent 将自动解析你的意图，提取参数并调用后端的 Python 脚本：

```bash
# Agent 内部执行的等效命令
python scripts/ifind_cli.py history_quotes \
  --codes "000001.SZ" \
  --indicators "open,close" \
  --startdate "2025-01-01" \
  --enddate "2025-01-10"
```

## 🛠️ 本地开发与测试 (Development)

如果你想对这个脚本进行二次开发或本地调试：

1. 确保已安装 Python 3 环境。
2. 安装依赖：
```bash
pip install requests python-dotenv
```
3. 运行命令行测试：
```bash
python scripts/ifind_cli.py history_quotes --codes "000001.SZ" --indicators "open,close" --startdate "2025-01-01" --enddate "2025-01-02"
```
成功的响应应该是一个状态为 `"ok"` 的 JSON 对象。

## 📄 目录结构
- `SKILL.md` - OpenClaw Agent 读取的技能定义文件
- `skill.json` - ClawHub 发现与发布的元数据文件
- `scripts/ifind_cli.py` - 核心的数据获取 Python 脚本
- `.env` - (需自行创建) 存放你的敏感 Token 

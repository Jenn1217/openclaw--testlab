---
name: tonghuashun
description: 通过本地 iFinD SDK 查询市场数据。适用于用户在特定日期查询中国市场证券的股票报价、市场价格、财务指标或排名的情况。支持三种命令：quote_data（完整市场快照）、basic_data（自定义字段）和 rank_basic_data（跨股票排名）。不适用于实时交易操作、不支持模糊指标或没有明确符号和日期的广泛财务分析。
metadata: {"openclaw":{"os":["linux","darwin"],"requires":{"bins":["python3"]}}}
---

# iFinD SDK Market Data Skill

Use this skill to fetch structured market data from **iFinD SDK** through the local adapter script:

`scripts/ifind_cli.py`

This skill is for **structured market-data retrieval and simple ranking**, not open-ended financial reasoning.

## What this skill currently supports

This version supports three operations:

- `quote_data` ← **优先使用**：用户说"查行情"时默认调这个
- `basic_data`
- `rank_basic_data`

## Authentication

This skill uses **SDK login credentials**, not HTTP refresh tokens.

Set these in `.env` or environment variables:

- `IFIND_USERNAME`
- `IFIND_PASSWORD`

Do **not** use `IFIND_REFRESH_TOKEN` for this SDK version.

---

## `quote_data` ← 查行情首选命令

当用户说出下列任何一种意图时，**优先使用 `quote_data`**，无需用户报告字段名：

### 触发关键词（出现其中任意一个即触发）

- "查……的行情"
- "看一下……今天/最新的情况"
- "……涨了多少 / 今天怎么样"
- "……的价格 / 开高低收 / 前收"
- "……的换手率 / 成交量 / 成交额 / 成交笔数"
- "……的涨跌停 / 交易状态 / 是否停牌"
- "给我看看……的数据"

### 内置字段（无需任何字段参数，自动全量返回，共 32 个）

**价格**

| 字段名 | 含义 |
|---|---|
| `ths_pre_close_stock` | 前收盘价 |
| `ths_open_price_stock` | 开盘价 |
| `ths_high_price_stock` | 最高价 |
| `ths_low_stock` | 最低价 |
| `ths_close_price_stock` | 收盘价 |
| `ths_avg_price_stock` | 均价 |
| `ths_max_up_stock` | 涨停价 |
| `ths_max_down_stock` | 跌停价 |

**涨跌**

| 字段名 | 含义 |
|---|---|
| `ths_chg_ratio_stock` | 涨跌幅(%) |
| `ths_chg_stock` | 涨跌额 |
| `ths_swing_stock` | 振幅(%) |
| `ths_relative_issue_price_chg_stock` | 相对发行价涨跌 |
| `ths_relative_issue_price_chg_ratio_stock` | 相对发行价涨跌幅 |
| `ths_relative_chg_ratio_stock` | 相对大盘涨跌幅（对标沪深300） |

**成交**

| 字段名 | 含义 |
|---|---|
| `ths_vol_stock` | 成交量(手) |
| `ths_vol_btin_stock` | 成交量(含大宗) |
| `ths_trans_num_stock` | 成交笔数 |
| `ths_amt_stock` | 成交额(元) |
| `ths_amt_btin_stock` | 成交额(含大宗) |
| `ths_turnover_ratio_stock` | 换手率(%) |
| `ths_vaild_turnover_stock` | 有效换手率 |

**盘后**

| 字段名 | 含义 |
|---|---|
| `ths_vol_after_trading_stock` | 盘后成交量 |
| `ths_trans_num_after_trading_stock` | 盘后成交笔数 |
| `ths_amt_after_trading_stock` | 盘后成交额 |

**状态**

| 字段名 | 含义 |
|---|---|
| `ths_up_and_down_status_stock` | 涨跌停状态 |
| `ths_trading_status_stock` | 交易状态 |
| `ths_continuous_suspension_days_stock` | 连续停牌天数 |
| `ths_suspen_reason_stock` | 停牌原因 |
| `ths_last_td_date_stock` | 最近交易日 |

**其他**

| 字段名 | 含义 |
|---|---|
| `ths_af_stock` | 复权因子 |
| `ths_af2_stock` | 复权因子2 |
| `ths_ahshare_premium_rate_stock` | AH股溢价率 |

> 注：`ths_specified_datenearly_td_date_stock`（指定日相近交易日）参数格式特殊，已从内置集中排除，如需使用请通过 `basic_data` 命令手动指定。

### Required inputs

- `codes`: 证券代码，如 `000001.SZ`，多个用逗号分隔
- `date`: `YYYY-MM-DD`

Optional:

- `--extra`: 额外追加的字段，分号分隔，会与内置字段合并去重

### Example

```bash
python3 scripts/ifind_cli.py quote_data \
  --codes "000001.SZ" \
  --date "2026-04-02"
```

用户说"再加一个EPS"时追加：

```bash
python3 scripts/ifind_cli.py quote_data \
  --codes "000001.SZ" \
  --date "2026-04-02" \
  --extra "ths_eps_ttm_stock"
```

## `basic_data`

Use this when the user asks for **specific named THS fields** that are NOT a general "行情" request. For example:

- "查 000001.SZ 2026-04-02 的市盈率、涨跌幅、收盘价"（字段明确给出）
- "查 000001.SZ 的 ths_pe_lyr_stock 和 ths_chg_ratio_stock"
- "给我 2026-04-02 这一天的这些 THS_BD 字段"

### Required inputs

- `codes`: comma-separated security codes such as `000001.SZ,600000.SH`
- `indicators`: semicolon-separated THS fields such as `ths_pe_lyr_stock;ths_chg_ratio_stock;ths_close_price_stock`
- `date`: `YYYY-MM-DD`

### Example

```bash
python3 scripts/ifind_cli.py basic_data \
  --codes "000001.SZ" \
  --indicators "ths_pe_lyr_stock;ths_chg_ratio_stock;ths_close_price_stock" \
  --date "2026-04-02"
```

---

## `rank_basic_data`

Use this when the user asks for **ranking/comparison across multiple securities on a single date**, for example:

- "今天涨幅最大的是哪个公司？"
- "比较这几家公司今天谁涨幅最高"
- "按 ths_chg_ratio_stock 对这些股票排序"
- "如果我没指定股票，就默认比较全A股排除北交所"

### Required inputs

- `codes`: optional; comma-separated security codes
- `indicator`: a single THS field such as `ths_chg_ratio_stock`
- `date`: `YYYY-MM-DD`
- optional `topn`: integer, default 10
- optional `chunk_size`: integer, default 300

If `codes` is omitted, the skill will automatically use the **full A-share pool excluding Beijing Stock Exchange**.

### Example: ranking on a user-provided stock pool

```bash
python3 scripts/ifind_cli.py rank_basic_data \
  --codes "000001.SZ,600036.SH,601166.SH" \
  --indicator "ths_chg_ratio_stock" \
  --date "2026-04-02" \
  --topn 3
```

### Example: ranking on full A-share pool excluding BJSE

```bash
python3 scripts/ifind_cli.py rank_basic_data \
  --date "2026-04-02" \
  --topn 10
```

---

## 中文意图 → 命令选择速查表

| 用户说的话 | 用哪个命令 | 备注 |
|---|---|---|
| 查平安银行今天的行情 | `quote_data` | 默认全量字段，无需指标 |
| 平安银行今天涨了多少 | `quote_data` | 同上 |
| 给我看看这几支股票的价格 | `quote_data` | 多codes逗号分隔 |
| 查平安银行的市盈率TTM和市净率 | `quote_data` 或 `basic_data` | 字段已在默认集里时用 quote_data |
| 查 ths_eps_ttm_stock 这个字段 | `basic_data` | 用户明确点名非默认字段 |
| 今天涨幅最大的股票是哪些 | `rank_basic_data` | 跨股票排名 |
| 帮我对这几只股票按换手率排个序 | `rank_basic_data` | 指定池排名 |

---

## Input normalization rules

Follow these rules carefully:

1. Prefer explicit user-provided security codes.
2. Do not invent or guess a security code if multiple matches are plausible.
3. Date inference:
   - 如果用户说"今天"，使用当前日期换算为 `YYYY-MM-DD`。
   - 如果当天非交易日，优先使用最近的交易日（或直接传用户说的日期，让 SDK 报错后告知用户）。
4. 如果用户没有提供任何指标且意图是"看行情"，**使用 `quote_data`，不要询问用户要哪些字段**。
5. 如果用户提到的字段名不在默认集里，通过 `--extra` 追加，而不是切换到 `basic_data`。

---

## When to use

Use this skill when all of the following are true:

1. The user wants **structured iFinD market data**
2. The request can be mapped to:
   - one or more security codes
   - a single date (or "today")
3. The request does **not** require browsing a website UI
4. The request does **not** require placing trades or taking external actions

## When NOT to use

Do **not** use this skill when:

- the user wants real-time trading, order placement, or account operations
- the user asks for vague research like "分析这家公司值不值得买" without a concrete data retrieval request
- the user asks for unsupported endpoints that this adapter does not implement yet
- the user does not provide a usable date input and you cannot infer it safely
- the request is better handled by another tool or skill

---

## Output handling

The adapter returns JSON only.

- If `status` is `ok` and command is `quote_data`:
  - 将 `result.records` 里的每个字段翻译成中文，按"价格 → 涨跌 → 成交 → 估值 → 市值"分组展示。
  - 明确报出使用的证券代码和日期。
  - **缺失字段处理（重要）**：检查 `result.missing_indicators` 字段。
    - 若该列表**非空**，在回复末尾加一行注释，格式为：
      > 注：X、Y、Z 暂时无法从 iFinD 接口中获取。
    - 其中 X、Y、Z 为列表中的中文字段名，用顿号分隔，末尾加句号。
    - 示例：`"missing_indicators": ["成交量", "换手率", "量比"]` → 注：成交量、换手率、量比暂时无法从 iFinD 接口中获取。
    - 若列表为空，不显示该注释行。
- If `status` is `ok` and command is `basic_data`: summarize the result clearly; same missing_indicators rule applies.
- If `status` is `ok` and command is `rank_basic_data`: 用排名列表展示，带股票名称和数值。
- If `status` is `error`, report the error plainly.
- Do not pretend the query succeeded when the adapter returned an error.
- Do not fabricate missing rows, symbols, or indicator values.

---

## Safety and reliability rules

- Treat the adapter output as the source of truth.
- Never expose SDK credentials in the response.
- Never place account passwords inside prompts, command arguments, or logs.
- Do not retry repeatedly in a tight loop.
- If the request is outside this skill's current scope, say exactly which command is supported and which is not.

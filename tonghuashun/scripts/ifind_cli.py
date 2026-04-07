import os
import sys
import json
import math
import atexit
import argparse
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

try:
    from iFinDPy import THS_iFinDLogin, THS_iFinDLogout, THS_BD, THS_DR  # type: ignore
except Exception as exc:  # pragma: no cover
    print(json.dumps({
        "status": "error",
        "error_type": "ImportError",
        "message": f"无法导入 iFinDPy：{exc}"
    }, ensure_ascii=False))
    sys.exit(1)

IFIND_USERNAME = os.getenv("IFIND_USERNAME") or os.getenv("IFIND_ACCOUNT") or os.getenv("IFIND_USER")
IFIND_PASSWORD = os.getenv("IFIND_PASSWORD")

_LOGIN_DONE = False


class IFindError(Exception):
    """iFinD SDK 适配层统一异常"""


def output_json(data: Dict[str, Any], exit_code: int = 0) -> None:
    print(json.dumps(data, ensure_ascii=False))
    sys.exit(exit_code)


def require_credentials() -> tuple[str, str]:
    if not IFIND_USERNAME or not IFIND_PASSWORD:
        raise IFindError("没有读取到 IFIND_USERNAME / IFIND_PASSWORD，请检查 .env 文件或环境变量")
    return IFIND_USERNAME, IFIND_PASSWORD


def ensure_login() -> None:
    global _LOGIN_DONE
    if _LOGIN_DONE:
        return

    username, password = require_credentials()
    ret = THS_iFinDLogin(username, password)
    if ret not in {0, -201}:
        raise IFindError(f"SDK 登录失败，返回码={ret}")
    _LOGIN_DONE = True


def safe_logout() -> None:
    global _LOGIN_DONE
    if not _LOGIN_DONE:
        return
    try:
        THS_iFinDLogout()
    except Exception:
        pass
    _LOGIN_DONE = False


atexit.register(safe_logout)


def validate_date(date_str: str, field_name: str) -> str:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as exc:
        raise IFindError(f"{field_name} 格式错误，必须是 YYYY-MM-DD：{date_str}") from exc
    return date_str


def split_items(value: str, *, separators: str = ",;") -> List[str]:
    if not value:
        return []

    normalized = value
    for sep in separators:
        normalized = normalized.replace(sep, ";")

    return [item.strip() for item in normalized.split(";") if item.strip()]


def normalize_codes(codes: str) -> str:
    code_list = split_items(codes)
    if not code_list:
        raise IFindError("codes 不能为空")
    return ",".join(code_list)


def normalize_basic_indicators(indicators: str) -> List[str]:
    indicator_list = split_items(indicators)
    if not indicator_list:
        raise IFindError("basic_data 至少要传一个指标")
    return indicator_list


def _normalize_scalar(value: Any) -> Any:
    try:
        if value is None:
            return None
        if isinstance(value, float) and math.isnan(value):
            return None
    except Exception:
        pass

    # pandas / numpy timestamp
    if hasattr(value, "isoformat") and callable(getattr(value, "isoformat")):
        try:
            return value.isoformat()
        except Exception:
            return str(value)

    # numpy scalar
    if hasattr(value, "item") and callable(getattr(value, "item")):
        try:
            value = value.item()
        except Exception:
            pass

    return value


def dataframe_to_records(df: Any) -> List[Dict[str, Any]]:
    if df is None:
        return []
    if not hasattr(df, "to_dict"):
        raise IFindError("SDK 返回的数据不是 DataFrame，无法转换为 JSON")

    try:
        records = df.to_dict(orient="records")
    except Exception as exc:
        raise IFindError(f"DataFrame 转 JSON 失败：{exc}") from exc

    normalized_records: List[Dict[str, Any]] = []
    for row in records:
        normalized_records.append({k: _normalize_scalar(v) for k, v in row.items()})
    return normalized_records


def sdk_call_ths_bd(codes: str, indicators: str, date: str) -> Any:
    ensure_login()
    query_date = validate_date(date, "date")
    code_str = normalize_codes(codes)
    indicator_list = normalize_basic_indicators(indicators)

    # THS_BD 支持多指标；大多数指标只需传日期，少数指标有额外参数要求
    params = ";".join(get_indicator_param(ind, query_date) for ind in indicator_list)
    functions = ";".join(indicator_list)

    result = THS_BD(code_str, functions, params)
    errorcode = getattr(result, "errorcode", None)
    errmsg = getattr(result, "errmsg", "")
    if errorcode not in {0, None}:
        raise IFindError(f"THS_BD 调用失败：errorcode={errorcode}, errmsg={errmsg}")
    if not hasattr(result, "data"):
        raise IFindError("THS_BD 返回结构异常：缺少 data")
    return result


def basic_data(
    codes: str,
    indicators: str,
    date: str,
) -> Dict[str, Any]:
    result = sdk_call_ths_bd(codes=codes, indicators=indicators, date=date)
    return {
        "records": dataframe_to_records(result.data),
        "errorcode": getattr(result, "errorcode", 0),
        "errmsg": getattr(result, "errmsg", ""),
    }


# ──────────────────────────────────────────────────────────────────────────────
# quote_data：行情快捷命令，内置一套完整的常用行情指标
# 当用户说「查某某的行情」「看一下涨跌幅/开高低收/换手率/市值...」时优先使用
# 所有查询直接调用 iFinD 接口，不使用本地缓存
# ──────────────────────────────────────────────────────────────────────────────
# 少数指标需要非标准参数格式；其余指标默认只传日期
INDICATOR_PARAMS: Dict[str, str] = {
    # 相对大盘涨跌幅：需指定对标指数（1=沪淳300）和填充方式
    "ths_relative_chg_ratio_stock": "{date},1,0",
}


def get_indicator_param(indicator: str, date: str) -> str:
    """根据指标返回对应的 THS_BD 参数字符串。"""
    template = INDICATOR_PARAMS.get(indicator, "{date}")
    return template.replace("{date}", date)


# ──────────────────────────────────────────────────────────────────────────────
# quote_data 默认指标集（32 个）
# 注：ths_specified_datenearly_td_date_stock 参数格式特殊(-1,date)，已主动排除
# ──────────────────────────────────────────────────────────────────────────────
DEFAULT_QUOTE_INDICATORS: List[str] = [
    # ── 价格 ───────────────────────────────────────────────────────────────
    "ths_pre_close_stock",                      # 前收盘价
    "ths_open_price_stock",                     # 开盘价
    "ths_high_price_stock",                     # 最高价
    "ths_low_stock",                            # 最低价
    "ths_close_price_stock",                    # 收盘价
    "ths_avg_price_stock",                      # 均价
    "ths_max_up_stock",                         # 涨停价
    "ths_max_down_stock",                       # 跌停价
    # ── 涨跌 ───────────────────────────────────────────────────────────────
    "ths_chg_ratio_stock",                      # 涨跌幅(%)
    "ths_chg_stock",                            # 涨跌额
    "ths_swing_stock",                          # 振幅(%)
    "ths_relative_issue_price_chg_stock",       # 相对发行价涨跌
    "ths_relative_issue_price_chg_ratio_stock", # 相对发行价涨跌幅
    "ths_relative_chg_ratio_stock",             # 相对大盘涨跌幅
    # ── 成交 ───────────────────────────────────────────────────────────────
    "ths_vol_stock",                            # 成交量(手)
    "ths_vol_btin_stock",                       # 成交量(含大宗)
    "ths_trans_num_stock",                      # 成交笔数
    "ths_amt_stock",                            # 成交额(元)
    "ths_amt_btin_stock",                       # 成交额(含大宗)
    "ths_turnover_ratio_stock",                 # 换手率(%)
    "ths_vaild_turnover_stock",                 # 有效换手率
    # ── 盘后 ───────────────────────────────────────────────────────────────
    "ths_vol_after_trading_stock",              # 盘后成交量
    "ths_trans_num_after_trading_stock",        # 盘后成交笔数
    "ths_amt_after_trading_stock",              # 盘后成交额
    # ── 状态 ───────────────────────────────────────────────────────────────
    "ths_up_and_down_status_stock",             # 涨跌停状态
    "ths_trading_status_stock",                 # 交易状态
    "ths_continuous_suspension_days_stock",     # 连续停牌天数
    "ths_suspen_reason_stock",                  # 停牌原因
    "ths_last_td_date_stock",                   # 最近交易日
    # ── 其他 ───────────────────────────────────────────────────────────────
    "ths_af_stock",                             # 复权因子
    "ths_af2_stock",                            # 复权因子2
    "ths_ahshare_premium_rate_stock",           # AH股溢价率
]

# 指标字段 → 中文名映射（用于生成「暂时无法获取」提示）
INDICATOR_CN_NAMES: Dict[str, str] = {
    # 价格
    "ths_pre_close_stock":                      "前收盘价",
    "ths_open_price_stock":                     "开盘价",
    "ths_high_price_stock":                     "最高价",
    "ths_low_stock":                            "最低价",
    "ths_close_price_stock":                    "收盘价",
    "ths_avg_price_stock":                      "均价",
    "ths_max_up_stock":                         "涨停价",
    "ths_max_down_stock":                       "跌停价",
    # 涨跌
    "ths_chg_ratio_stock":                      "涨跌幅",
    "ths_chg_stock":                            "涨跌额",
    "ths_swing_stock":                          "振幅",
    "ths_relative_issue_price_chg_stock":       "相对发行价涨跌",
    "ths_relative_issue_price_chg_ratio_stock": "相对发行价涨跌幅",
    "ths_relative_chg_ratio_stock":             "相对大盘涨跌幅",
    # 成交
    "ths_vol_stock":                            "成交量",
    "ths_vol_btin_stock":                       "成交量(含大宗)",
    "ths_trans_num_stock":                      "成交笔数",
    "ths_amt_stock":                            "成交额",
    "ths_amt_btin_stock":                       "成交额(含大宗)",
    "ths_turnover_ratio_stock":                 "换手率",
    "ths_vaild_turnover_stock":                 "有效换手率",
    # 盘后
    "ths_vol_after_trading_stock":              "盘后成交量",
    "ths_trans_num_after_trading_stock":        "盘后成交笔数",
    "ths_amt_after_trading_stock":              "盘后成交额",
    # 状态
    "ths_up_and_down_status_stock":             "涨跌停状态",
    "ths_trading_status_stock":                 "交易状态",
    "ths_continuous_suspension_days_stock":     "连续停牌天数",
    "ths_suspen_reason_stock":                  "停牌原因",
    "ths_last_td_date_stock":                   "最近交易日",
    # 其他
    "ths_af_stock":                             "复权因子",
    "ths_af2_stock":                            "复权因子2",
    "ths_ahshare_premium_rate_stock":           "AH股溢价率",
    # 历史兼容：旧头文件中可能存在的字段名
    "ths_amplitude_stock":                      "振幅",   # 旧名，现用 ths_swing_stock
    "ths_low_price_stock":                      "最低价",  # 旧名，现用 ths_low_stock
    "ths_volume_ratio_stock":                   "量比",
    "ths_pe_ttm_stock":                         "市盈率(TTM)",
    "ths_pb_mrq_stock":                         "市净率(MRQ)",
    "ths_total_mv_stock":                       "总市值",
    "ths_free_mv_stock":                        "流通市值",
}


def detect_missing_indicators(
    records: List[Dict[str, Any]],
    indicators: List[str],
) -> List[str]:
    """
    扫描 records 中所有记录，找出在全部记录里均为 None 的指标。
    返回缺失指标的中文名列表（供展示提示使用）。
    """
    if not records:
        return [INDICATOR_CN_NAMES.get(ind, ind) for ind in indicators]

    missing: List[str] = []
    for ind in indicators:
        # 只要有任意一条记录有有效值，就不算缺失
        has_value = any(
            rec.get(ind) is not None
            for rec in records
        )
        if not has_value:
            missing.append(INDICATOR_CN_NAMES.get(ind, ind))
    return missing


def quote_data(
    codes: str,
    date: str,
    extra_indicators: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    一次性查询完整行情快照，直接调用 iFinD 接口返回数据。
    """
    indicators = list(DEFAULT_QUOTE_INDICATORS)
    if extra_indicators:
        for ind in extra_indicators:
            if ind.strip() and ind.strip() not in indicators:
                indicators.append(ind.strip())

    indicators_str = ";".join(indicators)

    raw = basic_data(codes=codes, indicators=indicators_str, date=date)
    missing = detect_missing_indicators(raw.get("records", []), indicators)
    raw["indicators_used"] = indicators
    raw["missing_indicators"] = missing
    raw["source"] = "api"
    return raw


def get_all_a_share_ex_bj(date: str) -> str:
    """
    获取指定日期的全A股股票池（排除北交所）
    这里沿用你提供的专题报表方案：p03291 + blockname=001005345
    """
    ensure_login()
    query_date = validate_date(date, "date")
    date_compact = query_date.replace("-", "")

    var1 = "p03291"
    var2 = f"date={date_compact};blockname=001005345;iv_type=allcontract"
    var3 = "p03291_f002:Y"

    result = THS_DR(var1, var2, var3, "format:dataframe")
    errorcode = getattr(result, "errorcode", None)
    errmsg = getattr(result, "errmsg", "")
    if errorcode not in {0, None}:
        raise IFindError(f"THS_DR 调用失败：errorcode={errorcode}, errmsg={errmsg}")
    if not hasattr(result, "data"):
        raise IFindError("THS_DR 返回结构异常：缺少 data")

    df = result.data
    if df is None or getattr(df, "empty", True):
        raise IFindError("获取全A股股票池失败：返回股票池为空")
    if "p03291_f002" not in df.columns:
        raise IFindError(f"获取全A股股票池失败：缺少字段 p03291_f002，实际列={list(df.columns)}")

    codes = df["p03291_f002"].dropna().astype(str).tolist()
    codes = [x.strip() for x in codes if x.strip()]
    if not codes:
        raise IFindError("获取全A股股票池失败：代码列表为空")
    return ",".join(codes)


def resolve_codes(codes: str, date: str) -> str:
    if codes and codes.strip():
        return normalize_codes(codes)
    auto_codes = get_all_a_share_ex_bj(date)
    print("the code will analyse all A shares excluding Beijing Stock Exchange!", file=sys.stderr)
    return auto_codes


def chunk_list(items: List[str], chunk_size: int) -> List[List[str]]:
    if chunk_size <= 0:
        raise IFindError("chunk_size 必须为正整数")
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def pick_rank_value(row: Dict[str, Any], indicator: str) -> Optional[Any]:
    if indicator in row:
        return row.get(indicator)
    # 兜底：有些 DataFrame 列名可能带大小写或前后空格，尽量模糊匹配一次
    for key, value in row.items():
        if str(key).strip() == indicator:
            return value
    return None


def rank_basic_data(
    codes: str,
    indicator: str,
    date: str,
    topn: int = 10,
    descending: bool = True,
    chunk_size: int = 300,
) -> Dict[str, Any]:
    if not indicator or not indicator.strip():
        raise IFindError("indicator 不能为空")
    if topn <= 0:
        raise IFindError("topn 必须为正整数")

    resolved_codes = resolve_codes(codes, date)
    code_list = [x.strip() for x in resolved_codes.split(",") if x.strip()]
    if not code_list:
        raise IFindError("可用于排序的股票池为空")

    all_rows: List[Dict[str, Any]] = []

    for batch in chunk_list(code_list, chunk_size):
        batch_codes = ",".join(batch)
        raw = basic_data(
            codes=batch_codes,
            indicators=indicator,
            date=date,
        )
        for row in raw["records"]:
            value = pick_rank_value(row, indicator)
            if value is None:
                continue
            all_rows.append({
                "code": row.get("thscode") or row.get("THSCODE") or row.get("code"),
                "security_name": row.get("security_name") or row.get("SECURITY_NAME") or row.get("ths_security_name_stock"),
                "indicator": indicator,
                "value": _normalize_scalar(value),
            })

    all_rows = [x for x in all_rows if x.get("value") is not None]
    all_rows.sort(key=lambda x: x["value"], reverse=descending)

    return {
        "ranking": all_rows[:topn],
        "total": len(all_rows),
        "sort_order": "desc" if descending else "asc",
        "indicator": indicator,
        "date": date,
        "used_auto_pool": not bool(codes and codes.strip()),
        "pool_scope": (
            "all_A_share_excluding_BJSE"
            if not (codes and codes.strip())
            else "user_provided_codes"
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="iFinD SDK CLI for OpenClaw skill usage"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    basic_parser = subparsers.add_parser(
        "basic_data",
        help="通过 iFinD SDK 查询基础数据 / 财务指标 / 单日扩展行情字段",
    )
    basic_parser.add_argument("--codes", required=True, help="证券代码，多个可用英文逗号或分号分隔")
    basic_parser.add_argument(
        "--indicators",
        required=True,
        help=(
            "指标列表，建议用分号分隔，例如 "
            "ths_pe_lyr_stock;ths_close_price_stock;ths_chg_ratio_stock"
        ),
    )
    basic_parser.add_argument("--date", required=True, help="查询日期，如 2026-04-02")

    # quote_data 子命令
    quote_parser = subparsers.add_parser(
        "quote_data",
        help="查询单日完整行情快照（开高低收/涨跌幅/换手率/量比/市值等），无需手报指标名",
    )
    quote_parser.add_argument("--codes", required=True, help="证券代码，多个可用英文逗号或分号分隔")
    quote_parser.add_argument("--date", required=True, help="查询日期，如 2026-04-02")
    quote_parser.add_argument(
        "--extra",
        default="",
        help="额外追加的 THS 指标，多个用分号分隔；可与默认字段集合并",
    )

    rank_parser = subparsers.add_parser(
        "rank_basic_data",
        help="对多只股票的单日指标进行排序；未传 codes 时默认用全A股排除北交所",
    )
    rank_parser.add_argument(
        "--codes",
        default="",
        help="证券代码，多个可用英文逗号或分号分隔；不传则默认全A股排除北交所",
    )
    rank_parser.add_argument(
        "--indicator",
        default="ths_chg_ratio_stock",
        help="单个比较指标，默认 ths_chg_ratio_stock",
    )
    rank_parser.add_argument("--date", required=True, help="查询日期，如 2026-04-02")
    rank_parser.add_argument("--topn", type=int, default=10, help="返回前几名，默认 10")
    rank_parser.add_argument("--ascending", action="store_true", help="升序排序，默认降序")
    rank_parser.add_argument("--chunk_size", type=int, default=300, help="分批查询大小，默认 300")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "quote_data":
            extra = [x.strip() for x in args.extra.split(";") if x.strip()] if args.extra else []
            result = quote_data(
                codes=args.codes,
                date=args.date,
                extra_indicators=extra or None,
            )
            output_json(
                {
                    "status": "ok",
                    "command": "quote_data",
                    "input": {
                        "codes": normalize_codes(args.codes),
                        "date": args.date,
                        "extra_indicators": extra,
                    },
                    "result": result,
                }
            )

        elif args.command == "basic_data":
            result = basic_data(
                codes=args.codes,
                indicators=args.indicators,
                date=args.date,
            )
            output_json(
                {
                    "status": "ok",
                    "command": "basic_data",
                    "input": {
                        "codes": normalize_codes(args.codes),
                        "indicators": normalize_basic_indicators(args.indicators),
                        "date": args.date,
                    },
                    "result": result,
                }
            )

        elif args.command == "rank_basic_data":
            result = rank_basic_data(
                codes=args.codes,
                indicator=args.indicator,
                date=args.date,
                topn=args.topn,
                descending=not args.ascending,
                chunk_size=args.chunk_size,
            )
            output_json(
                {
                    "status": "ok",
                    "command": "rank_basic_data",
                    "input": {
                        "codes": args.codes,
                        "indicator": args.indicator,
                        "date": args.date,
                        "topn": args.topn,
                        "ascending": args.ascending,
                        "chunk_size": args.chunk_size,
                    },
                    "result": result,
                }
            )

        else:
            output_json(
                {
                    "status": "error",
                    "error_type": "UnsupportedCommand",
                    "message": f"不支持的命令：{args.command}",
                },
                exit_code=2,
            )

    except IFindError as exc:
        output_json(
            {
                "status": "error",
                "error_type": "IFindError",
                "message": str(exc),
            },
            exit_code=1,
        )

    except Exception as exc:
        output_json(
            {
                "status": "error",
                "error_type": type(exc).__name__,
                "message": str(exc),
            },
            exit_code=1,
        )


if __name__ == "__main__":
    main()

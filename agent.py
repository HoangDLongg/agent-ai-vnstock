# ============================================
# agent.py — BẢN FIX FULL CHO 14 TEST CASE
# ============================================

import os
os.environ["VNSTOCK_DISABLE_ADS"] = "1"

import ollama
import json
import re
from tools import all_tools
import logging

logging.getLogger("ollama").setLevel(logging.ERROR)

# ==============================================
# 1. Intent Classification (PHẦN QUAN TRỌNG NHẤT)
# ==============================================

def classify_intent(question: str) -> dict:
    q = question.lower()

    # -------- COMPANY INFO -----------
    if "cổ đông" in q:
        return {"intent": "company_info", "info_type": "shareholders"}
    if "ban lãnh đạo" in q or "lãnh đạo" in q:
        return {"intent": "company_info", "info_type": "officers"}
    if "công ty con" in q:
        return {"intent": "company_info", "info_type": "subsidiaries"}

    # ---------- COMPARE --------------
    if "so sánh" in q and "volume" in q:
        return {"intent": "compare_volume"}
    if "so sánh" in q or "thấp nhất" in q:
        return {"intent": "compare_price"}

    # ---------- TECHNICAL ------------
    if "sma" in q or "rsi" in q:
        return {"intent": "technical"}

    # ---------- OHLCV / VOLUME -------
    if "ohlcv" in q or "giá" in q or "volume" in q or "khối lượng" in q:
        return {"intent": "ohlcv"}

    return {"intent": "unknown"}

# ==============================================
# 2. Extract Useful Fields
# ==============================================

def extract_symbols(question: str):
    return re.findall(r'\b[A-Z]{2,4}\b', question)

def extract_resolution(question: str):
    q = question.lower()
    if "1m" in q:
        return "1m"
    if "1d" in q or "daily" in q:
        return "1d"
    return "1d"

def extract_date_query(question: str):
    """
    Cực kỳ quan trọng: GIỮ NGUYÊN CHUỖI GỐC TIẾNG VIỆT
    vì tools.py parse bằng regex tiếng Việt.
    """
    keywords = [
        "ngày", "tuần", "tháng",
        "gần nhất", "gần đây",
        "từ đầu", "đầu tháng"
    ]
    for kw in keywords:
        if kw in question.lower():
            # Lấy nguyên cụm có từ này
            idx = question.lower().index(kw)
            return question[idx-10:].strip()

    return question  # fallback

def extract_indicators(question: str):
    inds = []
    for sma in re.findall(r'sma\s*([0-9]+)', question.lower()):
        inds.append(f"SMA_{sma}")
    for rsi in re.findall(r'rsi\s*([0-9]+)', question.lower()):
        inds.append(f"RSI_{rsi}")
    return inds

# ==============================================
# 3. RESOLUTION MAP
# ==============================================

RESOLUTION_MAP = {
    '1d': '1D', 'daily': '1D',
    '1m': '1m',
    '5m': '5m', '15m': '15m',
    '30m': '30m',
    '1h': '1H',
}

# ==============================================
# 4. MAIN AGENT RESPONSE
# ==============================================

def get_agent_response(question: str) -> str:
    if not question.strip():
        return "Câu hỏi trống."

    intent = classify_intent(question)
    symbols = extract_symbols(question)

    # ticker1 / ticker2 cho compare
    symbol1 = symbols[0] if len(symbols) > 0 else None
    symbol2 = symbols[1] if len(symbols) > 1 else None

    date_query = extract_date_query(question)
    resolution = extract_resolution(question)
    indicators = extract_indicators(question)

    # ÁP DỤNG RESOLUTION MAP
    resolution = RESOLUTION_MAP.get(resolution.lower(), "1D")

    # ===============================================================
    # 5. MAP INTENT → TOOL CALL
    # ===============================================================

    tool_call = None

    # -------- COMPANY INFO ----------
    if intent["intent"] == "company_info":
        tool_call = {
            "name": "get_company_info",
            "arguments": {
                "symbol": symbol1,
                "info_type": intent["info_type"]
            }
        }

    # -------- COMPARE PRICE --------
    elif intent["intent"] == "compare_price":
        tool_call = {
            "name": "compare_stock_prices",
            "arguments": {
                "symbols": symbols,
                "date_query": date_query,
                "metric": "open"
            }
        }

    # -------- COMPARE VOLUME --------
    elif intent["intent"] == "compare_volume":
        tool_call = {
            "name": "compare_stock_volumes",
            "arguments": {
                "symbol1": symbol1,
                "symbol2": symbol2,
                "date_query": date_query
            }
        }

    # -------- TECHNICAL INDICATORS ----
    elif intent["intent"] == "technical":
        tool_call = {
            "name": "get_stock_analysis",
            "arguments": {
                "symbol": symbol1,
                "date_query": date_query,
                "indicators": indicators,
                "resolution": resolution
            }
        }

    # -------- OHLCV / VOLUME ----------
    elif intent["intent"] == "ohlcv":
        tool_call = {
            "name": "get_stock_analysis",
            "arguments": {
                "symbol": symbol1,
                "date_query": date_query,
                "indicators": [],
                "resolution": resolution
            }
        }

    else:
        return "Không hiểu yêu cầu."

    # ===============================================================
    # 6. RUN TOOL DIRECTLY
    # ===============================================================

    tool = next((t for t in all_tools if t.metadata.name == tool_call["name"]), None)
    result = tool.fn(**tool_call["arguments"])

    if "###DATA" in result:
        data = result.split("###DATA")[1].split("###END_DATA")[0].strip()
        return f"Dưới đây là bảng dữ liệu:\n```\n{data}\n```"

    return result



from llama_index.core.tools import FunctionTool
from vnstock import Quote, Company
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import pandas as pd
import re
import json
import logging
from typing import List, Dict, Union, Tuple

logging.getLogger("vnstock").setLevel(logging.ERROR)
DATA_SOURCE = 'TCBS'


# === sma and rsi ===


def _calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Tính toán SMA (Simple Moving Average)"""
    return series.rolling(window=period).mean()

def _calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Tính toán RSI (Relative Strength Index)"""
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def _parse_date_range(query: str) -> Tuple[str, str, int]:
    """
    Hàm helper quan trọng: Chuyển đổi một câu truy vấn thời gian
    bằng ngôn ngữ tự nhiên (ví dụ: "10 ngày qua", "từ đầu tháng 11")
    thành (start_date, end_date, num_days).
    """
    query = str(query).lower()
    today = datetime.now()
    end_date = today.strftime('%Y-%m-%d')
    start_date = None
    num_days = 30 # Default

    m_days = re.search(r'(\d+)\s*ngày', query)
    m_weeks = re.search(r'(\d+)\s*tuần', query)
    m_months = re.search(r'(\d+)\s*tháng', query)
    m_month_start = re.search(r'(từ|từ đầu|đầu) tháng\s+(\d{1,2})', query)

    if m_days:
        num_days = int(m_days.group(1))
        start_date = (today - timedelta(days=num_days)).strftime('%Y-%m-%d')
    elif m_weeks:
        num_days = int(m_weeks.group(1)) * 7
        start_date = (today - timedelta(weeks=int(m_weeks.group(1)))).strftime('%Y-%m-%d')
    elif m_months:
        num_days = int(m_months.group(1)) * 30
        start_date = (today - relativedelta(months=int(m_months.group(1)))).strftime('%Y-%m-%d')
    elif m_month_start:
        month = int(m_month_start.group(2))
        year = today.year if month <= today.month else today.year - 1
        start_date = f"{year}-{month:02d}-01"
        num_days = (today - datetime.strptime(start_date, '%Y-%m-%d')).days
    else:

        start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')

    return start_date, end_date, num_days


# === company and trading data ===


def _get_history_data(symbol: str, start: str, end: str, interval: str = '1D') -> pd.DataFrame:
    """Helper: Lấy và cache dữ liệu lịch sử, xử lý lỗi."""
    try:
        quote = Quote(symbol=symbol.upper(), source=DATA_SOURCE)
        df = quote.history(start=start, end=end, interval=interval)
        if df.empty:
            raise ValueError(f"Không có dữ liệu cho mã {symbol} trong khoảng thời gian này.")
        df = df.reset_index()
        df['time'] = pd.to_datetime(df['time']).dt.strftime('%Y-%m-%d')
        return df
    except Exception as e:
        logging.error(f"Lỗi _get_history_data cho {symbol}: {e}")
        return pd.DataFrame() 

def _get_company_data(symbol: str, info_type: str) -> pd.DataFrame:
    try:
        company = Company(symbol=symbol.upper(), source=DATA_SOURCE)

        if info_type == 'shareholders':
            df = company.shareholders()

            if df is None or df.empty:
                return pd.DataFrame(columns=[
                    "id", "share_holder", "quantity", "share_own_percent", "update_date"
                ])

            rename_map = {
                "holder_name": "share_holder",
                "own_percent": "share_own_percent",
                "own_quantity": "quantity",
                "last_update": "update_date",
                "update": "update_date"
            }
            df = df.rename(columns=rename_map)

            # ensure schema
            for col in ["id", "share_holder", "quantity", "share_own_percent", "update_date"]:
                if col not in df.columns:
                    df[col] = None

            return df[["id", "share_holder", "quantity", "share_own_percent", "update_date"]]

        elif info_type == 'officers':
            return company.officers()

        elif info_type == 'subsidiaries':
            return company.subsidiaries()

        else:
            raise ValueError("Loại thông tin không hợp lệ.")

    except Exception as e:
        logging.error(f"Lỗi _get_company_data cho {symbol} ({info_type}): {e}")
        return pd.DataFrame()

# ==============================================================================
# === 3. TOOLS DÀNH CHO AGENT (AGENT TOOLS) ===
# ==============================================================================


def get_stock_analysis(symbol: str, date_query: str, indicators: List[str] = None, resolution: str = '1D') -> str:
    """
    Tool chính: Lấy dữ liệu OHLCV, tính tổng Volume VÀ các chỉ báo kỹ thuật
    (SMA, RSI...) cho một mã cổ phiếu dựa trên truy vấn thời gian
    (ví dụ: "10 ngày qua", "2 tuần", "từ đầu tháng 11").
    """
    try:
        # 1. Parse thời gian
        start_date, end_date, num_days = _parse_date_range(date_query)
        
        # 2. Lấy dữ liệu
        # Cần lấy thêm dữ liệu quá khứ để tính indicators (ví dụ SMA20 cần 20 ngày)
        # Lấy thêm 3 tháng dữ liệu làm "buffer"
        buffer_start_date = (datetime.strptime(start_date, '%Y-%m-%d') - relativedelta(months=3)).strftime('%Y-%m-%d')
        df = _get_history_data(symbol, buffer_start_date, end_date, resolution)
        if df.empty: return f"Không tìm thấy dữ liệu cho {symbol}."

        # 3. Tính toán
        total_volume = df[df['time'] >= start_date]['volume'].sum()
        
        cols_to_display = ['time', 'open', 'high', 'low', 'close', 'volume']
        indicator_warnings = []

        if indicators:
            for ind in indicators:
                ind = ind.upper()
                if ind.startswith('SMA_'):
                    period = int(ind.split('_')[1])
                    df[ind] = _calculate_sma(df['close'], period)
                elif ind.startswith('RSI_'):
                    period = int(ind.split('_')[1])
                    df[ind] = _calculate_rsi(df['close'], period)
                
                if ind not in cols_to_display:
                    cols_to_display.append(ind)
                
                # Check cảnh báo RSI
                if ind.startswith('RSI_'):
                    rsi_val = df[ind].iloc[-1]
                    if rsi_val > 70: indicator_warnings.append(f"CẢNH BÁO: {ind} = {rsi_val:.1f} > 70 (Quá mua)")
                    elif rsi_val < 30: indicator_warnings.append(f"CẢNH BÁO: {ind} = {rsi_val:.1f} < 30 (Quá bán)")

        # 4. Lọc lại đúng khung thời gian
        df_display = df[df['time'] >= start_date].tail(num_days * 2) # Hiển thị 2* số ngày cho chắc
        
        # 5. Format Output
        table = df_display[cols_to_display].round(2).to_string(index=False, float_format="{:,.0f}".format)
        
        output = f"###DATA\n"
        output += f"Kết quả cho {symbol.upper()} (từ {start_date} đến {end_date}):\n"
        output += f"Tổng khối lượng (Volume): {total_volume:,.0f} cổ phiếu.\n\n"
        output += f"Dữ liệu chi tiết:\n{table}\n"
        if indicator_warnings:
            output += "\n" + "\n".join(indicator_warnings) + "\n"
        output += "###END_DATA"
        return output

    except Exception as e:
        return f"Lỗi khi phân tích {symbol}: {e}"


def get_company_info(symbol: str, info_type: str) -> str:
    """
    Lấy thông tin cơ bản của công ty.
    info_type phải là một trong: 'shareholders' (cổ đông), 'officers' (lãnh đạo), 'subsidiaries' (công ty con).
    """
    if info_type not in ['shareholders', 'officers', 'subsidiaries']:
        return "Lỗi: info_type không hợp lệ. Phải là 'shareholders', 'officers', hoặc 'subsidiaries'."

    try:
        df = _get_company_data(symbol, info_type)
        if df.empty:
            return f"Không có dữ liệu {info_type} cho {symbol}."

        output = ""
        # Xử lý đặc biệt cho 'officers' để lấy tên
        if info_type == 'officers':
            working = df[df['type'] == 'đang làm việc'] if 'type' in df.columns else df
            table = working[['officer_name', 'position']].head(10).to_string(index=False)
            names = ', '.join(working['officer_name'].dropna().tolist())
            output = f"###DATA\n{table}\nTên (toàn bộ): {names}\n###END_DATA"
        else:
            table = df.head(10).to_string(index=False)
            output = f"###DATA\n{table}\n###END_DATA"
        
        return output
    except Exception as e:
        return f"Lỗi khi lấy thông tin {info_type} cho {symbol}: {e}"


def compare_stock_prices(symbols: List[str], date_query: str, metric: str = 'open') -> str:
    """
    So sánh giá (open, high, low, close) của nhiều mã và tìm mã thấp nhất/cao nhất.
    metric: 'open', 'high', 'low', 'close'.
    """
    try:
        start_date, end_date, _ = _parse_date_range(date_query)
        results = {}
        
        for s in symbols:
            df = _get_history_data(s.upper(), start_date, end_date, '1D')
            if not df.empty:
                results[s.upper()] = df[metric].min() # Tìm giá MỞ CỬA thấp nhất
            else:
                results[s.upper()] = None
        
        valid = {k: v for k, v in results.items() if v is not None}
        if not valid: return "Không có dữ liệu cho bất kỳ mã nào."
        
        min_symbol = min(valid, key=valid.get)
        min_value = valid[min_symbol]
        
        summary = "\n".join([f"Mã {s}: {v:,.0f} VND" if v else f"Mã {s}: Không có dữ liệu" for s, v in results.items()])
        
        return f"###DATA\n{summary}\n\nMã có giá {metric} thấp nhất: {min_symbol} ({min_value:,.0f} VND)\n###END_DATA"
    except Exception as e:
        return f"Lỗi so sánh giá: {e}"


def compare_stock_volumes(symbol1: str, symbol2: str, date_query: str) -> str:
    """So sánh tổng khối lượng giao dịch (volume) của 2 mã cổ phiếu."""
    try:
        start_date, end_date, _ = _parse_date_range(date_query)
        
        df1 = _get_history_data(symbol1.upper(), start_date, end_date, '1D')
        df2 = _get_history_data(symbol2.upper(), start_date, end_date, '1D')
        
        if df1.empty or df2.empty:
            return "Không có đủ dữ liệu để so sánh."
            
        v1 = df1['volume'].sum()
        v2 = df2['volume'].sum()
        
        return f"###DATA\n{symbol1.upper()}: {v1:,.0f}\n{symbol2.upper()}: {v2:,.0f}\n###END_DATA"
    except Exception as e:
        return f"Lỗi so sánh volume: {e}"


# === 4. DANH SÁCH TOOLS (FINAL) ===


all_tools = [
    FunctionTool.from_defaults(
        fn=get_stock_analysis,
        name="get_stock_analysis",
        description=(
            "Tool chính để lấy dữ liệu OHLCV, Tổng Volume, HOẶC tính các chỉ báo kỹ thuật (SMA, RSI) cho MỘT mã cổ phiếu."
            " Sử dụng cho các câu hỏi về giá, khối lượng, hoặc chỉ báo của 1 mã."
            "\n"
            "HƯỚNG DẪN THAM SỐ:\n"
            "1. `symbol`: Mã cổ phiếu (ví dụ: 'HPG', 'VIC').\n"
            "2. `date_query`: PHẢI là chuỗi (string) thời gian GỐC bằng TIẾNG VIỆT lấy TỪ CÂU HỎI. "
            "   KHÔNG ĐƯỢC dịch sang tiếng Anh, KHÔNG ĐƯỢC tự ý đổi thành ngày tháng (YYYY-MM-DD)."
            "   VÍ DỤ ĐÚNG: '10 ngày gần nhất', 'từ đầu tháng 11', '1 tuần gần đây', '2 tháng'.\n"
            "3. `indicators`: PHẢI là một DANH SÁCH (list) các CHUỖI (string). "
            "   - Định dạng là 'TEN_SO', ví dụ: ['SMA_9', 'SMA_20', 'RSI_14']. "
            "   - Nếu câu hỏi chỉ lấy OHLCV hoặc Volume (như Câu 1, 2, 4 trong file test), hãy truyền vào một DANH SÁCH RỖNG: [].\n"
            "4. `resolution`: Khung thời gian. Mặc định là '1D'. Chỉ thay đổi nếu người dùng yêu cầu rõ (ví dụ: '1m', '1H')."
        )
    ),
    FunctionTool.from_defaults(
        fn=get_company_info,
        name="get_company_info",
        description=(
            "Lấy thông tin cơ bản của công ty (cổ đông, lãnh đạo, công ty con)."
            "\n"
            "HƯỚNG DẪN THAM SỐ:\n"
            "1. `symbol`: Mã cổ phiếu (ví dụ: 'VCB').\n"
            "2. `info_type`: PHẢI là MỘT TRONG BA chuỗi (string) sau: 'shareholders', 'officers', hoặc 'subsidiaries'."
            "   - Dùng 'shareholders' cho câu hỏi về 'cổ đông lớn'."
            "   - Dùng 'officers' cho câu hỏi về 'ban lãnh đạo', 'lãnh đạo đang làm việc', 'tên các lãnh đạo'."
            "   - Dùng 'subsidiaries' cho câu hỏi về 'công ty con'."
            "   KHÔNG ĐƯỢC dùng bất kỳ giá trị nào khác (ví dụ: 'management_board' là SAI)."
        )
    ),
    FunctionTool.from_defaults(
        fn=compare_stock_prices,
        name="compare_stock_prices",
        description=(
            "So sánh giá (open, high, low, close) của NHIỀU mã (từ 2 mã trở lên) và tìm mã thấp nhất."
            " Chỉ dùng khi câu hỏi yêu cầu so sánh GIÁ."
            "\n"
            "HƯỚNG DẪN THAM SỐ:\n"
            "1. `symbols`: PHẢI là một DANH SÁCH (list) các mã, ví dụ: ['BID', 'TCB', 'VCB'].\n"
            "2. `date_query`: PHẢI là chuỗi (string) thời gian GỐC bằng TIẾNG VIỆT. "
            "   VÍ DỤ ĐÚNG: '10 ngày qua'. KHÔNG ĐƯỢC dùng '10 days ago'.\n"
            "3. `metric`: Loại giá để so sánh. Dùng 'open' cho 'giá mở cửa'."
        )
    ),
    FunctionTool.from_defaults(
        fn=compare_stock_volumes,
        name="compare_stock_volumes",
        description=(
            "So sánh tổng khối lượng giao dịch (volume) của 2 mã cổ phiếu."
            " Chỉ dùng khi câu hỏi yêu cầu so sánh VOLUME."
            "\n"
            "HƯỚNG DẪN THAM SỐ:\n"
            "1. `symbol1`, `symbol2`: Hai mã cổ phiếu cần so sánh.\n"
            "2. `date_query`: PHẢI là chuỗi (string) thời gian GỐC bằng TIẾNG VIỆT. "
            "   VÍ DỤ ĐÚNG: '2 tuần gần đây'."
        )
    ),
]


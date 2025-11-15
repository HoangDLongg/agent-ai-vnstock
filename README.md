# Financial AI Agent for Vietnam Stock Market

## Giới thiệu

Dự án này xây dựng một **AI Agent** có khả năng hiểu câu hỏi tiếng Việt
và tự động gọi API để trả lời các truy vấn liên quan đến:

-   Giá cổ phiếu (OHLCV)
-   Khối lượng giao dịch
-   Chỉ báo kỹ thuật (SMA, RSI,...)
-   Thông tin doanh nghiệp (cổ đông, ban lãnh đạo, công ty con)
-   So sánh nhiều mã chứng khoán

Agent sử dụng:

-   **Ollama + LLaMA 3.1**
-   **VnStock API (free)**
-   **LlamaIndex FunctionTool**
-   **FastAPI** để triển khai REST API

------------------------------------------------------------------------

## Cách chạy dự án

### 1️Cài đặt yêu cầu

    pip install -r requirements.txt

### 2️Chạy Ollama

    ollama pull llama3.1:8b

### 3️Chạy server FastAPI

    uvicorn main:app --reload

API mặc định chạy tại:

    http://localhost:8000/ask

------------------------------------------------------------------------

## Cách hoạt động của Agent

Khi người dùng hỏi:

    Tính cho tôi SMA9 của VIC trong 2 tuần

Agent sẽ:

1.  Hiểu người dùng hỏi SMA9 → cần chỉ báo kỹ thuật\
2.  Trích ra mã chứng khoán → "VIC"\
3.  Trích ra thời gian → "2 tuần"\
4.  Gọi tool xử lý\
5.  Nhận kết quả dạng bảng\
6.  Trả về cho người dùng

------------------------------------------------------------------------

## Các Tool tích hợp

### get_stock_analysis

Lấy OHLCV + Volume + SMA/RSI

### get_company_info

Lấy:

-   `shareholders`
-   `officers`
-   `subsidiaries`

### compare_stock_prices

So sánh giá nhiều mã

###  compare_stock_volumes

So sánh volume 2 mã

------------------------------------------------------------------------

## API Usage (REST)

### Endpoint

    POST /ask

### Input JSON

``` json
{
  "question": "Lấy dữ liệu OHLCV 10 ngày gần nhất của HPG"
}
```

### Output JSON

``` json
{
  "answer": "Dưới đây là bảng dữ liệu: ..."
}
```

------------------------------------------------------------------------

## Ví dụ câu hỏi hỗ trợ

  Loại câu hỏi   Ví dụ
  -------------- ----------------------------------------
  OHLCV          Lấy dữ liệu OHLCV 10 ngày gần nhất HPG
  Giá            Lấy giá đóng cửa VCB từ đầu tháng 11
  So sánh giá    BID, TCB, VCB mở cửa thấp nhất?
  Volume         Tổng volume VIC trong 1 tuần
  Company        Danh sách cổ đông lớn của VCB
  SMA            SMA9 của VIC
  RSI            RSI14 của TCB

------------------------------------------------------------------------

## 📦 Cấu trúc dự án

    .
    ├── main.py
    ├── agent.py
    ├── tools.py
    ├── test.py
    ├── requirements.txt
    └── README.md

------------------------------------------------------------------------

## 🧪 Test Script

    python test.py

------------------------------------------------------------------------

## 💬 Liên hệ & mở rộng

Bạn có thể mở rộng:

-   Thêm MACD, Bollinger Bands\
-   Thêm dự báo\
-   Kết nối FireAnt, SSI, TCBS API khác

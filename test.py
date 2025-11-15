

import requests
import json
import time

API_URL = "http://localhost:8000/ask"

TEST_CASES = [
    # 1 OHLCV
    "Lấy dữ liệu OHLCV 10 ngày gần nhất HPG?",
    
    # 2 Giá đóng cửa
    "Lấy giá đóng của của mã VCB từ đầu tháng 11 theo khung 1d?",
    
    # 3 Compare price
    "Trong các mã BID, TCB và VCB mã nào có giá mở cửa thấp nhất trong 10 ngày qua?",
    
    # 4 Volume 1 mã
    "Tổng khối lượng giao dịch (volume) của mã VIC trong vòng 1 tuần gần đây?",
    
    # 5 Compare volume
    "So sánh khối lượng giao dịch của VIC với HPG trong 2 tuần gần đây?",
    
    # 6 Cổ đông lớn
    "Danh sách cổ đông lớn của VCB",
    
    # 7 Lãnh đạo
    "Danh sách ban lãnh đạo đang làm việc của VCB",
    
    # 8 Công ty con
    "Các công ty con thuộc VCB",
    
    # 9 Tên lãnh đạo
    "Lấy cho tôi toàn bộ tên các lãnh đạo đang làm việc của VCB",
    
    # 10 SMA9
    "Tính cho tôi SMA9 của mã VIC trong 2 tuần với timeframe 1d",
    
    # 11 SMA9 + SMA20
    "Tính cho tôi SMA9 và SMA20 của mã VIC trong 2 tháng với timeframe 1d",
    
    # 12 RSI14
    "Tính cho tôi RSI14 của TCB trong 1 tuần với timeframe 1m",
    
    # 13 SMA9 & SMA20 từ đầu tháng 11
    "Tính SMA9 và SMA20 của mã TCB từ đầu tháng 11 đến nay",
]

def run_test_case(question):
    try:
        response = requests.post(API_URL, json={"question": question})
        data = response.json()

        if "answer" not in data:
            return False, "Không có trường 'answer' trong JSON."

        answer = data["answer"]

        if "Lỗi" in answer or "error" in answer.lower():
            return False, answer

        if "Dưới đây là bảng dữ liệu" not in answer:
            return False, "Không thấy bảng dữ liệu trong câu trả lời."

        return True, answer

    except Exception as e:
        return False, f"Lỗi: {e}"

def main():
    results = []
    print("\n===== BẮT ĐẦU KIỂM THỬ AGENT =====\n")

    for i, question in enumerate(TEST_CASES, 1):
        print(f"[TEST {i}] {question}")
        success, output = run_test_case(question)

        if success:
            print(" → PASS\n")
        else:
            print(" → FAIL:", output[:200], "\n")

        results.append((i, question, success, output))
        time.sleep(0.5)

    # Ghi file log
    with open("test_results.txt", "w", encoding="utf-8") as f:
        for i, q, ok, out in results:
            f.write(f"=== TEST {i} ===\n")
            f.write(f"Question: {q}\n")
            f.write(f"Result: {'PASS' if ok else 'FAIL'}\n")
            f.write(f"Answer:\n{out}\n\n")

    print("===== HOÀN TẤT =====\nKết quả đã lưu vào test_results.txt\n")

if __name__ == "__main__":
    main()

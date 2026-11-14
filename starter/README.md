# Day 06 — Pipeline nạp dữ liệu

## Corpus

Bài làm sử dụng bài báo của Ariane Burel, *Equidistribution of curves in hypersurfaces of low degree*, phiên bản arXiv:2611.17120v1:

- Nguồn và phiên bản: <https://arxiv.org/abs/2611.17120>
- PDF: <https://arxiv.org/pdf/2611.17120>
- PDF có 98 trang vật lý. Manifest đưa vào các trang 1 và 3–95 (94 trang nội dung), loại trang mục lục và tài liệu tham khảo.
- PDF được giữ cục bộ tại `data/arxiv_2611.17120.pdf` và bị Git bỏ qua. Hồ sơ arXiv ghi giấy phép phân phối không độc quyền, không phải giấy phép CC chung; không phân phối lại PDF hoặc các đoạn trích xuất đầy đủ nếu chưa kiểm tra điều khoản.
- `data/manifest.json` ghi nguồn, giấy phép, quy tắc chọn trang và metadata section. `benchmark/questions.json` có 15 câu dev / 5 câu test cùng evidence đã kiểm tra theo trang. Tập test không được dùng để chọn chiến lược.

Nếu chưa có PDF trong thư mục dữ liệu, tải bằng PowerShell:

```powershell
Invoke-WebRequest -Uri "https://arxiv.org/pdf/2611.17120" -OutFile ".\data\arxiv_2611.17120.pdf"
```

## Cài đặt và chạy (Windows PowerShell)

Chạy các lệnh sau từ thư mục `starter/`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py
python -m src.run
python -m unittest discover -s tests
```

Pipeline dùng model embedding cục bộ thật `sentence-transformers/all-MiniLM-L6-v2` (384 chiều), chạy trên CPU và dùng cùng cách embedding cho tài liệu lẫn câu hỏi. Vector store là PostgreSQL + pgvector, tìm kiếm cosine chính xác. Model được tải ở lần chạy đầu; không cần API key và không phát sinh phí dịch vụ. Nếu tải model hoặc thao tác database thất bại, chương trình báo lỗi, không chuyển sang vector giả.

## Chiến lược và kết quả

- **A:** cửa sổ cố định 800 ký tự, overlap 100 ký tự, không lọc khi truy xuất.
- **B:** chia theo đoạn, tối đa 1.200 ký tự, không lọc khi truy xuất.
- **C:** dùng cùng chunk và embedding với B; chỉ áp dụng filter metadata `section` khi câu hỏi chỉ rõ phạm vi.

Cả ba chiến lược dùng cùng corpus, model và câu hỏi. Chương trình chọn cấu hình dựa trên Evidence Hit@3 của dev, tiếp đến Hit@1 của dev, rồi thời gian ingest. Quyết định được ghi lại trước khi chạy truy xuất trên tập test.

`results/metrics.json` chứa Hit@1 / Evidence Hit@3 tự động; `results/ingestion_summary.json` ghi thông tin corpus, model, tài nguyên và filter. `results/traces.jsonl` chứa đầy đủ văn bản top-3 và bị Git bỏ qua vì có trích nội dung nguồn. Các file `results/coherence_audit.csv`, `results/grounding_audit.csv` và `results/metadata_audit.csv` là phiếu chấm thủ công; hãy điền điểm và lý do sau khi kiểm tra tài liệu cùng trace. Ô trống không được xem là kết quả đã chấm. Quy tắc chọn và diễn giải kết quả cũng được ghi trong báo cáo cá nhân.

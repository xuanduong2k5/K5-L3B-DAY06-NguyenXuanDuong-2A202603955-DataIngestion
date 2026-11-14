# Báo cáo cá nhân — Ngày 6

## Dữ liệu và pipeline
- **Chủ đề:** Đại số hình học. Ariane Burel, *Equidistribution of curves in hypersurfaces of low degree*, [arXiv:2611.17120v1](https://arxiv.org/abs/2611.17120).
- **Nguồn và quyền sử dụng:** Bài báo được phát hành theo giấy phép phân phối không độc quyền của arXiv (không phải giấy phép CC). PDF được lưu cục bộ; không đưa PDF hoặc trace chứa toàn văn các chunk lên Git. Cần kiểm tra điều khoản trước khi phân phối nội dung trích xuất.
- **Số trang:** PDF có 98 trang vật lý; sử dụng trang 1 và 3–95 (94 trang nội dung trích xuất được), loại trang mục lục 2 và tài liệu tham khảo 96–98. Văn bản sau chuẩn hóa có 180.529 ký tự theo pypdf 6.21.4; không cần OCR.
- **Chuẩn hóa:** Dùng pypdf và Unicode NFKC, bỏ soft hyphen, nối các từ bị ngắt dòng; giữ ID tài liệu, trang vật lý và mục section. Manifest: `starter/data/manifest.json`.
- **Embedding:** Model cục bộ `sentence-transformers/all-MiniLM-L6-v2`, chạy CPU, 384 chiều; áp dụng cùng cách mã hóa cho tài liệu và câu hỏi. Đã kiểm tra vector câu hỏi có 384 chiều và được chuẩn hóa L2. Chi phí API: 0 USD.
- **Vector store:** PostgreSQL 16.16 + pgvector 0.8.7, chạy từ Docker image `pgvector/pgvector:0.8.7-pg16`; dùng cosine distance và tìm kiếm chính xác.
- **Metadata:** `document_id`, `source`, `page`, `section`. Giá trị section lấy từ mục lục bài báo và được dùng làm filter khi câu hỏi nêu rõ phạm vi.
- **Hỗ trợ AI:** AI hỗ trợ viết pipeline, soạn câu hỏi và chấm sơ bộ coherence/grounding theo rubric. Metadata được đối chiếu với manifest bằng script. Các nhãn không phải đánh giá độc lập của học viên; học viên cần rà soát trước khi nộp như kết quả chấm thủ công.

## Cấu hình và bộ benchmark
- **A:** Chia theo cửa sổ cố định 800 ký tự, chồng lấp 100 ký tự; không lọc khi truy xuất.
- **B:** Chia theo đoạn văn, tối đa 1.200 ký tự; không lọc khi truy xuất.
- **C:** Dùng cùng chunk và embedding như B; chỉ thêm filter `section` khi câu hỏi cung cấp phạm vi.
- **Bộ câu hỏi:** 20 câu (15 dev / 5 test), gồm 8 câu có filter (4 dev / 4 test). Evidence của cả 20 câu đã được đối chiếu tự động với đúng trang PDF. File: `starter/benchmark/questions.json`.
- **Tiêu chí chọn cấu hình:** Đã chốt trước khi chạy: ưu tiên dev Evidence Hit@3, tiếp đến dev Hit@1, sau đó là thời gian ingest. Tập test chỉ được chạy sau khi ghi quyết định chọn; không dùng test để điều chỉnh cấu hình.

## Kết quả truy xuất

| Chiến lược | Tập dữ liệu | Hit@1 (số câu/tổng) | Evidence Hit@3 (số câu/tổng) | Số chunk | Thời gian ingest | Chi phí |
|---|---|---:|---:|---:|---:|---:|
| A | dev | 4/15 | 7/15 | 293 | 7,244 giây | 0 USD API |
| A | test | 0/5 | 3/5 | — | — | 0 USD API |
| B | dev | 6/15 | 6/15 | 198 | 4,735 giây | 0 USD API |
| B | test | 0/5 | 2/5 | — | — | 0 USD API |
| C | dev | 7/15 | 8/15 | 198 | 0,074 giây* | 0 USD API |
| C | test | 1/5 | 4/5 | — | — | 0 USD API |

| Chiến lược | Điểm mạch lạc chunk trung bình /2 (n) | Metadata đầy đủ và chính xác (n/tổng) | Câu hỏi tuân thủ filter (n/tổng) | Điểm grounding 0/1/2 |
|---|---|---|---|---|
| A | 1,2/2 (10) | 15/15 | 1/8 câu có filter | 1,6/2 |
| B | 1,3/2 (10) | 15/15 | 1/8 câu có filter | 1,2/2 |
| C | 1,3/2 (10) | 13/13 | 8/8 câu có filter | 1,8/2 |

### Chi tiết chấm coherence

Chấm cùng 10 trang vật lý đã chọn trước khi xem điểm; thang 0–2 theo GUIDE.md. Điểm từng chiến lược theo thứ tự trang mẫu:

| Trang PDF | A | B | C | Lý do ngắn |
|---:|---:|---:|---:|---|
| 1 | 2 | 2 | 2 | Abstract nêu bối cảnh, kết quả và phương pháp trong một đoạn hoàn chỉnh. |
| 12 | 1 | 2 | 2 | A bị cắt giữa phát biểu Theorem C; B/C giữ được phát biểu và kết luận, dù thiếu một phần thiết lập trước đó. |
| 23 | 1 | 1 | 1 | Đoạn bắt đầu giữa câu; ký hiệu và sơ đồ chuỗi khớp bị mất/ngắt nên chỉ hiểu được một phần. |
| 33 | 2 | 2 | 2 | Heuristic nêu đối tượng, cách đếm và suy ra công thức chiều dự kiến theo mạch rõ ràng. |
| 43 | 1 | 1 | 1 | Mảnh chứng minh có lập luận và kết quả nhưng dựa vào bổ đề/định nghĩa ở trước. |
| 54 | 1 | 1 | 1 | So sánh phương pháp có thể theo dõi, nhưng dựa vào tài liệu tham khảo và ngữ cảnh mục trước. |
| 64 | 1 | 1 | 1 | Có giải thích các bước biến đổi, song mở đầu nhắc đến một phát biểu chưa có trong chunk và ký hiệu dày đặc. |
| 74 | 0 | 0 | 0 | Bắt đầu giữa bất đẳng thức; chủ thể và phần lập luận cần thiết bị thiếu, công thức trích xuất khó diễn giải độc lập. |
| 85 | 2 | 2 | 2 | Tiêu đề trường hợp, điều kiện và các bước ước lượng được giữ liên tục. |
| 95 | 1 | 1 | 1 | Đoạn viện dẫn “công thức thứ hai” và “công thức thứ nhất” nhưng thiếu phần đã nêu trước đó. |

### Chi tiết chấm grounding trên tập test

Điểm 0 = top-3 không có bằng chứng; 1 = có liên quan nhưng thiếu điều kiện/ngữ cảnh; 2 = đủ bằng chứng và truy được nguồn. Đây là đánh giá độ đủ của evidence truy xuất, không phải độ chính xác câu trả lời do LLM tạo ra.

| Câu | A | B | C | Nhận xét |
|---|---:|---:|---:|---|
| T01 — Bất đẳng thức dùng để khống chế minor arcs | 2 | 1 | 2 | A/C có trang 70 nêu trực tiếp global Weyl inequality; B chỉ có ngữ cảnh về minor arcs và các phiên bản Weyl ở trang khác. |
| T02 — Định nghĩa ρ từ các ρᵢ | 2 | 2 | 2 | Cả ba top-3 đều chứa trang 75 với định nghĩa ρ là giá trị lớn nhất của các ρᵢ. |
| T03 — Nhóm dùng để lấy thương không gian tham số | 2 | 1 | 1 | A có trang 10 mô tả phép chiếu theo Gₘ,P\|S; B/C chỉ có thông tin lấy thương Gₘ tổng quát, thiếu chỉ định cần thiết. |
| T04 — Công thức chiều của Homᵉ(C,V\|{φ}) | 2 | 2 | 2 | Cả ba top-3 đều có công thức (4.3.16) ở trang 94. |
| T05 — Kết quả của bài báo khi e đủ lớn | 0 | 0 | 2 | A/B không truy xuất abstract hay đoạn nêu đủ hai kết quả; C có abstract trang 1 nêu rõ chiều và phân rã thành phần bất khả quy. |

Trung bình grounding tính trên 5 câu test: A = (2+2+2+2+0)/5 = 1,6; B = (1+2+1+2+0)/5 = 1,2; C = (2+2+1+2+2)/5 = 1,8. Bảng chi tiết từng chunk và lý do được lưu trong các phiếu audit tại `starter/results/`.

### Kiểm tra metadata

Đối chiếu tất cả bản ghi top-3 thực tế với manifest theo `source`, trang vật lý và `section`: 43/43 bản ghi đúng và đủ (A 15/15, B 15/15, C 13/13). C chỉ trả một kết quả cho T05 sau filter nên tổng số bản ghi kiểm tra là 43, không phải 45. `source` và `page` giúp truy ngược về tài liệu/trang; `section` hỗ trợ giới hạn phạm vi. Hạn chế: section phụ thuộc cách gán mục trong manifest và filter đúng phạm vi không bảo đảm top-3 chứa đúng evidence.

*C dùng lại embedding của B; 0,074 giây chỉ là thời gian ghi/cập nhật dữ liệu nên không thể so sánh trực tiếp với thời gian ingest của A và B. Ở lần chạy cuối, thời gian nạp model là 10,326 giây. Đã chạy ingest lặp lại; số chunk không đổi và không bị trùng: A có 293/293 ID duy nhất, B có 198/198, C có 198/198.

Theo tiêu chí đã chốt, chọn **C** từ kết quả dev: Evidence Hit@3 đạt 8/15, so với A 7/15 và B 6/15. Sau đó, trên test, C đạt 4/5, A đạt 3/5 và B đạt 2/5. Với 8 câu có filter, filter section của C tuân thủ 8/8 câu. Đây là mức tuân thủ filter tự động, không thay thế việc kiểm tra thủ công tính chính xác của metadata.

Trace và phiếu đánh giá nằm trong `starter/results/`. Trace đầy đủ và mẫu coherence bị Git bỏ qua vì có chứa nội dung trích xuất từ nguồn. Các điểm và lý do trong phiếu được AI hỗ trợ chấm theo rubric; cần học viên xác nhận lại với nguồn trước khi coi là đánh giá thủ công.

## Phân tích và kết luận
- **So sánh A–B:** Kết quả chưa nghiêng hẳn về một cách chia chunk. A có Evidence Hit@3 cao hơn B trên dev và test (lần lượt 7/15, 3/5 so với 6/15, 2/5), nhưng B có Hit@1 dev cao hơn (6/15 so với 4/15). Mẫu coherence có AI hỗ trợ chấm cho thấy B đạt 1,3/2, A đạt 1,2/2; chênh lệch nhỏ và chỉ dựa trên 10 vị trí.
- **So sánh B–C:** Hai cấu hình chỉ khác filter. Trên corpus này, C tăng Evidence Hit@3 thêm 2 câu ở dev và 2 câu ở test. Ví dụ lỗi: câu T03 được lọc đúng vào Section 4 nhưng top-3 vẫn bỏ sót trang gold 83; lọc đúng phạm vi chưa đảm bảo tìm được evidence phù hợp. Với T05, filter Abstract giúp C tìm được trang 1, trong khi A/B trả về chunk ở các phần khác.
- **Kết luận:** C được chọn cho benchmark này, không phải khuyến nghị tổng quát. C đạt grounding trung bình cao nhất trong mẫu test (1,8/2) và tuân thủ filter 8/8; tuy nhiên, T03 vẫn thiếu bằng chứng chính xác dù filter đúng. Tập test chỉ có 5 câu, và điểm coherence/grounding hiện là đánh giá có AI hỗ trợ chứ chưa được học viên xác nhận độc lập. Trích xuất công thức toán từ PDF, cỡ mẫu nhỏ và khả năng sai khác khi chấm là các giới hạn của kết quả.

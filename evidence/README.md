# Báo cáo Lab Day 22 — LangSmith + Prompt Versioning

## Thông tin học viên

- Họ và tên: **Lê Văn Tài**
- MSSV: **2A202602464**
- Chủ đề: **LLMOps Prompt Versioning**

## Phạm vi đã hoàn thiện

1. **RAG Pipeline + LangSmith tracing**
   - Knowledge base được chia bằng `RecursiveCharacterTextSplitter` với `chunk_size=500`, `chunk_overlap=50`.
   - Chunks được index bằng FAISS.
   - RAG chain dùng retriever → prompt → LLM → `StrOutputParser`.
   - Hàm `ask()` dùng `@traceable(name="rag-query", tags=["rag", "step1"])`.

2. **Prompt Hub + A/B routing**
   - V1: trả lời ngắn gọn, chỉ dựa trên context.
   - V2: phân tích có cấu trúc, vẫn chỉ dựa trên context.
   - Hai prompt dùng tên riêng của học viên, được push và pull từ LangSmith Prompt Hub.
   - Routing dùng MD5 của `request_id`, nên cùng một request luôn nhận cùng phiên bản.

3. **RAGAS Evaluation**
   - Cả 50 cặp QA được chạy qua V1 và V2.
   - Dataset dùng đủ `user_input`, `response`, `retrieved_contexts`, `reference`.
   - Báo cáo gồm `faithfulness`, `answer_relevancy`, `context_recall`, `context_precision` cho cả hai phiên bản.
   - V1: faithfulness **0.9571**, answer relevancy **0.9091**, context recall **1.0000**, context precision **0.9450**.
   - V2: faithfulness **0.9656**, answer relevancy **0.8966**, context recall **1.0000**, context precision **0.9450**.

4. **Guardrails validators**
   - `PIIDetector` dùng regex để phát hiện email, số điện thoại, SSN và số thẻ tín dụng.
   - PII được thay thế bằng nhãn an toàn qua `FailResult(fix_value=...)` và `OnFailAction.FIX`.
   - `JSONFormatter` xử lý markdown fences, nháy đơn, trailing comma và có JSON fallback khi không thể sửa.

## Phân tích V1 và V2

V1 ưu tiên câu trả lời ngắn nên đạt answer relevancy cao hơn (**0.9091** so với **0.8966** của V2). V2 yêu cầu xác định facts liên quan và trình bày có cấu trúc, giúp faithfulness cao hơn (**0.9656** so với **0.9571** của V1). Cả hai prompt đều đạt context recall **1.0000** và context precision **0.9450**; cả hai faithfulness đều vượt **0.9**, đạt điểm thưởng. Cả hai prompt đều giữ `{context}` và cấm suy đoán ngoài tài liệu để bảo toàn faithfulness.

## Xác minh LangSmith

- Project: `le-van-tai-day22`
- Lần xác minh API ban đầu: **50 traces `rag-query`** và **50 traces `ab-rag-query`** (đủ 100 traces theo yêu cầu).
- Sau khi chạy lại bước RAG, giao diện LangSmith hiện **100 traces `rag-query`**; ảnh mới phản ánh số đếm này.
- Prompt Hub: `le-van-tai-2a202602464-rag-prompt-v1` và `le-van-tai-2a202602464-rag-prompt-v2` đã push và pull thành công.
- LangSmith project URL: https://smith.langchain.com/o/8b6ad29b-b395-4e91-8603-5675154851ab/projects/p/b93e897a-3131-45ef-b57d-a977b4681063
- `01_langsmith_traces.png` là ảnh chụp trực tiếp giao diện project LangSmith với bộ lọc `rag-query` và `Trace Count 100`.
- `01_langsmith_trace_detail.png` là ảnh chụp một trace thật: câu hỏi nằm trong `Input`, đoạn knowledge base truy xuất hiển thị trong `VectorStoreRetriever → Output`.
- `01_langsmith_trace_shared.png` là ảnh chụp trạng thái `Trace Shared`, xác nhận trace đã tạo public link.
- `02_prompt_hub.png` là ảnh chụp trực tiếp Prompt Hub, hiển thị cả hai prompt V1 và V2. Bốn ảnh giao diện được chụp lại rõ nét và chuyển định dạng JPEG → PNG mà không sửa nội dung.
- Các ảnh LangSmith cũng được chụp với thanh bên thu gọn để tránh lộ email cá nhân. Quyền truy cập project của tài khoản khác chưa được xác minh.

## Danh mục bằng chứng

- `01_langsmith_traces.png`: ảnh LangSmith project có 100 trace `rag-query` sau khi chạy lại.
- `01_langsmith_trace_detail.png`: ảnh trace mẫu với context truy xuất (bổ sung).
- `02_prompt_hub.png`: ảnh Prompt Hub có cả hai prompt.
- `02_ab_routing_log.txt`: log A/B có cả nhãn `prompt-v1` và `prompt-v2`.
- `03_ragas_scores.png`: biểu đồ dựng từ số liệu thật trong `ragas_report.json`; đây là ảnh tổng hợp, không phải ảnh chụp terminal.
- `03_ragas_report.json`: bản sao của `data/ragas_report.json`.
- `04_pii_demo_log.txt`: tối thiểu 5 ca PII.
- `04_json_demo_log.txt`: tối thiểu 4 ca JSON.

> Không ghi API key vào Git. Chỉ điền key trong `.env` local; file này đã nằm trong `.gitignore`.

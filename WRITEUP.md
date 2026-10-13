# NimbusAI — Báo Cáo Tối Ưu Hóa Chi Phí GPU (FinOps Technical Write-up)

> **Tác giả:** Trịnh Quốc Hoàng — MSSV: 2A202602847  
> **Dự án:** NimbusAI GPU FinOps Optimization (Lab 25 — Track 2)  
> **Thời điểm snapshot:** Tháng 6/2026  

---

## 1. Tổng quan Chi phí: Baseline vs. Optimized

Trong vai trò FinOps Lead tại NimbusAI, bài toán đặt ra là cắt giảm hóa đơn GPU đang mất kiểm soát mà không làm suy giảm chất lượng dịch vụ hoặc vi phạm SLA. Việc đánh giá chi phí được chuẩn hóa theo đơn vị **`$/1M-token`** (thay vì chi phí giờ máy `$/GPU-hr`) nhằm phản ánh chính xác hiệu suất sinh lời trên mỗi đơn vị token thực tế được phục vụ.

| Chỉ số kinh tế | Baseline (Trước tối ưu) | Optimized (Sau tối ưu) | Mức cải thiện / Tiết kiệm |
|---|---|---|---|
| **Tổng chi phí GPU / tháng** | **$27,133** | **$14,626** | **Giảm $12,507 (46.1%)** |
| **Chi phí Inference / ngày** | $48.87 / ngày | $8.48 / ngày | Giảm $40.39 / ngày (82.6%) |
| **Đơn giá phục vụ (`$/1M-token`)** | **$6.488 / 1M-token** | **$1.126 / 1M-token** | **Giảm 82.6%** |
| **Chi phí Purchasing / tháng** | $25,667 / tháng | $15,627 / tháng | Giảm $10,040 / tháng (39.1%) |
| **Lãng phí Idle qua đêm / tháng** | $3,750 / tháng | $0 / tháng | Tiệt trừ 100% lãng phí nhàn rỗi |

---

## 2. Phân tích Chi tiết Từng Đòn Bẩy Tài Chính (Savings Breakdown)

Khoản tiết kiệm **$12,507/tháng** đến từ sự phối hợp của 4 đòn bẩy:

1. **Purchasing Strategy (Spot & Reserved) — Đóng góp lớn nhất ($10,040/tháng ~ 80.3% tổng savings):**
   * *Nguyên nhân dẫn đầu:* Công ty tiêu tốn phần lớn chi phí vào các cụm GPU lớn (H100, A100) cho training và inference liên tục.
   * *Cơ chế:* 
     * Các job huấn luyện ngắt quãng được (`job-train-llm`, `job-batch-eval`, v.v.) được chuyển sang **Spot Instance** với cơ chế checkpointing định kỳ. Dù chịu phụ phí checkpoint 3% và rủi ro chạy lại 5% do thu hồi máy, chi phí vẫn giảm hơn 36–40% so với On-Demand.
     * Các workload inference phục vụ online 24/7 (`job-infer-chat`, `job-infer-rag`) có duty cycle đạt 100% (vượt xa điểm hòa vốn 55% của Reserved discount 45%), giúp hưởng trọn mức giảm giá 45% khi cam kết Reserved 3 năm.
2. **Inference Optimization Levers ($1,212/tháng):**
   * *Cơ chế:* Kết hợp Cascade Routing (chuyển 80% prompt đơn giản sang model nhỏ rẻ hơn 15–37 lần), Prompt Caching (giảm 90% giá input cho các system prompt lặp lại), và Batch API (giảm 50% cho các job chạy ngầm như nightly eval).
   * Nhân dồn chiết khấu đạt mức tối đa lên tới 95% giá gốc cho các query vừa batch vừa cache.
3. **Right-sizing GPU-Util Lies ($655/tháng):**
   * Hạ cấp GPU bị over-provisioned (`gpu-h100-4`) từ H100 ($2.50/h) xuống A100 ($1.79/h) do GPU này thực chất chỉ đạt MFU ~20%, giúp tiết kiệm $0.71/h liên tục.
4. **Kill Idle GPUs ($600/tháng tính trong mô hình report, thực tế telemetry phát hiện $3,750/tháng):**
   * Thu hồi các GPU bị treo hoặc nhàn rỗi không giải phóng tài nguyên sau khi train xong qua đêm (điển hình là `gpu-h100-5`).

---

## 3. Bản chất của "GPU-Util Lie" và Tác động Tài chính

* **Phát hiện:** Trong fleet telemetry, GPU `gpu-h100-4` ghi nhận chỉ số `gpu_util_pct = 98.0%`, nhưng **MFU (Model FLOPs Utilization) chỉ đạt 0.202 (20.2%)**.
* **Bản chất kỹ thuật:** Lệnh `nvidia-smi` đo GPU Utilization dựa trên tỷ lệ thời gian mà GPU kernel có hoạt động trên vi xử lý (clock active). Chỉ số này **hoàn toàn không phản ánh hiệu suất tính toán thực tế**. 
  * Hiện tượng "GPU-Util Lie" xảy ra khi GPU bận nhưng không sinh ra FLOPs có ích, chủ yếu do:
    1. **Memory Stall / Bandwidth Bottleneck:** Workload rơi vào trạng thái memory-bound (Arithmetic Intensity thấp hơn Ridge Point ~295 FLOP/byte của H100). Nhân Tensor Cores phải nhàn rỗi chờ nạp dữ liệu từ HBM/DRAM.
    2. **Kernel Launch Overhead & Small Batch Size:** Kernel khởi chạy với kích thước batch quá nhỏ, thời gian CPU dispatch và đồng bộ hóa lấn át thời gian tính toán thực tế.
* **Tác động tài chính:** NimbusAI đang thanh toán $2.50/h cho phần cứng đỉnh cao H100 nhưng chỉ thu lại hiệu năng tương đương một GPU cấp thấp (A10G hoặc L4). Điều này tạo ra ảo giác "hạ tầng đang quá tải cần mua thêm GPU", dẫn đến việc tiếp tục đầu tư lãng phí hàng nghìn USD mỗi tháng.

---

## 4. Phần Mở Rộng Kỹ Thuật Đã Triển Khai (Extensions 3 & 4)

### 4.1 Extension 3: Mô hình Điểm Hòa Vốn Prompt Caching (`cache_is_worth_it`)
* **Vấn đề thực tế:** Prompt Caching không miễn phí. Các nhà cung cấp (Google Gemini, Anthropic) tính phí tạo/ghi cache (thường bằng 1.25× giá input) và phí lưu trữ theo giờ. Nếu một prompt chỉ được đọc 1 lần rồi bỏ, caching sẽ gây lỗ ròng.
* **Công thức toán học:**
  $$\text{Break-even Reads} = \frac{\text{Write Cost}}{\text{Base Input Price} \times (1 - \text{Read Discount})} = \frac{1.25 \times P_{in}}{P_{in} \times (1 - 0.10)} \approx 1.389\text{ lần đọc}$$
* **Kết quả đo lường trên dataset:**
  * Ngưỡng hòa vốn: Cần đọc lại **$\ge 1.39$ lần** (từ 2 lần đọc trở lên).
  * Trong `token_usage.csv`, các system prompt được tái sử dụng trung bình **480.0 lần đọc/prefix** (trên 5 nhóm prefix).
  * Kết luận: `cache_is_worth_it()` trả về `True`, khẳng định chính sách caching tại NimbusAI mang lại lợi nhuận biên cực kỳ cao và an toàn để áp dụng toàn diện.

### 4.2 Extension 4: Quản trị Ngân sách Reasoning (Reasoning Budget & Sustainability)
* **Vấn đề thực tế:** Các truy vấn reasoning (suy luận chuỗi CoT) sản sinh output tokens dài gấp 6 lần và tiêu hao năng lượng gấp **80 lần** truy vấn tiêu chuẩn (`REASONING_ENERGY_MULTIPLIER = 80.0`).
* **Đo lường định lượng trên thực tế:**
  * **Tỷ trọng traffic:** 201 requests (**8.4%** tổng số truy vấn).
  * **Tỷ trọng chi phí:** $1.40/ngày — chiếm **16.5%** tổng hóa đơn inference tối ưu.
  * **Tỷ trọng năng lượng:** Tiêu thụ **29,787.7 Wh/ngày** — chiếm tới **94.0% tổng điện năng toàn hệ thống inference!**
* **Đề xuất Quy tắc Routing (Policy Proposal):**
  * Thiết lập bộ lọc độ phức tạp: Chỉ kích hoạt reasoning khi query thuộc nhóm tác vụ phân tích logic/toán phức tạp hoặc đánh giá chuyên sâu (`eval`); 100% câu hỏi giao tiếp thông thường bị chặn tính năng reasoning.
  * Nếu khống chế (cap) lưu lượng reasoning ở mức 5% tổng traffic, hệ thống sẽ tiết kiệm thêm **~$0.45/ngày** và cắt giảm tới **~11,854.0 Wh/ngày**, giảm phát thải CO₂ vượt trội.

---

## 5. Khuyến Nghị Chiến Lược Dành Cho FinOps Lead NimbusAI

Dựa trên dữ liệu định lượng, 3 hành động ưu tiên cao nhất theo tỷ suất hoàn vốn (ROI) gồm:

1. **Triển khai Auto-Shutdown Daemon & Spot Checkpointing:**
   * Tự động phát hiện và thu hồi GPU có utilization < 10% kéo dài quá 30 phút nhằm triệt tiêu ngay $3,750/tháng lãng phí nhàn rỗi.
   * Chuẩn hóa thư viện lưu checkpoint định kỳ cho mọi pipeline ML để chuyển 100% job training ngắt quãng sang Spot Instance.
2. **Áp dụng Bắt buộc Cascade Router & Prefix Caching Gateway:**
   * Đặt API Gateway phía trước mọi endpoint: 80% traffic không yêu cầu reasoning sẽ được tự động điều hướng sang model `small`.
   * Cố định tiền tố System Prompt cho `chat` và `doc-qa` nhằm tối đa hóa tỷ lệ trúng cache, duy trì chi phí ở ngưỡng $1.126/1M-token.
3. **Chuyển dịch Vùng Điện Toán Carbon-Aware (Sang `europe-north1`):**
   * Di dời các cụm GPU training từ `us-east-1` sang vùng Na Uy (`europe-north1`): Giá điện rẻ hơn (0.09 so với 0.12 USD/kWh) và phát thải carbon giảm từ 380 gCO₂/kWh xuống 30 gCO₂/kWh (giảm 92% dấu chân carbon), giúp đạt chuẩn Net Zero và tiết kiệm chi phí vận hành.

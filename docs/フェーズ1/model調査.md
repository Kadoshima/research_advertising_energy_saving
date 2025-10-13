受け取ったよ。添付の**「TinyMLモデル選定調査」**を確認した上で、すぐ動ける形に要点だけ固めるね。

# 要約（結論先出し）

* **第一候補**：**DS-CNN**（≈**987 params / 30k FLOPs / ~5 ms** @ESP32 240 MHz）。省メモリ・高効率で、精度もベースCNNと同等レンジ。Phase-1の本命。
* **高精度寄り代替**：**DeepConv-LSTM**（≈**10.6k params / 0.45 M FLOPs / ~20 ms**）。精度最優先ならこれ。制約内で収まる。
* **運用最適化の布石**：**Early-Exit CNN（AHAR型）**（早期出口~**5 ms**/フル~**18 ms**）。平均遅延・消費削減に効くのでPhase-2以降に導入。
* **ベースライン**：1D-CNN（**2.3k params / 89k FLOPs / ~7 ms**）。比較・回帰テスト用。
* **制約充足**：全候補とも **RAM≤80 KB / Flash≤200 KB / FLOPs≤8 M / t_inf≤20 ms** クリア。BLE 100 msアドバタイズ間に推論を完了可。

# これで進める（実装・評価プラン）

1. **モデル確定（Phase-1）**

* 本線：**DS-CNN** を採択。DeepConv-LSTMは“精度最重視プロファイル”として併走。

2. **データと学習**

* 入力：**50 Hz × 1.0 s窓 / 50%重畳 / 6ch IMU**。w-HAR/Opportunityを主、PAMAP2/MHEALTHを補助で一般化検証。前処理・QAT・温度スケーリングまで含む。

3. **デバイス展開（TFLM/int8）**

* .tflite生成→C配列化→**Tensor Arena ≤80 KB**でロード→**ESP32-S3/C3**にビルド。推論時間は`esp_timer_get_time()`で1000反復計測。

4. **電力・遅延計測**

* GPIOトグルで区間マーキングしつつ、**イベント電荷(μC/推論)・平均電流**を測定（推論時約数十mW想定）。BLE広告は100/500/2000 msで実験し、**Pout(τ)**とのトレードオフを整理。

5. **アウトプット（納品形）**

* **モデルカード×3（DS-CNN/DeepConv-LSTM/1D-CNN）**：構造図・Params/RAM/Flash/FLOPs/実測t_inf/μC/推奨ユース。
* **比較CSV**：`model, params, ram_kb, flash_kb, flops_m, t_inf_ms, f1_macro, event_uC, pout_1s`。
* **図**：F1–FLOPs前線、Pout(τ)曲線、エネルギ箱ひげ。

# すぐやるタスク（順番に）

* [ ] **DS-CNN** 学習 → QAT → .tflite化（代表データ含む）→ ESP32で**実測t_inf**取得。
* [ ] 同手順で **DeepConv-LSTM**（精度側ベンチ）→ 実測比較。
* [ ] **BLE 100/500/2000 ms**での**到達遅延×電力**のミニ実験（推論を“広告間隔内”で完結できることの確認）
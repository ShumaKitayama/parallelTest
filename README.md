# parallelTest

このシステムは、複数の Docker コンテナ上で Python スクリプト（Worker.py）を並行稼働させ、  
2次元積分の計算を分割して処理することで、**並列計算によるスピードアップ**を図る仕組みです。  
また、ベンチマーク用スクリプト (Benchmark.py) を外部プロセスとして起動し、  
CPU・メモリ使用量や経過時間などを計測します。

---

## 機能概要

1. **Master.py**  
   - ホストマシン上で起動するメイン制御スクリプト。  
   - `task.json` から計算式・積分範囲・ステップ幅を読み込み、範囲をワーカー数で分割。  
   - `docker-compose` を使って Redis コンテナと複数の Worker コンテナを立ち上げる。  
   - Redis キューにタスクを投入し、Worker の計算結果を回収して集約。  
   - ベンチマーク用サブプロセス (Benchmark.py) を起動し、開始/終了タイミングを制御。  
   - 結果を `output/output.txt`、ベンチマーク情報を `output/benchmark.txt` に書き出す。  
   - 処理が完了したら Worker にシャットダウン指示を送信し、Docker コンテナも停止する。

2. **Worker.py**  
   - Docker コンテナ上で起動し、Redis から「どの範囲を計算するか」を受け取る。  
   - Benchmark.py が「計測開始」を通知するまで重い計算をブロック。  
   - 計算完了後、結果を Redis キューに返す。  
   - 最後に Master から「シャットダウン」指令を受け取って終了する。

3. **Benchmark.py**  
   - ホストマシン上で Master.py からサブプロセスとして起動される。  
   - `stop` が来るまで計測を続け、最終的に CPU・メモリ使用量や経過時間などを JSON 形式で標準出力。  
   - Master.py は標準出力を受け取り、ファイルに書き出す。

4. **task.json**  
   - 積分式 (`equation`) や `x_start`, `x_end`, `y_start`, `y_end`, `step` など  
     計算に必要なパラメータを保存する JSON ファイル。

5. **docker-compose.yml**  
   - Redis コンテナ (redis:latest) と Worker コンテナ (Dockerfile でビルド) を管理。  
   - `--scale` オプションによって Worker の台数を柔軟に変更できる。

6. **Dockerfile**  
   - Worker.py を実行するための Python 環境 (redis, numpy など) をインストールし、  
     `/app/Worker.py` をコピーする。

7. **出力ファイル**  
   - `output/output.txt`: 計算結果 (数値)  
   - `output/benchmark.txt`: ベンチマーク結果 (JSON 形式)

---

## ディレクトリ構成（例）

```bash
.
├── Master.py
├── Worker.py
├── Benchmark.py
├── Dockerfile
├── docker-compose.yml
├── task.json
└── output
    ├── output.txt
    └── benchmark.txt
```

---

## 実行手順

1. **環境準備**  
   - ホストマシン上で Python (3.x) 仮想環境などを用意し、  
     `pip install redis psutil` など必要ライブラリをインストールする。  
   - Docker / Docker Compose がインストールされていることを確認。

2. **task.json の内容を設定**  
   - 積分する式 (`equation`)、範囲 (`x_start`, `x_end`, `y_start`, `y_end`)、ステップ幅 (`step`) を調整する。

3. **必要に応じて Dockerfile の修正**  
   - `RUN pip install redis numpy` など、Worker に必要なパッケージを追加する。  
   - 変更後は `docker-compose build` または `docker build .` でイメージを再ビルド。

4. **Master.py の起動**  
   ```bash
   python Master.py
   ```
   - 自動的に `docker-compose up -d --scale worker=4` を実行し、Redis + Worker 4台を起動。  
   - 5秒程度待機したのち、タスクを Redis に投入。  
   - Benchmark.py をサブプロセスで起動し、「計測開始」の合図を Worker に送る。  
   - Worker が計算を終えて結果を返すと、集計して `output/output.txt` に書き出し。  
   - Benchmark.py を停止 (`stop` を送信) → 出力を JSON で受け取り → `output/benchmark.txt` に書き出し。  
   - Worker に「シャットダウン」を送信 → Docker を停止。

5. **結果の確認**  
   - `output/output.txt` に最終的な積分結果が数値として出力。  
   - `output/benchmark.txt` にベンチマーク（経過時間、CPU/メモリ使用量など）が JSON で出力。

6. **ワーカー台数の変更**  
   - `Master.py` の `worker_count` を変更するか、  
     あるいは `docker-compose up -d --scale worker=N` を直接使ってワーカー台数を増減し、  
     並列度合いを変えた時の計算時間短縮やリソース消費の違いを評価できる。

---

## 注意点

1. **計算量とステップ幅**  
   - 2次元積分の場合、`step` が小さいほどループ回数が膨大になり、結果が返ってくるまで数分～数十分以上かかる場合あり。  
   - 最初はやや大きめのステップ幅 (たとえば 0.01 など) で動作確認するとよい。


3. **Redis の起動タイミング**  
   - Docker コンテナ内で Redis が立ち上がる前に Master.py が接続すると `ConnectionRefusedError` が出るため、  
     適度な待機 (`time.sleep()`) や再トライ処理を入れている。

4. **スケールアウト**  
   - `docker-compose.yml` で `container_name:` を指定しないこと。  
     指定したまま `--scale` するとコンテナ名が重複しエラーになる。  
   - `benchmark_channel` や `task_channel` への `rpush` 回数をワーカー台数と合わせるなど、  
     チャンネル通信用の実装ロジックを厳密にしておく。

---

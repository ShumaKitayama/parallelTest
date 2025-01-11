import subprocess
import json
import time
import redis
import math

TASK_CHANNEL = "task_queue"
RESULT_CHANNEL = "result_queue"
BENCHMARK_CHANNEL = "benchmark_channel"

def run_docker_compose_up(worker_count):
    """
    docker-compose を起動して指定数のworkerを立ち上げる。
    """
    print(f"[Master] Starting {worker_count} workers...")
    # --scale worker=4 のようにして起動
    subprocess.run(["docker-compose", "up", "-d", "--scale", f"worker={worker_count}"])

def stop_docker_compose():
    """
    docker-compose を停止（コンテナ削除）する。
    """
    print("[Master] Stopping docker-compose...")
    subprocess.run(["docker-compose", "down"])

def main():
    # 1. task.json 読み込み
    with open("task.json", "r") as f:
        task = json.load(f)
    equation = task["equation"]
    x_start = task["x_start"]
    x_end = task["x_end"]
    y_start = task["y_start"]
    y_end = task["y_end"]
    step = task["step"]

    # 2. Docker起動（例えばワーカー4台）
    worker_count = 7
    run_docker_compose_up(worker_count)

    # 3. Docker 起動の安定化待ち
    time.sleep(5)

    # Redis に接続
    r = redis.Redis(host="localhost", port=6379, db=0)

    # 4. 範囲分割：例として x 軸を worker 数で分割
    x_range_length = (x_end - x_start)
    range_per_worker = x_range_length / worker_count

    # ワーカーに送るタスクをキューへ積む
    for i in range(worker_count):
        partial_x_start = x_start + i * range_per_worker
        partial_x_end = x_start + (i+1) * range_per_worker
        task_data = {
            "equation": equation,
            "x_start": partial_x_start,
            "x_end": partial_x_end,
            "y_start": y_start,
            "y_end": y_end,
            "step": step
        }
        r.rpush(TASK_CHANNEL, json.dumps(task_data))
    print(f"[Master] {worker_count} tasks pushed to Redis.")

    # 5. Benchmark.py 起動 (サブプロセス; 標準入出力をパイプ)
    benchmark_process = subprocess.Popen(
        ["python", "Benchmark.py"], 
        stdin=subprocess.PIPE, 
        stdout=subprocess.PIPE,
        text=True
    )

    # ベンチマークが起動するのを少し待つ（任意・環境次第）
    time.sleep(2)

    # 6. Worker に計算開始合図 ("start" を BENCHMARK_CHANNEL に投げる)
    for _ in range(worker_count):
        r.rpush(BENCHMARK_CHANNEL, "start")
    print("[Master] Sent 'start' signal to Workers.")

    # 7. ワーカー結果を受信
    partial_sum = 0.0
    results_received = 0
    while results_received < worker_count:
        result_data = r.blpop(RESULT_CHANNEL, timeout=0)  # (RESULT_CHANNEL, JSON文字列) のタプル
        if result_data:
            _, result_json_str = result_data
            result_json = json.loads(result_json_str)
            partial_sum += result_json["partial_result"]
            results_received += 1

    print("[Master] All partial results collected.")

    # 8. ベンチマーク終了を指示
    benchmark_process.stdin.write("stop\n")
    benchmark_process.stdin.flush()

    # Benchmark.py の全標準出力をまとめて受け取る（communicate）
    benchmark_output, _ = benchmark_process.communicate()

    # 最後の行が JSON 出力である想定。複数行ログがあっても、最後だけパースすればOK。
    lines = benchmark_output.strip().splitlines()
    last_line = lines[-1]  # 一番最後の行
    benchmark_data = json.loads(last_line)

    # 念のためプロセス終了を待つ
    benchmark_process.wait()

    # 9. 計算結果をファイル出力
    with open("output/output.txt", "w") as f:
        f.write(str(partial_sum))

    # 10. ベンチマーク結果をファイル出力
    with open("output/benchmark.txt", "w") as f:
        f.write(json.dumps(benchmark_data, indent=2))

    print(f"[Master] Final Result = {partial_sum}")
    print(f"[Master] Benchmark Data = {benchmark_data}")

    # 11. Worker への終了指示 (shutdown)
    for _ in range(worker_count):
        r.rpush(TASK_CHANNEL, json.dumps({"command": "shutdown"}))

    time.sleep(5)  # ワーカー停止待機

    # 12. Docker停止
    stop_docker_compose()

    print("[Master] Done.")

if __name__ == "__main__":
    main()
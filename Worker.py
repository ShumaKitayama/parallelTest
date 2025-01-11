import os
import time
import redis
import json

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

TASK_CHANNEL = "task_queue"
RESULT_CHANNEL = "result_queue"
BENCHMARK_CHANNEL = "benchmark_channel"

def compute_integral(equation, x_start, x_end, y_start, y_end, step):
    """
    2次元積分を (x_start, x_end) x (y_start, y_end) の範囲で
    単純な数値積分（リーマン和）を行う例。
    """
    # セキュリティ簡略化のため eval を使うサンプル（本番環境では注意）
    total = 0.0
    x = x_start
    while x < x_end:
        y = y_start
        while y < y_end:
            val = eval(equation, {"x": x, "y": y, "__builtins__": {}})
            total += val * (step * step)
            y += step
        x += step
    return total

def main():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

    # タスク受信待ち
    print("[Worker] Waiting for task...")
    while True:
        # タスクをブロックしながら待つ
        task_data = r.blpop(TASK_CHANNEL, timeout=0)
        # task_data は (TASK_CHANNEL, JSON文字列) のタプルで帰ってくる
        if task_data:
            _, task_json_str = task_data
            task_json = json.loads(task_json_str)

            # もし "shutdown" タスクが来たら終了
            if task_json.get("command") == "shutdown":
                print("[Worker] Received shutdown signal. Exiting.")
                break

            # Benchmark.py の計測開始合図を待つ
            print("[Worker] Task received. Waiting for benchmark start signal...")
            benchmark_started = False
            while not benchmark_started:
                # benchmark_channel に "start" が投げられるまで待機
                msg = r.blpop(BENCHMARK_CHANNEL, timeout=0)
                if msg:
                    _, benchmark_cmd = msg
                    benchmark_cmd = benchmark_cmd.decode("utf-8")
                    if benchmark_cmd == "start":
                        benchmark_started = True
                        print("[Worker] Benchmark start signal received.")
            
            # 計算実行
            equation = task_json["equation"]
            x_start = task_json["x_start"]
            x_end = task_json["x_end"]
            y_start = task_json["y_start"]
            y_end = task_json["y_end"]
            step = task_json["step"]

            partial_result = compute_integral(equation, x_start, x_end, y_start, y_end, step)

            # 結果を Redis に返送
            result_data = {
                "worker_id": os.getenv("HOSTNAME"),  # コンテナIDやホスト名を送る例
                "partial_result": partial_result
            }
            r.rpush(RESULT_CHANNEL, json.dumps(result_data))
            print("[Worker] Computation done and result pushed.")
    
    print("[Worker] Terminated.")

if __name__ == "__main__":
    main()

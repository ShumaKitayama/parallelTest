import time
import json
import psutil
import sys

def main():
    # --- 計測開始 ---
    start_time = time.time()
    start_cpu_times = psutil.cpu_times_percent(interval=None)
    process = psutil.Process()
    start_mem_info = process.memory_info().rss

    print("[Benchmark] Measurement started...")
    print("[Benchmark] CPU/Memory usage measurement will end when 'stop' is received from Master.")

    # --- Master.py から "stop" が来るまで待機 ---
    while True:
        line = sys.stdin.readline().strip()
        if line == "stop":
            break
        time.sleep(0.1)

    # --- 計測終了 ---
    end_time = time.time()
    end_cpu_times = psutil.cpu_times_percent(interval=None)
    end_mem_info = process.memory_info().rss

    elapsed_time = end_time - start_time

    # シンプルに "user+system" の差分を一例として計算
    cpu_usage = (end_cpu_times.user - start_cpu_times.user) \
              + (end_cpu_times.system - start_cpu_times.system)

    # メモリはピークを正確にとるにはループ処理が必要ですが、ここでは開始・終了時の大きい方とする簡易例
    mem_usage = max(start_mem_info, end_mem_info)

    # --- 途中ログを出力 ---
    print(f"[Benchmark] Elapsed time (seconds): {elapsed_time:.3f}")
    print(f"[Benchmark] CPU usage diff (rough %): {cpu_usage:.3f}")
    print(f"[Benchmark] Memory usage (bytes): {mem_usage}")

    # --- 最後に JSON を出力 (Master.py はこの行をパースする) ---
    benchmark_data = {
        "elapsed_time_sec": elapsed_time,
        "cpu_usage_percent_diff": cpu_usage,
        "memory_usage_bytes": mem_usage
    }
    print(json.dumps(benchmark_data))

if __name__ == "__main__":
    main()
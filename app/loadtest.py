import argparse
import threading
import time
import requests

"""
Нагрузочный тест анти-бомбер-модуля: шлёт поток запросов на локальный
эмулятор шлюза и показывает, сколько прошло, сколько отклонено.
"""

def worker(url, phone, n, results):
    for _ in range(n):
        try:
            r = requests.post(url, json={"phone": phone}, timeout=5)
            results[r.status_code] = results.get(r.status_code, 0) + 1
        except Exception as e:
            results["err"] = results.get("err", 0) + 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:20129/sms/request")
    p.add_argument("--phone", default="79160000000")
    p.add_argument("--rate", type=int, default=20, help="запросов всего")
    p.add_argument("--threads", type=int, default=4)
    args = p.parse_args()

    results = {}
    threads = []
    per = max(1, args.rate // args.threads)
    t0 = time.time()
    for _ in range(args.threads):
        t = threading.Thread(target=worker, args=(args.url, args.phone, per, results))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

    print(f"Потрачено {time.time()-t0:.1f} c. Результаты по HTTP-кодам:")
    for code, n in sorted(results.items(), key=lambda x: str(x[0])):
        print(f"  {code}: {n}")
    print("200 = пропущено защитой, 429 = отклонено, 400 = неверный номер.")


if __name__ == "__main__":
    main()

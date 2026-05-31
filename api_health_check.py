import requests
import time
from datetime import datetime


URLS = [
    "https://jsonplaceholder.typicode.com/posts",
    "https://httpbin.org/status/500",
    "https://httpbin.org/delay/3"
]

HEADERS = {
    "Authorization": "Bearer fake-token-123"
}


def log(message):
    with open("api_log.txt", "a") as f:
        f.write(message + "\n")


def call_api(url):
    attempts = 0
    delays = [1, 2, 4]
    start = time.time()

    while attempts < 3:
        attempts += 1
        try:
            resp = requests.get(
                url,
                headers=HEADERS,
                timeout=5
            )

            status = resp.status_code

            # handle HTTP errors
            if 400 <= status < 600:
                raise Exception(f"HTTP {status}")

            log(f"{datetime.now()} | {url} | {status} | attempt {attempts} | SUCCESS")

            return {
                "url": url,
                "status": status,
                "attempts": attempts,
                "time": round(time.time() - start, 2)
            }

        except requests.exceptions.Timeout:
            log(f"{datetime.now()} | {url} | TIMEOUT | attempt {attempts} | FAIL")

        except requests.exceptions.ConnectionError:
            log(f"{datetime.now()} | {url} | CONNECTION ERROR | attempt {attempts} | FAIL")

        except Exception as e:
            log(f"{datetime.now()} | {url} | {str(e)} | attempt {attempts} | FAIL")

        # backoff delay before retry
        if attempts < 3:
            time.sleep(delays[attempts - 1])

    return {
        "url": url,
        "status": "FAILED",
        "attempts": attempts,
        "time": round(time.time() - start, 2)
    }


# ---------------- MAIN ----------------

results = []

for url in URLS:
    result = call_api(url)
    results.append(result)


# -------- SUMMARY TABLE --------

print("\nSUMMARY")
print("-" * 70)
print(f"{'URL':50} {'STATUS':10} {'ATTEMPTS':10} {'TIME(s)':10}")

for r in results:
    print(f"{r['url'][:48]:50} {str(r['status']):10} {r['attempts']:10} {r['time']:10}")
# Cloud Security Toolkit — Lab Scripts

---

## Repository Structure

```
.
├── api_health_check.py     # Resilient API health checker with retry + exponential backoff
├── flag_anomalies.py       # Statistical transaction anomaly detector
├── api_log.txt             # Generated at runtime — structured log of all API calls
├── transactions.csv        # Input data for flag_anomalies.py (you provide this)
├── flagged.json            # Generated at runtime — anomaly report output
└── README.md
```

---

## Script 1 — `api_health_check.py`

### What It Does

Checks the health of a list of HTTP endpoints, handles failures gracefully, and produces a structured audit log. Designed around the same resilience patterns used in production AWS Lambda health checks and CloudWatch Synthetics canaries.

### Key Behaviours

| Behaviour | Detail |
|---|---|
| Retry logic | Up to 3 attempts per URL before marking as `FAILED` |
| Backoff schedule | 1s → 2s → 4s (exponential, hardcoded in `delays` list) |
| Timeout enforcement | 5-second hard timeout per request |
| Error classification | Distinguishes Timeout, ConnectionError, and HTTP 4xx/5xx |
| Structured logging | Appends every attempt to `api_log.txt` with timestamp, URL, status, attempt number, and outcome |
| Summary table | Prints a formatted table to stdout after all checks complete |

### Log Format

Each line written to `api_log.txt` follows this structure:

```
<ISO timestamp> | <url> | <status or error> | attempt <n> | <SUCCESS or FAIL>
```

Example:
```
2025-05-30 14:22:01.443211 | https://jsonplaceholder.typicode.com/posts | 200 | attempt 1 | SUCCESS
2025-05-30 14:22:06.991432 | https://httpbin.org/status/500 | HTTP 500 | attempt 1 | FAIL
```

### How to Run

```bash
pip install requests
python api_health_check.py
```

Expected stdout:

```
SUMMARY
----------------------------------------------------------------------
URL                                                STATUS     ATTEMPTS   TIME(s)
https://jsonplaceholder.typicode.com/posts         200        1          0.43
https://httpbin.org/status/500                     FAILED     3          14.21
https://httpbin.org/delay/3                        FAILED     3          18.05
```

### Configuring for Your Own Endpoints

Edit the `URLS` list at the top of the file:

```python
URLS = [
    "https://your-api.example.com/health",
    "https://another-service.internal/status",
]
```

Update `HEADERS` with your actual auth token or remove it entirely for unauthenticated endpoints:

```python
HEADERS = {
    "Authorization": "Bearer your-real-token"
}
```

> **Security note:** Never commit real bearer tokens to version control. Move `HEADERS` to environment variables (`os.environ.get("API_TOKEN")`) before pushing to GitHub.

### AWS Integration Path

This script is a direct analogue of patterns used in production AWS environments:

- **CloudWatch Synthetics canaries** use the same retry-and-log pattern to monitor API endpoints on a schedule
- The structured `api_log.txt` output can be forwarded to **CloudWatch Logs** via the Unified Agent using a `log_stream_name` per environment
- Failed endpoints can trigger **CloudWatch Alarms → SNS → PagerDuty** for on-call alerting
- Replace the hardcoded `URLS` list with values read from **AWS Systems Manager Parameter Store** for environment-agnostic configuration

---

## Script 2 — `flag_anomalies.py`

### What It Does

Reads a CSV of financial transactions and flags individual records that exhibit statistically suspicious behaviour. Outputs flagged transactions to `flagged.json` with one or more labelled reasons per flag.

### Detection Rules

Three independent signals are evaluated per transaction. Multiple signals can fire on the same record and are reported together.

| Rule | Label | Logic |
|---|---|---|
| High amount | `AMOUNT_OUTLIER` | Transaction exceeds the **95th percentile** of that specific user's historical amounts |
| Late night | `LATE_NIGHT` | Transaction timestamp falls between **02:00 and 04:59** |
| Rapid repeat | `RAPID_REPEAT` | Same user has a prior transaction within the last **60 seconds** |

The 95th percentile threshold is computed **per user**, not globally. A $10,000 transaction is not flagged for a user whose normal range is $8,000–$12,000; it would be flagged for a user whose range is $20–$200. This prevents the false-positive problem that kills trust in flat-threshold detectors.

### Input Format — `transactions.csv`

The script expects a CSV with at minimum these columns:

```csv
user_id,amount,timestamp,merchant,category
U001,49.99,2025-05-01T14:22:00,Amazon,Shopping
U001,8500.00,2025-05-15T03:11:00,Wire Transfer,Finance
U002,12.50,2025-05-01T09:00:00,Starbucks,Food
```

| Column | Type | Notes |
|---|---|---|
| `user_id` | string | Used to compute per-user thresholds |
| `amount` | float | Parsed from string automatically |
| `timestamp` | ISO 8601 string | e.g. `2025-05-15T03:11:00` |
| `merchant` | string | Passed through to output |
| `category` | string | Passed through to output |

### Output Format — `flagged.json`

```json
[
  {
    "timestamp": "2025-05-15T03:11:00",
    "amount": 8500.0,
    "merchant": "Wire Transfer",
    "category": "Finance",
    "user_id": "U001",
    "reasons": ["AMOUNT_OUTLIER", "LATE_NIGHT"]
  }
]
```

### How to Run

```bash
# No external dependencies — stdlib only
python flag_anomalies.py
```

The script reads `transactions.csv` from the current directory and writes `flagged.json` on completion. Final count is printed to stdout:

```
Done. Flagged: 7
```

### Design Decisions Worth Noting

**Why per-user percentiles instead of a global threshold?**
A global `amount > $5000` rule will miss high-value account fraud and spam low-value account alerts. Per-user baselines reflect actual behavioural patterns, which is the same approach used in production fraud detection systems (Stripe Radar, AWS Fraud Detector).

**Why sort by `(user_id, timestamp)` before processing?**
The `RAPID_REPEAT` rule depends on `last_seen` being chronologically correct per user. Without sorting, a transaction processed out of order would produce wrong time deltas. Sorting is done in-memory before any detection logic runs.

**Why output to JSON instead of CSV?**
The `reasons` field is a list of variable length. JSON handles multi-value fields cleanly; CSV would require either a delimited string or multiple boolean columns, both of which are awkward to query downstream.

### AWS Integration Path

This script maps directly to patterns in production AWS fraud and anomaly detection pipelines:

- Replace `transactions.csv` with records pulled from an **S3 bucket** using `boto3.client('s3').get_object()`
- Write `flagged.json` back to a separate **S3 prefix** (`s3://your-bucket/flagged/`) for downstream processing
- Wrap in a **Lambda function** triggered by S3 `ObjectCreated` events for real-time processing
- Feed flagged records to **Amazon Fraud Detector** or a **DynamoDB** table for case management
- Emit `len(flagged)` as a **CloudWatch custom metric** to track anomaly rate over time and alarm on spikes

---

## Requirements

### `api_health_check.py`

```
requests>=2.31.0
```

Install: `pip install requests`

### `flag_anomalies.py`

Standard library only (`csv`, `json`, `collections`, `datetime`). No installation required.

---

## Known Limitations

### `api_health_check.py`

## Security Notes

- Do not commit `api_log.txt` or `flagged.json` to version control if they contain real endpoint data or transaction records — add both to `.gitignore`
- The `transactions.csv` input is not validated for schema correctness before processing. Malformed rows will raise an unhandled exception — add input validation before using in any pipeline that accepts external data
- The hardcoded `Authorization: Bearer fake-token-123` header in `api_health_check.py` is intentionally fake. Replace with `os.environ.get("API_BEARER_TOKEN")` and document this in your threat model

---

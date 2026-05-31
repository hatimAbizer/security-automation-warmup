import csv
import json
from collections import defaultdict
from datetime import datetime


def load_transactions(file_name):
    transactions = []

    with open(file_name, "r", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            row["amount"] = float(row["amount"])
            row["timestamp"] = datetime.fromisoformat(row["timestamp"])
            transactions.append(row)

    return transactions


def compute_user_thresholds(data):
    user_amounts = defaultdict(list)

    for tx in data:
        user_amounts[tx["user_id"]].append(tx["amount"])

    thresholds = {}

    for user, amounts in user_amounts.items():
        amounts.sort()
        index = int(0.95 * len(amounts))
        thresholds[user] = amounts[index]

    return thresholds


def flag_transaction(tx, thresholds, last_seen):
    reasons = []

    user = tx["user_id"]
    amount = tx["amount"]
    time = tx["timestamp"]

    # 1. High amount
    if amount > thresholds[user]:
        reasons.append("AMOUNT_OUTLIER")

    # 2. Late night
    if 2 <= time.hour < 5:
        reasons.append("LATE_NIGHT")

    # 3. Rapid repeat
    if user in last_seen:
        diff = (time - last_seen[user]).total_seconds()
        if diff <= 60:
            reasons.append("RAPID_REPEAT")

    last_seen[user] = time

    return reasons


# ---------- MAIN ----------

transactions = load_transactions("transactions.csv")

# sort so rapid repeat works properly
transactions.sort(key=lambda x: (x["user_id"], x["timestamp"]))

thresholds = compute_user_thresholds(transactions)

last_seen = {}
flagged = []

for tx in transactions:
    reasons = flag_transaction(tx, thresholds, last_seen)

    if reasons:
        flagged.append({
            "timestamp": tx["timestamp"].isoformat(),
            "amount": tx["amount"],
            "merchant": tx["merchant"],
            "category": tx["category"],
            "user_id": tx["user_id"],
            "reasons": reasons
        })

with open("flagged.json", "w") as f:
    json.dump(flagged, f, indent=2)

print("Done. Flagged:", len(flagged))
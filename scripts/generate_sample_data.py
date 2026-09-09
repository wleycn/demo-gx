import json
import uuid
from datetime import datetime, timedelta
import random
from pathlib import Path

def generate_sample_data(num_records=100, output_path="sample_data.json"):
    records = []
    now = datetime.utcnow()
    systems = ["web", "mobile", "api"]
    currencies = ["USD", "EUR", "GBP", "CNY", "JPY", "XXX"]  # XXX 用于测试非法货币
    event_types = ["purchase", "view", "click", "signup", "login"]
    for _ in range(num_records):
        rec = {
            "event_id": str(uuid.uuid4()),
            "source_system": random.choice(systems),
            "customer_id": f"cust_{random.randint(1, 50):03d}",
            "event_type": random.choice(event_types),
            "event_timestamp": (now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))).isoformat(),
            "amount": round(random.uniform(0, 1000), 2),
            "currency": random.choice(currencies),
            "ingestion_timestamp": now.isoformat(),
        }
        records.append(rec)
    # 故意添加一些异常记录
    # 1. 缺少 event_id
    records.append({"source_system": "web", "customer_id": "cust_999", "event_type": "purchase", "event_timestamp": now.isoformat(), "amount": 10, "currency": "USD", "ingestion_timestamp": now.isoformat()})
    # 2. 无效金额负数
    records.append({"event_id": str(uuid.uuid4()), "source_system": "api", "customer_id": "cust_888", "event_type": "view", "event_timestamp": now.isoformat(), "amount": -5, "currency": "USD", "ingestion_timestamp": now.isoformat()})
    # 3. 无效 source_system
    records.append({"event_id": str(uuid.uuid4()), "source_system": "unknown", "customer_id": "cust_777", "event_type": "click", "event_timestamp": now.isoformat(), "amount": 20, "currency": "EUR", "ingestion_timestamp": now.isoformat()})
    # 4. 未来时间戳
    records.append({"event_id": str(uuid.uuid4()), "source_system": "mobile", "customer_id": "cust_666", "event_type": "login", "event_timestamp": (now + timedelta(days=1)).isoformat(), "amount": 0, "currency": "GBP", "ingestion_timestamp": now.isoformat()})
    # 5. 重复 event_id
    dup_id = str(uuid.uuid4())
    records.append({"event_id": dup_id, "source_system": "web", "customer_id": "cust_555", "event_type": "signup", "event_timestamp": (now - timedelta(hours=1)).isoformat(), "amount": 0, "currency": "USD", "ingestion_timestamp": now.isoformat()})
    records.append({"event_id": dup_id, "source_system": "web", "customer_id": "cust_555", "event_type": "signup", "event_timestamp": (now - timedelta(hours=2)).isoformat(), "amount": 0, "currency": "USD", "ingestion_timestamp": (now - timedelta(hours=1)).isoformat()})

    with open(output_path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    print(f"Generated {len(records)} records to {output_path}")

if __name__ == "__main__":
    generate_sample_data()


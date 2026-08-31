import random
import time
import requests
import json

WEBHOOK_URL = "http://localhost:8000/webhook/razorpay"
LOGS_URL = "http://localhost:8000/api/logs"

# Error templates representing real-world Razorpay failure modes
FAILURE_SCENARIOS = [
    {
        "method": "upi",
        "bank": "HDFC",
        "error_code": "GATEWAY_TIMEOUT",
        "error_description": "Bank servers unavailable / timeout",
        "expected_category": "BANK_DEGRADATION"
    },
    {
        "method": "upi",
        "bank": "SBI",
        "error_code": "BAD_REQUEST_DOWNTIME",
        "error_description": "Server downtime at issuer bank",
        "expected_category": "BANK_DEGRADATION"
    },
    {
        "method": "upi",
        "bank": "ICICI",
        "error_code": "BAD_REQUEST_INCORRECT_MPIN",
        "error_description": "User entered incorrect UPI PIN",
        "expected_category": "USER_DROP_OR_PIN_ERROR"
    },
    {
        "method": "upi",
        "bank": "AXIS",
        "error_code": "BAD_REQUEST_TRANSACTION_CANCELLED",
        "error_description": "Transaction declined by customer in UPI App",
        "expected_category": "USER_DROP_OR_PIN_ERROR"
    },
    {
        "method": "card",
        "bank": "KOTAK",
        "error_code": "BAD_REQUEST_LIMIT_EXCEEDED",
        "error_description": "Daily transaction limit exceeded on card",
        "expected_category": "LIMIT_EXCEEDED"
    },
    {
        "method": "card",
        "bank": "SBI",
        "error_code": "BAD_REQUEST_INSUFFICIENT_FUNDS",
        "error_description": "Insufficient balance in account",
        "expected_category": "LIMIT_EXCEEDED"
    },
    {
        "method": "netbanking",
        "bank": "PNB",
        "error_code": "BAD_REQUEST_SESSION_EXPIRED",
        "error_description": "Netbanking session expired before authentication",
        "expected_category": "GENERIC_FAILURE"
    }
]

def generate_failed_payload(index: int):
    scenario = random.choice(FAILURE_SCENARIOS)
    amount_rupees = random.choice([499, 999, 1499, 2499, 4999, 9999, 14999])
    order_id = f"order_batch_{index:03d}"
    payment_id = f"pay_fail_{index:03d}_{random.randint(1000, 9999)}"
    phone_number = f"+9198{random.randint(10000000, 99999999)}"

    payload = {
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "order_id": order_id,
                    "amount": amount_rupees * 100,  # in paise
                    "currency": "INR",
                    "status": "failed",
                    "method": scenario["method"],
                    "bank": scenario["bank"],
                    "contact": phone_number,
                    "error_code": scenario["error_code"],
                    "error_description": scenario["error_description"]
                }
            }
        }
    }
    return payload, order_id, amount_rupees * 100

def generate_capture_payload(order_id: str, amount_paise: int):
    return {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": f"pay_recov_{random.randint(10000, 99999)}",
                    "order_id": f"order_recov_{order_id}",
                    "amount": amount_paise,
                    "currency": "INR",
                    "status": "captured",
                    "notes": {
                        "origin": "revguard_ai_recovery",
                        "original_order_id": order_id
                    }
                }
            }
        }
    }

def run_simulation(total_records=50, simulated_recovery_rate=0.42):
    print(f"==================================================")
    print(f"🚀 Starting RevGuard Batch Simulation ({total_records} Records)")
    print(f"==================================================\n")

    orders_to_recover = []

    # Step 1: Dispatch 50 Failed Payments
    print(f"[*] Step 1: Sending {total_records} `payment.failed` Webhook events...")
    for i in range(1, total_records + 1):
        payload, order_id, amount_paise = generate_failed_payload(i)
        try:
            res = requests.post(WEBHOOK_URL, json=payload)
            if res.status_code == 200:
                print(f"  [+] #{i:02d} Sent {order_id} ({payload['payload']['payment']['entity']['bank']} - {payload['payload']['payment']['entity']['error_code']})")
                orders_to_recover.append((order_id, amount_paise))
            else:
                print(f"  [-] #{i:02d} Failed: Status {res.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"\n❌ Error: Cannot connect to {WEBHOOK_URL}. Make sure `revguard_app.py` is running on port 8000!")
            return

        time.sleep(0.05) # fast simulation

    print(f"\n[*] Step 2: Simulating background AI diagnosis & recovery clicks...")
    time.sleep(1)

    # Step 2: Simulate customers completing payment via generated recovery link (~40% recovery rate)
    num_to_recover = int(len(orders_to_recover) * simulated_recovery_rate)
    recovered_samples = random.sample(orders_to_recover, num_to_recover)

    print(f"[*] Step 3: Simulating customer checkout completions ({num_to_recover}/{len(orders_to_recover)} conversions)...")
    for order_id, amount_paise in recovered_samples:
        capture_payload = generate_capture_payload(order_id, amount_paise)
        requests.post(WEBHOOK_URL, json=capture_payload)
        time.sleep(0.02)

    # Step 3: Fetch Final Audit Trail and Display Summary Table
    time.sleep(1)
    res = requests.get(LOGS_URL)
    if res.status_code == 200:
        data = res.json()
        metrics = data["metrics"]
        print(f"\n==================================================")
        print(f"📊 RECOVERY ENGINE PERFORMANCE RESULTS")
        print(f"==================================================")
        print(f"• Total Failed Transactions Processed : {metrics['total_incidents']}")
        print(f"• Total Failed Revenue                : ₹{metrics['total_failed_inr']:,.2f}")
        print(f"• Total Revenue Recovered             : ₹{metrics['total_recovered_inr']:,.2f}")
        print(f"• Revenue Recovery Rate               : {metrics['recovery_rate_pct']:.2f}%")
        print(f"==================================================")
        print(f"\n👉 View raw JSON logs at: {LOGS_URL}")

if __name__ == "__main__":
    run_simulation(total_records=50, simulated_recovery_rate=0.40)

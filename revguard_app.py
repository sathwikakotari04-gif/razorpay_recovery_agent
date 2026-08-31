import os
import hmac
import hashlib
import time
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Header
from pydantic import BaseModel
import razorpay

app = FastAPI(
    title="RevGuard AI - Smart Degradation & Recovery Engine",
    description="Autonomous payment failure diagnosis and bounded recovery agent for Razorpay.",
    version="1.0.0"
)

# In-memory store for tracking
recovery_logs = []

# --- 1. FAILURE DIAGNOSIS ENGINE ---
class DiagnosticResult(BaseModel):
    category: str
    is_bank_down: bool
    recommended_channel: str
    delay_seconds: int
    hinglish_message: str
    english_message: str

def diagnose_payment_failure(error_code: str, error_desc: str, method: str, bank: Optional[str] = None) -> DiagnosticResult:
    error_desc_lower = (error_desc or "").lower()
    error_code_lower = (error_code or "").lower()
    bank_name = bank if bank else "Bank"

    if any(k in error_desc_lower for k in ["downtime", "timeout", "unavailable", "server error", "gateway error"]) or "gateway" in error_code_lower:
        return DiagnosticResult(
            category="BANK_DEGRADATION",
            is_bank_down=True,
            recommended_channel="WHATSAPP_SMART_DELAY",
            delay_seconds=180,
            hinglish_message=f"Hey! Lagta hai {bank_name} servers busy the aur aapka payment complete nahi hua. Tension mat lijiye, aapka order saved hai. Dusre method (UPI / Other Bank) se instantly complete karne ke liye yahan click karein:",
            english_message=f"Hi! It looks like {bank_name} servers are temporarily down and your payment could not be processed. Your order is safely held. Click below to retry using an alternate UPI or Card method:"
        )
    elif any(k in error_desc_lower for k in ["pin", "mpin", "cancelled", "declined by customer"]) or "pin" in error_code_lower:
        return DiagnosticResult(
            category="USER_DROP_OR_PIN_ERROR",
            is_bank_down=False,
            recommended_channel="WHATSAPP_INSTANT",
            delay_seconds=0,
            hinglish_message="Hey! Aapka payment attempt cancel ya incorrect PIN ki wajah se fail ho gaya. Agar aap firse try karna chahte hain, toh direct 1-click UPI link ready hai:",
            english_message="Hi! Your payment attempt was cancelled or failed due to an incorrect MPIN. Click below to securely retry with 1-click UPI checkout:"
        )
    elif any(k in error_desc_lower for k in ["limit", "insufficient", "balance"]):
        return DiagnosticResult(
            category="LIMIT_EXCEEDED",
            is_bank_down=False,
            recommended_channel="WHATSAPP_INSTANT",
            delay_seconds=0,
            hinglish_message=f"Hey! Lagta hai aapka {bank_name} account daily limit reach kar chuka hai. Aap kisi aur account, Netbanking ya Credit Card se 10 seconds me payment complete kar sakte hain:",
            english_message=f"Hi! It appears the daily transaction limit on your {bank_name} account was exceeded. You can easily switch to another account, Netbanking, or Card using this link:"
        )
    else:
        return DiagnosticResult(
            category="GENERIC_FAILURE",
            is_bank_down=False,
            recommended_channel="WHATSAPP_INSTANT",
            delay_seconds=0,
            hinglish_message="Hey! Technical reason ki wajah se aapka payment complete nahi ho paya. Instant recovery link niche di gayi hai:",
            english_message="Hi! Your payment could not be completed due to a temporary technical glitch. Use this secure recovery link to finish your order:"
        )

def generate_recovery_payment_link(amount: int, currency: str, customer_contact: str, customer_name: str, order_id: str) -> str:
    return f"https://rzp.io/i/rec_{order_id[:8]}"

def execute_recovery_workflow(payload_data: Dict[str, Any]):
    payment = payload_data.get("payment", {}).get("entity", {})
    order_id = payment.get("order_id", "order_mock_123")
    payment_id = payment.get("id", "pay_mock_123")
    amount = payment.get("amount", 100000)
    currency = payment.get("currency", "INR")
    method = payment.get("method", "upi")
    bank = payment.get("bank", "HDFC")
    contact = payment.get("contact", "+919876543210")
    
    error_code = payment.get("error_code", "BAD_REQUEST_ERROR")
    error_desc = payment.get("error_description", "Bank server is down / timeout")

    diagnosis = diagnose_payment_failure(error_code, error_desc, method, bank)
    recovery_url = generate_recovery_payment_link(amount, currency, contact, "Customer", order_id)

    full_hinglish_msg = f"{diagnosis.hinglish_message}\n\n🔗 Payment Link: {recovery_url}\n⏰ Valid for 15 mins."
    full_english_msg = f"{diagnosis.english_message}\n\n🔗 Complete Payment: {recovery_url}\n⏰ Link expires in 15 mins."

    log_entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "payment_id": payment_id,
        "order_id": order_id,
        "amount_inr": amount / 100,
        "method": method,
        "bank": bank,
        "error_code": error_code,
        "root_cause_category": diagnosis.category,
        "action_taken": diagnosis.recommended_channel,
        "recovery_link": recovery_url,
        "dispatched_message_hinglish": full_hinglish_msg,
        "dispatched_message_english": full_english_msg,
        "status": "DISPATCHED_PENDING_RECOVERY"
    }

    recovery_logs.append(log_entry)

@app.post("/webhook/razorpay")
async def razorpay_webhook(request: Request, background_tasks: BackgroundTasks):
    event_payload = await request.json()
    event_type = event_payload.get("event")

    if event_type == "payment.failed":
        execute_recovery_workflow(event_payload.get("payload", {}))
        return {"status": "accepted", "message": "Failure logged. AI recovery triggered."}

    elif event_type == "payment.captured":
        notes = event_payload.get("payload", {}).get("payment", {}).get("entity", {}).get("notes", {})
        if notes.get("origin") == "revguard_ai_recovery":
            orig_order = notes.get("original_order_id")
            for log in recovery_logs:
                if log.get("order_id") == orig_order:
                    log["status"] = "RECOVERED_SUCCESSFULLY"
            return {"status": "success", "message": "Revenue successfully recovered!"}

    return {"status": "ignored", "event": event_type}

@app.get("/api/logs")
def get_recovery_audit_logs():
    total_failed_val = sum(item["amount_inr"] for item in recovery_logs)
    recovered_val = sum(item["amount_inr"] for item in recovery_logs if item["status"] == "RECOVERED_SUCCESSFULLY")
    
    return {
        "metrics": {
            "total_incidents": len(recovery_logs),
            "total_failed_inr": total_failed_val,
            "total_recovered_inr": recovered_val,
            "recovery_rate_pct": (recovered_val / total_failed_val * 100) if total_failed_val > 0 else 0
        },
        "audit_trail": recovery_logs
    }

@app.post("/api/reset")
def reset_recovery_logs():
    global recovery_logs
    recovery_logs = []
    return {"status": "cleared"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
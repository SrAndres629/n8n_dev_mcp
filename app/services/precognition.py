"""
Precognition Service - Predictive Analysis & Anomaly Detection
"""
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from collections import defaultdict
import statistics

from app.core.client import get_client, safe_tool
from app.core.logging import gateway_logger as logger


@safe_tool
async def traffic_anomaly_detection(hours: int = 24, threshold_std: float = 2.0) -> str:
    """Detect unusual traffic patterns by analyzing execution frequency."""
    logger.info(f"Running traffic anomaly detection for last {hours} hours")
    client = get_client()
    
    try:
        exec_data = await client.get("/executions", params={"limit": 500})
        executions = exec_data.get("data", [])
        
        hourly_counts = defaultdict(int)
        now = datetime.now()
        cutoff = now - timedelta(hours=hours)
        
        for ex in executions:
            started = ex.get("startedAt")
            if not started:
                continue
            try:
                exec_time = datetime.fromisoformat(started.replace("Z", "+00:00")).replace(tzinfo=None)
                if exec_time < cutoff:
                    continue
                hour_key = exec_time.strftime("%Y-%m-%d %H:00")
                hourly_counts[hour_key] += 1
            except:
                continue
        
        if len(hourly_counts) < 3:
            return json.dumps({"status": "insufficient_data", "hours_analyzed": len(hourly_counts)}, indent=2)
        
        counts = list(hourly_counts.values())
        mean_traffic = statistics.mean(counts)
        std_traffic = statistics.stdev(counts) if len(counts) > 1 else 0
        
        anomalies = []
        for hour, count in hourly_counts.items():
            if std_traffic > 0:
                z_score = (count - mean_traffic) / std_traffic
                if abs(z_score) > threshold_std:
                    anomalies.append({"hour": hour, "count": count, "z_score": round(z_score, 2)})
        
        return json.dumps({
            "status": "success",
            "mean_hourly": round(mean_traffic, 2),
            "std_deviation": round(std_traffic, 2),
            "anomalies": anomalies[:10]
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@safe_tool
async def token_burn_rate_prediction(model_cost_per_1k: float = 0.002) -> str:
    """Predict API token/cost burn rate based on usage patterns."""
    logger.info("Calculating token burn rate")
    client = get_client()
    
    try:
        exec_data = await client.get("/executions", params={"limit": 200})
        executions = exec_data.get("data", [])
        
        ai_types = ["openai", "anthropic", "langchain", "chat"]
        ai_executions = sum(1 for ex in executions 
                          for node in ex.get("workflowData", {}).get("nodes", [])
                          if any(t in node.get("type", "").lower() for t in ai_types))
        
        tokens_per_exec = 1500
        hourly_tokens = ai_executions / 24 * tokens_per_exec
        daily_cost = (hourly_tokens * 24 / 1000) * model_cost_per_1k
        
        return json.dumps({
            "status": "success",
            "ai_executions": ai_executions,
            "daily_tokens_estimate": round(hourly_tokens * 24),
            "daily_cost_usd": round(daily_cost, 2),
            "monthly_cost_usd": round(daily_cost * 30, 2)
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@safe_tool
async def predict_failures() -> str:
    """Predict potential failures based on historical patterns."""
    logger.info("Predicting failures")
    client = get_client()
    
    try:
        exec_data = await client.get("/executions", params={"limit": 500})
        executions = exec_data.get("data", [])
        
        stats = defaultdict(lambda: {"total": 0, "errors": 0})
        for ex in executions:
            wf_id = ex.get("workflowId")
            stats[wf_id]["total"] += 1
            if ex.get("status") == "error":
                stats[wf_id]["errors"] += 1
        
        at_risk = []
        for wf_id, s in stats.items():
            if s["total"] >= 5:
                rate = s["errors"] / s["total"]
                if rate > 0.2:
                    at_risk.append({"workflow_id": wf_id, "error_rate": round(rate * 100, 1)})
        
        at_risk.sort(key=lambda x: x["error_rate"], reverse=True)
        return json.dumps({"status": "success", "at_risk": at_risk[:10]}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@safe_tool
async def compute_reliability_score() -> str:
    """Compute overall system reliability score (0-100)."""
    logger.info("Computing reliability score")
    client = get_client()
    
    try:
        exec_data = await client.get("/executions", params={"limit": 200})
        executions = exec_data.get("data", [])
        
        success = sum(1 for ex in executions if ex.get("status") in ["success", "finished"])
        total = len(executions)
        success_rate = success / total if total > 0 else 1
        
        score = success_rate * 100
        grade = "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70 else "D"
        
        return json.dumps({
            "status": "success",
            "reliability_score": round(score, 1),
            "grade": grade,
            "success_rate": round(success_rate * 100, 1),
            "total_analyzed": total
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@safe_tool
async def detect_silence_anomaly(tolerance_minutes: int = 30) -> str:
    """Detect if there is unusual silence (no activity) in the system."""
    logger.info("Checking for unusual silence")
    client = get_client()
    
    try:
        exec_data = await client.get("/executions", params={"limit": 10})
        executions = exec_data.get("data", [])
        
        if not executions:
            return json.dumps({"status": "alert", "message": "No executions found!"}, indent=2)
        
        most_recent = None
        for ex in executions:
            started = ex.get("startedAt")
            if started:
                try:
                    t = datetime.fromisoformat(started.replace("Z", "+00:00")).replace(tzinfo=None)
                    if most_recent is None or t > most_recent:
                        most_recent = t
                except:
                    pass
        
        silence = (datetime.now() - most_recent).total_seconds() / 60 if most_recent else 999
        is_silent = silence > tolerance_minutes
        
        return json.dumps({
            "status": "silence_alert" if is_silent else "normal",
            "silence_minutes": round(silence, 1),
            "tolerance": tolerance_minutes,
            "is_unusual": is_silent
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)

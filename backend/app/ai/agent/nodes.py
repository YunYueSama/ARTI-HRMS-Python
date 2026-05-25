"""
Simplified Agent nodes implementation for LangGraph.

This module provides a compact, rule-based implementation of the main
nodes used by the Agent state graph:

- intent_recognition_node
- plan_generation_node
- human_approval_node
- execution_node
- result_reporting_node
- error_reporting_node

It also includes a small set of helper functions for extracting dates,
leave types, durations and remarks from plain text. The implementations
are intentionally conservative and dependency-free so they are safe for
development and tests. Replace or extend with LLM-backed logic later.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from app.ai.agent.state import AgentState


# ----- Simple configuration / keywords -----
LEAVE_TYPES = [
    "年假",
    "病假",
    "事假",
    "婚假",
    "产假",
    "陪产假",
    "丧假",
]

INTENT_KEYWORDS: Dict[str, List[str]] = {
    "leave.create": ["请假", "休假", "请两天", "请假申请", "我要请"],
    "attendance.upsert": ["打卡", "签到", "签退", "补卡"],
    "role-permission.update": ["权限", "分配权限", "授权"],
}


# ----- Small text utilities -----

def _contains_any(text: str, *keywords: str) -> bool:
    t = text or ""
    for k in keywords:
        if k and k in t:
            return True
    return False


CHINESE_NUMERAL = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def _chinese_number_to_int(s: str) -> Optional[int]:
    # Very small support: 一 二 三 四 五 六 七 八 九 十 两
    if not s:
        return None
    total = 0
    if s in CHINESE_NUMERAL:
        return CHINESE_NUMERAL[s]
    # handle 二十, 二十五 etc (simple)
    if "十" in s:
        parts = s.split("十")
        tens = CHINESE_NUMERAL.get(parts[0], 1) if parts[0] != "" else 1
        ones = CHINESE_NUMERAL.get(parts[1], 0) if len(parts) > 1 and parts[1] != "" else 0
        return tens * 10 + ones
    return None


def _safe_int(s: str) -> Optional[int]:
    try:
        return int(s)
    except Exception:
        return None


# ----- Date / time extraction helpers -----

def _extract_dates(text: str) -> List[str]:
    """Return list of date strings in ISO format (YYYY-MM-DD).

    Supports:
      - YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
      - MM月DD日 (assume current year)
      - today/今天, 明天, 后天
      - simple MM-DD or MM/DD (assume current year)
    """
    if not text:
        return []
    text = text.strip()
    today = date.today()
    results: List[str] = []

    # explicit YYYY-MM-DD
    for m in re.finditer(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b", text):
        y, mo, d = m.groups()
        try:
            dt = date(int(y), int(mo), int(d))
            results.append(dt.isoformat())
        except Exception:
            continue

    # MM月DD日 or MM月DD号
    for m in re.finditer(r"(\d{1,2})月(\d{1,2})[日号]", text):
        mo, d = m.groups()
        try:
            dt = date(today.year, int(mo), int(d))
            results.append(dt.isoformat())
        except Exception:
            continue

    # MM-DD or MM/DD (no year)
    for m in re.finditer(r"\b(\d{1,2})[-/](\d{1,2})\b", text):
        mo, d = m.groups()
        try:
            dt = date(today.year, int(mo), int(d))
            results.append(dt.isoformat())
        except Exception:
            continue

    # relative words
    if "今天" in text:
        results.append(today.isoformat())
    if "明天" in text:
        results.append((today + timedelta(days=1)).isoformat())
    if "后天" in text:
        results.append((today + timedelta(days=2)).isoformat())

    # de-duplicate while preserving order
    seen = set()
    out: List[str] = []
    for v in results:
        if v not in seen:
            out.append(v)
            seen.add(v)
    return out


def _extract_times(text: str) -> List[str]:
    if not text:
        return []
    out: List[str] = []
    # 24h times like 09:30 or 9:30
    for m in re.finditer(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text):
        out.append(f"{int(m.group(1)):02d}:{m.group(2)}")
    # Chinese times like 9点, 15点30分
    for m in re.finditer(r"(\d{1,2})点(?:((?:\d{1,2})分)?)", text):
        hour = int(m.group(1))
        minute = 0
        if m.group(2):
            mm = re.search(r"(\d{1,2})分", m.group(2))
            if mm:
                minute = int(mm.group(1))
        out.append(f"{hour:02d}:{minute:02d}")
    # deduplicate
    return list(dict.fromkeys(out))


def _extract_days_from_text(text: str) -> Optional[float]:
    if not text:
        return None
    # arabic numbers
    m = re.search(r"(\d+(?:\.\d+)?)\s*天", text)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            pass
    # chinese numerals
    m2 = re.search(r"([零一二两三四五六七八九十百]+)天", text)
    if m2:
        val = _chinese_number_to_int(m2.group(1))
        if val is not None:
            return float(val)
    return None


def _find_leave_type(text: str) -> Optional[str]:
    if not text:
        return None
    for t in LEAVE_TYPES:
        if t in text:
            return t
    # synonyms
    if "年休" in text:
        return "年假"
    return None


def _extract_remark(text: str) -> str:
    if not text:
        return ""
    m = re.search(r"(?:备注|原因|remark|reason)[:：]\s*(.+)$", text, flags=re.I | re.M)
    if m:
        return m.group(1).strip()
    return ""


# ----- Node implementations -----


async def intent_recognition_node(state: AgentState) -> Dict[str, Any]:
    """Basic rule-based intent recognizer.

    Returns partial state containing at least `intent` (or 'unknown') and
    optional `provider_name` (string).
    """
    cmd = (state.get("command") or "").strip()
    cmd_lower = cmd
    if not cmd:
        return {"intent": "unknown"}

    for intent, kws in INTENT_KEYWORDS.items():
        if _contains_any(cmd_lower, *kws):
            return {"intent": intent, "provider_name": "rule"}

    # fallback: try simple heuristics
    if "请" in cmd and "假" in cmd:
        return {"intent": "leave.create", "provider_name": "rule"}

    return {"intent": "unknown", "provider_name": "rule"}


async def plan_generation_node(state: AgentState) -> Dict[str, Any]:
    """Generate a minimal executable plan from recognized intent.

    This function fills `plan`, `executable`, `warnings`, `risk_level`.
    """
    intent = state.get("intent")
    cmd = state.get("command") or ""
    plan: Dict[str, Any] = {}
    warnings: List[str] = []
    executable = True
    risk_level = "low"

    if intent == "leave.create":
        dates = _extract_dates(cmd)
        start = dates[0] if dates else None
        end = dates[1] if len(dates) > 1 else None
        days = _extract_days_from_text(cmd)
        leave_type = _find_leave_type(cmd) or "年假"
        reason = _extract_remark(cmd)
        if not reason:
            reason = "AI代理提交"

        today_str = date.today().isoformat()

        # 统一日期和天数的推算逻辑
        # 规则：天数 = 结束日期 - 开始日期 + 1（主流 HR 系统惯例）
        if start and end:
            # 两个日期都有：从日期范围推算天数
            if days is None:
                try:
                    d1 = date.fromisoformat(start)
                    d2 = date.fromisoformat(end)
                    days = (d2 - d1).days + 1
                except Exception:
                    days = 1
        elif start and not end:
            # 只有一个日期：视为当天请假
            end = start
            if days is None:
                days = 1
        else:
            # 没有日期：默认从今天开始
            start = today_str
            if days is None:
                days = 1
            # end = start + (days - 1)
            try:
                d = date.fromisoformat(start)
                end = (d + timedelta(days=days - 1)).isoformat()
            except Exception:
                end = start

        preview = {
            "leaveType": leave_type,
            "startDate": start,
            "endDate": end,
            "days": int(days),
            "reason": reason,
        }
        plan = {
            "intent": "leave.create",
            "executable": True,
            "warnings": warnings,
            "preview": preview,
        }
    elif intent == "attendance.upsert":
        dates = _extract_dates(cmd)
        times = _extract_times(cmd)
        plan = {
            "intent": "attendance.upsert",
            "executable": False,
            "warnings": ["考勤打卡功能暂未实现"],
            "preview": {
                "attendanceDate": dates[0] if dates else "",
                "clockIn": times[0] if times else "",
                "clockOut": times[1] if len(times) > 1 else "",
                "remark": _extract_remark(cmd),
            },
        }
        executable = False
    elif intent == "role-permission.update":
        plan = {
            "intent": "role-permission.update",
            "executable": False,
            "warnings": ["角色权限功能暂未实现"],
            "preview": {},
        }
        executable = False
    else:
        plan = {"intent": intent or "unknown", "executable": False, "warnings": ["未知指令类型"]}
        executable = False
        warnings.append("自动生成计划为占位内容，需要人工确认")

    return {
        "plan": plan,
        "executable": plan.get("executable", executable),
        "warnings": plan.get("warnings", warnings),
        "risk_level": risk_level,
        "draft_plan": plan,
    }


async def human_approval_node(state: AgentState) -> Dict[str, Any]:
    """Mark a plan as pending approval if required.

    Simple behaviour: if `requires_approval` exists and is False, set approved.
    Otherwise set to pending.
    """
    requires = state.get("requires_approval")
    if requires is False:
        return {"approval_status": "approved", "requires_approval": False}
    # default behaviour: require approval
    return {"approval_status": "pending", "requires_approval": True}


async def execution_node(state: AgentState) -> Dict[str, Any]:
    """Execute the plan with best-effort simulation.

    The node appends to `execution_results` and sets `result_summary`.
    """
    plan = state.get("plan") or {}
    results: List[Dict[str, Any]] = state.get("execution_results") or []

    if plan.get("intent") == "leave.create":
        preview = plan.get("preview", {})
        created = {
            "step": len(results) + 1,
            "action": "create_leave",
            "status": "success",
            "detail": {
                "leave_type": preview.get("leaveType"),
                "start_date": preview.get("startDate"),
                "end_date": preview.get("endDate"),
                "days": preview.get("days"),
            },
        }
        results.append(created)
        summary = f"已为用户创建 {preview.get('leaveType')}，{preview.get('startDate')} → {preview.get('endDate')}"
        return {
            "execution_results": results,
            "result_summary": summary,
            "current_step": created["step"],
        }

    # fallback: mark as no-op
    results.append({
        "step": len(results) + 1,
        "action": "noop",
        "status": "skipped",
        "detail": {"note": "unsupported plan type"},
    })
    return {"execution_results": results, "result_summary": "未执行任何操作"}


async def result_reporting_node(state: AgentState) -> Dict[str, Any]:
    """Compose a user-facing result summary.

    Returns or preserves `result_summary` and may add small metadata.
    """
    summary = state.get("result_summary")
    if not summary:
        results = state.get("execution_results") or []
        if results:
            summary = ", ".join([f"{r.get('action')}:{r.get('status')}" for r in results])
        else:
            summary = "无可报告的执行结果"
    return {"result_summary": summary}


async def error_reporting_node(state: AgentState) -> Dict[str, Any]:
    """Aggregate and return error messages.

    Expects `error_history` in state.
    """
    errs = state.get("error_history") or []
    if not errs:
        return {"error_history": [], "result_summary": "无错误"}
    # keep last 5
    recent = errs[-5:]
    return {"error_history": recent, "result_summary": "; ".join(recent)}


# Expose a compact public API
__all__ = [
    "intent_recognition_node",
    "plan_generation_node",
    "human_approval_node",
    "execution_node",
    "result_reporting_node",
    "error_reporting_node",
]

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.db import DatabaseError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


logger = logging.getLogger("testhub.errors")


DETAIL_KEYS = {"provider", "http_status", "stage", "task_no", "resource", "operation"}
SECRET_PATTERNS = [
    (re.compile(r"([?&](?:key|api_key)=)[^&\s]+", re.I), r"\1***"),
    (re.compile(r"(authorization\s*[:=]\s*)(?:bearer\s+)?[^\s,;]+", re.I), r"\1***"),
    (re.compile(r"\b(?:AIza|sk-)[A-Za-z0-9_-]{12,}\b"), "***"),
    (re.compile(r"((?:password|secret|token)\s*[=:]\s*)[^\s,;&]+", re.I), r"\1***"),
]


@dataclass(frozen=True)
class ErrorDefinition:
    message: str
    reason: str
    solution: str
    retryable: bool = False
    action_type: str | None = None
    action_label: str | None = None


ERROR_CATALOG = {
    "VALIDATION_ERROR": ErrorDefinition("提交内容有误", "部分字段缺失或格式不符合要求", "请根据字段提示修改后重新提交"),
    "AUTH_REQUIRED": ErrorDefinition("登录状态已失效", "当前登录凭证不存在或已过期", "请重新登录后继续操作", action_type="login", action_label="重新登录"),
    "PERMISSION_DENIED": ErrorDefinition("没有操作权限", "当前账号无权执行此操作", "请联系项目管理员确认权限"),
    "RESOURCE_NOT_FOUND": ErrorDefinition("请求的数据不存在", "数据可能已被删除或地址已失效", "请刷新页面后重新选择"),
    "STATE_CONFLICT": ErrorDefinition("数据状态已发生变化", "当前操作与最新数据状态冲突", "请刷新数据并确认后重新操作", action_type="refresh", action_label="刷新数据"),
    "MODEL_CONFIGURATION_MISSING": ErrorDefinition("缺少可用的模型配置", "当前业务角色没有绑定已启用的模型", "请前往系统角色配置完成模型绑定", action_type="open_model_config", action_label="前往配置"),
    "MODEL_CREDENTIAL_INVALID": ErrorDefinition("模型认证失败", "API Key 无效、已过期或没有访问权限", "请检查模型配置中的密钥和访问权限", action_type="open_model_config", action_label="检查配置"),
    "MODEL_NOT_AVAILABLE": ErrorDefinition("配置的模型不可用", "模型名称不存在、已下线或当前账号无权访问", "请在模型配置中选择当前可用模型", action_type="open_model_config", action_label="检查配置"),
    "MODEL_REGION_UNSUPPORTED": ErrorDefinition("模型服务不支持当前运行地区", "模型供应商拒绝了当前地区发起的请求", "请在供应商支持且合规的地区运行，或切换已配置的可用供应商", action_type="open_model_config", action_label="检查配置"),
    "MODEL_RATE_LIMITED": ErrorDefinition("模型请求过于频繁", "短时间内的请求数量超过供应商限制", "请稍后重新发起任务", True, "retry_task", "重新发起"),
    "MODEL_QUOTA_EXCEEDED": ErrorDefinition("模型配额不足", "账号配额、余额或计费额度不足", "请检查供应商配额和计费状态后重试", action_type="open_model_config", action_label="检查配置"),
    "MODEL_CAPACITY_BUSY": ErrorDefinition("模型服务当前繁忙", "模型供应商暂时没有可用容量", "请等待 1～5 分钟后重新发起任务", True, "retry_task", "重新发起"),
    "MODEL_TIMEOUT": ErrorDefinition("模型调用超时", "模型服务未在限定时间内返回结果", "请稍后重新发起任务；持续失败时检查网络和模型状态", True, "retry_task", "重新发起"),
    "MODEL_PROVIDER_UNAVAILABLE": ErrorDefinition("模型服务暂时不可用", "供应商服务异常或网络连接失败", "请稍后重试，并检查供应商服务状态", True, "retry_task", "重新发起"),
    "MODEL_RESPONSE_INVALID": ErrorDefinition("模型返回内容无法处理", "模型响应缺少必要字段或不符合约定格式", "请检查系统角色提示词和模型能力后重新生成", action_type="open_model_config", action_label="检查配置"),
    "FILE_TYPE_INVALID": ErrorDefinition("文件类型不支持", "上传文件不属于允许的格式", "请转换为页面支持的文件格式后重新上传", action_type="reupload", action_label="重新上传"),
    "FILE_TOO_LARGE": ErrorDefinition("文件大小超过限制", "上传文件超过当前接口允许的大小", "请压缩或拆分文件后重新上传", action_type="reupload", action_label="重新上传"),
    "DOCUMENT_PARSE_FAILED": ErrorDefinition("文档解析失败", "文档内容、格式或解析组件出现异常", "请检查文档是否可正常打开，然后重新解析", True, "reparse", "重新解析"),
    "STORAGE_CONFIGURATION_MISSING": ErrorDefinition("文件存储配置不完整", "七牛云访问参数尚未正确配置", "请联系管理员补充存储配置"),
    "STORAGE_UNAVAILABLE": ErrorDefinition("文件存储服务不可用", "上传、下载或删除远端文件失败", "请检查存储服务和网络后重试", True, "retry_request", "重试"),
    "SEARCH_UNAVAILABLE": ErrorDefinition("检索服务不可用", "OpenSearch 或向量模型连接异常", "请检查索引服务与向量模型配置后重试", True, "retry_request", "重试"),
    "QUEUE_UNAVAILABLE": ErrorDefinition("后台任务队列不可用", "任务未能提交给 Celery 工作进程", "请确认 Redis 和 Celery 已启动后重新发起", True, "retry_task", "重新发起"),
    "DATABASE_UNAVAILABLE": ErrorDefinition("数据库暂时不可用", "数据库连接或查询执行失败", "请检查数据库服务后重新操作", True, "retry_request", "重试"),
    "NETWORK_ERROR": ErrorDefinition("网络连接失败", "浏览器或后端无法连接目标服务", "请检查网络连接后重试", True, "retry_request", "重试"),
    "INTERNAL_ERROR": ErrorDefinition("系统内部异常", "系统执行过程中发生了未预期错误", "请记录错误编号并联系管理员处理"),
}


ERROR_HTTP_STATUS = {
    "VALIDATION_ERROR": status.HTTP_400_BAD_REQUEST,
    "AUTH_REQUIRED": status.HTTP_401_UNAUTHORIZED,
    "PERMISSION_DENIED": status.HTTP_403_FORBIDDEN,
    "RESOURCE_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "STATE_CONFLICT": status.HTTP_409_CONFLICT,
    "MODEL_RATE_LIMITED": status.HTTP_429_TOO_MANY_REQUESTS,
    "MODEL_CAPACITY_BUSY": status.HTTP_503_SERVICE_UNAVAILABLE,
    "MODEL_TIMEOUT": status.HTTP_503_SERVICE_UNAVAILABLE,
    "MODEL_PROVIDER_UNAVAILABLE": status.HTTP_503_SERVICE_UNAVAILABLE,
    "MODEL_RESPONSE_INVALID": status.HTTP_502_BAD_GATEWAY,
    "STORAGE_UNAVAILABLE": status.HTTP_503_SERVICE_UNAVAILABLE,
    "SEARCH_UNAVAILABLE": status.HTTP_503_SERVICE_UNAVAILABLE,
    "QUEUE_UNAVAILABLE": status.HTTP_503_SERVICE_UNAVAILABLE,
    "DATABASE_UNAVAILABLE": status.HTTP_503_SERVICE_UNAVAILABLE,
    "NETWORK_ERROR": status.HTTP_503_SERVICE_UNAVAILABLE,
    "INTERNAL_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def error_http_status(code):
    return ERROR_HTTP_STATUS.get(code, status.HTTP_400_BAD_REQUEST)


class ClassifiedError(Exception):
    default_code = "INTERNAL_ERROR"

    def __init__(self, message="", *, code=None, details=None, cause_detail="", trace_id=None):
        super().__init__(message)
        self.error_code = code or self.default_code
        self.public_message = message
        self.error_details = details or {}
        self.cause_detail = cause_detail
        self.trace_id = trace_id


class AppError(ClassifiedError):
    def __init__(self, code, message="", *, http_status=None, details=None, cause_detail=""):
        super().__init__(message, code=code, details=details)
        self.status_code = http_status or error_http_status(code)
        self.cause_detail = cause_detail


def new_trace_id():
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"ERR-{stamp}-{uuid4().hex[:8].upper()}"


def sanitize_text(value, limit=2000):
    text = str(value or "")
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text[:limit]


def _definition(code):
    return ERROR_CATALOG.get(code, ERROR_CATALOG["INTERNAL_ERROR"])


def _action(definition):
    if not definition.action_type:
        return None
    return {"type": definition.action_type, "label": definition.action_label}


def _message_text(data):
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        return "；".join(_message_text(item) for item in data if item not in (None, ""))
    if isinstance(data, dict):
        preferred = data.get("detail") or data.get("message")
        if preferred:
            return _message_text(preferred)
        return "；".join(_message_text(item) for item in data.values() if item not in (None, ""))
    return str(data or "")


def field_errors_from_data(data):
    if not isinstance(data, dict):
        return {}
    return {
        key: value for key, value in data.items()
        if key not in {"detail", "message", "error", "field_errors"}
    }


def classify_message(message, http_status=None):
    lowered = (message or "").lower()
    if "location is not supported" in lowered or "region" in lowered and "not supported" in lowered:
        return "MODEL_REGION_UNSUPPORTED"
    if "high demand" in lowered or "capacity" in lowered or "overloaded" in lowered or "unavailable" in lowered and http_status == 503:
        return "MODEL_CAPACITY_BUSY"
    if "quota" in lowered or "billing" in lowered or "insufficient" in lowered and "balance" in lowered:
        return "MODEL_QUOTA_EXCEEDED"
    if http_status == 429 or "rate limit" in lowered or "resource_exhausted" in lowered:
        return "MODEL_RATE_LIMITED"
    if any(phrase in lowered for phrase in ("api key not valid", "invalid api key", "invalid_api_key", "authentication failed")):
        return "MODEL_CREDENTIAL_INVALID"
    if http_status in {401, 403} and any(word in lowered for word in ("api", "key", "credential", "permission")):
        return "MODEL_CREDENTIAL_INVALID"
    if http_status == 404 and "model" in lowered:
        return "MODEL_NOT_AVAILABLE"
    if any(word in message for word in ("缺少可用配置", "缺少启用的系统角色", "没有绑定", "模型未配置")):
        return "MODEL_CONFIGURATION_MISSING"
    if "模型" in message and any(word in message for word in ("超时", "timed out", "timeout")):
        return "MODEL_TIMEOUT"
    if "模型" in message and any(word in message for word in ("无法处理", "不可解析", "不是合法 JSON", "缺少 candidates", "缺少 choices")):
        return "MODEL_RESPONSE_INVALID"
    if "七牛" in message and any(word in message for word in ("配置不完整", "access_key", "secret_key", "bucket")):
        return "STORAGE_CONFIGURATION_MISSING"
    if "七牛" in message or "存储" in message:
        return "STORAGE_UNAVAILABLE"
    if "opensearch" in lowered or "检索服务" in message or "向量模型" in message:
        return "SEARCH_UNAVAILABLE"
    if "celery" in lowered or "后台队列" in message or "任务长时间未开始" in message:
        return "QUEUE_UNAVAILABLE"
    if "解析" in message or "docling" in lowered:
        return "DOCUMENT_PARSE_FAILED"
    if "文件" in message and ("大小" in message or "mb" in lowered):
        return "FILE_TOO_LARGE"
    if "仅支持" in message and "文件" in message:
        return "FILE_TYPE_INVALID"
    if http_status == 401:
        return "AUTH_REQUIRED"
    if http_status == 403:
        return "PERMISSION_DENIED"
    if http_status == 404:
        return "RESOURCE_NOT_FOUND"
    if http_status == 409:
        return "STATE_CONFLICT"
    if http_status and http_status >= 500:
        return "INTERNAL_ERROR"
    return "VALIDATION_ERROR"


def provider_error_info(http_status, body, *, provider="", stage=""):
    upstream_message = ""
    upstream_status = ""
    try:
        payload = json.loads(body or "{}")
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            upstream_message = str(error.get("message") or "")
            upstream_status = str(error.get("status") or error.get("code") or "")
    except (json.JSONDecodeError, TypeError):
        upstream_message = ""
    code = classify_message(f"{upstream_status} {upstream_message}", http_status)
    if code in {"VALIDATION_ERROR", "INTERNAL_ERROR"}:
        if http_status in {401, 403}:
            code = "MODEL_CREDENTIAL_INVALID"
        elif http_status == 404:
            code = "MODEL_NOT_AVAILABLE"
        elif http_status == 429:
            code = "MODEL_RATE_LIMITED"
        elif http_status == 503:
            code = "MODEL_CAPACITY_BUSY"
        elif http_status >= 500:
            code = "MODEL_PROVIDER_UNAVAILABLE"
        else:
            code = "MODEL_PROVIDER_UNAVAILABLE"
    definition = _definition(code)
    details = {"provider": provider, "http_status": http_status, "stage": stage}
    return build_error_info(code, trace_id=new_trace_id(), details=details), sanitize_text(upstream_message or body, 1200)


def build_error_info(code, *, trace_id=None, message="", details=None):
    definition = _definition(code)
    safe_details = {
        key: sanitize_text(value, 300) if isinstance(value, str) else value
        for key, value in (details or {}).items() if key in DETAIL_KEYS and value not in (None, "")
    }
    return {
        "code": code,
        "message": sanitize_text(message, 300) or definition.message,
        "reason": definition.reason,
        "solution": definition.solution,
        "retryable": definition.retryable,
        "action": _action(definition),
        "trace_id": trace_id or new_trace_id(),
        "details": safe_details,
    }


def error_info_from_exception(exc, *, trace_id=None, details=None, fallback_code=None):
    if isinstance(exc, ClassifiedError):
        code = exc.error_code
        merged = {**getattr(exc, "error_details", {}), **(details or {})}
        info = build_error_info(code, trace_id=trace_id or getattr(exc, "trace_id", None), message=getattr(exc, "public_message", ""), details=merged)
        diagnostic = getattr(exc, "cause_detail", "") or str(exc)
    elif isinstance(exc, DatabaseError):
        info = build_error_info("DATABASE_UNAVAILABLE", trace_id=trace_id, details=details)
        diagnostic = str(exc)
    elif isinstance(exc, ImproperlyConfigured):
        code = classify_message(str(exc))
        info = build_error_info(code, trace_id=trace_id, details=details)
        diagnostic = str(exc)
    else:
        code = fallback_code or classify_message(str(exc))
        if code == "VALIDATION_ERROR" and not isinstance(exc, (ValueError, Http404, PermissionDenied)):
            code = "INTERNAL_ERROR"
        info = build_error_info(code, trace_id=trace_id, details=details)
        diagnostic = str(exc)
    log_error(info, diagnostic, exc=exc)
    return info


def log_error(info, diagnostic="", *, exc=None):
    payload = {
        "trace_id": info["trace_id"],
        "code": info["code"],
        "details": info.get("details", {}),
        "diagnostic": sanitize_text(diagnostic, 4000),
    }
    if info["code"] == "INTERNAL_ERROR" and exc is not None:
        logger.error("testhub_error %s", payload, exc_info=(type(exc), exc, exc.__traceback__))
    else:
        logger.warning("testhub_error %s", payload)


def envelope(error_info, *, field_errors=None, legacy_data=None):
    payload = {
        "error": error_info,
        "detail": error_info["message"],
        "field_errors": field_errors or {},
    }
    if isinstance(legacy_data, dict):
        for key, value in legacy_data.items():
            if key not in payload:
                payload[key] = value
        if legacy_data.get("detail") not in (None, ""):
            payload["detail"] = legacy_data["detail"]
        elif legacy_data.get("message") not in (None, ""):
            payload["detail"] = legacy_data["message"]
    return payload


def app_exception_handler(exc, context):
    request = context.get("request")
    trace_id = getattr(request, "trace_id", None) or new_trace_id()
    if isinstance(exc, AppError):
        info = error_info_from_exception(exc, trace_id=trace_id)
        return Response(envelope(info), status=exc.status_code)

    response = drf_exception_handler(exc, context)
    if response is not None:
        original = response.data
        message = _message_text(original)
        if isinstance(exc, exceptions.ValidationError):
            code = "VALIDATION_ERROR"
        elif isinstance(exc, exceptions.NotAuthenticated):
            code = "AUTH_REQUIRED"
        elif isinstance(exc, exceptions.PermissionDenied):
            code = "PERMISSION_DENIED"
        elif isinstance(exc, exceptions.NotFound):
            code = "RESOURCE_NOT_FOUND"
        else:
            code = classify_message(message, response.status_code)
        info = build_error_info(
            code,
            trace_id=trace_id,
            message=message if response.status_code < 500 else "",
        )
        response.data = envelope(info, field_errors=field_errors_from_data(original), legacy_data=original)
        response["X-Trace-ID"] = trace_id
        return response

    info = error_info_from_exception(exc, trace_id=trace_id)
    return Response(envelope(info), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

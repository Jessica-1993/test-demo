from django.http import JsonResponse

from .errors import build_error_info, classify_message, envelope, field_errors_from_data, new_trace_id


class ApiErrorEnvelopeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.trace_id = request.headers.get("X-Trace-ID") or new_trace_id()
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            response["X-Trace-ID"] = request.trace_id
            if response.status_code >= 400 and hasattr(response, "data"):
                data = response.data
                if not (isinstance(data, dict) and isinstance(data.get("error"), dict)):
                    message = ""
                    if isinstance(data, dict):
                        message = data.get("detail") or data.get("message") or ""
                    elif isinstance(data, str):
                        message = data
                    code = classify_message(str(message), response.status_code)
                    info = build_error_info(
                        code,
                        trace_id=request.trace_id,
                        message=str(message) if response.status_code < 500 else "",
                    )
                    response.data = envelope(
                        info,
                        field_errors=field_errors_from_data(data),
                        legacy_data=data if isinstance(data, dict) else None,
                    )
            elif response.status_code >= 400:
                code = classify_message("", response.status_code)
                info = build_error_info(code, trace_id=request.trace_id)
                response = JsonResponse(
                    envelope(info),
                    status=response.status_code,
                    json_dumps_params={"ensure_ascii": False},
                )
                response["X-Trace-ID"] = request.trace_id
        return response

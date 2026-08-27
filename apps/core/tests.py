import json

from django.test import SimpleTestCase
from django.http import HttpResponseNotFound
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory

from .errors import (
    app_exception_handler,
    provider_error_info,
    sanitize_text,
)
from .middleware import ApiErrorEnvelopeMiddleware


class ErrorContractTests(SimpleTestCase):
    def setUp(self):
        self.request = APIRequestFactory().get("/api/example/")
        self.request.trace_id = "ERR-TEST-0001"

    def test_validation_error_keeps_legacy_fields_and_adds_contract(self):
        response = app_exception_handler(
            exceptions.ValidationError({"name": ["不能为空"]}),
            {"request": self.request, "view": None},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(response.data["error"]["trace_id"], "ERR-TEST-0001")
        self.assertEqual(response.data["field_errors"]["name"], ["不能为空"])
        self.assertEqual(response.data["name"], ["不能为空"])

    def test_unknown_exception_is_hidden_from_client(self):
        response = app_exception_handler(
            RuntimeError("database password=top-secret"),
            {"request": self.request, "view": None},
        )

        serialized = json.dumps(response.data, ensure_ascii=False)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["error"]["code"], "INTERNAL_ERROR")
        self.assertNotIn("top-secret", serialized)

    def test_provider_errors_are_classified_without_raw_body(self):
        region, _diagnostic = provider_error_info(
            400,
            '{"error":{"message":"User location is not supported for the API use.","status":"FAILED_PRECONDITION"}}',
            provider="gemini",
            stage="用例生成",
        )
        busy, _diagnostic = provider_error_info(
            503,
            '{"error":{"message":"This model is currently experiencing high demand.","status":"UNAVAILABLE"}}',
            provider="gemini",
            stage="用例生成",
        )

        self.assertEqual(region["code"], "MODEL_REGION_UNSUPPORTED")
        self.assertEqual(busy["code"], "MODEL_CAPACITY_BUSY")
        self.assertTrue(busy["retryable"])
        self.assertNotIn("high demand", json.dumps(busy, ensure_ascii=False))

    def test_secret_sanitizer_masks_keys_and_authorization(self):
        value = "https://example.test?key=AIza-SECRET-123456789 Authorization: Bearer sk-secret-token-value"
        sanitized = sanitize_text(value)
        self.assertNotIn("AIza-SECRET", sanitized)
        self.assertNotIn("sk-secret", sanitized)

    def test_middleware_wraps_manual_error_response(self):
        middleware = ApiErrorEnvelopeMiddleware(lambda _request: Response({"detail": "只能处理草稿"}, status=409))
        response = middleware(self.request)

        self.assertEqual(response.data["detail"], "只能处理草稿")
        self.assertEqual(response.data["error"]["code"], "STATE_CONFLICT")
        self.assertEqual(response["X-Trace-ID"], self.request.trace_id)

    def test_middleware_replaces_html_api_404(self):
        middleware = ApiErrorEnvelopeMiddleware(
            lambda _request: HttpResponseNotFound("<html>debug 404</html>", content_type="text/html"),
        )
        response = middleware(self.request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(payload["error"]["code"], "RESOURCE_NOT_FOUND")
        self.assertNotIn("debug 404", response.content.decode())

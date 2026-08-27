import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from apps.core.errors import build_error_info, log_error, provider_error_info


DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com"


def normalize_gemini_base_url(base_url):
    base_url = (base_url or DEFAULT_GEMINI_BASE_URL).rstrip("/")
    if base_url.endswith("/v1beta/models"):
        return base_url.removesuffix("/models")
    if base_url.endswith("/v1beta"):
        return base_url
    return f"{base_url}/v1beta"


def normalize_gemini_model_name(model_name):
    model_name = (model_name or "").strip()
    if model_name.startswith("models/"):
        return model_name
    return f"models/{model_name}"


class LLMConnectionTester:
    def __init__(self, config):
        self.config = config

    def test(self):
        if self.config.protocol == "openai_responses":
            return self._test_openai_responses()
        if self.config.protocol == "gemini":
            return self._test_gemini()
        return self._test_openai_compatible()

    def _test_openai_compatible(self):
        base_url = self.config.base_url.rstrip("/")
        if base_url.endswith("/v1/chat/completions"):
            url = base_url
        elif base_url.endswith("/v1"):
            url = f"{base_url}/chat/completions"
        else:
            url = f"{base_url}/v1/chat/completions"

        payload = {
            "model": self.config.model_name,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": min(self.config.max_tokens, 32),
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        return self._post_json(url, payload, headers)

    def _test_openai_responses(self):
        base_url = self.config.base_url.rstrip("/")
        if base_url.endswith("/v1/responses"):
            url = base_url
        elif base_url.endswith("/v1"):
            url = f"{base_url}/responses"
        else:
            url = f"{base_url}/v1/responses"

        payload = {
            "model": self.config.model_name,
            "input": "ping",
            "max_output_tokens": min(self.config.max_tokens, 32),
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
        }
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        return self._post_json(url, payload, headers)

    def _test_gemini(self):
        base_url = normalize_gemini_base_url(self.config.base_url)
        model = quote(normalize_gemini_model_name(self.config.model_name), safe="/")
        if getattr(self.config, "usage", "") == "embedding":
            url = f"{base_url}/{model}:embedContent?key={quote(self.config.api_key, safe='')}"
            payload = {
                "model": normalize_gemini_model_name(self.config.model_name),
                "content": {"parts": [{"text": "ping"}]},
                "taskType": "RETRIEVAL_QUERY",
                "outputDimensionality": self.config.embedding_dimension,
            }
            return self._post_json(url, payload, {"Content-Type": "application/json"})
        url = f"{base_url}/{model}:generateContent?key={quote(self.config.api_key, safe='')}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": "ping"}],
                }
            ],
            "generationConfig": {
                "maxOutputTokens": min(self.config.max_tokens, 32),
                "temperature": self.config.temperature,
                "topP": self.config.top_p,
            },
        }
        return self._post_json(url, payload, {"Content-Type": "application/json"})

    def _post_json(self, url, payload, headers):
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8")
                return {
                    "ok": 200 <= response.status < 300,
                    "status_code": response.status,
                    "message": "连接测试成功",
                }
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            info, diagnostic = provider_error_info(
                exc.code, body, provider=self.config.provider, stage="模型连接测试",
            )
            log_error(info, diagnostic, exc=exc)
            return {
                "ok": False,
                "status_code": exc.code,
                "message": info["message"],
                "error": info,
                "detail": info["message"],
            }
        except URLError as exc:
            info = build_error_info(
                "MODEL_PROVIDER_UNAVAILABLE",
                details={"provider": self.config.provider, "stage": "模型连接测试"},
            )
            log_error(info, str(exc.reason), exc=exc)
            return {
                "ok": False,
                "status_code": None,
                "message": info["message"],
                "error": info,
                "detail": info["message"],
            }
        except TimeoutError as exc:
            info = build_error_info(
                "MODEL_TIMEOUT",
                details={"provider": self.config.provider, "stage": "模型连接测试"},
            )
            log_error(info, "模型连接测试超时", exc=exc)
            return {
                "ok": False,
                "status_code": None,
                "message": info["message"],
                "error": info,
                "detail": info["message"],
            }


class LLMModelFetcher:
    def __init__(self, protocol, provider, base_url, api_key, usage=""):
        self.protocol = protocol
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.usage = usage

    def fetch(self):
        if self.protocol == "gemini":
            return self._fetch_gemini_models()
        return self._fetch_openai_compatible_models()

    def _fetch_openai_compatible_models(self):
        if self.base_url.endswith("/v1/models"):
            url = self.base_url
        elif self.base_url.endswith("/v1"):
            url = f"{self.base_url}/models"
        else:
            url = f"{self.base_url}/v1/models"

        request = Request(
            url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="GET",
        )
        result = self._request_json(request)
        if not result["ok"]:
            return result

        raw_models = result["data"].get("data", [])
        models = sorted(
            [
                item.get("id")
                for item in raw_models
                if isinstance(item, dict) and item.get("id")
            ]
        )
        return {
            "ok": True,
            "models": models,
            "message": f"获取到 {len(models)} 个模型",
        }

    def _fetch_gemini_models(self):
        base_url = normalize_gemini_base_url(self.base_url)
        models = []
        page_token = ""
        while True:
            url = f"{base_url}/models?pageSize=1000&key={quote(self.api_key, safe='')}"
            if page_token:
                url = f"{url}&pageToken={quote(page_token, safe='')}"
            result = self._request_json(Request(url, method="GET"))
            if not result["ok"]:
                return result

            data = result["data"]
            for item in data.get("models", []):
                methods = item.get("supportedGenerationMethods", [])
                name = item.get("name", "")
                required_method = "embedContent" if self.usage == "embedding" else "generateContent"
                if required_method in methods and name.startswith("models/"):
                    models.append(name.removeprefix("models/"))
            page_token = data.get("nextPageToken") or ""
            if not page_token:
                break

        models.sort()
        return {
            "ok": True,
            "models": models,
            "message": f"获取到 {len(models)} 个模型",
        }

    def _request_json(self, request):
        try:
            with urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8")
                return {
                    "ok": 200 <= response.status < 300,
                    "status_code": response.status,
                    "data": json.loads(body or "{}"),
                }
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            info, diagnostic = provider_error_info(
                exc.code, body, provider=self.provider, stage="获取模型列表",
            )
            log_error(info, diagnostic, exc=exc)
            return {
                "ok": False,
                "status_code": exc.code,
                "message": info["message"],
                "error": info,
                "detail": info["message"],
            }
        except URLError as exc:
            info = build_error_info(
                "MODEL_PROVIDER_UNAVAILABLE",
                details={"provider": self.provider, "stage": "获取模型列表"},
            )
            log_error(info, str(exc.reason), exc=exc)
            return {
                "ok": False,
                "status_code": None,
                "message": info["message"],
                "error": info,
                "detail": info["message"],
            }
        except TimeoutError as exc:
            info = build_error_info(
                "MODEL_TIMEOUT", details={"provider": self.provider, "stage": "获取模型列表"},
            )
            log_error(info, "获取模型列表超时", exc=exc)
            return {
                "ok": False,
                "status_code": None,
                "message": info["message"],
                "error": info,
                "detail": info["message"],
            }
        except json.JSONDecodeError:
            info = build_error_info(
                "MODEL_RESPONSE_INVALID", details={"provider": self.provider, "stage": "获取模型列表"},
            )
            return {
                "ok": False,
                "status_code": None,
                "message": info["message"],
                "error": info,
                "detail": info["message"],
            }

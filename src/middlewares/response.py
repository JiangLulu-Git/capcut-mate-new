from fastapi import Request
from fastapi.responses import JSONResponse
from exceptions import CustomError, CustomException
from starlette.middleware.base import BaseHTTPMiddleware
from src.schemas.api_standard import API_CODE_SUCCESS
from src.utils.logger import logger
import json

_ENVELOPE_KEYS = frozenset({"code", "message", "data"})


class ResponseMiddleware(BaseHTTPMiddleware):
    """统一响应：成功 {code:1, message, data}；失败 {code, message, data:null}。"""

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/output/"):
            return await call_next(request)

        lang = "zh"
        try:
            lang = self._get_language_from_request(request)
            response = await call_next(request)

            if response.status_code != 200:
                return await self._handle_non_200_response(response, lang)

            if self._is_json_response(response):
                return await self._process_json_response(response, lang)

            return response

        except CustomException as e:
            return self._handle_custom_exception(e, lang)
        except Exception as e:
            return self._handle_generic_exception(e, lang)

    def _get_language_from_request(self, request: Request) -> str:
        try:
            accept_lang = request.headers.get("Accept-Language", "zh")
            if not accept_lang or not accept_lang.strip():
                return "zh"

            lang_parts = accept_lang.split(",")[0].strip()
            if not lang_parts:
                return "zh"

            lang_code_parts = lang_parts.split("-")
            if not lang_code_parts or not lang_code_parts[0]:
                return "zh"

            lang = lang_code_parts[0].lower()
            return lang if lang in ["zh", "en"] else "zh"

        except Exception:
            return "zh"

    def _success_message(self, lang: str) -> str:
        return CustomError.SUCCESS.as_dict(lang=lang)["message"]

    def _is_standard_envelope(self, payload: dict) -> bool:
        return (
            isinstance(payload, dict)
            and "code" in payload
            and "message" in payload
            and "data" in payload
            and not any(k for k in payload if k not in _ENVELOPE_KEYS)
        )

    def _normalize_to_envelope(self, payload: dict, lang: str) -> dict:
        """将路由 JSON 或历史扁平响应统一为 {code, message, data}。"""
        if self._is_standard_envelope(payload):
            out = dict(payload)
            if out["code"] == 0:
                out["code"] = API_CODE_SUCCESS
            return out

        # 历史扁平：{code, message, task_id, draft_id, ...}（message 常被业务 message 覆盖）
        if isinstance(payload, dict) and "code" in payload and "message" in payload:
            top_msg = payload.get("message")
            business = {
                k: v for k, v in payload.items() if k not in _ENVELOPE_KEYS
            }
            raw_code = payload["code"]
            if raw_code in (0, 1):
                success_msg = self._success_message(lang)
                # 旧中间件 **展平 时，任务阶段说明会顶掉顶层「成功」
                if top_msg and top_msg != success_msg and "message" not in business:
                    business["message"] = top_msg
                return {
                    "code": API_CODE_SUCCESS,
                    "message": success_msg,
                    "data": business or None,
                }
            return {
                "code": raw_code,
                "message": payload["message"],
                "data": business or None,
            }

        business = payload if payload else None
        return {
            "code": API_CODE_SUCCESS,
            "message": self._success_message(lang),
            "data": business,
        }

    def _handle_422_error(self, body_str: str, lang: str) -> JSONResponse:
        try:
            error_data = json.loads(body_str)

            validation_messages = []
            if "detail" in error_data:
                for error in error_data["detail"]:
                    if "loc" in error and "msg" in error:
                        field = ".".join(str(part) for part in error["loc"] if part != "body")
                        message = f"{field}: {error['msg']}"
                        validation_messages.append(message)

            error_message = "; ".join(validation_messages) if validation_messages else ""
            error_response = CustomError.PARAM_VALIDATION_FAILED.as_dict(
                detail=error_message, lang=lang,
            )
            return JSONResponse(status_code=200, content=error_response)

        except json.JSONDecodeError:
            logger.warning(f"Failed to parse 422 response body: {body_str}")

            error_response = CustomError.PARAM_VALIDATION_FAILED.as_dict(
                detail=body_str, lang=lang,
            )
            return JSONResponse(status_code=200, content=error_response)

    async def _handle_non_200_response(self, response, lang: str) -> JSONResponse:
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        body_str = body.decode()

        if response.status_code == 422:
            return self._handle_422_error(body_str, lang)

        logger.error(f"Non-200 response: {response.status_code} - {body_str}")
        error_response = {
            "code": response.status_code,
            "message": f"HTTP Error {response.status_code}, detail: {body_str}",
            "data": None,
        }

        return JSONResponse(status_code=200, content=error_response)

    def _is_json_response(self, response) -> bool:
        return response.headers.get("content-type") == "application/json"

    async def _process_json_response(self, response, lang: str):
        body = [section async for section in response.body_iterator]
        if not body:
            return response

        body_str = b"".join(body).decode()

        try:
            payload = json.loads(body_str)
            if not isinstance(payload, dict):
                return response

            unified = self._normalize_to_envelope(payload, lang)
            return JSONResponse(
                status_code=response.status_code,
                content=unified,
            )

        except json.JSONDecodeError:
            logger.warning(f"JSON decode error: {body_str}")
            return response

    def _handle_custom_exception(self, e: CustomException, lang: str) -> JSONResponse:
        logger.warning(
            f"Custom exception: {e.err.code} - {e.err.cn_message}"
            + (f" ({e.detail})" if e.detail else "")
        )

        error_response = e.err.as_dict(detail=e.detail, lang=lang)
        return JSONResponse(status_code=200, content=error_response)

    def _handle_generic_exception(self, e: Exception, lang: str) -> JSONResponse:
        logger.warning(f"Internal server error: {str(e)}")

        error_response = CustomError.INTERNAL_SERVER_ERROR.as_dict(
            detail=str(e), lang=lang,
        )
        return JSONResponse(status_code=200, content=error_response)

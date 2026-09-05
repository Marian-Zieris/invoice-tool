from typing import Any, Dict, Optional


def api_success(data: Optional[Any] = None, message: str = "OK") -> Dict[str, Any]:
    return {
        "success": True,
        "data": data,
        "message": message,
    }


def api_error(message: str, error_code: Optional[str] = None, data: Optional[Any] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "success": False,
        "data": data,
        "message": message,
    }
    if error_code is not None:
        payload["error_code"] = error_code
    return payload

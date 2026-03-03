"""
UNS Data Engine — Payload Decoder

Strategy pattern：Phase 1 只實作 JSON，架構上預留擴展點。
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger("uns.decoder")


class DecodeResult:
    """解碼結果。"""

    __slots__ = ("data", "error")

    def __init__(self, data: Optional[dict] = None, error: Optional[str] = None):
        self.data = data
        self.error = error

    @property
    def ok(self) -> bool:
        return self.data is not None


class Decoder(ABC):
    """Decoder 基底類別。"""

    @abstractmethod
    def decode(self, payload: bytes) -> DecodeResult:
        """將 raw bytes 解碼為 Python dict。"""
        ...


class JsonDecoder(Decoder):
    """JSON payload 解碼器。"""

    def decode(self, payload: bytes) -> DecodeResult:
        if not payload:
            return DecodeResult(error="empty payload")
        try:
            text = payload.decode("utf-8")
            data = json.loads(text)
            if not isinstance(data, dict):
                return DecodeResult(error=f"expected JSON object, got {type(data).__name__}")
            return DecodeResult(data=data)
        except UnicodeDecodeError as e:
            logger.warning("UTF-8 decode error: %s", e)
            return DecodeResult(error=f"UTF-8 decode error: {e}")
        except json.JSONDecodeError as e:
            logger.warning("JSON parse error: %s", e)
            return DecodeResult(error=f"JSON parse error: {e}")


# ── Decoder Registry ──────────────────────────────────────────

_DECODERS: dict[str, type[Decoder]] = {
    "json": JsonDecoder,
}


def get_decoder(decoder_type: str) -> Decoder:
    """取得指定類型的 Decoder 實例。"""
    cls = _DECODERS.get(decoder_type)
    if cls is None:
        raise ValueError(f"unsupported decoder type: {decoder_type!r}")
    return cls()

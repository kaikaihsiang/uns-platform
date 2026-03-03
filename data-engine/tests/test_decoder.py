"""
Tests for UNS Data Engine — Decoder
"""

import pytest

from src.decoder import JsonDecoder, DecodeResult, get_decoder


class TestJsonDecoder:
    """JSON Decoder 測試。"""

    def setup_method(self):
        self.decoder = JsonDecoder()

    def test_valid_json(self):
        payload = b'{"temperature": 25.3, "pressure": 2.1}'
        result = self.decoder.decode(payload)
        assert result.ok
        assert result.data == {"temperature": 25.3, "pressure": 2.1}

    def test_nested_json(self):
        payload = b'{"_meta": {"timestamp": "2024-01-15T08:30:00Z"}, "data": {"temp": 25.0}}'
        result = self.decoder.decode(payload)
        assert result.ok
        assert result.data["_meta"]["timestamp"] == "2024-01-15T08:30:00Z"
        assert result.data["data"]["temp"] == 25.0

    def test_empty_payload(self):
        result = self.decoder.decode(b"")
        assert not result.ok
        assert "empty" in result.error

    def test_invalid_json(self):
        result = self.decoder.decode(b"not json at all")
        assert not result.ok
        assert "JSON parse error" in result.error

    def test_non_utf8(self):
        result = self.decoder.decode(b"\xff\xfe")
        assert not result.ok
        assert "UTF-8" in result.error or "decode" in result.error.lower()

    def test_json_array_not_object(self):
        """JSON 陣列不是 object → 錯誤。"""
        result = self.decoder.decode(b'[1, 2, 3]')
        assert not result.ok
        assert "expected JSON object" in result.error

    def test_json_number(self):
        """純數字不是 object → 錯誤。"""
        result = self.decoder.decode(b"42")
        assert not result.ok

    def test_unicode_payload(self):
        """含 Unicode 的 JSON。"""
        payload = '{"名稱": "印刷機溫度"}'.encode("utf-8")
        result = self.decoder.decode(payload)
        assert result.ok
        assert result.data["名稱"] == "印刷機溫度"

    def test_large_payload(self):
        """大 payload。"""
        data = {f"key_{i}": float(i) for i in range(100)}
        import json
        payload = json.dumps(data).encode("utf-8")
        result = self.decoder.decode(payload)
        assert result.ok
        assert len(result.data) == 100


class TestDecoderRegistry:
    """Decoder Registry 測試。"""

    def test_get_json_decoder(self):
        decoder = get_decoder("json")
        assert isinstance(decoder, JsonDecoder)

    def test_unknown_decoder(self):
        with pytest.raises(ValueError, match="unsupported"):
            get_decoder("sparkplug")

    def test_unknown_decoder_custom(self):
        with pytest.raises(ValueError):
            get_decoder("custom_xyz")

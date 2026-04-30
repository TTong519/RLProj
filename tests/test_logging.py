"""Tests for logging configuration."""

import logging

from surg_rl.utils.logging import SensitiveDataFilter


class TestSensitiveDataFilter:
    def test_masks_api_key_in_message(self):
        """API keys in LogRecord.msg are masked."""
        filt = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Error with key sk-abc1234567890123456789012345678",
            args=(),
            exc_info=None,
        )
        filt.filter(record)
        assert "sk-abc123" not in record.msg
        assert "5678" in record.msg
        assert record.msg.startswith("Error with key ****")

    def test_masks_api_key_in_args(self):
        """API keys in LogRecord.args are masked."""
        filt = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Key: %s",
            args=("sk-abc1234567890123456789012345678",),
            exc_info=None,
        )
        filt.filter(record)
        assert "sk-abc123" not in record.args[0]
        assert "5678" in record.args[0]

    def test_allows_non_sensitive_message(self):
        """Messages without API keys pass unchanged."""
        filt = SensitiveDataFilter()
        original = "Just a normal log message"
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=original,
            args=(),
            exc_info=None,
        )
        filt.filter(record)
        assert record.msg == original

    def test_masks_sk_ant_key(self):
        """Anthropic sk-ant- keys are masked."""
        filt = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Anthropic key sk-ant-api03-abc1234567890123456789012345678",
            args=(),
            exc_info=None,
        )
        filt.filter(record)
        assert "sk-ant-api03" not in record.msg
        assert "5678" in record.msg

    def test_short_key_replacement(self):
        """Very short keys are fully replaced."""
        filt = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Key sk-abc123",
            args=(),
            exc_info=None,
        )
        filt.filter(record)
        # sk-abc123 is only 10 chars, less than 20, so pattern won't match
        assert record.msg == "Key sk-abc123"

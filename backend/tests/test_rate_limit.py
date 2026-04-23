"""Tests for rate limiting behavior (check_rate_limit)."""
from unittest.mock import MagicMock

import main


def _pipeline_returning(num_requests):
    pipe = MagicMock()
    pipe.execute.return_value = (0, 1, num_requests, True)
    return pipe


class TestCheckRateLimit:
    def test_allows_request_under_limit(self, mock_redis):
        mock_redis.pipeline.return_value = _pipeline_returning(1)
        assert main.check_rate_limit("1.2.3.4") is True

    def test_allows_request_at_exactly_max(self, mock_redis):
        mock_redis.pipeline.return_value = _pipeline_returning(main.MAX_REQUESTS)
        assert main.check_rate_limit("1.2.3.4") is True

    def test_rejects_request_over_limit(self, mock_redis):
        mock_redis.pipeline.return_value = _pipeline_returning(main.MAX_REQUESTS + 1)
        assert main.check_rate_limit("1.2.3.4") is False

    def test_failsafe_allows_when_redis_errors(self, mock_redis):
        mock_redis.pipeline.side_effect = Exception("redis down")
        # When Redis fails, we should allow the request rather than block all traffic.
        assert main.check_rate_limit("1.2.3.4") is True

    def test_uses_ip_in_redis_key(self, mock_redis):
        pipe = _pipeline_returning(1)
        mock_redis.pipeline.return_value = pipe
        main.check_rate_limit("10.0.0.7")

        # zadd is called with the rate-limit key; verify the IP is namespaced into the key
        keys_used = [call.args[0] for call in pipe.zadd.call_args_list]
        assert any("10.0.0.7" in k for k in keys_used)

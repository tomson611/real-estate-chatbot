"""Tests for get_rentcast_data: caching, URL construction, error handling."""
import pickle
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

import main


SAMPLE_API_RESPONSE = [
    {
        "formattedAddress": "123 Main St, Austin, TX 78701",
        "price": 500000,
        "bedrooms": 3,
        "bathrooms": 2,
        "squareFootage": 1800,
        "propertyType": "Single-Family",
        "city": "Austin",
        "state": "TX",
        "yearBuilt": 2010,
        "lotSize": 5000,
        "status": "Active",
        "daysOnMarket": 14,
        "latitude": 30.2672,
        "longitude": -97.7431,
    }
]


def _mock_http_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else []
    resp.text = text
    return resp


class TestGetRentcastData:
    def test_returns_cached_data_on_cache_hit(self, mock_redis):
        cached = [{"address": "Cached property"}]
        mock_redis.get.return_value = pickle.dumps(cached)

        with patch("main.requests.get") as mock_get:
            result = main.get_rentcast_data(location="Austin, TX")

        assert result == cached
        mock_get.assert_not_called()  # API should not be called on cache hit

    def test_fetches_from_api_on_cache_miss(self, mock_redis):
        mock_redis.get.return_value = None

        with patch("main.requests.get", return_value=_mock_http_response(200, SAMPLE_API_RESPONSE)) as mock_get:
            result = main.get_rentcast_data(location="Austin, TX")

        mock_get.assert_called_once()
        assert len(result) == 1
        assert result[0]["address"] == "123 Main St, Austin, TX 78701"
        assert result[0]["price"] == "$500,000.00"
        assert result[0]["beds"] == 3
        assert result[0]["baths"] == 2
        assert result[0]["sqft"] == "1,800"

    def test_caches_api_response(self, mock_redis):
        mock_redis.get.return_value = None

        with patch("main.requests.get", return_value=_mock_http_response(200, SAMPLE_API_RESPONSE)):
            main.get_rentcast_data(location="Austin, TX")

        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args.args
        assert args[0].startswith("rentcast:")       # cache key
        assert args[1] == main.CACHE_TTL             # TTL
        # args[2] is the pickled payload

    def test_parses_city_and_state_from_comma_separated_location(self, mock_redis):
        with patch("main.requests.get", return_value=_mock_http_response(200, [])) as mock_get:
            main.get_rentcast_data(location="Austin, TX")

        url = mock_get.call_args.args[0]
        assert "city=Austin" in url
        assert "state=TX" in url

    def test_infers_state_for_known_city(self, mock_redis):
        with patch("main.requests.get", return_value=_mock_http_response(200, [])) as mock_get:
            main.get_rentcast_data(location="Los Angeles")

        url = mock_get.call_args.args[0]
        assert "state=CA" in url

    def test_adds_all_filter_params_to_url(self, mock_redis):
        with patch("main.requests.get", return_value=_mock_http_response(200, [])) as mock_get:
            main.get_rentcast_data(
                location="Austin, TX",
                max_price=500000,
                property_type="Condo",
                min_bedrooms=3,
                min_bathrooms=2.5,
            )

        url = mock_get.call_args.args[0]
        assert "maxPrice=500000" in url
        assert "propertyType=Condo" in url
        assert "minBedrooms=3" in url
        assert "minBathrooms=2.5" in url

    def test_omits_filter_params_when_not_provided(self, mock_redis):
        with patch("main.requests.get", return_value=_mock_http_response(200, [])) as mock_get:
            main.get_rentcast_data(location="Austin, TX")

        url = mock_get.call_args.args[0]
        assert "maxPrice" not in url
        assert "propertyType" not in url
        assert "minBedrooms" not in url
        assert "minBathrooms" not in url

    def test_sends_api_key_header(self, mock_redis):
        with patch("main.requests.get", return_value=_mock_http_response(200, [])) as mock_get:
            main.get_rentcast_data(location="Austin, TX")

        headers = mock_get.call_args.kwargs["headers"]
        assert headers["X-Api-Key"] == "test-rentcast-key"
        assert headers["Content-Type"] == "application/json"

    def test_raises_http_exception_on_non_200(self, mock_redis):
        with patch("main.requests.get", return_value=_mock_http_response(500, [], text="Server error")):
            with pytest.raises(HTTPException) as exc_info:
                main.get_rentcast_data(location="Austin, TX")

        assert exc_info.value.status_code == 500

    def test_raises_http_exception_on_network_error(self, mock_redis):
        import requests as req_lib
        with patch("main.requests.get", side_effect=req_lib.exceptions.ConnectionError("boom")):
            with pytest.raises(HTTPException) as exc_info:
                main.get_rentcast_data(location="Austin, TX")

        assert exc_info.value.status_code == 500

    def test_handles_missing_fields_gracefully(self, mock_redis):
        # Property with very little data -- defaults should kick in
        sparse = [{"formattedAddress": "Unknown"}]
        with patch("main.requests.get", return_value=_mock_http_response(200, sparse)):
            result = main.get_rentcast_data(location="Austin, TX")

        assert result[0]["address"] == "Unknown"
        assert result[0]["beds"] == "N/A"
        assert result[0]["baths"] == "N/A"
        assert result[0]["yearBuilt"] == "N/A"
        assert result[0]["listingAgent"]["name"] == "N/A"
        assert result[0]["listingOffice"]["name"] == "N/A"

    def test_formats_listing_agent_and_office(self, mock_redis):
        data = [{
            "formattedAddress": "1 Oak Ave",
            "price": 400000,
            "listingAgent": {"name": "Jane", "phone": "555", "email": "j@x.com", "website": "x.com"},
            "listingOffice": {"name": "Acme", "phone": "777", "email": "a@x.com"},
            "mlsNumber": "MLS1",
            "mlsName": "MRED",
        }]
        with patch("main.requests.get", return_value=_mock_http_response(200, data)):
            result = main.get_rentcast_data(location="Chicago, IL")

        assert result[0]["listingAgent"] == {
            "name": "Jane", "phone": "555", "email": "j@x.com", "website": "x.com"
        }
        assert result[0]["listingOffice"] == {
            "name": "Acme", "phone": "777", "email": "a@x.com"
        }
        assert result[0]["mlsNumber"] == "MLS1"
        assert result[0]["mlsName"] == "MRED"

"""Tests for pure helper functions: mortgage, property type mapping, cache key."""
import pytest

import main


class TestCalculateMortgagePayment:
    def test_typical_30_year_loan(self):
        # $100,000 at 6% for 30 years → ~$599.55/month
        result = main.calculate_mortgage_payment(100_000, 6.0, 30)
        assert result["monthly_payment"] == pytest.approx(599.55, abs=0.01)
        assert result["total_payment"] == pytest.approx(215_838.19, abs=0.1)
        assert result["total_interest"] == pytest.approx(115_838.19, abs=0.1)

    def test_25_year_loan(self):
        # $300,000 at 3% for 25 years → ~$1,422.63/month
        result = main.calculate_mortgage_payment(300_000, 3.0, 25)
        assert result["monthly_payment"] == pytest.approx(1_422.63, abs=0.1)

    def test_result_preserves_inputs(self):
        result = main.calculate_mortgage_payment(250_000, 4.5, 15)
        assert result["loan_amount"] == 250_000
        assert result["interest_rate"] == 4.5
        assert result["loan_term_years"] == 15

    def test_higher_interest_increases_monthly_payment(self):
        low = main.calculate_mortgage_payment(200_000, 3.0, 30)
        high = main.calculate_mortgage_payment(200_000, 7.0, 30)
        assert high["monthly_payment"] > low["monthly_payment"]

    def test_longer_term_decreases_monthly_payment(self):
        short = main.calculate_mortgage_payment(200_000, 5.0, 15)
        long = main.calculate_mortgage_payment(200_000, 5.0, 30)
        assert long["monthly_payment"] < short["monthly_payment"]
        # ...but costs more in total interest
        assert long["total_interest"] > short["total_interest"]

    def test_total_payment_matches_monthly_times_n_modulo_rounding(self):
        # monthly_payment and total_payment are rounded independently, so they
        # agree only up to ~1 dollar of cumulative rounding over all payments.
        result = main.calculate_mortgage_payment(150_000, 4.0, 20)
        expected_total = result["monthly_payment"] * 20 * 12
        assert result["total_payment"] == pytest.approx(expected_total, abs=1.0)

    def test_total_interest_is_total_minus_principal(self):
        result = main.calculate_mortgage_payment(150_000, 4.0, 20)
        assert result["total_interest"] == pytest.approx(
            result["total_payment"] - result["loan_amount"], abs=0.01
        )


class TestMapPropertyTypeToRentcast:
    @pytest.mark.parametrize("input_str,expected", [
        ("house", "Single-Family"),
        ("single-family", "Single-Family"),
        ("single family", "Single-Family"),
        ("single-family home", "Single-Family"),
        ("detached house", "Single-Family"),
        ("condo", "Condo"),
        ("condominium", "Condo"),
        ("apartment", "Condo"),
        ("flat", "Condo"),
        ("town home", "Townhouse"),
        ("multi-family", "Multi-Family"),
        ("multifamily", "Multi-Family"),
        ("duplex", "Multi-Family"),
        ("triplex", "Multi-Family"),
        ("fourplex", "Multi-Family"),
        ("land", "Land"),
        ("lot", "Land"),
        ("other", "Other"),
    ])
    def test_known_mappings(self, input_str, expected):
        assert main.map_property_type_to_rentcast(input_str) == expected

    def test_case_insensitive(self):
        assert main.map_property_type_to_rentcast("HOUSE") == "Single-Family"
        assert main.map_property_type_to_rentcast("Condo") == "Condo"
        assert main.map_property_type_to_rentcast("CONDOMINIUM") == "Condo"

    def test_townhouse_misclassified_due_to_house_substring(self):
        # Known quirk: "townhouse" contains "house" as a substring, and because
        # the mapping dict iterates in insertion order with substring `in`
        # matching, "house" wins before "townhouse" is checked. Documenting
        # current behavior — use "town home" to get a correct Townhouse mapping.
        assert main.map_property_type_to_rentcast("townhouse") == "Single-Family"

    def test_substring_matches(self):
        # The mapping uses `in` for broader matching
        assert main.map_property_type_to_rentcast("single-family homes") == "Single-Family"
        assert main.map_property_type_to_rentcast("modern condo unit") == "Condo"

    def test_none_input_returns_none(self):
        assert main.map_property_type_to_rentcast(None) is None

    def test_empty_string_returns_none(self):
        assert main.map_property_type_to_rentcast("") is None

    def test_unknown_type_returns_none(self):
        assert main.map_property_type_to_rentcast("mansion") is None
        assert main.map_property_type_to_rentcast("xyz") is None


class TestGetCacheKey:
    def test_all_parameters(self):
        key = main.get_cache_key(
            location="Los Angeles, CA",
            max_price=500000,
            property_type="Condo",
            min_bedrooms=3,
            min_bathrooms=2.0,
        )
        assert key.startswith("rentcast:")
        assert "los angeles, ca" in key
        assert "500000" in key
        assert "Condo" in key
        assert "3" in key
        assert "2.0" in key

    def test_only_location(self):
        key = main.get_cache_key(location="Austin")
        assert "austin" in key
        assert "no_price" in key
        assert "no_type" in key
        assert "no_beds" in key
        assert "no_baths" in key

    def test_location_is_lowercased(self):
        key_upper = main.get_cache_key(location="LOS ANGELES")
        key_lower = main.get_cache_key(location="los angeles")
        assert key_upper == key_lower

    def test_same_params_produce_same_key(self):
        k1 = main.get_cache_key("Austin", 500000, "Condo", 2, 1.5)
        k2 = main.get_cache_key("Austin", 500000, "Condo", 2, 1.5)
        assert k1 == k2

    def test_different_params_produce_different_keys(self):
        k1 = main.get_cache_key("Austin", 500000, "Condo", 2, 1.5)
        k2 = main.get_cache_key("Austin", 600000, "Condo", 2, 1.5)
        assert k1 != k2

    def test_different_location_different_key(self):
        k1 = main.get_cache_key("Austin")
        k2 = main.get_cache_key("Houston")
        assert k1 != k2

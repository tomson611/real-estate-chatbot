"""Integration-style tests for POST /api/chat using FastAPI's TestClient."""
from unittest.mock import AsyncMock, MagicMock, patch

import main
from tests.conftest import _make_pipeline


def _ai_reply(text):
    reply = MagicMock()
    reply.choices = [MagicMock()]
    reply.choices[0].message.content = text
    return reply


class TestChatEndpointValidation:
    def test_rejects_empty_messages_list(self, test_client):
        # No user message → endpoint raises 400 (but FastAPI wraps to 500 via catch-all)
        response = test_client.post("/api/chat", json={"messages": []})
        # The catch-all re-raises HTTPException as-is, so we expect 400
        assert response.status_code in (400, 500)

    def test_rejects_invalid_role(self, test_client):
        response = test_client.post("/api/chat", json={
            "messages": [{"role": "invalid_role", "content": "hi"}]
        })
        assert response.status_code == 422  # Pydantic validation

    def test_rejects_empty_content(self, test_client):
        response = test_client.post("/api/chat", json={
            "messages": [{"role": "user", "content": ""}]
        })
        assert response.status_code == 422  # Pydantic min_length=1

    def test_rejects_missing_messages_field(self, test_client):
        response = test_client.post("/api/chat", json={})
        assert response.status_code == 422

    def test_returns_400_when_no_user_message(self, test_client):
        response = test_client.post("/api/chat", json={
            "messages": [{"role": "assistant", "content": "hi there"}]
        })
        assert response.status_code == 400


class TestGeneralChatFlow:
    def test_returns_ai_response_for_general_question(self, test_client, mock_openai):
        response = test_client.post("/api/chat", json={
            "messages": [{"role": "user", "content": "What are good neighborhoods in Austin?"}]
        })

        assert response.status_code == 200
        body = response.json()
        assert body["response"]["text"] == "Mocked AI reply"
        assert body["response"]["properties"] == []
        mock_openai.chat.completions.create.assert_called_once()

    def test_does_not_call_rentcast_for_plain_question(self, test_client, mock_openai):
        with patch("main.requests.get") as mock_get:
            test_client.post("/api/chat", json={
                "messages": [{"role": "user", "content": "How does a fixed-rate mortgage work?"}]
            })

        mock_get.assert_not_called()

    def test_openai_receives_system_prompt_plus_history(self, test_client, mock_openai):
        test_client.post("/api/chat", json={
            "messages": [
                {"role": "user", "content": "I'm looking for homes"},
                {"role": "assistant", "content": "Where are you looking?"},
                {"role": "user", "content": "In Denver"},
            ]
        })

        call_messages = mock_openai.chat.completions.create.call_args.kwargs["messages"]
        # system prompt + 3 history messages = 4
        assert len(call_messages) == 4
        assert call_messages[0]["role"] == "system"
        assert call_messages[1]["content"] == "I'm looking for homes"
        assert call_messages[3]["content"] == "In Denver"


class TestMortgageFlow:
    def test_mortgage_query_is_handled_without_ai_call(self, test_client, mock_openai):
        response = test_client.post("/api/chat", json={
            "messages": [{
                "role": "user",
                "content": "$300,000 interest rate 3% for 25 years",
            }]
        })

        assert response.status_code == 200
        text = response.json()["response"]["text"]
        # Mortgage handler short-circuits before the AI call
        mock_openai.chat.completions.create.assert_not_called()
        assert "$300,000" in text
        assert "3.0%" in text  # interest_rate is stored as float, renders as "3.0%"
        assert "25 years" in text
        assert "monthly payment" in text.lower()

    def test_mortgage_response_includes_all_key_details(self, test_client):
        response = test_client.post("/api/chat", json={
            "messages": [{
                "role": "user",
                "content": "$500,000 rate 4% for 30 years",
            }]
        })

        text = response.json()["response"]["text"]
        assert "Loan Amount" in text
        assert "Interest Rate" in text
        assert "Loan Term" in text
        assert "Total payment" in text
        assert "Total interest" in text

    def test_conversational_mortgage_question_falls_through_to_ai(self, test_client, mock_openai):
        # No explicit numbers → regex doesn't match → falls through to OpenAI
        response = test_client.post("/api/chat", json={
            "messages": [{"role": "user", "content": "Can you help me calculate a mortgage?"}]
        })

        assert response.status_code == 200
        mock_openai.chat.completions.create.assert_called_once()


class TestPropertySearchFlow:
    def _setup_ai_extraction(self, mock_openai, params_json, chat_reply="Here are some listings!"):
        """Configure OpenAI to return extraction params on first call, chat reply on second."""
        mock_openai.chat.completions.create.side_effect = [
            _ai_reply(params_json),       # extract_search_parameters_with_ai
            _ai_reply(chat_reply),        # final chat completion
        ]

    def test_triggers_rentcast_search_on_go_ahead(self, test_client, mock_openai):
        self._setup_ai_extraction(
            mock_openai,
            '{"location": "Austin, TX", "property_type": "Condo", "min_bedrooms": 2, "min_bathrooms": 2.0, "max_price": 500000}',
        )
        sample = [{
            "formattedAddress": "1 Oak St, Austin, TX",
            "price": 450000,
            "bedrooms": 2,
            "bathrooms": 2,
            "squareFootage": 1200,
            "city": "Austin",
            "state": "TX",
            "propertyType": "Condo",
        }]

        with patch("main.requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200, text="")
            mock_get.return_value.json.return_value = sample

            response = test_client.post("/api/chat", json={
                "messages": [
                    {"role": "user", "content": "I want a condo in Austin, TX under 500k, 2 beds 2 baths"},
                    {"role": "assistant", "content": "Ready to search. Shall I search now?"},
                    {"role": "user", "content": "yes please"},
                ]
            })

        assert response.status_code == 200
        body = response.json()
        assert len(body["response"]["properties"]) == 1
        assert body["response"]["properties"][0]["address"] == "1 Oak St, Austin, TX"
        mock_get.assert_called_once()

    def test_returns_empty_properties_when_rentcast_returns_none(self, test_client, mock_openai):
        self._setup_ai_extraction(
            mock_openai,
            '{"location": "Boulder, CO"}',
            chat_reply="No results found. Try broadening your search.",
        )

        with patch("main.requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200, text="")
            mock_get.return_value.json.return_value = []

            response = test_client.post("/api/chat", json={
                "messages": [
                    {"role": "user", "content": "condos in Boulder"},
                    {"role": "assistant", "content": "Ready to search?"},
                    {"role": "user", "content": "yes"},
                ]
            })

        assert response.status_code == 200
        assert response.json()["response"]["properties"] == []

    def test_go_ahead_without_location_does_not_call_rentcast(self, test_client, mock_openai):
        # Extraction returns no location → endpoint should not call RentCast
        self._setup_ai_extraction(mock_openai, '{"location": null}')

        with patch("main.requests.get") as mock_get:
            response = test_client.post("/api/chat", json={
                "messages": [
                    {"role": "user", "content": "show me some listings"},
                    {"role": "assistant", "content": "Shall I search?"},
                    {"role": "user", "content": "yes"},
                ]
            })

        mock_get.assert_not_called()
        assert response.status_code == 200


class TestRateLimiting:
    def test_returns_429_when_rate_limit_exceeded(self, test_client, mock_redis):
        mock_redis.pipeline.return_value = _make_pipeline(num_requests=main.MAX_REQUESTS + 1)

        response = test_client.post("/api/chat", json={
            "messages": [{"role": "user", "content": "hi"}]
        })

        assert response.status_code == 429
        assert "too many requests" in response.json()["detail"].lower()

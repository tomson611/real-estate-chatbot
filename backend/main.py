from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os
from dotenv import load_dotenv
from openai import OpenAI
import requests
import json
from datetime import datetime, timedelta
import re
import time
import redis
import pickle

load_dotenv()

app = FastAPI(title="Real Estate Chatbot API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],  # Angular default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Redis
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=False  # Keep as bytes for pickle serialization
)

# Initialize OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
RENTCAST_API_KEY = os.getenv("RENTCAST_API_KEY")
print(f"RentCast API key loaded: {'Yes' if RENTCAST_API_KEY else 'No'}")

# System message to guide the AI's behavior
SYSTEM_MESSAGE = """You are a helpful and ethical real estate assistant. Your primary goal is to act in the best interest of the user and provide unbiased, honest advice. When users ask about properties:

1. First, ask for the location they're interested in.
2. Then ask about their preferred property type (e.g., single-family, condo, townhouse, etc.).
3. Ask about the number of bathrooms they need.
4. Finally, ask about their price range.

Once you have all this information:
1. Extract the location name.
2. If they mention a price (e.g., 'under $X' or 'below $X'), extract that as the maximum price.
3. DO NOT provide a text summary of the listings - the frontend will display them as cards.
4. If the user asks a general question about real estate or the area, provide a helpful and unbiased response.
5. Keep responses concise and focused on the user's question.
6. If you don't have access to real listings, be honest about it.

Additional guidelines:
1. Always prioritize the user's needs and financial well-being.
2. Be transparent about any limitations in your knowledge or data.
3. Provide balanced advice that considers both pros and cons.
4. Never pressure the user or make them feel rushed in their decision-making.
5. If a user's budget seems unrealistic for their desired area or property type, gently suggest alternatives or considerations.
6. When discussing neighborhoods or areas, provide objective information about safety, schools, and amenities.
7. If asked about investment potential, provide balanced information about risks and rewards.
8. Always maintain professional and ethical standards in your responses.
"""

# OpenAI model configuration
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # Default to GPT-4o Mini if not specified

# Cache configuration
CACHE_TTL = 60 * 60 * 24 * 365 * 10  # 10 years in seconds - effectively disabling cache refresh

# Rate limiting configuration
RATE_LIMIT_DURATION = 60  # 1 minute in seconds
MAX_REQUESTS = 20  # Maximum requests per time window

def get_cache_key(location: str, max_price: Optional[float] = None, property_type: Optional[str] = None, min_bathrooms: Optional[float] = None) -> str:
    """Generate a cache key from location and filters."""
    key_parts = [
        location.lower(),
        str(max_price) if max_price else 'no_price',
        property_type if property_type else 'no_type',
        str(min_bathrooms) if min_bathrooms else 'no_baths'
    ]
    return f"rentcast:{'_'.join(key_parts)}"

def get_cached_response(cache_key: str) -> Optional[list]:
    """Get cached response from Redis if it exists."""
    try:
        cached_data = redis_client.get(cache_key)
        if cached_data:
            print(f"Cache hit for {cache_key}")
            return pickle.loads(cached_data)
        print(f"Cache miss for {cache_key}")
        return None
    except Exception as e:
        print(f"Redis get error: {str(e)}")
        return None

def cache_response(cache_key: str, data: list):
    """Cache the response in Redis with expiration time."""
    try:
        redis_client.setex(
            cache_key,
            CACHE_TTL,
            pickle.dumps(data)
        )
        print(f"Cached response for {cache_key}")
    except Exception as e:
        print(f"Redis set error: {str(e)}")

class ChatMessage(BaseModel):
    role: str = Field(..., regex="^(user|assistant|system)$")
    content: str = Field(..., min_length=1)

class ChatRequest(BaseModel):
    messages: List[ChatMessage]

class MortgageRequest(BaseModel):
    loan_amount: float = Field(..., gt=0)
    interest_rate: float = Field(..., gt=0)
    loan_term_years: int = Field(..., gt=0)
    down_payment: Optional[float] = Field(0, ge=0)

def get_rentcast_data(location: str, max_price: Optional[float] = None, property_type: Optional[str] = None, min_bathrooms: Optional[float] = None):
    """Fetch data from RentCast API with caching"""
    try:
        # Check cache first
        cache_key = get_cache_key(location, max_price, property_type, min_bathrooms)
        cached_data = get_cached_response(cache_key)
        if cached_data is not None:
            return cached_data

        print(f"Cache miss for {cache_key}, fetching from API")
        
        # Format the location for the API - try to extract city and state
        location_parts = location.split(',')
        city = location_parts[0].strip()
        state = location_parts[1].strip() if len(location_parts) > 1 else None
        
        # Format the location string
        if state:
            formatted_location = f"{city}, {state}"
        else:
            # If no state provided, try to guess based on common city-state pairs
            city_state_map = {
                "los angeles": "CA",
                "san francisco": "CA",
                "new york": "NY",
                "chicago": "IL",
                "houston": "TX",
                "phoenix": "AZ",
                "philadelphia": "PA",
                "san antonio": "TX",
                "san diego": "CA",
                "dallas": "TX",
                "vallejo": "CA"
            }
            state = city_state_map.get(city.lower())
            formatted_location = f"{city}, {state}" if state else city
            
        # Format the location for the API - use city and state separately
        # Capitalize each word in the city name
        city_words = [word.capitalize() for word in city.split()]
        city_param = " ".join(city_words).replace(" ", "%20")
        state_param = state.replace(" ", "%20") if state else ""
        
        # Build the URL with optional filters
        url = f"https://api.rentcast.io/v1/listings/sale?city={city_param}"
        if state:
            url += f"&state={state_param}"
        url += "&limit=30"
        if max_price is not None:
            url += f"&maxPrice={max_price}"
        if property_type:
            url += f"&propertyType={property_type}"
        if min_bathrooms is not None:
            url += f"&minBathrooms={min_bathrooms}"
            
        print(f"Making request to RentCast API: {url}")
        
        headers = {
            "X-Api-Key": os.getenv("RENTCAST_API_KEY"),
            "Content-Type": "application/json"
        }
        
        print(f"Using headers: {headers}")
        
        # Make the API request
        response = requests.get(url, headers=headers, timeout=10)
        print(f"RentCast API response status: {response.status_code}")
        
        # Print the raw response structure
        try:
            data = response.json()
            print("\nRaw API Response Structure:")
            if data and len(data) > 0:
                print("\nAll available fields in first property:")
                for key, value in data[0].items():
                    print(f"- {key}: {value}")
                
                # Specifically check for owner-related fields
                print("\nOwner-related fields in first property:")
                owner_fields = ['owner', 'ownerName', 'ownerOccupied', 'ownerType', 'ownership']
                for field in owner_fields:
                    value = data[0].get(field)
                    print(f"- {field}: {'Present' if value is not None else 'Not present'}")
        except Exception as e:
            print(f"Error parsing API response: {e}")
        
        if response.status_code != 200:
            print(f"RentCast API error response: {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"RentCast API returned error: {response.text}"
            )
            
        data = response.json()
        
        # Format the properties data
        formatted_properties = []
        for prop in data:
            # Debug log for realtor information
            print(f"\nRaw realtor data for property {prop.get('formattedAddress')}:")
            print(f"Realtor Name: {prop.get('realtorName')}")
            print(f"Realtor Phone: {prop.get('realtorPhone')}")
            print(f"Realtor Email: {prop.get('realtorEmail')}")
            print(f"Realtor Company: {prop.get('realtorCompany')}")
            print(f"Listing URL: {prop.get('listingUrl')}")
            
            formatted_prop = {
                'address': prop.get('formattedAddress', 'N/A'),
                'price': f"${prop.get('price', 0):,.2f}",
                'beds': prop.get('bedrooms', 'N/A'),
                'baths': prop.get('bathrooms', 'N/A'),
                'sqft': f"{prop.get('squareFootage', 0):,}",
                'description': f"{prop.get('propertyType', 'Property')} in {prop.get('city', 'N/A')}, {prop.get('state', 'N/A')}",
                'yearBuilt': prop.get('yearBuilt', 'N/A'),
                'lotSize': f"{prop.get('lotSize', 0):,} sqft",
                'propertyType': prop.get('propertyType', 'N/A'),
                'listingStatus': prop.get('status', 'N/A'),
                'lastSoldDate': prop.get('lastSoldDate', 'N/A'),
                'lastSoldPrice': f"${prop.get('lastSoldPrice', 0):,.2f}" if prop.get('lastSoldPrice') else 'N/A',
                'zestimate': f"${prop.get('zestimate', 0):,.2f}" if prop.get('zestimate') else 'N/A',
                'rentZestimate': f"${prop.get('rentZestimate', 0):,.2f}" if prop.get('rentZestimate') else 'N/A',
                'daysOnMarket': prop.get('daysOnMarket', 'N/A'),
                'pricePerSqft': f"${prop.get('pricePerSqft', 0):,.2f}" if prop.get('pricePerSqft') else 'N/A',
                'latitude': prop.get('latitude', 'N/A'),
                'longitude': prop.get('longitude', 'N/A'),
                'listingAgent': {
                    'name': prop.get('listingAgent', {}).get('name', 'N/A'),
                    'phone': prop.get('listingAgent', {}).get('phone', 'N/A'),
                    'email': prop.get('listingAgent', {}).get('email', 'N/A'),
                    'website': prop.get('listingAgent', {}).get('website', 'N/A')
                },
                'listingOffice': {
                    'name': prop.get('listingOffice', {}).get('name', 'N/A'),
                    'phone': prop.get('listingOffice', {}).get('phone', 'N/A'),
                    'email': prop.get('listingOffice', {}).get('email', 'N/A')
                },
                'mlsNumber': prop.get('mlsNumber', 'N/A'),
                'mlsName': prop.get('mlsName', 'N/A')
            }
            formatted_properties.append(formatted_prop)
        
        # Cache the formatted response
        cache_response(cache_key, formatted_properties)
        
        return formatted_properties
    except requests.exceptions.RequestException as e:
        print(f"RentCast API request error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching data from RentCast: {str(e)}"
        )

def calculate_mortgage_payment(loan_amount: float, interest_rate: float, loan_term_years: int) -> Dict:
    """Calculate monthly mortgage payment and other details"""
    monthly_rate = interest_rate / 12 / 100
    num_payments = loan_term_years * 12
    
    # Monthly payment calculation using the mortgage payment formula
    monthly_payment = loan_amount * (monthly_rate * (1 + monthly_rate)**num_payments) / ((1 + monthly_rate)**num_payments - 1)
    
    total_payment = monthly_payment * num_payments
    total_interest = total_payment - loan_amount
    
    return {
        "monthly_payment": round(monthly_payment, 2),
        "total_payment": round(total_payment, 2),
        "total_interest": round(total_interest, 2),
        "loan_amount": loan_amount,
        "interest_rate": interest_rate,
        "loan_term_years": loan_term_years
    }

def check_rate_limit(ip: str) -> bool:
    """Check if the request is within rate limits using Redis."""
    try:
        pipe = redis_client.pipeline()
        now = int(time.time())
        key = f"rate_limit:{ip}"
        
        # Remove old timestamps and add new one
        pipe.zremrangebyscore(key, 0, now - RATE_LIMIT_DURATION)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, RATE_LIMIT_DURATION)
        
        # Execute pipeline
        _, _, num_requests, _ = pipe.execute()
        
        return num_requests <= MAX_REQUESTS
    except Exception as e:
        print(f"Redis rate limit error: {str(e)}")
        return True  # Allow request if Redis fails

async def rate_limit_dependency(request: Request):
    """Dependency to check rate limits."""
    client_ip = request.client.host
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later."
        )

@app.post("/api/chat")
async def chat(chat_request: ChatRequest, request: Request):
    try:
        # Check rate limit
        await rate_limit_dependency(request)
        
        # Extract location and price from the last user message
        last_user_message = next((msg for msg in reversed(chat_request.messages) if msg.role == "user"), None)
        if not last_user_message:
            raise HTTPException(status_code=400, detail="No user message found")

        # Extract location, price, property type, and bathrooms using regex
        location_pattern = r"(?:in|near|at|around|listings in|properties in|homes in)\s+([a-zA-Z\s]+?)(?:\s+under|\s+over|\s+below|\s+above|[?.!,]|$)|^(?:listings|properties|homes)\s+([a-zA-Z\s]+?)(?:\s+under|\s+over|\s+below|\s+above|[?.!,]|$)|(?:listings|properties|homes)\s+([a-zA-Z\s]+?)(?:\s+under|\s+over|\s+below|\s+above|[?.!,]|$)"
        price_pattern = r"(?:under|below|less than|maximum|max|up to)\s*\$?(\d+(?:,\d{3})*(?:\.\d{2})?)"
        property_type_pattern = r"(?:type|kind|style)\s+(?:of|is|are|:)\s*([a-zA-Z\s-]+?)(?:\s+with|\s+that|\s+and|\s+under|[?.!,]|$)"
        bathrooms_pattern = r"(?:bathrooms?|baths?)\s*(?:of|is|are|:)\s*(\d+(?:\.\d+)?)"

        location_match = re.search(location_pattern, last_user_message.content.lower())
        price_match = re.search(price_pattern, last_user_message.content.lower())
        property_type_match = re.search(property_type_pattern, last_user_message.content.lower())
        bathrooms_match = re.search(bathrooms_pattern, last_user_message.content.lower())

        location = location_match.group(1) or location_match.group(2) or location_match.group(3) if location_match else None
        max_price = float(price_match.group(1).replace(',', '')) if price_match else None
        property_type = property_type_match.group(1).strip() if property_type_match else None
        min_bathrooms = float(bathrooms_match.group(1)) if bathrooms_match else None

        # If we have a location, try to get property data
        if location:
            try:
                properties = get_rentcast_data(location, max_price, property_type, min_bathrooms)
                if properties:
                    return {
                        "response": {
                            "text": "",
                            "properties": properties
                        }
                    }
                else:
                    return {
                        "response": {
                            "text": "I couldn't find any properties matching your criteria. Would you like to try a different search?",
                            "properties": []
                        }
                    }
            except Exception as e:
                print(f"Error fetching RentCast data: {str(e)}")
                return {
                    "response": {
                        "text": "I encountered an error while searching for properties. Please try again later.",
                        "properties": []
                    }
                }

        # If no location or error, let GPT handle the response
        messages = [
            {"role": "system", "content": SYSTEM_MESSAGE},
            *[{"role": msg.role, "content": msg.content} for msg in chat_request.messages]
        ]
        
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.7
        )
        
        return {
            "response": {
                "text": response.choices[0].message.content,
                "properties": []
            }
        }
    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/calculate-mortgage")
async def calculate_mortgage(request: MortgageRequest):
    try:
        result = calculate_mortgage_payment(
            request.loan_amount,
            request.interest_rate,
            request.loan_term_years
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def test_rentcast_api():
    """Test function to check RentCast API response structure"""
    try:
        # Test parameters
        test_location = "Chicago, IL"  # Changed location to get fresh data
        test_max_price = 500000
        test_property_type = "Condo"
        test_min_bathrooms = 1
        
        # Force a fresh API call by using a unique cache key
        cache_key = f"test_{test_location}_{test_max_price}_{test_property_type}_{test_min_bathrooms}"
        
        # Get data from API
        properties = get_rentcast_data(
            location=test_location,
            max_price=test_max_price,
            property_type=test_property_type,
            min_bathrooms=test_min_bathrooms
        )
        
        if properties:
            print("\nTest API Call Results:")
            print(f"Number of properties returned: {len(properties)}")
            print("\nFirst property fields:")
            for key, value in properties[0].items():
                print(f"{key}: {value}")
        else:
            print("No properties returned from test API call")
            
    except Exception as e:
        print(f"Error in test API call: {str(e)}")

if __name__ == "__main__":
    test_rentcast_api() 
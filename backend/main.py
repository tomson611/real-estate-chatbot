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

For mortgage calculations:
1. When a user asks about mortgage payments, collect the following information:
   - Loan amount (or purchase price)
   - Interest rate
   - Loan term (in years)
   - Down payment (if mentioned)
2. Present the results in a clear, easy-to-understand format.
3. ALWAYS include the $ symbol before monetary values.
4. NEVER use any mathematical notation, formulas, or special characters.
5. NEVER use LaTeX, $, \\[, \\], or any other mathematical symbols.
6. Present numbers in plain text format only.
7. Keep all text on a single line, do not split numbers across multiple lines.
8. Include important context about what the calculation includes/excludes (e.g., property taxes, insurance, PMI).
9. Example of correct format:
   "Based on your inputs:
   Loan Amount: $300,000
   Interest Rate: 3%
   Loan Term: 25 years
   Down Payment: $0
   
   Your estimated monthly payment would be: $1,425.20
   
   Additional details:
   Total payment over loan term: $427,560.00
   Total interest paid: $127,560.00
   
   Note: This calculation does not include property taxes, homeowners insurance, or PMI if applicable."

Additional guidelines:
1. Always prioritize the user's needs and financial well-being.
2. Be transparent about any limitations in your knowledge or data.
3. Provide balanced advice that considers both pros and cons.
4. Never pressure the user or make them feel rushed in their decision-making.
5. If a user's budget seems unrealistic for their desired area or property type, gently suggest alternatives or considerations.
6. When discussing neighborhoods or areas, provide objective information about safety, schools, and amenities.
7. If asked about investment potential, provide balanced information about risks and rewards.
8. Always maintain professional and ethical standards in your responses.

When providing numbered lists in responses:
1. Use a single line break between items
2. Do not add extra line breaks between numbers
3. Keep the formatting consistent throughout the response
4. Use proper markdown formatting for lists

When discussing prices or ranges:
1. Always use the $ symbol before monetary values
2. Use commas for thousands (e.g., $1,000,000)
3. Keep price ranges on a single line
4. Example: "Prices range from $800,000 to $2,000,000"

When discussing neighborhoods or areas:
1. Keep paragraphs concise and focused
2. Use single line breaks between paragraphs
3. Avoid excessive newlines
4. Example format:
   "Silver Lake is one of Los Angeles' most vibrant neighborhoods. Known for its arts scene and trendy cafes, it attracts young professionals and families alike. The area offers a mix of housing options:
   
   1. Single-Family Homes: $800,000 to $2,000,000
   2. Condos and Townhouses: $400,000 to $1,000,000
   3. Rental Prices: $2,500 to $3,500 per month
   
   Market conditions can change, so these prices may vary. Let me know if you'd like to explore specific properties in this area."
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

        # Check if this is a mortgage calculation request
        mortgage_pattern = r"(?:purchase price|loan amount)?\s*\$?(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:interest rate|rate)\s*(\d+(?:\.\d+)?)%?\s*(?:loan|for)\s*(\d+)\s*(?:years?|yrs?)?"
        mortgage_match = re.search(mortgage_pattern, last_user_message.content.lower())
        
        if mortgage_match:
            try:
                # Extract mortgage parameters
                loan_amount = float(mortgage_match.group(1).replace(',', '')) if mortgage_match.group(1) else None
                interest_rate = float(mortgage_match.group(2)) if mortgage_match.group(2) else None
                loan_term = int(mortgage_match.group(3)) if mortgage_match.group(3) else None
                
                print(f"Extracted parameters - Loan: {loan_amount}, Rate: {interest_rate}, Term: {loan_term}")  # Debug log
                
                # If we have all required parameters, calculate the mortgage
                if loan_amount and interest_rate and loan_term:
                    result = calculate_mortgage_payment(loan_amount, interest_rate, loan_term)
                    
                    # Format the response with proper $ symbols
                    response_text = f"""Based on your inputs:
Loan Amount: ${loan_amount:,.2f}
Interest Rate: {interest_rate}%
Loan Term: {loan_term} years
Down Payment: $0.00

Your estimated monthly payment would be: ${result['monthly_payment']:,.2f}

Additional details:
Total payment over loan term: ${result['total_payment']:,.2f}
Total interest paid: ${result['total_interest']:,.2f}

Note: This calculation does not include property taxes, homeowners insurance, or PMI if applicable."""
                    
                    # Clean the response text without modifying the newlines
                    response_text = re.sub(r'<[^>]+>', '', response_text)  # Remove HTML tags
                    response_text = re.sub(r' +', ' ', response_text)  # Fix extra spaces
                    
                    return {
                        "response": {
                            "text": response_text,
                            "properties": []
                        }
                    }
                else:
                    # If we don't have all parameters, ask for them
                    return {
                        "response": {
                            "text": "I need more information to calculate your mortgage payment. Please provide:\n"
                                   "1. The loan amount (or purchase price)\n"
                                   "2. The interest rate\n"
                                   "3. The loan term (in years)\n"
                                   "4. Any down payment amount, if applicable",
                            "properties": []
                        }
                    }
            except Exception as e:
                print(f"Error calculating mortgage: {str(e)}")
                return {
                    "response": {
                        "text": "I encountered an error while calculating your mortgage payment. Please try again with the required information:\n\n1. The loan amount (or purchase price)\n2. The interest rate\n3. The loan term (in years)\n4. Any down payment amount, if applicable",
                        "properties": []
                    }
                }

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

        # Check if this is a property search request
        is_property_search = any([
            "listings" in last_user_message.content.lower(),
            "properties" in last_user_message.content.lower(),
            "homes" in last_user_message.content.lower(),
            "houses" in last_user_message.content.lower(),
            "for sale" in last_user_message.content.lower(),
            "buy" in last_user_message.content.lower(),
            "purchase" in last_user_message.content.lower()
        ])

        # If we have a location and it's a property search request, try to get property data
        if location and is_property_search:
            try:
                properties = get_rentcast_data(location, max_price, property_type, min_bathrooms)
                if properties and len(properties) > 0:
                    return {
                        "response": {
                            "text": "",
                            "properties": properties
                        }
                    }
                else:
                    # If no properties found, return a message and empty properties array
                    return {
                        "response": {
                            "text": "I couldn't find any properties matching your criteria. Would you like to try a different search?",
                            "properties": []  # Explicitly set to empty array
                        }
                    }
            except Exception as e:
                print(f"Error fetching RentCast data: {str(e)}")
                return {
                    "response": {
                        "text": "I encountered an error while searching for properties. Please try again later.",
                        "properties": []  # Explicitly set to empty array
                    }
                }

        # If no location or not a property search request, let GPT handle the response
        messages = [
            {"role": "system", "content": SYSTEM_MESSAGE},
            *[{"role": msg.role, "content": msg.content} for msg in chat_request.messages]
        ]
        
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.7
        )
        
        # Clean and format the response text
        response_text = response.choices[0].message.content
        # Remove any HTML tags
        response_text = re.sub(r'<[^>]+>', '', response_text)
        # Fix any double newlines
        response_text = re.sub(r'\n\n+', '\n\n', response_text)
        # Fix any extra spaces
        response_text = re.sub(r' +', ' ', response_text)
        # Remove any JSON-like formatting
        response_text = re.sub(r'^\s*{\s*"text"\s*:\s*"', '', response_text)
        response_text = re.sub(r'"\s*}\s*$', '', response_text)
        
        return {
            "response": {
                "text": response_text,
                "properties": []
            }
        }
    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
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
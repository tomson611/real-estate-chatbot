from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
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
    allow_origins=[
        "http://localhost:4200",  # Angular default port for local development
        "https://real-estate-chatbot-83uu.onrender.com"  # Deployed frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Redis
redis_url = os.getenv("REDIS_URL")
if redis_url:
    print(f"Connecting to Redis using REDIS_URL: {redis_url}")
    redis_client = redis.from_url(redis_url, decode_responses=False)
else:
    print("REDIS_URL not found, connecting to Redis using localhost defaults.")
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=0,
        decode_responses=False  # Keep as bytes for pickle serialization
    )

# Test Redis connection
try:
    if redis_client.ping():
        print("Successfully connected to Redis!")
    else:
        print("Redis ping failed.")
except redis.exceptions.ConnectionError as e:
    print(f"Failed to connect to Redis: {e}")

# Initialize OpenAI
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
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
   "Based on your inputs:\\n"
   "Loan Amount: $300,000\\n"
   "Interest Rate: 3%\\n"
   "Loan Term: 25 years\\n"
   "Down Payment: $0\\n\\n"
   "Your estimated monthly payment would be: $1,425.20\\n\\n"
   "Additional details:\\n"
   "Total payment over loan term: $427,560.00\\n"
   "Total interest paid: $127,560.00\\n\\n"
   "Note: This calculation does not include property taxes, homeowners insurance, or PMI if applicable."

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

def get_cache_key(location: str, max_price: Optional[float] = None, property_type: Optional[str] = None, min_bedrooms: Optional[int] = None, min_bathrooms: Optional[float] = None) -> str:
    """Generate a cache key from location and filters."""
    key_parts = [
        location.lower(),
        str(max_price) if max_price else 'no_price',
        property_type if property_type else 'no_type',
        str(min_bedrooms) if min_bedrooms else 'no_beds',
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

def get_rentcast_data(location: str, max_price: Optional[float] = None, property_type: Optional[str] = None, min_bedrooms: Optional[int] = None, min_bathrooms: Optional[float] = None):
    """Fetch data from RentCast API with caching"""
    try:
        # Check cache first
        cache_key = get_cache_key(location, max_price, property_type, min_bedrooms, min_bathrooms)
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
                "vallejo": "CA",
                "orange county": "CA"  # Added Orange County
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
        if min_bedrooms is not None:
            url += f"&minBedrooms={min_bedrooms}"
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

# Helper function to map common property terms to RentCast API values
def map_property_type_to_rentcast(pt_string: Optional[str]) -> Optional[str]:
    if not pt_string:
        return None
    pt_lower = pt_string.lower()
    # This map should align with RentCast's expected enum values for propertyType
    # Single-Family, Multi-Family, Condo, Townhouse, Land, Other
    mapping = {
        "house": "Single-Family",
        "single-family": "Single-Family",
        "single family": "Single-Family",
        "single-family home": "Single-Family",
        "detached house": "Single-Family",
        "condo": "Condo",
        "condominium": "Condo",
        "apartment": "Condo", # Assuming 'apartment' for sale is listed as Condo
        "flat": "Condo",
        "townhouse": "Townhouse",
        "town home": "Townhouse",
        "multi-family": "Multi-Family",
        "multifamily": "Multi-Family",
        "duplex": "Multi-Family",
        "triplex": "Multi-Family",
        "fourplex": "Multi-Family",
        "land": "Land",
        "lot": "Land",
        "other": "Other",
    }
    for key, value in mapping.items():
        if key in pt_lower: # Use 'in' for broader matching, e.g., "single-family homes"
            return value
    # If no specific map, try to capitalize, but RentCast might reject it.
    # It's safer to return None or a default like "Other" if no clear match.
    if pt_lower in ["single-family", "multi-family", "condo", "townhouse", "land", "other"]:
        return pt_lower.capitalize().replace("-f", "-F") # Ensure correct casing for direct matches
    return None # Or "Other"

async def extract_search_parameters_with_ai(messages_history: List[Dict[str, str]]) -> Dict[str, Any]:
    print("Attempting to extract search parameters with AI...")
    # Prepare a concise history, focusing on user and assistant messages
    extraction_prompt_messages = [{"role": "system", "content": """You are a parameter extraction assistant. Given the conversation history, identify the user's desired search criteria for real estate. Extract: location (city and state if possible, e.g., 'Los Angeles, CA'), property_type (e.g., 'house', 'condo'), min_bedrooms (integer), min_bathrooms (float, e.g., 1.5), and max_price (float). Respond ONLY with a JSON object containing these fields. If a field is not mentioned, omit it or set its value to null. Example: {\"location\": \"Los Angeles, CA\", \"property_type\": \"condo\", \"min_bedrooms\": 2, \"max_price\": 1000000}"""}]

    # Add relevant parts of the conversation history for the AI to parse
    # This can be optimized, but for now, let's use the last few messages
    # or a summary of the conversation focusing on criteria.
    # For simplicity, using the provided history.
    for msg in messages_history: # Use the full provided history for now
        if msg["role"] in ["user", "assistant"]: # Only include user and assistant messages for context
             extraction_prompt_messages.append({"role": msg["role"], "content": msg["content"]})


    try:
        response = await client.chat.completions.create( # Assuming async client or use sync version
            model=OPENAI_MODEL, # Or a faster/cheaper model if suitable for extraction
            messages=extraction_prompt_messages,
            temperature=0.0, # Low temperature for factual extraction
            response_format={"type": "json_object"}
        )
        extracted_json_str = response.choices[0].message.content
        print(f"AI raw extraction JSON string: {extracted_json_str}")
        if extracted_json_str:
            params = json.loads(extracted_json_str)
            # Basic validation/cleaning
            cleaned_params = {
                "location": params.get("location") if isinstance(params.get("location"), str) else None,
                "property_type": map_property_type_to_rentcast(params.get("property_type")) if isinstance(params.get("property_type"), str) else None,
                "min_bedrooms": int(params["min_bedrooms"]) if params.get("min_bedrooms") is not None else None,
                "min_bathrooms": float(params["min_bathrooms"]) if params.get("min_bathrooms") is not None else None,
                "max_price": float(params["max_price"]) if params.get("max_price") is not None else None,
            }
            print(f"AI Extracted and Cleaned Parameters: {cleaned_params}")
            return cleaned_params
    except Exception as e:
        print(f"Error during AI parameter extraction: {e}")
    return {}

@app.post("/api/chat")
async def chat(chat_request: ChatRequest, request: Request):
    try:
        await rate_limit_dependency(request)
        
        last_user_message_obj = next((msg for msg in reversed(chat_request.messages) if msg.role == "user"), None)
        if not last_user_message_obj:
            raise HTTPException(status_code=400, detail="No user message found")
        last_user_message_content = last_user_message_obj.content.strip().lower()

        # --- Mortgage Calculation Logic (keep as is) ---
        mortgage_pattern = r"(?:purchase price|loan amount)?\s*\$?([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{2})?)\s*(?:interest rate|rate)\s*([0-9]+(?:\.[0-9]+)?)\%?\s*(?:loan|for)\s*([0-9]+)\s*(?:years?|yrs?)?"
        mortgage_match = re.search(mortgage_pattern, last_user_message_content)
        if mortgage_match:
            # ... (mortgage calculation logic remains unchanged) ...
            try:
                loan_amount = float(mortgage_match.group(1).replace(',', '')) if mortgage_match.group(1) else None
                interest_rate = float(mortgage_match.group(2)) if mortgage_match.group(2) else None
                loan_term = int(mortgage_match.group(3)) if mortgage_match.group(3) else None
                
                if loan_amount and interest_rate and loan_term:
                    result = calculate_mortgage_payment(loan_amount, interest_rate, loan_term)
                    response_text = (
                        f"Based on your inputs:\\n"
                        f"Loan Amount: ${loan_amount:,.2f}\\n"
                        f"Interest Rate: {interest_rate}%\\n"
                        f"Loan Term: {loan_term} years\\n"
                        f"Down Payment: $0.00\\n\\n"
                        f"Your estimated monthly payment would be: ${result['monthly_payment']:,.2f}\\n\\n"
                        f"Additional details:\\n"
                        f"Total payment over loan term: ${result['total_payment']:,.2f}\\n"
                        f"Total interest paid: ${result['total_interest']:,.2f}\\n\\n"
                        f"Note: This calculation does not include property taxes, homeowners insurance, or PMI if applicable."
                    )
                    response_text = re.sub(r'<[^>]+>', '', response_text)
                    response_text = re.sub(r' +', ' ', response_text)
                    return {"response": {"text": response_text, "properties": []}}
                else: # Not enough info for mortgage
                    # Let OpenAI handle this by falling through, it's better at asking for missing mortgage info.
                    pass # Fall through to general OpenAI handling
            except Exception as e:
                print(f"Error in mortgage pre-processing: {str(e)}")
                # Fall through to general OpenAI handling if regex fails unexpectedly

        # --- Enhanced Parameter Extraction & Search Logic ---
        search_params = {}
        is_property_search_intent = False
        
        # Keywords that strongly suggest a property search or confirmation to search
        go_ahead_keywords = [
            "show me the listings", "show listings", "find them", "search now", "yes please search",
            "yes search", "ok search", "proceed with search", "go ahead and search", "display listings",
            "yes", "sure", "ok", "alright", "fine", "proceed", "continue", "go on", "show me", "let's see",
            "what do you have", "what did you find", "view listings", "get listings", "fetch listings",
            "do it", "let's do it", "i'm ready"
        ]

        # Check if the last user message is a "go-ahead" and if the assistant previously summarized criteria or asked to search
        if len(chat_request.messages) >= 2:
            prev_assistant_message_content = ""
            # Find the actual last assistant message
            for i in range(len(chat_request.messages) - 2, -1, -1):
                if chat_request.messages[i].role == "assistant":
                    prev_assistant_message_content = chat_request.messages[i].content.lower()
                    break
            
            assistant_asked_to_search_or_summarized = (
                "let me check for available listings" in prev_assistant_message_content or
                "shall i search" in prev_assistant_message_content or
                "ready to search" in prev_assistant_message_content or
                "here's what i have" in prev_assistant_message_content or # Assistant summarized
                "based on these criteria" in prev_assistant_message_content or
                "is this correct?" in prev_assistant_message_content
            )

            user_gave_go_ahead = any(keyword in last_user_message_content for keyword in go_ahead_keywords)

            if user_gave_go_ahead and assistant_asked_to_search_or_summarized:
                print("User gave go-ahead after assistant summarized/asked to search. Attempting AI extraction.")
                # Convert Pydantic models to simple dicts for the helper function
                history_for_extraction = [{"role": msg.role, "content": msg.content} for msg in chat_request.messages]
                search_params = await extract_search_parameters_with_ai(history_for_extraction)
                if search_params.get("location"): # Location is essential for a direct API search
                    is_property_search_intent = True
                    print(f"AI Extracted Parameters for Search: {search_params}")
                else:
                    print("AI extraction did not yield a location. Falling back to general AI response.")
                    is_property_search_intent = False # Let main AI ask for location
            else: # Fallback to regex if not a clear go-ahead scenario (or for simple one-liners)
                print("Not a clear go-ahead scenario after assistant summary. Trying regex extraction from last user message.")
                # Simple regex extraction from the LAST user message only as a fallback.
                # This part can be simplified or made less aggressive than the original complex regex block.
                # For now, let's extract very obvious parameters if present.
                
                # Simple Location (e.g., "in Los Angeles", "apartments Los Angeles")
                loc_match = re.search(r"\b(?:in|near|at|around|for)\s+((?:[A-Za-z'-]+(?:\s+[A-Za-z'-]+)*)(?:,\s*[A-Z]{2})?)\b", last_user_message_content, re.IGNORECASE)
                if not loc_match: # Try location at the end or start if no preposition
                    loc_match = re.search(r"\b((?:[A-Za-z'-]+(?:\s+[A-Za-z'-]+)*)(?:,\s*[A-Z]{2})?)\b(?=\s*(?:listings|properties|homes|condos|apartments|$))", last_user_message_content, re.IGNORECASE)
                if not loc_match:
                     loc_match = re.search(r"^((?:[A-Za-z'-]+(?:\s+[A-Za-z'-]+)*)(?:,\s*[A-Z]{2})?)\b", last_user_message_content, re.IGNORECASE)


                if loc_match: search_params["location"] = loc_match.group(1).strip()

                price_match = re.search(r"(?:under|below|less than|maximum|max|up to|around|for|price)\s*\$?([0-9,]+(?:\\.\\d{1,2})?)", last_user_message_content)
                if price_match: search_params["max_price"] = float(price_match.group(1).replace(',', ''))
                
                beds_match = re.search(r"(\d+)\s*(?:bedrooms?|beds?|br)\b", last_user_message_content)
                if beds_match: search_params["min_bedrooms"] = int(beds_match.group(1))
                
                baths_match = re.search(r"(\d+(?:\\.\\d+)?)\\s*(?:bathrooms?|baths?|ba)\b", last_user_message_content)
                if baths_match: search_params["min_bathrooms"] = float(baths_match.group(1))

                # Simple property type from last message
                pt_str_match = re.search(r"\b(apartment|condo|house|single-family|townhouse|multi-family|land)\b", last_user_message_content, re.IGNORECASE)
                if pt_str_match:
                    search_params["property_type"] = map_property_type_to_rentcast(pt_str_match.group(1))

                if search_params.get("location"): # Location is key for this path
                    # Stricter condition: require location, property_type, min_bathrooms, AND max_price for a direct regex-based search.
                    # Otherwise, let the main AI ask for more details according to SYSTEM_MESSAGE.
                    if (search_params.get("property_type") and 
                        search_params.get("min_bathrooms") and 
                        search_params.get("max_price")):
                        is_property_search_intent = True
                        print(f"Regex Extracted Parameters (sufficient for direct search: Loc, Type, Baths, Price) from last user message: {search_params}")
                    else:
                        is_property_search_intent = False # Not enough for a direct Rentcast call from simple regex
                        print(f"Regex Extracted Parameters (insufficient for direct search - need Loc, Type, Baths, Price) from last user message: {search_params}. Letting AI handle conversation flow.")
                else:
                    # If regex didn't find a location in the last message, it's likely a general query or needs more context.
                    print("Regex extraction from last user message did not find a location.")
                    is_property_search_intent = False # Ensure it's false if no location


        # --- Prepare for RentCast API call or OpenAI response ---
        messages_for_openai = [{"role": "system", "content": SYSTEM_MESSAGE}] + \
                              [{"role": msg.role, "content": msg.content} for msg in chat_request.messages]
        properties_result = []
        
        final_search_location = search_params.get("location")
        final_max_price = search_params.get("max_price")
        final_property_type = search_params.get("property_type") # Already mapped
        final_min_bedrooms = search_params.get("min_bedrooms")
        final_min_bathrooms = search_params.get("min_bathrooms")

        print(f"Parameters before RentCast decision: Location='{final_search_location}', PT='{final_property_type}', Beds='{final_min_bedrooms}', Baths='{final_min_bathrooms}', Price='{final_max_price}', IsSearchIntent={is_property_search_intent}")

        if is_property_search_intent and final_search_location:
            print(f"Attempting RentCast API call with: Loc='{final_search_location}', MaxPrice='{final_max_price}', PT='{final_property_type}', Beds='{final_min_bedrooms}', Baths='{final_min_bathrooms}'")
            try:
                properties_result = get_rentcast_data(
                    location=final_search_location,
                    max_price=final_max_price,
                    property_type=final_property_type,
                    min_bedrooms=final_min_bedrooms, # Added
                    min_bathrooms=final_min_bathrooms
                )
                print(f"RentCast returned {len(properties_result)} properties.")
                
                if not properties_result:
                    print("RentCast returned no properties. Will inform OpenAI for a contextual 'no results' message.")
                    search_criteria_summary = f"location: '{final_search_location}'"
                    if final_property_type: search_criteria_summary += f", property type: '{final_property_type}'"
                    if final_min_bedrooms: search_criteria_summary += f", bedrooms: {final_min_bedrooms}"
                    if final_min_bathrooms: search_criteria_summary += f", bathrooms: {final_min_bathrooms}"
                    if final_max_price: search_criteria_summary += f", max price: ${final_max_price:,.0f}"
                    
                    no_results_prompt_for_ai = (
                        "A specific property search for {" + search_criteria_summary + "} was performed but yielded no direct listings from the database. "
                        "Please inform the user empathetically that no exact matches were found for these criteria. "
                        "Then, proactively suggest they broaden their search (e.g., by adjusting price, location details, number of bedrooms/bathrooms, or property type) or ask if they'd like to try a different search strategy. "
                        "Avoid just saying 'no results'. Offer constructive next steps."
                    )
                    messages_for_openai.append({"role": "system", "content": no_results_prompt_for_ai})
            
            except HTTPException as e: # RentCast API specific error
                print(f"HTTPException from RentCast API: {e.detail}. Informing OpenAI.")
                error_prompt = f"I encountered an issue trying to fetch property listings from the database (API error: {e.detail}). Please try your search again in a moment. If the problem persists, you can ask general real estate questions."
                messages_for_openai.append({"role": "system", "content": error_prompt})
                properties_result = []
            except Exception as e: # Other errors during RentCast call
                print(f"Unexpected error during RentCast data call: {str(e)}. Informing OpenAI.")
                error_prompt = "I encountered an unexpected internal error while trying to fetch property listings. Please try your search again. If this continues, please let the support team know."
                messages_for_openai.append({"role": "system", "content": error_prompt})
                properties_result = []
        else:
            print("Not a direct property search for RentCast API (e.g. no location, or not a search intent). OpenAI will handle the conversation.")


        # --- OpenAI Call for Chat Response ---
        # (properties_result might be populated from RentCast, or empty if no search / no results / error)
        
        print(f"Messages for OpenAI ChatCompletion ({len(messages_for_openai)} total):")
        # for i, msg in enumerate(messages_for_openai):
        #     print(f"  [{i}] Role: {msg['role']}, Content: {msg['content'][:200]}...") # Debug

        ai_response = await client.chat.completions.create( # Use await for async client
            model=OPENAI_MODEL,
            messages=messages_for_openai,
            temperature=0.5, # Adjusted temperature for a balance
            max_tokens=700 # Increased max_tokens for potentially more detailed assistant responses
        )
        response_text = ai_response.choices[0].message.content.strip()
        print(f"OpenAI Raw Chat Response Text: {response_text}")

        # If properties were found by RentCast AND OpenAI didn't explicitly mention them (e.g. it just said "Okay, here are some listings"),
        # we might want to prepend a standard phrase if response_text is too short or generic.
        # However, the SYSTEM_MESSAGE already tells it "DO NOT provide a text summary of the listings - the frontend will display them as cards."
        # And if properties were found, the specific "no_results_prompt_for_ai" is NOT added.
        # So, OpenAI should naturally provide a lead-in text.

        return {"response": {"text": response_text, "properties": properties_result if properties_result else []}}

    except HTTPException as e: # Handle HTTPExceptions raised by our own code (e.g. rate limit)
        print(f"HTTPException in chat endpoint: {str(e.detail)}") # Log detail
        raise e # Re-raise to let FastAPI handle it
    except Exception as e: # Catch-all for other unexpected errors
        print(f"General Error in chat endpoint: {str(e)}")
        # Consider logging the full traceback here for debugging
        # import traceback
        # print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

def test_rentcast_api():
    """Test function to check RentCast API response structure"""
    try:
        # Test parameters
        test_location = "Chicago, IL"  # Changed location to get fresh data
        test_max_price = 500000
        test_property_type = "Condo"
        test_min_bedrooms = 2
        test_min_bathrooms = 1
        
        # Force a fresh API call by using a unique cache key
        cache_key = f"test_{test_location}_{test_max_price}_{test_property_type}_{test_min_bedrooms}_{test_min_bathrooms}"
        
        # Get data from API
        properties = get_rentcast_data(
            location=test_location,
            max_price=test_max_price,
            property_type=test_property_type,
            min_bedrooms=test_min_bedrooms,
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
    # To test async functions, you'd typically use asyncio.run()
    # For example:
    # async def main_test():
    #     await test_rentcast_api()
    #     # Test AI parameter extraction (example)
    #     sample_history = [
    #         {"role": "user", "content": "Hi, I'm looking for a house in San Diego"},
    #         {"role": "assistant", "content": "Okay! How many bedrooms and bathrooms are you looking for, and what's your price range?"},
    #         {"role": "user", "content": "3 beds, 2 baths, under 750k"}
    #     ]
    #     extracted = await extract_search_parameters_with_ai(sample_history)
    #     print(f"Test AI Extraction Result: {extracted}")
    #
    # import asyncio
    # asyncio.run(main_test())
    
    # Simpler sync test for Rentcast if preferred, but AI extraction test above is async
    test_rentcast_api() 
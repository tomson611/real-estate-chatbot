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
    allow_origins=[
        "http://localhost:4200",  # Angular default port for local development
        "https://real-estate-chatbot-83uu.onrender.com"  # Deployed frontend
    ],
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
        
        last_user_message = next((msg for msg in reversed(chat_request.messages) if msg.role == "user"), None)
        if not last_user_message:
            raise HTTPException(status_code=400, detail="No user message found")

        # Mortgage calculation logic
        mortgage_pattern = r"(?:purchase price|loan amount)?\s*\$?(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:interest rate|rate)\s*(\d+(?:\.\d+)?)\%?\s*(?:loan|for)\s*(\d+)\s*(?:years?|yrs?)?"
        mortgage_match = re.search(mortgage_pattern, last_user_message.content.lower())
        
        if mortgage_match:
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
                else:
                    return {
                        "response": {
                            "text": ("I need more information to calculate your mortgage payment. Please provide:\\n"
                                   "1. The loan amount (or purchase price)\\n"
                                   "2. The interest rate\\n"
                                   "3. The loan term (in years)\\n"
                                   "4. Any down payment amount, if applicable"),
                            "properties": []
                        }
                    }
            except Exception as e:
                print(f"Error calculating mortgage: {str(e)}")
                return {
                    "response": {
                        "text": ("I encountered an error while calculating your mortgage payment. Please try again with the required information:\\n\\n"
                               "1. The loan amount (or purchase price)\\n"
                               "2. The interest rate\\n"
                               "3. The loan term (in years)\\n"
                               "4. Any down payment amount, if applicable"),
                        "properties": []
                    }
                }

        # Initialize search parameters
        location: Optional[str] = None
        max_price: Optional[float] = None
        property_type: Optional[str] = None 
        min_bathrooms: Optional[float] = None
        is_property_search: bool = False
        parsed_from_assistant: bool = False

        # --- Start of Original Regex-based Parameter Extraction ---
        simple_confirmations = [
            "that is all", "yes", "correct", "proceed", "go ahead", "ok", 
            "sounds good", "yep", "confirm", "sounds right", "looks good",
            "that's it", "perfect", "great", "that looks right", "that's correct"
        ]

        if len(chat_request.messages) >= 2 and last_user_message.content.strip().lower() in simple_confirmations:
            potential_assistant_message = chat_request.messages[-2]
            if potential_assistant_message.role == "assistant":
                assistant_confirmation_text = potential_assistant_message.content
                print(f"Attempting to parse from assistant confirmation: {assistant_confirmation_text}") # Debug print

                # More robust regexes for parsing assistant's confirmation
                loc_match_assist = re.search(r"(?:Location|Area|City):\s*([^\n]+)", assistant_confirmation_text, re.IGNORECASE)
                pt_text_match_assist = re.search(r"(?:Property Type|Looking for|Type):\s*([^\n]+)", assistant_confirmation_text, re.IGNORECASE)
                bath_match_assist = re.search(r"(?:Bathrooms|Number of Bathrooms):\s*(\d+(?:\.\d+)?)", assistant_confirmation_text, re.IGNORECASE)
                price_match_assist = re.search(r"(?:Price Range|Maximum Price|Price):\s*(?:Under|Up to|Less than|Around)?\s*\$?([0-9,]+(?:\.\d{1,2})?)", assistant_confirmation_text, re.IGNORECASE)

                if loc_match_assist: location = loc_match_assist.group(1).strip()
                
                if pt_text_match_assist:
                    raw_pt_str = pt_text_match_assist.group(1).strip().lower()
                    parsed_canonical_pt = None
                    # Ensure known_property_keywords_map is accessible here or defined if not already
                    # sorted_keywords = sorted(known_property_keywords_map.keys(), key=len, reverse=True) # Assuming known_property_keywords_map is defined earlier
                    # For now, let's use a simplified local map for assistant parsing to RentCast types
                    # This map should ideally be comprehensive and align with RentCast enums
                    assistant_pt_to_rentcast_map = {
                        "apartment": "Condo",  # Assuming apartments for sale are condos
                        "condo": "Condo",
                        "house": "Single-Family",
                        "single-family": "Single-Family",
                        "townhouse": "Townhouse",
                        "multi-family": "Multi-Family",
                        "land": "Land"
                    }
                    # Try to map common terms found in the assistant's description
                    for keyword, rentcast_type in assistant_pt_to_rentcast_map.items():
                        if keyword in raw_pt_str:
                            property_type = rentcast_type # This is the RentCast valid type
                            break
                    if not property_type and raw_pt_str: # if still no property_type but raw_pt_str exists
                        print(f"Could not map assistant property type '{raw_pt_str}' to a known RentCast type. Clearing property_type.")
                        property_type = None # Clear it if no valid mapping to avoid sending invalid enum

                if bath_match_assist: min_bathrooms = float(bath_match_assist.group(1))
                if price_match_assist: max_price = float(price_match_assist.group(1).replace(',', ''))
                
                if location: # If a location was successfully parsed from assistant
                    is_property_search = True
                    parsed_from_assistant = True
                    print(f"Parameters PARSED from ASSISTANT confirmation: L='{location}', PT='{property_type}', B='{min_bathrooms}', P='{max_price}', IsSearch={is_property_search}")
                else:
                    print("No location found in assistant confirmation message.")

        if not parsed_from_assistant:
            content_lower = last_user_message.content.lower()
            
            # 1. Extract price and bathrooms - CORRECTED REGEX patterns:
            price_pattern = r"(?:under|below|less than|maximum|max|up to|around|for)\s*\$?([0-9,]+(?:\.\d{1,2})?)"
            bathrooms_pattern = r"(\d+(?:.\d+)?)\s*(?:bathrooms?|baths?)"
            price_match_user = re.search(price_pattern, content_lower)
            bathrooms_match_user = re.search(bathrooms_pattern, content_lower)
            if price_match_user: max_price = float(price_match_user.group(1).replace(',', ''))
            if bathrooms_match_user: min_bathrooms = float(bathrooms_match_user.group(1))

            # 2. Extract Property Type
            property_type_keyword_found: Optional[str] = None
            known_property_keywords_map = {
                "single-family homes": "Single-Family", "single family homes": "Single-Family",
                "single-family home": "Single-Family", "single family home": "Single-Family",
                "multi-family homes": "Multi-Family", "multi family homes": "Multi-Family",
                "multi-family home": "Multi-Family", "multi family home": "Multi-Family",
                "townhouses": "Townhouse", "townhouse": "Townhouse",
                "condos": "Condo", "condo": "Condo",
                "houses": "Single-Family", "house": "Single-Family", 
                "apartments": "Apartment", "apartment": "Apartment",
                "land plots": "Land", "land plot": "Land", "land": "Land"
            }
            sorted_pt_keywords = sorted(known_property_keywords_map.keys(), key=len, reverse=True)
            for kw in sorted_pt_keywords:
                # CORRECTED REGEX pattern:
                if re.search(r'\b' + re.escape(kw) + r'\b', content_lower):
                    property_type = known_property_keywords_map[kw]
                    property_type_keyword_found = kw 
                    print(f"Property type '{property_type}' found from keyword '{kw}'")
                    break
            if not property_type: 
                # CORRECTED REGEX pattern:
                property_type_pattern_orig = r"(?:type|kind|style|a|an)\s+(condo|townhouse|single-family|house|apartment|multi-family|land)\b"
                pt_match_regex = re.search(property_type_pattern_orig, content_lower)
                if pt_match_regex:
                    raw_pt = pt_match_regex.group(1).strip().lower()
                    property_type = known_property_keywords_map.get(raw_pt, raw_pt.capitalize())
                    if property_type == "House": property_type = "Single-Family"
                    print(f"Property type '{property_type}' found from regex pattern for '{raw_pt}'.")

            # 3. Prepare content for location search
            content_for_location_search = content_lower
            if property_type_keyword_found:
                # CORRECTED REGEX patterns:
                content_for_location_search = re.sub(r'\b' + re.escape(property_type_keyword_found) + r'\b', '', content_for_location_search, count=1, flags=re.IGNORECASE).strip()
                content_for_location_search = re.sub(r'\s\s+', ' ', content_for_location_search)
                print(f"Content for location search after PT '{property_type_keyword_found}' removal: '{content_for_location_search}'")
            else:
                print(f"No property type keyword found, using original content for location search: '{content_for_location_search}'")

            # 4. Extract Location - CORRECTED REGEX pattern:
            location_pattern = (
                r"(?:in|near|at|around|for|from)\s+((?:[A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+)*)(?:,\s*[A-Z]{2})?|(?:\w[\w\s.,'-]*))"\
                r"|^((?:[A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+)*)(?:,\s*[A-Z]{2})?|(?:\w[\w\s.,'-]*))(?=\s*(?:listings|properties|homes|condos|apartments|$))"
            )
            potential_locations = []
            for match in re.finditer(location_pattern, content_for_location_search, re.IGNORECASE):
                loc_group1 = match.group(1)
                loc_group2 = match.group(2)
                if loc_group1: potential_locations.append(loc_group1.strip().rstrip(',').strip())
                if loc_group2: potential_locations.append(loc_group2.strip().rstrip(',').strip())
            
            print(f"Potential locations found by regex: {potential_locations}")

            if potential_locations:
                cleaned_locations = []
                non_location_phrases = ["show me", "can you show me", "find me", "search for", "looking for", "i want", "i need", "tell me about", "what about"]
                non_location_phrases.extend(known_property_keywords_map.keys())
                
                for ploc in potential_locations:
                    temp_ploc_lower = ploc.lower()
                    is_fluff = any(temp_ploc_lower == fluff.lower() or temp_ploc_lower.startswith(fluff.lower() + " ") for fluff in non_location_phrases)
                    if not is_fluff and len(ploc) > 1 and not ploc.isdigit():
                        cleaned_locations.append(ploc)
                
                print(f"Cleaned potential locations: {cleaned_locations}")
                
                if cleaned_locations:
                    cleaned_locations.sort(key=lambda x: (len(x), ',' in x), reverse=True)
                    location = cleaned_locations[0] 
                    print(f"Selected location: '{location}'")

            # 5. Fallback: Location Inference for very short queries
            if not location and property_type_keyword_found and len(content_lower.split()) <= 4: 
                temp_loc_str = content_lower
                # CORRECTED REGEX patterns:
                temp_loc_str = re.sub(r'\b' + re.escape(property_type_keyword_found) + r'\b', '', temp_loc_str, flags=re.IGNORECASE).strip()
                temp_loc_str = re.sub(r'^(?:in|near|at|around|for|show me|the|a|an)\s+', '', temp_loc_str, flags=re.IGNORECASE).strip()
                temp_loc_str = re.sub(r'\s\s+', ' ', temp_loc_str).strip()
                if temp_loc_str and len(temp_loc_str) > 1 and temp_loc_str.lower() != property_type_keyword_found.lower():
                    location = temp_loc_str
                    print(f"Location inferred from short query '{content_lower}' after PT & preposition removal: '{location}'")

            # 6. Determine if it's a property search and refine location
            # `location` here is the string extracted by regex, or None.
            # `property_type`, `max_price`, `min_bathrooms` are also set.
            
            final_search_location = location # This will be used for API call if it's a search
            is_property_search = False # Default to False

            if parsed_from_assistant:
                if location: # Location must have been extracted from assistant's confirmation
                    is_property_search = True
                    # final_search_location is already 'location'
                    print(f"Property search: Parameters confirmed by user from assistant. Location: '{final_search_location}'")
                else:
                    print("Warning: Parsed from assistant confirmation, but no location found in assistant's message. Treating as general query.")
                    is_property_search = False 
                    final_search_location = None # Ensure no location is used for search
            else:
                # This is a direct user query, not a confirmation.
                # Assess plausibility of the initially extracted 'location'.
                if location: # If a location string was extracted by earlier regex
                    loc_lower_check = location.lower()
                    # List of phrases that, if the location starts with them or *is* them, indicate it's not a good search term
                    question_or_general_indicators = [
                        "what is", "what's", "how is", "how's", "tell me about", "can you tell me", 
                        "information on", "situation", "report", "market", "update", "overview", "analysis", 
                        "trends", "real estate", "homes in general in" 
                    ]
                    is_question_like_phrase = False
                    for indicator in question_or_general_indicators:
                        if loc_lower_check.startswith(indicator) or loc_lower_check == indicator:
                            is_question_like_phrase = True
                            break
                    
                    # Also consider overly long locations without structure (like a comma) as implausible
                    is_too_long_or_unstructured = (
                        (len(location.split()) > 7 and ',' not in location) or
                        (len(location) > 60 and ',' not in location)
                    )

                    if is_question_like_phrase or is_too_long_or_unstructured:
                        print(f"Extracted location '{location}' deemed not plausible for property search (question-like, too long, or unstructured). Discarding for search intent.")
                        final_search_location = None # Discard this location for search decision
                    else:
                        # Location seems plausible enough to consider for a search
                        print(f"Extracted location '{location}' deemed plausible for property search consideration.")
                        # final_search_location remains 'location'
                
                # Now, decide if it's a property search based on refined location and other criteria
                has_search_criteria = property_type or max_price or min_bathrooms
                
                # Keywords that strongly signal intent to search for properties when location might also be present
                strong_intent_keywords = [
                    "listings", "properties", "homes", "houses", "condos", "apartments",
                    "for sale", "for rent", "buy", "purchase", "find", "search", "look for", "looking for"
                ]
                has_strong_intent_keywords_in_query = any(re.search(r'\b' + re.escape(keyword) + r'\b', content_lower, re.IGNORECASE) for keyword in strong_intent_keywords)

                if final_search_location and (has_search_criteria or has_strong_intent_keywords_in_query):
                    is_property_search = True
                    print(f"Property search determined: Plausible location '{final_search_location}' AND (specific criteria OR strong intent keywords found in query).")
                elif not final_search_location and (has_search_criteria or (property_type and has_strong_intent_keywords_in_query)):
                    # E.g., "condos under $500k" (criteria, no location) or "find condos" (property_type + intent, no location)
                    is_property_search = False # Let OpenAI prompt for location
                    print(f"General query determined: Criteria/Property Type with intent present, but no plausible location. OpenAI to prompt.")
                elif final_search_location and not (has_search_criteria or has_strong_intent_keywords_in_query):
                    # E.g., user just types "Los Angeles" or "Tell me about Los Angeles".
                    # Location is plausible, but no other property search signals.
                    is_property_search = False # Treat as general question about the location.
                    print(f"General query determined: Plausible location '{final_search_location}' found, but no other property search signals. OpenAI to handle.")
                else:
                    # Default to not a property search if none of the above conditions are met.
                    is_property_search = False
                    print(f"General query determined: No clear property search intent or insufficient/implausible parameters. Query: '{content_lower}'")
            
            # Update the original 'location' variable with the refined 'final_search_location'
            # This ensures that if location was deemed implausible, it's None for the API call.
            location = final_search_location 

        # --- End of Original Regex-based Parameter Extraction --- (Comment seems misplaced from original, but logic ends here)
        print(f"Final decision before API call: Location='{location}', PropertyType='{property_type}', MaxPrice='{max_price}', MinBathrooms='{min_bathrooms}', IsPropertySearch={is_property_search}")
        
        is_valid_location_string = isinstance(location, str) and location.strip() != ""

        if is_valid_location_string and is_property_search: # location already stripped by this point if from regex
            try:
                properties = get_rentcast_data(location, max_price, property_type, min_bathrooms) # Use location directly
                if properties and len(properties) > 0:
                    text = f"Here are some {property_type.lower() if property_type else 'properties'} I found in {location}"
                    if max_price: text += f" under ${max_price:,.0f}"
                    if min_bathrooms: text += f" with at least {min_bathrooms:.0f} bathroom(s)"
                    text += ":"
                    return {"response": {"text": text, "properties": properties}}
                else:
                    return {"response": {"text": f"I couldn't find any {property_type.lower() if property_type else 'properties'} matching your criteria in {location}. Would you like to try a different search?", "properties": []}}
            except Exception as e:
                print(f"Error fetching RentCast data: {str(e)}")
                return {"response": {"text": "I encountered an error while searching for properties. Please try again later.", "properties": []}}

        # Fallback to general OpenAI completion if not a property search
        print(f"Final check before OpenAI call: Location='{final_search_location}', PropertyType='{property_type}', MinBathrooms='{min_bathrooms}', MaxPrice='{max_price}', IsPropertySearch={is_property_search}")

        messages_for_openai = [{"role": "system", "content": SYSTEM_MESSAGE}] + \
                              [{"role": msg.role, "content": msg.content} for msg in chat_request.messages]

        properties_result = [] # Initialize
        
        # If it's a property search and we have a location, call RentCast
        if is_property_search and final_search_location:
            print(f"Calling RentCast for: Loc='{final_search_location}', PT='{property_type}', Baths='{min_bathrooms}', Price='{max_price}'")
            try:
                properties_result = get_rentcast_data(
                    location=final_search_location,
                    max_price=max_price,
                    property_type=property_type,
                    min_bathrooms=min_bathrooms
                )
                print(f"RentCast returned {len(properties_result)} properties.")
                if not properties_result: # Explicitly check for empty list
                    print("RentCast returned no properties. Will inform OpenAI.")
                    # Add a specific system-like message to guide OpenAI for "no results"
                    no_results_prompt = f"The property search for {{location: '{final_search_location}', max_price: '{max_price}', property_type: '{property_type}', min_bathrooms: '{min_bathrooms}'}} yielded no results. Please inform the user and suggest they try broadening their search criteria, such as adjusting the price range, number of bathrooms, property type, or searching in a nearby area. Be empathetic and helpful."
                    messages_for_openai.append({"role": "system", "content": no_results_prompt})
                    # No need to pass properties_result to OpenAI if it's empty and handled by this prompt
                
            except HTTPException as e:
                print(f"HTTPException from RentCast: {e.detail}")
                # Let OpenAI handle this as a general error or a situation where it can't fetch listings
                error_prompt = "I encountered an issue trying to fetch property listings. Please try again or ask a different question."
                messages_for_openai.append({"role": "system", "content": error_prompt})
                properties_result = [] # Ensure properties_result is empty

            except Exception as e: # Catch any other unexpected errors from RentCast
                print(f"Unexpected error from RentCast: {str(e)}")
                error_prompt = "I encountered an unexpected issue while trying to fetch property listings. Please try again."
                messages_for_openai.append({"role": "system", "content": error_prompt})
                properties_result = []


        # If properties_result is not empty, OpenAI doesn't need to generate text about them,
        # it just needs to provide a contextual message if any.
        # The properties will be sent to the frontend for display.
        # If properties_result IS empty (either no search, or search yielded no results and we added a prompt),
        # then OpenAI will generate the main text response.
        
        if properties_result:
             # If we have properties, the AI's main role is to provide a brief intro/summary.
             # The actual property data is sent separately.
             # We might want to slightly adjust the prompt or system message for this case too,
             # to ensure it doesn't try to re-list properties in text.
             # For now, the SYSTEM_MESSAGE has "DO NOT provide a text summary of the listings"
             # which should cover this.
            print("OpenAI will be called, but properties_result will be sent directly to frontend.")
            pass # OpenAI call will proceed with existing messages_for_openai

        print(f"Messages for OpenAI ({len(messages_for_openai)} total):")
        for i, msg in enumerate(messages_for_openai):
            print(f"  [{i}] Role: {msg['role']}, Content: {msg['content'][:200]}...") # Print first 200 chars

        ai_response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages_for_openai,
            temperature=0.3, # Slightly lower temperature for more factual/less creative property responses
            max_tokens=500
        )
        
        response_text = ai_response.choices[0].message.content.strip()
        print(f"OpenAI Raw Response Text: {response_text}")

        # Ensure proper markdown for lists is converted to HTML for the frontend later
        # (The frontend already has some markdown conversion, but ensuring good input helps)
        # response_text = response_text.replace("\n- ", "\n<br>- ") # Example, might need more robust markdown handling

        return {"response": {"text": response_text, "properties": properties_result if properties_result else []}}

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
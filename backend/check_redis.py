import redis
import pickle
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize Redis connection
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=False
)

# Get all keys
keys = redis_client.keys("*")
print("Redis keys found:", [key.decode() for key in keys])

# For each key, get and display the data
for key in keys:
    print(f"\nData for key: {key.decode()}")
    data = redis_client.get(key)
    if data:
        try:
            # Try to unpickle the data
            unpickled_data = pickle.loads(data)
            # Convert to JSON for pretty printing
            print(json.dumps(unpickled_data, indent=2))
        except Exception as e:
            print(f"Error unpickling data: {e}")
            print("Raw data:", data) 
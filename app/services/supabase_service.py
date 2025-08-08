from datetime import datetime
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from openai import OpenAI
from google import g
from typing import Optional
from app.models.schemas import User, OrderRequest

load_dotenv()


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_EMBEDDING_TABLE_NAME = os.getenv("SUPABASE_EMBEDDING_TABLE_NAME")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME")


# initialize Supabase client
if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: Supabase URL or Key not found in environment variables.")
    supabase: Client = None # set client to None if keys are missing
else:
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabase client initialized successfully.")
    except Exception as e:
        print(f"Error initializing Supabase client: {e}")
        supabase: Client = None # set client to None if initialization fails

gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        print("Gemini client initialized in db.py.")
    except Exception as e:
        print(f"Error initializing Gemini client in db.py: {e}")
else:
    print("Gemini API Key not found. OpenAI client not initialized in db.py.")

SUPABASE_TABLE_NAME = "google_sheets_data"

GOOGLE_SHEET_ID_KEY = "Id"

def get_embedding(text):
    try:
        results = gemini_client.models.embed_content(
            model=GEMINI_EMBEDDING_MODEL_NAME,
            contents=text,
            config={
            "output_dimensionality": 384,
            }
        )
        return results.embeddings[0].values
    
    except Exception as e:
        print(f"❌ Failed to get embedding: {e}")
        return None

def store_data_in_supabase(row_data: dict):
    """
    Stores or updates a row in the Supabase table based on the row ID.
    Stores the entire row_data dictionary in the 'data' column.

    Args:
        row_data: A dictionary representing a single row read directly from
                  the Google Sheet by data_ingestion.py.
                  Must contain the unique ID under the key specified by GOOGLE_SHEET_ID_KEY.
    """

    if supabase is None:
        print("Supabase client is not initialized. Cannot store data.")
        return

    # get the unique ID from the row data using the defined key
    row_id = row_data.get(GOOGLE_SHEET_ID_KEY)

    if not row_id:
        print(f"Error in store_data_in_supabase: Missing or empty row ID in row data. Skipping storage for this row.")
        return # cannot store without an ID

    try:
        # supabase's 'data' column should be of type JSONB or JSON
        data_to_store = {
            "Id": row_id,       # map the Google Sheet ID to the Supabase 'id' column (Primary Key)
            "data": row_data    # store the entire row dictionary in the 'data' column
            # vector embeddings should be here
        }
        print(f"DEBUG: {row_data.keys()}") # Debugging line to check keys in row_data

        # perform the upsert operation
        # this will insert a new row if 'id' doesn't exist, or update the existing row if it does.
        response = supabase.from_(SUPABASE_TABLE_NAME).upsert(data_to_store, on_conflict="Id").execute()

        # check response for errors
        if not response.data:
            print(f"Error upserting data for ID {row_id} to Supabase")
            print(f"Response: {response}")  # added to see full response details

        # generate embedding for the row data
        text = str(row_data)
        vector = get_embedding(text)
        if vector is None:
            print(f"Error: Failed to generate embedding for row ID {row_id}.")
            return

        print(f"DEBUG: Embedding ID for row {row_id}")

        vector_to_upsert = {
            "embedding": vector,
            "content": text,     
            "parent_row_id": row_id,
        }

        print(f"DEBUG: About to upsert embedding data: {vector_to_upsert}")
        print(f"DEBUG: Vector length: {len(vector)}")
        print(f"DEBUG: Vector type: {type(vector)}")

        try:
            response_embeddings = supabase.from_(SUPABASE_EMBEDDING_TABLE_NAME).upsert(vector_to_upsert, on_conflict="parent_row_id").execute()
        except Exception as upsert_error:
            print(f"Error during embedding upsert for row ID {row_id}: {upsert_error}")
            try:
                # get table schema
                response_embeddings = supabase.from_(SUPABASE_EMBEDDING_TABLE_NAME).select("*").execute()
                print(f"DEBUG: Table schema response: {response_embeddings}")
            except Exception as insert_error:
                print(f"Error during embedding insert for row ID {row_id}: {insert_error}")
            raise upsert_error
        
        print(f"DEBUG: Full embedding upsert response: {response_embeddings}")
        print(f"DEBUG: Response type: {type(response_embeddings)}")
        print(f"DEBUG: Response data: {response_embeddings.data}")
        print(f"DEBUG: Response count: {getattr(response_embeddings, 'count', 'N/A')}")
        
        if not response_embeddings.data:
            print(f"Error upserting embedding for row ID {row_id} to Supabase")
            print(f"Embedding response: {response_embeddings}")
            
    except Exception as e:
        print(f"Error in store_data_in_supabase for row ID {row_id}: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")


def get_recent_messages(session_id: str, limit: int):
    result = supabase.table("chat_messages")\
        .select("*")\
        .eq("session_id", session_id)\
        .limit(limit)\
        .execute()
    return result.data

def save_message(session_id: str, user_id: str, sender: str, content: str):
    supabase.table("chat_messages").insert({
        "session_id": session_id,
        "user_id": user_id,
        "sender": sender,
        "content": content
    }).execute()


def get_id_content(id: str):
    """
    Fetches the content associated with a given ID from Supabase.
    """
    result = supabase.table(SUPABASE_TABLE_NAME)\
        .select("data")\
        .eq(GOOGLE_SHEET_ID_KEY, id)\
        .execute()

    if result.data:
        return result.data[0]["data"]
    else:
        print(f"No data found for ID {id}.")
        return None


def get_relevant_ids(query: str, top_k: int = 10, similarity: float = 0.5):
    """
    Retrieves relevant IDs based on the query from the Supabase embedding table.
    """
    if supabase is None:
        print("Supabase client is not initialized. Cannot retrieve relevant IDs.")
        return []
    
    # get user query embedings
    query_embedding = get_embedding(query)
    print(f"DEBUG: Query embedding length: {len(query_embedding) if query_embedding else 'None'}")


    if query_embedding is None:
        print("Error: Failed to generate embedding for the query.")
        return []

    try:
        result = supabase.rpc(
            "match_documents",{
            "query_embedding": query_embedding,
            "match_threshold": similarity,
            "match_count": top_k,
        }
        ).execute()

        relevant_chunks_data = []
        if result.data:
            for match in result.data:
                if "parent_row_id" in match and "content" in match:
                    print(f"DEBUG: Found match with parent_row_id: {match['parent_row_id']}")
                    relevant_chunks_data.append({
                        "parent_row_id": match["parent_row_id"],
                        "content": match["content"]
                    })
                print(f"DEBUG: Found match: {match}")

        print(f"Found {len(relevant_chunks_data)} relevant chunks from Supabase vector search.")
        return relevant_chunks_data # return the list of dictionaries
    except Exception as e:
        print(f"Error retrieving relevant IDs from Supabase: {e}")
        return []


def save_order_to_supabase(user: User, session_id: str, api_response: dict, order_data: OrderRequest, batch_id: str = None):
    """
    Saves an order to the Supabase orders table.
    """
    if supabase is None:
        print("Supabase client is not initialized. Cannot save order.")
        return
    

    try:
        full_record = {
            "batch_id": batch_id,
            "user_id": user.user_id,
            "session_id": session_id,
            "customer_name": user.name,
            "customer_age": user.age,
            "customer_hmo_id": user.hmo_id,
            "customer_phone": user.phone,
            "customer_alt_phone": user.alt_phone,
            "customer_email": user.email,
            "customer_address": user.address,
            "customer_alt_phone": user.alt_phone,
            "customer_gender": user.gender,
            "fulfilment_mode": order_data.fulfilment_mode,
            "landmark": user.landmark ,
            "city": user.city,
            "state": user.state,
            "lga": user.lga,
            "order_items": [item.model_dump() for item in order_data.order_items],
            "api_response": api_response
        }
        response = supabase.table("orders").insert(full_record).execute()

        if response.data:
            # print(f"Order saved successfully: {response.data}")
            return {"success": True, "data": response.data}
        else:
            # print("Failed to save order. No data returned.")
            return {"success": False, "error": "Error in saving order. No data returned."}
    except Exception as e:
        print(f"Error saving order to Supabase: {e}")

def update_order_api_response(batch_id: str, api_response: dict):
    """Update an existing order record with the API response."""
    if supabase is None:
        print("Supabase client is not initialized. Cannot update order.")
        return {"success": False, "error": "Supabase client not initialized"}
    
    try:
        response = supabase.table("orders").update({"api_response": api_response}).eq("batch_id", batch_id).execute()
        
        if response.data:
            return {"success": True, "data": response.data}
        else:
            return {"success": False, "error": "Failed to update order with API response"}
            
    except Exception as e:
        print(f"Error updating order API response: {e}")
        return {"success": False, "error": str(e)}


def delete_order_from_supabase(batch_id: str):
    """Delete an order from the database by batch_id."""
    if supabase is None:
        print("Supabase client is not initialized. Cannot delete order.")
        return {"success": False, "error": "Supabase client not initialized"}
    
    try:
        response = supabase.table("orders").delete().eq("batch_id", batch_id).execute()
        
        if response.data is not None:  # Supabase delete returns empty list on success
            print(f"Order with batch_id {batch_id} deleted successfully")
            return {"success": True}
        else:
            print(f"Failed to delete order with batch_id {batch_id}")
            return {"success": False, "error": "Failed to delete order"}
            
    except Exception as e:
        print(f"Error deleting order from Supabase: {e}")
        return {"success": False, "error": str(e)}


def check_user(user_id) -> bool:
    existing_user = supabase.table("users")\
        .select("*")\
        .eq("user_id", user_id)\
        .execute()
    
    if existing_user.data:
        return False
    else:
        return True

def get_user_data_db(user_id: str, name: str) -> User:
    response = supabase.table("users") \
        .select("*") \
        .eq("user_id", user_id) \
        .eq("name", name) \
        .single() \
        .execute()
    
    if response.data:
        print(f"DEBUG: Retrieved user data for user_id {user_id}: {response.data}")
        return User.model_validate(response.data)
    else:
        return None
    
def update_user(user_data: dict):
    user_id = user_data["user_id"]

    response = supabase.table("users") \
        .update(user_data) \
        .eq("user_id", user_id) \
        .execute()
    
    if response.data:
        return {"success": True, "data": response.data}
    else:
        return {"success": False, "error": response.error}

def check_or_create_user(user: User):
    existing_user = supabase.table("users")\
        .select("*")\
        .eq("user_id", user.user_id)\
        .execute()
    
    if existing_user.data:
        return {"user_id": user.user_id, "new": False}

    # only insert non-null fields
    user_data = {k: v for k, v in user.model_dump().items() if v is not None}

    new_user = supabase.table("users").insert(user_data).execute()

    if new_user.data:
        return {"user_id": user.user_id, "new": True}


def create_session(user_id, session_id, name):
    response = supabase.table("chat_sessions").insert({
        "session_id": session_id,
        "user_id": user_id,
        "username": name 
    }).execute()

    if response.data:
        print(f"New Session {session_id} creeated for {name} with User ID: {user_id}")

def get_or_create_active_session(user_id: str, session_id: Optional[str] = None):
    if session_id:
        # try to resume explicitly provided session
        session = (
            supabase.table("chat_sessions")
            .select("*")
            .eq("id", session_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        if session and session.data and session.data.get("status") == "active":
            print(f"Resuming session {session_id}")
            return session.data

    # else, try to find latest active session
    result = (
        supabase.table("chat_sessions")
        .select("*")
        .eq("user_id", user_id)
        .eq("status", "active")
        .order("started_at", desc=True)
        .limit(1)
        .execute()
    )

    if result.data:
        return result.data[0]['session_id']

    # create a new session
    new_session = (
        supabase.table("chat_sessions")
        .insert({"user_id": user_id})
        .execute()
    )
    return new_session.data[0]

def end_session(session_id: str):
    supabase.table("chat_sessions").update({
        "status": "completed",
        "ended_at": datetime.utcnow()
    }).eq("id", session_id).execute()
    return {"message": "Session ended"}

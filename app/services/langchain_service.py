import os
from tenacity import retry, stop_after_attempt, wait_fixed
import requests
import hashlib
from langchain.tools import tool
from langchain.agents import initialize_agent, AgentType
from langchain_community.chat_models import ChatOpenAI
from typing import Optional
from app.models.schemas import User, OrderRequest, ProductQuery
from app.services.supabase_service import (
    save_order_to_supabase, 
    check_or_create_user, 
    update_user, 
    get_user_data_db, 
    get_relevant_ids,
    update_order_api_response,
    delete_order_from_supabase
)

PAYMENT_URL = "https://api.pharmacy.com/orders" # TODO: change to production URL
HEADERS = {
    "CN-API-KEY": os.getenv("CN_API_KEY"),
    "Content-Type": "application/json",
    "Accept": "application/json"
}

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def send_order_to_api(user: User, order: OrderRequest, batch_id: str) -> dict:    
    # Prepare only allowed fields
    payload = {
        "batch_id": batch_id,
        "customer_name": user.name,
        "customer_age": str(user.age),
        "customer_hmo_id": user.hmo_id,
        "customer_phone": user.phone,
        "customer_alt_phone": user.alt_phone,
        "customer_email": user.email,
        "customer_address": user.address,
        "customer_gender": user.gender,
        "landmark": user.landmark,
        "city": user.city,
        "state": user.state,
        "lga": user.lga,
        "fulfilment_mode": order.fulfilment_mode,
        "order_items": [dict(item) for item in order.order_items],
    }

    response = requests.post(PAYMENT_URL, headers=HEADERS, json=payload)

    # raise exception for HTTP errors
    response.raise_for_status()

    return response.json()


@tool
def store_customer_identity(user: User) -> str:
    """Store customer's basic identity information"""
    try:
        update_user(user.model_dump())
        return {"success": True, "message": f"Stored customer identity for {user.name}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    
@tool
def get_user_data(user_id: str, name: str) -> User:
    """Retrieve user data by user_id"""
    try:
        user_data = get_user_data_db(user_id, name)
        if user_data:
            # UserModel = User.model_validate(i)
            return {"success": True, "user_data": User.model_validate(user_data)}
    except Exception as e:
        return {"success": False, "error": str(e)}
    
    
@tool("get_relevant_product_info_tool", args_schema=ProductQuery, return_direct=False)
def get_relevant_product_info(user_query: str, product_name: str = None, symptom: str = None, additional_notes: str = None) -> dict:
    """
    Retrieve relevant product information based on full user query.
    """
    try:
        query_parts = []

        if user_query:
            query_parts.append(f"{user_query}")
        if product_name:
            query_parts.append(f"about {product_name}")
        if symptom:
            query_parts.append(f"related to {symptom}")
        if additional_notes:
            query_parts.append(f"note: {additional_notes}")

        full_query = " ".join(query_parts).strip()
        print(f"Full query constructed: {full_query}")

        context_chunks = get_relevant_ids(full_query)
        print(f"Context chunks found: {(context_chunks)}")
        if not context_chunks:
            return {"success": False, "message": "No relevant product information found."}
        
        return {"success": True, "context_chunks": context_chunks}
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool
def place_order(user: User, session_id: str ,order_data: OrderRequest) -> str:
    """Place an order for a customer when all details for an order has been confirmed. Expects full order_data dict."""
    try:
        batch_id = hashlib.md5(f"{user.user_id}-{order_data.customer_name}-{order_data.order_items[0].name}".encode()).hexdigest()[:8]
        print(f"Generated batch ID: {batch_id}")

        save_order = save_order_to_supabase(user=user, session_id=session_id, order_data=order_data, api_response=None, batch_id=batch_id)
        if not save_order or not save_order.get("success"):
            return {"success": False, "error": "Failed to save order to database."}
        
        try:
            api_response = send_order_to_api(user, order_data, batch_id)
            update_order = update_order_api_response(batch_id=batch_id, api_response=api_response)

            if not update_order or not update_order.get("success"):
                delete_order_from_supabase(batch_id=batch_id)
                return {"success": False, "error": "Failed to update order with API response."}

            if isinstance(api_response, dict):
                return {"success": True, "api_response":api_response}
            else:
                delete_order_from_supabase(batch_id=batch_id)
                return {"success": False, "error": "Failed to place order. No valid API response."}

        except Exception as api_error:
            print(f"Error placing order via API: {api_error}")
            error_details = str(api_error)
            if hasattr(api_error, 'last_attempt') and api_error.last_attempt:
                try:
                    # Get the actual HTTP error from the retry wrapper
                    actual_error = api_error.last_attempt.exception()
                    if hasattr(actual_error, 'response') and actual_error.response:
                        error_details = f"HTTP {actual_error.response.status_code}: {actual_error.response.text}"
                    else:
                        error_details = str(actual_error)
                except:
                    pass
            delete_order_from_supabase(batch_id=batch_id)
            return {"success": False, "error": str(error_details)}

    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
def refer_to_pharmacist(customer_symptoms: Optional[str]) -> str:
    """Returns the contact number of a human pharmacist."""
    return "+999999999999"

llm = ChatOpenAI(model="gpt-4o-mini")

tools = [get_user_data, store_customer_identity, get_relevant_product_info, place_order]

agent_executor = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.OPENAI_FUNCTIONS,
    verbose=True
)

def run_agent(input_message: str, context: str = "", chat_history: list = []) -> str:
    # Combine context and history into a single prompt
    full_prompt = context + "\n\n"
    for msg in chat_history:
        full_prompt += f"{msg['sender']}: {msg['content']}\n"
    full_prompt += f"user: {input_message}"

    return agent_executor.run(full_prompt)


# add tool for leaving session notes


# @tool
# def store_user(user_data: dict) -> str:
#     """Stores user personal information: name, age, phone, email, gender"""
#     # Save to database (Supabase)
#     save_user_to_supabase(**user_data)
#     return f"User {user_data['name']} stored successfully."

# @tool
# def check_drug_availability(drug_name: str) -> dict:
#     """Check if a drug exists in the inventory and return its price and dosage if available."""
#     return check_drug_in_inventory(drug_name)

# @tool
# def recommend_drug(symptoms: str) -> dict:
#     """
#     Recommend a drug based on symptoms. Only return recommendation if confidence > 90%.
#     If confidence is low, return {'refer': True}.
#     """
#     return recommend_drug_based_on_symptoms(symptoms)

# @tool
# def place_order(order_data: dict) -> str:
#     """Places order for the customer and returns a payment link if successful."""
#     response = send_order_to_api(order_data)
#     return response.get("payment_link", "Order placed successfully but no payment link generated.")


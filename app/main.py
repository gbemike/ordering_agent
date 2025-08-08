import time
import hashlib
from fastapi import FastAPI
from dotenv import load_dotenv
from app.routes import chat
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

app.include_router(chat.router)
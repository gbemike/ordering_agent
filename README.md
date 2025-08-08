# AI Ordering Agent

This project is an AI-powered conversational agent designed to assist users in ordering medications and receiving drug recommendations from a Pharmacy. The agent provides a friendly and interactive experience while ensuring safety, and adherence to business rules.

## 📖 Table of Contents
- [Project Overview](#project-overview)
- [Features](#features)
- [System Architecture](#system-architecture)
  - [Frontend](#frontend)
  - [Backend](#backend)
  - [Database](#database)
- [Tools and Technologies](#tools-and-technologies)
- [Setup and Installation](#setup-and-installation)
- [Usage](#usage)
- [API Endpoints](#api-endpoints)
- [Database Schema](#database-schema)

## 📝 Project Overview

The AI Ordering Agent is a sophisticated chatbot that guides users through the process of purchasing medications. It can handle user queries, collect necessary information, search for products, and place orders. The agent is designed to be reliable, secure, and user-friendly, prioritizing the user's health and safety while also aligning with the pharmacy's business objectives.

The primary purpose of this agent is to:
- Assist users in ordering medications.
- Provide drug recommendations based on user needs.
- Collect user information for order fulfillment.
- Offer a seamless and conversational user experience.

## ✨ Features

- **Conversational Interface**: A chat-based interface for users to interact with the agent.
- **User Authentication**: Identifies new and existing users.
- **Information Collection**: Gathers necessary user details (name, age, contact information, etc.).
- **Drug Search**: Searches the pharmacy's inventory for specific drugs or based on symptoms.
- **Product Recommendations**: Suggests relevant products from the company catalog.
- **Order Placement**: Collects all required information and places an order.

## 🏗️ System Architecture

The project is built with a modern architecture, separating the frontend, backend, and database for scalability and maintainability.

### 💻 Frontend

The frontend is a single-page application (SPA) built with **React**. It provides the user interface for the chat application.

- **Framework**: React.js
- **Styling**: Bootstrap for responsive design.
- **HTTP Client**: Axios for making API requests to the backend.
- **UI Components**: The main component is the `Chat` component, which handles the conversation flow.

### ⚙️ Backend

The backend is a **FastAPI** application that serves as the brain of the AI agent. It handles business logic, interacts with the database, and communicates with the LangChain service.

- **Framework**: FastAPI
- **Language**: Python
- **Services**:
  - `langchain_service`: Manages the AI agent, including the language model, tools, and agent execution.
  - `supabase_service`: Handles all interactions with the Supabase database.
- **Routing**: Manages API endpoints for chat, session management, and testing.

### 🗄️ Database

The database is managed using **Supabase**, a backend-as-a-service platform that provides a PostgreSQL database, authentication, and more.

- **Platform**: Supabase
- **Database**: PostgreSQL
- **Schemas**: The database includes tables for users, chat sessions, chat messages, and orders.

## 🛠️ Tools and Technologies

- **Frontend**:
  - React
  - Bootstrap
  - Axios
- **Backend**:
  - FastAPI
  - LangChain
  - OpenAI (for the language model)
  - Supabase Python Client
- **Database**:
  - Supabase (PostgreSQL)
- **Other Tools**:
  - Uvicorn (for running the FastAPI server)
  - python-dotenv (for managing environment variables)

## 🚀 Setup and Installation

### Prerequisites

- Node.js and npm
- Python 3.8+ and pip
- A Supabase account and project
- An OpenAI API key

### Frontend

1. **Navigate to the `frontend` directory:**
   ```bash
   cd frontend
   ```
2. **Install dependencies:**
   ```bash
   npm install
   ```
3. **Start the development server:**
   ```bash
   npm start
   ```

### Backend

1. **Navigate to the project root directory.**
2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```
3. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Create a `.env` file** in the root directory and add your Supabase and OpenAI credentials:
   ```env
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   OPENAI_API_KEY=your_openai_api_key
   ```
5. **Start the FastAPI server:**
   ```bash
   uvicorn app.main:app --reload
   ```

## Usage

Once both the frontend and backend servers are running, you can open your browser to `http://localhost:3000` to interact with the AI agent.

## API Endpoints

- `POST /chat`: The main endpoint for sending messages to the agent.
- `POST /test`: A test endpoint to check if the server is running.

## Database Schema

### `users`
- `user_id` (text, primary key)
- `name` (text)
- `age` (integer)
- `phone` (text)
- `email` (text)
- `gender` (text)
- `created_at` (timestamp)

### `chat_sessions`
- `session_id` (text, primary key)
- `user_id` (text, foreign key to `users.user_id`)
- `started_at` (timestamp)
- `ended_at` (timestamp, nullable)

### `chat_messages`
- `message_id` (serial, primary key)
- `session_id` (text, foreign key to `chat_sessions.session_id`)
- `user_id` (text, foreign key to `users.user_id`)
- `sender` (text)
- `content` (text)
- `created_at` (timestamp)
- `metadata` (jsonb, nullable)

### `orders`
- `order_id` (serial, primary key)
- `session_id` (text, foreign key to `chat_sessions.session_id`)
- `user_id` (text, foreign key to `users.user_id`)
- `order_data` (jsonb)
- `api_response` (jsonb, nullable)
- `batch_id` (text)
- `created_at` (timestamp)
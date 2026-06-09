# Real Estate Chatbot

A real estate chatbot that integrates with RentCast API and uses OpenAI's GPT for natural language processing. Built with Vue.js frontend and FastAPI backend.

## Prerequisites

- Python 3.8+
- Node.js 14+
- npm
- OpenAI API key
- RentCast API key

## Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the backend directory with your API keys:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   RENTCAST_API_KEY=your_rentcast_api_key_here
   ```

5. Run the backend server:
   ```bash
   uvicorn main:app --reload
   ```

## Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Run the development server:
   ```bash
   ng serve
   ```

4. Open your browser and navigate to `http://localhost:4200`

## Features

- Real-time chat interface
- Integration with RentCast API for property data
- Mortgage calculations
- Market trend analysis
- Natural language processing using OpenAI's GPT

## API Endpoints

- `POST /api/chat`: Main chat endpoint that processes user messages and returns AI responses

## Technologies Used

- Frontend: Angular
- Backend: FastAPI
- AI: OpenAI GPT
- Real Estate Data: RentCast API 

# PhoneERP - AI-Powered Phone-Order ERP System

An intelligent Phone ERP system that automates phone-based sales orders using AI transcription and information extraction.

## Technology Stack

- **Frontend**: Next.js (App Router, TypeScript, Tailwind CSS)
- **Backend**: FastAPI (Python 3.10+, Pydantic v2)
- **Database**: Supabase (PostgreSQL)
- **AI Engine**: Google Gemini API (transcription, structured data extraction)

## Project Structure

```text
PhoneERP/
├── frontend/             # Next.js frontend application
├── backend/              # FastAPI backend application
│   ├── app/
│   │   ├── config/       # App settings and env loading
│   │   ├── routes/       # API endpoints (transcribe, action-cards, health)
│   │   ├── schemas/      # Pydantic validation schemas
│   │   ├── services/     # Gemini and Supabase services
│   │   └── main.py       # FastAPI application entry point
│   ├── requirements.txt
│   └── .env.example
├── docs/                 # Documentation files
├── README.md
└── .gitignore
```

## Setup Instructions

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables:
   ```bash
   cp .env.example .env
   # Update .env with your Google Gemini and Supabase keys
   ```
5. Run the development server:
   ```bash
   uvicorn app.main:app --reload
   ```

### Frontend Setup

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
   npm run dev
   ```
4. Access the dashboard at `http://localhost:3000`.

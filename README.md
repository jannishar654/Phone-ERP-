# PhoneERP

AI-powered Phone ERP system that transforms phone calls, voice notes, and WhatsApp orders into structured business workflows.

---

## Overview

Many small businesses manage customer orders through phone calls and messaging platforms. This often leads to manual errors, missed details, and inefficient operations.

PhoneERP aims to automate this process by converting unstructured communication into structured **Action Cards** that can be reviewed, managed, and tracked through a centralized dashboard.

---

## Core Workflow

```text
Voice Call / Voice Note / WhatsApp Message
                ↓
        AI Processing
                ↓
      Action Card Generation
                ↓
      Human Verification
                ↓
        Order Management
                ↓
      Delivery & Operations
```

---

## Features

* Voice-based order capture
* AI-powered information extraction
* Editable Action Cards
* Order management dashboard
* Customer and delivery tracking
* Business workflow automation
* Audit-ready order records

---

## Technology Stack

### Frontend

* Next.js
* TypeScript
* Tailwind CSS

### Backend

* FastAPI
* Python
* Pydantic

### Database

* Supabase (PostgreSQL)

### AI Engine

* Google Gemini

---

## Project Structure

```text
PhoneERP/
├── frontend/
├── backend/
│   ├── app/
│   │   ├── config/
│   │   ├── controllers/
│   │   ├── routes/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── main.py
│   ├── requirements.txt
│   └── .env.example
├── docs/
├── README.md
└── .gitignore
```

---

## Local Setup

### Backend

```bash
cd backend

python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt

uvicorn app.main:app --reload
```

Backend Server:

```text
http://localhost:8000
```

API Documentation:

```text
http://localhost:8000/docs
```

---

### Frontend

```bash
cd frontend

npm install

npm run dev
```

Frontend Application:

```text
http://localhost:3000
```

---

## Development Roadmap

### Current Phase

* Project Setup
* Authentication
* Dashboard UI
* Action Card Workflow (MVP)

### Upcoming Features

* Voice Recording Pipeline
* Speech-to-Text Processing
* Gemini Integration
* Automated Action Card Extraction
* Order Persistence with Supabase
* Delivery Workflow Management
* Notifications and Tracking

---

## Team

Managed and developed by:

* Mohammad Jannishar
* Mohd Danish
* Mohd Nasir

---

## Project Goal

PhoneERP explores how AI can enable traditional phone-based businesses to operate through structured digital workflows without requiring complex ERP software.

The objective is to transform informal communication into actionable business operations using modern AI technologies.

---

## License

This project is developed for educational, internship, and research purposes.

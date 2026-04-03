# WillGuard

WillGuard is a production-grade AI financial safety system. It acts as an intelligent trading guardian, protecting your family assets during periods of user inactivity by automatically enforcing a pre-defined "Financial Will."

## Features

- **ArmorClaw Enforcement Engine**: A YAML-driven safety policy that dictates risk tolerance, daily limits, and approved tickers.
- **OpenClaw Agentic Loop**: AI-driven risk scoring and tone classification powered by Gemini natively (OpenAI-compatible SDK).
- **System State Engine**: Tracks user activity and transitions the system between three states:
  - **Co-Pilot**: Active monitoring of trades.
  - **Guardian**: Automated pause on new trades after moderate inactivity.
  - **Lockdown**: Full trade freeze and emergency contact notification after extended inactivity.
- **Decision Ledger**: Append-only audit log of all system decisions for maximum transparency.
- **Real-Time Notification System**: EmailJS integration for notifying emergency contacts during Lockdown mode.
- **Hackathon-Ready React Dashboard**: A polished frontend (Vite/React) for visualizing real-time enforcement, risk scores, and system mode transitions.

## Project Structure

- `/backend`: Python/FastAPI server containing the Intelligence layer (Risk Scorer, Tone Classifier) and ArmorClaw engine.
- `/frontend`: React/Vite web dashboard for interacting with the system.

## Setup Instructions

### Environment Variables
You must have a `GEMINI_API_KEY` configured in `backend/.env`.

### Running Locally

1. **Backend** (FastAPI)
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python api.py
```
*Runs on http://localhost:8000*

2. **Frontend** (React)
```bash
cd frontend
npm install
npm run dev
```
*Runs on http://localhost:5173*

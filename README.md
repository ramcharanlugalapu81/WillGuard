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

## System Walkthrough & UI Modes

WillGuard relies on a dynamic state engine that automatically adapts the UI and backend logic based on your activity.

### 1. Co-Pilot Mode (Active)
- **Status:** The default mode when continuous user interaction (mouse tracking, keyboard inputs) is detected.
- **Rules:** The ArmorClaw engine evaluates trades actively through Gemini risk scoring. High-risk trades will prompt a **Confirm/Reject Notification**, while clean trades are executed directly.

### 2. Guardian Mode (Warning)
- **Trigger:** Activates after moderate inactivity (e.g., leaving your desk for a few seconds).
- **UI Changes:** A yellow warning banner appears at the top. The mode badge shifts to the pulsing amber Guardian shield.
- **Rules:** All new trade evaluations are instantly **frozen**. Market signals stay active, but interaction relies entirely on pre-approved constraints. Any user activity instantly restores Co-Pilot Mode.

### 3. Lockdown Mode (Critical)
- **Trigger:** Activates after extended, dangerous levels of inactivity.
- **UI Changes:** A high-contrast red lockdown border and banner take over the screen. The entire Dashboard becomes completely disabled and overlaid with a lockdown shield.
- **Rules:** Emergency contacts configured in the "Financial Will" tab receive an **instant EmailJS real-time alert** notifying them of the unattended trading session. Trades are absolutely blocked.

### 4. Configuration & Settings
- **Financial Will Tab:** Update your approved tickers, risk tolerance, and daily limits on the fly.
- **Settings (Gear Icon):** Ensures your EmailJS Service ID, Template ID, and Public Key are securely saved in LocalStorage so that real emails can be dispatched seamlessly upon Lockdown.

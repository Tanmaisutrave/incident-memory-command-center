# Incident Memory Agent

**AI-powered incident response with operational memory**

An intelligent DevOps/SRE agent that accumulates operational experience from previous incidents and uses that experience to improve recommendations for future incidents.

## 🎯 Problem

Production incidents often repeat. Engineers waste time investigating problems that their organization has already solved. Knowledge lives in scattered postmortems, runbooks, and tribal memory.

## 💡 Solution

The Incident Memory Agent functions like an engineer that never forgets. It:

- **Remembers** every incident, root cause, and resolution
- **Recalls** similar historical incidents when new problems occur
- **Learns** from outcomes to improve future recommendations
- **Explains** which previous experiences influenced its advice

## 🧠 Why Memory Matters

### Without Memory
Generic troubleshooting: "Check Redis connectivity, network latency, CPU usage..."

### With Hindsight Memory
Evidence-based recommendations: "3 similar incidents found. 2 were caused by Redis connection pool exhaustion. The previous successful resolution was increasing the pool size from 100 to 250 connections. Check current connection utilization first."

## 🏗️ Architecture

```
Frontend (React + Vite)
         ↓
FastAPI Backend
         ↓
Incident Agent
    ├── Groq LLM (Analysis)
    └── Hindsight Memory
         ├── RETAIN (Store incidents)
         ├── RECALL (Find similar)
         └── REFLECT (Discover patterns)
```

## 🚀 Features

- **Intelligent Incident Analysis** - LLM-powered understanding of production issues
- **Historical Context** - Automatic retrieval of similar past incidents
- **Evidence-Based Recommendations** - Suggestions backed by previous outcomes
- **Memory Transparency** - Clear visibility into which memories influenced decisions
- **Learning Timeline** - Visual representation of knowledge accumulation
- **Pattern Discovery** - Reflection across multiple incidents to identify trends

## 🛠️ Tech Stack

- **Frontend**: React, Vite, Tailwind CSS
- **Backend**: Python, FastAPI
- **AI**: Groq API (Llama 3.3 70B)
- **Memory**: Hindsight
- **Deployment**: Vercel (frontend), Render (backend)

## 📁 Project Structure

```
incident-memory-agent/
├── frontend/              # React application
├── backend/               # FastAPI application
│   ├── app/
│   │   ├── config.py
│   │   ├── hindsight_client.py
│   │   ├── main.py
│   │   └── ...
│   └── requirements.txt
├── scripts/
│   └── test_hindsight.py  # Hindsight integration test
├── docs/
└── README.md
```

## ⚙️ Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Hindsight API key
- Groq API key

### Backend Setup

1. Navigate to backend directory:
```powershell
cd backend
```

2. Create virtual environment:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

3. Install dependencies:
```powershell
pip install -r requirements.txt
```

4. Configure environment variables:
```powershell
Copy-Item .env.example .env
# Edit .env with your API keys
```

5. Test Hindsight integration:
```powershell
python ..\scripts\test_hindsight.py
```

6. Run the backend:
```powershell
uvicorn app.main:app --reload
```

### Frontend Setup

1. Navigate to frontend directory:
```powershell
cd frontend
```

2. Install dependencies:
```powershell
npm install
```

3. Configure environment variables:
```powershell
Copy-Item .env.example .env
# Edit .env if backend is not on localhost:8000
```

4. Run the development server:
```powershell
npm run dev
```

5. Open http://localhost:5173 in your browser

### Frontend Build

Build for production:
```powershell
npm run build
npm run preview
```

## 🧪 Testing

### Phase 1: Hindsight Integration

Run the Hindsight integration test:

```powershell
python scripts/test_hindsight.py
```

This verifies:
- ✓ Hindsight connectivity
- ✓ RETAIN - Store incident memories
- ✓ RECALL - Retrieve similar incidents
- ✓ REFLECT - Discover patterns

### Phase 2: Backend Tests

Run the backend tests:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
pytest tests/ -v
```

## 📊 Demo Scenario

1. **Incident #1**: Redis connection pool exhaustion - Agent learns the pattern
2. **Incident #2**: Similar symptoms - Agent recalls previous incident and suggests the same fix
3. **Incident #3**: Similar symptoms, different cause - Agent distinguishes between cases

## 🔒 Security

- Never commit `.env` files
- Use environment variables for all secrets
- API keys are never exposed in responses

## 🚧 Development Status

**Current Phase**: Phase 3 - Frontend Complete ✅

**Phase 1**: ✅ Hindsight Integration
- [x] Hindsight client setup
- [x] RETAIN/RECALL/REFLECT verified
- [x] Integration tests passing

**Phase 2**: ✅ Core Backend Agent
- [x] LLM integration (Groq)
- [x] Incident data models
- [x] Memory service
- [x] Analysis service
- [x] Incident service
- [x] Core agent logic
- [x] FastAPI endpoints (11 endpoints)
- [x] Seed data (12 incidents)
- [x] Backend tests (7/7 passing)

**Phase 3**: ✅ Frontend (COMPLETE)
- [x] React + Vite + Tailwind setup
- [x] Professional dark theme UI
- [x] Dashboard page
- [x] Analyze Incident page with memory display
- [x] Memory Explorer page (RECALL)
- [x] Learning Center page (REFLECT)
- [x] Compare Incidents page
- [x] Backend API integration
- [x] Historical memory prominently displayed

**Phase 4**: 🔜 Polish & Demo
- [ ] Advanced features
- [ ] Authentication
- [ ] Performance optimization

## 🎮 Running the Application

### Complete Setup (Backend + Frontend)

#### 1. Seed Historical Incidents

Populate Hindsight with synthetic incident data:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
py ..\scripts\seed_incidents.py
```

This creates 12 realistic production incidents in Hindsight memory.

#### 2. Start the Backend Server

```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

The API will be available at http://127.0.0.1:8000

#### 3. Start the Frontend (New Terminal)

```powershell
cd frontend
npm run dev
```

The UI will be available at http://localhost:5173

#### 4. Explore the Application

Open http://localhost:5173 in your browser and:
- View the Dashboard with system stats
- Click "Analyze New Incident" to test incident analysis
- Try demo incident buttons for quick testing
- Notice the **Historical Memory section** showing related past incidents
- Explore memories in the Memory Explorer
- Generate insights in the Learning Center
- Compare incidents to find patterns

### API Endpoints

**Core Workflows:**
- `POST /api/incidents/analyze` - Analyze a new incident with memory
- `POST /api/incidents/{id}/resolve` - Resolve and store to memory
- `POST /api/incidents/compare` - Compare with/without memory

**Memory Operations:**
- `POST /api/memory/recall` - Manual memory search
- `POST /api/memory/reflect` - Pattern discovery
- `GET /api/memory/stats` - Memory statistics

**Utilities:**
- `GET /api/health` - System health check
- `GET /api/incidents/{id}` - Get incident details
- `GET /api/incidents/{id}/memories` - Get related memories

## 🎯 Testing the Agent

### Test Scenario 1: Analyze with Memory

```bash
curl -X POST http://localhost:8000/api/incidents/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Payment API Redis Timeout",
    "service": "payment-api",
    "environment": "production",
    "severity": "P1",
    "symptoms": "API latency 7 seconds, Redis timeout errors, 502 responses"
  }'
```

The agent will:
1. Recall similar historical incidents (INC-1001, INC-1006)
2. Analyze with historical context
3. Provide evidence-based recommendations

### Test Scenario 2: Compare With/Without Memory

```bash
curl -X POST http://localhost:8000/api/incidents/compare \
  -H "Content-Type: application/json" \
  -d '{
    "incident": {
      "title": "Database Connection Issues",
      "service": "order-service",
      "environment": "production",
      "severity": "P1",
      "symptoms": "Connection timeouts, pool exhausted"
    }
  }'
```

This demonstrates the difference between generic and memory-informed analysis.

### Test Scenario 3: Reflect on Patterns

```bash
curl -X POST http://localhost:8000/api/memory/reflect \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the most common incident patterns and their resolutions?"
  }'
```

## 📝 License

MIT

## 🤝 Hackathon

Built for the Hindsight AI Agent Hackathon.

**Focus**: Demonstrating how persistent memory transforms an AI agent from generic advice-giver to experienced operational partner.

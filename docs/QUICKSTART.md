# 🚀 Quick Start Guide
## Incident Memory Command Center

Get the application running in 5 minutes!

---

## Prerequisites Checklist

Before starting, ensure you have:

- [ ] Python 3.11+ installed
- [ ] Node.js 18+ installed
- [ ] npm installed (comes with Node.js)
- [ ] Hindsight API key ([Get one here](https://hindsight.dev))
- [ ] Groq API key ([Get one here](https://console.groq.com))

---

## Step 1: Clone & Setup Backend (2 minutes)

### Navigate to Backend
```powershell
cd backend
```

### Create Virtual Environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Install Dependencies
```powershell
pip install -r requirements.txt
```

### Configure Environment
```powershell
# Copy example environment file
Copy-Item .env.example .env

# Edit .env and add your API keys:
# HINDSIGHT_API_KEY=your_hindsight_key_here
# GROQ_API_KEY=your_groq_key_here
```

### Seed Test Data
```powershell
py ..\scripts\seed_incidents.py
```

Expected output: ✅ "Successfully seeded 12 incidents"

---

## Step 2: Setup Frontend (1 minute)

### Open New Terminal & Navigate
```powershell
cd frontend
```

### Install Dependencies
```powershell
npm install
```

Expected output: "added 137 packages"

### Configure Environment
```powershell
# Copy example environment file
Copy-Item .env.example .env

# Default is fine: VITE_API_BASE_URL=http://127.0.0.1:8000
```

---

## Step 3: Start Both Servers (1 minute)

### Terminal 1: Start Backend
```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Wait for: ✅ "Application startup complete."

Backend running at: **http://127.0.0.1:8000**

### Terminal 2: Start Frontend
```powershell
cd frontend
npm run dev
```

Wait for: ✅ "Local: http://localhost:5173/"

Frontend running at: **http://localhost:5173**

---

## Step 4: Test the Application (1 minute)

### Open Your Browser
Navigate to: **http://localhost:5173**

### Try the Demo Flow
1. ✅ You should see the **Dashboard** with system stats
2. ✅ Click **"Analyze New Incident"** button
3. ✅ Click a **demo incident button** (e.g., "Database Connection Failed")
4. ✅ Click **"Analyze Incident"**
5. ✅ Wait for analysis (~5-10 seconds)
6. ✅ Scroll down to see **"🧠 Historical Memory"** section
7. ✅ Verify related past incidents are shown
8. ✅ See evidence-based recommendations

### Success Criteria
- You see the Historical Memory section with related incidents
- Recommendations reference past solutions
- No error messages appear

---

## 🎉 You're Ready!

Both servers are running and the agent is learning from incident history.

### What to Try Next

**Memory Explorer** (http://localhost:5173/memory)
- Search: "database issues"
- See all stored memories related to databases

**Learning Center** (http://localhost:5173/learning)
- Topic: "database performance"
- Generate insights from historical patterns

**Compare Incidents** (http://localhost:5173/compare)
- Compare any two incidents from the seeded data
- See similarities and differences

---

## 🐛 Troubleshooting

### Backend won't start
```
Error: "Hindsight connection failed"
```
**Solution**: Check your `HINDSIGHT_API_KEY` in `backend/.env`

### Frontend shows connection error
```
Error: "Failed to fetch"
```
**Solution**: Ensure backend is running at http://127.0.0.1:8000

### No memories found
```
"0 memories in bank"
```
**Solution**: Run seed script again: `py ..\scripts\seed_incidents.py`

### Port already in use
```
Error: "Address already in use"
```
**Solution**: 
- Backend: Change port with `--port 8001`
- Frontend: Change port in `vite.config.js`

---

## 📚 Learn More

- **Full README**: See [../README.md](../README.md)
- **API Documentation**: http://127.0.0.1:8000/docs (when backend running)
- **Phase 3 Report**: See [PHASE3_COMPLETION.md](PHASE3_COMPLETION.md)

---

## 🛑 Stopping the Servers

### Stop Backend
In Terminal 1: Press `Ctrl+C`

### Stop Frontend
In Terminal 2: Press `Ctrl+C`

---

## 🔑 Environment Variables Reference

### Backend (`.env`)
```env
# Required
HINDSIGHT_API_KEY=your_key_here
GROQ_API_KEY=your_key_here

# Optional (defaults are fine)
HINDSIGHT_BANK=incident-agent
GROQ_MODEL=openai/gpt-oss-120b
```

### Frontend (`.env`)
```env
# Optional (default is fine)
VITE_API_BASE_URL=http://127.0.0.1:8000
```

---

## 🎯 Key Features to Demo

### 1. Memory-Powered Analysis ⭐
- Analyze incident → See historical context
- **Most Important**: Historical Memory section shows evidence

### 2. Memory Search
- Search memories by natural language
- Filter by tags
- See similarity scores

### 3. Pattern Learning
- Generate insights from patterns
- REFLECT API in action

### 4. Incident Comparison
- Compare two incidents
- Find similarities and differences
- Memory-powered analysis

---

## 💡 Pro Tips

1. **Use Demo Buttons**: Fastest way to test analysis
2. **Watch Loading States**: Shows what the agent is doing
3. **Check Memory Section**: Always scroll down to see historical context
4. **Try Similar Incidents**: See how agent recognizes patterns
5. **Explore All Pages**: Each showcases different Hindsight capabilities

---

## 📞 Need Help?

- Check [PHASE3_COMPLETION.md](PHASE3_COMPLETION.md) for detailed documentation
- Review backend logs in Terminal 1
- Check browser console for frontend errors (F12)
- Verify both servers are running

---

**Happy Incident Analyzing! 🎉**

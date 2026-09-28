# Quick Start Guide

## Incident Memory Agent - Phase 1 Setup

### Prerequisites

- ✅ Python 3.14.4 (already installed)
- ✅ Virtual environment created
- ✅ Dependencies installed
- ⚠️ **API keys required** (you need to provide these)

---

## Step 1: Get Your API Keys

### Hindsight API Key
1. Visit: https://hindsight.vectorize.io/
2. Sign up or log in
3. Navigate to your dashboard
4. Create a new API key
5. Copy the key

### Groq API Key
1. Visit: https://console.groq.com/
2. Sign up or log in
3. Navigate to API Keys section
4. Create a new API key
5. Copy the key

---

## Step 2: Configure Environment

### Option A: Automated Setup (Recommended)

Run the setup script:

```powershell
.\scripts\setup.ps1
```

This will:
- Create the `.env` file
- Prompt you for API keys
- Configure everything automatically

### Option B: Manual Setup

1. Create the `.env` file:
```powershell
Copy-Item backend\.env.example backend\.env
```

2. Edit `backend\.env` and replace:
```
HINDSIGHT_API_KEY=your_actual_hindsight_api_key_here
GROQ_API_KEY=your_actual_groq_api_key_here
```

---

## Step 3: Test Hindsight Integration

```powershell
cd backend
.\venv\Scripts\Activate.ps1
py ..\scripts\test_hindsight.py
```

### Expected Output

```
============================================================
HINDSIGHT INTEGRATION TEST
============================================================
Bank ID: incident-agent

============================================================
TEST 0: HEALTH CHECK
============================================================
✓ Hindsight connection is healthy

============================================================
TEST 1: RETAIN - Store incident memory
============================================================
✓ Successfully retained memory

============================================================
TEST 2: RECALL - Retrieve similar incidents
============================================================
✓ Successfully recalled X memories

============================================================
TEST 3: REFLECT - Discover patterns
============================================================
✓ Successfully completed reflection

============================================================
TEST RESULTS SUMMARY
============================================================
Health Check.................................... ✓ PASS
RETAIN.......................................... ✓ PASS
RECALL.......................................... ✓ PASS
REFLECT......................................... ✓ PASS

============================================================
ALL TESTS PASSED ✓
Hindsight integration is working correctly!
============================================================
```

---

## Verification

✅ **Phase 1 is complete when all 4 tests pass**

If all tests pass, report back with:
- "All tests passed ✓"
- Screenshot or output (optional)

---

## Troubleshooting

### "API key not set" error
- Ensure `.env` file exists in `backend/` directory
- Check that API keys are set correctly (no quotes)

### "Module not found" error
- Ensure virtual environment is activated
- Re-run: `pip install -r requirements.txt`

### "Connection refused" error
- Check internet connection
- Verify Hindsight API is accessible
- Try again in a few minutes

### Tests still failing?
- Check `backend/SETUP.md` for detailed troubleshooting
- Verify API keys are valid and active
- Ensure no firewall blocking Hindsight API

---

## What's Next?

Once Phase 1 tests pass, we'll proceed to:

**Phase 2**: LLM Integration
- Groq client setup
- Incident parsing
- Prompt engineering

**Phase 3**: Synthetic incident data
- 30-50 realistic incidents
- Multiple categories
- Test scenarios

**Phase 4+**: Backend API, Frontend, Demo mode...

---

## Current Status

```
[✅] Project structure
[✅] Python environment
[✅] Dependencies installed
[✅] Hindsight client
[✅] Configuration system
[✅] Integration tests
[⏳] Waiting for API keys and test verification
```

---

## One-Command Test (After Setup)

```powershell
cd backend ; .\venv\Scripts\Activate.ps1 ; py ..\scripts\test_hindsight.py
```

This runs all three steps in one command.

---

**Ready?** Get your API keys and run the tests! 🚀

# Backend Setup Instructions

## Step 1: Environment Configuration

Before running the tests, you need to create a `.env` file with your API keys:

1. Copy the example file:
```powershell
Copy-Item .env.example .env
```

2. Edit the `.env` file and add your API keys:
```
HINDSIGHT_API_KEY=your_actual_hindsight_api_key
GROQ_API_KEY=your_actual_groq_api_key
```

### Getting API Keys

**Hindsight API Key:**
- Sign up at https://hindsight.vectorize.io/
- Navigate to your dashboard
- Create a new API key
- Copy it to your .env file

**Groq API Key:**
- Sign up at https://console.groq.com/
- Navigate to API Keys
- Create a new API key
- Copy it to your .env file

## Step 2: Test Hindsight Integration

Once you have configured your `.env` file, test the integration:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
py ..\\scripts\\test_hindsight.py
```

This will test:
- ✓ Hindsight connectivity
- ✓ RETAIN - Store incident memories
- ✓ RECALL - Retrieve similar incidents
- ✓ REFLECT - Discover patterns

## Expected Output

If successful, you should see:

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
✓ Successfully recalled memories

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

## Troubleshooting

### "API key not set" error
- Ensure you've created the `.env` file in the `backend/` directory
- Verify the API keys are correctly set (no quotes, no spaces)

### "Connection refused" error
- Check your internet connection
- Verify the HINDSIGHT_BASE_URL is correct
- Check if Hindsight service is accessible

### "Bank not found" error
- The bank will be created automatically on first use
- If persistent, check your API key permissions

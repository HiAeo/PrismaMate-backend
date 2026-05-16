import asyncio, traceback, sys
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# login as admin
r = client.post('/api/v1/auth/login', json={'username':'admin','password':'admin123'})
print('login status:', r.status_code)
print('login body:', r.text[:300])
token = r.json().get('access_token','')

# call reports
r2 = client.get('/api/v1/reports?skip=0&limit=50', headers={'Authorization':'Bearer '+token})
print('reports status:', r2.status_code)
print('reports body:', r2.text[:500])

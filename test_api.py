import requests, os
key = os.environ.get('DEEPSEEK_API_KEY','')
print('Key loaded:', key[:10]+'...')
try:
    r = requests.post('https://api.deepseek.com/v1/chat/completions',
        headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
        json={'model':'deepseek-chat', 'messages':[{'role':'user','content':'你好'}], 'max_tokens':10},
        timeout=10)
    print('Status:', r.status_code)
    print('Response:', r.json())
except Exception as e:
    print('Error:', e)

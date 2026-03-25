import json, os
state_file = os.path.join('data', 'state.json')
try:
    with open(state_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"Loaded {len(data.get('trades', []))} trades")
    original = len(data.get('trades', []))
    data['trades'] = [t for t in data.get('trades', []) if t.get('token_symbol') != 'CAPTCHA' and t.get('symbol') != 'CAPTCHA']
    new_len = len(data['trades'])
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Removed {original - new_len} CAPTCHA trades.")
except Exception as e:
    print(f"Error: {e}")

import requests

url = "http://localhost:11434/api/generate"

payload = {
    "model": "mistral",
    "prompt": "Escribe una breve descripción cultural del Museo del Prado",
    "stream": False
}

response = requests.post(url, json=payload)

if response.status_code == 200:
    print(response.json()["response"])
else:
    print("Error:", response.text)

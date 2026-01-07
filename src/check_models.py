import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("❌ ERRO: GEMINI_API_KEY não encontrada no .env")
    exit(1)

try:
    genai.configure(api_key=GEMINI_API_KEY)
    print("✨ Conectado à API Gemini\n")
    print("📋 Modelos disponíveis:\n")
    
    models = genai.list_models()
    for model in models:
        name = model.name.replace("models/", "")
        print(f"  - {name}")
        
except Exception as e:
    print(f"❌ Erro: {e}")

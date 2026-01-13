import os 
import sqlite3
import re
import sys
from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
from dotenv import load_dotenv
from google import genai

# --- INICIALIZAÇÃO ---

load_dotenv() 

app = Flask(__name__)

# Configuração de CORS robusta
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Variáveis de Ambiente
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Localização do Banco de Dados - LOGS IMPORTANTES AQUI
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Tentamos encontrar o banco na raiz ou na pasta src (onde o Render costuma rodar)
DB_PATH = os.path.join(BASE_DIR, 'NVI.sqlite.db')

def get_client():
    if not GEMINI_API_KEY:
        return None
    try:
        return genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"ERRO GENAI: {e}")
        return None

# --- DIAGNÓSTICO DO BANCO DE DADOS ---

def check_db_integrity():
    if not os.path.exists(DB_PATH):
        print(f"❌ ALERTA: Arquivo {DB_PATH} NÃO ENCONTRADO!")
        return False
    print(f"✅ Banco de dados encontrado em: {DB_PATH}")
    return True

def get_connection():
    if not check_db_integrity():
        return None
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"ERRO SQLITE: {e}")
        return None

# --- LÓGICA DE BUSCA ---

def fetch_relevant_verses(query):
    conn = get_connection()
    if not conn: 
        return "Atenção: O acesso ao banco de dados falhou. Responda usando seu conhecimento teológico geral."
    
    try:
        cursor = conn.cursor()
        clean_query = re.sub(r'[^\w\s]', '', query).strip()
        if not clean_query: return ""

        # Tenta busca simples se o FTS5 falhar ou não estiver pronto
        try:
            cursor.execute(
                "SELECT T1.text, T2.name, T1.chapter, T1.verse "
                "FROM verse T1 JOIN book T2 ON T1.book_id = T2.id "
                "WHERE T1.text LIKE ? LIMIT 3", (f'%{clean_query}%',)
            )
            results = cursor.fetchall()
            if results:
                return "\n".join([f"[{r[1]} {r[2]}:{r[3]}]: {r[0]}" for r in results])
        except Exception as e:
            print(f"Erro na busca: {e}")
            
        return ""
    finally:
        conn.close()

# --- ROTAS ---

@app.route('/')
def status():
    db_exists = os.path.exists(DB_PATH)
    return jsonify({
        "server": "online",
        "database_found": db_exists,
        "database_path": DB_PATH,
        "api_key_set": bool(GEMINI_API_KEY),
        "python_version": sys.version
    })

@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat():
    if request.method == 'OPTIONS':
        return _build_cors_preflight_response()
        
    if not GEMINI_API_KEY:
        return jsonify({"answer": "Erro: A chave GEMINI_API_KEY não foi detectada. Verifique as 'Environment Variables' no Render.", "source": "Sistema"}), 500

    try:
        data = request.get_json()
        user_query = data.get('query', '')
        
        if not user_query:
            return jsonify({"answer": "Diga-me, o que procuras?"}), 400

        # Busca contexto
        context = fetch_relevant_verses(user_query)
        
        client = get_client()
        if not client:
            return jsonify({"answer": "Erro ao conectar com a inteligência do Google.", "source": "API"}), 500

        prompt = f"""
        Você é o Rei Salomão, conhecido por sua sabedoria divina. 
        Responda de forma pastoral, poética e sábia.
        Se houver contexto abaixo, use-o para fundamentar sua resposta.
        
        CONTEXTO DAS ESCRITURAS:
        {context}
        
        PERGUNTA DO USUÁRIO:
        {user_query}
        """
        
        response = client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
        
        return _corsify_actual_response(jsonify({
            "answer": response.text,
            "source": "Busca na Bíblia NVI" if "Atenção" not in context and context else "Conhecimento Teológico Geral"
        }))

    except Exception as e:
        print(f"ERRO CRÍTICO: {str(e)}")
        return jsonify({"answer": f"Lamento, houve um erro no templo: {str(e)}", "source": "Erro Interno"}), 500

def _build_cors_preflight_response():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add('Access-Control-Allow-Headers', "Content-Type")
    response.headers.add('Access-Control-Allow-Methods', "POST")
    return response

def _corsify_actual_response(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
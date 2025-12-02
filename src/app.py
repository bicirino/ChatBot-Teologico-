#  O arquivo app.py é responsável por gerenciar a conexão com o banco de dados SQLite, implementar a lógica de busca 
# de texto bílico e iniciar o servidor Flask ; 

# -----------------------------------------------------------------------------------------------------------------------
import os                                                         #interação com o sistema operacional; 
import sqlite3                                                    #biblioteca para se conectar e manipular bancos de dados SQLite; 
from flask import Flask, jsonify, request                         #importa as ferramentas Flask; 
from flask_cors import CORS                                       #permite que o frontend se comunique com o backend; 
from dotenv import load_dotenv                                    #capacita a ferramenta para ler arquivo .env; 
from google import genai 
from google.genai import types 
from google.genai.errors import APIError 

#------------------------------------------------------------------------------------------------------------------------
#Carrega as variáveis do arquivo .env 
load_dotenv() 

#Abrir chave API do Gemini 
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY: 
    print("ERRO CRÍTICO Chave GEMINI_API_KEY não encontrada no arquivo .env") 

    #Usa uma chave imaginária para permiter que o app inicie (a IA não funcionará sem a chave real)
    GEMINI_API_KEY = "CHAVE_VAZIA_PARA_TESTE"

try: 
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"ERRO ao inicializar o cliente Gemini: {e}")
    client = None

# O caminho está configurado para voltar uma pasta (..) e buscar o arquivo na pasta 'data'
DB_PATH = os.path.join('..', 'data', 'NVI.sqlite.db')

# ------------------------------------------------------------------------------------------------------------------------
#FUNÇÃO DE CONEXÃO COM O BANCO DE DADOS: 
def get_connection():                                             
    """Cria e retorna a conexão com o banco de dados."""
    try:
        conn = sqlite3.connect(DB_PATH)                           #abre conexão com o banco de dados SQLite; 
        conn.row_factory = sqlite3.Row                            #configura os resultados para estrutura ({'nome_coluna': 'valor'}); 
        return conn
    
    except sqlite3.Error as e:                                    #abre o bloco de tratamento de erros; 
        print(f"ERRO CRÍTICO: Não foi possível conectar ao banco de dados em {DB_PATH}.")
        print(f"Detalhes do Erro: {e}")
        return None

# -------------------------------------------------------------------------------------------------------------------------
#FUNÇÃO DE BUSCA DE VERSÍCULO: 

def fetch_relevant_verses(query):
    """
    Simulação RAG: Retorna versículos relevantes para a pergunta do usuário.
    Esta função é temporária e retorna 3 versículos fixos para testar a IA.
    """
    conn = get_connection()
    if conn is None:
        return None

    # Versículos fixos: Gênesis 1:3, Salmos 23:1, João 14:6
    fixed_verses = [
        ("Gênesis", 1, 3), 
        ("Salmos", 23, 1), 
        ("João", 14, 6)
    ]
    
    results = []
    
    try:
        cursor = conn.cursor()
        
        # Consulta SQL para buscar os textos dos versículos fixos
        query_sql = """
        SELECT T1.text, T2.name AS book_name, T1.chapter, T1.verse
        FROM verse T1
        JOIN book T2 ON T1.book_id = T2.id
        WHERE T2.name = ? AND T1.chapter = ? AND T1.verse = ?
        """
        
        for book, chapter, verse in fixed_verses:
            cursor.execute(query_sql, (book, chapter, verse))
            result = cursor.fetchone()
            if result:
                results.append(
                    f"[{result['book_name']} {result['chapter']}:{result['verse']}]: {result['text']}"
                )
        return "\n".join(results)
        
    except sqlite3.Error as e:
        print(f"SQL_QUERY_FAILED: {e}")
        return None
    finally:
        conn.close()
#---------------------------------------------------------------------------------------------------------------------
# --- FUNÇÃO DE GERAÇÃO DA RESPOSTA (GEMINI) ---

def generate_answer_with_gemini(user_query, relevant_context):
    """
    Usa o modelo Gemini 2.5 Flash para gerar uma resposta baseada no contexto.
    Esta é a parte de Raciocínio (Generation).
    """
    if not client or GEMINI_API_KEY == "CHAVE_VAZIA_PARA_TESTE":
        return None, "CLIENT_NOT_INITIALIZED"

    # 1. Definir a Persona e Regras do Sistema (System Instruction)
    system_instruction = (
        "Você é Salomão, o ChatBot da Sabedoria. Sua persona é sábia, calma e teológica. "
        "Sua principal função é responder a perguntas do usuário baseando-se no CONTEXTO "
        "bíblico fornecido. Mantenha a resposta concisa, direta e sempre cite a referência "
        "do versículo no final da sua resposta, mesmo que já esteja no contexto."
    )

    # 2. Montar o Prompt RAG
    prompt = (
        f"CONTEXTO BÍBLICO PARA REFERÊNCIA:\n---\n{relevant_context}\n---\n\n"
        f"PERGUNTA DO USUÁRIO: {user_query}\n\n"
        "Com base no contexto e em sua sabedoria, forneça uma resposta única, completa e pastoral para o usuário."
    )

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction
            )
        )
        # Verifica se o conteúdo foi bloqueado por segurança
        if response.candidates and response.candidates[0].finish_reason == types.FinishReason.SAFETY:
            return None, "SAFETY_BLOCKED"
            
        return response.text, None

    except APIError as e:
        print(f"ERRO API GEMINI: {e}")
        return None, "API_ERROR"
    except Exception as e:
        print(f"ERRO INESPERADO: {e}")
        return None, "UNKNOWN_ERROR"


#----------------------------------------------------------------------------------------------------------------------
# --- APLICAÇÃO FLASK (ROUTING) ---
app = Flask(__name__)
CORS(app) 

# Rota de Teste Simples
@app.route('/')
def home():
    """Confirma que o servidor Flask está rodando."""
    return "Bem-vindo ao ChatBot Salomão! O servidor Flask está ativo."

# Rota Principal da API do Chat (RF.01)
@app.route('/api/chat', methods=['POST'])
def process_chat_query():
    """
    Recebe a pergunta do usuário, busca o contexto e usa a IA para gerar a resposta.
    """
    try:
        data = request.get_json()
        user_query = data.get('query', 'Pergunta Vazia')
        
    except Exception:
        return jsonify({"error": "Formato de requisição JSON inválido."}), 400

    if not client or GEMINI_API_KEY == "CHAVE_VAZIA_PARA_TESTE":
        return jsonify({"answer": "O servidor não conseguiu inicializar a conexão com a IA. Verifique sua GEMINI_API_KEY no arquivo .env.", "source": "Erro de Chave API"}), 503

    # 1. Fase RAG - Retrieval (Busca de Contexto)
    relevant_context = fetch_relevant_verses(user_query) # CHAMA A NOVA FUNÇÃO
    
    if not relevant_context:
        return jsonify({
            "answer": "Sinto muito, houve um erro ao consultar a Base de Dados.",
            "source": "Erro DB"
        }), 500

    # 2. Fase RAG - Generation (Geração da Resposta com a IA)
    generated_text, error_code = generate_answer_with_gemini(user_query, relevant_context) # CHAMA O GEMINI

    # 3. Tratamento de Erro da IA
    if error_code == "API_ERROR" or error_code == "UNKNOWN_ERROR":
        return jsonify({
            "answer": "Houve uma falha de comunicação com os Céus. Tente novamente.",
            "source": f"Erro API: {error_code}"
        }), 500
    if error_code == "SAFETY_BLOCKED":
        return jsonify({
            "answer": "Sinto muito, essa pergunta tocou em um tópico sensível. Minha Sabedoria está limitada a questões teológicas.",
            "source": "Bloqueio de Segurança"
        }), 400
    
    # 4. Sucesso: Retorno JSON
    # A fonte é o contexto que passamos para o modelo
    source_citation = "Referências usadas: " + relevant_context.replace('\n', ' | ')
    
    return jsonify({
        "answer": generated_text,
        "source": source_citation,
        "is_rag_active": True # AGORA DEVE SER TRUE
    })

# Executa o servidor Flask na porta 5000 (padrão)
if __name__ == '__main__':
    app.run(debug=True)
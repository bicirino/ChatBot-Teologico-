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



DB_PATH = os.path.join('..', 'data', 'NVI.sqlite.db')             #variável que armazena o caminho do banco de dados SQLite;

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

def fetch_verse_by_name(book_name, chapter, verse):
    """
    Busca um versículo específico usando o NOME do livro, capítulo e versículo.
    Usa JOIN para ligar as tabelas 'book' e 'verse'.
    """
    conn = get_connection()
    if conn is None:
        return {"error": "DB_CONNECTION_FAILED"}

    try:
        cursor = conn.cursor()

        # Consulta SQL usando JOIN para buscar o texto (T1.text) pelo nome do livro (T2.name)
        query = """
        SELECT T1.text, T2.name AS book_name, T1.chapter, T1.verse
        FROM verse T1
        JOIN book T2 ON T1.book_id = T2.id
        WHERE T2.name = ? AND T1.chapter = ? AND T1.verse = ?      
        """

        cursor.execute(query, (book_name, chapter, verse))         #executa a consulta SQL com os parâmetros fornecidos;
        result = cursor.fetchone()                                 #retorna apenas um resultado; 
        
        if result:
            # Retorna um dicionário com os dados
            return {
                "book": result['book_name'],
                "chapter": result['chapter'],
                "verse": result['verse'],
                "text": result['text']
            }
        else:
            return None # Versículo não encontrado

    except sqlite3.Error as e:
        return {"error": f"SQL_QUERY_FAILED: {e}"}
    finally:
        conn.close()
#---------------------------------------------------------------------------------------------------------------------
#CONFIGURAÇÃO DA APLICAÇÃO FLASK 

app = Flask(__name__)                                              #cria a instância da aplicação Flask;
CORS(app)                                                          #aplica as configurações CORS; 

# Rota de Teste Simples
@app.route('/')                                                    #define uma rota ou endpoint; 

def home():                                                        #função associada à rota raiz; 
    """Confirma que o servidor Flask está rodando."""
    return "Bem-vindo ao ChatBot Salomão! O servidor Flask está ativo."

#----------------------------------------------------------------------------------------------------------------------
# Rota Principal da API do Chat (RF.01)
@app.route('/api/chat', methods=['POST'])                          #define a rota '/api/chat' que enviará as perguntas dos usuários; 

def process_chat_query():
    """
    Recebe a pergunta do usuário e simula uma resposta RAG.
    
    No futuro (Fase 3), aqui entra o código real da IA que:
    1. Analisa a pergunta.
    2. Busca versículos relevantes (via RAG).
    3. Usa a IA Generativa (Gemini API) para formular a resposta.
    """
    try:
        data = request.get_json()                                 #Lê o corpo da requisição JSON; 
        user_query = data.get('query', 'Pergunta Vazia')          #Extrai a pergunta do usuário; 
 
    
    except Exception as e:                                        #tratamento de exceções e erros; 
        return jsonify({"error": "Formato de requisição JSON inválido."}), 400



    
    # TESTE DE INTEGRAÇÃO RAG 
    
    # 1. Simulação da busca do versículo (Retrieval)
    # Aqui, buscamos um versículo(Gênesis 1:3) apenas para testar a comunicação completa.
    test_result = fetch_verse_by_name('Gênesis', 1, 3) 
    
    if test_result and 'error' not in test_result:
        # 2. Simulação da Resposta da IA (Generation)
        # O modelo de IA Generativa usaria o 'test_result['text']' para formular a resposta.
        response_text = (
            f"Sua pergunta era: '{user_query}'. "
            f"Como um ponto de partida, o Espírito de Salomão ilumina a passagem: "
            f"'{test_result['text']}'"
        )
        
        # 3. Retorno JSON (RT.02 e RF.06)
        return jsonify({
            "answer": response_text,
            "source": f"{test_result['book']} {test_result['chapter']}:{test_result['verse']}",
            "is_rag_active": False # Marcador para o futuro
        })
    else:
        # Se a busca falhar (provavelmente problema no DB ou na query)
        error_message = test_result.get('error', 'Falha desconhecida na Base de Dados.')
        return jsonify({
            "answer": "Sinto muito, houve um erro crítico ao consultar a Sabedoria Antiga.",
            "source": f"Erro: {error_message}"
        }), 500

#-----------------------------------------------------------------------------------------------------------------
# Executa o servidor Flask na porta 5000 (padrão)
if __name__ == '__main__':                                #garante que o código dentro deste bloco só seja executado quando você executa o arquivo diretamente
    
    app.run(debug=True)                                   # 'debug=True'permite que o servidor reinicie automaticamente após alterações
                                                          # e inicia o servidor web Flask; 
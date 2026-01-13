# ChatBot-Teológico 
ChatBot Teológico “Salomão”

- O ChatBot Salomão é um assistente digital voltado para teologia e estudo bíblico, projetado para responder perguntas simples e complexas relacionadas ao contexto cristão.
O projeto combina IA Generativa com um banco de dados especializado para garantir respostas fundamentadas e confiáveis;
- Com uma didática respeitosa, clara e biblicamente embasada, o chatbot Salomão é capaz de responder a maioria esmagadora de qualquer dúvida teológica;
- **O chatbot responde usando exclusivamente conteúdo cristão/teológico**.

Deve interpretar perguntas envolvendo:
**Doutrina cristã** ;
**Ética** ;
**História bíblica** ;
**Teologia sistemática**.


## 🏗️ Arquitetura Técnica
**Backend**: 
Desenvolvido em Python;

**Frontend**: 
Construído com HTML + CSS;

**Base de Conhecimento**: 
Banco de Dados da tradução bíblica NVI;


## 🖥️ Usabilidade (UX/UI)

Interface simples, intuitiva e preparada para troca rápida de mensagens.

O usuário pode visualizar o histórico da conversa durante a sessão.

## 🛠 Estrutura do projeto 
```
PROJETO SALOMÃO/
├── src/                    # Pasta principal do código-fonte   
│   ├── app.py              # Servidor Flask 
│   └── NVI.sqlite.db       # Banco de dados da Bíblia NVI
|   └── .env                # Chaves de API 
|   └── index.html          # Interface visual do ChatBot (Frontend)
|
├── venv/                   # Ambiente virtual Python 
├── .gitignore              # Lista de arquivos ignorados pelo Git
├── LICENSE                 # Licença do projeto
├── README.md               # Documentação principal do projeto

```

## 🕹 Como iniciar o sistema? 

1. Obtenha as **variáveis do ambiente** com autor do projeto; 
2. **Clone o repositório** para seu computador;
3. Crie o arquivo **".env"** para o repositório, com a estrutura seguinte:
          ```GEMINI_API_KEY=CHAVE FORNECIDA PELO AUTOR ``` 
5. Inicie o **ambiente virtual venv**: 
      -  ``` Use o comando:  "Set-ExecutionPolicy RemoteSigned -Scope Process" para liberar temporariamente o acesso à segurança; ```
      -  ``` Use o comando: ".\venv\Scripts\activate" para ativar o ambiente virtual;```
6. Com o ambiente virtual ativado, **mude para a pasta "src"** - onde o servidor Flask está localizado;
7. Ative o servidor com o comando: **"python app.py"**;
8. Abra o arquivo **"index.html"** e teste diretamente no Vscode ou use o link para abrir no seu Browser.

**obs:** certifique que você tenha as bibliotecas seguintes instaladas: 
**Flask** | **flask-cors** | **google-genai** | **pythondotenv**
          
         
          


## ⚖ Licença 

Este projeto é licenciado pelo licença: MIT 



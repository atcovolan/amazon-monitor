# Monitor de Preços Amazon

Aplicação para monitorar preços de produtos da Amazon com scraping resiliente, histórico de preços com gráficos e alertas via Discord (preço alvo atingido e reposição de estoque).

## Stack

- **Backend**: Python 3.11 + FastAPI
- **Frontend**: React + Vite + TypeScript
- **Deploy**: Railway (Nixpacks)

## Como Executar Localmente

### 1. Backend (FastAPI)

```bash
pip install -r backend/requirements.txt
python -m uvicorn backend.app.main:app --reload
```

Backend em `http://127.0.0.1:8000`.

### 2. Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

Frontend em `http://localhost:5173`. O Vite faz proxy das chamadas `/api` para o backend na porta 8000.

## Deploy no Railway

O projeto usa Nixpacks (configurado em `nixpacks.toml`). O push para o repositório dispara o deploy automaticamente.

O build instala Node 20 + Python 3.11, compila o frontend React e serve tudo pelo backend com uvicorn.

## Dados

Persistidos localmente na pasta `data/` (excluída do git):

- `settings.json` — configurações gerais
- `monitors.json` — produtos monitorados
- `history/{id}.json` — histórico de preços por produto
- `backups/` — cópias de segurança automáticas

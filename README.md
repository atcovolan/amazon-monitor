# Monitor de Preços Amazon

Aplicação completa para monitorar preços de produtos da Amazon, com scraping resiliente, histórico de preços com gráficos, e alertas via webhook do Discord.

## Requisitos

- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) ou Anaconda instalado.
- [Node.js](https://nodejs.org/) (versão 18+ recomendada) instalado.

## Como Executar Localmente (Sem Docker)

### 1. Iniciar o Backend (FastAPI)

Abra o terminal (PowerShell ou Prompt de Comando) na raiz do projeto:

1. Ative o ambiente Conda:
   ```bash
   conda activate monitor-amazon
   ```
2. Execute o servidor de desenvolvimento a partir da raiz:
   ```bash
   python -m uvicorn backend.app.main:app --reload
   ```

O backend estará rodando em `http://127.0.0.1:8000`.

---

### 2. Iniciar o Frontend (React + Vite)

Abra outro terminal na raiz do projeto:

1. Mude para a pasta `frontend`:
   ```bash
   cd frontend
   ```
2. Execute o servidor de desenvolvimento:
   ```bash
   npm run dev
   ```

O frontend estará rodando em `http://localhost:5173`. O Vite está configurado para fazer o proxy de todas as chamadas `/api` automaticamente para o backend na porta `8000`.

---

## Estrutura de Pastas de Dados (`data/`)

Os dados são persistidos localmente na raiz do projeto na pasta `data/`:
- `data/settings.json`: Configurações gerais do sistema.
- `data/monitors.json`: Produtos monitorados.
- `data/history/{monitor_uuid}.json`: Histórico de variação de preços individual de cada produto.
- `data/backups/`: Cópias automáticas de segurança criadas antes de alterações críticas.

# Prompt para Codex — Monitor de Preços Amazon

Quero que você desenvolva uma aplicação completa de **monitoramento de preços de produtos da Amazon**, com interface web, monitoramento automático e notificações via webhook do Discord.

A aplicação deve ser organizada, modular, simples de executar localmente e preparada para crescer futuramente.

> **Importante:** leia todos os requisitos antes de começar. Antes de escrever o código, proponha a arquitetura definitiva, identifique possíveis conflitos ou riscos técnicos e crie um arquivo `IMPLEMENTATION_PLAN.md`. Depois, implemente o projeto fase por fase.

---

# 1. Objetivo

O usuário deverá conseguir cadastrar um produto da Amazon informando:

- URL do produto;
- preço desejado para alerta;
- intervalo de monitoramento;
- webhook do Discord, quando não quiser utilizar o webhook padrão;
- status ativo/pausado.

A aplicação deverá acessar periodicamente a página do produto, obter seu preço atual e enviar uma notificação para o Discord quando o preço atingir ou ficar abaixo do valor definido.

Fluxo esperado:

```text
Adicionar Monitor
        ↓
colar URL Amazon
        ↓
Testar Produto
        ↓
produto encontrado
        ↓
definir preço alvo
        ↓
definir intervalo
        ↓
definir webhook ou usar padrão
        ↓
Salvar
        ↓
Monitoramento automático
```

---

# 2. Stack

Utilize preferencialmente:

## Backend

- Python
- FastAPI
- Pydantic
- `curl_cffi`
- APScheduler ou solução equivalente para execução dos monitores
- armazenamento em JSON

## Frontend

- React
- Vite
- TypeScript
- Tailwind CSS
- Recharts para gráficos

Se considerar outra tecnologia mais apropriada, explique a justificativa antes de alterar a stack.

## Não utilizar nesta primeira versão

Não utilize como mecanismo principal de persistência:

- SQLite
- PostgreSQL
- MySQL
- SQLAlchemy
- Alembic

Nesta versão, **configurações, links, monitores e histórico devem ser persistidos em JSON**.

A arquitetura, porém, deve permitir uma migração futura para banco de dados sem reescrever toda a aplicação.

---

# 3. Estrutura do projeto

Quero separação clara de responsabilidades.

Estrutura sugerida:

```text
project/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── routes/
│   │   ├── services/
│   │   │   ├── amazon.py
│   │   │   ├── discord.py
│   │   │   └── monitor.py
│   │   ├── scheduler/
│   │   ├── storage/
│   │   │   ├── base.py
│   │   │   └── json_storage.py
│   │   └── utils/
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   ├── hooks/
│   │   ├── types/
│   │   └── utils/
│   └── package.json
│
├── data/
│   ├── settings.json
│   ├── monitors.json
│   ├── history/
│   └── backups/
│
├── docker-compose.yml
├── README.md
└── IMPLEMENTATION_PLAN.md
```

Evite colocar toda a aplicação em poucos arquivos.

---

# 4. Persistência obrigatória em JSON

Todas as configurações da aplicação, links cadastrados, monitores e histórico de preços devem ser armazenados em arquivos JSON.

A estrutura desejada é:

```text
data/
├── settings.json
├── monitors.json
├── history/
│   ├── UUID-1.json
│   ├── UUID-2.json
│   └── UUID-3.json
└── backups/
    ├── monitors.backup.json
    └── settings.backup.json
```

Não espalhe leitura e escrita de JSON pela aplicação.

Crie uma camada específica de armazenamento.

Exemplo:

```text
backend/app/storage/json_storage.py
```

Crie também uma abstração para permitir uma futura troca do armazenamento.

Exemplo conceitual:

```python
class StorageInterface:
    def get_monitors(self):
        ...

    def get_monitor(self, monitor_id):
        ...

    def create_monitor(self, data):
        ...

    def update_monitor(self, monitor_id, data):
        ...

    def delete_monitor(self, monitor_id):
        ...

    def get_settings(self):
        ...

    def update_settings(self, data):
        ...

    def append_history(self, monitor_id, entry):
        ...

    def get_history(self, monitor_id):
        ...
```

Implementação atual:

```python
class JsonStorage(StorageInterface):
    ...
```

Futuramente deverá ser possível implementar:

```python
class DatabaseStorage(StorageInterface):
    ...
```

sem modificar a lógica principal de:

- scraper;
- scheduler;
- Discord;
- API;
- frontend.

---

# 5. `settings.json`

O arquivo deve armazenar configurações globais.

Exemplo:

```json
{
  "discord_webhook": "https://discord.com/api/webhooks/...",
  "default_check_interval": 300,
  "theme": "dark",
  "currency": "BRL"
}
```

Pode adicionar outros campos que sejam necessários.

O webhook padrão deve poder ser editado pela interface.

---

# 6. `monitors.json`

O arquivo deve armazenar todos os produtos monitorados e suas configurações.

Exemplo:

```json
{
  "monitors": [
    {
      "id": "1de431f8-14d5-436c-a48e-84931ee305cc",
      "name": "Logitech G Pro X Superlight",
      "asin": "B0XXXXXXXX",
      "original_url": "https://www.amazon.com.br/produto/dp/B0XXXXXXXX?tag=abc",
      "url": "https://www.amazon.com.br/dp/B0XXXXXXXX",
      "image_url": "https://...",
      "target_price": 499.90,
      "current_price": 549.90,
      "previous_price": 599.90,
      "lowest_price": 499.90,
      "highest_price": 699.90,
      "check_interval": 300,
      "is_active": true,
      "alert_triggered": false,
      "use_default_webhook": true,
      "discord_webhook": null,
      "availability": true,
      "status": "monitoring",
      "last_checked_at": "2026-08-26T21:30:00",
      "next_check_at": "2026-08-26T21:35:00",
      "last_error": null,
      "last_error_at": null,
      "created_at": "2026-08-26T20:00:00",
      "updated_at": "2026-08-26T21:30:00"
    }
  ]
}
```

Cada monitor deve possuir um UUID único.

---

# 7. Histórico em JSON

Não armazene todo o histórico dentro de `monitors.json`.

Cada produto deve possuir seu próprio arquivo:

```text
data/history/{monitor_uuid}.json
```

Exemplo:

```json
{
  "monitor_id": "1de431f8-14d5-436c-a48e-84931ee305cc",
  "history": [
    {
      "price": 599.90,
      "available": true,
      "checked_at": "2026-08-26T20:00:00"
    },
    {
      "price": 549.90,
      "available": true,
      "checked_at": "2026-08-26T21:00:00"
    }
  ]
}
```

Registrar pelo menos:

- preço;
- disponibilidade;
- data e hora da consulta.

O sistema deve utilizar o histórico para calcular:

- menor preço registrado;
- maior preço registrado;
- preço médio;
- variação de preço;
- gráfico de evolução.

---

# 8. Escrita segura dos JSONs

A aplicação poderá possuir vários jobs concorrentes.

Portanto, a escrita nos JSONs precisa ser segura.

Não sobrescreva diretamente os arquivos principais de maneira que possa causar corrupção.

Utilize escrita atômica.

Fluxo sugerido:

```text
monitors.json
      ↓
escrever monitors.tmp
      ↓
validar conteúdo
      ↓
os.replace(...)
      ↓
monitors.json atualizado
```

Implemente:

- lock de leitura/escrita quando necessário;
- escrita atômica;
- tratamento de exceções;
- validação antes de substituir arquivo principal.

Evite race conditions quando dois monitores terminarem consultas praticamente ao mesmo tempo.

---

# 9. Criação automática dos arquivos

Na primeira execução, caso os arquivos não existam, a aplicação deverá criá-los automaticamente.

Exemplo:

`data/monitors.json`

```json
{
  "monitors": []
}
```

`data/settings.json`

```json
{
  "discord_webhook": null,
  "default_check_interval": 300,
  "theme": "dark",
  "currency": "BRL"
}
```

Também crie automaticamente:

```text
data/history/
data/backups/
```

A primeira execução não deve falhar por ausência dos arquivos.

---

# 10. Backup dos JSONs

Antes de substituir configurações importantes, mantenha uma cópia de backup quando apropriado.

Exemplo:

```text
data/backups/monitors.backup.json
data/backups/settings.backup.json
```

Se o JSON principal estiver corrompido:

1. registrar o erro;
2. tentar carregar o backup;
3. restaurar o arquivo principal somente se o backup for válido;
4. nunca apagar silenciosamente dados do usuário.

---

# 11. Cadastro de produto

Criar interface para cadastrar um monitor.

Campos:

- nome do produto, opcional;
- URL da Amazon;
- preço alvo;
- intervalo de consulta;
- usar webhook padrão;
- webhook específico, se desejado;
- ativo/pausado.

Exemplo:

```text
URL:
https://www.amazon.com.br/dp/XXXXXXXX

Preço alvo:
R$ 299,90

Verificar a cada:
5 minutos

Webhook:
Usar padrão
```

Permitir pelo menos:

- 30 segundos;
- 1 minuto;
- 2 minutos;
- 5 minutos;
- 10 minutos;
- 30 minutos;
- 1 hora.

Internamente armazenar o intervalo em segundos.

---

# 12. Testar produto antes de salvar

Ao inserir uma URL, deve existir o botão:

```text
Testar produto
```

O backend deverá consultar a Amazon antes do cadastro e retornar:

- título;
- imagem;
- preço atual;
- disponibilidade;
- ASIN;
- URL normalizada.

Assim o usuário consegue confirmar que o link está correto antes de criar o monitor.

---

# 13. Amazon scraper

Utilize obrigatoriamente:

```python
from curl_cffi import requests
```

Exemplo conceitual:

```python
response = requests.get(
    url,
    impersonate="chrome",
    timeout=30
)
```

Não utilize Selenium ou Playwright inicialmente.

Toda a lógica relacionada à Amazon deve ficar isolada em:

```text
backend/app/services/amazon.py
```

Estrutura conceitual:

```python
class AmazonScraper:
    def get_product(self, url):
        ...

    def get_price(self, url):
        ...
```

O scraper deverá tentar extrair:

- título;
- preço atual;
- imagem;
- disponibilidade;
- ASIN;
- URL.

---

# 14. Extração de preço

Não dependa de apenas um seletor CSS.

Implemente múltiplas estratégias de extração.

Considere estruturas como:

```text
.a-price .a-offscreen
#priceblock_ourprice
#priceblock_dealprice
#corePrice_feature_div
```

Esses são apenas exemplos.

A implementação deve ser resiliente a pequenas mudanças no HTML.

O valor deve ser convertido corretamente para um tipo apropriado para cálculos monetários, preferencialmente `Decimal`.

Exemplo:

```text
R$ 1.299,90
```

deve virar:

```text
1299.90
```

Não use `float` quando isso puder introduzir erro de precisão monetária.

---

# 15. Normalização de URLs

Aceitar URLs como:

```text
amazon.com.br/dp/ASIN
amazon.com.br/gp/product/ASIN
URLs longas com parâmetros
URLs de compartilhamento
```

Crie funções como:

```python
extract_asin(url)
normalize_amazon_url(url)
```

Sempre que possível, gerar URL canônica:

```text
https://www.amazon.com.br/dp/{ASIN}
```

Armazenar no JSON:

- URL original;
- URL normalizada;
- ASIN.

Remover parâmetros de tracking desnecessários.

---

# 16. Todos os links devem ser salvos em JSON

Qualquer link importante para o funcionamento da aplicação deve ser persistido.

Incluindo:

- URL original da Amazon;
- URL normalizada;
- URL da imagem;
- webhook do Discord;
- qualquer outro link necessário para o monitor.

Não deixar links essenciais apenas em memória.

---

# 17. Monitoramento de preço

Cada produto deve possuir seu próprio intervalo.

Exemplo:

```text
Produto A -> 1 minuto
Produto B -> 5 minutos
Produto C -> 30 minutos
```

O scheduler deverá respeitar cada intervalo individualmente.

Não crie loops bloqueantes.

Não faça:

```python
while True:
    ...
```

na thread principal da API.

Utilize jobs em background.

---

# 18. Scheduler

Na inicialização:

```text
Aplicação inicia
        ↓
carregar monitors.json
        ↓
identificar monitores ativos
        ↓
registrar jobs
        ↓
iniciar monitoramento
```

Ao criar monitor:

```text
salvar monitors.json
        ↓
criar job
```

Ao alterar intervalo:

```text
atualizar monitors.json
        ↓
reschedule job
```

Ao pausar:

```text
is_active = false
        ↓
salvar JSON
        ↓
pausar/remover job
```

Ao retomar:

```text
is_active = true
        ↓
salvar JSON
        ↓
criar job novamente
```

Ao excluir:

```text
remover job
      ↓
remover monitor do JSON
      ↓
tratar arquivo de histórico
```

Não deixe jobs órfãos.

---

# 19. Próxima consulta

Sempre que possível, mantenha no monitor:

```text
last_checked_at
next_check_at
```

A interface deverá mostrar:

- última consulta;
- próxima consulta.

Essas datas devem permanecer consistentes com o scheduler.

---

# 20. Concorrência

A aplicação deve suportar vários produtos.

Não quero que:

```text
Produto A demora 10 segundos
```

e bloqueie:

```text
Produto B
Produto C
Produto D
```

Projete execução concorrente adequada.

Ao mesmo tempo, adicione limite de concorrência para evitar dezenas de requisições simultâneas.

Utilize mecanismos como:

- worker pool;
- semaphore;
- executor;
- limite configurável de tarefas concorrentes.

Garanta também que a concorrência não corrompa os arquivos JSON.

---

# 21. Comportamento diante de bloqueios

Não implemente técnicas agressivas de evasão.

Pode utilizar recursos normais do `curl_cffi`, como impersonação de navegador.

Não quero:

- bypass agressivo de captcha;
- técnicas de evasão de mecanismos anti-bot;
- loops massivos;
- rotação abusiva de requisições.

Se houver:

- HTTP 403;
- HTTP 429;
- captcha;
- bloqueio;
- resposta inválida;

registre o erro e aguarde o próximo ciclo normal.

---

# 22. Sessões HTTP

Centralize as requisições HTTP da Amazon.

Quando apropriado, utilize uma sessão reutilizável.

Configure:

- timeout;
- headers adequados;
- `impersonate`;
- tratamento de erro;
- fechamento correto dos recursos.

Não espalhe chamadas HTTP diretamente pelas rotas da API.

---

# 23. Discord

Criar:

```text
backend/app/services/discord.py
```

Quando:

```text
preço_atual <= preço_alvo
```

enviar uma notificação pelo webhook do Discord.

Utilizar embed.

Exemplo de conteúdo:

```text
🔥 PREÇO ALVO ATINGIDO

Produto:
Logitech G Pro X Superlight

Preço anterior:
R$ 599,90

Preço atual:
R$ 449,90

Preço alvo:
R$ 500,00

Economia:
R$ 150,00

[ABRIR PRODUTO]
```

O embed deve incluir:

- nome;
- imagem;
- preço atual;
- preço alvo;
- preço anterior;
- diferença em reais;
- porcentagem de queda;
- link do produto;
- horário da consulta.

---

# 24. Webhook padrão e webhook por produto

O sistema deverá permitir um webhook padrão em `settings.json`.

Cada monitor poderá possuir:

```json
{
  "use_default_webhook": true,
  "discord_webhook": null
}
```

ou:

```json
{
  "use_default_webhook": false,
  "discord_webhook": "https://discord.com/api/webhooks/..."
}
```

Se não houver webhook válido, o monitor deverá continuar funcionando, apenas registrando que não foi possível enviar a notificação.

---

# 25. Segurança do webhook

Mesmo sendo salvo em JSON:

- nunca mostre o webhook completo na interface;
- nunca registre o webhook completo nos logs;
- não envie o webhook inteiro ao frontend quando isso não for necessário.

Na interface, mostrar algo semelhante a:

```text
https://discord.com/api/webhooks/********
```

Segredos adicionais podem ficar no `.env`.

Crie:

```text
.env.example
```

Nunca versione:

```text
.env
```

---

# 26. Evitar spam de alertas

Não quero receber mensagem a cada consulta enquanto o preço permanecer abaixo do alvo.

Exemplo:

Preço alvo:

```text
R$ 500
```

Histórico:

```text
550
520
499 -> ALERTAR
480 -> NÃO ALERTAR
470 -> NÃO ALERTAR
510 -> resetar alerta
490 -> ALERTAR NOVAMENTE
```

Utilize um estado como:

```text
alert_triggered
```

Quando o preço voltar a ficar acima do alvo, o estado deve ser resetado.

---

# 27. Dashboard

Criar dashboard mostrando os produtos monitorados.

Cada produto deverá aparecer em card ou lista visualmente organizada.

Exemplo:

```text
┌─────────────────────────────────┐
│ Logitech G Pro X                │
│                                 │
│ Atual:       R$ 549,90          │
│ Alvo:        R$ 499,90          │
│                                 │
│ Última consulta: 21:32          │
│ Próxima consulta: 21:37         │
│                                 │
│ 🟢 Monitorando                  │
│                                 │
│ [Ver] [Editar] [Pausar]         │
└─────────────────────────────────┘
```

Mostrar:

- imagem;
- nome;
- preço atual;
- preço alvo;
- último preço;
- diferença percentual;
- status;
- última consulta;
- próxima consulta;
- intervalo configurado.

Status possíveis:

```text
Monitorando
Preço alvo atingido
Pausado
Produto indisponível
Erro
```

---

# 28. Resumo da dashboard

No topo da dashboard, mostrar indicadores como:

```text
Produtos monitorados
Alertas disparados
Produtos abaixo do alvo
Erros de consulta
```

Esses valores devem ser derivados dos dados reais.

---

# 29. Página do produto

Ao abrir um monitor, mostrar:

- imagem;
- título;
- URL;
- ASIN;
- preço atual;
- preço alvo;
- preço anterior;
- menor preço registrado;
- maior preço registrado;
- preço médio;
- última atualização;
- próxima atualização;
- intervalo de consulta;
- disponibilidade;
- status;
- último erro, quando houver.

---

# 30. Gráfico

Na página do produto, criar gráfico da evolução do preço.

Eixo X:

```text
Data / hora
```

Eixo Y:

```text
Preço
```

Também desenhar uma linha visual indicando o preço alvo.

Utilizar preferencialmente:

```text
Recharts
```

Adicionar filtros:

```text
24 horas
7 dias
30 dias
Todo período
```

---

# 31. Histórico visual

Nos cards e na página do produto, exibir variação.

Exemplo de queda:

```text
R$ 549,90

↓ 8,3%

Último preço:
R$ 599,90
```

Exemplo de aumento:

```text
R$ 629,90

↑ 5,0%

Último preço:
R$ 599,90
```

---

# 32. Gerenciamento dos monitores

Permitir:

- criar;
- editar;
- excluir;
- pausar;
- retomar;
- executar consulta manual;
- alterar preço alvo;
- alterar intervalo;
- trocar webhook;
- alternar entre webhook padrão e específico.

Adicionar botão:

```text
Verificar agora
```

A consulta manual também deve atualizar:

- preço;
- histórico;
- datas;
- status;
- alerta, quando aplicável.

---

# 33. Configurações

Criar uma página de configurações.

Permitir editar:

- webhook padrão do Discord;
- intervalo padrão;
- tema;
- moeda;
- limite máximo de consultas simultâneas, se implementado;
- outras configurações globais relevantes.

Persistir tudo em:

```text
data/settings.json
```

---

# 34. Interface

Quero uma interface moderna, simples e responsiva.

Utilize Tailwind CSS.

Layout sugerido:

```text
Sidebar
    Dashboard
    Monitores
    Adicionar produto
    Configurações

Header
    Monitor de Preços Amazon
```

Não faça uma interface com aparência de protótipo cru.

Utilize bom espaçamento, hierarquia visual e componentes reutilizáveis.

---

# 35. Dark mode

Criar suporte a:

```text
Light
Dark
```

Dark pode ser o padrão inicial.

A escolha deve ser persistida em `settings.json`.

---

# 36. UX

Adicionar:

- loading states;
- mensagens de erro;
- toasts;
- confirmação para excluir;
- skeleton loading;
- badges de status;
- campos validados;
- formatação monetária brasileira;
- estados vazios;
- feedback de sucesso;
- botões desabilitados durante requisições.

Formato brasileiro:

```text
R$ 1.299,90
```

---

# 37. API

Criar endpoints aproximadamente assim:

```text
GET    /api/products
POST   /api/products
GET    /api/products/{id}
PUT    /api/products/{id}
DELETE /api/products/{id}

POST   /api/products/test
POST   /api/products/{id}/check
POST   /api/products/{id}/pause
POST   /api/products/{id}/resume

GET    /api/products/{id}/history

GET    /api/settings
PUT    /api/settings
```

Utilizar Pydantic para validação dos requests e responses.

Não permitir que as rotas manipulem diretamente arquivos JSON.

As rotas devem chamar services/storage apropriados.

---

# 38. Tratamento de erros

A aplicação não deve quebrar se uma consulta falhar.

Tratar:

- timeout;
- HTTP 403;
- HTTP 429;
- HTTP 500;
- produto removido;
- produto indisponível;
- preço não encontrado;
- HTML inesperado;
- URL inválida;
- webhook inválido;
- conexão perdida;
- JSON corrompido;
- erro de escrita em disco.

Nos monitores, armazenar:

```text
last_error
last_error_at
```

Depois de um erro, tentar novamente somente no próximo ciclo normal.

Não faça retry agressivo.

---

# 39. Logs

Adicionar logging estruturado e legível.

Exemplo:

```text
[21:30:01] Verificando B0XXXXXXXX
[21:30:02] Produto encontrado: Mouse Logitech
[21:30:02] Preço: R$ 529,90
[21:30:02] Alvo: R$ 499,90
[21:30:02] Nenhum alerta necessário
```

Erro:

```text
[21:35:01] ERROR B0XXXXXXXX - preço não encontrado
```

Nunca inclua webhook completo nos logs.

---

# 40. Datas e horários

Utilize datas e horários consistentes.

Preferencialmente:

- armazenar timestamps em formato ISO 8601;
- centralizar manipulação de datas;
- evitar strings montadas manualmente em vários pontos.

Exemplo:

```text
2026-08-26T21:30:00-03:00
```

O frontend deverá formatar as datas de maneira amigável.

---

# 41. Valores monetários

Internamente, utilize `Decimal` ou outra estratégia segura.

Evite usar `float` diretamente para lógica monetária importante.

Nos JSONs, serialize os valores de maneira consistente.

A aplicação deve conseguir ler novamente esses valores sem perda de precisão relevante.

---

# 42. Testes

Criar testes principalmente para:

- extração de ASIN;
- normalização de URL;
- parse de preço;
- múltiplos layouts HTML;
- detecção de preço alvo;
- controle anti-spam;
- persistência em JSON;
- escrita atômica;
- locks;
- recuperação de backup;
- scheduler;
- pause/resume;
- histórico;
- cálculo de menor/maior/média.

Criar HTML mocks para testar o scraper sem acessar a Amazon em todos os testes.

Evite testes que dependam constantemente da Amazon real.

---

# 43. Testes da camada JSON

Crie testes específicos para:

```text
criar monitors.json
ler monitors.json
adicionar monitor
editar monitor
excluir monitor
escrita concorrente
arquivo corrompido
restauração de backup
criação de history/{uuid}.json
append de histórico
```

Nunca deixe um teste alterar os arquivos reais do usuário.

Utilize diretórios temporários nos testes.

---

# 44. Docker

Depois da aplicação funcionar localmente, adicionar:

```text
Dockerfile backend
Dockerfile frontend
docker-compose.yml
```

Para iniciar:

```bash
docker compose up --build
```

Não comece pelo Docker.

Primeiro faça a aplicação funcionar localmente.

Ao usar Docker, monte a pasta:

```text
data/
```

como volume persistente para que os monitores não sejam perdidos quando o container for recriado.

---

# 45. README

Criar README completo explicando:

- objetivo;
- requisitos;
- instalação;
- backend;
- frontend;
- variáveis de ambiente;
- estrutura dos JSONs;
- como iniciar;
- como cadastrar produto;
- como criar webhook do Discord;
- como funciona o monitoramento;
- como funciona o histórico;
- testes;
- Docker;
- estrutura do projeto;
- solução de problemas comuns.

---

# 46. Arquivos que não devem ser versionados

Configure `.gitignore` adequadamente.

Não versionar:

```text
.env
__pycache__/
node_modules/
dist/
arquivos temporários
```

Avalie se os JSONs reais do usuário devem ficar fora do Git.

Se sim, crie exemplos:

```text
data/settings.example.json
data/monitors.example.json
```

e faça a aplicação criar os arquivos reais automaticamente.

Não coloque webhooks reais no repositório.

---

# 47. Qualidade de código

Quero:

- código legível;
- nomes claros;
- type hints em Python;
- interfaces bem definidas;
- componentes frontend reutilizáveis;
- funções pequenas quando fizer sentido;
- separação de responsabilidades;
- tratamento de erro consistente;
- ausência de duplicação desnecessária.

Evite overengineering.

A aplicação deve continuar simples de entender e manter.

---

# 48. Não criar placeholders

Não considere uma funcionalidade pronta se possuir somente:

```text
TODO
pass
mock temporário
função vazia
```

Funcionalidades essenciais devem estar realmente implementadas.

Mocks só devem existir em testes ou quando explicitamente justificados.

---

# 49. Plano de implementação obrigatório

Antes de começar a escrever código:

1. leia todos os requisitos;
2. proponha a arquitetura;
3. identifique pontos de atenção;
4. crie `IMPLEMENTATION_PLAN.md`;
5. só depois inicie a implementação.

Divida o plano em fases.

Sugestão:

```text
Fase 1
Estrutura inicial do projeto

Fase 2
Schemas e modelos de domínio

Fase 3
Camada de persistência JSON

Fase 4
Amazon scraper com curl_cffi

Fase 5
API FastAPI

Fase 6
Scheduler e concorrência

Fase 7
Discord e controle de alertas

Fase 8
Frontend

Fase 9
Histórico e gráficos

Fase 10
Testes e robustez

Fase 11
Docker

Fase 12
Documentação e revisão final
```

---

# 50. Processo de implementação

Ao final de cada fase:

1. revise o código;
2. execute os testes disponíveis;
3. execute lint/type checking quando configurado;
4. corrija os erros encontrados;
5. verifique se não houve regressão;
6. atualize o `IMPLEMENTATION_PLAN.md`;
7. só então avance.

Não faça uma alteração gigantesca tentando implementar tudo de uma vez.

Prefira etapas pequenas e verificáveis.

---

# 51. Critérios de conclusão

Considere a aplicação concluída somente quando for possível:

```text
abrir a interface
      ↓
adicionar URL Amazon
      ↓
testar produto
      ↓
visualizar dados encontrados
      ↓
definir preço alvo
      ↓
definir intervalo
      ↓
salvar monitor
      ↓
reiniciar aplicação
      ↓
monitor continuar cadastrado
      ↓
scheduler recuperar monitor
      ↓
consultar automaticamente
      ↓
salvar histórico
      ↓
atingir preço alvo
      ↓
enviar Discord
```

Também deverá ser possível:

```text
pausar monitor
retomar monitor
editar monitor
excluir monitor
verificar agora
ver histórico
visualizar gráfico
alterar configurações
```

---

# 52. Fluxo técnico esperado

```text
Frontend React
      ↓
FastAPI
      ↓
Services
      ↓
JsonStorage
      ↓
settings.json / monitors.json
      ↓
Scheduler
      ↓
AmazonScraper
      ↓
curl_cffi
      ↓
Amazon
      ↓
resultado da consulta
      ↓
history/{monitor_id}.json
      ↓
comparação com preço alvo
      ↓
controle anti-spam
      ↓
Discord Webhook
```

---

# 53. Requisito de persistência após reinicialização

A aplicação deve continuar funcionando após ser reiniciada.

Ao iniciar:

1. carregar `settings.json`;
2. carregar `monitors.json`;
3. validar os dados;
4. recuperar monitores ativos;
5. recriar seus jobs no scheduler;
6. continuar o monitoramento.

Nenhuma configuração ou produto cadastrado pode depender exclusivamente da memória do processo.

---

# 54. Requisito final

Não altere os requisitos silenciosamente.

Caso encontre uma decisão técnica problemática:

1. explique o problema;
2. proponha uma solução;
3. escolha a alternativa mais simples e robusta;
4. registre a decisão no `IMPLEMENTATION_PLAN.md`.

Não comece codificando aleatoriamente.

Primeiro organize a arquitetura e o plano.

Depois implemente de forma incremental até termos uma aplicação funcional e executável localmente.

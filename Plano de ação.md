# 🤖 PLANO DE EXECUÇÃO DE CORREÇÕES — DOWNLOADER 5K+ (AGENT RUNBOOK)

**Instrução para o Agente de IA:**
Você deve executar este plano passo a passo, na ordem estrita das **7 Fases** abaixo. 
- Não pule itens. 
- Ao concluir cada fase, execute uma verificação de sintaxe antes de avançar para a próxima.
- Escopo de arquivos afetados: `backend/db.py`, `backend/downloader.py`, `backend/api.py`, `frontend/js/app.js`, `main.py`, `iniciar.bat`, `iniciar.vbs`, `requirements.txt`, `.gitignore`.

---

## FASE 1: Banco de Dados e Isolamento do OneDrive (`backend/db.py`)
**Itens resolvidos:** A8, M12, B10 e Risco Operacional (OneDrive + SQLite WAL).

### 1.1. Mover diretório de dados para fora do OneDrive (Risco OneDrive)
- **Problema:** O projeto roda dentro de `OneDrive\Documentos`, e o sincronizador corrompe arquivos `.db-wal`/`.db-shm` e `settings.json`.
- **Ação em `backend/db.py`:**
  1. Defina o diretório de dados seguro usando `%LOCALAPPDATA%`:
     ```python
     APP_DATA_DIR = Path(os.getenv("LOCALAPPDATA", Path.home())) / "Downloader5K" / "data"
     LEGACY_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
     DB_PATH = APP_DATA_DIR / "downloads.db"
     SETTINGS_PATH = APP_DATA_DIR / "settings.json"
     ```
  2. Crie uma rotina de migração automática executada uma única vez na inicialização (`init_db()`):
     - Crie `APP_DATA_DIR.mkdir(parents=True, exist_ok=True)`.
     - Se `LEGACY_DATA_DIR / "downloads.db"` ou `downloader.db` existir e `DB_PATH` não existir, copie para `APP_DATA_DIR`.

### 1.2. Fechamento correto de conexões SQLite e remoção de overhead (M12)
- **Onde:** `backend/db.py`.
- **Ação:**
  1. Implemente o contextmanager `get_db_connection()` com fechamento garantido no `finally`.
  2. Mova `PRAGMA journal_mode=WAL;` e `PRAGMA synchronous=NORMAL;` para dentro de `init_db()`.
  3. Adicione inserção em lote `create_downloads_batch(items: list[dict])`.
  4. Adicione `get_all_downloads(limit: int = 500)` com `LIMIT ?`.

### 1.3. Reconciliação de registros "zumbis" no Startup (A8)
- **Ação:** Execute `reconcile_zombie_downloads()` em `init_db()` marcando downloads interrompidos como `error`.

---

## FASE 2: Qualidade Máxima, Resoluções e Extração (`backend/downloader.py`)
**Itens resolvidos:** C1, A3, A4, B1, B4, B9.

### 2.1. Restaurar Qualidade Máxima (8K/4K/1080p) e Remover Override de Client (C1)
- **Onde:** `backend/downloader.py:316-320` e `get_base_ydl_opts()`.
- **Problema:** `player_client: ["android","ios","web_creator","mweb"]` capava os vídeos em 360p e bloqueava formatos de alta resolução.
- **Ação:** Remover o override restritivo de `player_client`, utilizando a negociação padrão moderna do yt-dlp.

### 2.2. Correção de EmbedThumbnail para Formato WebM (A3)
- **Onde:** `backend/downloader.py` na adição do pós-processador `EmbedThumbnail`.
- **Problema:** O yt-dlp lança erro com WebM pois não suporta thumbnail embutida nesse container.
- **Ação:** Só adicionar `EmbedThumbnail` se o container for suportado (`mp3`, `mkv`, `mka`, `ogg`, `opus`, `flac`, `m4a`, `mp4`, `m4v`, `mov`). Para `webm`, não adicionar o pós-processador.

### 2.3. Extração Rápida de Canais, Usuários e Playlists (`extract_flat`) (A4)
- **Onde:** `backend/downloader.py: MediaInspector.inspect`.
- **Problema:** URLs como `/@canal/videos` ou `/channel/...` faziam extração lenta de vídeo por vídeo.
- **Ação:** Tratar como playlist e usar `extract_flat = True` em qualquer link que resolva para múltiplos itens (playlists, canais, abas de vídeos).

### 2.4. Correção da Função `format_bytes` (B1)
- **Onde:** `backend/downloader.py:19-26`.
- **Ação:** Tratar valores `< 1`, negativos e índices `>= len(units)`.

### 2.5. Filtragem de Vídeos Privados/Excluídos e Live Streams (B4, B9)
- **Onde:** `backend/downloader.py: MediaInspector.inspect`.
- **Ação:** Ignorar itens que contenham títulos como `[Private video]`, `[Deleted video]` ou entradas vazias, e sinalizar/bloquear downloads infinitos de transmissões ao vivo ativas (`is_live`).

---

## FASE 3: Ciclo de Vida dos Downloads, Cancelamento e Resiliência (`backend/downloader.py`)
**Itens resolvidos:** A2, A6, M3, M4, M5, M8, M9, B7.

### 3.1. Proteção Abrangente de `_execute_download` contra Travamentos Silenciosos (A2)
- **Onde:** `backend/downloader.py: _execute_download`.
- **Ação:** Colocar `os.makedirs(dest_dir)` e configuração do yt-dlp dentro do bloco `try/except` geral, garantindo que qualquer falha atualize o status para `error` e emita notificação via WebSocket.

### 3.2. Estabilidade de Progresso e Multiplexação (M3)
- **Onde:** `backend/downloader.py: hook_progress`.
- **Ação:** Evitar que `finished` do primeiro stream (vídeo) envie `progress: 99%` falso quando o áudio ainda precisa ser baixado.

### 3.3. Caminho Real do Arquivo Baixado e Anti-Colisão (M4, M5)
- **Onde:** `backend/downloader.py`.
- **Ação:** 
  1. Utilizar `requested_downloads[0]['filepath']` ou hook `postprocessor_hooks` para obter o caminho exato do arquivo gerado pelo yt-dlp.
  2. Ajustar o template de nome para evitar que vídeos com o mesmo título colidam e sobrescrevam arquivos: `%(title).150s [%(id)s].%(ext)s`.

### 3.4. Cancelamento Confiável e Limpeza de Tarefas (A6, M8, M9, B9)
- **Onde:** `backend/downloader.py: DownloadManager`.
- **Ação:**
  1. Limpar `active_tasks` ao finalizar ou falhar tarefas (evita vazamento de memória).
  2. Verificar se a tarefa já foi cancelada antes de obter o semáforo de concorrência.
  3. No método `cancel_download` e `cancel_all_downloads`, remover arquivos temporários `.part` / `.ytdl`.
  4. No método `delete_download` e `clear_all_downloads`, cancelar downloads ativos correspondentes antes de excluir.

### 3.5. Throttle no Envio de Progresso via WebSocket (B7)
- **Onde:** `backend/downloader.py: hook_progress`.
- **Ação:** Limitar os disparos de broadcast a no máximo 1 envio a cada 250ms por tarefa, salvo em status de término ou erro.

---

## FASE 4: Segurança, API e Gerenciamento de Processos (`backend/api.py`, `main.py`)
**Itens resolvidos:** C2, C3, C4, A1, M10, M11, M14, B8.

### 4.1. Correção do Auto-Encerramento e Prevenção de Queda no F5 (C2, A1)
- **Onde:** `backend/api.py: ConnectionManager`.
- **Ação:**
  1. Remover timer de shutdown duplicado.
  2. Nunca agendar ou executar encerramento se houver downloads em status `downloading` ou `processing`.
  3. Na rota `/api/shutdown`, checar se ainda há conexões ativas antes de agendar o encerramento.

### 4.2. Segurança e Restrição de CORS (C3)
- **Onde:** `backend/api.py`.
- **Ação:** Restringir CORS apenas a origens locais (`http://127.0.0.1:8000`, `http://localhost:8000`).

### 4.3. Validação Estrita de Caminho e Formatos (C4)
- **Onde:** `backend/api.py`.
- **Ação:** Validar `dest_dir` garantindo que seja um caminho válido e seguro; aplicar whitelist para `resolution`, `container` e `audio_format`.

### 4.4. Isolamento do Seletor de Pasta do Modal (M10)
- **Onde:** `backend/api.py`.
- **Ação:** Permitir que o endpoint de seleção de pasta receba um parâmetro indicando se deve ou não salvar como padrão global (`save_as_default=False`).

### 4.5. Operações Pesadas Fora do Event Loop (M11) e Diálogo Tkinter Seguro (B8)
- **Onde:** `backend/api.py`.
- **Ação:** Executar `subprocess.run(explorer)` e consultas pesadas via `asyncio.to_thread`; sincronizar chamadas do seletor Tkinter com trava para impedir abertura múltipla simultânea.

### 4.6. Finalização Segura de Porta em `main.py` (M14)
- **Onde:** `main.py: kill_stale_process_on_port`.
- **Ação:** Refinar o regex/filtro do `netstat` para casar exatamente a porta `:8000\s` e verificar se a linha está no estado `LISTENING`.

---

## FASE 5: Classificador Musical, Metadados e Legendas (`backend/downloader.py`)
**Itens resolvidos:** M1, M2, M6, M7.

### 5.1. Refinamento de Gêneros e Correção de Regex (M1, M2)
- **Onde:** `backend/downloader.py: GenreClassifier`.
- **Ação:**
  1. Corrigir termos com símbolos como `ira!` e `bk'` ajustando o regex para que não falhe com `\b`.
  2. Priorizar correspondência no nome do artista / canal e título; dar peso menor ou desconsiderar palavras genéricas na descrição.

### 5.2. Respeito às Opções de Legendas e Capas (M6, M7)
- **Onde:** `backend/downloader.py`.
- **Ação:** Aplicar `embed_subtitles`, `subtitles_langs` e `embed_cover` estritamente conforme enviado pelo cliente ou configurado no settings.

---

## FASE 6: Frontend, XSS e Sincronização (`frontend/js/app.js`, `frontend/index.html`)
**Itens resolvidos:** A5, A7, M13, B2, B3, B5.

### 6.1. Sanitização Contra XSS em Todo o Histórico (A5)
- **Onde:** `frontend/js/app.js`.
- **Ação:** Escapar `title`, `author`, `thumbnail` e `format_note` em todos os templates de renderização (`renderHistory`, `createActiveCard`, modais).

### 6.2. Sincronização de Downloads Ativos Após F5 (A7)
- **Onde:** `frontend/js/app.js`.
- **Ação:** Ao inicializar ou reconectar o WebSocket, consultar o backend por tarefas ativas e recriar os cards visuais na área "Downloads Ativos".

### 6.3. Otimização de `loadHistory` (M13)
- **Onde:** `frontend/js/app.js`.
- **Ação:** Debounce nas chamadas de `loadHistory` para evitar recargas excessivas da lista durante múltiplos eventos.

### 6.4. Formatação de Rótulos, Fusos e Duplicatas (B2, B3, B5)
- **Onde:** `frontend/js/app.js`.
- **Ação:** Tratar qualidade de áudio `"0"` para `"Melhor"`, corrigir timezone da data UTC e normalizar acentuação na remoção de duplicados.

---

## FASE 7: Ambiente, Scripts de Inicialização e Dependências
**Itens resolvidos:** B10, Riscos de Operação.

### 7.1. Atualização do `requirements.txt` e `.gitignore`
- **Ação:** Adicionar dependências recomendadas do yt-dlp (`yt-dlp[default]`) e garantir codificação UTF-8 correta no `.gitignore`.

### 7.2. Ajuste nos Scripts `iniciar.bat` e `iniciar.vbs`
- **Ação:** Adicionar log de erros na inicialização e verificação de saúde do ambiente virtual.
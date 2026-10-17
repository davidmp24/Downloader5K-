// Downloader 5K+ - Aplicação Frontend e WebSocket Engine

class DownloaderApp {
    constructor() {
        this.activeDownloads = new Map();
        this.history = [];
        this.settings = {};
        this.currentInspectedMedia = null;
        this.selectedResolution = null;
        this.selectedAudio = null;
        this.activeFilter = 'all';
        this.searchQuery = '';
        this.currentPlaylist = null;
        this.selectedPlaylistEntries = new Set();
        this.playlistTab = 'video';
        this.historyDisplayLimit = 30;
        this.activeDisplayLimit = 30;
        this.duplicateEntriesIndices = new Set();
        this.ws = null;
        this.wsReconnectTimer = null;

        this.initElements();
        this.initEvents();
        this.loadSettings();
        this.loadHistory();
        this.initWebSocket();
    }

    initElements() {
        // Inputs & Botões Principais
        this.inputUrl = document.getElementById('inputUrl');
        this.btnClearInput = document.getElementById('btnClearInput');
        this.btnPaste = document.getElementById('btnPasteClipboard');
        this.btnAnalyze = document.getElementById('btnAnalyze');
        this.analyzeSpinner = document.getElementById('analyzeSpinner');

        // Smart Mode
        this.smartModePill = document.getElementById('smartModePill');
        this.smartModeText = document.getElementById('smartModeText');

        // Modais
        this.inspectorModal = document.getElementById('inspectorModal');
        this.btnCloseInspectorModal = document.getElementById('btnCloseInspectorModal');
        this.btnCancelInspector = document.getElementById('btnCancelInspector');
        this.btnConfirmDownload = document.getElementById('btnConfirmDownload');

        this.settingsModal = document.getElementById('settingsModal');
        this.btnOpenSettings = document.getElementById('btnOpenSettings');
        this.btnCloseSettingsModal = document.getElementById('btnCloseSettingsModal');
        this.btnCancelSettings = document.getElementById('btnCancelSettings');
        this.btnSaveSettings = document.getElementById('btnSaveSettings');
        this.btnChooseFolder = document.getElementById('btnChooseFolder');

        // Campos do Modal Inspector
        this.modalMediaThumb = document.getElementById('modalMediaThumb');
        this.modalMediaDuration = document.getElementById('modalMediaDuration');
        this.modalMediaTitle = document.getElementById('modalMediaTitle');
        this.modalMediaAuthor = document.getElementById('modalMediaAuthor');
        this.modalMediaViews = document.getElementById('modalMediaViews');
        this.modalResolutionsList = document.getElementById('modalResolutionsList');
        this.modalAudioList = document.getElementById('modalAudioList');
        this.selectContainer = document.getElementById('selectContainer');
        this.checkEmbedSubs = document.getElementById('checkEmbedSubs');
        this.checkEmbedCover = document.getElementById('checkEmbedCover');
        this.tabBtnVideo = document.getElementById('tabBtnVideo');
        this.tabBtnAudio = document.getElementById('tabBtnAudio');
        this.tabVideo = document.getElementById('tabVideo');
        this.tabAudio = document.getElementById('tabAudio');

        // Campos do Modal Playlist
        this.playlistModal = document.getElementById('playlistModal');
        this.btnClosePlaylistModal = document.getElementById('btnClosePlaylistModal');
        this.btnCancelPlaylist = document.getElementById('btnCancelPlaylist');
        this.btnConfirmPlaylistDownload = document.getElementById('btnConfirmPlaylistDownload');
        this.btnConfirmPlaylistText = document.getElementById('btnConfirmPlaylistText');
        this.playlistTotalCountBadge = document.getElementById('playlistTotalCountBadge');
        this.playlistThumb = document.getElementById('playlistThumb');
        this.playlistTitle = document.getElementById('playlistTitle');
        this.playlistAuthor = document.getElementById('playlistAuthor');
        this.playlistItemsList = document.getElementById('playlistItemsList');
        this.btnSelectAllPlaylist = document.getElementById('btnSelectAllPlaylist');
        this.btnDeselectAllPlaylist = document.getElementById('btnDeselectAllPlaylist');
        this.playlistSelectedCount = document.getElementById('playlistSelectedCount');
        this.playlistTotalCount = document.getElementById('playlistTotalCount');
        this.tabBtnPlaylistVideo = document.getElementById('tabBtnPlaylistVideo');
        this.tabBtnPlaylistAudio = document.getElementById('tabBtnPlaylistAudio');
        this.playlistVideoOptions = document.getElementById('playlistVideoOptions');
        this.playlistAudioOptions = document.getElementById('playlistAudioOptions');
        this.selectPlaylistQuality = document.getElementById('selectPlaylistQuality');
        this.selectPlaylistContainer = document.getElementById('selectPlaylistContainer');
        this.selectPlaylistAudioFormat = document.getElementById('selectPlaylistAudioFormat');
        this.selectPlaylistAudioBitrate = document.getElementById('selectPlaylistAudioBitrate');

        // Campos do Modal Settings
        this.settingSmartModeToggle = document.getElementById('settingSmartModeToggle');
        this.settingDownloadDir = document.getElementById('settingDownloadDir');
        this.settingOrganizeGenre = document.getElementById('settingOrganizeGenre');
        this.settingDefaultType = document.getElementById('settingDefaultType');
        this.settingDefaultQuality = document.getElementById('settingDefaultQuality');
        this.settingDefaultAudioFormat = document.getElementById('settingDefaultAudioFormat');
        this.settingDefaultAudioBitrate = document.getElementById('settingDefaultAudioBitrate');
        this.settingEmbedSubs = document.getElementById('settingEmbedSubs');
        this.settingBrowserCookies = document.getElementById('settingBrowserCookies');

        // Campos de Pasta e Gênero nos Modais
        this.inspectorDownloadDir = document.getElementById('inspectorDownloadDir');
        this.btnChooseInspectorFolder = document.getElementById('btnChooseInspectorFolder');
        this.checkInspectorOrganizeGenre = document.getElementById('checkInspectorOrganizeGenre');

        this.playlistDownloadDir = document.getElementById('playlistDownloadDir');
        this.btnChoosePlaylistFolder = document.getElementById('btnChoosePlaylistFolder');
        this.checkPlaylistOrganizeGenre = document.getElementById('checkPlaylistOrganizeGenre');
        this.playlistDuplicatesNotice = document.getElementById('playlistDuplicatesNotice');

        // Listas e Contadores
        this.activeDownloadsList = document.getElementById('activeDownloadsList');
        this.emptyActiveState = document.getElementById('emptyActiveState');
        this.activeCounter = document.getElementById('activeCounter');
        this.btnCancelAllDownloads = document.getElementById('btnCancelAllDownloads');

        this.historyList = document.getElementById('historyList');
        this.emptyHistoryState = document.getElementById('emptyHistoryState');
        this.historyCounter = document.getElementById('historyCounter');
        this.btnClearHistory = document.getElementById('btnClearHistory');
        this.filterTabs = document.getElementById('filterTabs');
        this.inputSearchHistory = document.getElementById('inputSearchHistory');

        this.toastContainer = document.getElementById('toastContainer');
    }

    initEvents() {
        // Digitação no input
        this.inputUrl.addEventListener('input', () => {
            this.btnClearInput.classList.toggle('hidden', !this.inputUrl.value.trim());
        });

        this.btnClearInput.addEventListener('click', () => {
            this.inputUrl.value = '';
            this.btnClearInput.classList.add('hidden');
            this.inputUrl.focus();
        });

        this.inputUrl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                this.handleAnalyze();
            }
        });

        // Colar da área de transferência com 1 clique
        this.btnPaste.addEventListener('click', async () => {
            try {
                const text = await navigator.clipboard.readText();
                if (text && (text.includes('youtube.com') || text.includes('youtu.be'))) {
                    this.inputUrl.value = text.trim();
                    this.btnClearInput.classList.remove('hidden');
                    this.showToast('Link colado da área de transferência!', 'info');
                    this.handleAnalyze();
                } else if (text) {
                    this.inputUrl.value = text.trim();
                    this.btnClearInput.classList.remove('hidden');
                    this.handleAnalyze();
                } else {
                    this.showToast('A área de transferência está vazia.', 'warning');
                }
            } catch (err) {
                this.inputUrl.focus();
                this.showToast('Permissão de leitura negada. Cole manualmente com Ctrl+V.', 'warning');
            }
        });

        // Botão Analisar
        this.btnAnalyze.addEventListener('click', () => this.handleAnalyze());

        // Smart Mode Pill no Header
        this.smartModePill.addEventListener('click', () => {
            const newState = !this.settings.smart_mode;
            this.saveSettingsPatch({ smart_mode: newState });
        });

        // Abas do Modal Inspector
        this.tabBtnVideo.addEventListener('click', () => this.switchInspectorTab('video'));
        this.tabBtnAudio.addEventListener('click', () => this.switchInspectorTab('audio'));

        // Fechar Modais
        this.btnCloseInspectorModal.addEventListener('click', () => this.closeInspectorModal());
        this.btnCancelInspector.addEventListener('click', () => this.closeInspectorModal());
        this.inspectorModal.addEventListener('click', (e) => {
            if (e.target === this.inspectorModal) this.closeInspectorModal();
        });
        this.btnConfirmDownload.addEventListener('click', () => this.confirmDownload());

        // Eventos do Modal Playlist
        this.btnClosePlaylistModal.addEventListener('click', () => this.closePlaylistModal());
        this.btnCancelPlaylist.addEventListener('click', () => this.closePlaylistModal());
        this.playlistModal.addEventListener('click', (e) => {
            if (e.target === this.playlistModal) this.closePlaylistModal();
        });
        this.btnSelectAllPlaylist.addEventListener('click', () => this.selectAllPlaylist(true));
        this.btnDeselectAllPlaylist.addEventListener('click', () => this.selectAllPlaylist(false));
        this.tabBtnPlaylistVideo.addEventListener('click', () => this.switchPlaylistTab('video'));
        this.tabBtnPlaylistAudio.addEventListener('click', () => this.switchPlaylistTab('audio'));
        this.btnConfirmPlaylistDownload.addEventListener('click', () => this.confirmPlaylistDownload());

        this.btnOpenSettings.addEventListener('click', () => this.openSettingsModal());
        this.btnCloseSettingsModal.addEventListener('click', () => this.closeSettingsModal());
        this.btnCancelSettings.addEventListener('click', () => this.closeSettingsModal());
        this.settingsModal.addEventListener('click', (e) => {
            if (e.target === this.settingsModal) this.closeSettingsModal();
        });
        this.btnSaveSettings.addEventListener('click', () => this.saveSettingsFromModal());

        // Botão Procurar Pasta (Nativo do Windows)
        this.btnChooseFolder.addEventListener('click', () => this.chooseDownloadFolder());

        // Botões de Seleção de Pasta nos Modais de Análise
        if (this.btnChooseInspectorFolder) {
            this.btnChooseInspectorFolder.addEventListener('click', () => this.chooseFolderForModal('inspector'));
        }
        if (this.btnChoosePlaylistFolder) {
            this.btnChoosePlaylistFolder.addEventListener('click', () => this.chooseFolderForModal('playlist'));
        }

        // Filtros do Histórico
        this.filterTabs.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.filterTabs.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.activeFilter = btn.dataset.filter;
                this.renderHistory();
            });
        });

        // Busca no Histórico
        this.inputSearchHistory.addEventListener('input', (e) => {
            this.searchQuery = e.target.value.toLowerCase().trim();
            this.renderHistory();
        });

        // Botão Limpar Histórico / Biblioteca
        if (this.btnClearHistory) {
            this.btnClearHistory.addEventListener('click', () => this.clearHistory());
        }

        // Botão Cancelar Todos os Downloads Ativos
        if (this.btnCancelAllDownloads) {
            this.btnCancelAllDownloads.addEventListener('click', () => this.cancelAllDownloads());
        }

        // Notificação de encerramento do backend ao fechar ou descarregar a aba do navegador
        window.addEventListener('beforeunload', () => {
            try {
                navigator.sendBeacon('/api/shutdown');
            } catch (e) {
                // Silencioso se não suportado
            }
        });
    }

    // ==========================================
    // Conexão WebSocket em Tempo Real
    // ==========================================
    initWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host || 'localhost:8000';
        const wsUrl = `${protocol}//${host}/ws`;

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                console.log('WebSocket conectado com sucesso.');
                if (this.wsReconnectTimer) {
                    clearInterval(this.wsReconnectTimer);
                    this.wsReconnectTimer = null;
                }
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'progress') {
                        this.handleProgressUpdate(data);
                    }
                } catch (e) {
                    console.error('Erro ao ler mensagem WebSocket:', e);
                }
            };

            this.ws.onclose = () => {
                console.warn('WebSocket desconectado. Tentando reconectar...');
                if (!this.wsReconnectTimer) {
                    this.wsReconnectTimer = setInterval(() => this.initWebSocket(), 3000);
                }
            };

            this.ws.onerror = (err) => {
                console.error('Erro no WebSocket:', err);
            };
        } catch (e) {
            console.error('Falha ao instanciar WebSocket:', e);
        }
    }

    handleProgressUpdate(update) {
        const { id, status, progress, speed, eta, file_size, file_size_formatted, error_message } = update;
        const task = this.activeDownloads.get(id);

        if (status === 'completed') {
            this.showToast(`Download concluído: "${task?.title || 'Arquivo'}"!`, 'success');
            this.activeDownloads.delete(id);
            this.renderActiveDownloads();
            this.loadHistory(); // Atualiza histórico
            return;
        }

        if (status === 'cancelled') {
            this.showToast(`Download cancelado.`, 'warning');
            this.activeDownloads.delete(id);
            this.renderActiveDownloads();
            this.loadHistory();
            return;
        }

        if (status === 'error') {
            this.showToast(`Erro no download: ${error_message || 'Falha de rede/FFmpeg.'}`, 'error');
            this.activeDownloads.delete(id);
            this.renderActiveDownloads();
            this.loadHistory();
            return;
        }

        if (task) {
            task.progress = progress;
            task.speed = speed;
            task.eta = eta;
            task.status = status;
            task.file_size = file_size;
            task.file_size_formatted = file_size_formatted;
            this.updateActiveCardUI(task);
        }
    }

    // ==========================================
    // Configurações & Smart Mode
    // ==========================================
    async loadSettings() {
        try {
            const res = await fetch('/api/settings');
            this.settings = await res.json();
            this.updateSmartModeUI();
        } catch (e) {
            console.error('Erro ao carregar configurações:', e);
        }
    }

    updateSmartModeUI() {
        const isSmart = !!this.settings.smart_mode;
        this.smartModePill.classList.toggle('active', isSmart);
        if (isSmart) {
            const mode = this.settings.default_type === 'audio' 
                ? `MP3 ${this.settings.default_audio_bitrate}k` 
                : `${this.settings.default_quality}p ${this.settings.default_video_format.toUpperCase()}`;
            this.smartModeText.textContent = `Smart Mode: Ligado (${mode})`;
        } else {
            this.smartModeText.textContent = 'Smart Mode: Desativado';
        }
    }

    async saveSettingsPatch(patch) {
        try {
            const res = await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(patch)
            });
            this.settings = await res.json();
            this.updateSmartModeUI();
            this.showToast('Configurações atualizadas.', 'info');
        } catch (e) {
            this.showToast('Erro ao atualizar configurações.', 'error');
        }
    }

    openSettingsModal() {
        this.settingSmartModeToggle.checked = !!this.settings.smart_mode;
        this.settingDownloadDir.value = this.settings.download_dir || '';
        if (this.settingOrganizeGenre) {
            this.settingOrganizeGenre.checked = (this.settings.organize_by_genre !== false);
        }
        this.settingDefaultType.value = this.settings.default_type || 'video';
        this.settingDefaultQuality.value = this.settings.default_quality || '1080';
        this.settingDefaultAudioFormat.value = this.settings.default_audio_format || 'mp3';
        this.settingDefaultAudioBitrate.value = this.settings.default_audio_bitrate || '320';
        this.settingEmbedSubs.checked = !!this.settings.embed_subtitles;
        if (this.settingBrowserCookies) {
            this.settingBrowserCookies.value = this.settings.browser_cookies || 'none';
        }

        this.settingsModal.classList.remove('hidden');
    }

    closeSettingsModal() {
        this.settingsModal.classList.add('hidden');
    }

    async chooseDownloadFolder() {
        this.showToast('Selecione a pasta na janela do Windows...', 'info');
        try {
            const res = await fetch('/api/select-folder', { method: 'POST' });
            const data = await res.json();
            if (data.selected && data.download_dir) {
                this.settingDownloadDir.value = data.download_dir;
                this.settings.download_dir = data.download_dir;
                if (this.inspectorDownloadDir) this.inspectorDownloadDir.value = data.download_dir;
                if (this.playlistDownloadDir) this.playlistDownloadDir.value = data.download_dir;
                this.showToast(`Pasta de download alterada para: ${data.download_dir}`, 'success');
            }
        } catch (e) {
            this.showToast('Erro ao abrir seletor de pasta.', 'error');
        }
    }

    async chooseFolderForModal(target) {
        this.showToast('Selecione a pasta na janela do Windows...', 'info');
        try {
            const res = await fetch('/api/select-folder', { method: 'POST' });
            const data = await res.json();
            if (data.selected && data.download_dir) {
                if (target === 'inspector' && this.inspectorDownloadDir) {
                    this.inspectorDownloadDir.value = data.download_dir;
                } else if (target === 'playlist' && this.playlistDownloadDir) {
                    this.playlistDownloadDir.value = data.download_dir;
                }
                this.settings.download_dir = data.download_dir;
                if (this.settingDownloadDir) this.settingDownloadDir.value = data.download_dir;
                this.showToast(`Pasta de destino definida: ${data.download_dir}`, 'success');
            }
        } catch (e) {
            this.showToast('Erro ao selecionar pasta.', 'error');
        }
    }

    async saveSettingsFromModal() {
        const payload = {
            smart_mode: this.settingSmartModeToggle.checked,
            download_dir: this.settingDownloadDir.value,
            organize_by_genre: this.settingOrganizeGenre ? this.settingOrganizeGenre.checked : true,
            default_type: this.settingDefaultType.value,
            default_quality: this.settingDefaultQuality.value,
            default_audio_format: this.settingDefaultAudioFormat.value,
            default_audio_bitrate: this.settingDefaultAudioBitrate.value,
            embed_subtitles: this.settingEmbedSubs.checked,
            browser_cookies: this.settingBrowserCookies ? this.settingBrowserCookies.value : 'none'
        };
        await this.saveSettingsPatch(payload);
        this.closeSettingsModal();
    }

    // ==========================================
    // Análise e Inspeção de Link
    // ==========================================
    async handleAnalyze() {
        const url = this.inputUrl.value.trim();
        if (!url) {
            this.showToast('Insira uma URL do YouTube para analisar.', 'warning');
            return;
        }

        // Se o link for de uma playlist, sempre inspeciona para exibir a seleção dos vídeos!
        const isLikelyPlaylist = url.includes('list=') || url.includes('/playlist');

        // Se Smart Mode estiver ativo e NÃO for playlist, dispara direto em 1 clique!
        if (this.settings.smart_mode && !isLikelyPlaylist) {
            this.executeSmartDownload(url);
            return;
        }

        // Modo manual ou Playlist: Inspeciona formatos
        this.btnAnalyze.disabled = true;
        this.analyzeSpinner.classList.remove('hidden');

        try {
            const res = await fetch('/api/inspect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Falha ao inspecionar link.');
            }

            const data = await res.json();
            if (data.is_playlist) {
                this.openPlaylistModal(data);
            } else {
                this.openInspectorModal(data);
            }
        } catch (err) {
            this.showToast(err.message, 'error');
        } finally {
            this.btnAnalyze.disabled = false;
            this.analyzeSpinner.classList.add('hidden');
        }
    }

    async executeSmartDownload(url) {
        this.btnAnalyze.disabled = true;
        this.analyzeSpinner.classList.remove('hidden');
        this.showToast('Smart Mode: Analisando link...', 'info');

        try {
            const res = await fetch('/api/download/smart', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Falha ao processar link no Smart Mode.');
            }

            const data = await res.json();
            if (data.is_playlist && data.info) {
                this.openPlaylistModal(data.info);
                return;
            }

            this.inputUrl.value = '';
            this.btnClearInput.classList.add('hidden');
            this.showToast(`Download de "${data.title}" iniciado!`, 'success');
            
            // Adiciona aos ativos
            this.activeDownloads.set(data.task_id, {
                id: data.task_id,
                title: data.title,
                status: 'downloading',
                progress: 0,
                speed: 'Iniciando...',
                eta: '--:--',
                type: this.settings.default_type,
                format_note: this.settings.default_type === 'audio' 
                    ? `MP3 (${this.settings.default_audio_bitrate}k)` 
                    : `${this.settings.default_quality}p (${this.settings.default_video_format.toUpperCase()})`
            });
            this.renderActiveDownloads();
        } catch (err) {
            this.showToast(err.message, 'error');
        } finally {
            this.btnAnalyze.disabled = false;
            this.analyzeSpinner.classList.add('hidden');
        }
    }

    openInspectorModal(data) {
        this.currentInspectedMedia = data;

        this.modalMediaThumb.src = data.thumbnail || '';
        this.modalMediaDuration.textContent = data.duration_formatted || '--:--';
        this.modalMediaTitle.textContent = data.title || 'Vídeo sem título';
        this.modalMediaAuthor.textContent = data.uploader || 'YouTube';
        this.modalMediaViews.textContent = data.view_count 
            ? `${data.view_count.toLocaleString('pt-BR')} visualizações` 
            : '';

        // Renderiza opções de resolução
        this.modalResolutionsList.innerHTML = '';
        const resolutions = data.video_resolutions || [];

        if (resolutions.length > 0) {
            resolutions.forEach((res, index) => {
                const card = document.createElement('div');
                card.className = `format-option-card ${index === 0 ? 'selected' : ''}`;
                if (index === 0) this.selectedResolution = res;

                card.innerHTML = `
                    <div class="format-card-title">${res.label}</div>
                    <div class="format-card-meta">
                        <span>${res.vcodec ? res.vcodec.split('.')[0] : 'Vídeo'}</span>
                        <span>${res.filesize_formatted}</span>
                    </div>
                `;

                card.addEventListener('click', () => {
                    this.modalResolutionsList.querySelectorAll('.format-option-card').forEach(c => c.classList.remove('selected'));
                    card.classList.add('selected');
                    this.selectedResolution = res;
                });

                this.modalResolutionsList.appendChild(card);
            });
        } else {
            this.modalResolutionsList.innerHTML = '<p class="text-muted">Resoluções padrão serão multiplexadas pelo FFmpeg.</p>';
        }

        // Renderiza opções de áudio
        this.modalAudioList.innerHTML = '';
        const audios = data.audio_options || [];
        audios.forEach((aud, index) => {
            const card = document.createElement('div');
            card.className = `format-option-card ${index === 0 ? 'selected' : ''}`;
            if (index === 0) this.selectedAudio = aud;

            card.innerHTML = `
                <div class="format-card-title">${aud.label}</div>
                <div class="format-card-meta">
                    <span>${aud.format.toUpperCase()}</span>
                    <span>${aud.lossless ? 'Sem perdas' : aud.quality + ' kbps'}</span>
                </div>
            `;

            card.addEventListener('click', () => {
                this.modalAudioList.querySelectorAll('.format-option-card').forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
                this.selectedAudio = aud;
            });

            this.modalAudioList.appendChild(card);
        });

        // Atualiza campos de pasta e organização de gênero
        if (this.inspectorDownloadDir) {
            this.inspectorDownloadDir.value = this.settings.download_dir || '';
        }
        if (this.checkInspectorOrganizeGenre) {
            this.checkInspectorOrganizeGenre.checked = (this.settings.organize_by_genre !== false);
        }

        // Configuração inicial de aba
        this.switchInspectorTab('video');
        this.inspectorModal.classList.remove('hidden');
    }

    switchInspectorTab(tab) {
        if (tab === 'video') {
            this.tabBtnVideo.classList.add('active');
            this.tabBtnAudio.classList.remove('active');
            this.tabVideo.classList.add('active');
            this.tabAudio.classList.remove('active');
            this.selectedTab = 'video';
        } else {
            this.tabBtnAudio.classList.add('active');
            this.tabBtnVideo.classList.remove('active');
            this.tabAudio.classList.add('active');
            this.tabVideo.classList.remove('active');
            this.selectedTab = 'audio';
        }
    }

    closeInspectorModal() {
        this.inspectorModal.classList.add('hidden');
        this.currentInspectedMedia = null;
    }

    // ==========================================
    // Modal e Seleção de Playlist com Detecção de Duplicatas
    // ==========================================
    escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    normalizeTitle(title) {
        if (!title) return '';
        return title
            .toLowerCase()
            .replace(/[\(\)\[\]\{\}\-_,.:;!?|/\\~`"'^]/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
    }

    openPlaylistModal(playlistData) {
        this.currentPlaylist = playlistData;
        const entries = playlistData.entries || [];

        this.playlistTitle.textContent = playlistData.title || 'Playlist do YouTube';
        this.playlistAuthor.textContent = playlistData.uploader || 'YouTube';
        this.playlistTotalCountBadge.textContent = `${entries.length} vídeos`;
        this.playlistTotalCount.textContent = entries.length;
        this.playlistThumb.src = playlistData.thumbnail || 'https://placehold.co/140x80/141824/64748b?text=Playlist';

        // Atualiza campos de pasta e organização por gênero no modal de playlist
        if (this.playlistDownloadDir) {
            this.playlistDownloadDir.value = this.settings.download_dir || '';
        }
        if (this.checkPlaylistOrganizeGenre) {
            this.checkPlaylistOrganizeGenre.checked = (this.settings.organize_by_genre !== false);
        }

        // Lógica de Detecção Inteligente de Vídeos Duplicados
        const seenTitles = new Map();
        const seenIds = new Set();
        let duplicateCount = 0;
        this.duplicateEntriesIndices = new Set();
        this.selectedPlaylistEntries = new Set();

        this.playlistItemsList.innerHTML = '';
        this.playlistItemsList.scrollTop = 0;
        entries.forEach((entry, idx) => {
            const rawTitle = entry.title || `Vídeo #${idx + 1}`;
            const safeTitle = this.escapeHtml(rawTitle);
            const normTitle = this.normalizeTitle(rawTitle);
            let isDuplicate = false;
            let duplicateReason = '';

            if (entry.id && seenIds.has(entry.id)) {
                isDuplicate = true;
                duplicateReason = 'mesmo ID';
            } else if (normTitle && seenTitles.has(normTitle)) {
                isDuplicate = true;
                const firstIdx = seenTitles.get(normTitle);
                duplicateReason = `mesmo título que #${firstIdx + 1}`;
            } else {
                if (normTitle) seenTitles.set(normTitle, idx);
                if (entry.id) seenIds.add(entry.id);
            }

            if (isDuplicate) {
                duplicateCount++;
                this.duplicateEntriesIndices.add(idx);
                // Permanece DESMARCADO automaticamente!
            } else {
                // Vídeos únicos são selecionados por padrão
                this.selectedPlaylistEntries.add(idx);
            }

            const card = document.createElement('div');
            card.className = `playlist-item-card ${isDuplicate ? 'is-duplicate' : 'selected'}`;
            card.id = `pl-item-${idx}`;

            card.innerHTML = `
                <input type="checkbox" class="playlist-item-check" data-index="${idx}" ${isDuplicate ? '' : 'checked'} />
                <span class="playlist-item-index">#${entry.index || (idx + 1)}</span>
                <div class="playlist-item-thumb">
                    <img src="${entry.thumbnail || 'https://placehold.co/70x40/141824/64748b?text=Thumb'}" alt="Thumb" onerror="this.src='https://placehold.co/70x40/141824/64748b?text=Thumb'"/>
                </div>
                <div class="playlist-item-info">
                    <h5 class="playlist-item-title" title="${safeTitle}">
                        ${safeTitle}
                        ${isDuplicate ? `<span class="duplicate-tag" title="Vídeo duplicado (${duplicateReason}) desmarcado automaticamente para evitar repetição">⚠️ Duplicado (Desmarcado)</span>` : ''}
                    </h5>
                </div>
                <span class="playlist-item-duration">${entry.duration_formatted || '--:--'}</span>
            `;

            const checkbox = card.querySelector('.playlist-item-check');
            checkbox.addEventListener('change', (e) => {
                e.stopPropagation();
                this.togglePlaylistEntry(idx, checkbox.checked);
            });

            card.addEventListener('click', (e) => {
                if (e.target !== checkbox) {
                    checkbox.checked = !checkbox.checked;
                    this.togglePlaylistEntry(idx, checkbox.checked);
                }
            });

            this.playlistItemsList.appendChild(card);
        });

        // Exibe aviso na barra de ferramentas se houver duplicatas desmarcadas
        if (this.playlistDuplicatesNotice) {
            if (duplicateCount > 0) {
                this.playlistDuplicatesNotice.textContent = `⚠️ ${duplicateCount} duplicado(s) desmarcado(s)`;
                this.playlistDuplicatesNotice.classList.remove('hidden');
                this.showToast(`${duplicateCount} vídeo(s) com o mesmo nome foram desmarcados automaticamente.`, 'info');
            } else {
                this.playlistDuplicatesNotice.classList.add('hidden');
            }
        }

        this.updatePlaylistCounter();
        this.switchPlaylistTab('video');
        this.playlistModal.classList.remove('hidden');
    }

    closePlaylistModal() {
        this.playlistModal.classList.add('hidden');
        this.currentPlaylist = null;
    }

    togglePlaylistEntry(index, isChecked) {
        if (isChecked) {
            this.selectedPlaylistEntries.add(index);
        } else {
            this.selectedPlaylistEntries.delete(index);
        }

        const card = document.getElementById(`pl-item-${index}`);
        if (card) card.classList.toggle('selected', isChecked);

        this.updatePlaylistCounter();
    }

    selectAllPlaylist(selectAll) {
        if (!this.currentPlaylist) return;
        const entries = this.currentPlaylist.entries || [];

        if (selectAll) {
            // Seleciona todos os vídeos únicos (evitando selecionar duplicatas novamente)
            this.selectedPlaylistEntries = new Set(
                entries.map((_, i) => i).filter(i => !this.duplicateEntriesIndices.has(i))
            );
        } else {
            this.selectedPlaylistEntries.clear();
        }

        this.playlistItemsList.querySelectorAll('.playlist-item-card').forEach((card, idx) => {
            const isDup = this.duplicateEntriesIndices.has(idx);
            const shouldCheck = selectAll ? !isDup : false;
            card.classList.toggle('selected', shouldCheck);
            const cb = card.querySelector('.playlist-item-check');
            if (cb) cb.checked = shouldCheck;
        });

        this.updatePlaylistCounter();
    }

    updatePlaylistCounter() {
        const count = this.selectedPlaylistEntries.size;
        this.playlistSelectedCount.textContent = count;
        this.btnConfirmPlaylistText.textContent = `Baixar Selecionados (${count})`;
        this.btnConfirmPlaylistDownload.disabled = (count === 0);
    }

    switchPlaylistTab(tab) {
        this.playlistTab = tab;
        this.tabBtnPlaylistVideo.classList.toggle('active', tab === 'video');
        this.tabBtnPlaylistAudio.classList.toggle('active', tab === 'audio');
        this.playlistVideoOptions.classList.toggle('hidden', tab !== 'video');
        this.playlistAudioOptions.classList.toggle('hidden', tab !== 'audio');
    }

    async confirmPlaylistDownload() {
        if (!this.currentPlaylist || this.selectedPlaylistEntries.size === 0) return;

        const allEntries = this.currentPlaylist.entries || [];
        const selectedEntries = allEntries.filter((_, idx) => this.selectedPlaylistEntries.has(idx));

        let downloadType = this.playlistTab;
        let formatNote = '';

        const destDir = (this.playlistDownloadDir && this.playlistDownloadDir.value.trim())
            ? this.playlistDownloadDir.value.trim()
            : (this.settings.download_dir || '');
        const organizeGenre = this.checkPlaylistOrganizeGenre
            ? this.checkPlaylistOrganizeGenre.checked
            : (this.settings.organize_by_genre !== false);

        let options = {
            dest_dir: destDir,
            organize_by_genre: organizeGenre
        };

        if (downloadType === 'video') {
            const quality = this.selectPlaylistQuality.value;
            const container = this.selectPlaylistContainer.value;
            formatNote = `${quality}p (${container.toUpperCase()})`;
            options.resolution = quality;
            options.container = container;
        } else {
            const audioFmt = this.selectPlaylistAudioFormat.value;
            const audioBitrate = this.selectPlaylistAudioBitrate.value;
            formatNote = `${audioFmt.toUpperCase()} (${audioBitrate}k)`;
            options.audio_format = audioFmt;
            options.audio_quality = audioBitrate;
        }

        this.btnConfirmPlaylistDownload.disabled = true;

        try {
            const res = await fetch('/api/download/batch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    items: selectedEntries,
                    download_type: downloadType,
                    format_note: formatNote,
                    options: options
                })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Falha ao iniciar download da playlist.');
            }

            const data = await res.json();
            this.closePlaylistModal();
            this.inputUrl.value = '';
            this.btnClearInput.classList.add('hidden');
            this.showToast(`${data.count} vídeos adicionados à fila de download!`, 'success');

            if (data.tasks) {
                data.tasks.forEach(t => {
                    this.activeDownloads.set(t.task_id, {
                        id: t.task_id,
                        title: t.title,
                        author: t.author,
                        thumbnail: t.thumbnail,
                        type: t.download_type,
                        format_note: t.format_note,
                        status: 'downloading',
                        progress: 0,
                        speed: 'Na fila...',
                        eta: '--:--'
                    });
                });
                this.renderActiveDownloads();
            }
        } catch (err) {
            this.showToast(err.message, 'error');
        } finally {
            this.btnConfirmPlaylistDownload.disabled = false;
        }
    }

    async confirmDownload() {
        if (!this.currentInspectedMedia) return;

        const media = this.currentInspectedMedia;
        const isVideo = this.selectedTab === 'video';

        let formatNote = '';
        const destDir = (this.inspectorDownloadDir && this.inspectorDownloadDir.value.trim())
            ? this.inspectorDownloadDir.value.trim()
            : (this.settings.download_dir || '');
        const organizeGenre = this.checkInspectorOrganizeGenre
            ? this.checkInspectorOrganizeGenre.checked
            : (this.settings.organize_by_genre !== false);

        let options = {
            dest_dir: destDir,
            organize_by_genre: organizeGenre
        };

        if (isVideo) {
            const res = this.selectedResolution;
            const container = this.selectContainer.value;
            const height = res ? res.height : '1080';
            formatNote = `${height}p (${container.toUpperCase()})`;
            options.resolution = String(height);
            options.container = container;
            options.embed_subtitles = this.checkEmbedSubs.checked;
        } else {
            const aud = this.selectedAudio || { format: 'mp3', quality: '320' };
            formatNote = `${aud.format.toUpperCase()} (${aud.quality}k)`;
            options.audio_format = aud.format;
            options.audio_quality = aud.quality;
            options.embed_cover = this.checkEmbedCover.checked;
        }

        const payload = {
            url: media.url,
            title: media.title,
            author: media.uploader,
            thumbnail: media.thumbnail,
            duration: media.duration,
            download_type: isVideo ? 'video' : 'audio',
            format_note: formatNote,
            options: options
        };

        try {
            const res = await fetch('/api/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Falha ao iniciar download.');
            }

            const data = await res.json();
            this.closeInspectorModal();
            this.inputUrl.value = '';
            this.btnClearInput.classList.add('hidden');
            this.showToast(`Download de "${media.title}" iniciado!`, 'success');

            // Adiciona aos ativos
            this.activeDownloads.set(data.task_id, {
                id: data.task_id,
                title: media.title,
                author: media.uploader,
                thumbnail: media.thumbnail,
                duration_formatted: media.duration_formatted,
                type: isVideo ? 'video' : 'audio',
                format_note: formatNote,
                status: 'downloading',
                progress: 0,
                speed: 'Iniciando...',
                eta: '--:--'
            });

            this.renderActiveDownloads();
        } catch (err) {
            this.showToast(err.message, 'error');
        }
    }

    // ==========================================
    // Renderização de Downloads Ativos
    // ==========================================
    renderActiveDownloads() {
        const count = this.activeDownloads.size;
        this.activeCounter.textContent = count;
        this.emptyActiveState.classList.toggle('hidden', count > 0);

        if (this.btnCancelAllDownloads) {
            this.btnCancelAllDownloads.classList.toggle('hidden', count === 0);
        }

        // Remove cards órfãos
        const existingCardIds = new Set(Array.from(this.activeDownloadsList.querySelectorAll('.download-card')).map(c => c.id.replace('card-', '')));
        for (let id of existingCardIds) {
            if (!this.activeDownloads.has(id)) {
                const el = document.getElementById(`card-${id}`);
                if (el) el.remove();
            }
        }

        this.activeDownloadsList.querySelectorAll('.btn-load-more').forEach(el => el.remove());

        if (count === 0) return;

        const allTasks = Array.from(this.activeDownloads.values());
        const displayedTasks = allTasks.slice(0, this.activeDisplayLimit);

        // Renderiza ou atualiza cards limitados ao activeDisplayLimit
        displayedTasks.forEach(task => {
            let card = document.getElementById(`card-${task.id}`);
            if (!card) {
                card = this.createActiveCardElement(task);
                this.activeDownloadsList.appendChild(card);
            }
            this.updateActiveCardUI(task);
        });

        // Botão Carregar Mais se houver mais itens que o limite
        if (count > this.activeDisplayLimit) {
            const loadMoreBtn = document.createElement('button');
            loadMoreBtn.className = 'btn-load-more';
            const remaining = count - this.activeDisplayLimit;
            loadMoreBtn.innerHTML = `
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
                Exibir mais (${remaining} downloads restantes)
            `;
            loadMoreBtn.addEventListener('click', () => {
                this.activeDisplayLimit += 30;
                this.renderActiveDownloads();
            });
            this.activeDownloadsList.appendChild(loadMoreBtn);
        }
    }

    createActiveCardElement(task) {
        const card = document.createElement('div');
        card.className = 'download-card';
        card.id = `card-${task.id}`;

        const safeTitle = this.escapeHtml(task.title || 'Vídeo sem título');
        const safeAuthor = this.escapeHtml(task.author || 'YouTube');

        card.innerHTML = `
            <div class="card-thumb">
                <img src="${task.thumbnail || '/static/placeholder.jpg'}" alt="Thumb" onerror="this.src='https://placehold.co/140x80/141824/64748b?text=Download'"/>
                ${task.duration_formatted ? `<span class="card-thumb-duration">${task.duration_formatted}</span>` : ''}
            </div>
            <div class="card-info">
                <div class="card-title-row">
                    <h4 class="card-title" title="${safeTitle}">${safeTitle}</h4>
                    <span class="card-format-badge">${task.format_note || task.type.toUpperCase()}</span>
                </div>
                <p class="card-author">${safeAuthor}</p>
                <div class="progress-bar-container">
                    <div class="progress-bar-fill" id="fill-${task.id}" style="width: ${task.progress || 0}%"></div>
                </div>
                <div class="card-metrics">
                    <div class="metric-left">
                        <span id="speed-${task.id}">${task.speed || 'Calculando...'}</span>
                        <span id="eta-${task.id}">ETA: ${task.eta || '--:--'}</span>
                    </div>
                    <div class="metric-right">
                        <span id="percent-${task.id}">${task.progress || 0}%</span>
                    </div>
                </div>
            </div>
            <div class="card-actions">
                <button class="btn-action-small danger" onclick="window.app.cancelDownload('${task.id}')" title="Cancelar Download">
                    ✕
                </button>
            </div>
        `;

        return card;
    }

    updateActiveCardUI(task) {
        const fill = document.getElementById(`fill-${task.id}`);
        const speed = document.getElementById(`speed-${task.id}`);
        const eta = document.getElementById(`eta-${task.id}`);
        const percent = document.getElementById(`percent-${task.id}`);

        if (fill) fill.style.width = `${task.progress || 0}%`;
        if (speed) speed.textContent = task.speed || '';
        if (eta) eta.textContent = task.eta ? `ETA: ${task.eta}` : '';
        if (percent) percent.textContent = `${task.progress || 0}%`;
    }

    async cancelDownload(taskId) {
        try {
            await fetch(`/api/downloads/${taskId}/cancel`, { method: 'POST' });
            this.showToast('Cancelamento solicitado.', 'info');
        } catch (e) {
            this.showToast('Erro ao cancelar download.', 'error');
        }
    }

    async cancelAllDownloads() {
        if (!this.activeDownloads || this.activeDownloads.size === 0) {
            this.showToast('Não há downloads ativos para cancelar.', 'info');
            return;
        }

        if (!confirm(`Deseja realmente cancelar todos os ${this.activeDownloads.size} downloads em andamento e na fila?`)) {
            return;
        }

        try {
            const res = await fetch('/api/downloads/cancel-all', { method: 'POST' });
            if (res.ok) {
                const data = await res.json();
                this.activeDownloads.clear();
                this.renderActiveDownloads();
                this.showToast(`Todos os downloads foram cancelados (${data.count} cancelado(s)).`, 'info');
                await this.loadHistory();
            } else {
                const err = await res.json();
                throw new Error(err.detail || 'Erro ao cancelar downloads.');
            }
        } catch (err) {
            this.showToast(err.message, 'error');
        }
    }

    // ==========================================
    // Histórico e Biblioteca
    // ==========================================
    async loadHistory() {
        try {
            const res = await fetch('/api/downloads');
            this.history = await res.json();
            this.renderHistory();
        } catch (e) {
            console.error('Erro ao buscar histórico:', e);
        }
    }

    renderHistory() {
        let filtered = [...this.history];

        // Filtro por categoria
        if (this.activeFilter === 'video') {
            filtered = filtered.filter(item => item.type === 'video');
        } else if (this.activeFilter === 'audio') {
            filtered = filtered.filter(item => item.type === 'audio');
        } else if (this.activeFilter === 'completed') {
            filtered = filtered.filter(item => item.status === 'completed');
        }

        // Filtro por texto
        if (this.searchQuery) {
            filtered = filtered.filter(item => 
                (item.title && item.title.toLowerCase().includes(this.searchQuery)) ||
                (item.author && item.author.toLowerCase().includes(this.searchQuery))
            );
        }

        this.historyCounter.textContent = filtered.length;
        this.emptyHistoryState.classList.toggle('hidden', filtered.length > 0);

        // Limpa lista exceto o emptyState
        this.historyList.querySelectorAll('.history-card, .btn-load-more').forEach(el => el.remove());

        if (filtered.length === 0) return;

        const totalCount = filtered.length;
        const displayedItems = filtered.slice(0, this.historyDisplayLimit);

        displayedItems.forEach(item => {
            const card = document.createElement('div');
            card.className = 'history-card';

            const isDone = item.status === 'completed';
            const sizeStr = item.file_size ? `${(item.file_size / (1024 * 1024)).toFixed(1)} MB` : '';

            card.innerHTML = `
                <div class="history-thumb">
                    <img src="${item.thumbnail || 'https://placehold.co/100x58/141824/64748b?text=Mídia'}" alt="Thumb" onerror="this.src='https://placehold.co/100x58/141824/64748b?text=Mídia'"/>
                </div>
                <div class="history-info">
                    <h4 class="history-title" title="${item.title}">${item.title}</h4>
                    <div class="history-meta">
                        <span class="history-badge ${item.type}">${item.format_note || item.type.toUpperCase()}</span>
                        <span>${item.author || 'YouTube'}</span>
                        ${sizeStr ? `<span>• ${sizeStr}</span>` : ''}
                        <span>• ${new Date(item.created_at).toLocaleDateString('pt-BR')}</span>
                    </div>
                </div>
                <div class="history-actions">
                    ${isDone ? `
                        <button class="btn-action-small play" onclick="window.app.playMedia('${item.id}')" title="Reproduzir no Windows">
                            ▶ Reproduzir
                        </button>
                        <button class="btn-action-small" onclick="window.app.openFolder('${item.id}')" title="Mostrar na Pasta do Windows">
                            📁 Abrir Pasta
                        </button>
                    ` : `
                        <span class="badge ${item.status}">${item.status}</span>
                    `}
                    <button class="btn-action-small danger" onclick="window.app.deleteMedia('${item.id}')" title="Excluir do Histórico">
                        🗑
                    </button>
                </div>
            `;

            this.historyList.appendChild(card);
        });

        // Botão Carregar Mais se houver mais itens que o limite
        if (totalCount > this.historyDisplayLimit) {
            const loadMoreBtn = document.createElement('button');
            loadMoreBtn.className = 'btn-load-more';
            const remaining = totalCount - this.historyDisplayLimit;
            loadMoreBtn.innerHTML = `
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
                Exibir mais (${remaining} itens restantes)
            `;
            loadMoreBtn.addEventListener('click', () => {
                this.historyDisplayLimit += 30;
                this.renderHistory();
            });
            this.historyList.appendChild(loadMoreBtn);
        }
    }

    async clearHistory() {
        if (!this.history || this.history.length === 0) {
            this.showToast('A biblioteca já está vazia.', 'info');
            return;
        }

        if (!confirm('Deseja limpar todos os downloads da biblioteca? A tela ficará vazia.')) {
            return;
        }

        try {
            const res = await fetch('/api/downloads/clear/all', { method: 'DELETE' });
            if (res.ok) {
                this.history = [];
                this.renderHistory();
                this.showToast('Biblioteca de downloads limpa com sucesso!', 'success');
            } else {
                const err = await res.json();
                throw new Error(err.detail || 'Erro ao limpar downloads.');
            }
        } catch (err) {
            this.showToast(err.message, 'error');
        }
    }

    async playMedia(id) {
        try {
            const res = await fetch(`/api/downloads/${id}/play`, { method: 'POST' });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Não foi possível reproduzir.');
            }
            this.showToast('Abrindo reprodutor de mídia...', 'info');
        } catch (e) {
            this.showToast(e.message, 'error');
        }
    }

    async openFolder(id) {
        try {
            const res = await fetch(`/api/downloads/${id}/open-folder`, { method: 'POST' });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Não foi possível abrir a pasta.');
            }
            this.showToast('Pasta aberta no Windows Explorer!', 'info');
        } catch (e) {
            this.showToast(e.message, 'error');
        }
    }

    async deleteMedia(id) {
        if (!confirm('Deseja excluir este item do histórico?')) return;
        const deleteFile = confirm('Deseja também apagar o arquivo do disco no Windows?');

        try {
            const res = await fetch(`/api/downloads/${id}?delete_file=${deleteFile}`, { method: 'DELETE' });
            if (res.ok) {
                this.showToast('Item removido com sucesso.', 'info');
                this.loadHistory();
            }
        } catch (e) {
            this.showToast('Erro ao excluir item.', 'error');
        }
    }

    // ==========================================
    // Sistema de Toast
    // ==========================================
    showToast(message, type = 'info', duration = 3500) {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;

        this.toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }
}

// Inicializa a aplicação
window.addEventListener('DOMContentLoaded', () => {
    window.app = new DownloaderApp();
});

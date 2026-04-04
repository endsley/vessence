# Code Map — Android (Kotlin)
_Auto-generated on 2026-03-27 08:15 UTC by `generate_code_map.py`_

## android:.../CrashReporter.kt (118 lines)
  object CrashReporter → L17
    install() → L22
    uploadPendingCrash() → L44
    getLastCrash() → L61
    clearLastCrash() → L66
    buildReport() → L71
    sendToServer() → L104

## android:.../MainActivity.kt (108 lines)
  class MainActivity → L22
    override onResume() → L27
    override onPause() → L32
    override onCreate() → L37
    override onNewIntent() → L58
    handleIncomingShareIntent() → L63
    requestNotificationPermissionIfNeeded() → L96

## android:.../PlaybackService.kt (28 lines)
  class PlaybackService → L7
    override onCreate() → L10
    override onGetSession() → L16
    override onDestroy() → L20

## android:.../SharedIntentState.kt (30 lines)
  object SharedIntentState → L11
    setSharedUris() → L18
    setSharedText() → L22
    clear() → L26

## android:.../VessencesApp.kt (197 lines)
  @Composable VessencesApp() → L46
  @Composable AuthenticatedApp() → L70
  @Composable EssenceViewRouter() → L143
  @Composable EssencePlaceholderView() → L157

## android:.../data/api/ApiClient.kt (106 lines)
  object ApiClient → L17
    init() → L26
    getOkHttpClient() → L69
    getCookieStore() → L70
    getVaultBaseUrl() → L71
    getJaneBaseUrl() → L72
    getJaneRetrofit() → L73
    getAuthenticatedImageLoader() → L77
    clearSession() → L100
    ensureTrailingSlash() → L104

## android:.../data/api/AuthApi.kt (22 lines)
  interface AuthApi → L7
    suspend googleToken() → L9
    suspend checkAuth() → L12
    suspend logout() → L15
    suspend getDevices() → L18
    suspend revokeDevice() → L21

## android:.../data/api/EssenceApi.kt (25 lines)
  interface EssenceApi → L7
    suspend listEssences() → L9
    suspend loadEssence() → L12
    suspend unloadEssence() → L15
    suspend activateEssence() → L18
    suspend deleteEssence() → L21
    suspend getActiveEssences() → L24

## android:.../data/api/UpdateChecker.kt (121 lines)
  class AppVersion → L20
  interface UpdateApi → L27
    suspend getLatestVersion() → L29
  object UpdateManager → L32
    suspend checkForUpdate() → L35
    downloadAndInstall() → L57
    override onReceive() → L77
    getInstalledVersionCode() → L108

## android:.../data/api/VaultApi.kt (92 lines)
  interface VaultApi → L10
    suspend listRoot() → L12
    suspend listDirectory() → L18
    suspend getMetadata() → L25
    suspend getThumbnail() → L28
    suspend serveFile() → L32
    suspend getFileContent() → L35
    suspend saveFileContent() → L38
    suspend updateDescription() → L44
    suspend getFileChanges() → L50
    suspend uploadFiles() → L54
    suspend amberChat() → L62
    suspend getPlaylists() → L66
    suspend getPlaylist() → L69
    suspend createPlaylist() → L72
    suspend updatePlaylist() → L75
    suspend deletePlaylist() → L81
    suspend getShares() → L85
    suspend createShare() → L88
    suspend revokeShare() → L91

## android:.../data/model/BriefingModels.kt (31 lines)
  class BriefingArticle → L5
  class BriefingTopic → L21
  class BriefingResponse → L28

## android:.../data/model/ChatMessage.kt (21 lines)
  class ChatMessage → L3
  class ChatRequest → L15

## android:.../data/model/Essence.kt (27 lines)
  class Essence → L5
  class EssenceCapabilities → L19
  class PreferredModel → L24

## android:.../data/model/FileItem.kt (68 lines)
  class DirectoryListing → L5
  class FolderItem → L14
  class FileItem → L20
  class FileMetadata → L38
  class FileContentResponse → L54
  class FileChangesResponse → L56
  class UploadResult → L58
  class UploadResponse → L68

## android:.../data/model/Playlist.kt (30 lines)
  class Playlist → L5
  class Track → L14
  class CreatePlaylistRequest → L22
  class TrackInput → L27

## android:.../data/repository/AnnouncementPoller.kt (76 lines)
  class AnnouncementPoller → L13
  class ProgressBubble → L16
    start() → L28
    stop() → L40
    suspend poll() → L46

## android:.../data/repository/AuthRepository.kt (102 lines)
  class AuthRepository → L19
    suspend checkAuth() → L25
    suspend signInWithGoogle() → L39
    suspend logout() → L95

## android:.../data/repository/ChatRepository.kt (171 lines)
  class UploadResult → L29
  class ChatRepository → L36
    suspend uploadFile() → L43
    streamChat() → L98
    initSession() → L143
    suspend endJaneSession() → L166

## android:.../data/repository/EssenceRepository.kt (73 lines)
  class EssenceRepository → L6
    suspend listEssences() → L8
    suspend getActiveEssences() → L21
    suspend loadEssence() → L34
    suspend unloadEssence() → L44
    suspend activateEssence() → L54
    suspend deleteEssence() → L64

## android:.../data/repository/FileRepository.kt (195 lines)
  class FileRepository → L14
  class CachedListing → L18
    isExpired() → L22
    suspend listDirectory() → L34
    suspend getCachedListing() → L75
    suspend invalidateCache() → L80
    suspend invalidateAllCache() → L85
    suspend getMetadata() → L89
    getThumbnailUrl() → L99
    getServeUrl() → L103
    suspend getFileContent() → L107
    suspend saveFileContent() → L117
    suspend updateDescription() → L127
    suspend uploadFiles() → L137
    getFileName() → L171
    getInstance() → L189

## android:.../data/repository/LiveBroadcastListener.kt (110 lines)
  class LiveBroadcastListener → L14
  class LiveStatus → L18
    start() → L28
    stop() → L44
    connect() → L50

## android:.../data/repository/PlaylistRepository.kt (51 lines)
  class PlaylistRepository → L6
    suspend getPlaylists() → L8
    suspend getPlaylist() → L18
    suspend createPlaylist() → L28
    suspend deletePlaylist() → L38
    getTrackUrl() → L48

## android:.../data/repository/SettingsRepository.kt (48 lines)
  class SettingsRepository → L7
    suspend getDevices() → L9
    suspend revokeDevice() → L19
    suspend getShares() → L29
    suspend revokeShare() → L39

## android:.../data/repository/VoiceSettingsRepository.kt (37 lines)
  class VoiceSettingsRepository → L6
    isAlwaysListeningEnabled() → L9
    setAlwaysListeningEnabled() → L12
    getTriggerPhrase() → L16
    setTriggerPhrase() → L20
    isTriggerTrained() → L24
    setTriggerTrained() → L27
    getTriggerSamplesCount() → L31
    setTriggerSamplesCount() → L34

## android:.../notifications/ChatNotificationManager.kt (115 lines)
  class ChatNotificationManager → L19
    ensureChannels() → L27
    showReplyNotification() → L62

## android:.../ui/auth/LoginScreen.kt (150 lines)
  @Composable LoginScreen() → L31

## android:.../ui/auth/LoginViewModel.kt (50 lines)
  class LoginViewModel → L13
    signIn() → L29
    logout() → L41
    clearError() → L47

## android:.../ui/briefing/BriefingScreen.kt (749 lines)
  @Composable BriefingScreen() → L89
  @Composable TopBar() → L201
  @Composable TopicChips() → L261
  @Composable ArticleGrid() → L302
  @Composable ArticleCard() → L325
  @Composable ArticleDetailSheet() → L521
  formatSourceLine() → L709
  formatTimeAgo() → L716

## android:.../ui/briefing/BriefingViewModel.kt (307 lines)
  class BriefingUiState → L26
  class BriefingViewModel → L39
    refresh() → L57
    selectCategory() → L89
    toggleArticleExpanded() → L93
    getFilteredArticles() → L100
    dismissArticle() → L111
    getImageUrl() → L134
    speakArticle() → L140
    suspend playAudioFile() → L168
    suspend tryPlayServerAudio() → L199
    stopSpeaking() → L245
    readAll() → L255
    suspend fetchArticles() → L268
    suspend fetchTopics() → L288
    override onCleared() → L302

## android:.../ui/chat/AmberChatScreen.kt (28 lines)
  @Composable AmberChatScreen() → L11

## android:.../ui/chat/AttachmentSheet.kt (220 lines)
  @Composable AttachmentSheet() → L43

## android:.../ui/chat/ChatInputRow.kt (309 lines)
  @Composable ChatInputRow() → L61
    launchSpeechToText() → L109

## android:.../ui/chat/ChatMessageList.kt (64 lines)
  @Composable ChatMessageList() → L22

## android:.../ui/chat/ChatScreen.kt (499 lines)
  @Composable ChatScreen() → L61
    hasMicPermission() → L95
  @Composable ChatHeader() → L281
  @Composable LiveActivityBanner() → L381
  @Composable VoiceStatusBanner() → L418
  @Composable ErrorBanner() → L468

## android:.../ui/chat/ChatViewModel.kt (635 lines)
  class PendingMessage → L33
  class ChatUiState → L39
  class ChatViewModel → L56
    initSession() → L157
    sendMessage() → L206
    cancelCurrentResponse() → L229
    executeSend() → L249
    onSendComplete() → L385
    processNextInQueue() → L396
    clearError() → L406
    dismissUpdate() → L410
    installUpdate() → L414
    toggleTts() → L419
    stopSpeaking() → L429
    speakText() → L434
    speakIfEnabled() → L440
    suspend tryServerTts() → L453
    autoListenAfterTts() → L515
    startAndroidSpeechRecognizer() → L525
    override onResults() → L536
    override onError() → L544
    override onReadyForSpeech() → L545
    override onBeginningOfSpeech() → L546
    override onRmsChanged() → L547
    override onBufferReceived() → L548
    override onEndOfSpeech() → L549
    override onPartialResults() → L550
    override onEvent() → L551
    clearSession() → L560
    setAlwaysListeningEnabled() → L573
    syncVoicePreferences() → L578
    startPushToTalk() → L582
    stopPushToTalk() → L586
    clearVoiceError() → L590
    updateAiMessage() → L594
    override onCleared() → L620

## android:.../ui/chat/JaneChatScreen.kt (656 lines)
  @Composable JaneChatScreen() → L68
  @Composable JaneTopBar() → L191
  @Composable UpdateBanner() → L230
  @Composable ChatInputBar() → L285
    launchSpeechRecognition() → L377

## android:.../ui/chat/PromptQueueSheet.kt (264 lines)
  class QueuePrompt → L41
  @Composable PromptQueueSheet() → L49
    loadPrompts() → L61
    addPrompt() → L84
    deletePrompt() → L101
    retryPrompt() → L114
    reorder() → L128

## android:.../ui/components/BottomNavBar.kt (52 lines)
  @Composable BottomNavBar() → L22

## android:.../ui/components/MarkdownText.kt (78 lines)
  @Composable MarkdownText() → L16
  parseBasicMarkdown() → L29

## android:.../ui/components/MessageBubble.kt (428 lines)
  @Composable MessageBubble() → L55
  @Composable UserBubble() → L70
  @Composable AiBubble() → L105
  @Composable AudioPlayCard() → L326
  @Composable AvatarFallback() → L413

## android:.../ui/components/RichMessageContent.kt (157 lines)
  @Composable RichMessageContent() → L31
  class MessagePart → L113
  class Text → L114
  class Image → L115
  splitMessageParts() → L121
  resolveImageUrl() → L152

## android:.../ui/essences/EssencesScreen.kt (341 lines)
  @Composable EssencesScreen() → L35
  @Composable EssenceListItem() → L114
  @Composable EssenceDetailView() → L181
  @Composable ChipRow() → L327

## android:.../ui/essences/EssencesViewModel.kt (112 lines)
  class EssencesUiState → L11
  class EssencesViewModel → L19
    loadEssences() → L35
    selectEssence() → L64
    loadEssence() → L68
    unloadEssence() → L79
    activateEssence() → L90
    deleteEssence() → L101

## android:.../ui/home/HomeScreen.kt (578 lines)
  class HomeEssenceCard → L70
  @Composable HomeScreen() → L79
  @Composable ProminentEssenceCard() → L322
  @Composable StandardEssenceCard() → L405
  @Composable EssenceAgentCard() → L457
  @Composable UpdateBanner() → L523

## android:.../ui/music/MusicScreen.kt (287 lines)
  @Composable MusicScreen() → L34
  @Composable PlaylistListScreen() → L75
  @Composable PlayerScreen() → L128
  formatTime() → L282

## android:.../ui/music/MusicViewModel.kt (237 lines)
  class MusicUiState → L26
  class MusicViewModel → L41
    override onMediaItemTransition() → L68
    override onIsPlayingChanged() → L72
    loadPlaylists() → L80
    openPlaylist() → L91
    closePlaylist() → L100
    preparePlaylist() → L111
    playTrack() → L122
    togglePlayPause() → L131
    next() → L144
    previous() → L158
    seekTo() → L164
    toggleShuffle() → L170
    toggleRepeat() → L174
    startProgressUpdates() → L178
    syncCookiesForMedia() → L202
    buildCookieHeaders() → L217
    override onCleared() → L231

## android:.../ui/settings/SettingsScreen.kt (371 lines)
  @Composable SettingsScreen() → L45

## android:.../ui/settings/SettingsViewModel.kt (78 lines)
  class SettingsUiState → L15
  class SettingsViewModel → L25
    loadAll() → L41
    revokeDevice() → L57
    revokeShare() → L63
    setAlwaysListeningEnabled() → L69

## android:.../ui/settings/TtsVoicePicker.kt (160 lines)
  @Composable TtsVoicePickerSheet() → L33

## android:.../ui/theme/ThemePreferences.kt (36 lines)
  object ThemePreferences → L8
    init() → L15
    toggleTheme() → L20
    setDarkMode() → L29

## android:.../ui/theme/VessenceTheme.kt (58 lines)
  @Composable VessenceTheme() → L47

## android:.../ui/vault/FileViewerScreen.kt (240 lines)
  @Composable FileViewerScreen() → L38
  syncCookiesToWebView() → L223

## android:.../ui/vault/VaultScreen.kt (395 lines)
  @Composable VaultScreen() → L47
  @Composable GridView() → L205
  @Composable ListView() → L235
  @Composable FolderGridItem() → L258
  @Composable FileGridItem() → L290
  @Composable FolderListItem() → L349
  @Composable FileListItem() → L370

## android:.../ui/vault/VaultViewModel.kt (146 lines)
  class VaultUiState → L15
  class VaultViewModel → L30
    loadDirectory() → L39
    buildPathSegments() → L73
    navigateToFolder() → L86
    navigateToPath() → L90
    toggleViewMode() → L94
    toggleFileSelection() → L99
    clearSelection() → L105
    openFile() → L109
    closeFile() → L120
    saveFileContent() → L124
    uploadFiles() → L133
    getThumbnailUrl() → L144
    getServeUrl() → L145

## android:.../ui/voice/TriggerWordTrainingScreen.kt (715 lines)
  @Composable TriggerWordTrainingScreen() → L96
    sampleFile() → L132
    startRecording() → L138
    playSample() → L156
    nextSample() → L166
    retryCurrentSample() → L179
  @Composable SetupPhase() → L277
  @Composable RecordingPhase() → L348
  @Composable ReviewPhase() → L424
  @Composable CompletePhase() → L504
  @Composable SampleIndicator() → L554
  recordSample() → L596
  writeWavFile() → L646
  playWavFile() → L672

## android:.../ui/worklog/WorkLogScreen.kt (133 lines)
  @Composable WorkLogScreen() → L38
    override shouldOverrideUrlLoading() → L93
  syncCookiesToWebView() → L117

## android:.../util/BriefingAudioCache.kt (116 lines)
  object BriefingAudioCache → L19
    getCacheDir() → L24
    isOnWifi() → L30
    getCachedFile() → L38
    suspend downloadToCache() → L46
    suspend prefetchAll() → L86
    cleanupOldFiles() → L103

## android:.../util/ChatPersistence.kt (71 lines)
  class ChatPersistence → L12
    saveMessages() → L18
    loadMessages() → L28
    clearMessages() → L39
  class SerializableMessage → L47
    toChatMessage() → L53
    from() → L63

## android:.../util/ChatPreferences.kt (31 lines)
  class ChatPreferences → L8
    isTtsEnabled() → L11
    setTtsEnabled() → L14
    getTtsVoice() → L18
    setTtsVoice() → L21
    isAutoListenEnabled() → L25
    setAutoListenEnabled() → L28

## android:.../util/CookieStore.kt (44 lines)
  class CookieStore → L9
    override saveFromResponse() → L13
    override loadForRequest() → L24
    loadForHost() → L32
    clear() → L41

## android:.../util/NdjsonParser.kt (43 lines)
  object NdjsonParser → L14
    parse() → L17

## android:.../util/SettingsSync.kt (101 lines)
  object SettingsSync → L21
    suspend pullFromServer() → L31
    suspend pushToServer() → L76
    getString() → L93
    getBoolean() → L96
    getLong() → L99

## android:.../voice/AlwaysListeningService.kt (465 lines)
  class AlwaysListeningService → L43
    start() → L54
    stop() → L63
    override onCreate() → L81
    override onStartCommand() → L88
    override onBind() → L96
    override onDestroy() → L98
    createNotificationChannels() → L116
    buildListeningNotification() → L141
    acquireWakeLock() → L160
    releaseWakeLock() → L170
    isInCall() → L177
    startListeningLoop() → L182
    runWakeWordDetection() → L205
    matchesTrigger() → L272
    onWakeWordDetected() → L291
    vibrateShort() → L299
    captureCommand() → L323
    sendToJane() → L399
    showResponseNotification() → L424
    extractText() → L449
    rmsLevel() → L452

## android:.../voice/AndroidTtsManager.kt (90 lines)
  class AndroidTtsManager → L15
    override onStart() → L27
    override onDone() → L29
    override onError() → L34
    override onError() → L38
    override onInit() → L45
    suspend speak() → L56
    stop() → L71
    shutdown() → L75
    suspend awaitReady() → L82

## android:.../voice/VoiceController.kt (560 lines)
  class VoiceState → L21
  class VoiceController → L31
    setAlwaysListeningEnabled() → L62
    setTriggerPhrase() → L71
    startPushToTalk() → L80
    stopPushToTalk() → L88
    startWakeWordListening() → L92
    onAssistantReply() → L106
    clearError() → L123
    release() → L127
    startListeningWithTimeout() → L137
    suspend startCommandListening() → L149
    suspend prepareModel() → L158
    startSession() → L180
    stopListening() → L277
    emitState() → L290
    acknowledgementForBackend() → L295
    wakePhrasesForBackend() → L301
    statusForMode() → L313
  class ListeningSession → L329
    start() → L352
    stop() → L358
    runLoop() → L364
    containsWakePhrase() → L472
    extractText() → L498
    rmsLevel() → L501
    AudioRecord() → L515
    AudioRecord() → L523
    normalizedSimilarity() → L538
    levenshteinDistance() → L545

## android:.../voice/VoskModelManager.kt (113 lines)
  class VoskModelManager → L15
    getModelSync() → L26
    suspend ensureModel() → L40
    ensureModelDirectory() → L51
    unzip() → L85
    looksReady() → L102

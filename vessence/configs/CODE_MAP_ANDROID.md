# Code Map — Android (Kotlin)
_Auto-generated on 2026-04-05 01:57 UTC by `generate_code_map.py`_

## android:.../CrashReporter.kt (118 lines)
  object CrashReporter → L17
    install() → L22
    uploadPendingCrash() → L44
    getLastCrash() → L61
    clearLastCrash() → L66
    buildReport() → L71
    sendToServer() → L104

## android:.../DiagnosticReporter.kt (124 lines)
  object DiagnosticReporter → L23
    init() → L28
    report() → L41
    wakeWordModelLoaded() → L73
    wakeWordModelFailed() → L80
    wakeWordDetected() → L87
    wakeWordScoreUpdate() → L91
    micPermissionState() → L99
    micInitFailed() → L105
    serviceEvent() → L109
    nonFatalError() → L117

## android:.../MainActivity.kt (206 lines)
  class MainActivity → L22
    launchStt() → L34
    override onResume() → L57
    override onPause() → L68
    override onCreate() → L75
    override onNewIntent() → L122
    handleWakeWordIntent() → L129
    handleNotificationIntent() → L153
    handleIncomingShareIntent() → L161
    requestNotificationPermissionIfNeeded() → L194

## android:.../MusicPlayNavigationState.kt (24 lines)
  object MusicPlayNavigationState → L11
    requestPlay() → L15
    consume() → L19

## android:.../NotificationNavigationState.kt (24 lines)
  object NotificationNavigationState → L11
    consumeTarget() → L19

## android:.../PlaybackService.kt (28 lines)
  class PlaybackService → L7
    override onCreate() → L10
    override onGetSession() → L16
    override onDestroy() → L20

## android:.../ShareReceiverActivity.kt (110 lines)
  class ShareReceiverActivity → L22
    override onCreate() → L24
    extractUrl() → L68
    submitArticle() → L74

## android:.../SharedIntentState.kt (30 lines)
  object SharedIntentState → L11
    setSharedUris() → L18
    setSharedText() → L22
    clear() → L26

## android:.../SttResultBus.kt (23 lines)
  object SttResultBus → L11
    postResult() → L14

## android:.../VessencesApp.kt (257 lines)
  @Composable VessencesApp() → L49
  @Composable AuthenticatedApp() → L73
  @Composable EssenceViewRouter() → L203
  @Composable EssencePlaceholderView() → L217

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

## android:.../data/api/AuthApi.kt (25 lines)
  interface AuthApi → L7
    suspend googleToken() → L9
    suspend checkAuth() → L12
    suspend logout() → L15
    suspend getDevices() → L18
    suspend revokeDevice() → L21
    suspend getModelSettings() → L24

## android:.../data/api/EssenceApi.kt (25 lines)
  interface EssenceApi → L7
    suspend listEssences() → L9
    suspend loadEssence() → L12
    suspend unloadEssence() → L15
    suspend activateEssence() → L18
    suspend deleteEssence() → L21
    suspend getActiveEssences() → L24

## android:.../data/api/UpdateChecker.kt (137 lines)
  class AppVersion → L20
  interface UpdateApi → L27
    suspend getLatestVersion() → L29
  object UpdateManager → L32
    suspend checkForUpdate() → L35
    downloadAndInstall() → L65
    override onReceive() → L85
    getInstalledVersionCode() → L116
    getInstalledVersionName() → L130

## android:.../data/api/VaultApi.kt (88 lines)
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
    suspend getPlaylists() → L62
    suspend getPlaylist() → L65
    suspend createPlaylist() → L68
    suspend updatePlaylist() → L71
    suspend deletePlaylist() → L77
    suspend getShares() → L81
    suspend createShare() → L84
    suspend revokeShare() → L87

## android:.../data/model/BriefingModels.kt (38 lines)
  class BriefingArticle → L5
  class BriefingTopic → L21
  class BriefingResponse → L28
  class SavedArticleEntry → L33

## android:.../data/model/ChatMessage.kt (22 lines)
  class ChatMessage → L3
  class ChatRequest → L16

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

## android:.../data/repository/AuthRepository.kt (147 lines)
  class AuthRepository → L19
    suspend checkAuth() → L25
    isServerDown() → L39
    suspend signInWithGoogle() → L64
    suspend logout() → L140

## android:.../data/repository/ChatRepository.kt (161 lines)
  class UploadResult → L27
  class ChatRepository → L34
    suspend uploadFile() → L41
    streamChat() → L94
    initSession() → L133
    suspend endJaneSession() → L156

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

## android:.../data/repository/SettingsRepository.kt (58 lines)
  class SettingsRepository → L7
    suspend getDevices() → L9
    suspend revokeDevice() → L19
    suspend getShares() → L29
    suspend revokeShare() → L39
    suspend getModelSettings() → L49

## android:.../data/repository/VoiceSettingsRepository.kt (44 lines)
  class VoiceSettingsRepository → L6
    isAlwaysListeningEnabled() → L9
    setAlwaysListeningEnabled() → L12
    getTriggerPhrase() → L16
    setTriggerPhrase() → L20
    isTriggerTrained() → L24
    setTriggerTrained() → L27
    getTriggerSamplesCount() → L31
    setTriggerSamplesCount() → L34
    getWakeWordThreshold() → L38
    setWakeWordThreshold() → L41

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

## android:.../ui/briefing/BriefingScreen.kt (897 lines)
  @Composable BriefingScreen() → L94
  @Composable TopBar() → L267
  @Composable HistorySheet() → L338
  @Composable TopicChips() → L397
  @Composable ArticleGrid() → L438
  @Composable ArticleCard() → L471
  @Composable ArticleDetailSheet() → L669
  formatSourceLine() → L857
  formatTimeAgo() → L864

## android:.../ui/briefing/BriefingViewModel.kt (528 lines)
  class BriefingUiState → L28
  class BriefingViewModel → L49
    refresh() → L70
    fetchArchiveDates() → L106
    loadArchive() → L127
    clearArchive() → L159
    selectCategory() → L164
    toggleArticleExpanded() → L168
    getFilteredArticles() → L175
    dismissArticle() → L186
    getImageUrl() → L209
    speakArticle() → L215
    suspend playAudioFile() → L252
    suspend tryPlayServerAudio() → L283
    stopSpeaking() → L329
    readAll() → L345
    suspend fetchArticles() → L366
    suspend fetchTopics() → L386
    saveArticle() → L400
    unsaveArticle() → L427
    isArticleSaved() → L445
    toggleSavedView() → L447
    loadSavedArticles() → L453
    fetchSavedArticleIds() → L481
    fetchSavedCategories() → L502
    override onCleared() → L523

## android:.../ui/chat/AttachmentSheet.kt (255 lines)
  @Composable AttachmentSheet() → L46

## android:.../ui/chat/ChatInputRow.kt (425 lines)
  isConversationEndPhrase() → L109
  @Composable ChatInputRow() → L130
    launchSpeechToText() → L202

## android:.../ui/chat/ChatMessageList.kt (68 lines)
  @Composable ChatMessageList() → L22

## android:.../ui/chat/ChatScreen.kt (535 lines)
  @Composable ChatScreen() → L66
    hasMicPermission() → L122
  @Composable ChatHeader() → L328
  @Composable LiveActivityBanner() → L417
  @Composable VoiceStatusBanner() → L454
  @Composable ErrorBanner() → L504

## android:.../ui/chat/ChatViewModel.kt (909 lines)
  class PendingMessage → L33
  class ChatUiState → L39
  class ChatViewModel → L57
    consumeMusicPlayRequest() → L77
    initSession() → L186
    sendMessage() → L235
    cancelCurrentResponse() → L258
    executeSend() → L278
    isConversationEnding() → L524
    onSendComplete() → L541
    processNextInQueue() → L586
    clearError() → L596
    dismissUpdate() → L600
    installUpdate() → L604
    toggleTts() → L611
    stopSpeaking() → L621
    speakText() → L629
    speakIfEnabled() → L635
    suspend tryServerTts() → L646
    autoListenAfterTts() → L708
    endVoiceConversation() → L722
    isConversationEndPhrase() → L738
    showSystemMessage() → L758
    clearSession() → L767
    setAlwaysListeningEnabled() → L780
    syncVoicePreferences() → L787
    clearWakeWordTrigger() → L791
    triggerWakeWord() → L796
    startPushToTalk() → L801
    stopPushToTalk() → L805
    cancelListening() → L809
    clearVoiceError() → L813
    updateAiMessage() → L817
    switchProvider() → L845
    override onCleared() → L894

## android:.../ui/chat/ChatViewModelFactory.kt (24 lines)
  class ChatViewModelFactory → L9

## android:.../ui/chat/EndPhraseDetector.kt (82 lines)
  object EndPhraseDetector → L9
    isEndPhrase() → L62

## android:.../ui/chat/JaneChatScreen.kt (708 lines)
  @Composable JaneChatScreen() → L69
  @Composable JaneTopBar() → L193
  @Composable UpdateBanner() → L232
  @Composable ChatInputBar() → L287
    launchSpeechRecognition() → L402

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

## android:.../ui/components/MarkdownText.kt (124 lines)
  @Composable MarkdownText() → L19
  parseBasicMarkdown() → L48

## android:.../ui/components/MessageBubble.kt (480 lines)
  @Composable MessageBubble() → L55
  @Composable UserBubble() → L71
  @Composable AiBubble() → L106
  @Composable AudioPlayCard() → L378
  @Composable AvatarFallback() → L465

## android:.../ui/components/RichMessageContent.kt (287 lines)
  @Composable RichMessageContent() → L35
  class MessagePart → L120
  class Text → L121
  class Image → L122
  class JobQueue → L123
  splitMessageParts() → L130
  class TagMatch → L134
  resolveImageUrl() → L173
  class ParsedJob → L180
  parseJobQueue() → L191
  @Composable JobQueueCards() → L216

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

## android:.../ui/home/HomeScreen.kt (598 lines)
  class HomeEssenceCard → L72
  @Composable HomeScreen() → L81
  @Composable ProminentEssenceCard() → L342
  @Composable StandardEssenceCard() → L425
  @Composable EssenceAgentCard() → L477
  @Composable UpdateBanner() → L543

## android:.../ui/music/MusicScreen.kt (325 lines)
  @Composable MusicScreen() → L39
  @Composable PlaylistListScreen() → L85
  @Composable PlayerScreen() → L166
  formatTime() → L320

## android:.../ui/music/MusicViewModel.kt (344 lines)
  class MusicUiState → L26
  class MusicViewModel → L41
    override onMediaItemTransition() → L68
    override onPlayerError() → L72
    override onPlaybackStateChanged() → L81
    override onIsPlayingChanged() → L91
    checkPendingPlay() → L125
    loadPlaylists() → L139
    openPlaylist() → L150
    deletePlaylist() → L159
    closePlaylist() → L174
    preparePlaylist() → L185
    ensurePlayerReady() → L198
    playTrack() → L215
    togglePlayPause() → L230
    next() → L245
    previous() → L259
    seekTo() → L265
    toggleShuffle() → L271
    toggleRepeat() → L275
    startProgressUpdates() → L279
    syncCookiesForMedia() → L303
    buildCookieHeaders() → L318
    override onCleared() → L332

## android:.../ui/settings/SettingsScreen.kt (586 lines)
  @Composable SettingsScreen() → L48

## android:.../ui/settings/SettingsViewModel.kt (128 lines)
  class SettingsUiState → L17
  class SettingsViewModel → L30
    loadAll() → L49
    revokeDevice() → L69
    revokeShare() → L75
    setAlwaysListeningEnabled() → L81
    requestBatteryOptimizationExemption() → L93
    setAutoListenAfterTts() → L107
    sendDiagnosticPing() → L112
    setWakeWordThreshold() → L122

## android:.../ui/settings/SettingsViewModelFactory.kt (22 lines)
  class SettingsViewModelFactory → L8

## android:.../ui/settings/SystemArchitectureScreen.kt (570 lines)
  @Composable SystemArchitectureScreen() → L40
  @Composable ArchitectureHub() → L65
  @Composable SectionHeader() → L207
  @Composable NavCard() → L219
  @Composable DetailPage() → L244
  @Composable InfoCard() → L268
  @Composable BulletList() → L284
  @Composable OverviewContent() → L302
  @Composable JaneContent() → L328
  @Composable LlmTiersContent() → L354
  @Composable MemoryContent() → L396
  @Composable EssencesContent() → L421
  @Composable VaultContent() → L447
  @Composable StandingBrainContent() → L465
  @Composable ProviderSwitchContent() → L487
  @Composable DockerContent() → L505
  @Composable CronContent() → L527
  @Composable SecurityContent() → L547

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

## android:.../util/ChatPreferences.kt (46 lines)
  class ChatPreferences → L8
    getJaneSessionId() → L12
    resetJaneSessionId() → L20
    isTtsEnabled() → L26
    setTtsEnabled() → L29
    getTtsVoice() → L33
    setTtsVoice() → L36
    isAutoListenEnabled() → L40
    setAutoListenEnabled() → L43

## android:.../util/Constants.kt (22 lines)
  object Constants → L3
    DEFAULT_VAULT_BASE_URL → L4
    DEFAULT_JANE_BASE_URL → L5
    USER_AGENT → L6
    PREFS_NAME → L7
    PREF_SERVER_URL → L8
    PREF_JANE_URL → L9
    PREF_GOOGLE_CLIENT_ID → L10
    PREF_ALWAYS_LISTENING → L11
    PREF_TRIGGER_PHRASE → L12
    PREF_TRIGGER_TRAINED → L13
    PREF_TRIGGER_SAMPLES_COUNT → L14
    DEFAULT_TRIGGER_PHRASE → L15
    PREF_WAKE_WORD_THRESHOLD → L16
    DEFAULT_WAKE_WORD_THRESHOLD → L17
    GOOGLE_CLIENT_ID → L18
    DEFAULT_RELAY_URL → L19
    PREF_CONNECTION_MODE → L20
    PREF_KEEP_SCREEN_ON → L21

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

## android:.../voice/AlwaysListeningService.kt (552 lines)
  class AlwaysListeningService → L36
    ACTION_STOP → L41
    start() → L51
    stop() → L60
    override onReceive() → L82
    override onCreate() → L103
    override onStartCommand() → L112
    override onBind() → L144
    override onDestroy() → L146
    createNotificationChannel() → L177
    buildListeningNotification() → L196
    acquireWakeLock() → L223
    releaseWakeLock() → L233
    pauseListening() → L239
    resumeListening() → L260
    isInCall() → L267
    isMediaPlaying() → L276
    startListeningLoop() → L285
    runWakeWordDetection() → L346
    CONFIRMATION_FRAMES → L405
    onWakeWordDetected() → L474

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

## android:.../voice/OpenWakeWordDetector.kt (291 lines)
  class OpenWakeWordDetector → L15
    SAMPLE_RATE → L22
    CHUNK_SIZE → L23
    feedAudio() → L77
    feedShorts() → L139
    isDetected() → L156
    reset() → L162
    computeMel() → L173
    computeSingleEmbedding() → L220
    classify() → L254
    override close() → L286

## android:.../voice/VessenceVoiceInteractionService.kt (35 lines)
  class VessenceVoiceInteractionService → L14
    override onReady() → L20
    override onShutdown() → L30

## android:.../voice/VessenceVoiceInteractionSessionService.kt (41 lines)
  class VessenceVoiceInteractionSessionService → L12
    override onNewSession() → L14
  class VessenceVoiceInteractionSession → L24
    override onShow() → L27

## android:.../voice/VoiceController.kt (336 lines)
  class VoiceState → L27
  class VoiceController → L37
    isWaitingForReply() → L63
    setAlwaysListeningEnabled() → L72
    setTriggerPhrase() → L81
    startPushToTalk() → L86
    stopPushToTalk() → L94
    cancelListening() → L98
    startWakeWordListening() → L102
    onAssistantReply() → L113
    stopTts() → L134
    clearError() → L138
    release() → L142
    startListeningWithTimeout() → L148
    startWakeDetection() → L157
    suspend startCommandCapture() → L250
    override onResults() → L274
    override onPartialResults() → L280
    override onError() → L287
    override onReadyForSpeech() → L291
    override onBeginningOfSpeech() → L292
    override onRmsChanged() → L293
    override onBufferReceived() → L294
    override onEndOfSpeech() → L295
    override onEvent() → L296
    stopListening() → L323
    emitState() → L332

## android:.../voice/WakeWordBridge.kt (26 lines)
  object WakeWordBridge → L11
    signal() → L19
    consume() → L23

## android:.../voice/WakeWordVerifier.kt (118 lines)
  object WakeWordVerifier → L20
  interface VerificationCallback → L29
    onVerified() → L30
    onRejected() → L31
    onError() → L32
    verify() → L39
    override onResults() → L57
    override onPartialResults() → L73
    override onError() → L88
    override onReadyForSpeech() → L103
    override onBeginningOfSpeech() → L106
    override onRmsChanged() → L107
    override onBufferReceived() → L108
    override onEndOfSpeech() → L109
    override onEvent() → L112

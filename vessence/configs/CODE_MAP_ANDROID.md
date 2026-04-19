# Code Map — Android (Kotlin)
_Auto-generated on 2026-04-18 08:15 UTC by `generate_code_map.py`_

## android:.../ArticleReaderV2Activity.kt (241 lines)
  class ArticleReaderV2Activity → L36
    EXTRA_URL → L39
    override onCreate() → L52
    override onPageFinished() → L116
    override onReceivedError() → L126
    extractAndSpeak() → L139
    readAsset() → L171
    parseJsString() → L179
    cleanArticleText() → L184
    splitForTts() → L201
    flush() → L205
    articleExtractionJs() → L226
    override onDestroy() → L233

## android:.../CrashReporter.kt (118 lines)
  object CrashReporter → L17
    install() → L22
    uploadPendingCrash() → L44
    getLastCrash() → L61
    clearLastCrash() → L66
    buildReport() → L71
    sendToServer() → L104

## android:.../DiagnosticReporter.kt (224 lines)
  object DiagnosticReporter → L31
    init() → L40
    loadPending() → L56
    savePending() → L67
    enqueue() → L77
    drainPending() → L87
    postOne() → L95
    report() → L113
    wakeWordModelLoaded() → L154
    wakeWordModelFailed() → L161
    wakeWordDetected() → L168
    wakeWordScoreUpdate() → L172
    micPermissionState() → L180
    micInitFailed() → L186
    serviceEvent() → L190
    nonFatalError() → L198
    voiceFlow() → L219

## android:.../MainActivity.kt (508 lines)
  class MainActivity → L27
    launchStt() → L56
    override onResults() → L101
    override onError() → L123
    override onReadyForSpeech() → L151
    override onBeginningOfSpeech() → L163
    override onRmsChanged() → L164
    override onBufferReceived() → L165
    override onEndOfSpeech() → L166
    override onPartialResults() → L167
    override onEvent() → L175
    startAlwaysListeningGuarded() → L191
    restoreAlwaysListening() → L227
    override onResume() → L234
    override onPause() → L257
    override onCreate() → L264
    override onNewIntent() → L323
    handleSharedSummaryIntent() → L337
    handleWakeWordIntent() → L358
    handleNotificationIntent() → L382
    handleIncomingShareIntent() → L390
    requestNotificationPermissionIfNeeded() → L423
    requestPhoneToolsPermissionsIfNeeded() → L442
    promptNotificationListenerIfNeeded() → L461
    override onDestroy() → L494

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

## android:.../ShareReceiverActivity.kt (253 lines)
  class ShareReceiverActivity → L34
    override onCreate() → L36
    extractUrl() → L83
    summarizeNowV2() → L88
    summarizeNow() → L100
    addToBriefing() → L152
  object ShareSummarizer → L194
    postSummaryReady() → L201
    postSummaryFailed() → L229
    ensureChannel() → L242

## android:.../SharedIntentState.kt (30 lines)
  object SharedIntentState → L11
    setSharedUris() → L18
    setSharedText() → L22
    clear() → L26

## android:.../SttResultBus.kt (32 lines)
  object SttResultBus → L16
    postResult() → L23

## android:.../VessencesApp.kt (257 lines)
  @Composable VessencesApp() → L49
  @Composable AuthenticatedApp() → L73
  @Composable EssenceViewRouter() → L203
  @Composable EssencePlaceholderView() → L217

## android:.../contacts/ContactsResolver.kt (182 lines)
  object ContactsResolver → L21
  class Contact → L24
  class ResolveResult → L32
  class Single → L34
  class Multiple → L37
  object PermissionDenied → L40
  object None → L43
    suspend findCallable() → L62
    suspend resolveExact() → L155
    hasReadContactsPermission() → L175

## android:.../contacts/ContactsSyncManager.kt (175 lines)
  object ContactsSyncManager → L20
    suspend syncIfNeeded() → L31
    suspend forceSync() → L60
    suspend queryAllContacts() → L77
    suspend uploadContacts() → L161
    hasPermission() → L172

## android:.../contacts/SmsSyncManager.kt (263 lines)
  object SmsSyncManager → L31
    suspend backfillIfNeeded() → L45
    suspend pushNewMessages() → L78
    suspend forceSync() → L108
    suspend querySmsSince() → L141
    buildNumberToNameCache() → L188
    suspend uploadMessages() → L211
    normalizeNumber() → L225
    startPeriodicSync() → L241
    hasPermission() → L260

## android:.../data/api/ApiClient.kt (116 lines)
  object ApiClient → L17
    init() → L26
    getOkHttpClient() → L79
    getCookieStore() → L80
    getVaultBaseUrl() → L81
    getJaneBaseUrl() → L82
    getJaneRetrofit() → L83
    getAuthenticatedImageLoader() → L87
    clearSession() → L110
    ensureTrailingSlash() → L114

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

## android:.../data/api/JaneApi.kt (22 lines)
  interface JaneApi → L7
    suspend janeChat() → L9
    suspend endSession() → L12
    suspend getAnnouncements() → L15
    suspend syncContacts() → L18
    suspend syncMessages() → L21

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

## android:.../data/repository/AnnouncementPoller.kt (104 lines)
  class AnnouncementPoller → L13
  class ProgressBubble → L17
    start() → L29
    stop() → L41
    suspend poll() → L47
    handleDeviceCommand() → L88

## android:.../data/repository/AuthRepository.kt (147 lines)
  class AuthRepository → L19
    suspend checkAuth() → L25
    isServerDown() → L39
    suspend signInWithGoogle() → L64
    suspend logout() → L140

## android:.../data/repository/ChatRepository.kt (162 lines)
  class UploadResult → L28
  class ChatRepository → L35
    suspend uploadFile() → L42
    streamChat() → L95
    initSession() → L134
    suspend endJaneSession() → L157

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

## android:.../notifications/NotificationSafety.kt (119 lines)
  object NotificationSafety → L21
    MAX_BODY_CHARS → L24
    OTP_REGEX → L45
    isPlaceholderBody() → L58
    looksLikeOtp() → L67
    isPhoneLocked() → L70
    isListenerEnabled() → L86
    filterSafe() → L109

## android:.../notifications/RecentMessagesBuffer.kt (83 lines)
  object RecentMessagesBuffer → L16
  class Entry → L29
    record() → L58
    snapshot() → L73
    size() → L77
    clear() → L80

## android:.../notifications/VessenceNotificationListener.kt (198 lines)
  class VessenceNotificationListener → L33
    override onListenerConnected() → L35
    override onListenerDisconnected() → L42
    override onNotificationPosted() → L55
    handlePosted() → L63
    extractMessages() → L93
    snapshotActiveMessages() → L162
    setLive() → L194

## android:.../tools/ActionQueue.kt (90 lines)
  class ActionQueue → L24
    attachTts() → L34
    suspend speak() → L44
    suspend startActivity() → L66
    suspend fence() → L83

## android:.../tools/ClientToolCall.kt (79 lines)
  class ClientToolCall → L16
  class ToolActionStatus → L29
  object Requested → L31
  class Running → L34
  class Completed → L37
  class CompletedWithData → L45
  class Failed → L48
  object Cancelled → L51
  class NeedsUser → L60
  class ToolResult → L72

## android:.../tools/ClientToolDispatcher.kt (401 lines)
  class ClientToolDispatcher → L40
    register() → L74
    registerAlias() → L83
    dispatchRaw() → L92
    dispatch() → L105
    parseCall() → L179
    toToolResult() → L209
  class SeenEntry → L229
    pruneSeen() → L231
    isDuplicate() → L240
    recordSeen() → L248
    pruneSharedPrefsOnce() → L265
    isFeatureEnabled() → L288
    shutdown() → L299
    reportHandlerDiagnostic() → L313
  object PendingToolResultBuffer → L358
    record() → L368
    suspend awaitAndDrainAll() → L378
    drainAll() → L391
    isEmpty() → L400

## android:.../tools/ClientToolHandler.kt (40 lines)
  interface ClientToolHandler → L22
    suspend handle() → L35

## android:.../tools/ContactsCallHandler.kt (98 lines)
  object ContactsCallHandler → L33
    suspend handle() → L38
    hasCallPermission() → L89

## android:.../tools/ContactsSmsHandler.kt (431 lines)
  object ContactsSmsHandler → L41
    ALIASES → L46
    sanitizeBody() → L79
    stripToolMarkers() → L110
    addSignature() → L185
  class PendingDraft → L191
  class DraftPreview → L202
    suspend handle() → L211
    suspend openDraft() → L224
    suspend updateDraft() → L267
    suspend commitDraft() → L292
    suspend cancelDraft() → L360
    suspend sendDirect() → L382
    isExpired() → L421
    hasSendSmsPermission() → L424

## android:.../tools/DeviceSpeakTimeHandler.kt (41 lines)
  object DeviceSpeakTimeHandler → L19
    suspend handle() → L25

## android:.../tools/JsonExtensions.kt (63 lines)
  JsonElement() → L25
  JsonElement() → L41
  JsonObject() → L60

## android:.../tools/MessagesFetchUnreadHandler.kt (113 lines)
  object MessagesFetchUnreadHandler → L30
    suspend handle() → L38

## android:.../tools/MessagesReadInboxHandler.kt (275 lines)
  object MessagesReadInboxHandler → L34
    suspend handle() → L42
  class SmsMessage → L101
    queryInbox() → L117
    buildNumberToNameCache() → L203
    resolveContactNumbers() → L237
    normalizeNumber() → L270

## android:.../tools/MessagesReadRecentHandler.kt (74 lines)
  object MessagesReadRecentHandler → L24
    suspend handle() → L32

## android:.../tools/SyncForceSmsHandler.kt (64 lines)
  object SyncForceSmsHandler → L23
    suspend handle() → L29

## android:.../tools/TimerHandler.kt (339 lines)
  object TimerHandler → L31
    ALIASES → L34
    CHANNEL_ID → L40
    ACTION_FIRE → L41
    EXTRA_TIMER_ID → L42
    EXTRA_LABEL → L43
    suspend handle() → L45
    setTimer() → L58
    cancelAll() → L110
    deleteTimer() → L140
    listTimers() → L199
    readBook() → L223
    appendToBook() → L226
    pruneExpired() → L234
    removeFromBook() → L247
    ensureChannel() → L258
  class TimerFireReceiver → L279
    override onReceive() → L280
    override onStart() → L299
    override onDone() → L300
    override onError() → L304

## android:.../ui/auth/LoginScreen.kt (150 lines)
  @Composable LoginScreen() → L31

## android:.../ui/auth/LoginViewModel.kt (50 lines)
  class LoginViewModel → L13
    signIn() → L29
    logout() → L41
    clearError() → L47

## android:.../ui/briefing/BriefingScreen.kt (1080 lines)
  @Composable BriefingScreen() → L97
  @Composable TopBar() → L415
  @Composable HistorySheet() → L486
  @Composable TopicChips() → L545
  @Composable ArticleGrid() → L588
  @Composable ArticleCard() → L621
  @Composable ArticleDetailSheet() → L852
  formatSourceLine() → L1040
  formatTimeAgo() → L1047

## android:.../ui/briefing/BriefingViewModel.kt (569 lines)
  class BriefingUiState → L29
  class BriefingViewModel → L50
    refresh() → L82
    fetchArchiveDates() → L127
    loadArchive() → L148
    clearArchive() → L180
    selectCategory() → L185
    toggleArticleExpanded() → L189
    getFilteredArticles() → L196
    dismissArticle() → L207
    getImageUrl() → L230
    speakArticle() → L236
    suspend playAudioFile() → L260
    suspend tryPlayServerAudio() → L291
    stopSpeaking() → L337
    readAll() → L353
    loadCachedArticles() → L374
    saveCachedArticles() → L393
    suspend fetchArticles() → L404
    suspend fetchTopics() → L424
    saveArticle() → L438
    unsaveArticle() → L465
    isArticleSaved() → L483
    toggleSavedView() → L485
    openSavedCategory() → L491
    loadSavedArticles() → L495
    fetchSavedArticleIds() → L523
    fetchSavedCategories() → L544
    override onCleared() → L564

## android:.../ui/chat/AttachmentSheet.kt (255 lines)
  @Composable AttachmentSheet() → L46

## android:.../ui/chat/ChatInputRow.kt (441 lines)
  isConversationEndPhrase() → L110
  @Composable ChatInputRow() → L133
    launchSpeechToText() → L205

## android:.../ui/chat/ChatMessageList.kt (68 lines)
  @Composable ChatMessageList() → L22

## android:.../ui/chat/ChatScreen.kt (557 lines)
  @Composable ChatScreen() → L66
    hasMicPermission() → L122
  @Composable ChatHeader() → L333
  @Composable LiveActivityBanner() → L422
  @Composable VoiceStatusBanner() → L459
  @Composable ErrorBanner() → L526

## android:.../ui/chat/ChatViewModel.kt (1484 lines)
  class PendingMessage → L35
  class ChatUiState → L41
  class ChatViewModel → L59
    removeTrailingPartialAwaitingMarker() → L115
    stripAssistantTags() → L126
    assistantTextForDisplay() → L134
    assistantTextForSpeech() → L143
    extractedSpokenBlock() → L156
    acquireStreamWakeLock() → L159
    releaseStreamWakeLock() → L168
    consumeMusicPlayRequest() → L176
    override onReceive() → L211
    initSession() → L333
    sendMessage() → L382
    cancelCurrentResponse() → L409
    executeSend() → L430
    FIRE_AND_FORGET → L740
    isConversationEnding() → L954
    onSendComplete() → L971
    processNextInQueue() → L1106
    clearError() → L1116
    dismissUpdate() → L1120
    installUpdate() → L1124
    toggleTts() → L1131
    stopSpeaking() → L1141
    speakText() → L1150
    speakIfEnabled() → L1156
    suspend tryServerTts() → L1167
    autoListenAfterTts() → L1229
    endVoiceConversation() → L1243
    isConversationEndPhrase() → L1259
    showSystemMessage() → L1281
    clearSession() → L1290
    setAlwaysListeningEnabled() → L1303
    syncVoicePreferences() → L1310
    clearWakeWordTrigger() → L1314
    triggerWakeWord() → L1319
    startPushToTalk() → L1324
    stopPushToTalk() → L1328
    cancelListening() → L1332
    stopListeningAndReturnToWakeWord() → L1337
    clearVoiceError() → L1346
    updateAiMessage() → L1350
    switchProvider() → L1378
    suspend prependPendingToolResults() → L1441
    override onCleared() → L1467

## android:.../ui/chat/ChatViewModelFactory.kt (24 lines)
  class ChatViewModelFactory → L9

## android:.../ui/chat/EndPhraseDetector.kt (90 lines)
  object EndPhraseDetector → L9
    isEndPhrase() → L68

## android:.../ui/chat/JaneChatScreen.kt (766 lines)
  @Composable JaneChatScreen() → L70
  @Composable JaneTopBar() → L194
  @Composable UpdateBanner() → L233
  @Composable ChatInputBar() → L288
    launchSpeechRecognition() → L428

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

## android:.../ui/settings/SystemArchitectureScreen.kt (574 lines)
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
  @Composable ProviderSwitchContent() → L491
  @Composable DockerContent() → L509
  @Composable CronContent() → L531
  @Composable SecurityContent() → L551

## android:.../ui/settings/TtsVoicePicker.kt (160 lines)
  @Composable TtsVoicePickerSheet() → L33

## android:.../ui/theme/ThemePreferences.kt (36 lines)
  object ThemePreferences → L8
    init() → L15
    toggleTheme() → L20
    setDarkMode() → L29

## android:.../ui/theme/VessenceTheme.kt (58 lines)
  @Composable VessenceTheme() → L47

## android:.../ui/vault/FileViewerScreen.kt (245 lines)
  @Composable FileViewerScreen() → L39
  syncCookiesToWebView() → L228

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

## android:.../ui/worklog/WorkLogScreen.kt (137 lines)
  @Composable WorkLogScreen() → L38
    override shouldOverrideUrlLoading() → L93
  syncCookiesToWebView() → L121

## android:.../util/BriefingAudioCache.kt (143 lines)
  object BriefingAudioCache → L19
    getCacheDir() → L24
    isOnWifi() → L30
    getCachedFile() → L38
  class ServerBusyException → L52
    suspend downloadToCache() → L54
    suspend prefetchAll() → L108
    cleanupOldFiles() → L130

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

## android:.../util/Constants.kt (27 lines)
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
    PREF_PHONE_TOOLS_ENABLED → L26

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

## android:.../voice/AlwaysListeningService.kt (632 lines)
  class AlwaysListeningService → L36
    ACTION_STOP → L41
    start() → L69
    stop() → L91
    override onReceive() → L113
    override onCreate() → L134
    startForegroundWithPlaceholder() → L164
    override onStartCommand() → L183
    override onBind() → L219
    override onDestroy() → L221
    createNotificationChannel() → L257
    buildListeningNotification() → L276
    acquireWakeLock() → L303
    releaseWakeLock() → L313
    pauseListening() → L319
    resumeListening() → L340
    isInCall() → L347
    isMediaPlaying() → L356
    startListeningLoop() → L365
    runWakeWordDetection() → L426
    CONFIRMATION_FRAMES → L485
    onWakeWordDetected() → L554

## android:.../voice/AndroidTtsManager.kt (110 lines)
  class AndroidTtsManager → L15
    override onStart() → L27
    override onDone() → L29
    override onError() → L34
    override onError() → L38
    override onStop() → L46
    override onInit() → L53
    suspend speak() → L64
    stop() → L79
    shutdown() → L95
    suspend awaitReady() → L102

## android:.../voice/HybridTtsManager.kt (75 lines)
  class HybridTtsManager → L14
    USE_SERVER_TTS → L23
    ensureWarm() → L35
    suspend speak() → L41
    stop() → L66
    shutdown() → L71

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

## android:.../voice/SentenceTtsQueue.kt (214 lines)
  class SentenceTtsQueue → L23
    getBaseUrl() → L32
    checkWarm() → L55
    startPlayback() → L70
    submitSentence() → L92
    finishSubmitting() → L103
    suspend awaitCompletion() → L110
    stop() → L114
    generateWav() → L126
    suspend playWav() → L163
    escapeJson() → L199

## android:.../voice/ServerTtsPlayer.kt (264 lines)
  class ServerTtsPlayer → L28
    getBaseUrl() → L41
    isModelWarm() → L60
    triggerWarmUp() → L82
    ensureWarm() → L112
    suspend speak() → L124
    stop() → L196
    suspend playWavFile() → L206
    escapeJson() → L249

## android:.../voice/VessenceVoiceInteractionService.kt (35 lines)
  class VessenceVoiceInteractionService → L14
    override onReady() → L20
    override onShutdown() → L30

## android:.../voice/VessenceVoiceInteractionSessionService.kt (41 lines)
  class VessenceVoiceInteractionSessionService → L12
    override onNewSession() → L14
  class VessenceVoiceInteractionSession → L24
    override onShow() → L27

## android:.../voice/VoiceController.kt (358 lines)
  class VoiceState → L27
  class VoiceController → L37
    isWaitingForReply() → L66
    setAlwaysListeningEnabled() → L75
    setTriggerPhrase() → L84
    startPushToTalk() → L89
    stopPushToTalk() → L97
    cancelListening() → L101
    startWakeWordListening() → L105
    onAssistantReply() → L116
    stopTts() → L144
    clearError() → L148
    release() → L152
    startListeningWithTimeout() → L160
    startWakeDetection() → L169
    suspend startCommandCapture() → L269
    override onResults() → L294
    override onPartialResults() → L300
    override onError() → L307
    override onReadyForSpeech() → L311
    override onBeginningOfSpeech() → L312
    override onRmsChanged() → L313
    override onBufferReceived() → L314
    override onEndOfSpeech() → L315
    override onEvent() → L316
    stopListening() → L343
    emitState() → L354

## android:.../voice/WakeWordBridge.kt (39 lines)
  object WakeWordBridge → L11
    signal() → L32
    consume() → L36

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

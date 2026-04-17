# Code Map — Web Frontend
_Auto-generated on 2026-04-17 08:15 UTC by `generate_code_map.py`_

## vault_web/templates/jane.html (2469 lines)
  setChatSize() → L453
  setStepSize() → L457
  formatStatusEntry() → L920
  async send() → L954
  setResponseMode() → L962
  enqueueMessage() → L971
  moveQueueItem() → L984
  removeQueueItem() → L993
  async processQueue() → L1008
  async consumeStream() → L1094
  async requestJaneFallback() → L1128
  async readJaneError() → L1171
  applyStreamEvent() → L1190
  event.type === 'heartbeat' → L1218
  event.type === 'offloaded' → L1220
  event.type === 'model' → L1231
  event.type === 'ack' → L1235
  event.type === 'status' → L1244
  event.type === 'permission_request' → L1252
  event.type === 'thought' → L1262
  event.type === 'tool_use' → L1270
  event.type === 'tool_result' → L1278
  event.type === 'delta' → L1285
  event.type === 'done' → L1310
  event.type === 'error' → L1335
  event.type === 'provider_error' → L1343
  event.type === 'error' → L1367
  event.type === 'conversation_end' → L1373
  event.type === 'done' → L1378
  _previousBubbleVisible() → L1381
  _initScrollTracker() → L1393
  scrollBottom() → L1395
  formatMessage() → L1412
  _renderMath() → L1534
  hasMathPreview() → L1542
  autoResize() → L1544
  async onJaneFilePick() → L1551
  openJanePicker() → L1558
  isImageUpload() → L1569
  async collectJaneUploadDescriptions() → L1573
  async uploadJaneFiles() → L1594
  removeJaneAttachment() → L1630
  buildJaneFileContext() → L1634
  async registerNotifications() → L1643
  async toggleNotifications() → L1653
  async notifyReply() → L1675
  async fetchAnnouncements() → L1696
  toggleTtsMute() → L1736
  toggleMic() → L1745
  _startMicListening() → L1756
  _stopMicListening() → L1795
  speakText() → L1803
  stopSpeech() → L1824
  resetSpeechState() → L1832
  async respondPermission() → L1850
  async checkPendingPermissions() → L1873
  focusInput() → L1893
  endSession() → L1897
  clearSession() → L1905
  copyText() → L1917
  async switchProvider() → L1931
  async _runProviderAuth() → L1974
  async loadModelSettings() → L2015
  async saveModelSettings() → L2033
  resetModelDefaults() → L2055
  cancelResponse() → L2059
  async checkHealth() → L2076
  init() → L2094
  async loadActiveEssence() → L2149
  async activateEssenceAndInit() → L2166
  async deactivateEssence() → L2202
  async initSession() → L2219
  event.type === 'status' → L2275
  event.type === 'done' → L2278
  async startLiveListener() → L2299
  async toggle() → L2378
  async refresh() → L2382
  async switchTo() → L2392
  init() → L2416
  async toggle() → L2426
  async fetchItems() → L2436
  async toggle() → L2449
  async fetchItems() → L2459

## vault_web/templates/app.html (1969 lines)
  setSize() → L750
  event.type === 'status' → L1431
  event.type === 'done' → L1433
  event.type === 'error' → L1437

## vault_web/templates/briefing.html (1361 lines)
  topicColor() → L826
  async init() → L835
  async loadArticles() → L866
  async loadTopics() → L902
  async addTopic() → L916
  async deleteTopic() → L940
  async toggleDismiss() → L956
  async expandArticle() → L970
  async triggerFetch() → L987
  async searchArticles() → L1001
  playArticleAudio() → L1020
  _startAudioPlayback() → L1039
  _browserTTSInPlayer() → L1066
  toggleAudioPlayback() → L1101
  closeAudioPlayer() → L1129
  switchAudioType() → L1136
  async saveArticleToCategory() → L1148
  async loadSavedCategories() → L1171
  async toggleSavedView() → L1184
  async loadSavedArticles() → L1191
  playSavedArticleAudio() → L1205
  async unsaveArticle() → L1214
  _browserTTS() → L1231
  readAllSummaries() → L1254
  _readNext() → L1264
  stopSpeaking() → L1296
  timeAgo() → L1304
  toggle() → L1325
  async fetchItems() → L1329
  toggle() → L1344
  async fetchItems() → L1348

## vault_web/templates/tax_accountant.html (735 lines)
  init() → L358
  _initScrollTracker() → L362
  scrollBottom() → L371
  autoResize() → L379
  onFilePick() → L387
  handleDrop() → L395
  async uploadFiles() → L403
  async send() → L425
  async processQueue() → L458
  async consumeStream() → L529
  applyStreamEvent() → L560
  event.type === 'heartbeat' → L571
  event.type === 'model' → L573
  event.type === 'ack' → L575
  event.type === 'status' → L577
  event.type === 'delta' → L585
  event.type === 'done' → L591
  event.type === 'error' → L600
  event.type === 'done' → L605
  formatMessage() → L609
  clearSession() → L628
  cancelResponse() → L637
  copyText() → L652
  speakText() → L665
  stopSpeech() → L682
  resetSpeechState() → L688
  toggle() → L699
  async fetchItems() → L703
  toggle() → L718
  async fetchItems() → L722

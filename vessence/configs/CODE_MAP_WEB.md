# Code Map — Web Frontend
_Auto-generated on 2026-04-05 01:57 UTC by `generate_code_map.py`_

## vault_web/templates/jane.html (2430 lines)
  setChatSize() → L443
  setStepSize() → L447
  formatStatusEntry() → L909
  async send() → L943
  setResponseMode() → L951
  enqueueMessage() → L960
  moveQueueItem() → L973
  removeQueueItem() → L982
  async processQueue() → L997
  async consumeStream() → L1083
  async requestJaneFallback() → L1117
  async readJaneError() → L1160
  applyStreamEvent() → L1179
  event.type === 'heartbeat' → L1207
  event.type === 'offloaded' → L1209
  event.type === 'model' → L1220
  event.type === 'ack' → L1224
  event.type === 'status' → L1233
  event.type === 'permission_request' → L1241
  event.type === 'thought' → L1251
  event.type === 'tool_use' → L1259
  event.type === 'tool_result' → L1267
  event.type === 'delta' → L1274
  event.type === 'done' → L1299
  event.type === 'provider_error' → L1324
  event.type === 'error' → L1348
  event.type === 'done' → L1354
  _previousBubbleVisible() → L1357
  _initScrollTracker() → L1369
  scrollBottom() → L1371
  formatMessage() → L1388
  _renderMath() → L1510
  hasMathPreview() → L1518
  autoResize() → L1520
  async onJaneFilePick() → L1527
  openJanePicker() → L1534
  isImageUpload() → L1545
  async collectJaneUploadDescriptions() → L1549
  async uploadJaneFiles() → L1570
  removeJaneAttachment() → L1606
  buildJaneFileContext() → L1610
  async registerNotifications() → L1619
  async toggleNotifications() → L1629
  async notifyReply() → L1651
  async fetchAnnouncements() → L1672
  toggleTtsMute() → L1712
  toggleMic() → L1721
  _startMicListening() → L1732
  _stopMicListening() → L1771
  speakText() → L1779
  stopSpeech() → L1800
  resetSpeechState() → L1806
  async respondPermission() → L1811
  async checkPendingPermissions() → L1834
  focusInput() → L1854
  endSession() → L1858
  clearSession() → L1866
  copyText() → L1878
  async switchProvider() → L1892
  async _runProviderAuth() → L1935
  async loadModelSettings() → L1976
  async saveModelSettings() → L1994
  resetModelDefaults() → L2016
  cancelResponse() → L2020
  async checkHealth() → L2037
  init() → L2055
  async loadActiveEssence() → L2110
  async activateEssenceAndInit() → L2127
  async deactivateEssence() → L2163
  async initSession() → L2180
  event.type === 'status' → L2236
  event.type === 'done' → L2239
  async startLiveListener() → L2260
  async toggle() → L2339
  async refresh() → L2343
  async switchTo() → L2353
  init() → L2377
  async toggle() → L2387
  async fetchItems() → L2397
  async toggle() → L2410
  async fetchItems() → L2420

## vault_web/templates/app.html (1969 lines)
  setSize() → L750
  event.type === 'status' → L1431
  event.type === 'done' → L1433
  event.type === 'error' → L1437

## vault_web/templates/briefing.html (1251 lines)
  topicColor() → L746
  async init() → L755
  async loadArticles() → L760
  async loadTopics() → L791
  async addTopic() → L805
  async deleteTopic() → L829
  async toggleDismiss() → L845
  async expandArticle() → L859
  async triggerFetch() → L876
  async searchArticles() → L890
  playArticleAudio() → L908
  _startAudioPlayback() → L927
  _browserTTSInPlayer() → L954
  toggleAudioPlayback() → L989
  closeAudioPlayer() → L1017
  switchAudioType() → L1024
  async saveArticleToCategory() → L1036
  async loadSavedCategories() → L1059
  async toggleSavedView() → L1072
  async loadSavedArticles() → L1079
  playSavedArticleAudio() → L1095
  async unsaveArticle() → L1104
  _browserTTS() → L1121
  readAllSummaries() → L1144
  _readNext() → L1154
  stopSpeaking() → L1186
  timeAgo() → L1194
  toggle() → L1215
  async fetchItems() → L1219
  toggle() → L1234
  async fetchItems() → L1238

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

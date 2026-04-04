# Code Map — Web Frontend
_Auto-generated on 2026-04-03 08:15 UTC by `generate_code_map.py`_

## vault_web/templates/jane.html (2432 lines)
  setChatSize() → L443
  setStepSize() → L447
  formatStatusEntry() → L917
  async send() → L951
  setResponseMode() → L959
  enqueueMessage() → L968
  moveQueueItem() → L981
  removeQueueItem() → L990
  async processQueue() → L1005
  async consumeStream() → L1091
  async requestJaneFallback() → L1125
  async readJaneError() → L1168
  applyStreamEvent() → L1187
  event.type === 'heartbeat' → L1215
  event.type === 'offloaded' → L1217
  event.type === 'model' → L1228
  event.type === 'ack' → L1232
  event.type === 'status' → L1235
  event.type === 'permission_request' → L1243
  event.type === 'thought' → L1253
  event.type === 'tool_use' → L1261
  event.type === 'tool_result' → L1269
  event.type === 'delta' → L1276
  event.type === 'done' → L1301
  event.type === 'provider_error' → L1326
  event.type === 'error' → L1350
  event.type === 'done' → L1356
  _previousBubbleVisible() → L1359
  _initScrollTracker() → L1371
  scrollBottom() → L1373
  formatMessage() → L1390
  _renderMath() → L1512
  hasMathPreview() → L1520
  autoResize() → L1522
  async onJaneFilePick() → L1529
  openJanePicker() → L1536
  isImageUpload() → L1547
  async collectJaneUploadDescriptions() → L1551
  async uploadJaneFiles() → L1572
  removeJaneAttachment() → L1608
  buildJaneFileContext() → L1612
  async registerNotifications() → L1621
  async toggleNotifications() → L1631
  async notifyReply() → L1653
  async fetchAnnouncements() → L1674
  toggleTtsMute() → L1714
  toggleMic() → L1723
  _startMicListening() → L1734
  _stopMicListening() → L1773
  speakText() → L1781
  stopSpeech() → L1802
  resetSpeechState() → L1808
  async respondPermission() → L1813
  async checkPendingPermissions() → L1836
  focusInput() → L1856
  endSession() → L1860
  clearSession() → L1868
  copyText() → L1880
  async switchProvider() → L1894
  async _runProviderAuth() → L1937
  async loadModelSettings() → L1978
  async saveModelSettings() → L1996
  resetModelDefaults() → L2018
  cancelResponse() → L2022
  async checkHealth() → L2039
  init() → L2057
  async loadActiveEssence() → L2112
  async activateEssenceAndInit() → L2129
  async deactivateEssence() → L2165
  async initSession() → L2182
  event.type === 'status' → L2238
  event.type === 'done' → L2241
  async startLiveListener() → L2262
  async toggle() → L2341
  async refresh() → L2345
  async switchTo() → L2355
  init() → L2379
  async toggle() → L2389
  async fetchItems() → L2399
  async toggle() → L2412
  async fetchItems() → L2422

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

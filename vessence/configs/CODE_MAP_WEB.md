# Code Map — Web Frontend
_Auto-generated on 2026-05-01 08:15 UTC by `generate_code_map.py`_

## vault_web/templates/jane.html (2609 lines)
  setChatSize() → L453
  setStepSize() → L457
  formatStatusEntry() → L984
  async send() → L1018
  setResponseMode() → L1026
  enqueueMessage() → L1035
  moveQueueItem() → L1048
  removeQueueItem() → L1057
  async processQueue() → L1072
  async consumeStream() → L1158
  async requestJaneFallback() → L1192
  async readJaneError() → L1235
  applyStreamEvent() → L1254
  event.type === 'heartbeat' → L1282
  event.type === 'offloaded' → L1284
  event.type === 'model' → L1295
  event.type === 'ack' → L1299
  event.type === 'status' → L1308
  event.type === 'permission_request' → L1316
  event.type === 'thought' → L1326
  event.type === 'tool_use' → L1334
  event.type === 'tool_result' → L1342
  event.type === 'delta' → L1349
  event.type === 'done' → L1374
  event.type === 'error' → L1399
  event.type === 'provider_error' → L1407
  event.type === 'error' → L1431
  event.type === 'conversation_end' → L1437
  event.type === 'done' → L1442
  _previousBubbleVisible() → L1445
  _initScrollTracker() → L1457
  scrollBottom() → L1459
  formatMessage() → L1476
  _renderMath() → L1598
  hasMathPreview() → L1606
  autoResize() → L1608
  async onJaneFilePick() → L1615
  openJanePicker() → L1622
  isImageUpload() → L1633
  async collectJaneUploadDescriptions() → L1637
  async uploadJaneFiles() → L1658
  removeJaneAttachment() → L1694
  buildJaneFileContext() → L1698
  async registerNotifications() → L1707
  async toggleNotifications() → L1717
  async notifyReply() → L1739
  async fetchAnnouncements() → L1760
  toggleTtsMute() → L1800
  toggleMic() → L1809
  _startMicListening() → L1820
  _stopMicListening() → L1859
  speakText() → L1867
  stopSpeech() → L1888
  resetSpeechState() → L1896
  async respondPermission() → L1914
  async checkPendingPermissions() → L1937
  focusInput() → L1957
  endSession() → L1961
  clearSession() → L1969
  copyText() → L1981
  async switchProvider() → L1995
  async _runProviderAuth() → L2038
  async loadModelSettings() → L2079
  async saveModelSettings() → L2097
  resetModelDefaults() → L2119
  async loadManagedUsersAdmin() → L2124
  toggleNewUserCapability() → L2140
  async createManagedUser() → L2146
  async deleteManagedUser() → L2175
  cancelResponse() → L2199
  async checkHealth() → L2216
  init() → L2234
  async loadActiveEssence() → L2289
  async activateEssenceAndInit() → L2306
  async deactivateEssence() → L2342
  async initSession() → L2359
  event.type === 'status' → L2415
  event.type === 'done' → L2418
  async startLiveListener() → L2439
  async toggle() → L2518
  async refresh() → L2522
  async switchTo() → L2532
  init() → L2556
  async toggle() → L2566
  async fetchItems() → L2576
  async toggle() → L2589
  async fetchItems() → L2599

## vault_web/templates/app.html (2106 lines)
  setSize() → L750
  event.type === 'status' → L1511
  event.type === 'done' → L1513
  event.type === 'error' → L1517

## vault_web/templates/briefing.html (1979 lines)
  topicColor() → L1193
  async init() → L1202
  async loadArticles() → L1233
  async loadTopics() → L1269
  async addTopic() → L1283
  async deleteTopic() → L1307
  startEditTopic() → L1323
  cancelEditTopic() → L1330
  async saveEditTopic() → L1337
  async toggleDismiss() → L1367
  async expandArticle() → L1381
  async triggerFetch() → L1398
  async searchArticles() → L1412
  playArticleAudio() → L1431
  _startAudioPlayback() → L1450
  _browserTTSInPlayer() → L1477
  toggleAudioPlayback() → L1512
  closeAudioPlayer() → L1540
  switchAudioType() → L1547
  async saveArticleToCategory() → L1559
  async loadSavedCategories() → L1582
  async toggleSavedView() → L1595
  async loadSavedArticles() → L1602
  async loadMarketplaceSearches() → L1617
  async openMarketplaceSearch() → L1632
  async loadMarketplaceSummary() → L1653
  async pullMarketplaceNow() → L1665
  openMarketplaceEditor() → L1705
  async saveMarketplaceEditor() → L1733
  async deleteMarketplaceSearch() → L1782
  async openMarketplaceListing() → L1799
  marketplaceImageUrl() → L1815
  playSavedArticleAudio() → L1823
  async unsaveArticle() → L1832
  _browserTTS() → L1849
  readAllSummaries() → L1872
  _readNext() → L1882
  stopSpeaking() → L1914
  timeAgo() → L1922
  toggle() → L1943
  async fetchItems() → L1947
  toggle() → L1962
  async fetchItems() → L1966

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

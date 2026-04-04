# Code Map — Web Frontend
_Auto-generated on 2026-03-27 08:15 UTC by `generate_code_map.py`_

## vault_web/templates/jane.html (1960 lines)
  formatStatusEntry() → L717
  async send() → L751
  setResponseMode() → L759
  enqueueMessage() → L764
  moveQueueItem() → L777
  removeQueueItem() → L786
  async processQueue() → L801
  async consumeStream() → L887
  async requestJaneFallback() → L921
  async readJaneError() → L964
  applyStreamEvent() → L983
  event.type === 'heartbeat' → L1011
  event.type === 'offloaded' → L1013
  event.type === 'model' → L1024
  event.type === 'ack' → L1028
  event.type === 'status' → L1031
  event.type === 'permission_request' → L1039
  event.type === 'thought' → L1049
  event.type === 'tool_use' → L1057
  event.type === 'tool_result' → L1065
  event.type === 'delta' → L1072
  event.type === 'done' → L1081
  event.type === 'error' → L1104
  event.type === 'done' → L1110
  _initScrollTracker() → L1115
  scrollBottom() → L1126
  formatMessage() → L1144
  _renderMath() → L1249
  hasMathPreview() → L1257
  autoResize() → L1259
  async onJaneFilePick() → L1266
  openJanePicker() → L1273
  isImageUpload() → L1284
  async collectJaneUploadDescriptions() → L1288
  async uploadJaneFiles() → L1309
  removeJaneAttachment() → L1345
  buildJaneFileContext() → L1349
  async registerNotifications() → L1358
  async toggleNotifications() → L1368
  async notifyReply() → L1390
  async fetchAnnouncements() → L1411
  speakText() → L1449
  stopSpeech() → L1470
  resetSpeechState() → L1476
  async respondPermission() → L1481
  async checkPendingPermissions() → L1504
  focusInput() → L1524
  endSession() → L1528
  clearSession() → L1536
  copyText() → L1548
  async loadModelSettings() → L1562
  async saveModelSettings() → L1579
  resetModelDefaults() → L1601
  cancelResponse() → L1605
  async checkHealth() → L1622
  init() → L1640
  async loadActiveEssence() → L1690
  async activateEssenceAndInit() → L1707
  async deactivateEssence() → L1743
  async initSession() → L1760
  event.type === 'status' → L1816
  event.type === 'done' → L1819
  async startLiveListener() → L1840
  async toggle() → L1917
  async fetchItems() → L1927
  async toggle() → L1940
  async fetchItems() → L1950

## vault_web/templates/app.html (1933 lines)
  setSize() → L714
  event.type === 'status' → L1395
  event.type === 'done' → L1397
  event.type === 'error' → L1401

## vault_web/templates/briefing.html (763 lines)
  topicColor() → L462
  async init() → L471
  async loadArticles() → L476
  async loadTopics() → L492
  async addTopic() → L506
  async deleteTopic() → L530
  async toggleDismiss() → L546
  async expandArticle() → L560
  async triggerFetch() → L577
  async searchArticles() → L591
  async playArticleAudio() → L609
  _browserTTS() → L635
  readAllSummaries() → L658
  _readNext() → L667
  stopSpeaking() → L698
  timeAgo() → L706
  toggle() → L727
  async fetchItems() → L731
  toggle() → L746
  async fetchItems() → L750

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

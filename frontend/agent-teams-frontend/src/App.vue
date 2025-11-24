<template>
  <div>
    <!-- Top Centered Title -->
    <div class="main-title">Hierarchical Agent Teams</div>
    <div class="container">
      <!-- Left Panel: User Input + File List -->
      <div class="left-panel">
        <!-- User Input Area -->
        <section class="input-area card glass">
          <h2 class="area-title"><span class="icon">💬</span>User Input</h2>
          <textarea
            v-model="userInput"
            placeholder="Please enter content"
            rows="3"
            class="input-box"
          />
          <button class="main-btn input-submit-btn" @click="handleSubmit">
            <span class="btn-icon">🚀</span>Submit
          </button>
        </section>

        <!-- File Generation Area -->
        <section class="file-list card glass">
          <div class="file-header">
            <h2 class="area-title"><span class="icon">🗂️</span>File Generation Area</h2>
            <button class="refresh-btn" @click="refreshFiles">Refresh Files</button>
          </div>
          <transition-group name="fade" tag="ul" class="file-ul">
            <li v-for="file in files" :key="file.name" class="file-li">
              <span class="file-icon">{{ getFileIcon(file.name) }}</span>
              <span>{{ file.name }}</span>
              <button class="download-btn" @click="downloadFile(file)">
                <span class="download-icon">⬇️</span> Download
              </button>
            </li>
          </transition-group>
        </section>
      </div>

      <!-- Right Panel: Flow Area -->
      <div class="right-panel">
        <section class="flow-area card glass">
          <div class="flow-header">
            <h2 class="area-title"><span class="icon">🔄</span>Flow Area</h2>
            <button class="clear-btn" @click="clearFlow">Clear</button>
            <button class="theme-btn" @click="toggleDarkMode">
              <span v-if="isDarkMode">🌞</span><span v-else>🌙</span>
            </button>
          </div>
          <div class="flow-content">
            <transition-group name="fade" tag="div">
              <div
                v-for="(msg, idx) in chatMessages"
                :key="idx"
                class="flow-msg"
                :class="{'user-msg': msg.team === 'user', 'system-msg': msg.team === 'system'}"
              >
                <div class="msg-header">
                  <span class="msg-meta">[{{ msg.timestamp }}]</span>
                  <span v-if="msg.avatar" class="avatar">{{ msg.avatar }}</span>
                  <span class="orange-id">{{ msg.sender === 'User' ? 'User Input' : msg.sender }}</span>
                </div>
                <div class="msg-content" v-html="msg.content"></div>
              </div>
            </transition-group>
            <div v-if="isWaiting" class="flow-msg loading-msg">
              <span class="dot dot1"></span>
              <span class="dot dot2"></span>
              <span class="dot dot3"></span>
              <span class="wait-text">Processing on backend...</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const userInput = ref('')
const isFinished = ref(false)
const files = ref([])
const chatMessages = ref([
  { team: 'system', sender: 'System', sender_id: 'system:default', avatar: '🤖', content: 'Welcome to the Flow Area', timestamp: getCurrentTime() }
])

let ws = null
const isWaiting = ref(false)
const isDarkMode = ref(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches)

function getCurrentTime() {
  const now = new Date()
  return now.toLocaleTimeString()
}

function getFileIcon(name) {
  const ext = name.split('.').pop().toLowerCase()
  if (['png', 'jpg', 'jpeg', 'gif', 'bmp', 'svg'].includes(ext)) return '🖼️'
  if (['pdf'].includes(ext)) return '📑'
  if (['doc', 'docx'].includes(ext)) return '📄'
  if (['xls', 'xlsx', 'csv'].includes(ext)) return '📊'
  if (['ppt', 'pptx'].includes(ext)) return '📈'
  if (['zip', 'rar', '7z', 'tar', 'gz'].includes(ext)) return '🗜️'
  if (['py', 'js', 'ts', 'java', 'c', 'cpp', 'cs', 'go', 'sh'].includes(ext)) return '💻'
  if (['txt', 'md'].includes(ext)) return '📃'
  return '📁'
}

function handleSubmit() {
  if (!userInput.value.trim()) return

  chatMessages.value = []

  chatMessages.value.push({
    team: 'user',
    sender: 'User',
    sender_id: 'user:input',
    avatar: '🧑',
    content: userInput.value,
    timestamp: getCurrentTime()
  })

  if (ws) ws.close()
  isWaiting.value = true

  const queryToSend = userInput.value  // 保存当前输入

  ws = new WebSocket("ws://localhost:8000/ws/stream")

  ws.onopen = () => {
    ws.send(JSON.stringify({ query: queryToSend, graph: "supervisor" }))
    // 插入一条空消息用于流式拼接
    chatMessages.value.push({
      team: 'system',
      sender: 'Agent',
      sender_id: 'bot',
      avatar: '🤖',
      content: '',
      timestamp: getCurrentTime()
    })
    userInput.value = ''   // 放到这里
  }

  ws.onmessage = (event) => {
    setTimeout(() => {
      try {
        const parsedData = JSON.parse(event.data)
        if (parsedData.event === "end") {
          isFinished.value = true
          refreshFiles()
          isWaiting.value = false
          ws.close()
          chatMessages.value.push({
            team: 'system',
            sender: 'System',
            sender_id: 'system:end',
            avatar: '✅',
            content: 'Task completed',
            timestamp: getCurrentTime()
          })
          return
        }
        if (parsedData.event === "error") {
          isWaiting.value = false
          chatMessages.value.push({
            team: 'system',
            sender: 'System',
            sender_id: 'system:error',
            avatar: '❗',
            content: 'Backend error: ' + parsedData.msg,
            timestamp: getCurrentTime()
          })
          ws.close()
          return
        }
        const content = parsedData.content || parsedData.response || ''
        const metadata = parsedData.metadata || {}
        const sender_id = metadata || 'bot'
        const sender_name = typeof sender_id === 'string'
          ? sender_id.split(':')[0]
          : 'Agent'
        const teamName = sender_name.split('_team')[0] || sender_name
        let avatar = '🤖'
        if (teamName === 'user') avatar = '🧑'
        else if (teamName === 'search') avatar = '🔍'
        else if (teamName === 'web_scraper') avatar = '🌐'
        else if (teamName === 'doc_writer') avatar = '✍️'
        else if (teamName === 'note_taker') avatar = '📝'
        else if (teamName === 'chart_generator') avatar = '📊'
        else if (teamName === 'supervisor') avatar = '🧑‍💼'
        else if (teamName === 'super_team') avatar = '👥'
        else if (teamName === 'writing_team') avatar = '📝'
        else if (teamName === 'research_team') avatar = '🔬'

        // 只追加到最后一个 sender_id/team 相同的消息上，否则新建
        const lastMsg = chatMessages.value[chatMessages.value.length - 1]
        if (
          lastMsg &&
          lastMsg.sender_id === sender_id &&
          lastMsg.team === teamName
        ) {
          lastMsg.content += content
          lastMsg.timestamp = getCurrentTime()
          // Vue3 响应式强制刷新
          chatMessages.value[chatMessages.value.length - 1] = { ...lastMsg }
        } else {
          chatMessages.value.push({
            team: teamName,
            sender: sender_name,
            sender_id: sender_id,
            avatar,
            content,
            timestamp: getCurrentTime()
          })
        }
      } catch (error) {
        chatMessages.value.push({
          team: 'system',
          sender: 'System',
          sender_id: 'system:error',
          avatar: '❗',
          content: error.message,
          timestamp: getCurrentTime()
        })
      }
    }, 0)
  }

  ws.onerror = (err) => {
    isWaiting.value = false
    chatMessages.value.push({
      team: 'system',
      sender: 'System',
      sender_id: 'system:error',
      avatar: '❗',
      content: 'WebSocket error: ' + (err?.message || ''),
      timestamp: getCurrentTime()
    })
    ws.close()
  }

  userInput.value = ''
}

function clearFlow() {
  chatMessages.value = [
    { team: 'system', sender: 'System', sender_id: 'system:default', avatar: '🤖', content: 'Welcome to the Flow Area', timestamp: getCurrentTime() }
  ]
}

function downloadFile(file) {
  const link = document.createElement('a')
  link.href = file.url
  link.download = file.name
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

function refreshFiles() {
  fetch('http://localhost:8000/files')
    .then(res => res.json())
    .then(data => {
      files.value = data.files
        .slice(0, 20)
        .map(name => ({
          name,
          url: `http://localhost:8000/download?file_name=${encodeURIComponent(name)}`
        }))
      chatMessages.value.push({
        team: 'system',
        sender: 'System',
        sender_id: 'system:refresh',
        avatar: '🔄',
        content: 'File list refreshed',
        timestamp: getCurrentTime()
      })
    })
    .catch(err => {
      chatMessages.value.push({
        team: 'system',
        sender: 'System',
        sender_id: 'system:error',
        avatar: '❗',
        content: 'Failed to refresh file list: ' + err.message,
        timestamp: getCurrentTime()
      })
    })
}

function toggleDarkMode() {
  isDarkMode.value = !isDarkMode.value
  document.documentElement.classList.toggle('dark', isDarkMode.value)
}

onMounted(() => {
  if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
      isDarkMode.value = e.matches
      document.documentElement.classList.toggle('dark', isDarkMode.value)
    })
  }
  refreshFiles()
})
</script>

<style scoped>
.main-title {
  text-align: center;
  font-size: 2.4rem;
  font-weight: bold;
  margin-top: 24px;
  margin-bottom: 24px;
  letter-spacing: 1.5px;
  color: #0050b3;
  background: linear-gradient(90deg, #0050b3 30%, #4f8cff 90%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
:root {
  --main-color: #0050b3;
  --main-color-dark: #001a33;
  --bg-card: #fff;
  --bg-card-dark: #1a2233;
  --border-radius: 22px;
  --box-shadow: 0 6px 32px 0 rgba(0,80,220,0.10), 0 1.5px 4px rgba(80,120,180,0.07);
  --box-shadow-hover: 0 12px 40px 0 rgba(0,80,220,0.18), 0 2px 8px rgba(80,120,180,0.14);
  --transition: 0.2s all;
  --flow-user: #e3f0ff;
  --flow-user-dark: #263f60;
  --flow-system: #f1f3f6;
  --flow-system-dark: #202a34;
  --font-color: #222;
  --font-color-dark: #e5eaf3;
}

body {
  background: linear-gradient(135deg, #e9f3ff 0%, #f4f6fa 60%, #f7faff 100%);
  color: var(--font-color);
  transition: background 0.2s, color 0.2s;
}
.dark body {
  background: linear-gradient(135deg, #1d2337 0%, #131722 100%);
  color: var(--font-color-dark);
}

.container {
  max-width: 1200px;
  margin: 40px auto;
  font-family: 'Segoe UI', Arial, sans-serif;
  display: flex;
  flex-direction: row;
  gap: 32px;
}

.left-panel, .right-panel {
  flex: 1 1 420px;
  display: flex;
  flex-direction: column;
  gap: 28px;
}
.right-panel { min-width: 370px; }
.card {
  background: var(--bg-card);
  border-radius: var(--border-radius);
  box-shadow: var(--box-shadow);
  padding: 24px 32px;
  transition: box-shadow 0.25s, transform 0.18s, background 0.2s, color 0.2s;
}
.card:hover {
  box-shadow: var(--box-shadow-hover);
  transform: translateY(-4px) scale(1.01);
}
.dark .card {
  background: var(--bg-card-dark);
  color: var(--font-color-dark);
}
.area-title {
  margin: 0 0 18px 0;
  font-size: 1.4rem;
  font-weight: 800;
  background: linear-gradient(90deg, #0050b3 20%, #4f8cff 80%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: 1px;
  display: flex;
  align-items: center;
  gap: 9px;
}
.icon {
  font-size: 1.25em;
  filter: drop-shadow(0 1px 2px #8bc4ff77);
}

.input-area { display: flex; flex-direction: column; gap: 12px; }
.input-box {
  width: 100%;
  padding: 16px;
  font-size: 1.12rem;
  border: 1px solid #d0d7de;
  border-radius: 14px;
  resize: vertical;
  margin-bottom: 8px;
  transition: border 0.2s;
  background: rgba(255,255,255,0.93);
}
.dark .input-box { background: rgba(30,35,45,0.93); border: 1px solid #333; color: #eee; }

.input-submit-btn, .refresh-btn, .clear-btn, .theme-btn, .download-btn {
  transition: background 0.23s, box-shadow 0.22s, transform 0.13s;
  box-shadow: 0 2px 8px rgba(0,80,220,0.08);
}
.input-submit-btn, .download-btn {
  background: linear-gradient(93deg, #4f8cff 0%, #0050b3 100%);
  color: #fff;
  border: none;
}
.input-submit-btn:hover, .download-btn:hover {
  background: linear-gradient(93deg, #0050b3 0%, #4f8cff 100%);
  transform: scale(1.05);
  box-shadow: 0 6px 18px rgba(0,80,220,0.14);
}
.input-submit-btn {
  align-self: flex-start;
  width: 160px;
  font-size: 1.18rem;
  padding: 12px 0;
  border-radius: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
}
.theme-btn {
  background: linear-gradient(120deg, #ffe59c 0%, #8bc4ff 100%);
  color: #333;
  padding: 7px 13px;
  font-size: 1.2rem;
}
.theme-btn:hover {
  background: linear-gradient(120deg, #8bc4ff 0%, #ffe59c 100%);
}
.clear-btn, .refresh-btn {
  background: #e7f1ff;
  color: var(--main-color);
  border: 1px solid #b6d4fe;
  border-radius: 8px;
  padding: 7px 18px;
  font-size: 1.01rem;
  font-weight: 600;
  cursor: pointer;
}
.clear-btn:hover, .refresh-btn:hover {
  background: #d0e3ff;
}

.file-list { margin-bottom: 0; }
.file-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.file-ul { list-style: none; padding: 0; margin: 0; }
.file-li {
  display: flex;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #f0f0f3;
  gap: 14px;
  border-radius: 14px;
  transition: background 0.2s;
}
.file-li:hover {
  background: #f3f7ff;
}
.file-icon {
  font-size: 1.35em;
  color: #5c6bc0;
  margin-right: 6px;
}

.download-btn {
  margin-left: auto;
  border-radius: 8px;
  padding: 10px 28px;
  font-size: 1.08rem;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
}
.download-icon { font-size: 1.2em; }

.flow-area { min-height: 180px; }
.flow-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  gap: 8px;
}
.flow-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.fade-enter-active, .fade-leave-active {
  transition: all 0.33s cubic-bezier(.4,2,.6,1);
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
  transform: translateY(16px) scale(0.98);
}

.flow-msg {
  align-self: flex-start;
  background: var(--flow-system);
  color: #255b90;
  padding: 10px 16px;
  border-radius: 18px;
  margin-bottom: 12px;
  font-size: 1.09rem;
  box-shadow: 0 1px 4px rgba(0,123,255,0.05);
  max-width: 82%;
  word-break: break-all;
  transition: background 0.2s, box-shadow 0.2s;
  animation: fadeinmsg 0.5s;
  display: flex;
  flex-direction: column;
  gap: 6px;
  border: 1.5px solid #c4d6ff;
  position: relative;
}
.flow-msg.user-msg { background: var(--flow-user); color: #1b3b70;}
.flow-msg.system-msg { background: #fffbe8; color: #4c4c1b; border-color: #ffe59c;}
.dark .flow-msg { background: var(--flow-system-dark); color: #aef; border-color: #35577b;}
.dark .flow-msg.user-msg { background: var(--flow-user-dark); color: #8bc4ff;}
.flow-msg.user-msg::before {
  content: "";
  position: absolute;
  left: -16px; top: 18px;
  border-width: 8px;
  border-style: solid;
  border-color: transparent var(--flow-user) transparent transparent;
}
.flow-msg.system-msg::before {
  content: "";
  position: absolute;
  left: -16px; top: 18px;
  border-width: 8px;
  border-style: solid;
  border-color: transparent #fffbe8 transparent transparent;
}
.dark .flow-msg.user-msg::before {
  border-color: transparent var(--flow-user-dark) transparent transparent;
}
.dark .flow-msg.system-msg::before {
  border-color: transparent var(--flow-system-dark) transparent transparent;
}
.msg-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}
.avatar {
  font-size: 1.3em;
  margin-right: 6px;
  border-radius: 50%;
  background: linear-gradient(135deg, #e9f3ff 40%, #8bc4ff 100%);
  box-shadow: 0 1px 6px rgba(90,130,180,0.09);
  padding: 2px 8px;
  color: #0050b3;
}
.msg-meta { color: #888; font-size: 0.95em; margin-right: 8px; }
.orange-id {
  font-size: 1.18em;
  color: orange;
  font-weight: bold;
  margin-right: 8px;
}
.msg-content {
  word-break: break-all;
}

.loading-msg {
  display: flex;
  align-items: center;
  gap: 5px;
  background: #fffbe8;
  color: #0050b3;
  font-weight: 500;
  border-radius: 16px;
  box-shadow: 0 1px 4px rgba(0,80,179,0.05);
  padding: 10px 16px;
  min-width: 120px;
  margin-bottom: 0;
  max-width: 80%;
  font-size: 1.08rem;
}
.dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-right: 2px;
  border-radius: 50%;
  background: #0050b3;
  opacity: 0.7;
  animation: blink 1s infinite;
}
.dot1 { animation-delay: 0s; }
.dot2 { animation-delay: 0.2s; }
.dot3 { animation-delay: 0.4s; }
@keyframes blink {
  0%, 80%, 100% { opacity: 0.7; }
  40% { opacity: 0.1; }
}
@keyframes fadeinmsg {
  from { opacity:0; transform: translateY(10px);}
  to { opacity:1; transform: translateY(0);}
}

/* Glass effect */
.glass {
  background: rgba(255,255,255,0.85);
  backdrop-filter: blur(14px) saturate(1.1);
  border: 1.5px solid rgba(60,120,255,0.12);
}
.dark .glass {
  background: rgba(34,40,60,0.85);
  border: 1.5px solid rgba(120,180,255,0.12);
}

@media (max-width: 900px) {
  .container { flex-direction: column; gap: 0; padding: 10px; }
  .left-panel, .right-panel { width: 100%; min-width: 0; flex: 1 1 100%; }
  .right-panel { min-width: 0;}
}

::-webkit-scrollbar {
  width: 8px;
  background: #f1f1f1;
}
::-webkit-scrollbar-thumb {
  background: #cfd8dc;
  border-radius: 8px;
}
.dark ::-webkit-scrollbar-thumb { background: #233; }
</style>
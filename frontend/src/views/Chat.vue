<template>
  <div class="chat-container">
    <div class="messages-container" ref="messagesContainer">
      <div
        v-for="(message, index) in displayMessages"
        :key="index"
        :class="'message ' + message.role"
      >
        <template v-if="isPropertyListing(message.content)">
          <div v-html="getMessageText(message.content)" class="message-text"></div>
          <div class="property-listings">
            <div class="property-grid">
              <div
                class="property-card"
                v-for="(property, pIndex) in message.content.properties"
                :key="pIndex"
                @click="onPropertyClick(property)"
              >
                <div class="property-details">
                  <h3>{{ property.address }}</h3>
                  <p class="price">{{ property.price }}</p>
                  <p>{{ property.beds }} beds | {{ property.baths }} baths | {{ property.sqft }} sqft</p>
                  <p class="description">{{ property.description }}</p>
                </div>
              </div>
            </div>
          </div>
        </template>
        <div v-else v-html="getMessageText(message.content)" class="message-text"></div>
      </div>
      <div v-if="isLoading" class="loading"></div>
    </div>

    <div class="input-container">
      <input
        type="text"
        v-model="newMessage"
        @keyup.enter="sendMessage"
        placeholder="Type your message..."
      />
      <button @click="sendMessage" :disabled="!canSendMessage()">Send</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUpdated, nextTick } from 'vue'
import { useRouter } from 'vue-router'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api'
const CHAT_STORAGE_KEY = 'chatMessages'
const COOLDOWN_PERIOD = 2000

const router = useRouter()
const messagesContainer = ref(null)
const messages = ref([])
const displayMessages = ref([])
const newMessage = ref('')
const isLoading = ref(false)
const lastMessageTime = ref(0)

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

function formatText(text) {
  let formatted = text.replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>')
  formatted = formatted.replace(/(\d+\.\s.*?)(\n(?!\d+\.|$)|$)/g, '<li>$1</li>')
  formatted = formatted.replace(/(<li>.*?<\/li>)+/g, '<ol>$&</ol>')
  return formatted
}

function canSendMessage() {
  const now = Date.now()
  return !isLoading.value && (!lastMessageTime.value || now - lastMessageTime.value >= COOLDOWN_PERIOD)
}

function isPropertyListing(content) {
  return content &&
    typeof content === 'object' &&
    'properties' in content &&
    Array.isArray(content.properties) &&
    content.properties.length > 0
}

function getMessageText(content) {
  if (typeof content === 'string') return formatText(content)
  if (content && typeof content === 'object' && content.text) return formatText(content.text)
  return ''
}

function saveMessages() {
  try {
    localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages.value))
  } catch (e) {
    console.error('Error saving messages to localStorage', e)
  }
}

function loadMessages() {
  try {
    const saved = localStorage.getItem(CHAT_STORAGE_KEY)
    if (saved) {
      messages.value = JSON.parse(saved)
      displayMessages.value = [...messages.value]
    }
  } catch (e) {
    console.error('Error loading messages from localStorage', e)
    messages.value = []
    displayMessages.value = []
  }
}

async function sendMessage() {
  if (!newMessage.value.trim() || !canSendMessage()) return

  lastMessageTime.value = Date.now()
  const userMessage = { role: 'user', content: newMessage.value }
  newMessage.value = ''

  messages.value.push(userMessage)
  displayMessages.value.push(userMessage)
  saveMessages()
  isLoading.value = true

  await nextTick()
  scrollToBottom()

  const formattedMessages = messages.value.map(msg => ({
    role: msg.role,
    content: typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content),
  }))

  try {
    const res = await fetch(`${API_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: formattedMessages }),
    })

    if (!res.ok) throw new Error(`HTTP ${res.status}`)

    const data = await res.json()
    isLoading.value = false

    if (!data || !data.response) {
      const errMsg = { role: 'assistant', content: 'Sorry, I received an empty response from the server. Please try again.' }
      messages.value.push(errMsg)
      displayMessages.value.push(errMsg)
    } else {
      const { text, properties } = data.response
      const assistantMessage = {
        role: 'assistant',
        content: properties && properties.length > 0 ? { text, properties } : text,
      }
      messages.value.push(assistantMessage)
      displayMessages.value.push(assistantMessage)
    }
  } catch {
    isLoading.value = false
    const errMsg = { role: 'assistant', content: 'Sorry, I encountered an error. Please try again.' }
    messages.value.push(errMsg)
    displayMessages.value.push(errMsg)
  }

  saveMessages()
  await nextTick()
  scrollToBottom()
}

function onPropertyClick(property) {
  router.push({ path: '/property-details', state: { property } })
}

onMounted(() => {
  loadMessages()
  if (messages.value.length === 0) {
    const initial = {
      role: 'assistant',
      content: 'Hello! I am your real estate assistant. I can help you with property information, mortgage calculations, and market trends. How can I assist you today?',
    }
    messages.value.push(initial)
    displayMessages.value.push(initial)
  }
  nextTick(scrollToBottom)
})

onUpdated(() => {
  scrollToBottom()
})
</script>

<style scoped>
.chat-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
  height: calc(100vh - 60px);
  display: flex;
  flex-direction: column;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  margin-bottom: 20px;
  padding: 20px;
  background: #f5f5f5;
  border-radius: 8px;
}

.input-container {
  position: sticky;
  bottom: 0;
  background: white;
  padding: 20px;
  border-top: 1px solid #eee;
  display: flex;
  gap: 10px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

input {
  flex: 1;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 16px;
}

button {
  padding: 10px 20px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}

button:hover {
  background-color: #0056b3;
}

button:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.message {
  margin-bottom: 10px;
  width: fit-content;
  max-width: 80%;
  min-width: 60px;
}

.user {
  margin-left: auto;
  background: #007bff;
  color: white;
  padding: 12px 16px;
  border-radius: 18px 18px 0 18px;
  word-wrap: break-word;
  white-space: pre-wrap;
}

.assistant {
  margin-right: auto;
  background: white;
  color: #333;
  padding: 12px 16px;
  border-radius: 18px 18px 18px 0;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  line-height: 1.5;
  font-size: 15px;
  word-wrap: break-word;
  white-space: pre-wrap;
}

.message-text {
  color: inherit;
  font-size: 16px;
  display: inline-block;
  width: 100%;
}

.message-text p {
  margin: 10px;
}

.message-text p:last-child {
  margin-bottom: 0;
}

.message-text strong {
  color: #1a1a1a;
  font-weight: 600;
}

.user .message-text strong {
  color: white;
  font-weight: 600;
}

.loading {
  display: flex;
  justify-content: center;
  align-items: center;
  margin: 20px 0;
  position: relative;
}

.loading::after {
  content: "";
  width: 30px;
  height: 30px;
  border: 3px solid #f3f3f3;
  border-top: 3px solid #007bff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.property-listings {
  padding: 10px;
  padding-bottom: 20px;
}

.property-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  margin-top: 10px;
}

@media screen and (min-width: 769px) and (max-width: 1024px) {
  .property-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.property-card {
  background: #ffffff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  cursor: pointer;
}

.property-card:hover {
  background: #f8f9fa;
}

.property-details h3 {
  margin: 0 0 8px 0;
  color: #333;
  font-size: 1.1em;
}

.property-details .price {
  color: #2c5282;
  font-size: 1.2em;
  font-weight: 600;
  margin: 8px 0;
}

.property-details p {
  margin: 8px 0;
  color: #666;
}

.property-details .description {
  color: #4a5568;
  font-size: 0.9em;
  margin-top: 12px;
}

@media screen and (max-width: 768px) {
  .property-grid {
    grid-template-columns: 1fr;
    max-width: 100%;
  }

  .property-card {
    width: 100%;
    margin: 0 auto;
  }

  .chat-container {
    padding: 10px;
  }

  .messages-container {
    padding: 10px;
  }
}
</style>

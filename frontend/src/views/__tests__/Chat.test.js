import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import Chat from '../Chat.vue'

const makeRouter = () =>
  createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div/>' } },
      { path: '/chat', component: Chat },
      { path: '/property-details', component: { template: '<div/>' } },
    ],
  })

const SAMPLE_PROPERTY = {
  address: '123 Main St, Austin, TX',
  price: '$500,000',
  beds: 3,
  baths: 2,
  sqft: '1,800',
  description: 'A lovely home.',
}

function mockOkFetch(text, properties = []) {
  return vi.fn().mockResolvedValueOnce({
    ok: true,
    json: async () => ({ response: { text, properties } }),
  })
}

describe('Chat', () => {
  let router

  beforeEach(() => {
    router = makeRouter()
    localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  const mountChat = () => mount(Chat, { global: { plugins: [router] } })

  it('shows the welcome message on first load', async () => {
    const wrapper = mountChat()
    await flushPromises()

    expect(wrapper.text()).toContain('Hello! I am your real estate assistant')
  })

  it('does not show the welcome message if saved messages exist', async () => {
    localStorage.setItem('chatMessages', JSON.stringify([
      { role: 'user', content: 'I want a house' },
    ]))
    const wrapper = mountChat()
    await flushPromises()

    expect(wrapper.text()).not.toContain('Hello! I am your real estate assistant')
    expect(wrapper.text()).toContain('I want a house')
  })

  it('restores all saved messages from localStorage', async () => {
    localStorage.setItem('chatMessages', JSON.stringify([
      { role: 'user', content: 'Find me a condo' },
      { role: 'assistant', content: 'Sure, here are some options.' },
    ]))
    const wrapper = mountChat()
    await flushPromises()

    expect(wrapper.text()).toContain('Find me a condo')
    expect(wrapper.text()).toContain('Sure, here are some options.')
  })

  it('shows user message in the chat after sending', async () => {
    vi.stubGlobal('fetch', mockOkFetch('Got it!'))
    const wrapper = mountChat()
    await flushPromises()

    await wrapper.find('input').setValue('I need a 3 bedroom house')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('I need a 3 bedroom house')
  })

  it('displays the assistant text response', async () => {
    vi.stubGlobal('fetch', mockOkFetch('Here are some great options for you!'))
    const wrapper = mountChat()
    await flushPromises()

    await wrapper.find('input').setValue('Show me houses')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Here are some great options for you!')
  })

  it('clears the input field after sending', async () => {
    vi.stubGlobal('fetch', mockOkFetch('OK'))
    const wrapper = mountChat()
    await flushPromises()

    const input = wrapper.find('input')
    await input.setValue('test message')
    await wrapper.find('button').trigger('click')
    await wrapper.vm.$nextTick()

    expect(input.element.value).toBe('')
  })

  it('calls the chat API with the correct payload', async () => {
    const fetchMock = mockOkFetch('Response text')
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mountChat()
    await flushPromises()

    await wrapper.find('input').setValue('What is the market like?')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledOnce()
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toContain('/chat')
    const body = JSON.parse(options.body)
    expect(body.messages.some(m => m.content === 'What is the market like?')).toBe(true)
  })

  it('shows an error message when the API call fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValueOnce(new Error('Network error')))
    const wrapper = mountChat()
    await flushPromises()

    await wrapper.find('input').setValue('test')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Sorry, I encountered an error')
  })

  it('shows an error message when the API returns a non-ok status', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce({ ok: false, status: 500 }))
    const wrapper = mountChat()
    await flushPromises()

    await wrapper.find('input').setValue('test')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Sorry, I encountered an error')
  })

  it('renders property cards when the response includes listings', async () => {
    vi.stubGlobal('fetch', mockOkFetch('Found these properties:', [SAMPLE_PROPERTY]))
    const wrapper = mountChat()
    await flushPromises()

    await wrapper.find('input').setValue('Find houses in Austin')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(wrapper.find('.property-card').exists()).toBe(true)
    expect(wrapper.text()).toContain('123 Main St, Austin, TX')
    expect(wrapper.text()).toContain('$500,000')
    expect(wrapper.text()).toContain('3 beds')
  })

  it('navigates to /property-details when a property card is clicked', async () => {
    vi.stubGlobal('fetch', mockOkFetch('Here:', [SAMPLE_PROPERTY]))
    const wrapper = mountChat()
    await flushPromises()

    await wrapper.find('input').setValue('Show me something')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    await wrapper.find('.property-card').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/property-details')
  })

  it('persists messages to localStorage after sending', async () => {
    vi.stubGlobal('fetch', mockOkFetch('Saved!'))
    const wrapper = mountChat()
    await flushPromises()

    await wrapper.find('input').setValue('Remember this message')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    const saved = JSON.parse(localStorage.getItem('chatMessages'))
    expect(saved.some(m => m.content === 'Remember this message')).toBe(true)
  })

  it('disables the send button while a request is in flight', async () => {
    let resolveFetch
    vi.stubGlobal('fetch', vi.fn().mockReturnValueOnce(
      new Promise(resolve => { resolveFetch = resolve })
    ))
    const wrapper = mountChat()
    await flushPromises()

    await wrapper.find('input').setValue('Pending message')
    await wrapper.find('button').trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('button').element.disabled).toBe(true)

    resolveFetch({ ok: true, json: async () => ({ response: { text: 'Done', properties: [] } }) })
    await flushPromises()
  })

  it('does not send when the input is empty', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mountChat()
    await flushPromises()

    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('sends on Enter key press', async () => {
    const fetchMock = mockOkFetch('Enter works!')
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mountChat()
    await flushPromises()

    await wrapper.find('input').setValue('Triggered by Enter')
    await wrapper.find('input').trigger('keyup.enter')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledOnce()
  })
})

import { describe, it, expect } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import Home from '../Home.vue'

const makeRouter = () =>
  createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: Home },
      { path: '/chat', component: { template: '<div/>' } },
    ],
  })

describe('Home', () => {
  const mountHome = () => {
    const router = makeRouter()
    const wrapper = mount(Home, { global: { plugins: [router] } })
    return { wrapper, router }
  }

  it('renders the hero headline', () => {
    const { wrapper } = mountHome()
    expect(wrapper.text()).toContain('Welcome to Your Real Estate Assistant')
  })

  it('renders the hero subtitle', () => {
    const { wrapper } = mountHome()
    expect(wrapper.text()).toContain('Find your dream home with the help of AI')
  })

  it('renders the Start Chatting button', () => {
    const { wrapper } = mountHome()
    expect(wrapper.find('button.start-button').exists()).toBe(true)
    expect(wrapper.find('button.start-button').text()).toBe('Start Chatting')
  })

  it('navigates to /chat when Start Chatting is clicked', async () => {
    const { wrapper, router } = mountHome()
    await wrapper.find('button.start-button').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/chat')
  })

  it('renders the three main feature cards', () => {
    const { wrapper } = mountHome()
    const cards = wrapper.findAll('.feature-card:not(.coming-soon)')
    expect(cards.length).toBe(3)
    expect(wrapper.text()).toContain('Property Search')
    expect(wrapper.text()).toContain('Mortgage Calculator')
    expect(wrapper.text()).toContain('24/7 Assistance')
  })

  it('renders the Coming Soon section with three cards', () => {
    const { wrapper } = mountHome()
    expect(wrapper.text()).toContain('Coming Soon')
    const comingSoonCards = wrapper.findAll('.feature-card.coming-soon')
    expect(comingSoonCards.length).toBe(3)
  })

  it('renders the How It Works section with three steps', () => {
    const { wrapper } = mountHome()
    expect(wrapper.text()).toContain('How It Works')
    const steps = wrapper.findAll('.step')
    expect(steps.length).toBe(3)
    expect(steps[0].find('.step-number').text()).toBe('1')
    expect(steps[1].find('.step-number').text()).toBe('2')
    expect(steps[2].find('.step-number').text()).toBe('3')
  })
})

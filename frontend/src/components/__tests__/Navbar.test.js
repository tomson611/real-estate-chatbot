import { describe, it, expect } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import Navbar from '../Navbar.vue'

const makeRouter = (initialPath = '/') =>
  createRouter({
    history: createMemoryHistory(initialPath),
    routes: [
      { path: '/', component: { template: '<div/>' } },
      { path: '/chat', component: { template: '<div/>' } },
    ],
  })

describe('Navbar', () => {
  const mountNavbar = (router) =>
    mount(Navbar, { global: { plugins: [router] } })

  it('renders the brand name', () => {
    const wrapper = mountNavbar(makeRouter())
    expect(wrapper.text()).toContain('Real Estate AI')
  })

  it('renders the brand home icon', () => {
    const wrapper = mountNavbar(makeRouter())
    expect(wrapper.find('.brand-icon').text()).toBe('🏠')
  })

  it('renders Home and Chat navigation links', () => {
    const wrapper = mountNavbar(makeRouter())
    const links = wrapper.findAll('.navbar-links a')
    expect(links.length).toBe(2)
    expect(links[0].text()).toBe('Home')
    expect(links[1].text()).toBe('Chat')
  })

  it('Home link points to /', () => {
    const wrapper = mountNavbar(makeRouter())
    const homeLink = wrapper.findAll('.navbar-links a')[0]
    expect(homeLink.attributes('href')).toBe('/')
  })

  it('Chat link points to /chat', () => {
    const wrapper = mountNavbar(makeRouter())
    const chatLink = wrapper.findAll('.navbar-links a')[1]
    expect(chatLink.attributes('href')).toBe('/chat')
  })

  it('brand link navigates to / when clicked', async () => {
    const router = makeRouter('/chat')
    await router.push('/chat')
    const wrapper = mountNavbar(router)

    await wrapper.find('.navbar-brand').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/')
  })

  it('Home link has active class on the / route', async () => {
    const router = makeRouter()
    await router.push('/')
    const wrapper = mountNavbar(router)
    await flushPromises()

    const homeLink = wrapper.findAll('.navbar-links a')[0]
    expect(homeLink.classes()).toContain('active')
  })

  it('Home link does not have active class on /chat', async () => {
    const router = makeRouter()
    await router.push('/chat')
    await router.isReady()
    const wrapper = mountNavbar(router)
    await flushPromises()

    const homeLink = wrapper.findAll('.navbar-links a')[0]
    expect(homeLink.classes()).not.toContain('active')
  })

  it('Chat link has active class on the /chat route', async () => {
    const router = makeRouter()
    await router.push('/chat')
    await router.isReady()
    const wrapper = mountNavbar(router)
    await flushPromises()

    const chatLink = wrapper.findAll('.navbar-links a')[1]
    expect(chatLink.classes()).toContain('active')
  })
})

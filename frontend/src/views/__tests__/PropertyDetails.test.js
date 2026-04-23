import { describe, it, expect, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import PropertyDetails from '../PropertyDetails.vue'

const makeRouter = () =>
  createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div/>' } },
      { path: '/property-details', component: PropertyDetails },
    ],
  })

const FULL_PROPERTY = {
  address: '789 Oak Ave, Denver, CO',
  price: '$650,000',
  beds: 4,
  baths: 3,
  sqft: '2,400',
  lotSize: '0.25 acres',
  yearBuilt: 2005,
  propertyType: 'Single Family',
  listingStatus: 'For Sale',
  daysOnMarket: 12,
  pricePerSqft: '$271',
  lastSoldDate: '2018-06-15',
  lastSoldPrice: '$480,000',
  zestimate: '$660,000',
  rentZestimate: '$3,200/mo',
  description: 'Spacious family home with mountain views.',
  latitude: 39.7392,
  longitude: -104.9903,
  listingAgent: { name: 'Jane Smith', phone: '555-1234', email: 'jane@example.com', website: 'https://jane.com' },
  listingOffice: { name: 'Denver Realty', phone: '555-5678', email: 'office@denverrealty.com' },
  mlsNumber: 'MLS123456',
  mlsName: 'REcolorado',
}

describe('PropertyDetails', () => {
  beforeEach(() => {
    window.history.replaceState({ property: FULL_PROPERTY }, '')
  })

  const mountDetails = () => {
    const router = makeRouter()
    return { wrapper: mount(PropertyDetails, { global: { plugins: [router] } }), router }
  }

  it('renders the property address and price', async () => {
    const { wrapper } = mountDetails()
    await flushPromises()

    expect(wrapper.text()).toContain('789 Oak Ave, Denver, CO')
    expect(wrapper.text()).toContain('$650,000')
  })

  it('renders all spec items', async () => {
    const { wrapper } = mountDetails()
    await flushPromises()

    expect(wrapper.text()).toContain('4')   // beds
    expect(wrapper.text()).toContain('3')   // baths
    expect(wrapper.text()).toContain('2,400')
    expect(wrapper.text()).toContain('0.25 acres')
    expect(wrapper.text()).toContain('2005')
    expect(wrapper.text()).toContain('Single Family')
    expect(wrapper.text()).toContain('For Sale')
    expect(wrapper.text()).toContain('12')  // days on market
    expect(wrapper.text()).toContain('$271')
  })

  it('renders the property history section', async () => {
    const { wrapper } = mountDetails()
    await flushPromises()

    expect(wrapper.text()).toContain('Property History')
    expect(wrapper.text()).toContain('2018-06-15')
    expect(wrapper.text()).toContain('$480,000')
  })

  it('renders the valuations section', async () => {
    const { wrapper } = mountDetails()
    await flushPromises()

    expect(wrapper.text()).toContain('Valuations')
    expect(wrapper.text()).toContain('$660,000')
    expect(wrapper.text()).toContain('$3,200/mo')
  })

  it('renders the description', async () => {
    const { wrapper } = mountDetails()
    await flushPromises()

    expect(wrapper.text()).toContain('Spacious family home with mountain views.')
  })

  it('renders listing agent info', async () => {
    const { wrapper } = mountDetails()
    await flushPromises()

    expect(wrapper.text()).toContain('Listing Agent')
    expect(wrapper.text()).toContain('Jane Smith')
    expect(wrapper.find('a[href="tel:555-1234"]').exists()).toBe(true)
    expect(wrapper.find('a[href="mailto:jane@example.com"]').exists()).toBe(true)
    expect(wrapper.find('a[href="https://jane.com"]').exists()).toBe(true)
  })

  it('renders listing office info', async () => {
    const { wrapper } = mountDetails()
    await flushPromises()

    expect(wrapper.text()).toContain('Listing Office')
    expect(wrapper.text()).toContain('Denver Realty')
  })

  it('renders MLS information', async () => {
    const { wrapper } = mountDetails()
    await flushPromises()

    expect(wrapper.text()).toContain('MLS Information')
    expect(wrapper.text()).toContain('MLS123456')
    expect(wrapper.text()).toContain('REcolorado')
  })

  it('redirects to / when no property is in history state', async () => {
    window.history.replaceState({}, '')
    const router = makeRouter()
    await router.push('/property-details')
    await router.isReady()

    mount(PropertyDetails, { global: { plugins: [router] } })
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/')
  })

  it('navigates to / when Back to Chat is clicked', async () => {
    const { wrapper, router } = mountDetails()
    await flushPromises()

    await wrapper.find('button.back-button').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/')
  })

  it('hides listing info when agent and office names are N/A', async () => {
    window.history.replaceState({
      property: {
        ...FULL_PROPERTY,
        listingAgent: { name: 'N/A', phone: 'N/A', email: 'N/A', website: 'N/A' },
        listingOffice: { name: 'N/A', phone: 'N/A', email: 'N/A' },
      },
    }, '')
    const { wrapper } = mountDetails()
    await flushPromises()

    expect(wrapper.find('.listing-info').exists()).toBe(false)
  })
})

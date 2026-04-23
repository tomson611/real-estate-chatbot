import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Chat from '../views/Chat.vue'
import PropertyDetails from '../views/PropertyDetails.vue'

const routes = [
  { path: '/', component: Home },
  { path: '/chat', component: Chat },
  { path: '/property-details', component: PropertyDetails },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})

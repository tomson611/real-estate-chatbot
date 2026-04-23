<template>
  <Navbar />
  <main class="main-content">
    <RouterView />
  </main>
</template>

<script setup>
import Navbar from './components/Navbar.vue'
import { RouterView } from 'vue-router'
</script>

<style>
.main-content {
  padding-top: 60px;
  min-height: calc(100vh - 60px);
  background-color: #f8f9fa;
}
</style>

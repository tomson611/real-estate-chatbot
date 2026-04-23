<template>
  <nav class="navbar">
    <div class="navbar-container">
      <RouterLink to="/" class="navbar-brand">
        <span class="brand-icon">🏠</span>
        <span class="brand-name">Real Estate AI</span>
      </RouterLink>
      <div class="navbar-links">
        <RouterLink to="/" exact-active-class="active" active-class="">Home</RouterLink>
        <RouterLink to="/chat" active-class="active">Chat</RouterLink>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { RouterLink } from 'vue-router'
</script>

<style scoped>
.navbar {
  background-color: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 1000;
  height: 60px;
}

.navbar-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 100%;
}

.navbar-brand {
  display: flex;
  align-items: center;
  cursor: pointer;
  text-decoration: none;
  padding: 0.5rem;
}

.brand-icon {
  font-size: 1.5rem;
  margin-right: 0.5rem;
}

.brand-name {
  font-size: 1.25rem;
  font-weight: bold;
  color: #2c3e50;
}

.navbar-links {
  display: flex;
  align-items: center;
  gap: 2rem;
  height: 100%;
}

.navbar-links a {
  color: #7f8c8d;
  text-decoration: none;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.3s ease;
  padding: 0.5rem 1rem;
  display: flex;
  align-items: center;
  height: 100%;
}

.navbar-links a:hover {
  color: #3498db;
}

.navbar-links a.active {
  color: #3498db;
  border-bottom: 2px solid #3498db;
}

@media (max-width: 768px) {
  .navbar-container {
    padding: 0 1rem;
  }

  .navbar-links {
    gap: 1rem;
  }

  .brand-name {
    display: none;
  }
}
</style>

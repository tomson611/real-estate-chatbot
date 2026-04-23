<template>
  <div class="home-container">
    <div class="hero-section">
      <h1>Welcome to Your Real Estate Assistant</h1>
      <p class="subtitle">Find your dream home with the help of AI</p>
      <button class="start-button" @click="startChat">Start Chatting</button>
    </div>

    <div class="features-section">
      <div class="feature-card">
        <div class="feature-icon">🏠</div>
        <h3>Property Search</h3>
        <p>Find properties that match your exact criteria</p>
      </div>
      <div class="feature-card">
        <div class="feature-icon">💰</div>
        <h3>Mortgage Calculator</h3>
        <p>Calculate your monthly payments and total costs</p>
      </div>
      <div class="feature-card">
        <div class="feature-icon">📱</div>
        <h3>24/7 Assistance</h3>
        <p>Get help with your real estate questions anytime</p>
      </div>
    </div>

    <div class="coming-soon-section">
      <h2>Coming Soon</h2>
      <div class="features-section">
        <div class="feature-card coming-soon">
          <div class="feature-icon">📊</div>
          <h3>Market Data</h3>
          <p>Access comprehensive real estate market trends and analytics</p>
          <span class="coming-soon-badge">Coming Soon</span>
        </div>
        <div class="feature-card coming-soon">
          <div class="feature-icon">📈</div>
          <h3>Property Valuation</h3>
          <p>Get accurate property value estimates and price history</p>
          <span class="coming-soon-badge">Coming Soon</span>
        </div>
        <div class="feature-card coming-soon">
          <div class="feature-icon">📋</div>
          <h3>Property Data</h3>
          <p>Detailed property information and historical data</p>
          <span class="coming-soon-badge">Coming Soon</span>
        </div>
      </div>
    </div>

    <div class="how-it-works">
      <h2>How It Works</h2>
      <div class="steps">
        <div class="step">
          <div class="step-number">1</div>
          <p>Start a chat with our AI assistant</p>
        </div>
        <div class="step">
          <div class="step-number">2</div>
          <p>Tell us what you're looking for</p>
        </div>
        <div class="step">
          <div class="step-number">3</div>
          <p>Get personalized property recommendations</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

function startChat() {
  router.push('/chat')
}
</script>

<style scoped>
.home-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
}

.hero-section {
  text-align: center;
  padding: 4rem 0;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  border-radius: 1rem;
  margin-bottom: 3rem;
}

.hero-section h1 {
  font-size: 2.5rem;
  color: #2c3e50;
  margin-bottom: 1rem;
}

.subtitle {
  font-size: 1.2rem;
  color: #7f8c8d;
  margin-bottom: 2rem;
}

.start-button {
  background-color: #3498db;
  color: white;
  border: none;
  padding: 1rem 2rem;
  font-size: 1.1rem;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: background-color 0.3s ease;
}

.start-button:hover {
  background-color: #2980b9;
}

.features-section {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 2rem;
  margin-bottom: 3rem;
}

.feature-card {
  background: white;
  padding: 2rem;
  border-radius: 1rem;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  text-align: center;
  position: relative;
}

.feature-icon {
  font-size: 2.5rem;
  margin-bottom: 1rem;
}

.feature-card h3 {
  color: #2c3e50;
  margin-bottom: 1rem;
}

.feature-card p {
  color: #7f8c8d;
}

.coming-soon-section {
  margin-bottom: 3rem;
}

.coming-soon-section h2 {
  text-align: center;
  color: #2c3e50;
  margin-bottom: 2rem;
}

.feature-card.coming-soon {
  opacity: 0.8;
  filter: grayscale(20%);
}

.coming-soon-badge {
  position: absolute;
  top: 1rem;
  right: 1rem;
  background-color: #3498db;
  color: white;
  padding: 0.25rem 0.75rem;
  border-radius: 1rem;
  font-size: 0.8rem;
  font-weight: 500;
}

.how-it-works {
  text-align: center;
  margin-bottom: 3rem;
}

.how-it-works h2 {
  color: #2c3e50;
  margin-bottom: 2rem;
}

.steps {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 2rem;
}

.step {
  background: white;
  padding: 2rem;
  border-radius: 1rem;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.step-number {
  width: 40px;
  height: 40px;
  background-color: #3498db;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 1rem;
  font-weight: bold;
}

.step p {
  color: #7f8c8d;
}

@media (max-width: 768px) {
  .hero-section {
    padding: 2rem 1rem;
  }

  .hero-section h1 {
    font-size: 2rem;
  }

  .features-section {
    grid-template-columns: 1fr;
  }

  .steps {
    grid-template-columns: 1fr;
  }
}
</style>

<template>
  <div class="property-details-container" v-if="property">
    <div class="property-header">
      <h1>{{ property.address }}</h1>
      <p class="price">{{ property.price }}</p>
    </div>

    <div class="property-specs">
      <div class="spec-item">
        <span class="label">Beds</span>
        <span class="value">{{ property.beds }}</span>
      </div>
      <div class="spec-item">
        <span class="label">Baths</span>
        <span class="value">{{ property.baths }}</span>
      </div>
      <div class="spec-item">
        <span class="label">Square Feet</span>
        <span class="value">{{ property.sqft }}</span>
      </div>
      <div class="spec-item">
        <span class="label">Lot Size</span>
        <span class="value">{{ property.lotSize }}</span>
      </div>
      <div class="spec-item">
        <span class="label">Year Built</span>
        <span class="value">{{ property.yearBuilt }}</span>
      </div>
      <div class="spec-item">
        <span class="label">Property Type</span>
        <span class="value">{{ property.propertyType }}</span>
      </div>
      <div class="spec-item">
        <span class="label">Listing Status</span>
        <span class="value">{{ property.listingStatus }}</span>
      </div>
      <div class="spec-item">
        <span class="label">Days on Market</span>
        <span class="value">{{ property.daysOnMarket }}</span>
      </div>
      <div class="spec-item">
        <span class="label">Price per Sqft</span>
        <span class="value">{{ property.pricePerSqft }}</span>
      </div>
    </div>

    <div class="property-history">
      <h2>Property History</h2>
      <div class="history-item">
        <span class="label">Last Sold Date</span>
        <span class="value">{{ property.lastSoldDate }}</span>
      </div>
      <div class="history-item">
        <span class="label">Last Sold Price</span>
        <span class="value">{{ property.lastSoldPrice }}</span>
      </div>
    </div>

    <div class="property-valuations">
      <h2>Valuations</h2>
      <div class="valuation-item">
        <span class="label">Zestimate</span>
        <span class="value">{{ property.zestimate }}</span>
      </div>
      <div class="valuation-item">
        <span class="label">Rent Zestimate</span>
        <span class="value">{{ property.rentZestimate }}</span>
      </div>
    </div>

    <div class="property-description">
      <h2>Description</h2>
      <p>{{ property.description }}</p>
    </div>

    <div class="property-location">
      <h2>Location</h2>
      <div class="location-item">
        <span class="label">Latitude</span>
        <span class="value">{{ property.latitude }}</span>
      </div>
      <div class="location-item">
        <span class="label">Longitude</span>
        <span class="value">{{ property.longitude }}</span>
      </div>
    </div>

    <div
      class="listing-info"
      v-if="property.listingAgent?.name !== 'N/A' || property.listingOffice?.name !== 'N/A'"
    >
      <h3>Listing Information</h3>

      <div class="info-section" v-if="property.listingAgent?.name !== 'N/A'">
        <h4>Listing Agent</h4>
        <div class="info-grid">
          <div class="info-item" v-if="property.listingAgent.name !== 'N/A'">
            <span class="label">Name:</span>
            <span class="value">{{ property.listingAgent.name }}</span>
          </div>
          <div class="info-item" v-if="property.listingAgent.phone !== 'N/A'">
            <span class="label">Phone:</span>
            <a :href="'tel:' + property.listingAgent.phone" class="value link">{{ property.listingAgent.phone }}</a>
          </div>
          <div class="info-item" v-if="property.listingAgent.email !== 'N/A'">
            <span class="label">Email:</span>
            <a :href="'mailto:' + property.listingAgent.email" class="value link">{{ property.listingAgent.email }}</a>
          </div>
          <div class="info-item" v-if="property.listingAgent.website !== 'N/A'">
            <span class="label">Website:</span>
            <a :href="property.listingAgent.website" target="_blank" class="value link">Visit Website</a>
          </div>
        </div>
      </div>

      <div class="info-section" v-if="property.listingOffice?.name !== 'N/A'">
        <h4>Listing Office</h4>
        <div class="info-grid">
          <div class="info-item" v-if="property.listingOffice.name !== 'N/A'">
            <span class="label">Name:</span>
            <span class="value">{{ property.listingOffice.name }}</span>
          </div>
          <div class="info-item" v-if="property.listingOffice.phone !== 'N/A'">
            <span class="label">Phone:</span>
            <a :href="'tel:' + property.listingOffice.phone" class="value link">{{ property.listingOffice.phone }}</a>
          </div>
          <div class="info-item" v-if="property.listingOffice.email !== 'N/A'">
            <span class="label">Email:</span>
            <a :href="'mailto:' + property.listingOffice.email" class="value link">{{ property.listingOffice.email }}</a>
          </div>
        </div>
      </div>

      <div
        class="info-section"
        v-if="property.mlsNumber !== 'N/A' || property.mlsName !== 'N/A'"
      >
        <h4>MLS Information</h4>
        <div class="info-grid">
          <div class="info-item" v-if="property.mlsNumber !== 'N/A'">
            <span class="label">MLS Number:</span>
            <span class="value">{{ property.mlsNumber }}</span>
          </div>
          <div class="info-item" v-if="property.mlsName !== 'N/A'">
            <span class="label">MLS Name:</span>
            <span class="value">{{ property.mlsName }}</span>
          </div>
        </div>
      </div>
    </div>

    <button class="back-button" @click="goBack">Back to Chat</button>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const property = ref(null)

onMounted(() => {
  const propertyData = window.history.state?.property
  if (propertyData) {
    property.value = propertyData
  } else {
    router.replace('/')
  }
})

function goBack() {
  router.push('/')
}
</script>

<style scoped>
.property-details-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
  background: #ffffff;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.property-header {
  margin-bottom: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid #eee;
}

.property-header h1 {
  margin: 0;
  color: #333;
  font-size: 24px;
}

.price {
  font-size: 20px;
  color: #2ecc71;
  font-weight: bold;
  margin-top: 10px;
}

.property-specs {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.spec-item,
.history-item,
.valuation-item,
.location-item {
  background: #f8f9fa;
  padding: 15px;
  border-radius: 6px;
}

.label {
  display: block;
  font-size: 14px;
  color: #666;
  margin-bottom: 5px;
}

.value {
  font-size: 16px;
  color: #333;
  font-weight: 500;
}

.property-history,
.property-valuations,
.property-location {
  margin-bottom: 30px;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 8px;
}

.property-history h2,
.property-valuations h2,
.property-location h2 {
  margin-top: 0;
  margin-bottom: 15px;
  color: #333;
  font-size: 20px;
}

.property-description {
  margin-bottom: 30px;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 8px;
}

.property-description h2 {
  margin-top: 0;
  margin-bottom: 15px;
  color: #333;
  font-size: 20px;
}

.property-description p {
  margin: 0;
  line-height: 1.6;
  color: #444;
}

.back-button {
  display: block;
  width: 100%;
  padding: 12px;
  background: #3498db;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 16px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.back-button:hover {
  background: #2980b9;
}

.listing-info {
  background-color: #f8f9fa;
  border-radius: 8px;
  padding: 1.5rem;
  margin: 2rem 0;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.listing-info h3 {
  color: #2c3e50;
  margin-bottom: 1.5rem;
  font-size: 1.25rem;
  font-weight: 600;
}

.info-section {
  margin-bottom: 1.5rem;
  padding: 1rem;
  background-color: white;
  border-radius: 6px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.info-section:last-child {
  margin-bottom: 0;
}

.info-section h4 {
  color: #2c3e50;
  margin-bottom: 1rem;
  font-size: 1.1rem;
  font-weight: 500;
}

.info-grid {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.info-item .label {
  color: #6c757d;
  font-size: 0.875rem;
  font-weight: 500;
}

.info-item .value {
  color: #2c3e50;
  font-size: 1rem;
  font-weight: 500;
}

.info-item .link {
  color: #007bff;
  text-decoration: none;
  transition: color 0.2s;
}

.info-item .link:hover {
  color: #0056b3;
  text-decoration: underline;
}
</style>

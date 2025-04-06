export interface ListingAgent {
  name: string;
  phone: string;
  email: string;
  website: string;
}

export interface ListingOffice {
  name: string;
  phone: string;
  email: string;
}

export interface Property {
  address: string;
  price: string;
  beds: string | number;
  baths: string | number;
  sqft: string;
  image_url?: string;
  property_url?: string;
  description: string;
  yearBuilt: string | number;
  lotSize: string;
  propertyType: string;
  listingStatus: string;
  lastSoldDate: string;
  lastSoldPrice: string;
  zestimate: string;
  rentZestimate: string;
  daysOnMarket: string | number;
  pricePerSqft: string;
  latitude: string | number;
  longitude: string | number;
  listingAgent: ListingAgent;
  listingOffice: ListingOffice;
  mlsNumber: string;
  mlsName: string;
} 
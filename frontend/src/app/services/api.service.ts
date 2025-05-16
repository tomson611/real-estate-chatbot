import { Injectable } from '@angular/core';

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private apiUrl: string;

  constructor() {
    // In production, this will be replaced during build
    this.apiUrl = 'API_URL_PLACEHOLDER';
  }

  getApiUrl(): string {
    return this.apiUrl;
  }
} 
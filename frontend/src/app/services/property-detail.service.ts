import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { Property } from '../models/property.interface';

@Injectable({
  providedIn: 'root'
})
export class PropertyDetailService {
  private selectedPropertySource = new BehaviorSubject<Property | null>(null);
  selectedProperty$ = this.selectedPropertySource.asObservable();

  constructor() { }

  setSelectedProperty(property: Property | null) {
    this.selectedPropertySource.next(property);
  }
} 
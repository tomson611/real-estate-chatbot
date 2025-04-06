import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { Property } from '../models/property.interface';

@Component({
  selector: 'app-property-details',
  templateUrl: './property-details.component.html',
  styleUrls: ['./property-details.component.css']
})
export class PropertyDetailsComponent implements OnInit {
  property: Property | null = null;

  constructor(
    private route: ActivatedRoute,
    private router: Router
  ) { }

  ngOnInit() {
    const propertyData = history.state.property;
    if (propertyData) {
      this.property = propertyData;
    } else {
      this.router.navigate(['/']);
    }
  }

  goBack() {
    this.router.navigate(['/']);
  }
} 
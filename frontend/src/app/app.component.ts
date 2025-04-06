import { Component } from '@angular/core';

@Component({
  selector: 'app-root',
  template: `
    <div class="app-container">
      <h1>Real Estate Chatbot</h1>
      <router-outlet></router-outlet>
    </div>
  `,
  styles: [`
    .app-container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 20px;
    }
    h1 {
      text-align: center;
      color: #333;
      margin-bottom: 30px;
    }
  `]
})
export class AppComponent {
  title = 'real-estate-chatbot';
} 
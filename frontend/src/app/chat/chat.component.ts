import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router, ActivatedRoute } from '@angular/router';
import { Property } from '../models/property.interface';

interface Message {
  role: string;
  content: string | any;
}

interface ChatResponse {
  response: {
    text: string;
    properties?: Property[];
  };
}

@Component({
  selector: 'app-chat',
  templateUrl: './chat.component.html',
  styleUrls: ['./chat.component.css']
})
export class ChatComponent implements OnInit {
  messages: Message[] = [];
  displayMessages: Message[] = [];
  newMessage: string = '';
  isLoading: boolean = false;
  lastMessageTime: number = 0;
  cooldownPeriod: number = 2000; // 2 seconds cooldown

  constructor(private http: HttpClient, private router: Router, private route: ActivatedRoute) {}

  ngOnInit() {
    this.displayMessages.push({
      role: 'assistant',
      content: 'Hello! I am your real estate assistant. I can help you with property information, mortgage calculations, and market trends. How can I assist you today?'
    });
  }

  formatText(text: string): string {
    // First handle bold text
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Split into paragraphs first
    const paragraphs = text.split(/(?:\r?\n){2,}/);
    
    return paragraphs.map(paragraph => {
      // Check if this paragraph contains a numbered list
      if (paragraph.match(/\d+\.\s+/)) {
        // Split the initial text from the list
        const [intro, ...listItems] = paragraph.split(/(?=\d+\.\s+)/);
        
        // Format the list items
        const formattedList = listItems.map(item => {
          const [number] = item.match(/\d+/) || [''];
          return `<div class="list-item">
            <span class="number">${number}.</span>
            <span class="content">${item.replace(/^\d+\.\s+/, '')}</span>
          </div>`;
        }).join('');

        // Combine intro and list
        return `<p>${intro || ''}</p>
          <div class="numbered-list">
            ${formattedList}
          </div>`;
      }
      
      // Regular paragraph
      return `<p>${paragraph}</p>`;
    }).join('');
  }

  canSendMessage(): boolean {
    const now = Date.now();
    return !this.isLoading && (!this.lastMessageTime || now - this.lastMessageTime >= this.cooldownPeriod);
  }

  sendMessage() {
    if (!this.newMessage.trim() || !this.canSendMessage()) return;

    this.lastMessageTime = Date.now();
    const userMessage: Message = {
      role: 'user',
      content: this.newMessage
    };

    this.messages.push(userMessage);
    this.displayMessages.push(userMessage);
    this.isLoading = true;

    const formattedMessages = this.messages.map(msg => ({
      role: msg.role,
      content: typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content)
    }));

    const payload = { messages: formattedMessages };
    console.log('Sending to backend:', payload);

    this.http.post<ChatResponse>('http://127.0.0.1:8000/api/chat', payload)
      .subscribe({
        next: (response) => {
          console.log('Response from backend:', response);
          
          if (response && response.response) {
            const assistantMessage = {
              role: 'assistant',
              content: response.response
            };
            
            console.log('Formatted assistant message:', assistantMessage);
            this.messages.push(assistantMessage);
            this.displayMessages.push(assistantMessage);
          } else {
            console.error('Unexpected response format:', response);
            const errorMessage = {
              role: 'assistant',
              content: 'Sorry, I received an unexpected response format. Please try again.'
            };
            this.displayMessages.push(errorMessage);
          }
          this.isLoading = false;
        },
        error: (error) => {
          console.error('Error details:', error);
          const errorMessage = {
            role: 'assistant',
            content: 'Sorry, I encountered an error. Please try again.'
          };
          this.displayMessages.push(errorMessage);
          this.isLoading = false;
        }
      });

    this.newMessage = '';
  }

  isPropertyListing(content: any): boolean {
    console.log('Checking if content is property listing:', content);
    return content && 
           typeof content === 'object' && 
           'properties' in content && 
           Array.isArray(content.properties) && 
           content.properties.length > 0;
  }

  getMessageText(content: any): string {
    console.log('Getting message text from:', content);
    if (typeof content === 'string') {
      return this.formatText(content);
    } else if (content && typeof content === 'object') {
      return this.formatText(content.text || '');
    }
    return '';
  }

  viewPropertyDetails(property: Property) {
    console.log('Property clicked:', property);
    try {
      console.log('Navigating to property details');
      this.router.navigate(['/property-details'], { 
        state: { property }
      }).then(success => {
        console.log('Navigation success:', success);
      }).catch(error => {
        console.error('Navigation error:', error);
      });
    } catch (error) {
      console.error('Error in viewPropertyDetails:', error);
    }
  }

  logClick() {
    console.log('Card clicked');
  }
} 
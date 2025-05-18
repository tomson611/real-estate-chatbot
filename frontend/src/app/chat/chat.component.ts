import { Component, OnInit, ViewChild, ElementRef, AfterViewChecked, ChangeDetectorRef } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router, ActivatedRoute } from '@angular/router';
import { Property } from '../models/property.interface';
import { ApiService } from '../services/api.service';
import { PropertyDetailService } from '../services/property-detail.service';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: any;
}

interface ChatResponse {
  response: {
    text: string;
    properties?: any[];
  };
}

@Component({
  selector: 'app-chat',
  templateUrl: './chat.component.html',
  styleUrls: ['./chat.component.css']
})
export class ChatComponent implements OnInit, AfterViewChecked {
  @ViewChild('messagesContainer') private messagesContainer!: ElementRef;
  messages: ChatMessage[] = [];
  displayMessages: ChatMessage[] = [];
  newMessage: string = '';
  isLoading: boolean = false;
  lastMessageTime: number = 0;
  cooldownPeriod: number = 2000; // 2 seconds cooldown

  private readonly chatStorageKey = 'chatMessages';

  constructor(
    private http: HttpClient,
    private router: Router,
    private route: ActivatedRoute,
    private apiService: ApiService,
    private propertyDetailService: PropertyDetailService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit() {
    this.loadMessages();
    if (this.messages.length === 0) { // Or displayMessages, depending on logic
      const initialMessage = {
        role: 'assistant' as const,
        content: 'Hello! I am your real estate assistant. I can help you with property information, mortgage calculations, and market trends. How can I assist you today?'
      };
      this.messages.push(initialMessage);
      this.displayMessages.push(initialMessage); // Ensure displayMessages also gets this
    }
  }

  ngAfterViewChecked() {
    this.scrollToBottom();
  }

  scrollToBottom(): void {
    try {
      this.messagesContainer.nativeElement.scrollTop = this.messagesContainer.nativeElement.scrollHeight;
    } catch(err) { }
  }

  formatText(text: string): string {
    // Convert markdown-like lists to HTML lists
    let formattedText = text.replace(/\n\n/g, '<br><br>'); // Handle double newlines for paragraphs
    formattedText = formattedText.replace(/\n/g, '<br>'); // Handle single newlines

    // Convert numbered lists
    formattedText = formattedText.replace(/(\d+\.\s.*?)(\n(?!\d+\.|$)|$)/g, '<li>$1</li>');
    formattedText = formattedText.replace(/(<li>.*?<\/li>)+/g, '<ol>$&</ol>');

    // Convert bulleted lists (if any, though system prompt emphasizes numbered)
    // formattedText = formattedText.replace(/\*\s(.*?)\n/g, '<li>$1</li>');
    // formattedText = formattedText.replace(/(<li>.*?<\/li>)+/g, '<ul>$&</ul>');
    return formattedText;
  }

  canSendMessage(): boolean {
    const now = Date.now();
    return !this.isLoading && (!this.lastMessageTime || now - this.lastMessageTime >= this.cooldownPeriod);
  }

  sendMessage() {
    if (!this.newMessage.trim() || !this.canSendMessage()) return;

    this.lastMessageTime = Date.now();
    const userMessage: ChatMessage = {
      role: 'user',
      content: this.newMessage
    };

    this.messages.push(userMessage);
    this.displayMessages.push(userMessage);
    this.saveMessages(); // Save after adding user message
    this.isLoading = true;

    const formattedMessages = this.messages.map(msg => ({
      role: msg.role,
      content: typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content)
    }));

    const payload = { messages: formattedMessages };

    this.http.post<ChatResponse>(`${this.apiService.getApiUrl()}/chat`, payload)
      .subscribe({
        next: (response: ChatResponse | null) => {
          this.isLoading = false;
          if (!response || !response.response) {
            const errorMessage: ChatMessage = {
              role: 'assistant',
              content: 'Sorry, I received an empty response from the server. Please try again.'
            };
            this.messages.push(errorMessage);
            this.displayMessages.push(errorMessage);
            this.saveMessages(); // Save after adding error message
            return;
          }

          const assistantMessageContent = response.response.text;
          const properties = response.response.properties;

          const assistantMessage: ChatMessage = {
            role: 'assistant',
            content: properties && properties.length > 0 ? { text: assistantMessageContent, properties: properties } : assistantMessageContent
          };

          this.messages.push(assistantMessage);
          this.displayMessages.push(assistantMessage);
          this.saveMessages(); // Save after adding assistant message
          this.cdr.detectChanges();
          this.scrollToBottom();
        },
        error: (error: any) => {
          this.isLoading = false;
          const errorMessage: ChatMessage = {
            role: 'assistant',
            content: 'Sorry, I encountered an error. Please try again.'
          };
          this.messages.push(errorMessage);
          this.displayMessages.push(errorMessage);
          this.saveMessages(); // Save after adding error message
          this.cdr.detectChanges();
          this.scrollToBottom();
        }
      });

    this.newMessage = '';
  }

  isPropertyListing(content: any): boolean {
    return content &&
           typeof content === 'object' &&
           'properties' in content &&
           Array.isArray(content.properties) &&
           content.properties.length > 0;
  }

  getMessageText(content: any): string {
    if (typeof content === 'string') {
      return this.formatText(content);
    } else if (content && typeof content === 'object' && content.text) {
      return this.formatText(content.text);
    }
    return '';
  }

  getProperties(content: any): any[] {
    if (this.isPropertyListing(content)) {
      return content.properties;
    }
    return [];
  }

  onPropertyClick(property: any): void {
    this.propertyDetailService.setSelectedProperty(property);
    this.router.navigate(['/property-detail'])
      .then((success: boolean) => {
        // if (success) {
        //   // console.log('Navigation success:', success);
        // } else {
        //   // console.error('Navigation failed');
        // }
      })
      .catch((err: any) => {
        // console.error('Navigation error:', err);
      });
  }

  onCardClick(event: Event) {
    // console.log('Card clicked');
  }

  private saveMessages(): void {
    try {
      localStorage.setItem(this.chatStorageKey, JSON.stringify(this.messages));
    } catch (e) {
      console.error('Error saving messages to localStorage', e); // Keep console.error for debugging
    }
  }

  private loadMessages(): void {
    try {
      const savedMessages = localStorage.getItem(this.chatStorageKey);
      if (savedMessages) {
        this.messages = JSON.parse(savedMessages);
        // Assuming displayMessages should be a direct copy or derived from messages.
        // If displayMessages undergoes transformations not captured just by copying,
        // this logic might need to be more complex, or save/load displayMessages too.
        this.displayMessages = [...this.messages];
      }
    } catch (e) {
      console.error('Error loading messages from localStorage', e); // Keep console.error for debugging
      this.messages = [];
      this.displayMessages = [];
    }
  }
} 
import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { PropertyDetailsComponent } from './property-details/property-details.component';
import { ChatComponent } from './chat/chat.component';

const routes: Routes = [
  { path: '', component: ChatComponent },
  { path: 'property-details', component: PropertyDetailsComponent }
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { } 
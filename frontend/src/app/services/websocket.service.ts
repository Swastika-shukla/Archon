import { Injectable, signal } from '@angular/core';
import { Subject } from 'rxjs';

export interface WsMessage {
  type: string;
  step: number;
  data: Record<string, any>;
}

export type WsStatus = 'idle' | 'connecting' | 'connected' | 'disconnected' | 'error' | 'done';

@Injectable({ providedIn: 'root' })
export class WebsocketService {
  status = signal<WsStatus>('idle');

  private _socket: WebSocket | null = null;
  private _msg$ = new Subject<WsMessage>();
  messages$ = this._msg$.asObservable();

  connect(goal: string, dryRun: boolean): void {
    this.disconnect();
    this.status.set('connecting');
    this._socket = new WebSocket('ws://localhost:8000/ws/run');

    this._socket.onopen = () => {
      this.status.set('connected');
      this._socket!.send(JSON.stringify({ goal, dry_run: dryRun }));
    };
    this._socket.onmessage = ({ data }) => {
      try { this._msg$.next(JSON.parse(data)); } catch {}
    };
    this._socket.onerror = () => this.status.set('error');
    this._socket.onclose = () => {
      if (this.status() !== 'done') this.status.set('disconnected');
    };
  }
  sendAnswer(answer: string): void {
    if (this._socket && this._socket.readyState === WebSocket.OPEN) {
      this._socket.send(JSON.stringify({ answer }));
    }
  }

  disconnect(): void {
    this._socket?.close();
    this._socket = null;
    this.status.set('idle');
  }
}


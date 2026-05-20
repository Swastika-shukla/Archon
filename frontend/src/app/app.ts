import { Component, signal, inject, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { ThemeService } from './services/theme.service';
import { WebsocketService, WsMessage } from './services/websocket.service';

interface HistoryItem {
  goal: string;
  dry: boolean;
  time: string;
  sessionId: string;
}

interface ChatBubble {
  type: 'user' | 'agent' | 'error';
  text: string;
  points?: string[];
  rawSteps?: WsMessage[];
  showDetails?: boolean;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
<div class="app-shell">

  <!-- ═══ Left strip ═══ -->
  <div class="left-strip">
    <button class="ham" (click)="toggleHist()" title="History">
      <svg width="17" height="17" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/>
      </svg>
    </button>
  </div>

  <!-- ═══ History panel ═══ -->
  <div class="hist-panel" [class.open]="histOpen()">
    <div class="hist-header">
      <p class="hist-title">History</p>
      <button class="ham sm" (click)="toggleHist()">
        <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    </div>
    <div class="hist-list">
      @if (history().length === 0) {
        <p class="hist-empty">No runs yet.<br>Start a goal to see history.</p>
      }
      @for (item of history(); track item.time) {
        <div class="hist-item">
          <p class="hist-item-goal">{{ item.goal }}</p>
          <div class="hist-item-meta">
            <span class="hist-time">{{ item.time }}</span>
            <span class="hist-badge" [class.dry]="item.dry" [class.live]="!item.dry">
              {{ item.dry ? 'dry' : 'live' }}
            </span>
            @if (item.sessionId) {
              <button class="copy-btn" (click)="copyId(item.sessionId)" title="Copy session ID">
                <svg width="11" height="11" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/>
                </svg>
              </button>
            }
          </div>
        </div>
      }
    </div>
  </div>

  <!-- ═══ Main ═══ -->
  <div class="main">

    <!-- Topbar -->
    <nav class="topbar">
      <div class="logo">
        <div class="logo-icon">
          <svg width="11" height="11" fill="none" viewBox="0 0 24 24" stroke="white" stroke-width="3">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/>
          </svg>
        </div>
        <span class="logo-text">Archon</span>
      </div>
      <div class="nav-right">
        <div class="pill nodim">
          <span class="dot" [style.background]="dotColor()"></span>
          <span class="pill-text mono">{{ ws.status() }}</span>
        </div>
        <button class="pill" (click)="theme.toggle()">
          @if (theme.isDark()) {
            <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z"/>
            </svg>
            <span>Light</span>
          } @else {
            <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z"/>
            </svg>
            <span>Dark</span>
          }
        </button>
      </div>
    </nav>

    <!-- ─── Idle view ─── -->
    @if (!hasStarted()) {
      <div class="idle-view">
        <h1 class="heading">What do you want to automate?</h1>
        <div class="input-card" [class.focused]="focused()">
          <div class="textarea-wrap">
            <textarea
              [(ngModel)]="goal"
              rows="3"
              placeholder="Describe what Archon should do…"
              (focus)="focused.set(true)"
              (blur)="focused.set(false)"
              (keydown.enter)="onEnter($event)"
            ></textarea>
          </div>
          <div class="card-divider"></div>
          <div class="toolbar">
            <button class="dry-btn" (click)="toggleDry()">
              <span class="knob-wrap" [class.on]="dryRun()">
                <span class="knob" [class.on]="dryRun()"></span>
              </span>
              <span>{{ dryRun() ? 'Dry run' : 'Live' }}</span>
            </button>
            <button class="run-btn" (click)="run()" [disabled]="!goal.trim() || isRunning()">
              <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"/>
              </svg>
              <span>{{ dryRun() ? 'Simulate' : 'Run' }}</span>
            </button>
          </div>
        </div>
        <div class="chips">
          @for (s of suggestions; track s) {
            <button class="chip" (click)="goal = s">{{ s }}</button>
          }
        </div>
      </div>
    }

    <!-- ─── Active / Chat view ─── -->
    @if (hasStarted()) {
      <div class="chat-view">

        <!-- Chat messages -->
        <div class="chat-messages">
          @for (bubble of bubbles(); track $index) {

            <!-- User bubble -->
            @if (bubble.type === 'user') {
              <div class="bubble-row user-row">
                <div class="bubble user-bubble">{{ bubble.text }}</div>
              </div>
            }

            <!-- Agent bubble -->
            @if (bubble.type === 'agent') {
              <div class="bubble-row agent-row">
                <div class="agent-avatar">
                  <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="white" stroke-width="3">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/>
                  </svg>
                </div>
                <div class="bubble-wrap">
                  <div class="bubble agent-bubble">
                    <p style="margin-bottom: 4px;">{{ bubble.text }}</p>
                    @if (bubble.points && bubble.points.length > 0) {
                      <ul style="margin:0; padding-left:16px; display:flex; flex-direction:column; gap:3px;">
                        @for (point of bubble.points; track $index) {
                          <li style="font-size:12px; line-height:1.5;">{{ point }}</li>
                        }
                      </ul>
                    }
                  </div>
                  @if (bubble.rawSteps && bubble.rawSteps.length > 0) {
                    <button class="details-toggle" (click)="toggleDetails($index)">
                      {{ bubble.showDetails ? 'Hide details' : 'Show details' }}
                    </button>
                    @if (bubble.showDetails) {
                      <div class="raw-steps">
                        @for (step of bubble.rawSteps; track $index) {
                          <div class="raw-step">
                            <span class="raw-type">{{ step.type }}</span>
                            <span class="raw-text">{{ format(step) }}</span>
                          </div>
                        }
                      </div>
                    }
                  }
                </div>
              </div>
            }

            <!-- Error bubble -->
            @if (bubble.type === 'error') {
              <div class="bubble-row agent-row">
                <div class="agent-avatar error-avatar">
                  <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="white" stroke-width="3">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"/>
                  </svg>
                </div>
                <div class="bubble error-bubble">{{ bubble.text }}</div>
              </div>
            }

          }

          <!-- Thinking indicator -->
          @if (isRunning()) {
            <div class="bubble-row agent-row">
              <div class="agent-avatar">
                <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="white" stroke-width="3">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/>
                </svg>
              </div>
              <div class="bubble agent-bubble thinking-bubble">
                <span class="dot-bounce"></span>
                <span class="dot-bounce" style="animation-delay:150ms"></span>
                <span class="dot-bounce" style="animation-delay:300ms"></span>
              </div>
            </div>
          }
        </div>

        <!-- Bottom input bar -->
        <div class="chat-input-bar">
          <div class="chat-input-card" [class.focused]="focused()">
            <textarea
              [(ngModel)]="goal"
              rows="1"
              placeholder="Ask Archon something else…"
              (focus)="focused.set(true)"
              (blur)="focused.set(false)"
              (keydown.enter)="onEnter($event)"
            ></textarea>
            <div class="chat-toolbar">
              <button class="dry-btn" (click)="toggleDry()">
                <span class="knob-wrap" [class.on]="dryRun()">
                  <span class="knob" [class.on]="dryRun()"></span>
                </span>
                <span>{{ dryRun() ? 'Dry run' : 'Live' }}</span>
              </button>
              <button class="pill" (click)="reset()" style="margin-left:auto">New chat</button>
              <button class="run-btn" (click)="run()" [disabled]="!goal.trim() || isRunning()">
                <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"/>
                </svg>
              </button>
            </div>
          </div>
        </div>

      </div>
    }

  </div>
</div>
  `,
})
export class AppComponent implements OnDestroy {
  theme = inject(ThemeService);
  ws    = inject(WebsocketService);

  goal       = '';
  dryRun     = signal(true);
  isRunning  = signal(false);
  hasStarted = signal(false);
  focused    = signal(false);
  activeGoal = signal('');
  steps      = signal<WsMessage[]>([]);
  histOpen   = signal(false);
  history    = signal<HistoryItem[]>([]);
  bubbles    = signal<ChatBubble[]>([]);
  currentStepBuffer = signal<WsMessage[]>([]);
  summaryBuffer     = signal<string[]>([]);
  waitingForAnswer = signal(false);
  suggestions = [
    'Clean my Downloads folder',
    'Find and remove duplicate files',
    'Organize files by type',
    'Move files to a new folder',
  ];

  private sub?: Subscription;

  toggleHist(): void { this.histOpen.update(v => !v); }
  toggleDry():  void { this.dryRun.update(v => !v); }

  copyId(id: string): void {
    navigator.clipboard.writeText(id);
  }

  toggleDetails(index: number): void {
    this.bubbles.update(b => {
      const updated = [...b];
      if (updated[index]) {
        updated[index] = { ...updated[index], showDetails: !updated[index].showDetails };
      }
      return updated;
    });
  }

  onEnter(e: Event): void { e.preventDefault(); this.run(); }

  run(): void {
    if (!this.goal.trim() || this.isRunning()) return;
    const goal = this.goal.trim();

    if (this.waitingForAnswer()) {
    this.bubbles.update(b => [...b, { type: 'user', text: goal }]);
    this.isRunning.set(true);
    this.waitingForAnswer.set(false);
    this.ws.sendAnswer(goal);
    this.goal = '';
    return;
  }

    this.sub?.unsubscribe();
    this.ws.disconnect();
    this.steps.set([]);
    this.bubbles.update(b => [...b, { type: 'user', text: goal }]);
    this.currentStepBuffer.set([]);
    this.summaryBuffer.set([]);
    this.isRunning.set(true);
    this.hasStarted.set(true);
    this.activeGoal.set(goal);
    this.history.update(h => [{
      goal,
      dry: this.dryRun(),
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      sessionId: ''
    }, ...h]);

    this.sub = this.ws.messages$.subscribe((msg: WsMessage) => {
      if (msg.type === 'complete' && !msg.data?.['session_id']) return;

      this.steps.update(s => [...s, msg]);

      if (['thought','action','tool_result','observation'].includes(msg.type)) {
        this.currentStepBuffer.update(b => [...b, msg]);
      }

      // Collect summaries — skip empty ones (list_files returns "")
      if (msg.type === 'summary') {
        const text = msg.data['text'] ?? '';
        if (text.trim()) {
          this.summaryBuffer.update(b => [...b, text]);
        }
      }

      // On complete — ONE agent bubble with all summaries as bullet points
      if (msg.type === 'complete') {
        this.isRunning.set(false);
        this.ws.status.set('done');
        const sid = msg.data?.['session_id'] ?? '';
        const stepsRun = msg.data?.['steps_run'] ?? '?';
        const points = this.summaryBuffer();
        const raw = this.currentStepBuffer();

        this.bubbles.update(b => [...b, {
          type: 'agent',
          text: `Here's what I did (${stepsRun} steps):`,
          points: [...points],
          rawSteps: [...raw],
          showDetails: false
        }]);

        this.summaryBuffer.set([]);
        this.currentStepBuffer.set([]);

        this.history.update(h => {
          if (h.length === 0) return h;
          const updated = [...h];
          updated[0] = { ...updated[0], sessionId: sid };
          return updated;
        });
      }
      if (msg.type === 'ask_user') {
        this.isRunning.set(false);
        this.waitingForAnswer.set(true);  // ← keep socket open, flag answer mode
        const question = msg.data?.['question'] ?? 'Could you provide more details?';
        this.bubbles.update(b => [...b, {
          type: 'agent',
          text: question
        }]);
}
      // if (msg.type === 'ask_user') {
      //   this.isRunning.set(false);
      //   this.ws.status.set('done');
      //   const question = msg.data?.['question'] ?? 'Could you provide more details?';
      //   this.bubbles.update(b => [...b, {
      //     type: 'agent',
      //     text: question
      //   }]);
      // }

      if (msg.type === 'error') {
        this.isRunning.set(false);
        this.ws.status.set('done');
        this.bubbles.update(b => [...b, {
          type: 'error',
          text: msg.data?.['message'] ?? 'Something went wrong.'
        }]);
      }
    });


    this.ws.connect(goal, this.dryRun());
      this.goal = '';
    }

  reset(): void {
    this.sub?.unsubscribe();
    this.ws.disconnect();
    this.steps.set([]);
    this.bubbles.set([]);
    this.currentStepBuffer.set([]);
    this.summaryBuffer.set([]);
    this.isRunning.set(false);
    this.waitingForAnswer.set(false);
    this.hasStarted.set(false);
    this.goal = '';
  }

  dotColor(): string {
    const map: Record<string, string> = {
      idle: 'var(--border)', connecting: '#FBBF24',
      connected: '#34D399', disconnected: 'var(--border)',
      error: '#F87171', done: 'var(--border)',
    };
    return map[this.ws.status()] ?? 'var(--border)';
  }

  pillBg(type: string): string {
    const m: Record<string, string> = {
      start: 'rgba(59,130,246,.15)', iteration: 'rgba(148,163,184,.1)',
      thought: 'rgba(167,139,250,.15)', action: 'rgba(251,191,36,.15)',
      tool_result: 'rgba(52,211,153,.15)', observation: 'rgba(56,189,248,.15)',
      complete: 'rgba(52,211,153,.15)', error: 'rgba(239,68,68,.15)',
    };
    return m[type] ?? 'rgba(148,163,184,.1)';
  }

  pillColor(type: string): string {
    const m: Record<string, string> = {
      start: '#60A5FA', iteration: '#94A3B8', thought: '#A78BFA',
      action: '#FCD34D', tool_result: '#34D399', observation: '#38BDF8',
      complete: '#34D399', error: '#F87171',
    };
    return m[type] ?? '#94A3B8';
  }

  format(msg: WsMessage): string {
    const d = msg.data;
    if (!d) return '';
    switch (msg.type) {
      case 'start':       return `Goal: ${d['goal']} · ${d['dry_run'] ? 'dry run' : 'live'}`;
      case 'iteration':   return `Iteration ${d['iteration']} / ${d['max']}`;
      case 'thought':     return `${d['action']} — ${d['reasoning']}`;
      case 'action':      return `${d['tool']}(${JSON.stringify(d['params'])})`;
      case 'tool_result': return d['success'] ? `✓ ${d['message']}` : `✗ ${d['error']}`;
      case 'observation': return d['text'] ?? '';
      case 'complete':    return `Done · ${d['steps_run'] ?? '?'} steps · ${(d['session_id'] ?? '').slice(0, 8)}…`;
      case 'ask_user':    return d['question'] ?? '';
      case 'error':       return d['message'] ?? 'Unknown error';
      default:            return JSON.stringify(d);
    }
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
    this.ws.disconnect();
  }
}
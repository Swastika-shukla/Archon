import { Injectable, signal, effect } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  isDark = signal<boolean>(this._init());

  constructor() {
    effect(() => {
      document.documentElement.classList.toggle('dark', this.isDark());
      localStorage.setItem('archon-theme', this.isDark() ? 'dark' : 'light');
    });
  }

  toggle(): void { this.isDark.update(v => !v); }

  private _init(): boolean {
    const s = localStorage.getItem('archon-theme');
    if (s) return s === 'dark';
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  }
}
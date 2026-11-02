// omniscribe-studio/frontend-angular/src/app/app.component.ts
import { Component, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

export type StudioTheme = 'theme-dark' | 'theme-light' | 'theme-grey';

export interface ParagraphBlock {
  paragraph_index: number;
  version: number;
  original: string;
  edited: string;
}

export interface ChatMessage {
  sender_id: string;
  sender_name: string;
  content: string;
  timestamp: string;
  role?: string;
}

export interface TelemetryEvent {
  timestamp: string;
  service: string;
  event_type: string;
  message: string;
  progress?: number;
}

export interface ServiceDetail {
  connected: boolean;
  target: string;
  status: string;
}

export interface ServiceHealthStatus {
  status?: string;
  codename?: string;
  storage_target: 'docker' | 'local';
  sqlite_fallback_active: boolean;
  force_local_mode: boolean;
  services?: {
    postgres?: ServiceDetail;
    neo4j?: ServiceDetail;
    qdrant?: ServiceDetail;
    redis?: ServiceDetail;
  };
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent implements OnInit {
  // Splash Screen & Studio Theme State
  isBooting = signal<boolean>(true);
  bootStatusText = signal<string>('Initializing DaoForge Polyglot Engines (Postgres, Neo4j, Qdrant)...');
  activeTheme = signal<StudioTheme>('theme-dark');

  // Service Health & Storage Backend Configuration
  isSettingsOpen = signal<boolean>(false);
  serviceHealth = signal<ServiceHealthStatus>({
    storage_target: 'local',
    sqlite_fallback_active: true,
    force_local_mode: false,
    services: {
      postgres: { connected: false, target: 'data/trait_engine/traits.db', status: 'local_fallback' },
      neo4j: { connected: false, target: 'In-Memory Lore Graph Mock', status: 'offline' },
      qdrant: { connected: false, target: 'In-Memory Vector Store', status: 'offline' },
      redis: { connected: false, target: 'Direct Local Async Event Loop', status: 'offline' },
    }
  });

  // Project & Genre Configuration
  projectId = signal<string>('immortal-sovereign-vol1');
  chapterId = signal<string>('chapter-001');
  selectedGenre = signal<string>('xianxia');
  useUncensoredModel = signal<boolean>(false);
  scrapeUrlOrDir = signal<string>('');

  genres = [
    'xianxia', 'wuxia', 'martial_arts', 'wizardry', 'horror',
    'urban', 'fantasy', 'cyberpunk', 'steampunk', 'medieval', 'dark_romance'
  ];

  // Manuscript Paragraphs (Granular Versioned)
  paragraphs = signal<ParagraphBlock[]>([
    {
      paragraph_index: 0,
      version: 1,
      original: '第1章 问道长生。Lin Xuan sat cross-legged atop the Jade Cloud Peak, spiritual qi surging into his dantian.',
      edited: 'Atop Jade Cloud Peak, Lin Xuan sat cross-legged as vast tides of spiritual qi surged into his dantian.'
    },
    {
      paragraph_index: 1,
      version: 1,
      original: 'Below the mountain, Elder Mo drew his blood-stained saber with murderous intent.',
      edited: 'At the mountain base, Elder Mo unsheathed his blood-stained saber, cold killing intent locking onto the peak.'
    }
  ]);

  // Non-Blocking Multi-Agent Chat State
  chatInput = signal<string>('');
  activeTasksCount = signal<number>(0);
  chatMessages = signal<ChatMessage[]>([
    {
      sender_id: 'director_alfred',
      sender_name: 'Director Alfred (Orchestrator)',
      content: 'Welcome to OmniScribe Studio. You can dispatch multiple tasks in parallel—our council will tag specialists (@grandmaster_lin, @nyx_unfiltered, @kael_blades, @pip_continuity) asynchronously while you keep typing.',
      timestamp: new Date().toLocaleTimeString()
    }
  ]);

  // Live Progress & Telemetry Drawer
  isLogDrawerOpen = signal<boolean>(true);
  overallProgress = signal<number>(100);
  telemetryLogs = signal<TelemetryEvent[]>([]);

  private ws?: WebSocket;
  private readonly apiBase = 'http://localhost:8000';

  ngOnInit(): void {
    this.refreshHealthStatus();
    this.connectWebSocketStreams();
    setTimeout(() => {
      this.bootStatusText.set('Trait DNA Engine & 14B/Dao-9B Routers Online.');
      setTimeout(() => this.isBooting.set(false), 700);
    }, 1100);
  }

  setTheme(theme: StudioTheme): void {
    this.activeTheme.set(theme);
  }

  toggleSettingsModal(): void {
    this.isSettingsOpen.update((v) => !v);
    if (this.isSettingsOpen()) {
      this.refreshHealthStatus();
    }
  }

  async refreshHealthStatus(): Promise<void> {
    try {
      const res = await fetch(`${this.apiBase}/api/health`);
      if (res.ok) {
        const data = await res.json();
        this.serviceHealth.set({
          storage_target: data.storage_target || (data.sqlite_fallback_active ? 'local' : 'docker'),
          sqlite_fallback_active: !!data.sqlite_fallback_active,
          force_local_mode: !!data.force_local_mode,
          services: data.services || this.serviceHealth().services,
        });
      }
    } catch {
      // In offline / preview mode keep default fallback state
    }
  }

  async switchStorageTarget(mode: 'docker' | 'local'): Promise<void> {
    try {
      const res = await fetch(`${this.apiBase}/api/settings/storage-mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode })
      });
      if (res.ok) {
        const data = await res.json();
        this.serviceHealth.set({
          storage_target: data.storage_target || mode,
          sqlite_fallback_active: !!data.sqlite_fallback_active,
          force_local_mode: !!data.force_local_mode,
          services: data.services || this.serviceHealth().services,
        });
      } else {
        await this.refreshHealthStatus();
      }
    } catch {
      this.serviceHealth.update((curr) => ({ ...curr, storage_target: mode }));
    }
  }

  connectWebSocketStreams(): void {
    try {
      this.ws = new WebSocket('ws://localhost:8000/ws/stream');
      this.ws.onmessage = (event) => {
        const envelope = JSON.parse(event.data);
        const data = JSON.parse(envelope.payload);

        if (envelope.channel === 'omniscribe:chat_stream') {
          this.chatMessages.update((msgs) => [...msgs, data]);
          this.activeTasksCount.update((c) => Math.max(0, c - 1));
        } else if (envelope.channel === 'omniscribe:telemetry_stream') {
          this.telemetryLogs.update((logs) => [data, ...logs.slice(0, 99)]);
          if (typeof data.progress === 'number') {
            this.overallProgress.set(Math.round(data.progress * 100));
          }
        }
      };
    } catch {
      // Offline preview mode fallback
    }
  }

  async sendParallelChatMessage(): Promise<void> {
    const msg = this.chatInput().trim();
    if (!msg) return;

    // Immediately append user message & clear input so chat NEVER blocks
    this.chatMessages.update((msgs) => [
      ...msgs,
      {
        sender_id: 'author',
        sender_name: 'Author (You)',
        content: msg,
        timestamp: new Date().toLocaleTimeString()
      }
    ]);
    this.chatInput.set('');
    this.activeTasksCount.update((c) => c + 1);

    try {
      await fetch(`${this.apiBase}/api/chat/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: this.projectId(),
          message: msg,
          genre: this.selectedGenre()
        })
      });
    } catch {
      this.activeTasksCount.update((c) => Math.max(0, c - 1));
    }
  }

  async polishChapterParallel(): Promise<void> {
    this.overallProgress.set(10);
    try {
      const res = await fetch(`${this.apiBase}/api/editor/process-chapter`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: this.projectId(),
          chapter_id: this.chapterId(),
          paragraphs: this.paragraphs().map((p) => p.edited),
          genre_tag: this.selectedGenre(),
          use_uncensored_model: this.useUncensoredModel(),
          author_agent_id: this.useUncensoredModel() ? 'nyx_unfiltered' : 'grandmaster_lin'
        })
      });
      const data = await res.json();
      if (data.paragraphs) {
        this.paragraphs.set(data.paragraphs);
      }
    } finally {
      this.overallProgress.set(100);
    }
  }

  async undoParagraph(pIndex: number): Promise<void> {
    try {
      const res = await fetch(`${this.apiBase}/api/editor/undo-paragraph`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: this.projectId(),
          chapter_id: this.chapterId(),
          paragraph_index: pIndex
        })
      });
      const restored = await res.json();
      this.paragraphs.update((list) =>
        list.map((item) =>
          item.paragraph_index === pIndex
            ? { ...item, edited: restored.content, version: restored.restored_version }
            : item
        )
      );
    } catch {
      // Fallback local undo to original raw
      this.paragraphs.update((list) =>
        list.map((item) =>
          item.paragraph_index === pIndex
            ? { ...item, edited: item.original, version: Math.max(1, item.version - 1) }
            : item
        )
      );
    }
  }

  async rateAgent(rating: 'good' | 'bad', agentId: string): Promise<void> {
    this.chatInput.set(`/rate ${rating} ${agentId}`);
    await this.sendParallelChatMessage();
  }
}

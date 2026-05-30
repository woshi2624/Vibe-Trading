import { create } from "zustand";
import type { AgentMessage, ToolCallEntry } from "@/types/agent";

const SESSION_CACHE_MAX = 5;
const _sessionCache = new Map<string, AgentMessage[]>();

interface AgentState {
  messages: AgentMessage[];
  sessionId: string | null;
  status: "idle" | "streaming" | "error";
  streamingText: string;

  toolCalls: ToolCallEntry[];

  sseStatus: "disconnected" | "connected" | "reconnecting";
  sseRetryAttempt: number;

  addMessage: (msg: Omit<AgentMessage, "id"> & { id?: string }) => void;
  appendDelta: (delta: string) => void;
  setStatus: (s: AgentState["status"]) => void;
  setSessionId: (id: string | null) => void;
  loadHistory: (msgs: AgentMessage[]) => void;

  addToolCall: (entry: ToolCallEntry) => void;
  updateToolCall: (id: string, update: Partial<ToolCallEntry>) => void;

  cacheSession: (sid: string, msgs: AgentMessage[]) => void;
  getCachedSession: (sid: string) => AgentMessage[] | undefined;

  clearStreaming: () => void;

  setSseStatus: (s: AgentState["sseStatus"], retryAttempt?: number) => void;

  switchSession: (sid: string, msgs?: AgentMessage[]) => void;
  sessionLoading: boolean;
  setSessionLoading: (v: boolean) => void;

  reset: () => void;
}

let _id = 0;
const nextId = () => String(++_id);

export const useAgentStore = create<AgentState>((set) => ({
  messages: [],
  sessionId: null,
  status: "idle",
  streamingText: "",
  toolCalls: [],
  sseStatus: "disconnected",
  sseRetryAttempt: 0,
  sessionLoading: false,

  addMessage: (msg) =>
    set((s) => ({ messages: [...s.messages, { ...msg, id: msg.id || nextId() } as AgentMessage] })),

  appendDelta: (delta) =>
    set((s) => ({ streamingText: s.streamingText + delta })),

  setStatus: (status) => set({ status }),
  setSessionId: (sessionId) => set({ sessionId }),
  loadHistory: (msgs) => set({ messages: msgs }),

  addToolCall: (entry) =>
    set((s) => ({ toolCalls: [...s.toolCalls, entry] })),
  updateToolCall: (tool, update) =>
    set((s) => {
      // Match the most recent running entry for this tool name.
      // Falls back to the most recent entry of any status if none is running.
      let targetIdx = -1;
      for (let i = s.toolCalls.length - 1; i >= 0; i--) {
        if (s.toolCalls[i].tool === tool) {
          if (s.toolCalls[i].status === "running") { targetIdx = i; break; }
          if (targetIdx === -1) targetIdx = i;
        }
      }
      if (targetIdx === -1) return s;
      return {
        toolCalls: s.toolCalls.map((tc, i) => i === targetIdx ? { ...tc, ...update } : tc),
      };
    }),

  cacheSession: (sid, msgs) => {
    _sessionCache.delete(sid);
    _sessionCache.set(sid, msgs);
    if (_sessionCache.size > SESSION_CACHE_MAX) {
      const oldest = _sessionCache.keys().next().value;
      if (oldest) _sessionCache.delete(oldest);
    }
  },
  getCachedSession: (sid) => _sessionCache.get(sid),

  clearStreaming: () => set({ streamingText: "" }),

  setSseStatus: (sseStatus, retryAttempt) =>
    set({ sseStatus, sseRetryAttempt: retryAttempt ?? 0 }),

  switchSession: (sid, msgs) => {
    _id = 0;
    set({
      sessionId: sid,
      messages: msgs || [],
      status: "idle",
      streamingText: "",
      toolCalls: [],
      sessionLoading: !msgs,
    });
  },

  setSessionLoading: (sessionLoading) => set({ sessionLoading }),

  reset: () => {
    _id = 0;
    set({
      messages: [], status: "idle", streamingText: "",
      sessionId: null, toolCalls: [], sessionLoading: false,
    });
  },
}));

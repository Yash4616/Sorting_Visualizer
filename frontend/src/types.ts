export type RunStatus = "running" | "completed" | "cancelled" | "failed";

export type AppStateStatus =
  | "idle"
  | "starting"
  | "running"
  | "paused"
  | "cancelling"
  | "completed"
  | "failed";

export interface ComplexityInfo {
  best: string;
  avg: string;
  worst: string;
  space: string;
}

export interface ConfigPayload {
  algorithms: string[];
  inputTypes: string[];
  arraySize: {
    min: number;
    max: number;
    default: number;
    step?: number;
  };
  complexity: Record<string, ComplexityInfo>;
}

export interface SortStep {
  array: number[];
  comparing: number[];
  swapped: boolean;
  stepNumber: number;
  algorithm: string;
  comparisons: number;
  swaps: number;
}

export interface SortResult {
  algorithm: string;
  arraySize: number;
  inputType: string;
  durationMs: number;
  comparisons: number;
  swaps: number;
  steps: number;
  correct: boolean;
  complexity: string;
}

export interface PollResponse {
  runId: string;
  status: RunStatus;
  steps: SortStep[];
  nextCursor: number;
  totalSteps: number;
  hasMore: boolean;
  result: SortResult | null;
  error: string | null;
}

export interface AppState {
  status: AppStateStatus;
  runId: string | null;
  cursor: number;
  serverStatus: RunStatus | null;
  hasMoreFromServer: boolean;
  polling: boolean;
  pollIntervalId: number | null;
  animationFrameId: number | null;
  resizeObserver: ResizeObserver | null;
  startAbortController: AbortController | null;
  pollAbortController: AbortController | null;
  cancelAbortController: AbortController | null;
  queue: SortStep[];
  currentArray: number[];
  comparing: number[];
  swapped: boolean;
  pausedByUser: boolean;
  speed: number;
  result: SortResult | null;
  error: string | null;
  inlineError: string | null;
  totalSteps: number;
  lastStepTimestamp: number;
  lastThroughputStep: number;
  lastThroughputTime: number;
  completionSweep: number;
  droppedFramesCounter: number;
  configLoaded: boolean;
  renderPausedByVisibility: boolean;
  sizeMin: number;
  sizeMax: number;
  complexityByAlgorithm: Record<string, ComplexityInfo>;
}

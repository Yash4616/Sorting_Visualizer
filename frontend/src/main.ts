import "./styles.css";

import {
  API_BASE,
  MAX_QUEUE_BUFFER,
  MIN_QUEUE_BUFFER,
  MIN_RENDER_DELAY_MS,
  POLL_INTERVAL_MS,
  POLL_LIMIT,
  POLL_RETRY_BASE_MS,
  POLL_RETRY_COUNT,
  SPEED_DEFAULT,
  SPEED_MAX,
  SPEED_MIN,
  UI_MAX_SIZE,
  UI_MIN_SIZE,
  UI_SIZE_STEP,
} from "./config";
import type {
  AppState,
  AppStateStatus,
  ConfigPayload,
  PollResponse,
  RunStatus,
  SortResult,
  SortStep,
} from "./types";

const app = document.getElementById("app");
if (!app) {
  throw new Error("App container not found");
}
const appRoot = app;

appRoot.innerHTML = `
  <main class="layout">
    <section class="card control-card">
      <h1 class="title title-gradient">Sorting Visualizer</h1>
      <p class="subtitle" id="subtitle">Production-safe polling and rendering pipeline</p>

      <div class="control-grid">
        <label>
          Algorithm
          <select id="algorithm"></select>
        </label>

        <label>
          Input Type
          <select id="inputType"></select>
        </label>

        <label>
          Array Size
          <select id="arraySize"></select>
        </label>

        <label>
          Playback Speed
          <div class="speed-header">
            <span>Level</span>
            <span class="speed-pill" id="speedBadge">${SPEED_DEFAULT}x</span>
          </div>
          <input id="speed" type="range" min="${SPEED_MIN}" max="${SPEED_MAX}" value="${SPEED_DEFAULT}" />
        </label>
      </div>

      <div class="button-row">
        <button id="start" class="primary" disabled>Start</button>
        <button id="pause" class="secondary" disabled>Pause</button>
        <button id="stop" class="danger" disabled>Stop</button>
      </div>
      <p class="inline-error" id="inlineError" aria-live="polite"></p>

      <div class="stat-grid">
        <article class="stat-tile stat-steps"><div class="stat-label">Steps</div><div class="stat-value" id="steps">0</div></article>
        <article class="stat-tile stat-comparisons"><div class="stat-label">Comparisons</div><div class="stat-value" id="comparisons">0</div></article>
        <article class="stat-tile stat-swaps"><div class="stat-label">Swaps</div><div class="stat-value" id="swaps">0</div></article>
        <article class="stat-tile stat-elapsed"><div class="stat-label">Elapsed</div><div class="stat-value" id="elapsed">0.0 ms</div></article>
        <article class="stat-tile stat-throughput"><div class="stat-label">Bars/Sec</div><div class="stat-value" id="throughput">0.0</div></article>
      </div>
    </section>

    <section class="card canvas-card" id="canvasCard">
      <div class="canvas-header">
        <div class="status-pill status-idle" id="statusPill">
          <span class="status-dot"></span>
          <span class="status-label" id="statusLabel">Idle</span>
        </div>
        <div class="canvas-meta" id="canvasMeta">0 / 0</div>
      </div>

      <div class="progress-track" aria-hidden="true">
        <div class="progress-fill" id="progressFill"></div>
      </div>

      <canvas id="chart"></canvas>

      <section class="complexity-panel card-lite">
        <h2 class="complexity-title" id="complexityTitle">Big-O Details</h2>
        <div class="complexity-grid">
          <article class="complexity-tile"><span class="complexity-badge badge-best">Best</span><strong id="complexityBest">N/A</strong></article>
          <article class="complexity-tile"><span class="complexity-badge badge-avg">Average</span><strong id="complexityAvg">N/A</strong></article>
          <article class="complexity-tile"><span class="complexity-badge badge-worst">Worst</span><strong id="complexityWorst">N/A</strong></article>
          <article class="complexity-tile"><span class="complexity-badge badge-space">Space</span><strong id="complexitySpace">N/A</strong></article>
        </div>
      </section>

      <div class="summary" id="summary">Loading configuration...</div>
    </section>
  </main>
`;

const subtitle = document.getElementById("subtitle") as HTMLParagraphElement;
const algorithmSelect = document.getElementById("algorithm") as HTMLSelectElement;
const inputTypeSelect = document.getElementById("inputType") as HTMLSelectElement;
const arraySizeSelect = document.getElementById("arraySize") as HTMLSelectElement;
const speedInput = document.getElementById("speed") as HTMLInputElement;
const speedBadge = document.getElementById("speedBadge") as HTMLSpanElement;
const startButton = document.getElementById("start") as HTMLButtonElement;
const pauseButton = document.getElementById("pause") as HTMLButtonElement;
const stopButton = document.getElementById("stop") as HTMLButtonElement;
const inlineError = document.getElementById("inlineError") as HTMLParagraphElement;
const statusPill = document.getElementById("statusPill") as HTMLDivElement;
const statusLabel = document.getElementById("statusLabel") as HTMLSpanElement;
const canvasMeta = document.getElementById("canvasMeta") as HTMLDivElement;
const progressFill = document.getElementById("progressFill") as HTMLDivElement;
const summary = document.getElementById("summary") as HTMLDivElement;

const complexityTitle = document.getElementById("complexityTitle") as HTMLHeadingElement;
const complexityBest = document.getElementById("complexityBest") as HTMLElement;
const complexityAvg = document.getElementById("complexityAvg") as HTMLElement;
const complexityWorst = document.getElementById("complexityWorst") as HTMLElement;
const complexitySpace = document.getElementById("complexitySpace") as HTMLElement;

const stepValue = document.getElementById("steps") as HTMLDivElement;
const comparisonsValue = document.getElementById("comparisons") as HTMLDivElement;
const swapsValue = document.getElementById("swaps") as HTMLDivElement;
const elapsedValue = document.getElementById("elapsed") as HTMLDivElement;
const throughputValue = document.getElementById("throughput") as HTMLDivElement;

const canvas = document.getElementById("chart") as HTMLCanvasElement;
const maybeCtx = canvas.getContext("2d");
if (!maybeCtx) {
  throw new Error("Canvas context unavailable");
}
const ctx: CanvasRenderingContext2D = maybeCtx;

const VALID_TRANSITIONS: Record<AppStateStatus, ReadonlySet<AppStateStatus>> = {
  idle: new Set(["starting"]),
  starting: new Set(["running", "failed", "idle", "cancelling"]),
  running: new Set(["paused", "cancelling", "completed", "failed"]),
  paused: new Set(["running", "cancelling", "completed", "failed"]),
  cancelling: new Set(["completed", "failed", "idle"]),
  completed: new Set(["starting", "idle"]),
  failed: new Set(["starting", "idle"]),
};

const STATUS_CLASS_MAP: Record<AppStateStatus, string> = {
  idle: "status-idle",
  starting: "status-running",
  running: "status-running",
  paused: "status-paused",
  cancelling: "status-paused",
  completed: "status-completed",
  failed: "status-failed",
};

const state: AppState = {
  status: "idle",
  runId: null,
  cursor: 0,
  serverStatus: null,
  hasMoreFromServer: false,
  polling: false,
  pollIntervalId: null,
  animationFrameId: null,
  resizeObserver: null,
  startAbortController: null,
  pollAbortController: null,
  cancelAbortController: null,
  queue: [],
  currentArray: [],
  comparing: [],
  swapped: false,
  pausedByUser: false,
  speed: SPEED_DEFAULT,
  result: null,
  error: null,
  inlineError: null,
  totalSteps: 0,
  lastStepTimestamp: 0,
  lastThroughputStep: 0,
  lastThroughputTime: performance.now(),
  completionSweep: 0,
  droppedFramesCounter: 0,
  configLoaded: false,
  renderPausedByVisibility: false,
  sizeMin: UI_MIN_SIZE,
  sizeMax: UI_MAX_SIZE,
  complexityByAlgorithm: {},
};

function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function toDisplayError(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message;
  }
  return fallback;
}

function resetAbortController(controller: AbortController | null): void {
  if (controller) {
    controller.abort();
  }
}

function createAbortController(): AbortController {
  return new AbortController();
}

function makeOption(value: string): HTMLOptionElement {
  const option = document.createElement("option");
  option.value = value;
  option.textContent = value;
  return option;
}

function makeNumberOption(value: number): HTMLOptionElement {
  const option = document.createElement("option");
  option.value = String(value);
  option.textContent = String(value);
  return option;
}

function setSummary(parts: string[]): void {
  if (parts.length === 0) {
    summary.textContent = "";
    return;
  }

  summary.innerHTML = parts
    .map((part, index) => {
      const segment = `<span class="summary-seg summary-seg-${index + 1}">${part}</span>`;
      return index < parts.length - 1 ? `${segment}<span class="summary-pipe"> | </span>` : segment;
    })
    .join("");
}

function setInlineError(message: string | null): void {
  state.inlineError = message;
  inlineError.textContent = message ?? "";
  inlineError.classList.toggle("visible", Boolean(message));
}

function statusTextFromState(): string {
  if (state.status === "completed" && state.serverStatus === "cancelled") {
    return "Cancelled";
  }
  if (state.status === "starting") {
    return "Starting";
  }
  if (state.status === "running") {
    return "Running";
  }
  if (state.status === "paused") {
    return "Paused";
  }
  if (state.status === "cancelling") {
    return "Cancelling";
  }
  if (state.status === "completed") {
    return "Completed";
  }
  if (state.status === "failed") {
    return "Failed";
  }
  return "Idle";
}

function updateStatusPill(): void {
  statusLabel.textContent = statusTextFromState();
  statusPill.classList.remove("status-idle", "status-running", "status-completed", "status-failed", "status-paused");
  statusPill.classList.add(STATUS_CLASS_MAP[state.status]);
}

function syncUI(): void {
  const status = state.status;

  const canStart = state.configLoaded && (status === "idle" || status === "completed" || status === "failed");
  const canPause = status === "running" || status === "paused";
  const canStop = status === "starting" || status === "running" || status === "paused" || status === "cancelling";

  startButton.disabled = !canStart;
  pauseButton.disabled = !canPause;
  stopButton.disabled = !canStop;

  pauseButton.textContent = status === "paused" ? "Resume" : "Pause";

  const disableControls = status === "starting" || status === "running" || status === "paused" || status === "cancelling";
  algorithmSelect.disabled = disableControls || !state.configLoaded;
  inputTypeSelect.disabled = disableControls || !state.configLoaded;
  arraySizeSelect.disabled = disableControls || !state.configLoaded;

  // Speed is intentionally adjustable during active playback.
  speedInput.disabled = !state.configLoaded || status === "starting";

  updateStatusPill();
}

function transitionTo(next: AppStateStatus, reason: string): boolean {
  if (state.status === next) {
    syncUI();
    return true;
  }

  const allowed = VALID_TRANSITIONS[state.status];
  if (!allowed.has(next)) {
    console.warn(`Ignored invalid state transition: ${state.status} -> ${next} (${reason})`);
    return false;
  }

  state.status = next;
  syncUI();
  return true;
}

function updateSpeedTrackFill(): void {
  const min = Number(speedInput.min || SPEED_MIN);
  const max = Number(speedInput.max || SPEED_MAX);
  const current = Number(speedInput.value || SPEED_DEFAULT);
  const percent = ((current - min) / Math.max(1, max - min)) * 100;
  speedInput.style.setProperty("--fill-percent", `${percent.toFixed(2)}%`);
}

function updateProgress(stepNumber: number): void {
  const total = Math.max(0, state.totalSteps);
  const safeStep = Math.max(0, stepNumber);
  const ratio = total > 0 ? Math.min(1, safeStep / total) : 0;
  progressFill.style.width = `${(ratio * 100).toFixed(2)}%`;
  canvasMeta.textContent = `${safeStep.toLocaleString()} / ${total.toLocaleString()}`;
}

function updateComplexityPanel(): void {
  const algorithm = algorithmSelect.value;
  const info = state.complexityByAlgorithm[algorithm];

  complexityTitle.textContent = algorithm ? `Big-O Details (${algorithm})` : "Big-O Details";
  complexityBest.textContent = info?.best ?? "N/A";
  complexityAvg.textContent = info?.avg ?? "N/A";
  complexityWorst.textContent = info?.worst ?? "N/A";
  complexitySpace.textContent = info?.space ?? "N/A";
}

function speedToDelay(speed: number): number {
  const normalized = Math.max(SPEED_MIN, Math.min(SPEED_MAX, speed));
  const ratio = (SPEED_MAX - normalized) / Math.max(1, SPEED_MAX - SPEED_MIN);
  return Math.max(MIN_RENDER_DELAY_MS, Math.round(MIN_RENDER_DELAY_MS + ratio * 120));
}

function updateStatsFromStep(step: SortStep): void {
  stepValue.textContent = String(step.stepNumber);
  comparisonsValue.textContent = String(step.comparisons);
  swapsValue.textContent = String(step.swaps);
  updateProgress(step.stepNumber);

  const now = performance.now();
  const stepDelta = Math.max(0, step.stepNumber - state.lastThroughputStep);
  const timeDeltaSec = (now - state.lastThroughputTime) / 1000;
  if (timeDeltaSec >= 0.15) {
    const throughput = stepDelta / Math.max(0.001, timeDeltaSec);
    throughputValue.textContent = throughput.toFixed(1);
    state.lastThroughputStep = step.stepNumber;
    state.lastThroughputTime = now;
  }
}

function updateStatsFromResult(result: SortResult): void {
  stepValue.textContent = String(result.steps);
  comparisonsValue.textContent = String(result.comparisons);
  swapsValue.textContent = String(result.swaps);
  elapsedValue.textContent = `${result.durationMs.toFixed(2)} ms`;
  updateProgress(result.steps);

  const durationSec = result.durationMs / 1000;
  const throughput = durationSec > 0 ? result.steps / durationSec : 0;
  throughputValue.textContent = throughput.toFixed(1);
}

function resetRunVisualState(): void {
  state.cursor = 0;
  state.serverStatus = null;
  state.hasMoreFromServer = false;
  state.queue = [];
  state.currentArray = [];
  state.comparing = [];
  state.swapped = false;
  state.result = null;
  state.error = null;
  state.totalSteps = 0;
  state.lastStepTimestamp = 0;
  state.lastThroughputStep = 0;
  state.lastThroughputTime = performance.now();
  state.completionSweep = 0;
  state.droppedFramesCounter = 0;
  state.pausedByUser = false;

  elapsedValue.textContent = "0.0 ms";
  stepValue.textContent = "0";
  comparisonsValue.textContent = "0";
  swapsValue.textContent = "0";
  throughputValue.textContent = "0.0";
  updateProgress(0);
}

function clampArraySize(raw: number): number {
  return Math.max(state.sizeMin, Math.min(state.sizeMax, raw));
}

function nearestSizeOption(values: number[], target: number): number {
  if (values.length === 0) {
    return target;
  }

  let best = values[0];
  let bestDistance = Math.abs(best - target);
  for (let index = 1; index < values.length; index += 1) {
    const candidate = values[index];
    const distance = Math.abs(candidate - target);
    if (distance < bestDistance) {
      best = candidate;
      bestDistance = distance;
    }
  }
  return best;
}

async function fetchConfig(): Promise<ConfigPayload> {
  const controller = createAbortController();
  try {
    const response = await fetch(apiUrl("/api/config"), {
      method: "GET",
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`Failed to load API configuration (${response.status})`);
    }

    return (await response.json()) as ConfigPayload;
  } catch (error) {
    if (isAbortError(error)) {
      throw new Error("Configuration request aborted");
    }
    throw error;
  } finally {
    controller.abort();
  }
}

function applyConfig(config: ConfigPayload): void {
  state.complexityByAlgorithm = config.complexity ?? {};

  state.sizeMin = Math.max(UI_MIN_SIZE, Number(config.arraySize?.min ?? UI_MIN_SIZE));
  state.sizeMax = Math.min(UI_MAX_SIZE, Number(config.arraySize?.max ?? UI_MAX_SIZE));
  if (state.sizeMin > state.sizeMax) {
    state.sizeMin = UI_MIN_SIZE;
    state.sizeMax = UI_MAX_SIZE;
  }

  algorithmSelect.replaceChildren(...config.algorithms.map(makeOption));
  inputTypeSelect.replaceChildren(...config.inputTypes.map(makeOption));

  const sizeOptions: HTMLOptionElement[] = [];
  const step = Math.max(1, Number(config.arraySize?.step ?? UI_SIZE_STEP));
  for (let size = state.sizeMin; size <= state.sizeMax; size += step) {
    sizeOptions.push(makeNumberOption(size));
  }

  const availableSizes = sizeOptions.map((option) => Number(option.value));
  if (availableSizes.length === 0 || availableSizes[availableSizes.length - 1] !== state.sizeMax) {
    sizeOptions.push(makeNumberOption(state.sizeMax));
  }

  arraySizeSelect.replaceChildren(...sizeOptions);

  const defaultAlgorithm = config.algorithms[0] ?? "";
  const defaultInput = config.inputTypes[0] ?? "";
  const rawDefaultSize = clampArraySize(Number(config.arraySize?.default ?? state.sizeMax));
  const finalSizes = sizeOptions.map((option) => Number(option.value));
  const defaultSize = nearestSizeOption(finalSizes, rawDefaultSize);

  algorithmSelect.value = defaultAlgorithm;
  inputTypeSelect.value = defaultInput;
  arraySizeSelect.value = String(defaultSize);

  speedInput.min = String(SPEED_MIN);
  speedInput.max = String(SPEED_MAX);
  speedInput.value = String(SPEED_DEFAULT);
  state.speed = SPEED_DEFAULT;
  speedBadge.textContent = `${state.speed}x`;
  updateSpeedTrackFill();

  state.configLoaded = true;
  subtitle.textContent = "Backend-configured controls with resilient polling and rendering";
  updateComplexityPanel();
  updateProgress(0);
  setSummary(["Ready", "Select options", "Press Start"]);
  syncUI();
}

function parseBackendError(payload: unknown, fallback: string): string {
  if (payload && typeof payload === "object" && "error" in payload) {
    const candidate = (payload as { error?: unknown }).error;
    if (typeof candidate === "string" && candidate.trim().length > 0) {
      return candidate;
    }
  }
  return fallback;
}

async function requestCreateRun(): Promise<boolean> {
  const selectedAlgorithm = algorithmSelect.value;
  const selectedInput = inputTypeSelect.value;
  const selectedSize = clampArraySize(Number(arraySizeSelect.value));
  arraySizeSelect.value = String(selectedSize);

  resetAbortController(state.startAbortController);
  state.startAbortController = createAbortController();

  try {
    const response = await fetch(apiUrl("/api/runs"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        algorithm: selectedAlgorithm,
        inputType: selectedInput,
        arraySize: selectedSize,
      }),
      signal: state.startAbortController.signal,
    });

    if (response.status === 400) {
      const payload = (await response.json()) as unknown;
      setInlineError(parseBackendError(payload, "Invalid request"));
      transitionTo("idle", "validation failure");
      return false;
    }

    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as unknown;
      throw new Error(parseBackendError(payload, `Unable to create run (${response.status})`));
    }

    const payload = (await response.json()) as { runId?: string };
    if (!payload.runId) {
      throw new Error("Backend did not return a run identifier");
    }

    state.runId = payload.runId;
    state.cursor = 0;
    state.hasMoreFromServer = true;
    state.serverStatus = "running";
    state.completionSweep = 0;
    transitionTo("running", "run created");
    setSummary(["Streaming run from backend", selectedAlgorithm, `${selectedSize} items`]);
    return true;
  } catch (error) {
    if (isAbortError(error)) {
      transitionTo("idle", "start request aborted");
      return false;
    }

    state.error = toDisplayError(error, "Unable to start run");
    transitionTo("failed", "start request failed");
    setSummary([`Start failed: ${state.error}`]);
    return false;
  } finally {
    state.startAbortController = null;
  }
}

function stopPollingLoop(): void {
  if (state.pollIntervalId !== null) {
    window.clearInterval(state.pollIntervalId);
    state.pollIntervalId = null;
  }
}

function startPollingLoop(): void {
  if (state.pollIntervalId !== null) {
    return;
  }

  state.pollIntervalId = window.setInterval(() => {
    void pollTick();
  }, POLL_INTERVAL_MS);
}

async function fetchPollWithRetry(runId: string, cursor: number, limit: number): Promise<PollResponse> {
  let backoff = POLL_RETRY_BASE_MS;

  for (let attempt = 0; attempt <= POLL_RETRY_COUNT; attempt += 1) {
    resetAbortController(state.pollAbortController);
    state.pollAbortController = createAbortController();

    try {
      const response = await fetch(apiUrl(`/api/runs/${runId}?cursor=${cursor}&limit=${limit}`), {
        method: "GET",
        headers: { Accept: "application/json" },
        signal: state.pollAbortController.signal,
      });

      if (response.status === 404) {
        throw new Error("Server restarted — run lost");
      }

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as unknown;
        throw new Error(parseBackendError(payload, `Polling failed (${response.status})`));
      }

      return (await response.json()) as PollResponse;
    } catch (error) {
      if (isAbortError(error)) {
        throw error;
      }
      if (attempt >= POLL_RETRY_COUNT) {
        throw error;
      }
      await sleep(backoff);
      backoff *= 2;
    } finally {
      state.pollAbortController = null;
    }
  }

  throw new Error("Polling failed");
}

function isTerminalServerStatus(status: RunStatus): boolean {
  return status === "completed" || status === "cancelled" || status === "failed";
}

function finalizeClientRun(status: RunStatus): void {
  stopPollingLoop();
  resetAbortController(state.pollAbortController);
  resetAbortController(state.startAbortController);
  resetAbortController(state.cancelAbortController);

  state.pollAbortController = null;
  state.startAbortController = null;
  state.cancelAbortController = null;
  state.hasMoreFromServer = false;
  state.runId = null;
  state.cursor = 0;
  state.pausedByUser = false;

  if (status === "completed" && state.result) {
    transitionTo("completed", "run finalized");
    updateStatsFromResult(state.result);
    setSummary([
      `${state.result.algorithm} on ${state.result.arraySize} items`,
      `Input: ${state.result.inputType}`,
      `Complexity: ${state.result.complexity}`,
      `Correct: ${state.result.correct ? "Yes" : "No"}`,
    ]);
    return;
  }

  if (status === "cancelled") {
    state.serverStatus = "cancelled";
    transitionTo("completed", "run cancelled");
    setSummary(["Run cancelled by user."]);
    return;
  }

  transitionTo("failed", "run failed");
  const message = state.error ?? "Run failed";
  setSummary([`Run failed: ${message}`]);
}

async function pollTick(): Promise<void> {
  if (!state.runId) {
    return;
  }
  if (state.polling) {
    return;
  }

  if (!state.hasMoreFromServer && state.serverStatus && isTerminalServerStatus(state.serverStatus)) {
    if (state.queue.length === 0) {
      finalizeClientRun(state.serverStatus);
    }
    return;
  }

  const budget = Math.max(0, MAX_QUEUE_BUFFER - state.queue.length);
  if (budget <= 0) {
    return;
  }

  const limit = Math.max(MIN_QUEUE_BUFFER, Math.min(POLL_LIMIT, budget));

  state.polling = true;
  try {
    const payload = await fetchPollWithRetry(state.runId, state.cursor, limit);

    state.cursor = payload.nextCursor;
    state.totalSteps = Math.max(state.totalSteps, payload.totalSteps ?? 0);
    state.hasMoreFromServer = payload.hasMore;
    state.serverStatus = payload.status;

    if (payload.status === "completed" && payload.result) {
      state.result = payload.result;
    }
    if (payload.status === "failed") {
      state.error = payload.error ?? "Run failed";
    }

    if (payload.steps.length > 0) {
      state.queue.push(...payload.steps);
    }

    const displayedStep = Number(stepValue.textContent ?? "0") || 0;
    updateProgress(displayedStep);

    if (payload.status === "running" && state.status !== "paused" && state.status !== "cancelling") {
      transitionTo("running", "poll status running");
    }

    if (isTerminalServerStatus(payload.status) && !payload.hasMore && state.queue.length === 0) {
      finalizeClientRun(payload.status);
    }
  } catch (error) {
    if (isAbortError(error)) {
      return;
    }

    state.error = toDisplayError(error, "Polling failed");
    state.serverStatus = "failed";
    state.hasMoreFromServer = false;
    state.queue = [];
    finalizeClientRun("failed");
  } finally {
    state.polling = false;
  }
}

async function requestCancelRun(useKeepAlive: boolean): Promise<void> {
  if (state.status === "idle" || state.status === "completed" || state.status === "failed") {
    return;
  }

  const runIdToCancel = state.runId;
  transitionTo("cancelling", "cancel requested");
  state.pausedByUser = false;

  stopPollingLoop();
  resetAbortController(state.startAbortController);
  resetAbortController(state.pollAbortController);
  resetAbortController(state.cancelAbortController);
  state.startAbortController = null;
  state.pollAbortController = null;
  state.cancelAbortController = null;

  // Make Stop immediate in the UI; backend cancellation is best-effort.
  state.queue = [];
  state.hasMoreFromServer = false;
  state.serverStatus = "cancelled";
  finalizeClientRun("cancelled");

  if (!runIdToCancel) {
    return;
  }

  const localCancelController = createAbortController();
  try {
    const response = await fetch(apiUrl(`/api/runs/${runIdToCancel}/cancel`), {
      method: "POST",
      headers: { Accept: "application/json" },
      signal: localCancelController.signal,
      keepalive: useKeepAlive,
    });

    if (!response.ok && response.status !== 404) {
      const payload = (await response.json().catch(() => null)) as unknown;
      console.warn(parseBackendError(payload, `Cancel failed (${response.status})`));
    }
  } catch (error) {
    if (!isAbortError(error)) {
      console.warn(toDisplayError(error, "Cancel request failed after local stop"));
    }
  }
}

function drawRoundedRect(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
): void {
  const radius = Math.max(0, Math.min(r, w / 2, h / 2));
  context.beginPath();
  context.moveTo(x + radius, y);
  context.lineTo(x + w - radius, y);
  context.quadraticCurveTo(x + w, y, x + w, y + radius);
  context.lineTo(x + w, y + h - radius);
  context.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
  context.lineTo(x + radius, y + h);
  context.quadraticCurveTo(x, y + h, x, y + h - radius);
  context.lineTo(x, y + radius);
  context.quadraticCurveTo(x, y, x + radius, y);
  context.closePath();
}

function resizeCanvas(): { width: number; height: number } {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;

  const displayWidth = Math.max(1, Math.floor(rect.width));
  const displayHeight = Math.max(1, Math.floor(rect.height));

  const targetWidth = Math.floor(displayWidth * dpr);
  const targetHeight = Math.floor(displayHeight * dpr);

  if (canvas.width !== targetWidth || canvas.height !== targetHeight) {
    canvas.width = targetWidth;
    canvas.height = targetHeight;
  }

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { width: displayWidth, height: displayHeight };
}

function darkenHex(hex: string, amount: number): string {
  const normalized = hex.replace("#", "");
  const value = Number.parseInt(normalized, 16);
  const r = (value >> 16) & 255;
  const g = (value >> 8) & 255;
  const b = value & 255;

  const factor = Math.max(0, Math.min(1, 1 - amount));
  const nr = Math.round(r * factor);
  const ng = Math.round(g * factor);
  const nb = Math.round(b * factor);

  const packed = (nr << 16) | (ng << 8) | nb;
  return `#${packed.toString(16).padStart(6, "0")}`;
}

function drawValueLabel(text: string, x: number, y: number): void {
  ctx.font = "600 11px JetBrains Mono";
  ctx.textAlign = "center";
  ctx.fillStyle = "rgba(255, 255, 255, 0.9)";
  ctx.fillText(text, x, y);
}

function drawFrame(width: number, height: number): void {
  const array = state.currentArray;
  const comparing = state.comparing;
  const swapped = state.swapped;
  const status = state.status;
  const completionSweep = state.completionSweep;

  const background = ctx.createLinearGradient(0, 0, 0, height);
  background.addColorStop(0, "#0a0a0a");
  background.addColorStop(1, "#000000");

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = background;
  ctx.fillRect(0, 0, width, height);

  if (array.length === 0) {
    ctx.fillStyle = "#f5f5f5";
    ctx.font = "600 18px Space Grotesk";
    ctx.textAlign = "center";
    ctx.fillText("Start a run to visualize sorting", width / 2, height / 2);
    return;
  }

  const n = array.length;
  const maxValue = array.reduce((acc, value) => (value > acc ? value : acc), 0) || 1;
  const minValue = array.reduce((acc, value) => (value < acc ? value : acc), array[0]);
  const maxIndex = array.findIndex((value) => value === maxValue);
  const minIndex = array.findIndex((value) => value === minValue);

  const paddingX = 14;
  const paddingBottom = 24;
  const topGap = 18;
  const chartHeight = height - topGap - paddingBottom;
  const usableWidth = width - paddingX * 2;
  const barWidth = usableWidth / n;

  ctx.strokeStyle = "rgba(255, 255, 255, 0.18)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(paddingX, height - paddingBottom + 0.5);
  ctx.lineTo(width - paddingX, height - paddingBottom + 0.5);
  ctx.stroke();

  for (let i = 0; i < n; i += 1) {
    const value = array[i];
    const normalized = value / maxValue;
    const barHeight = Math.max(2, normalized * chartHeight);
    const x = paddingX + i * barWidth;
    const y = height - paddingBottom - barHeight;
    const w = Math.max(1, barWidth - 1.4);

    const baseTop = "#e5e7eb";
    const baseBottom = darkenHex(baseTop, 0.3);

    let topColor = baseTop;
    let bottomColor = baseBottom;

    if (status === "completed" && state.serverStatus === "completed" && i <= completionSweep) {
      topColor = "#86efac";
      bottomColor = darkenHex("#22c55e", 0.3);
    }

    const isComparing = comparing.includes(i);
    if (isComparing && swapped) {
      topColor = "#ff9a62";
      bottomColor = darkenHex("#ff6b35", 0.3);
      ctx.shadowColor = "#ff6b35";
      ctx.shadowBlur = 12;
    } else if (isComparing) {
      topColor = "#ffffff";
      bottomColor = darkenHex("#ffffff", 0.3);
      ctx.shadowColor = "#ffffff";
      ctx.shadowBlur = 12;
    } else {
      ctx.shadowBlur = 0;
      ctx.shadowColor = "transparent";
    }

    drawRoundedRect(ctx, x, y, w, barHeight, Math.min(4, w / 2));
    const barGradient = ctx.createLinearGradient(0, y, 0, y + barHeight);
    barGradient.addColorStop(0, topColor);
    barGradient.addColorStop(1, bottomColor);
    ctx.fillStyle = barGradient;
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.shadowColor = "transparent";
  }

  if (n <= 30) {
    const maxX = paddingX + maxIndex * barWidth + barWidth / 2;
    const maxY = height - paddingBottom - (maxValue / maxValue) * chartHeight;
    drawValueLabel(`max:${maxValue}`, maxX, Math.max(14, maxY - 8));

    const minX = paddingX + minIndex * barWidth + barWidth / 2;
    const minY = height - paddingBottom - (minValue / maxValue) * chartHeight;
    drawValueLabel(`min:${minValue}`, minX, Math.max(14, minY - 8));
  }
}

function stopRenderLoop(): void {
  if (state.animationFrameId !== null) {
    window.cancelAnimationFrame(state.animationFrameId);
    state.animationFrameId = null;
  }
}

function renderLoop(timestamp: number): void {
  const { width, height } = resizeCanvas();

  if (state.queue.length > MAX_QUEUE_BUFFER) {
    state.droppedFramesCounter += 1;
    if (state.droppedFramesCounter % 60 === 0) {
      console.warn(`Queue pressure detected (${state.queue.length} pending steps)`);
    }
  }

  const delay = speedToDelay(state.speed);
  const shouldConsume =
    (state.status === "running" || state.status === "cancelling") &&
    !state.pausedByUser &&
    state.queue.length > 0 &&
    timestamp - state.lastStepTimestamp >= delay;

  if (shouldConsume) {
    const nextStep = state.queue.shift();
    if (nextStep) {
      state.currentArray = nextStep.array;
      state.comparing = nextStep.comparing;
      state.swapped = nextStep.swapped;
      updateStatsFromStep(nextStep);
      state.lastStepTimestamp = timestamp;
    }
  }

  if (
    state.status === "completed" &&
    state.serverStatus === "completed" &&
    state.completionSweep < state.currentArray.length - 1
  ) {
    state.completionSweep += 1;
  }

  if (state.runId && state.serverStatus && isTerminalServerStatus(state.serverStatus) && !state.hasMoreFromServer) {
    if (state.queue.length === 0) {
      finalizeClientRun(state.serverStatus);
    }
  }

  drawFrame(width, height);

  state.animationFrameId = window.requestAnimationFrame(renderLoop);
}

function startRenderLoop(): void {
  if (state.animationFrameId !== null || state.renderPausedByVisibility) {
    return;
  }
  state.animationFrameId = window.requestAnimationFrame(renderLoop);
}

function installResizeObserver(): void {
  if (state.resizeObserver) {
    state.resizeObserver.disconnect();
  }

  state.resizeObserver = new ResizeObserver(() => {
    resizeCanvas();
  });

  state.resizeObserver.observe(canvas);
}

function handleVisibilityChange(): void {
  if (document.hidden) {
    state.renderPausedByVisibility = true;
    stopRenderLoop();
    return;
  }

  state.renderPausedByVisibility = false;
  startRenderLoop();
}

function cleanupRuntime(sendCancelBeacon: boolean): void {
  stopPollingLoop();
  stopRenderLoop();

  if (sendCancelBeacon && state.runId) {
    try {
      navigator.sendBeacon(apiUrl(`/api/runs/${state.runId}/cancel`), "");
    } catch {
      // best-effort only
    }
  }

  resetAbortController(state.startAbortController);
  resetAbortController(state.pollAbortController);
  resetAbortController(state.cancelAbortController);
  state.startAbortController = null;
  state.pollAbortController = null;
  state.cancelAbortController = null;

  if (state.resizeObserver) {
    state.resizeObserver.disconnect();
    state.resizeObserver = null;
  }
}

function renderBootstrapError(message: string): void {
  cleanupRuntime(false);
  appRoot.innerHTML = `
    <main class="startup-error-wrap">
      <section class="card startup-error-card">
        <h1 class="title">Initialization Failed</h1>
        <p class="subtitle">The app could not load backend configuration.</p>
        <p class="startup-error-message">${message}</p>
      </section>
    </main>
  `;
}

function bindEvents(): void {
  algorithmSelect.addEventListener("change", () => {
    updateComplexityPanel();
  });

  speedInput.addEventListener("input", () => {
    state.speed = Number(speedInput.value);
    speedBadge.textContent = `${state.speed}x`;
    updateSpeedTrackFill();
  });

  startButton.addEventListener("click", () => {
    void handleStartClick();
  });

  pauseButton.addEventListener("click", () => {
    if (state.status === "running") {
      if (transitionTo("paused", "pause clicked")) {
        state.pausedByUser = true;
      }
      return;
    }
    if (state.status === "paused") {
      if (transitionTo("running", "resume clicked")) {
        state.pausedByUser = false;
      }
    }
  });

  stopButton.addEventListener("click", () => {
    void requestCancelRun(false);
  });

  document.addEventListener("visibilitychange", handleVisibilityChange);

  window.addEventListener("beforeunload", () => {
    cleanupRuntime(true);
  });
}

async function handleStartClick(): Promise<void> {
  if (state.status === "starting") {
    return;
  }

  if (!transitionTo("starting", "start clicked")) {
    return;
  }

  setInlineError(null);
  resetRunVisualState();
  setSummary(["Creating run..."]);

  const created = await requestCreateRun();
  if (!created) {
    return;
  }

  startPollingLoop();
}

async function bootstrap(): Promise<void> {
  syncUI();
  bindEvents();
  installResizeObserver();
  startRenderLoop();

  const config = await fetchConfig();
  applyConfig(config);
  transitionTo("idle", "config loaded");
}

void bootstrap().catch((error) => {
  const message = toDisplayError(error, "Unable to initialize app");
  renderBootstrapError(message);
});

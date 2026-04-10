/** Minimum playback multiplier shown in the speed slider UI. */
export const SPEED_MIN = 1;

/** Maximum playback multiplier shown in the speed slider UI. */
export const SPEED_MAX = 12;

/** Default playback multiplier used on bootstrap. */
export const SPEED_DEFAULT = 5;

/** Lower bound for selectable array sizes in the UI. */
export const UI_MIN_SIZE = 20;

/** Upper bound for selectable array sizes in the UI. */
export const UI_MAX_SIZE = 50;

/** Step increment for selectable array sizes (20, 30, 40, 50). */
export const UI_SIZE_STEP = 10;

/** Poll tick cadence (in milliseconds). */
export const POLL_INTERVAL_MS = 16;

/** Maximum number of steps requested per poll request. */
export const POLL_LIMIT = 120;

/** Maximum local queue length before polling throttles. */
export const MAX_QUEUE_BUFFER = 240;

/** Minimum poll limit when there is queue budget available. */
export const MIN_QUEUE_BUFFER = 32;

/** Number of retry attempts after the initial poll request attempt. */
export const POLL_RETRY_COUNT = 3;

/** Base exponential-backoff delay in milliseconds. */
export const POLL_RETRY_BASE_MS = 100;

/** Minimum delay between rendered steps to avoid browser lockups at max speed. */
export const MIN_RENDER_DELAY_MS = 8;

/** API base URL for production deployments; empty string uses same-origin/proxy. */
export const API_BASE = import.meta.env.VITE_API_BASE ?? "";

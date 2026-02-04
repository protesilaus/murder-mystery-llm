/**
 * Game state management
 * Contains all the shared state variables for the game UI
 */

export const state = {
  // Next actor information from preview
  nextActorInfo: null,

  // Last game snapshot received from server
  lastSnapshot: null,

  // Current list of events
  currentEvents: [],

  // Current event cursor position (for timeline navigation)
  eventCursor: null,

  // Murderer player ID
  currentMurdererId: null,

  // Detective player ID
  currentDetectiveId: null,

  // Map of player_id -> display_name
  displayNameMap: {},

  // Set of collapsed phase keys
  collapsedPhases: new Set(),
};

/**
 * Get the currently visible events (respecting cursor if set)
 */
export const visibleEvents = () => state.currentEvents;

/**
 * Get the current actor ID from the most recent event
 */
export const currentActorId = () => {
  const events = visibleEvents();
  for (let i = events.length - 1; i >= 0; i -= 1) {
    if (events[i].actor_id) return events[i].actor_id;
  }
  return null;
};

/**
 * Get display name for a player ID
 */
export const displayNameFor = (playerId) => {
  if (!playerId) return "unknown";
  return state.displayNameMap?.[playerId] || playerId;
};

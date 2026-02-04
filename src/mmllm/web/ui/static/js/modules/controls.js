/**
 * Game control functions
 * Functions for controlling game flow and state
 */

import { state, visibleEvents, currentActorId, displayNameFor } from './state.js';
import { formatEvent, findLastActionEvent } from './events.js';
import { renderTimeline, renderTimelineDetail } from './timeline.js';
import { renderPlayers } from './players.js';

/**
 * Update game stats (phase, alive count, event count)
 */
export const updateStats = (publicState, events, phaseIcon, phaseValue, aliveCount, aliveBadge, eventCount) => {
  if (publicState?.phase) {
    const phaseName = publicState.phase;
    const isNight = phaseName === "night";
    if (phaseIcon) phaseIcon.textContent = isNight ? "🌙" : "☀";
    if (phaseValue) phaseValue.textContent = String(publicState.round_num);
  }
  if (publicState?.players) {
    const alive = publicState.players.filter((p) => p.alive).length;
    const total = publicState.players.length;
    if (aliveCount) aliveCount.textContent = String(alive);
    if (aliveBadge) aliveBadge.textContent = `${alive}/${total}`;
  }
  if (eventCount && events) {
    eventCount.textContent = String(events.length);
  }
};

/**
 * Update current player and previous action display
 */
export const updateCurrentPlayerAndAction = (events, currentPlayer, previousAction) => {
  const actorId = currentActorId();
  if (currentPlayer) {
    currentPlayer.textContent = actorId ? displayNameFor(actorId) : "—";
  }
  if (previousAction) {
    const event = findLastActionEvent(events);
    if (event) {
      const formatted = formatEvent(event);
      previousAction.textContent = `${formatted.label}: ${formatted.detail}`;
    } else {
      previousAction.textContent = "No actions yet.";
    }
  }
};

/**
 * Render the public transcript
 */
export const renderTranscript = (events, transcript) => {
  if (!transcript) return;
  transcript.innerHTML = "";

  const publicMessages = (events || []).filter(
    (event) => event.event_type === "message_public"
  );
  if (publicMessages.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "Transcript will appear here.";
    transcript.appendChild(empty);
    return;
  }

  publicMessages.forEach((event) => {
    const item = document.createElement("div");
    item.className = "timeline-item";
    const title = document.createElement("strong");
    title.textContent = displayNameFor(event.actor_id || "unknown");
    const description = document.createElement("div");
    description.textContent = event.payload?.body || "";
    item.appendChild(title);
    item.appendChild(description);
    transcript.appendChild(item);
  });
  transcript.scrollTop = transcript.scrollHeight;
};

/**
 * Render a complete game snapshot
 */
export const renderGameSnapshot = (payload, elements, previewCallback) => {
  state.lastSnapshot = payload;
  state.currentEvents = payload?.events || [];
  state.currentMurdererId = payload?.murderer_id || null;
  state.currentDetectiveId = payload?.detective_id || null;
  state.displayNameMap = payload?.display_names || {};
  if (state.eventCursor !== null) {
    if (state.eventCursor >= state.currentEvents.length) {
      state.eventCursor = state.currentEvents.length - 1;
    }
  }
  const events = visibleEvents();
  renderTimeline(events, elements.timeline);
  renderTranscript(events, elements.transcript);
  updateStats(
    payload?.public_state,
    state.currentEvents,
    elements.phaseIcon,
    elements.phaseValue,
    elements.aliveCount,
    elements.aliveBadge,
    elements.eventCount
  );
  renderPlayers(
    payload?.public_state?.players || [],
    elements.playersList,
    elements.turnIndicator,
    elements.interjectTarget
  );
  updateCurrentPlayerAndAction(state.currentEvents, elements.currentPlayer, elements.previousAction);
  if (state.eventCursor !== null && state.currentEvents[state.eventCursor]) {
    renderTimelineDetail(state.currentEvents[state.eventCursor], elements.timelineDetail);
  } else {
    renderTimelineDetail(null, elements.timelineDetail);
  }
  // Preview next action after rendering
  if (previewCallback) previewCallback();
};

/**
 * Refresh game from server
 */
export const refreshGame = async (refreshButton, elements, previewCallback, showMarker = true) => {
  if (!refreshButton) return;
  try {
    const gameId = window.location.pathname.split("/").pop();
    const response = await fetch(`/games/${encodeURIComponent(gameId)}`);
    if (!response.ok) throw new Error("Failed to fetch game snapshot");
    const payload = await response.json();
    renderGameSnapshot(payload, elements, previewCallback);
    if (showMarker) {
      // pushTimelineEvent would need to be exposed or handled differently
    }
  } catch (error) {
    console.error("Failed to refresh snapshot:", error);
  }
};

/**
 * Run a single round action
 */
export const runRound = async (runRoundButton, elements, previewCallback) => {
  if (!runRoundButton) return;
  runRoundButton.disabled = true;
  runRoundButton.textContent = "▶️";
  try {
    const gameId = window.location.pathname.split("/").pop();
    const response = await fetch(`/games/${encodeURIComponent(gameId)}/action`, {
      method: "POST",
    });
    if (!response.ok) throw new Error("Failed to run action");
    const payload = await response.json();
    renderGameSnapshot(payload, elements, previewCallback);
  } catch (error) {
    console.error("Failed to run action:", error);
  } finally {
    runRoundButton.disabled = false;
    runRoundButton.textContent = "▶️";
  }
};

/**
 * Step through events
 */
export const stepEvent = (direction, elements, previewCallback) => {
  if (!state.currentEvents.length || !state.lastSnapshot) return;
  if (state.eventCursor === null) {
    state.eventCursor = direction > 0 ? -1 : state.currentEvents.length - 1;
  }
  state.eventCursor = Math.max(-1, Math.min(state.currentEvents.length - 1, state.eventCursor + direction));
  renderGameSnapshot(state.lastSnapshot || { events: state.currentEvents, public_state: null }, elements, previewCallback);
};

/**
 * Show all events (reset cursor)
 */
export const showAllEvents = (elements, previewCallback) => {
  if (!state.lastSnapshot) return;
  state.eventCursor = null;
  renderGameSnapshot(state.lastSnapshot, elements, previewCallback);
};

/**
 * Rewind game to specific event
 */
export const rewindToCursor = async (eventRewind, elements, previewCallback) => {
  if (!eventRewind || !state.lastSnapshot) return;
  const index = state.eventCursor === null ? state.currentEvents.length - 1 : state.eventCursor;
  if (index < -1) return;
  eventRewind.disabled = true;
  eventRewind.textContent = "Rewinding...";
  try {
    const gameId = window.location.pathname.split("/").pop();
    const response = await fetch(`/games/${encodeURIComponent(gameId)}/rewind`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event_index: index }),
    });
    if (!response.ok) throw new Error("Failed to rewind");
    const payload = await response.json();
    state.eventCursor = null;
    renderGameSnapshot(payload, elements, previewCallback);
  } catch (error) {
    console.error("Failed to rewind history:", error);
  } finally {
    eventRewind.disabled = false;
    eventRewind.textContent = "Rewind Here";
  }
};

/**
 * Send an interjection message
 */
export const sendInterject = async (interjectSend, interjectBody, interjectVisibility, interjectTarget, interjectSpeaker, interjectRecord, interjectResult, refreshGameCallback) => {
  if (!interjectSend) return;
  const body = interjectBody?.value?.trim() || "";
  if (!body) {
    if (interjectResult) interjectResult.textContent = "Message is required.";
    return;
  }
  const visibility = interjectVisibility?.value || "public";
  const toPlayer = interjectTarget?.value || "";
  const speaker = interjectSpeaker?.value?.trim() || "narrator";
  const recordHistory = interjectRecord?.checked ?? true;

  interjectSend.disabled = true;
  interjectSend.textContent = "Sending...";
  try {
    const gameId = window.location.pathname.split("/").pop();
    const response = await fetch(`/games/${encodeURIComponent(gameId)}/interject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        body,
        visibility,
        to_player_id: visibility === "private" ? toPlayer : null,
        speaker_id: speaker,
        record_history: recordHistory,
      }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      throw new Error(payload?.error || "Interject failed");
    }
    if (interjectResult) {
      interjectResult.textContent = payload.recorded
        ? "Interjection recorded."
        : "Interjection sent (not recorded).";
    }
    if (payload.recorded) {
      if (refreshGameCallback) await refreshGameCallback();
    }
  } catch (error) {
    if (interjectResult) interjectResult.textContent = "Interject failed.";
  } finally {
    interjectSend.disabled = false;
    interjectSend.textContent = "Interject";
  }
};

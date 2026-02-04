/**
 * Event formatting utilities
 * Functions for formatting game events for display
 */

import { displayNameFor } from './state.js';

/**
 * Format an event for display
 */
export const formatEvent = (event) => {
  const type = event.event_type || "event";
  const actor = event.actor_id ? `${displayNameFor(event.actor_id)}` : "";
  const payload = event.payload || {};

  switch (type) {
    case "game_created":
      return { label: "Game Created", detail: "A new game was initialized." };
    case "phase_started":
      return {
        label: "Phase Started",
        detail: `Phase ${payload.phase || event.phase}`,
      };
    case "message_public":
      return {
        label: "Public Message",
        detail: `${actor}: ${payload.body || ""}`,
      };
    case "message_private":
      return {
        label: "Private Message",
        detail: `${actor} → ${displayNameFor(payload.to || "")}: ${payload.body || ""}`,
      };
    case "vote_cast":
      return {
        label: "Vote Cast",
        detail: `${actor} voted ${displayNameFor(payload.target || "")}`,
      };
    case "vote_resolved":
      return {
        label: "Vote Resolved",
        detail: `Eliminated ${displayNameFor(payload.eliminated || "none")}`,
      };
    case "night_kill":
      return {
        label: "Night Kill",
        detail: `${actor} killed ${displayNameFor(payload.target || "")}`,
      };
    case "player_eliminated":
      return {
        label: "Player Eliminated",
        detail: `${displayNameFor(payload.player_id || "")} was eliminated`,
      };
    case "round_summary":
      if (payload.note && typeof payload.note === "string" && payload.note.startsWith("parse_failed:")) {
        return {
          label: "Parse Failed",
          detail: payload.note.replace("parse_failed:", "").trim() || "Parse failed.",
        };
      }
      return {
        label: "Round Summary",
        detail: payload.note || "Pass",
      };
    case "game_ended":
      return {
        label: "Game Ended",
        detail: `Winner: ${payload.winner || "unknown"}`,
      };
    default:
      return {
        label: type.replaceAll("_", " "),
        detail: actor ? `${actor} ${JSON.stringify(payload)}` : JSON.stringify(payload),
      };
  }
};

/**
 * Get symbol representation for event type
 */
export const eventSymbol = (event) => {
  switch (event.event_type) {
    case "game_created":
      return "★";
    case "phase_started":
      return "⏱";
    case "message_public":
      return "💬";
    case "message_private":
      return "🔒";
    case "vote_cast":
      return "🗳";
    case "vote_resolved":
      return "⚖";
    case "night_kill":
      return "🗡";
    case "player_eliminated":
      return "✖";
    case "round_summary":
      return "📝";
    case "game_ended":
      return "🏁";
    default:
      return "•";
  }
};

/**
 * Find the last actionable event from the event list
 */
export const findLastActionEvent = (events) => {
  if (!events || events.length === 0) return null;
  const actionable = new Set([
    "message_public",
    "message_private",
    "vote_cast",
    "vote_resolved",
    "night_kill",
    "player_eliminated",
    "round_summary",
  ]);
  for (let i = events.length - 1; i >= 0; i -= 1) {
    if (actionable.has(events[i].event_type)) return events[i];
  }
  return events[events.length - 1];
};

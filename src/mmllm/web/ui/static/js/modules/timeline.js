/**
 * Timeline rendering utilities
 * Functions for rendering and managing the event timeline
 */

import { state, visibleEvents } from './state.js';
import { formatEvent, eventSymbol } from './events.js';

/**
 * Group events by phase (round number + phase type)
 */
export const groupEventsByPhase = (events) => {
  const phases = [];
  let currentPhase = null;
  let currentPhaseEvents = [];

  events.forEach((event, index) => {
    const phaseKey = `${event.phase}_${event.round_num}`;
    if (currentPhase !== phaseKey) {
      if (currentPhaseEvents.length > 0) {
        phases.push({ phaseKey: currentPhase, events: currentPhaseEvents });
      }
      currentPhase = phaseKey;
      currentPhaseEvents = [];
    }
    currentPhaseEvents.push({ event, index });
  });

  if (currentPhaseEvents.length > 0) {
    phases.push({ phaseKey: currentPhase, events: currentPhaseEvents });
  }

  return phases;
};

/**
 * Group consecutive similar events (same type and symbol)
 */
export const groupConsecutiveSimilar = (eventItems) => {
  const grouped = [];
  let currentGroup = null;

  eventItems.forEach(item => {
    const symbol = eventSymbol(item.event);
    const type = item.event.event_type;

    if (currentGroup && currentGroup.symbol === symbol && currentGroup.type === type) {
      currentGroup.items.push(item);
    } else {
      if (currentGroup) {
        grouped.push(currentGroup);
      }
      currentGroup = {
        symbol,
        type,
        items: [item],
      };
    }
  });

  if (currentGroup) {
    grouped.push(currentGroup);
  }

  return grouped;
};

/**
 * Render the timeline with collapsible phases and grouped events
 */
export const renderTimeline = (events, timelineElement) => {
  if (!timelineElement) return;
  const wasAtEnd = timelineElement.scrollLeft >= timelineElement.scrollWidth - timelineElement.clientWidth - 50;

  timelineElement.innerHTML = "";
  if (!events || events.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No events yet. Start the engine to see activity.";
    timelineElement.appendChild(empty);
    return;
  }

  const phases = groupEventsByPhase(events);

  phases.forEach((phase, phaseIdx) => {
    const isCollapsed = state.collapsedPhases.has(phase.phaseKey);

    // Phase header
    const phaseHeader = document.createElement("button");
    phaseHeader.type = "button";
    phaseHeader.className = "timeline-phase-header";
    const firstEvent = phase.events[0].event;
    const phaseIcon = firstEvent.phase === "night" ? "🌙" : firstEvent.phase === "day" ? "☀" : "🗳";
    phaseHeader.innerHTML = `
      <span class="phase-toggle">${isCollapsed ? '▶' : '▼'}</span>
      <span>${phaseIcon} R${firstEvent.round_num}</span>
      <span class="phase-count">${phase.events.length}</span>
    `;
    phaseHeader.addEventListener("click", () => {
      if (state.collapsedPhases.has(phase.phaseKey)) {
        state.collapsedPhases.delete(phase.phaseKey);
      } else {
        state.collapsedPhases.add(phase.phaseKey);
      }
      renderTimeline(visibleEvents(), timelineElement);
    });
    timelineElement.appendChild(phaseHeader);

    // Phase events
    if (!isCollapsed) {
      const grouped = groupConsecutiveSimilar(phase.events);

      grouped.forEach(group => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "timeline-item symbol";

        // Check if any event in group is active
        const hasActive = group.items.some(({ index }) => state.eventCursor !== null && index === state.eventCursor);
        if (hasActive) {
          item.classList.add("active");
        }

        // Show symbol with count if multiple
        if (group.items.length > 1) {
          item.innerHTML = `
            ${group.symbol}
            <span class="timeline-badge">${group.items.length}</span>
          `;
        } else {
          item.textContent = group.symbol;
        }

        const firstItem = group.items[0];
        item.title = formatEvent(firstItem.event).label + (group.items.length > 1 ? ` (×${group.items.length})` : '');

        item.addEventListener("click", () => {
          // Show first event in group
          state.eventCursor = firstItem.index;
          renderTimelineDetail(firstItem.event, document.getElementById("timeline-detail"));
          renderTimeline(visibleEvents(), timelineElement);
        });

        timelineElement.appendChild(item);
      });
    }
  });

  // Auto-scroll to end if was at end or if first render
  if (wasAtEnd || timelineElement.scrollLeft === 0) {
    setTimeout(() => {
      timelineElement.scrollLeft = timelineElement.scrollWidth;
    }, 0);
  }
};

/**
 * Render detailed view of a selected event
 */
export const renderTimelineDetail = (event, detailElement) => {
  if (!detailElement) return;
  detailElement.innerHTML = "";
  if (!event) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "Select an event to see details.";
    detailElement.appendChild(empty);
    return;
  }
  const { label, detail } = formatEvent(event);
  const title = document.createElement("strong");
  title.textContent = label;
  const description = document.createElement("div");
  description.textContent = detail;
  detailElement.appendChild(title);
  detailElement.appendChild(description);
};

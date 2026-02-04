/**
 * AI-related features
 * Functions for AI chat, narrator generation, and action control
 */

import { state, displayNameFor } from './state.js';

/**
 * Preview the next action without executing it
 */
export const previewNextAction = async (nextActor, narratorSection, narratorText) => {
  if (!nextActor) return;
  try {
    const gameId = window.location.pathname.split("/").pop();
    const response = await fetch(`/games/${encodeURIComponent(gameId)}/preview-next`);
    if (!response.ok) throw new Error("Failed to preview next action");

    const result = await response.json();
    state.nextActorInfo = result.next_actor;

    const actorId = state.nextActorInfo.actor_id;
    const actorType = state.nextActorInfo.actor_type;

    if (actorType === "narrator") {
      nextActor.textContent = "Narrator";
      nextActor.style.color = "var(--accent-2)";
      if (narratorSection) {
        narratorSection.style.display = "flex";
        if (narratorText) narratorText.value = "";
      }
    } else {
      nextActor.textContent = displayNameFor(actorId);
      nextActor.style.color = "var(--ink)";
      if (narratorSection) narratorSection.style.display = "none";
    }
  } catch (error) {
    if (nextActor) nextActor.textContent = "—";
    console.error("Preview failed:", error);
  }
};

/**
 * Generate narrator text using AI
 */
export const generateNarratorText = async (generateNarrator, narratorText) => {
  if (!generateNarrator || !narratorText || !state.nextActorInfo) return;

  generateNarrator.disabled = true;
  generateNarrator.textContent = "...";

  try {
    const gameId = window.location.pathname.split("/").pop();
    const response = await fetch(`/games/${encodeURIComponent(gameId)}/generate-narrator-text`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: state.nextActorInfo.reason || "summary" }),
    });

    if (!response.ok) throw new Error("Failed to generate narrator text");

    const result = await response.json();
    narratorText.value = result.narrator_text || "";
  } catch (error) {
    alert(`Failed to generate narrator text: ${error.message}`);
  } finally {
    generateNarrator.disabled = false;
    generateNarrator.textContent = "Generate";
  }
};

/**
 * Fast forward to the next phase
 */
export const fastForwardToPhase = async (fastForward, renderGameSnapshot, previewCallback) => {
  if (!fastForward) return;

  const confirmed = confirm("Fast forward to next phase? This will run all actions until the phase changes.");
  if (!confirmed) return;

  fastForward.disabled = true;
  fastForward.textContent = "Running...";

  try {
    const gameId = window.location.pathname.split("/").pop();
    const startPhase = state.lastSnapshot?.public_state?.phase;

    let safety = 0;
    while (safety < 100) {
      const response = await fetch(`/games/${encodeURIComponent(gameId)}/action`, {
        method: "POST",
      });

      if (!response.ok) throw new Error("Failed to run action");

      const payload = await response.json();
      renderGameSnapshot(payload);

      const currentPhase = payload.public_state?.phase;
      if (currentPhase !== startPhase) {
        break;
      }

      safety++;
      await new Promise(resolve => setTimeout(resolve, 100));
    }

    if (previewCallback) await previewCallback();
  } catch (error) {
    alert(`Fast forward failed: ${error.message}`);
  } finally {
    fastForward.disabled = false;
    fastForward.textContent = "⏩ Phase";
  }
};

/**
 * Toggle AI chat history visibility
 */
export const toggleAIChatHistory = (aiChatMessages, toggleChatHistory) => {
  if (!aiChatMessages || !toggleChatHistory) return;
  const isVisible = aiChatMessages.style.display !== "none";
  aiChatMessages.style.display = isVisible ? "none" : "block";
  toggleChatHistory.textContent = isVisible ? "History" : "Hide";
};

/**
 * Send a message to the AI
 */
export const sendAIChat = async (aiChatInput, aiChatMessages, aiChatSend) => {
  if (!aiChatInput || !aiChatMessages || !aiChatSend) return;
  const message = aiChatInput.value.trim();
  if (!message) return;

  // Add user message to chat
  const userMsg = document.createElement("div");
  userMsg.className = "chat-message user";
  userMsg.textContent = `You: ${message}`;

  if (aiChatMessages.querySelector('.empty-state')) {
    aiChatMessages.innerHTML = '';
  }
  aiChatMessages.appendChild(userMsg);
  aiChatInput.value = "";
  aiChatMessages.scrollTop = aiChatMessages.scrollHeight;

  // Disable send button while waiting for response
  aiChatSend.disabled = true;
  aiChatSend.textContent = "...";

  try {
    const gameId = window.location.pathname.split("/").pop();
    const response = await fetch(`/games/${encodeURIComponent(gameId)}/ai-chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });

    if (!response.ok) {
      throw new Error("Failed to get AI response");
    }

    const result = await response.json();
    const aiMsg = document.createElement("div");
    aiMsg.className = "chat-message";
    aiMsg.textContent = `AI: ${result.response || "No response"}`;
    aiChatMessages.appendChild(aiMsg);
    aiChatMessages.scrollTop = aiChatMessages.scrollHeight;
  } catch (error) {
    const errorMsg = document.createElement("div");
    errorMsg.className = "chat-message";
    errorMsg.style.color = "var(--accent)";
    errorMsg.textContent = `Error: ${error.message}`;
    aiChatMessages.appendChild(errorMsg);
    aiChatMessages.scrollTop = aiChatMessages.scrollHeight;
  } finally {
    aiChatSend.disabled = false;
    aiChatSend.textContent = "Send";
  }
};

/**
 * Update visibility of action details field based on selected action type
 */
export const updateActionDetailsVisibility = (actionTypeSelect, actionDetailsField) => {
  if (!actionTypeSelect || !actionDetailsField) return;
  const selectedAction = actionTypeSelect.value;
  // Show details field for actions that need parameters
  const needsDetails = ["speak", "question", "poll", "vote"].includes(selectedAction);
  actionDetailsField.style.display = needsDetails ? "block" : "none";
};

/**
 * Force an AI action
 */
export const sendForceAction = async (forceAction, actionTypeSelect, actionDetails, actionDetailsField, refreshGameCallback) => {
  if (!forceAction || !actionTypeSelect) return;
  const actionType = actionTypeSelect.value;
  if (!actionType) {
    alert("Please select an action type");
    return;
  }

  forceAction.disabled = true;
  forceAction.textContent = "Forcing...";

  try {
    const gameId = window.location.pathname.split("/").pop();

    // If there's manual JSON input, use that
    if (actionDetails && actionDetails.value.trim()) {
      try {
        const details = JSON.parse(actionDetails.value.trim());
        const response = await fetch(`/games/${encodeURIComponent(gameId)}/force-action`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action_type: actionType, details }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData?.error || "Failed to force action");
        }

        if (refreshGameCallback) await refreshGameCallback(false);
        alert("Action forced successfully");
      } catch (error) {
        if (error instanceof SyntaxError) {
          alert("Invalid JSON in action details");
        } else {
          alert(`Failed to force action: ${error.message}`);
        }
        forceAction.disabled = false;
        forceAction.textContent = "Force Action";
        return;
      }
    } else {
      // Ask AI to generate the action JSON
      forceAction.textContent = "AI Generating...";
      const response = await fetch(`/games/${encodeURIComponent(gameId)}/ai-generate-action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action_type: actionType }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData?.error || "Failed to generate action");
      }

      const result = await response.json();

      // Show the generated action in the details field
      if (actionDetails && result.action_json) {
        actionDetails.value = JSON.stringify(result.action_json, null, 2);
        actionDetailsField.style.display = "block";
        alert(`AI generated action:\n${JSON.stringify(result.action_json, null, 2)}\n\nReview and click Force Action again to execute.`);
      } else {
        alert("Action generated and executed successfully");
        if (refreshGameCallback) await refreshGameCallback(false);
      }
    }
  } catch (error) {
    alert(`Failed to force action: ${error.message}`);
  } finally {
    forceAction.disabled = false;
    forceAction.textContent = "Force Action";
  }
};

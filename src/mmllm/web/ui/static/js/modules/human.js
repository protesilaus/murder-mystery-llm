/**
 * Human player action handling
 * Manages the UI for human-controlled players
 */

import { state, displayNameFor } from './state.js';

let currentActionType = null;

// Element references (cached on init)
let elements = null;

/**
 * Initialize human player module with DOM elements
 */
export function initHumanModule() {
  elements = {
    panel: document.getElementById("human-action-panel"),
    phase: document.getElementById("human-phase"),
    ap: document.getElementById("human-ap"),
    buttons: document.getElementById("human-action-buttons"),
    form: document.getElementById("human-action-form"),
    submitBtn: document.getElementById("human-action-submit"),
    cancelBtn: document.getElementById("human-action-cancel"),
    // Form sections
    formSpeak: document.getElementById("human-form-speak"),
    formQuestion: document.getElementById("human-form-question"),
    formVote: document.getElementById("human-form-vote"),
    formInvestigate: document.getElementById("human-form-investigate"),
    formKill: document.getElementById("human-form-kill"),
    formPass: document.getElementById("human-form-pass"),
    // Form inputs
    speakBody: document.getElementById("human-speak-body"),
    questionTarget: document.getElementById("human-question-target"),
    questionBody: document.getElementById("human-question-body"),
    voteTarget: document.getElementById("human-vote-target"),
    investigateTarget: document.getElementById("human-investigate-target"),
    killTarget: document.getElementById("human-kill-target"),
  };

  // Set up event listeners
  if (elements.cancelBtn) {
    elements.cancelBtn.addEventListener("click", hideActionForm);
  }
  if (elements.submitBtn) {
    elements.submitBtn.addEventListener("click", submitHumanAction);
  }

  // Action button listeners
  if (elements.buttons) {
    const actionBtns = elements.buttons.querySelectorAll("[data-action]");
    actionBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        const action = btn.dataset.action;
        showActionForm(action);
      });
    });
  }
}

/**
 * Update the human action panel based on game status
 */
export function updateHumanPanel(statusData, publicState) {
  if (!elements?.panel) return;

  const isHumanTurn = statusData.is_human_turn;
  elements.panel.style.display = isHumanTurn ? "block" : "none";

  if (!isHumanTurn) {
    hideActionForm();
    return;
  }

  // Update phase and AP display
  if (elements.phase) {
    elements.phase.textContent = statusData.phase || "—";
  }
  if (elements.ap) {
    elements.ap.textContent = statusData.human_ap ?? "—";
  }

  // Update allowed actions (enable/disable buttons)
  const allowedActions = statusData.allowed_actions || [];
  if (elements.buttons) {
    const actionBtns = elements.buttons.querySelectorAll("[data-action]");
    actionBtns.forEach((btn) => {
      const action = btn.dataset.action;
      const isAllowed = allowedActions.includes(action) ||
                        (action === "pass" && allowedActions.includes("pass_turn"));
      btn.disabled = !isAllowed;
      btn.classList.toggle("disabled", !isAllowed);
    });
  }

  // Populate target dropdowns with alive players (excluding self)
  if (publicState?.players) {
    const humanId = statusData.human_player_id;
    const aliveOthers = publicState.players
      .filter((p) => p.alive && p.player_id !== humanId)
      .map((p) => ({
        id: p.player_id,
        name: displayNameFor(p.player_id),
      }));

    populateTargetDropdown(elements.questionTarget, aliveOthers);
    populateTargetDropdown(elements.voteTarget, aliveOthers);
    populateTargetDropdown(elements.investigateTarget, aliveOthers);
    populateTargetDropdown(elements.killTarget, aliveOthers);
  }
}

/**
 * Populate a target dropdown with player options
 */
function populateTargetDropdown(select, players) {
  if (!select) return;
  select.innerHTML = "";
  players.forEach((p) => {
    const option = document.createElement("option");
    option.value = p.id;
    option.textContent = `${p.name} (${p.id})`;
    select.appendChild(option);
  });
}

/**
 * Show the action form for a specific action type
 */
function showActionForm(actionType) {
  currentActionType = actionType;

  // Hide all form sections
  const formSections = [
    elements.formSpeak,
    elements.formQuestion,
    elements.formVote,
    elements.formInvestigate,
    elements.formKill,
    elements.formPass,
  ];
  formSections.forEach((section) => {
    if (section) section.style.display = "none";
  });

  // Show the relevant form section
  const sectionMap = {
    speak: elements.formSpeak,
    question: elements.formQuestion,
    vote: elements.formVote,
    investigate: elements.formInvestigate,
    kill: elements.formKill,
    pass: elements.formPass,
  };

  const section = sectionMap[actionType];
  if (section) {
    section.style.display = "block";
  }

  // Show the form container
  if (elements.form) {
    elements.form.style.display = "block";
  }

  // Hide action buttons while form is shown
  if (elements.buttons) {
    elements.buttons.style.display = "none";
  }
}

/**
 * Hide the action form and show buttons again
 */
function hideActionForm() {
  currentActionType = null;

  if (elements.form) {
    elements.form.style.display = "none";
  }
  if (elements.buttons) {
    elements.buttons.style.display = "flex";
  }

  // Clear form inputs
  if (elements.speakBody) elements.speakBody.value = "";
  if (elements.questionBody) elements.questionBody.value = "";
}

/**
 * Submit the human action to the server
 */
async function submitHumanAction() {
  if (!currentActionType) {
    alert("Please select an action type");
    return;
  }

  const gameId = window.location.pathname.split("/").pop();
  const details = buildActionDetails();

  if (details === null) {
    return; // Validation failed
  }

  // The ActionType enum has pass_turn = "pass", so send "pass" not "pass_turn"
  const actionType = currentActionType;

  try {
    elements.submitBtn.disabled = true;
    elements.submitBtn.textContent = "Submitting...";

    const response = await fetch(`/games/${encodeURIComponent(gameId)}/human-action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action_type: actionType,
        details: details,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Failed to submit action");
    }

    // Success - hide form, UI will update via status polling
    hideActionForm();
    currentActionType = null;

    // Trigger a refresh to update the game state
    const refreshBtn = document.getElementById("refresh-game");
    if (refreshBtn) refreshBtn.click();

  } catch (error) {
    alert(`Action failed: ${error.message}`);
  } finally {
    elements.submitBtn.disabled = false;
    elements.submitBtn.textContent = "Submit Action";
  }
}

/**
 * Build action details from the current form
 */
function buildActionDetails() {
  switch (currentActionType) {
    case "speak": {
      const body = elements.speakBody?.value?.trim();
      if (!body) {
        alert("Please enter a message");
        return null;
      }
      return { body };
    }
    case "question": {
      const target = elements.questionTarget?.value;
      const body = elements.questionBody?.value?.trim();
      if (!target) {
        alert("Please select a target player");
        return null;
      }
      if (!body) {
        alert("Please enter your question");
        return null;
      }
      return { to_player_id: target, body };
    }
    case "vote": {
      const target = elements.voteTarget?.value;
      if (!target) {
        alert("Please select a player to vote for");
        return null;
      }
      return { target_player_id: target };
    }
    case "investigate": {
      const target = elements.investigateTarget?.value;
      if (!target) {
        alert("Please select a player to investigate");
        return null;
      }
      return { target_player_id: target };
    }
    case "kill": {
      const target = elements.killTarget?.value;
      if (!target) {
        alert("Please select a target");
        return null;
      }
      return { target_player_id: target };
    }
    case "pass":
      return {};
    default:
      return {};
  }
}

/**
 * Check if the human action panel is currently visible
 */
export function isHumanPanelVisible() {
  return elements?.panel?.style?.display !== "none";
}

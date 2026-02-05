/**
 * Player management utilities
 * Functions for rendering and managing player UI elements
 */

import { state, currentActorId, displayNameFor } from './state.js';

/**
 * Render the list of players
 */
export const renderPlayers = (players, playersList, turnIndicator, interjectTarget) => {
  if (!playersList) return;
  playersList.innerHTML = "";
  if (!players || players.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "Players will appear here.";
    playersList.appendChild(empty);
    return;
  }

  const actorId = currentActorId();
  if (turnIndicator) {
    turnIndicator.textContent = actorId
      ? `Turn: ${displayNameFor(actorId)} (${actorId})`
      : "Awaiting turn";
  }

  if (interjectTarget) {
    interjectTarget.innerHTML = "";
    players.forEach((player) => {
      const option = document.createElement("option");
      option.value = player.player_id;
      option.textContent = `${displayNameFor(player.player_id)} (${player.player_id})`;
      interjectTarget.appendChild(option);
    });
  }

  // Sort players: alive first, then eliminated
  const sortedPlayers = [...players].sort((a, b) => {
    if (a.alive === b.alive) return 0;
    return a.alive ? -1 : 1;
  });

  sortedPlayers.forEach((player) => {
    const card = document.createElement("div");
    card.className = "player-card";
    if (actorId && actorId === player.player_id) {
      card.classList.add("active");
    }
    // Add eliminated class for styling
    if (!player.alive) {
      card.classList.add("eliminated");
    }

    const left = document.createElement("div");
    left.className = "player-left";

    const icon = document.createElement("div");
    icon.className = "player-icon";
    if (!player.alive) {
      icon.textContent = "💀";
    } else if (state.currentMurdererId && player.player_id === state.currentMurdererId) {
      icon.textContent = "🗡";
    } else if (state.currentDetectiveId && player.player_id === state.currentDetectiveId) {
      icon.textContent = "🕵️";
    } else {
      icon.textContent = "❤";
    }

    const info = document.createElement("div");
    info.style.display = "flex";
    info.style.alignItems = "center";
    info.style.gap = "0.5rem";
    info.style.flex = "1";

    const nameSection = document.createElement("div");
    nameSection.style.flex = "1";
    const name = document.createElement("strong");
    name.textContent = `${displayNameFor(player.player_id)} (${player.player_id})`;
    nameSection.appendChild(name);

    const apDisplay = document.createElement("div");
    apDisplay.className = "player-ap";
    apDisplay.title = "Click to edit AP";
    apDisplay.textContent = `${player.social_ap || 0}/${player.social_ap_max || 3}`;
    apDisplay.style.cursor = "pointer";
    apDisplay.style.fontSize = "0.85em";
    apDisplay.style.color = "#999";
    apDisplay.style.fontFamily = "'Space Grotesk', 'Trebuchet MS', sans-serif";
    apDisplay.addEventListener("click", () => editPlayerAP(player.player_id, player.social_ap || 0));

    info.appendChild(nameSection);
    info.appendChild(apDisplay);

    left.appendChild(icon);
    left.appendChild(info);

    const actions = document.createElement("div");
    actions.style.display = "flex";
    actions.style.gap = "0.5rem";

    const detailsBtn = document.createElement("button");
    detailsBtn.className = "btn ghost";
    detailsBtn.textContent = "🔍";
    detailsBtn.title = "View Details";
    detailsBtn.addEventListener("click", () => openPlayerModal(player));

    const whisper = document.createElement("button");
    whisper.className = "btn ghost";
    whisper.textContent = "💬";
    whisper.title = "Whisper";
    whisper.addEventListener("click", () => {
      const interjectVisibility = document.getElementById("interject-visibility");
      if (!interjectVisibility || !interjectTarget) return;
      interjectVisibility.value = "private";
      interjectTarget.value = player.player_id;
      const toggleInterjectTarget = () => {
        const interjectTargetField = document.getElementById("interject-target-field");
        if (!interjectVisibility || !interjectTargetField) return;
        const isPrivate = interjectVisibility.value === "private";
        interjectTargetField.style.display = isPrivate ? "block" : "none";
      };
      toggleInterjectTarget();
    });

    actions.appendChild(detailsBtn);
    actions.appendChild(whisper);

    card.appendChild(left);
    card.appendChild(actions);
    playersList.appendChild(card);
  });
};

/**
 * Edit player AP (action points)
 */
export const editPlayerAP = async (playerId, currentAP) => {
  const newAP = window.prompt(`Edit AP for ${playerId}:`, String(currentAP));
  if (newAP === null) return;
  const apValue = Number.parseInt(newAP, 10);
  if (Number.isNaN(apValue) || apValue < 0 || apValue > 20) {
    alert("AP must be between 0 and 20");
    return;
  }
  try {
    const gameId = window.location.pathname.split("/").pop();
    const response = await fetch(`/games/${encodeURIComponent(gameId)}/players/${encodeURIComponent(playerId)}/ap`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ap: apValue }),
    });
    if (!response.ok) throw new Error("Failed to update AP");
    const payload = await response.json();
    if (!payload.ok) throw new Error(payload.error || "Update failed");
    // Trigger refresh from parent
    return true;
  } catch (error) {
    alert("Failed to update AP: " + error.message);
    return false;
  }
};

/**
 * Open player details modal
 */
export const openPlayerModal = (player) => {
  const playerModal = document.getElementById("player-modal");
  const modalPlayerName = document.getElementById("modal-player-name");
  const modalPlayerId = document.getElementById("modal-player-id");
  const modalPlayerStatus = document.getElementById("modal-player-status");
  const modalPlayerRole = document.getElementById("modal-player-role");
  const modalPlayerAp = document.getElementById("modal-player-ap");
  const modalPlayerKnowledge = document.getElementById("modal-player-knowledge");
  const modalChatMessages = document.getElementById("modal-chat-messages");

  if (!playerModal) return;
  if (modalPlayerName) modalPlayerName.textContent = displayNameFor(player.player_id);
  if (modalPlayerId) modalPlayerId.textContent = player.player_id;
  if (modalPlayerStatus) {
    modalPlayerStatus.textContent = player.alive ? "Alive" : "Eliminated";
  }
  if (modalPlayerRole) {
    let role = "Villager";
    if (state.currentMurdererId && player.player_id === state.currentMurdererId) {
      role = "Murderer 🗡";
    } else if (state.currentDetectiveId && player.player_id === state.currentDetectiveId) {
      role = "Detective 🕵️";
    }
    modalPlayerRole.textContent = role;
  }
  if (modalPlayerAp) {
    modalPlayerAp.textContent = `${player.social_ap || 0} / ${player.social_ap_max || 3}`;
  }
  if (modalPlayerKnowledge) {
    // Fetch knowledge context from backend
    const gameId = window.location.pathname.split("/").pop();
    modalPlayerKnowledge.innerHTML = `<p>Loading knowledge context...</p>`;
    fetch(`/games/${encodeURIComponent(gameId)}/players/${player.player_id}/knowledge`)
      .then(res => res.json())
      .then(data => {
        const suspicionEntries = Object.entries(data.beliefs.suspicion || {});
        const suspicionHtml = suspicionEntries.length > 0
          ? suspicionEntries
              .map(([pid, score]) => `<li>${displayNameFor(pid)}: ${(score * 100).toFixed(0)}%</li>`)
              .join('')
          : '<li>No suspicions recorded</li>';

        const topSuspectsHtml = data.beliefs.top_suspects && data.beliefs.top_suspects.length > 0
          ? data.beliefs.top_suspects.map(displayNameFor).join(', ')
          : 'None';

        const trustedHtml = data.beliefs.trusted && data.beliefs.trusted.length > 0
          ? data.beliefs.trusted.map(displayNameFor).join(', ')
          : 'None';

        modalPlayerKnowledge.innerHTML = `
          <h4>Suspicions:</h4>
          <ul>${suspicionHtml}</ul>
          <h4>Top Suspects:</h4>
          <p>${topSuspectsHtml}</p>
          <h4>Trusted Players:</h4>
          <p>${trustedHtml}</p>
          <h4>Next Plan:</h4>
          <p>${data.plan_next || 'No plan set'}</p>
        `;
      })
      .catch(err => {
        console.error('Failed to load knowledge context:', err);
        modalPlayerKnowledge.innerHTML = '<p class="error">Failed to load knowledge context</p>';
      });
  }
  if (modalChatMessages) {
    modalChatMessages.innerHTML = "";
  }
  playerModal.classList.add("active");
  playerModal.dataset.currentPlayerId = player.player_id;
};

/**
 * Close player details modal
 */
export const closePlayerModal = () => {
  const playerModal = document.getElementById("player-modal");
  if (!playerModal) return;
  playerModal.classList.remove("active");
  delete playerModal.dataset.currentPlayerId;
};

/**
 * Send a chat message to the agent
 */
export const sendModalChat = async () => {
  const modalChatInput = document.getElementById("modal-chat-input");
  const modalChatMessages = document.getElementById("modal-chat-messages");
  const playerModal = document.getElementById("player-modal");

  if (!modalChatInput || !modalChatMessages || !playerModal) return;
  const message = modalChatInput.value.trim();
  if (!message) return;
  const playerId = playerModal.dataset.currentPlayerId;
  if (!playerId) return;

  // Add user message to chat
  const userMsg = document.createElement("div");
  userMsg.className = "chat-message user";
  userMsg.textContent = message;
  modalChatMessages.appendChild(userMsg);
  modalChatInput.value = "";
  modalChatMessages.scrollTop = modalChatMessages.scrollHeight;

  // Send to backend and get response
  const gameId = window.location.pathname.split("/").pop();

  // Show loading indicator
  const loadingMsg = document.createElement("div");
  loadingMsg.className = "chat-message loading";
  loadingMsg.innerHTML = `<strong>${displayNameFor(playerId)}:</strong><br><em>Thinking...</em>`;
  modalChatMessages.appendChild(loadingMsg);
  modalChatMessages.scrollTop = modalChatMessages.scrollHeight;

  try {
    const response = await fetch(`/games/${encodeURIComponent(gameId)}/players/${playerId}/chat`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: message})
    });

    // Remove loading message
    modalChatMessages.removeChild(loadingMsg);

    if (!response.ok) {
      throw new Error(`HTTP error ${response.status}`);
    }

    const data = await response.json();

    if (data.ok && data.response) {
      const agentMsg = document.createElement("div");
      agentMsg.className = "chat-message";
      agentMsg.innerHTML = `<strong>${displayNameFor(playerId)}:</strong><br>${data.response}`;
      modalChatMessages.appendChild(agentMsg);
    } else {
      throw new Error('Invalid response format');
    }
  } catch (err) {
    console.error('Chat error:', err);
    // Remove loading message if still present
    if (loadingMsg.parentNode) {
      modalChatMessages.removeChild(loadingMsg);
    }
    const errorMsg = document.createElement("div");
    errorMsg.className = "chat-message error";
    errorMsg.textContent = `Error: ${err.message || 'Failed to send message'}`;
    modalChatMessages.appendChild(errorMsg);
  }

  modalChatMessages.scrollTop = modalChatMessages.scrollHeight;
};

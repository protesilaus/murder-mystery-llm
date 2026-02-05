/**
 * Game status monitoring and display
 */

let statusPollInterval = null;

export function startStatusPolling(gameId, statusUpdateCallback, voteUpdateCallback) {
  stopStatusPolling();

  const pollStatus = async () => {
    try {
      const response = await fetch(`/games/${encodeURIComponent(gameId)}/status`);
      if (!response.ok) return;

      const payload = await response.json();
      if (payload.ok && payload.status) {
        statusUpdateCallback(payload.status);
      }
      // Handle vote data if present
      if (payload.ok && voteUpdateCallback) {
        updateVoteDisplay(payload.phase, payload.votes);
      }
    } catch (error) {
      console.error("Status polling error:", error);
    }
  };

  statusPollInterval = setInterval(pollStatus, 500); // Poll every 500ms
  pollStatus(); // Immediate poll
}

export function stopStatusPolling() {
  if (statusPollInterval) {
    clearInterval(statusPollInterval);
    statusPollInterval = null;
  }
}

export function updateStatusDisplay(status) {
  const statusIcon = document.getElementById("status-icon");
  const statusText = document.getElementById("status-text");
  const statusDetails = document.getElementById("status-details");
  const viewPromptLink = document.getElementById("view-prompt-link");
  const statusMessage = document.getElementById("status-message");

  if (!statusText) return;

  const statusConfig = {
    idle: { icon: "⏸️", text: "Ready", showPrompt: false, className: "" },
    querying_llm: {
      icon: "💭",
      text: status.action_description || "Querying LLM",
      showPrompt: true,
      className: "querying"
    },
    waiting_response: {
      icon: "⏳",
      text: status.action_description || "Waiting for response",
      showPrompt: true,
      className: "waiting"
    },
    applying_action: {
      icon: "⚙️",
      text: status.action_description || "Applying action",
      showPrompt: false,
      className: "applying"
    },
    phase_transition: {
      icon: "🔄",
      text: "Phase transition",
      showPrompt: false,
      className: ""
    },
  };

  const config = statusConfig[status.status] || statusConfig.idle;

  if (statusIcon) statusIcon.textContent = config.icon;
  statusText.textContent = config.text;

  if (statusMessage) {
    statusMessage.className = `status-message ${config.className}`;
  }

  if (config.showPrompt && status.request_id) {
    if (statusDetails) statusDetails.style.display = "block";
    if (viewPromptLink) {
      viewPromptLink.onclick = (e) => {
        e.preventDefault();
        showPromptModal(status.request_id);
      };
    }
  } else {
    if (statusDetails) statusDetails.style.display = "none";
  }
}

async function showPromptModal(requestId) {
  const gameId = window.location.pathname.split("/").pop();

  try {
    const response = await fetch(`/games/${encodeURIComponent(gameId)}/prompts/${requestId}`);
    if (!response.ok) {
      alert("Failed to load prompt");
      return;
    }

    const payload = await response.json();
    if (!payload.ok) {
      alert("Prompt not found");
      return;
    }

    displayPromptInModal(payload.prompt);
  } catch (error) {
    console.error("Failed to fetch prompt:", error);
    alert("Error loading prompt");
  }
}

function displayPromptInModal(promptData) {
  const messagesHtml = promptData.messages.map(msg => `
    <div class="prompt-message">
      <strong>${msg.role}:</strong>
      <pre>${msg.content}</pre>
    </div>
  `).join("");

  const modalContent = `
    <div class="prompt-modal-overlay" id="prompt-modal">
      <div class="modal-content large">
        <div class="modal-header">
          <h2>LLM Query Details</h2>
          <button class="modal-close" onclick="closePromptModal()">&times;</button>
        </div>
        <div class="modal-body">
          <div class="prompt-metadata">
            <p><strong>Player:</strong> ${promptData.player_id}</p>
            <p><strong>Phase:</strong> ${promptData.phase}</p>
            <p><strong>Round:</strong> ${promptData.round_num}</p>
            <p><strong>Timestamp:</strong> ${new Date(promptData.timestamp).toLocaleString()}</p>
          </div>
          <div class="prompt-messages">
            ${messagesHtml}
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn ghost" onclick="closePromptModal()">Close</button>
        </div>
      </div>
    </div>
  `;

  const existing = document.getElementById("prompt-modal");
  if (existing) existing.remove();

  document.body.insertAdjacentHTML("beforeend", modalContent);
}

window.closePromptModal = function() {
  const modal = document.getElementById("prompt-modal");
  if (modal) modal.remove();
};

/**
 * Update the real-time vote display
 */
export function updateVoteDisplay(phase, voteData) {
  const voteSection = document.getElementById("vote-display-section");
  const voteProgress = document.getElementById("vote-progress");
  const voteTally = document.getElementById("vote-tally");
  const voteDetails = document.getElementById("vote-details");

  if (!voteSection) return;

  // Only show during vote phase
  if (phase !== "vote" || !voteData) {
    voteSection.style.display = "none";
    return;
  }

  voteSection.style.display = "block";

  // Update progress (votes cast / total voters)
  if (voteProgress) {
    voteProgress.textContent = `${voteData.votes_cast}/${voteData.total_voters}`;
  }

  // Build tally display
  if (voteTally) {
    const tallyEntries = Object.entries(voteData.vote_tally || {});

    // Find max votes for highlighting leader
    const maxVotes = tallyEntries.length > 0
      ? Math.max(...tallyEntries.map(([_, count]) => count))
      : 0;

    // Sort by vote count descending
    tallyEntries.sort((a, b) => b[1] - a[1]);

    const tallyHtml = tallyEntries.map(([target, count]) => {
      const isLeading = count === maxVotes && count > 0;
      return `
        <div class="vote-tally-item ${isLeading ? 'leading' : ''}">
          <span class="target">${target}</span>
          <span class="count">${count}</span>
        </div>
      `;
    }).join("");

    voteTally.innerHTML = tallyHtml || '<span class="no-votes">No votes yet</span>';
  }

  // Build vote details (who voted for whom)
  if (voteDetails) {
    const currentVotes = voteData.current_votes || {};
    const voteArrows = Object.entries(currentVotes).map(([voter, target]) => `
      <span class="vote-arrow">
        <span class="voter">${voter}</span>
        <span class="arrow">→</span>
        <span class="target">${target}</span>
      </span>
    `).join("");

    voteDetails.innerHTML = voteArrows || '<span class="no-votes">Waiting for votes...</span>';
  }
}

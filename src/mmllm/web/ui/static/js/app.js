/**
 * Main application entry point
 * Coordinates UI elements and event handlers
 */

import { closePlayerModal, sendModalChat } from './modules/players.js';
import {
  previewNextAction,
  generateNarratorText,
  fastForwardToPhase,
  toggleAIChatHistory,
  sendAIChat,
  updateActionDetailsVisibility,
  sendForceAction,
} from './modules/ai.js';
import {
  renderGameSnapshot,
  refreshGame,
  runRound,
  stepEvent,
  showAllEvents,
  rewindToCursor,
  sendInterject,
} from './modules/controls.js';
import { startStatusPolling, stopStatusPolling, updateStatusDisplay, updateVoteDisplay } from './modules/status.js';

(() => {
  // Element references
  const statusPill = document.getElementById("status-pill");
  const statusLine = document.getElementById("status-line");
  const lastUpdated = document.getElementById("last-updated");
  const gameList = document.getElementById("games-list");
  const activeCount = document.getElementById("active-count");
  const createButton = document.getElementById("create-game");
  const agentTypeSelect = document.getElementById("agent-type");
  const refreshButton = document.getElementById("refresh-game");
  const runRoundButton = document.getElementById("run-round");
  const timeline = document.getElementById("timeline");
  const eventCount = document.getElementById("event-count");
  const phaseValue = document.getElementById("phase");
  const phaseIcon = document.getElementById("phase-icon");
  const aliveCount = document.getElementById("alive-count");
  const transcript = document.getElementById("transcript");
  const playersList = document.getElementById("players-list");
  const turnIndicator = document.getElementById("turn-indicator");
  const eventPrev = document.getElementById("event-prev");
  const eventNext = document.getElementById("event-next");
  const eventShowAll = document.getElementById("event-show-all");
  const eventRewind = document.getElementById("event-rewind");
  const timelineDetail = document.getElementById("timeline-detail");
  const currentPlayer = document.getElementById("current-player");
  const previousAction = document.getElementById("previous-action");
  const playerModal = document.getElementById("player-modal");
  const modalClose = document.getElementById("modal-close");
  const modalCloseBtn = document.getElementById("modal-close-btn");
  const modalChatInput = document.getElementById("modal-chat-input");
  const modalChatSend = document.getElementById("modal-chat-send");
  const interjectVisibility = document.getElementById("interject-visibility");
  const interjectTargetField = document.getElementById("interject-target-field");
  const interjectTarget = document.getElementById("interject-target");
  const interjectSpeaker = document.getElementById("interject-speaker");
  const interjectBody = document.getElementById("interject-body");
  const interjectRecord = document.getElementById("interject-record");
  const interjectSend = document.getElementById("interject-send");
  const interjectResult = document.getElementById("interject-result");
  const ollamaTestButton = document.getElementById("ollama-test");
  const ollamaBaseUrl = document.getElementById("ollama-base-url");
  const ollamaModel = document.getElementById("ollama-model");
  const ollamaPrompt = document.getElementById("ollama-prompt");
  const ollamaResponse = document.getElementById("ollama-response");
  const partyList = document.getElementById("party-list");
  const partySave = document.getElementById("party-save");
  const partyGenerate = document.getElementById("party-generate");
  const aliveBadge = document.getElementById("alive-badge");
  const toggleChatHistory = document.getElementById("toggle-chat-history");
  const aiChatMessages = document.getElementById("ai-chat-messages");
  const aiChatInput = document.getElementById("ai-chat-input");
  const aiChatSend = document.getElementById("ai-chat-send");
  const actionTypeSelect = document.getElementById("action-type-select");
  const actionDetailsField = document.getElementById("action-details-field");
  const actionDetails = document.getElementById("action-details");
  const forceAction = document.getElementById("force-action");
  const nextActor = document.getElementById("next-actor");
  const narratorSection = document.getElementById("narrator-section");
  const narratorText = document.getElementById("narrator-text");
  const generateNarrator = document.getElementById("generate-narrator");
  const fastForward = document.getElementById("fast-forward");

  // Create elements object for passing to functions
  const elements = {
    timeline,
    timelineDetail,
    transcript,
    playersList,
    turnIndicator,
    interjectTarget,
    phaseIcon,
    phaseValue,
    aliveCount,
    aliveBadge,
    eventCount,
    currentPlayer,
    previousAction,
  };

  // Utility functions
  const formatTime = () =>
    new Date().toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });

  const setStatus = (ok, message) => {
    if (statusPill) {
      statusPill.textContent = ok ? "Online" : "Offline";
      statusPill.classList.toggle("online", ok);
      statusPill.classList.toggle("error", !ok);
    }
    if (statusLine && message) {
      statusLine.textContent = message;
    }
  };

  const touchUpdated = () => {
    if (lastUpdated) {
      lastUpdated.textContent = `Last update: ${formatTime()}`;
    }
  };

  const renderGames = (games) => {
    if (!gameList) return;
    gameList.innerHTML = "";
    if (!games || games.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "No games yet. Start one to see it here.";
      gameList.appendChild(empty);
      if (activeCount) activeCount.textContent = "0";
      return;
    }

    games.forEach((gameId) => {
      const card = document.createElement("div");
      card.className = "session-card";

      const left = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = gameId;
      const meta = document.createElement("div");
      meta.className = "session-meta";
      meta.textContent = "Ready for live updates";
      left.appendChild(title);
      left.appendChild(meta);

      const link = document.createElement("a");
      link.className = "btn ghost";
      link.href = `/game/${encodeURIComponent(gameId)}`;
      link.textContent = "Open";

      card.appendChild(left);
      card.appendChild(link);
      gameList.appendChild(card);
    });

    if (activeCount) activeCount.textContent = String(games.length);
  };

  const renderParty = (players) => {
    if (!partyList) return;
    partyList.innerHTML = "";
    if (!players || players.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "No party members yet.";
      partyList.appendChild(empty);
      return;
    }

    players.forEach((player) => {
      const row = document.createElement("div");
      row.className = "party-row";
      row.dataset.playerId = player.player_id;

      const idCol = document.createElement("div");
      const idLabel = document.createElement("div");
      idLabel.className = "field-label";
      idLabel.textContent = "Player";
      const idValue = document.createElement("strong");
      idValue.textContent = player.player_id;
      idCol.appendChild(idLabel);
      idCol.appendChild(idValue);

      const nameCol = document.createElement("label");
      nameCol.className = "field";
      const nameLabel = document.createElement("span");
      nameLabel.className = "field-label";
      nameLabel.textContent = "Display name";
      const nameInput = document.createElement("input");
      nameInput.className = "input";
      nameInput.value = player.display_name || "";
      nameInput.dataset.field = "display_name";
      nameCol.appendChild(nameLabel);
      nameCol.appendChild(nameInput);

      const characterCol = document.createElement("label");
      characterCol.className = "field";
      const characterLabel = document.createElement("span");
      characterLabel.className = "field-label";
      characterLabel.textContent = "Character name";
      const characterInput = document.createElement("input");
      characterInput.className = "input";
      characterInput.value = player.character_name || "";
      characterInput.dataset.field = "character_name";
      characterCol.appendChild(characterLabel);
      characterCol.appendChild(characterInput);

      const scoreCol = document.createElement("label");
      scoreCol.className = "field";
      const scoreLabel = document.createElement("span");
      scoreLabel.className = "field-label";
      scoreLabel.textContent = "Score";
      const scoreInput = document.createElement("input");
      scoreInput.className = "input";
      scoreInput.type = "number";
      scoreInput.step = "1";
      scoreInput.value = String(player.score ?? 0);
      scoreInput.dataset.field = "score";
      scoreCol.appendChild(scoreLabel);
      scoreCol.appendChild(scoreInput);

      row.appendChild(idCol);
      row.appendChild(nameCol);
      row.appendChild(characterCol);
      row.appendChild(scoreCol);
      partyList.appendChild(row);
    });
  };

  const collectParty = () => {
    if (!partyList) return [];
    const rows = Array.from(partyList.querySelectorAll(".party-row"));
    return rows.map((row) => {
      const playerId = row.dataset.playerId || "";
      const inputs = row.querySelectorAll("input");
      const data = { player_id: playerId, display_name: "", character_name: "", score: 0 };
      inputs.forEach((input) => {
        const field = input.dataset.field;
        if (field === "display_name") data.display_name = input.value.trim();
        if (field === "character_name") data.character_name = input.value.trim();
        if (field === "score") data.score = Number.parseFloat(input.value || "0");
      });
      return data;
    });
  };

  const loadParty = async () => {
    if (!partyList) return;
    try {
      const response = await fetch("/party");
      if (!response.ok) throw new Error("Failed to fetch party");
      const payload = await response.json();
      renderParty(payload.players || []);
    } catch (error) {
      renderParty([]);
    }
  };

  const saveParty = async () => {
    if (!partySave) return;
    partySave.disabled = true;
    partySave.textContent = "Saving...";
    try {
      const players = collectParty();
      const response = await fetch("/party", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ players }),
      });
      if (!response.ok) throw new Error("Failed to save party");
      const payload = await response.json();
      renderParty(payload.players || []);
    } catch (error) {
      // ignore
    } finally {
      partySave.disabled = false;
      partySave.textContent = "Save Party";
    }
  };

  const generatePartyNames = async () => {
    if (!partyGenerate) return;
    partyGenerate.disabled = true;
    partyGenerate.textContent = "Generating...";
    try {
      const baseUrl = ollamaBaseUrl?.value?.trim() || "http://127.0.0.1:11434";
      const model = ollamaModel?.value?.trim() || "llama3.1:8b";
      const response = await fetch("/party/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ base_url: baseUrl, model }),
      });
      if (!response.ok) throw new Error("Failed to generate names");
      const payload = await response.json();
      renderParty(payload.players || []);
    } catch (error) {
      // ignore
    } finally {
      partyGenerate.disabled = false;
      partyGenerate.textContent = "Generate Names";
    }
  };

  const fetchGames = async () => {
    if (!gameList) return;
    try {
      const response = await fetch("/games");
      if (!response.ok) throw new Error("Failed to fetch games");
      const payload = await response.json();
      renderGames(payload.games || []);
      touchUpdated();
      setStatus(true, "Server reachable. Games list refreshed.");
    } catch (error) {
      setStatus(false, "Unable to reach the server.");
    }
  };

  const createGame = async () => {
    if (!createButton) return;
    createButton.disabled = true;
    createButton.textContent = "Starting...";
    console.info("[createGame] POST /games");
    try {
      const response = await fetch("/games", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          agent_type: agentTypeSelect?.value || "ollama",
        }),
      });
      const contentType = response.headers.get("content-type") || "";
      const rawBody = contentType.includes("application/json")
        ? await response.json()
        : await response.text();
      console.info("[createGame] status", response.status, "body", rawBody);
      if (!response.ok) {
        throw new Error(
          `Failed to create game (status ${response.status})`
        );
      }
      const payload = rawBody;
      if (payload.game_id) {
        await fetchGames();
      }
    } catch (error) {
      console.error("[createGame] error", error);
      setStatus(false, "Failed to start a new game.");
    } finally {
      createButton.disabled = false;
      createButton.textContent = "Start New Game";
    }
  };

  const toggleInterjectTarget = () => {
    if (!interjectVisibility || !interjectTargetField) return;
    const isPrivate = interjectVisibility.value === "private";
    interjectTargetField.style.display = isPrivate ? "block" : "none";
  };

  const testOllama = async () => {
    if (!ollamaTestButton) return;
    const baseUrl = ollamaBaseUrl?.value?.trim() || "http://127.0.0.1:11434";
    const model = ollamaModel?.value?.trim() || "llama3.1:8b";
    const prompt = ollamaPrompt?.value?.trim() || "Say hello in one sentence.";

    ollamaTestButton.disabled = true;
    ollamaTestButton.textContent = "Testing...";
    if (ollamaResponse) ollamaResponse.textContent = "Contacting Ollama...";
    console.info("[ollamaTest]", { baseUrl, model, prompt });

    try {
      const response = await fetch("/agents/ollama/test", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ base_url: baseUrl, model, prompt }),
      });
      const payload = await response.json();
      console.info("[ollamaTest] status", response.status, payload);

      if (!response.ok || !payload.ok) {
        const message = payload?.error || `HTTP ${response.status}`;
        if (ollamaResponse) ollamaResponse.textContent = `Error: ${message}`;
        setStatus(false, "Ollama test failed.");
        return;
      }

      if (ollamaResponse) ollamaResponse.textContent = payload.response || "(empty response)";
      setStatus(true, "Ollama responded successfully.");
      touchUpdated();
    } catch (error) {
      console.error("[ollamaTest] error", error);
      if (ollamaResponse) ollamaResponse.textContent = "Error: request failed.";
      setStatus(false, "Ollama test failed.");
    } finally {
      ollamaTestButton.disabled = false;
      ollamaTestButton.textContent = "Test Ollama";
    }
  };

  const checkHealth = async () => {
    try {
      const response = await fetch("/health");
      if (!response.ok) throw new Error("Health check failed");
      setStatus(true, "Server reachable.");
    } catch (error) {
      setStatus(false, "Server not responding.");
    }
  };

  // Wrapper functions to pass proper arguments
  const doPreviewNextAction = () => previewNextAction(nextActor, narratorSection, narratorText);
  const doGenerateNarratorText = () => generateNarratorText(generateNarrator, narratorText);
  const doFastForwardToPhase = () => fastForwardToPhase(fastForward, (p) => renderGameSnapshot(p, elements, doPreviewNextAction), doPreviewNextAction);
  const doToggleAIChatHistory = () => toggleAIChatHistory(aiChatMessages, toggleChatHistory);
  const doSendAIChat = () => sendAIChat(aiChatInput, aiChatMessages, aiChatSend);
  const doUpdateActionDetailsVisibility = () => updateActionDetailsVisibility(actionTypeSelect, actionDetailsField);
  const doSendForceAction = () => sendForceAction(forceAction, actionTypeSelect, actionDetails, actionDetailsField, doRefreshGame);
  const doRefreshGame = (showMarker = true) => refreshGame(refreshButton, elements, doPreviewNextAction, showMarker);
  const doRunRound = () => runRound(runRoundButton, elements, doPreviewNextAction);
  const doStepEvent = (direction) => stepEvent(direction, elements, doPreviewNextAction);
  const doShowAllEvents = () => showAllEvents(elements, doPreviewNextAction);
  const doRewindToCursor = () => rewindToCursor(eventRewind, elements, doPreviewNextAction);
  const doSendInterject = () => sendInterject(interjectSend, interjectBody, interjectVisibility, interjectTarget, interjectSpeaker, interjectRecord, interjectResult, doRefreshGame);

  // Event listeners
  if (createButton) {
    createButton.addEventListener("click", createGame);
  }

  if (refreshButton) {
    refreshButton.addEventListener("click", doRefreshGame);
  }

  if (runRoundButton) {
    runRoundButton.addEventListener("click", doRunRound);
  }

  if (eventPrev) eventPrev.addEventListener("click", () => doStepEvent(-1));
  if (eventNext) eventNext.addEventListener("click", () => doStepEvent(1));
  if (eventShowAll) eventShowAll.addEventListener("click", doShowAllEvents);
  if (eventRewind) eventRewind.addEventListener("click", doRewindToCursor);

  if (interjectVisibility) {
    interjectVisibility.addEventListener("change", toggleInterjectTarget);
    toggleInterjectTarget();
  }
  if (interjectSend) interjectSend.addEventListener("click", doSendInterject);

  if (ollamaTestButton) {
    ollamaTestButton.addEventListener("click", testOllama);
  }

  if (partySave) {
    partySave.addEventListener("click", saveParty);
  }
  if (partyGenerate) {
    partyGenerate.addEventListener("click", generatePartyNames);
  }

  if (toggleChatHistory) {
    toggleChatHistory.addEventListener("click", doToggleAIChatHistory);
  }

  if (aiChatSend) {
    aiChatSend.addEventListener("click", doSendAIChat);
  }

  if (aiChatInput) {
    aiChatInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") doSendAIChat();
    });
  }

  if (actionTypeSelect) {
    actionTypeSelect.addEventListener("change", doUpdateActionDetailsVisibility);
  }

  if (forceAction) {
    forceAction.addEventListener("click", doSendForceAction);
  }

  if (generateNarrator) {
    generateNarrator.addEventListener("click", doGenerateNarratorText);
  }

  if (fastForward) {
    fastForward.addEventListener("click", doFastForwardToPhase);
  }

  // Modal event listeners
  if (modalClose) modalClose.addEventListener("click", closePlayerModal);
  if (modalCloseBtn) modalCloseBtn.addEventListener("click", closePlayerModal);
  if (modalChatSend) modalChatSend.addEventListener("click", sendModalChat);
  if (modalChatInput) {
    modalChatInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") sendModalChat();
    });
  }
  if (playerModal) {
    playerModal.addEventListener("click", (e) => {
      if (e.target === playerModal) closePlayerModal();
    });
  }

  // Initial load
  if (refreshButton && window.location.pathname.startsWith("/game/")) {
    doRefreshGame(false);

    // Start status polling for game page (with vote display enabled)
    const gameId = window.location.pathname.split("/").pop();
    startStatusPolling(gameId, updateStatusDisplay, true);
  }

  if (partyList) {
    loadParty();
  }

  checkHealth();
  fetchGames();

  // Cleanup on page unload
  window.addEventListener("beforeunload", () => {
    stopStatusPolling();
  });
})();

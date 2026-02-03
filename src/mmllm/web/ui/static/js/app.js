(() => {
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
  const phaseMeta = document.getElementById("phase-meta");
  const aliveCount = document.getElementById("alive-count");
  const transcript = document.getElementById("transcript");
  const playersList = document.getElementById("players-list");
  const turnIndicator = document.getElementById("turn-indicator");
  const eventPrev = document.getElementById("event-prev");
  const eventNext = document.getElementById("event-next");
  const eventShowAll = document.getElementById("event-show-all");
  const eventRewind = document.getElementById("event-rewind");
  const timelineDetail = document.getElementById("timeline-detail");
  const lastActionBody = document.getElementById("last-action-body");
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

  const pushTimelineEvent = (label, detail) => {
    if (!timeline) return;
    const item = document.createElement("div");
    item.className = "timeline-item";

    const title = document.createElement("strong");
    title.textContent = label;
    const description = document.createElement("div");
    description.textContent = detail;

    item.appendChild(title);
    item.appendChild(description);
    timeline.prepend(item);
    if (eventCount) {
      const current = Number.parseInt(eventCount.textContent || "0", 10);
      eventCount.textContent = String(current + 1);
    }
  };

  let lastSnapshot = null;
  let currentEvents = [];
  let eventCursor = null;
  let currentMurdererId = null;
  let currentDetectiveId = null;
  let displayNameMap = {};

  const visibleEvents = () => currentEvents;

  const currentActorId = () => {
    const events = visibleEvents();
    for (let i = events.length - 1; i >= 0; i -= 1) {
      if (events[i].actor_id) return events[i].actor_id;
    }
    return null;
  };

  const displayNameFor = (playerId) => {
    if (!playerId) return "unknown";
    return displayNameMap?.[playerId] || playerId;
  };

  const formatEvent = (event) => {
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

  const eventSymbol = (event) => {
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

  const renderTimelineDetail = (event) => {
    if (!timelineDetail) return;
    timelineDetail.innerHTML = "";
    if (!event) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "Select an event to see details.";
      timelineDetail.appendChild(empty);
      return;
    }
    const { label, detail } = formatEvent(event);
    const title = document.createElement("strong");
    title.textContent = label;
    const description = document.createElement("div");
    description.textContent = detail;
    timelineDetail.appendChild(title);
    timelineDetail.appendChild(description);
  };

  const findLastActionEvent = (events) => {
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

  const renderLastAction = (events) => {
    if (!lastActionBody) return;
    const event = findLastActionEvent(events);
    if (!event) {
      lastActionBody.textContent = "No actions yet.";
      return;
    }
    const formatted = formatEvent(event);
    lastActionBody.textContent = `${formatted.label}: ${formatted.detail}`;
  };

  const renderTimeline = (events) => {
    if (!timeline) return;
    timeline.innerHTML = "";
    if (!events || events.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "No events yet. Start the engine to see activity.";
      timeline.appendChild(empty);
      return;
    }

    events.forEach((event, index) => {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "timeline-item symbol";
      if (eventCursor !== null && index === eventCursor) {
        item.classList.add("active");
      }
      item.textContent = eventSymbol(event);
      item.title = formatEvent(event).label;
      item.addEventListener("click", () => {
        eventCursor = index;
        renderTimelineDetail(event);
        renderTimeline(visibleEvents());
      });
      timeline.appendChild(item);
    });
  };

  const renderTranscript = (events) => {
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

  const renderPlayers = (players) => {
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

    players.forEach((player) => {
      const card = document.createElement("div");
      card.className = "player-card";
      if (actorId && actorId === player.player_id) {
        card.classList.add("active");
      }

      const left = document.createElement("div");
      left.className = "player-left";

      const icon = document.createElement("div");
      icon.className = "player-icon";
      if (!player.alive) {
        icon.textContent = "💀";
      } else if (currentMurdererId && player.player_id === currentMurdererId) {
        icon.textContent = "🗡";
      } else if (currentDetectiveId && player.player_id === currentDetectiveId) {
        icon.textContent = "🕵️";
      } else {
        icon.textContent = "❤";
      }

      const info = document.createElement("div");
      const name = document.createElement("strong");
      name.textContent = displayNameFor(player.player_id);
      const meta = document.createElement("div");
      meta.className = "player-meta";
      meta.textContent = player.alive
        ? `${player.player_id} · Alive`
        : `${player.player_id} · Eliminated`;
      if (!player.alive) {
        meta.classList.add("player-status", "dead");
      }
      info.appendChild(name);
      info.appendChild(meta);

      left.appendChild(icon);
      left.appendChild(info);

      const whisper = document.createElement("button");
      whisper.className = "btn ghost";
      whisper.textContent = "Whisper";
      whisper.addEventListener("click", () => {
        if (!interjectVisibility || !interjectTarget) return;
        interjectVisibility.value = "private";
        interjectTarget.value = player.player_id;
        toggleInterjectTarget();
      });

      card.appendChild(left);
      card.appendChild(whisper);
      playersList.appendChild(card);
    });
  };

  const updateStats = (publicState, events) => {
    if (publicState?.phase) {
      const phaseName = publicState.phase;
      const isNight = phaseName === "night";
      if (phaseIcon) phaseIcon.textContent = isNight ? "🌙" : "☀";
      if (phaseValue) phaseValue.textContent = String(publicState.round_num);
    }
    if (aliveCount && publicState?.players) {
      const alive = publicState.players.filter((p) => p.alive).length;
      aliveCount.textContent = String(alive);
    }
    if (eventCount && events) {
      eventCount.textContent = String(events.length);
    }
  };

  const renderGameSnapshot = (payload) => {
    lastSnapshot = payload;
    currentEvents = payload?.events || [];
    currentMurdererId = payload?.murderer_id || null;
    currentDetectiveId = payload?.detective_id || null;
    displayNameMap = payload?.display_names || {};
    if (eventCursor !== null) {
      if (eventCursor >= currentEvents.length) {
        eventCursor = currentEvents.length - 1;
      }
    }
    const events = visibleEvents();
    renderTimeline(events);
    renderTranscript(events);
    updateStats(payload?.public_state, currentEvents);
    renderPlayers(payload?.public_state?.players || []);
    renderLastAction(currentEvents);
    if (eventCursor !== null && currentEvents[eventCursor]) {
      renderTimelineDetail(currentEvents[eventCursor]);
    } else {
      renderTimelineDetail(null);
    }
  };

  const toggleInterjectTarget = () => {
    if (!interjectVisibility || !interjectTargetField) return;
    const isPrivate = interjectVisibility.value === "private";
    interjectTargetField.style.display = isPrivate ? "block" : "none";
  };

  const refreshGame = async (showMarker = true) => {
    if (!refreshButton) return;
    try {
      const gameId = window.location.pathname.split("/").pop();
      const response = await fetch(`/games/${encodeURIComponent(gameId)}`);
      if (!response.ok) throw new Error("Failed to fetch game snapshot");
      const payload = await response.json();
      renderGameSnapshot(payload);
      if (showMarker) {
        pushTimelineEvent("Snapshot", `Manual refresh at ${formatTime()}.`);
      }
      touchUpdated();
    } catch (error) {
      setStatus(false, "Failed to refresh snapshot.");
    }
  };

  const runRound = async () => {
    if (!runRoundButton) return;
    runRoundButton.disabled = true;
    runRoundButton.textContent = "Running...";
    try {
      const gameId = window.location.pathname.split("/").pop();
      const response = await fetch(`/games/${encodeURIComponent(gameId)}/action`, {
        method: "POST",
      });
      if (!response.ok) throw new Error("Failed to run action");
      const payload = await response.json();
      renderGameSnapshot(payload);
      pushTimelineEvent(
        "Action Step",
        `Round ${payload.round_num} · Phase ${payload.phase}`
      );
    } catch (error) {
      setStatus(false, "Failed to run action.");
    } finally {
      runRoundButton.disabled = false;
      runRoundButton.textContent = "Run Action";
    }
  };

  const stepEvent = (direction) => {
    if (!currentEvents.length || !lastSnapshot) return;
    if (eventCursor === null) {
      eventCursor = direction > 0 ? -1 : currentEvents.length - 1;
    }
    eventCursor = Math.max(-1, Math.min(currentEvents.length - 1, eventCursor + direction));
    renderGameSnapshot(lastSnapshot || { events: currentEvents, public_state: null });
  };

  const showAllEvents = () => {
    if (!lastSnapshot) return;
    eventCursor = null;
    renderGameSnapshot(lastSnapshot);
  };

  const rewindToCursor = async () => {
    if (!eventRewind || !lastSnapshot) return;
    const index = eventCursor === null ? currentEvents.length - 1 : eventCursor;
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
      eventCursor = null;
      renderGameSnapshot(payload);
      setStatus(true, "Rewound game history.");
    } catch (error) {
      setStatus(false, "Failed to rewind history.");
    } finally {
      eventRewind.disabled = false;
      eventRewind.textContent = "Rewind Here";
    }
  };

  const sendInterject = async () => {
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
        await refreshGame();
      } else if (payload.event) {
        const event = payload.event;
        pushTimelineEvent("Interject", event.payload?.body || "");
        if (event.event_type === "message_public" && transcript) {
          const item = document.createElement("div");
          item.className = "timeline-item";
          const title = document.createElement("strong");
          title.textContent = event.actor_id || "narrator";
          const description = document.createElement("div");
          description.textContent = event.payload?.body || "";
          item.appendChild(title);
          item.appendChild(description);
          transcript.prepend(item);
          transcript.scrollTop = transcript.scrollHeight;
        }
      }
    } catch (error) {
      if (interjectResult) interjectResult.textContent = "Interject failed.";
    } finally {
      interjectSend.disabled = false;
      interjectSend.textContent = "Interject";
    }
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

  if (createButton) {
    createButton.addEventListener("click", createGame);
  }

  if (refreshButton) {
    refreshButton.addEventListener("click", refreshGame);
  }

  if (runRoundButton) {
    runRoundButton.addEventListener("click", runRound);
  }

  if (eventPrev) eventPrev.addEventListener("click", () => stepEvent(-1));
  if (eventNext) eventNext.addEventListener("click", () => stepEvent(1));
  if (eventShowAll) eventShowAll.addEventListener("click", showAllEvents);
  if (eventRewind) eventRewind.addEventListener("click", rewindToCursor);

  if (interjectVisibility) {
    interjectVisibility.addEventListener("change", toggleInterjectTarget);
    toggleInterjectTarget();
  }
  if (interjectSend) interjectSend.addEventListener("click", sendInterject);

  if (ollamaTestButton) {
    ollamaTestButton.addEventListener("click", testOllama);
  }

  if (partySave) {
    partySave.addEventListener("click", saveParty);
  }
  if (partyGenerate) {
    partyGenerate.addEventListener("click", generatePartyNames);
  }

  if (refreshButton && window.location.pathname.startsWith("/game/")) {
    refreshGame(false);
  }

  if (partyList) {
    loadParty();
  }

  checkHealth();
  fetchGames();
})();




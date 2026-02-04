(() => {
  const baseUrl = document.getElementById("test-base-url");
  const model = document.getElementById("test-model");
  const roleSelect = document.getElementById("test-role");
  const systemPrompt = document.getElementById("test-system");
  const userPrompt = document.getElementById("test-user");
  const sendButton = document.getElementById("test-send");
  const responseBox = document.getElementById("test-response");
  const markdownBox = document.getElementById("test-markdown");
  const rawBox = document.getElementById("test-raw");
  const validationStatus = document.getElementById("validation-status");
  const validationBody = document.getElementById("validation-body");
  const varFields = {
    request_id: document.getElementById("var-request_id"),
    game_id: document.getElementById("var-game_id"),
    player_id: document.getElementById("var-player_id"),
    round_num: document.getElementById("var-round_num"),
    phase: document.getElementById("var-phase"),
    role: document.getElementById("var-role"),
    ap_available: document.getElementById("var-ap_available"),
    allowed_actions: document.getElementById("var-allowed_actions"),
    action_request: document.getElementById("var-action_request"),
    observation: document.getElementById("var-observation"),
    constraints: document.getElementById("var-constraints"),
  };

  const escapeHtml = (text) =>
    text
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");

  const renderMarkdown = (text) => {
    if (!text) return "<p>(empty response)</p>";
    let html = escapeHtml(text);

    html = html.replace(/```([\w-]+)?\n([\s\S]*?)```/g, (_, lang, code) => {
      const label = lang ? `<div class="code-lang">${escapeHtml(lang)}</div>` : "";
      return `<pre><code>${escapeHtml(code)}</code></pre>${label}`;
    });

    html = html
      .replace(/^###\s+(.*)$/gm, "<h3>$1</h3>")
      .replace(/^##\s+(.*)$/gm, "<h2>$1</h2>")
      .replace(/^#\s+(.*)$/gm, "<h1>$1</h1>");

    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/`([^`]+?)`/g, "<code>$1</code>");
    html = html.replace(/(^|\n)-\s+(.*?)(?=\n|$)/g, "$1<li>$2</li>");
    html = html.replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>");
    html = html.replace(/\n\n+/g, "</p><p>");
    html = `<p>${html}</p>`;

    return html;
  };

  const setResponse = (content, raw) => {
    if (responseBox) responseBox.innerHTML = renderMarkdown(content || "");
    if (markdownBox) markdownBox.textContent = content || "(empty response)";
    if (rawBox) rawBox.textContent = raw ? JSON.stringify(raw, null, 2) : "";
    setValidation(content || "");
  };

  const setValidationStatus = (label, state) => {
    if (!validationStatus) return;
    validationStatus.textContent = label;
    validationStatus.className = `status-pill ${state || ""}`.trim();
  };

  const extractJsonText = (text) => {
    if (!text) return null;
    const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
    if (fenced && fenced[1]) return fenced[1].trim();
    const trimmed = text.trim();
    if (trimmed.startsWith("{") && trimmed.endsWith("}")) return trimmed;
    const first = trimmed.indexOf("{");
    const last = trimmed.lastIndexOf("}");
    if (first !== -1 && last !== -1 && last > first) {
      return trimmed.slice(first, last + 1);
    }
    return null;
  };

  const validateActionResponse = (value) => {
    const issues = [];
    const warnings = [];
    const values = [];

    const requireString = (key, obj, label = key) => {
      if (!obj || !(key in obj)) {
        issues.push(`Missing ${label}.`);
        return;
      }
      if (typeof obj[key] !== "string" || !obj[key].trim()) {
        issues.push(`${label} must be a non-empty string.`);
      }
    };

    const requireNumber = (key, obj, label = key) => {
      if (!obj || !(key in obj)) {
        issues.push(`Missing ${label}.`);
        return;
      }
      if (typeof obj[key] !== "number" || Number.isNaN(obj[key])) {
        issues.push(`${label} must be a number.`);
      }
    };

    requireString("request_id", value);
    requireString("game_id", value);
    requireString("player_id", value);
    requireNumber("round_num", value);
    requireString("phase", value);

    if (!value || typeof value.action !== "object" || value.action === null) {
      issues.push("Missing action object.");
    } else {
      const action = value.action;
      if (!("type" in action)) {
        issues.push("Missing action.type.");
      } else if (typeof action.type !== "string") {
        issues.push("action.type must be a string.");
      }

      const actionType = action?.type;
      const allowed = ["speak", "question", "poll", "investigate", "whisper_send", "whisper_reply", "vote", "kill", "pass"];
      if (actionType && !allowed.includes(actionType)) {
        issues.push(`action.type must be one of ${allowed.join(", ")}.`);
      }

      if (actionType === "speak" && typeof action.body !== "string") {
        issues.push("action.body is required for speak.");
      }
      if (actionType === "question" && typeof action.to_player_id !== "string") {
        issues.push("action.to_player_id is required for question.");
      }
      if (actionType === "question" && typeof action.body !== "string") {
        issues.push("action.body is required for question.");
      }
      if (actionType === "poll" && typeof action.body !== "string") {
        issues.push("action.body is required for poll.");
      }
      if (actionType === "investigate" && typeof action.target_player_id !== "string") {
        issues.push("action.target_player_id is required for investigate.");
      }
      if (actionType === "whisper_send" && typeof action.to_player_id !== "string") {
        issues.push("action.to_player_id is required for whisper_send.");
      }
      if (actionType === "whisper_send" && typeof action.body !== "string") {
        issues.push("action.body is required for whisper_send.");
      }
      if (actionType === "whisper_reply" && typeof action.to_player_id !== "string") {
        issues.push("action.to_player_id is required for whisper_reply.");
      }
      if (actionType === "whisper_reply" && typeof action.body !== "string") {
        issues.push("action.body is required for whisper_reply.");
      }
      if (actionType === "vote" && typeof action.target_player_id !== "string") {
        issues.push("action.target_player_id is required for vote.");
      }
      if (actionType === "kill" && typeof action.target_player_id !== "string") {
        issues.push("action.target_player_id is required for kill.");
      }
    }

    if (value && typeof value === "object") {
      const allowedTop = new Set(["request_id", "game_id", "player_id", "round_num", "phase", "action", "suspicion_scores"]);
      Object.keys(value).forEach((key) => {
        if (!allowedTop.has(key)) warnings.push(`Unexpected top-level key: ${key}.`);
      });
    }

    if (value?.request_id) values.push({ label: "request_id", value: value.request_id });
    if (value?.game_id) values.push({ label: "game_id", value: value.game_id });
    if (value?.player_id) values.push({ label: "player_id", value: value.player_id });
    if (typeof value?.round_num === "number") values.push({ label: "round_num", value: String(value.round_num) });
    if (value?.phase) values.push({ label: "phase", value: value.phase });
    if (value?.action?.type) values.push({ label: "type", value: value.action.type });
    if (value?.action?.target_player_id) values.push({ label: "target_player_id", value: value.action.target_player_id });
    if (value?.action?.to_player_id) values.push({ label: "to_player_id", value: value.action.to_player_id });

    return { issues, warnings, values };
  };

  const setValidation = (content) => {
    if (!validationBody) return;
    if (!content) {
      setValidationStatus("Waiting", "");
      validationBody.textContent = "Send a prompt to validate the response.";
      return;
    }

    const jsonText = extractJsonText(content);
    if (!jsonText) {
      setValidationStatus("No JSON", "error");
      validationBody.textContent = "No JSON object found in the response content.";
      return;
    }

    let parsed;
    try {
      parsed = JSON.parse(jsonText);
    } catch (error) {
      setValidationStatus("Invalid", "error");
      validationBody.textContent = `JSON parse error: ${String(error)}`;
      return;
    }

    const { issues, warnings, values } = validateActionResponse(parsed);
    const hasIssues = issues.length > 0;
    const hasWarnings = warnings.length > 0;

    if (hasIssues) {
      setValidationStatus("Invalid", "error");
    } else if (hasWarnings) {
      setValidationStatus("Warnings", "warn");
    } else {
      setValidationStatus("Valid", "ok");
    }

    const parts = [];
    if (values.length) {
      parts.push("<div class=\"validation-item\"><strong>Extracted values</strong></div>");
      parts.push(
        `<ul class="validation-list">${values
          .map(
            (item) =>
              `<li><code>${escapeHtml(item.label)}</code>: ${escapeHtml(item.value)}</li>`,
          )
          .join("")}</ul>`,
      );
    }
    if (issues.length) {
      parts.push("<div class=\"validation-item\"><strong>Problems</strong></div>");
      parts.push(
        `<ul class="validation-list">${issues
          .map((item) => `<li>${escapeHtml(item)}</li>`)
          .join("")}</ul>`,
      );
    }
    if (!issues.length && hasWarnings) {
      parts.push("<div class=\"validation-item\"><strong>Warnings</strong></div>");
      parts.push(
        `<ul class="validation-list">${warnings
          .map((item) => `<li>${escapeHtml(item)}</li>`)
          .join("")}</ul>`,
      );
    }

    validationBody.innerHTML = parts.join("") || "No validation details available.";
  };

  const collectVariables = () => {
    const values = {};
    for (const [key, field] of Object.entries(varFields)) {
      if (field && typeof field.value === "string") {
        values[key] = field.value;
      }
    }
    return values;
  };

  const renderWithVariables = (text, variables) => {
    let rendered = text || "";
    for (const [key, value] of Object.entries(variables)) {
      rendered = rendered.replaceAll(`{${key}}`, value);
    }
    return rendered;
  };

  let cachedPrompts = { system_town: "", system_murderer: "", system_detective: "", user: "" };

  const loadPrompts = async () => {
    try {
      const response = await fetch("/agents/prompts");
      if (!response.ok) return;
      const data = await response.json();
      cachedPrompts = {
        system_town: data.system_town || data.system || "",
        system_murderer: data.system_murderer || data.system || "",
        system_detective: data.system_detective || data.system || "",
        user: data.user || "",
      };
      const role = roleSelect?.value || "town";
      if (systemPrompt) {
        if (role === "murderer") {
          systemPrompt.value = cachedPrompts.system_murderer;
        } else if (role === "detective") {
          systemPrompt.value = cachedPrompts.system_detective;
        } else {
          systemPrompt.value = cachedPrompts.system_town;
        }
      }
      if (userPrompt && !userPrompt.value) {
        userPrompt.value = cachedPrompts.user;
      }
    } catch (error) {
      // ignore
    }
  };

  const onRoleChange = async () => {
    if (!systemPrompt) return;
    if (!cachedPrompts.system_town && !cachedPrompts.system_murderer) {
      await loadPrompts();
    }
    const role = roleSelect?.value || "town";
    if (role === "murderer") {
      systemPrompt.value = cachedPrompts.system_murderer;
    } else if (role === "detective") {
      systemPrompt.value = cachedPrompts.system_detective;
    } else {
      systemPrompt.value = cachedPrompts.system_town;
    }
  };

  const sendPrompt = async () => {
    if (!sendButton) return;
    sendButton.disabled = true;
    sendButton.textContent = "Sending...";
    setResponse("Contacting Ollama...", null);

    try {
      const variables = collectVariables();
      const payload = {
        base_url: baseUrl?.value?.trim() || "http://127.0.0.1:11434",
        model: model?.value?.trim() || "llama3.1:8b",
        system_prompt: renderWithVariables(systemPrompt?.value || "", variables),
        user_prompt: renderWithVariables(userPrompt?.value || "", variables),
      };

      const response = await fetch("/agents/ollama/raw", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      if (!response.ok || !data.ok) {
        setResponse(`Error: ${data?.error || response.status}`, data);
        return;
      }

      setResponse(data.response, data.raw);
    } catch (error) {
      setResponse("Error: request failed.", { error: String(error) });
    } finally {
      sendButton.disabled = false;
      sendButton.textContent = "Send Prompt";
    }
  };

  if (sendButton) {
    sendButton.addEventListener("click", sendPrompt);
  }

  if (roleSelect) {
    roleSelect.addEventListener("change", onRoleChange);
  }

  loadPrompts();
})();

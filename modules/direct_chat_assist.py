"""Small browser-only helpers for the ASIN Resolver Direct Chat Assist UI."""

from __future__ import annotations

import base64
import re
from urllib.parse import urlsplit


_DOM_ID_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_-]*\Z")


def encode_prompt_base64(prompt: str) -> str:
    """Encode the prompt without changing its Unicode or whitespace."""
    return base64.b64encode(prompt.encode("utf-8")).decode("ascii")


def decode_prompt_base64(encoded_prompt: str) -> str:
    """Decode an encoded prompt for tests and local validation."""
    return base64.b64decode(encoded_prompt.encode("ascii"), validate=True).decode("utf-8")


def is_valid_chatgpt_project_url(url: str) -> bool:
    """Accept only a normal HTTPS URL for the ChatGPT project host."""
    if not isinstance(url, str) or not url or any(character.isspace() for character in url):
        return False

    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return False

    return (
        parsed.scheme.lower() == "https"
        and hostname == "chatgpt.com"
        and parsed.username is None
        and parsed.password is None
        and port in (None, 443)
    )


def build_copy_button_html(prompt: str, dom_id: str) -> str:
    """Build a static Clipboard API control without embedding prompt text directly."""
    if not _DOM_ID_PATTERN.fullmatch(dom_id):
        raise ValueError("dom_id must contain only letters, numbers, underscores, or hyphens")

    encoded_prompt = encode_prompt_base64(prompt)
    button_id = f"{dom_id}-button"
    status_id = f"{dom_id}-status"

    return f"""
<div id="{dom_id}">
  <button type="button" id="{button_id}">プロンプトをコピー</button>
  <span id="{status_id}" role="status" aria-live="polite"></span>
</div>
<script>
(() => {{
  const button = document.getElementById("{button_id}");
  const status = document.getElementById("{status_id}");
  const encodedPrompt = "{encoded_prompt}";
  const failureMessage = "コピーできませんでした。下のプロンプト欄から手動でコピーしてください。";

  const showFailure = () => {{
    status.textContent = failureMessage;
  }};

  button.addEventListener("click", () => {{
    if (!navigator.clipboard || typeof navigator.clipboard.writeText !== "function") {{
      showFailure();
      return;
    }}

    try {{
      const bytes = Uint8Array.from(atob(encodedPrompt), (character) => character.charCodeAt(0));
      const promptText = new TextDecoder("utf-8").decode(bytes);
      navigator.clipboard.writeText(promptText).then(
        () => {{
          status.textContent = "コピーしました。";
        }},
        showFailure,
      );
    }} catch (_error) {{
      showFailure();
    }}
  }});
}})();
</script>
""".strip()

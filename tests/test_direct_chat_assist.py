import pytest

import modules.config as config
from modules.direct_chat_assist import (
    build_copy_button_html,
    decode_prompt_base64,
    encode_prompt_base64,
    is_valid_chatgpt_project_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://chatgpt.com/project/example",
        "https://example.com/chatgpt.com/project/example",
        "https://chatgpt.com.example/project/example",
        "https://user@chatgpt.com/project/example",
        "javascript:alert(1)",
        "data:text/plain,test",
        "file:///C:/project",
        "https://chatgpt.com/project path",
        "https://[invalid",
    ],
)
def test_is_valid_chatgpt_project_url_rejects_invalid_urls(url):
    assert not is_valid_chatgpt_project_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://chatgpt.com/",
        "https://chatgpt.com/g/g-example/project?new_chat=true",
        "https://chatgpt.com:443/project/example#details",
    ],
)
def test_is_valid_chatgpt_project_url_accepts_chatgpt_https_urls(url):
    assert is_valid_chatgpt_project_url(url)


def test_load_settings_allows_an_unset_project_url(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ENV_PATH", tmp_path / ".env")
    monkeypatch.delenv("AMAZON_SEARCH_PROJECT_URL", raising=False)

    settings = config.load_settings()

    assert settings.amazon_search_project_url == ""


def test_load_settings_reads_the_optional_project_url(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ENV_PATH", tmp_path / ".env")
    project_url = "https://chatgpt.com/g/g-example/project"
    monkeypatch.setenv("AMAZON_SEARCH_PROJECT_URL", project_url)

    settings = config.load_settings()

    assert settings.amazon_search_project_url == project_url


def test_prompt_base64_round_trip_preserves_unicode_whitespace():
    prompt = "R0001\tモンチッチ Key Chain\nR0002\tRefill 200ml\n"

    encoded_prompt = encode_prompt_base64(prompt)

    assert decode_prompt_base64(encoded_prompt) == prompt


def test_copy_button_html_uses_base64_and_clipboard_api_without_plaintext_prompt():
    prompt = "R0001\tモンチッチ Key Chain\n"

    html = build_copy_button_html(prompt, "initial-copy")

    assert prompt not in html
    assert encode_prompt_base64(prompt) in html
    assert "navigator.clipboard.writeText" in html
    assert 'TextDecoder("utf-8")' in html
    assert "コピーできませんでした。下のプロンプト欄から手動でコピーしてください。" in html
    assert "innerHTML" not in html
    assert "eval(" not in html


def test_copy_button_html_uses_the_requested_dom_id():
    html = build_copy_button_html("prompt", "retry-copy")

    assert 'id="retry-copy-button"' in html
    assert 'id="retry-copy-status"' in html


def test_copy_button_html_rejects_an_unsafe_dom_id():
    with pytest.raises(ValueError):
        build_copy_button_html("prompt", 'copy" onclick="alert(1)')

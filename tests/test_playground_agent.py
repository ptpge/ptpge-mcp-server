"""Playground 0.27.0 — agent mode is wired in (static checks; the browser
loop itself is exercised by tests/browser/agent_loop_check.py with a mocked
model against the live /mcp)."""
from ptpge_mcp.playground import PLAYGROUND_HTML as H


def test_agent_mode_present():
    assert 'id="agent-box"' in H and 'id="ag-mode"' in H and 'id="ag-key"' in H
    assert "async function agentRun" in H and "agModeChange()" in H
    for opt in ("sponsored", "anthropic", "openai"):
        assert f'value="{opt}"' in H


def test_agent_system_prompt_and_proxy():
    assert "PTPGE-PLAYGROUND-AGENT/1" in H              # the proxy's marker
    assert 'https://engine.gutenlex.com' in H           # Layer 3 holds the key
    assert '/agent/messages' in H and '/agent/status' in H
    assert 'language = \\"LANGCODE\\"' in H              # escaped for the JS string
    for tool in ("ptpge_search_terms", "ptpge_get_product_envelope",
                 "ptpge_resolve_color_notation", "ptpge_validate_config", "ptpge_fingerprint"):
        assert tool in H


def test_own_key_never_leaves_browser_path():
    # own-key calls go straight to the providers, never to our servers
    assert "https://api.anthropic.com/v1/messages" in H
    assert "https://api.openai.com/v1/chat/completions" in H
    assert "anthropic-dangerous-direct-browser-access" in H
    assert "ptpge-agent-key-" in H                        # localStorage only


def test_0280_rules_never_assume_the_fold_and_regex_is_literal():
    """0.28.0 (SD-0083): 'folded' with no fold named is not assumed; the validator
    asks and no identity is issued. A folded sheet's faces are outside/inside.
    The FOLDW regex must reach the browser with a literal backslash-b — a bare \\b inside the Python string is a backspace
    (trap hit 2026-09-16)."""
    # 0.28.0 / SD-0083: the fold is no longer assumed — the validator asks.
    assert "the validator will ask which fold (SD-0083)" in H
    assert "single-fold (one fold — name the fold to change it)" not in H
    assert "no identity yet — the Standard asks (SD-0083)" in H
    assert 'folded ? "outside" : "front"' in H
    i = H.index("const FOLDW"); line = H[i:H.index("\n", i)]
    assert "\\bfolded\\b" in line and "\b" not in line   # literal \b, no backspace char
    assert "gefalzt" in line and "gevouwen" in line and "fals(et|ede|ad|ade)" in line

"""
Adversarial Empirical Verification Suite for Pluto UI Milestone 2.
Path: /home/jenil/Pluto/tests/test_frontend_adversarial.py

Tests:
1. CSS Light Theme & OLED Dark Purge Audit
2. WCAG 2.1 Contrast & Typography Audit
3. ThinkingOrb dark={false} and State Transition Machine Audit
4. SettingsModal Backdrop, Escape Key, and Health Check Audit
5. Backend API Service Contract & Robustness Audit
"""

import re
from pathlib import Path
import pytest

UI_ROOT = Path("/home/jenil/Pluto/ui")
SRC_ROOT = UI_ROOT / "src"


def parse_hex_color(hex_str: str) -> tuple[float, float, float]:
    """Parse #rgb or #rrggbb to normalized (r, g, b) floats."""
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join(c * 2 for c in hex_str)
    r = int(hex_str[0:2], 16) / 255.0
    g = int(hex_str[2:4], 16) / 255.0
    b = int(hex_str[4:6], 16) / 255.0
    return r, g, b


def relative_luminance(r: float, g: float, b: float) -> float:
    """Compute WCAG 2.1 relative luminance."""
    def channel_lum(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    rl = channel_lum(r)
    gl = channel_lum(g)
    bl = channel_lum(b)
    return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl


def contrast_ratio(hex1: str, hex2: str) -> float:
    """Compute WCAG 2.1 contrast ratio between two hex colors."""
    l1 = relative_luminance(*parse_hex_color(hex1))
    l2 = relative_luminance(*parse_hex_color(hex2))
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


class TestAdversarialThemeAudit:
    """Inspect CSS styles, background tokens, and contrast ratios."""

    def test_01_purge_of_oled_dark_styles(self):
        """Verify that no #050505 or old dark OLED styles remain in any CSS or JSX files."""
        css_files = list(SRC_ROOT.glob("**/*.css")) + list(SRC_ROOT.glob("**/*.jsx"))
        forbidden_patterns = [
            r"#050505",
            r"rgb\(\s*5\s*,\s*5\s*,\s*5\s*\)",
            r"aurora-bg",
            r"dark=\{true\}",
            r"AgentPanel",
        ]

        violations = []
        for file_path in css_files:
            content = file_path.read_text(encoding="utf-8")
            for pattern in forbidden_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    violations.append(f"{file_path.name}: matched '{pattern}' {len(matches)} times")

        assert not violations, f"Forbidden OLED dark artifacts found: {violations}"

    def test_02_css_root_tokens_are_light(self):
        """Verify that root CSS background tokens are light/white (#ffffff, #f8fafc, #f1f5f9)."""
        index_css = (SRC_ROOT / "index.css").read_text(encoding="utf-8")

        expected_tokens = {
            "--pluto-bg-app": "#f8fafc",
            "--pluto-bg-surface": "#ffffff",
            "--pluto-bg-sidebar": "#f8fafc",
            "--pluto-bg-muted": "#f1f5f9",
            "--pluto-bg-active": "#eff6ff",
            "--pluto-text-primary": "#0f172a",
            "--pluto-text-secondary": "#475569",
        }

        for token, expected_val in expected_tokens.items():
            pattern = rf"{re.escape(token)}:\s*([^;]+);"
            match = re.search(pattern, index_css)
            assert match is not None, f"Token {token} not found in index.css"
            actual_val = match.group(1).strip()
            assert actual_val.lower() == expected_val.lower(), (
                f"Token {token} expected {expected_val}, got {actual_val}"
            )

    def test_03_text_contrast_wcag_standards(self):
        """Verify that primary and secondary text colors meet WCAG AA and AAA requirements."""
        # Primary text #0f172a against white #ffffff
        primary_white_ratio = contrast_ratio("#0f172a", "#ffffff")
        assert primary_white_ratio >= 7.0, (
            f"Primary text on white contrast {primary_white_ratio:.2f} fails WCAG AAA (>= 7.0)"
        )

        # Primary text #0f172a against app background #f8fafc
        primary_app_ratio = contrast_ratio("#0f172a", "#f8fafc")
        assert primary_app_ratio >= 7.0, (
            f"Primary text on #f8fafc contrast {primary_app_ratio:.2f} fails WCAG AAA (>= 7.0)"
        )

        # Secondary text #475569 against white #ffffff
        secondary_white_ratio = contrast_ratio("#475569", "#ffffff")
        assert secondary_white_ratio >= 4.5, (
            f"Secondary text on white contrast {secondary_white_ratio:.2f} fails WCAG AA (>= 4.5)"
        )

        # Secondary text #475569 against app background #f8fafc
        secondary_app_ratio = contrast_ratio("#475569", "#f8fafc")
        assert secondary_app_ratio >= 4.5, (
            f"Secondary text on #f8fafc contrast {secondary_app_ratio:.2f} fails WCAG AA (>= 4.5)"
        )

        # Accent button text #ffffff against accent bg #2563eb
        accent_btn_ratio = contrast_ratio("#ffffff", "#2563eb")
        assert accent_btn_ratio >= 4.5, (
            f"Accent button text contrast {accent_btn_ratio:.2f} fails WCAG AA (>= 4.5)"
        )

        # Accent hover text #ffffff against hover bg #1d4ed8
        accent_hover_ratio = contrast_ratio("#ffffff", "#1d4ed8")
        assert accent_hover_ratio >= 4.5, (
            f"Accent hover button text contrast {accent_hover_ratio:.2f} fails WCAG AA (>= 4.5)"
        )

        # Danger text #dc2626 on white #ffffff
        danger_ratio = contrast_ratio("#dc2626", "#ffffff")
        assert danger_ratio >= 4.5, (
            f"Danger text contrast {danger_ratio:.2f} fails WCAG AA (>= 4.5)"
        )

        # Status badge success text #065f46 on badge bg #ecfdf5
        success_badge_ratio = contrast_ratio("#065f46", "#ecfdf5")
        assert success_badge_ratio >= 7.0, (
            f"Success badge contrast {success_badge_ratio:.2f} fails WCAG AAA (>= 7.0)"
        )

        # Status badge error text #991b1b on badge bg #fef2f2
        error_badge_ratio = contrast_ratio("#991b1b", "#fef2f2")
        assert error_badge_ratio >= 7.0, (
            f"Error badge contrast {error_badge_ratio:.2f} fails WCAG AAA (>= 7.0)"
        )


class TestThinkingOrbAudit:
    """Inspect ThinkingOrb component usage, dark prop, and state machine triggers."""

    def test_01_thinking_orb_dark_false_is_strictly_enforced(self):
        """Verify that all ThinkingOrb JSX usages strictly specify dark={false}."""
        jsx_files = list(SRC_ROOT.glob("**/*.jsx"))
        orb_instances = []

        orb_tag_pattern = re.compile(r"<ThinkingOrb\b([^>]*)/?>", re.DOTALL)

        for file_path in jsx_files:
            content = file_path.read_text(encoding="utf-8")
            for match in orb_tag_pattern.finditer(content):
                attrs = match.group(1)
                orb_instances.append((file_path.name, attrs))

        assert len(orb_instances) >= 3, f"Expected at least 3 ThinkingOrb instances, found {len(orb_instances)}"

        for filename, attrs in orb_instances:
            assert "dark={false}" in attrs, (
                f"{filename}: ThinkingOrb instance missing dark={{false}}: <ThinkingOrb {attrs}/>"
            )
            assert "dark={true}" not in attrs, (
                f"{filename}: ThinkingOrb instance has dark={{true}}: <ThinkingOrb {attrs}/>"
            )

    def test_02_at_least_three_distinct_visual_states_triggered(self):
        """Verify that at least 3 distinct visual states are dynamically triggered in the UI."""
        app_jsx = (SRC_ROOT / "App.jsx").read_text(encoding="utf-8")
        chat_area_jsx = (SRC_ROOT / "components" / "ChatArea.jsx").read_text(encoding="utf-8")

        # Find all setOrbState calls in App.jsx
        set_state_pattern = re.compile(r"setOrbState\(['\"]([^'\"]+)['\"]\)")
        triggered_states = set(set_state_pattern.findall(app_jsx))

        # Check default initial state in useState
        initial_match = re.search(r"useState\(['\"]([^'\"]+)['\"]\)", app_jsx)
        if initial_match:
            triggered_states.add(initial_match.group(1))

        # Valid thinking-orbs states
        valid_orb_states = {
            "working", "searching", "solving", "listening",
            "connecting", "weaving", "composing", "breathing", "shaping"
        }

        # Verify all triggered states are valid thinking-orbs states
        invalid_states = triggered_states - valid_orb_states
        assert not invalid_states, f"App triggers invalid thinking-orbs states: {invalid_states}"

        # Verify >= 3 distinct states are triggered
        assert len(triggered_states) >= 3, (
            f"Expected at least 3 distinct states, found {len(triggered_states)}: {triggered_states}"
        )

        # Specifically verify interaction transitions:
        assert "breathing" in triggered_states, "Expected 'breathing' state (idle)"
        assert "listening" in triggered_states, "Expected 'listening' state (input focus)"
        assert "searching" in triggered_states, "Expected 'searching' state (query submit)"
        assert "solving" in triggered_states, "Expected 'solving' state (deliberation)"
        assert "working" in triggered_states, "Expected 'working' state (response processing)"

    def test_03_chat_area_status_labels_correspond_to_states(self):
        """Verify ChatArea getStatusLabel maps all triggered states cleanly."""
        chat_area_jsx = (SRC_ROOT / "components" / "ChatArea.jsx").read_text(encoding="utf-8")

        for state in ["listening", "connecting", "searching", "solving", "working", "shaping", "breathing"]:
            assert f"case '{state}':" in chat_area_jsx or state == "breathing", (
                f"ChatArea missing status label handler for state '{state}'"
            )


class TestSettingsModalAudit:
    """Inspect SettingsModal behavior, backdrop click, Escape key handling, and health check."""

    def test_01_escape_key_listener_and_cleanup(self):
        """Verify SettingsModal listens for Escape key and cleans up event listener."""
        settings_jsx = (SRC_ROOT / "components" / "SettingsModal.jsx").read_text(encoding="utf-8")

        assert "window.addEventListener('keydown', handleKeyDown)" in settings_jsx, (
            "SettingsModal must register keydown listener on window"
        )
        assert "window.removeEventListener('keydown', handleKeyDown)" in settings_jsx, (
            "SettingsModal must clean up keydown listener on unmount"
        )
        assert "e.key === 'Escape'" in settings_jsx, (
            "SettingsModal must dismiss on Escape key"
        )

    def test_02_backdrop_click_dismissal(self):
        """Verify modal backdrop dismissal checks e.target === e.currentTarget to prevent modal content clicks dismissing."""
        settings_jsx = (SRC_ROOT / "components" / "SettingsModal.jsx").read_text(encoding="utf-8")

        assert "e.target === e.currentTarget" in settings_jsx, (
            "SettingsModal backdrop click must check e.target === e.currentTarget"
        )
        assert "onClick={handleBackdropClick}" in settings_jsx, (
            "modal-backdrop element must have onClick={handleBackdropClick}"
        )

    def test_03_backend_health_check_trigger(self):
        """Verify SettingsModal triggers checkBackendHealth on Test Connection click."""
        settings_jsx = (SRC_ROOT / "components" / "SettingsModal.jsx").read_text(encoding="utf-8")

        assert "checkBackendHealth" in settings_jsx, (
            "SettingsModal must import and call checkBackendHealth"
        )
        assert "onClick={handleTestConnection}" in settings_jsx, (
            "Test Connection button must have onClick={handleTestConnection}"
        )
        assert "setTestStatus('testing')" in settings_jsx, (
            "handleTestConnection must set status to testing"
        )
        assert "setTestStatus('success')" in settings_jsx, (
            "handleTestConnection must set status to success upon resolution"
        )
        assert "setTestStatus('error')" in settings_jsx, (
            "handleTestConnection must set status to error upon rejection"
        )


class TestFrontendBackendContractAudit:
    """Verify frontend api.js contract matches backend specifications."""

    def test_01_default_endpoint_matches_backend(self):
        """Verify DEFAULT_BASE_URL is http://localhost:8000."""
        api_js = (SRC_ROOT / "services" / "api.js").read_text(encoding="utf-8")

        assert "http://localhost:8000" in api_js, (
            "api.js default endpoint must point to http://localhost:8000"
        )

    def test_02_api_endpoints_match_backend_routes(self):
        """Verify /api/health and /api/chat endpoints are correctly constructed."""
        api_js = (SRC_ROOT / "services" / "api.js").read_text(encoding="utf-8")

        assert "/api/health" in api_js, "api.js must call /api/health"
        assert "/api/chat" in api_js, "api.js must call /api/chat"

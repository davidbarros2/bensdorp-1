"""Tests for ui/prompts.py — custom prompts per rules 6.15-6.18 (D-05)."""

import pytest
from rich.console import Console

from bensdorp1.ui.prompts import confirm_prompt, number_prompt, text_prompt

# ---------------------------------------------------------------------------
# confirm_prompt tests
# ---------------------------------------------------------------------------


def test_confirm_y(monkeypatch: pytest.MonkeyPatch) -> None:
    """Input 'y' returns True."""
    monkeypatch.setattr("builtins.input", lambda _: "y")
    assert confirm_prompt("Delete?") is True


def test_confirm_Y_uppercase(monkeypatch: pytest.MonkeyPatch) -> None:
    """Input 'Y' returns True."""
    monkeypatch.setattr("builtins.input", lambda _: "Y")
    assert confirm_prompt("Delete?") is True


def test_confirm_n(monkeypatch: pytest.MonkeyPatch) -> None:
    """Input 'n' returns False."""
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert confirm_prompt("Delete?") is False


def test_confirm_N_uppercase(monkeypatch: pytest.MonkeyPatch) -> None:
    """Input 'N' returns False."""
    monkeypatch.setattr("builtins.input", lambda _: "N")
    assert confirm_prompt("Delete?") is False


def test_confirm_reprompts_on_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty or non-y/n input causes re-prompt; True after 'y' on third try."""
    call_count = 0
    inputs = iter(["", "maybe", "y"])

    def counting_input(_: str) -> str:
        nonlocal call_count
        call_count += 1
        return next(inputs)

    monkeypatch.setattr("builtins.input", counting_input)
    result = confirm_prompt("Delete?")
    assert result is True
    assert call_count == 3


def test_confirm_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    """KeyboardInterrupt causes cancellation message and returns False."""

    def _raise_kbd(_: str) -> str:
        raise KeyboardInterrupt

    c = Console(record=True, width=80)
    monkeypatch.setattr("builtins.input", _raise_kbd)
    result = confirm_prompt("Delete?", console=c)
    assert result is False
    output = c.export_text()
    assert "Operation aborted. No changes were made." in output


def test_confirm_displays_y_n_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """The string passed to input() contains the literal '[y/n] ' suffix."""
    recorded_prompt: list[str] = []

    def recorder(prompt: str) -> str:
        recorded_prompt.append(prompt)
        return "y"

    monkeypatch.setattr("builtins.input", recorder)
    confirm_prompt("Delete?")
    assert len(recorded_prompt) == 1
    assert "[y/n] " in recorded_prompt[0]


# ---------------------------------------------------------------------------
# text_prompt tests
# ---------------------------------------------------------------------------


def test_text_prompt_returns_input(monkeypatch: pytest.MonkeyPatch) -> None:
    """text_prompt returns the stripped input value."""
    monkeypatch.setattr("builtins.input", lambda _: "hello")
    assert text_prompt("name") == "hello"


def test_text_prompt_reprompts_on_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """text_prompt re-prompts when input is empty; returns second non-empty value."""
    call_count = 0
    inputs = iter(["", "x"])

    def counting_input(_: str) -> str:
        nonlocal call_count
        call_count += 1
        return next(inputs)

    monkeypatch.setattr("builtins.input", counting_input)
    result = text_prompt("label")
    assert result == "x"
    assert call_count == 2


# ---------------------------------------------------------------------------
# number_prompt tests
# ---------------------------------------------------------------------------


def test_number_prompt_parses_float(monkeypatch: pytest.MonkeyPatch) -> None:
    """number_prompt parses valid float input and returns it."""
    monkeypatch.setattr("builtins.input", lambda _: "100.50")
    assert number_prompt("Cash", "USD") == pytest.approx(100.50)


def test_number_prompt_reprompts_on_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """number_prompt re-prompts on non-numeric input and returns next valid float."""
    call_count = 0
    inputs = iter(["abc", "50"])

    def counting_input(_: str) -> str:
        nonlocal call_count
        call_count += 1
        return next(inputs)

    c = Console(record=True, width=80)
    monkeypatch.setattr("builtins.input", counting_input)
    result = number_prompt("Cash", "USD", console=c)
    assert result == pytest.approx(50.0)
    assert call_count == 2

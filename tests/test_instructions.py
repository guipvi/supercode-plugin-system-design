"""Garante que as instruções dos agentes impõem o fluxo de permissão da UI."""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_instructions():
    with open(os.path.join(ROOT, "instructions.md"), encoding="utf-8") as fh:
        return fh.read()


def test_forbids_direct_writes():
    text = read_instructions()
    assert "NUNCA" in text
    assert "system-design" in text and ".json" in text


def test_concept_requires_proposal():
    text = read_instructions()
    assert "conceitual" in text.lower()
    assert "proposta" in text.lower()


def test_locked_targets_respected():
    text = read_instructions()
    assert "locked" in text


def test_only_user_decides():
    text = read_instructions().lower()
    assert "usuário" in text or "usuario" in text
    assert "aprov" in text

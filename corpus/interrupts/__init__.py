"""Corpus interrupt bridge — connects signals to checkpoint governance."""

from corpus.interrupts.interrupt_bridge import InterruptBridge
from corpus.interrupts.interrupt_rules import InterruptRules, RuleMatch

__all__ = ["InterruptBridge", "InterruptRules", "RuleMatch"]

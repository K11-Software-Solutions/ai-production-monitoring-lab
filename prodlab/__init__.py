"""prodlab: monitor an AI assistant in (simulated) production.

A deterministic simulator produces realistic traffic for a support assistant,
including scheduled incidents: a silent model update, a product launch the
docs don't cover, a language shift, a provider latency spike, a prompt-
injection campaign and prompt bloat. Because the simulator knows the ground
truth, the monitoring itself can be tested: did every incident raise the
right alert, how fast, and how many false alarms were there?
"""

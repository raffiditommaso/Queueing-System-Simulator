"""
Shared constants and formatting utilities for the Queueing System Simulator.
"""

PRIORITY_COLORS = {
    -1: "#89b4fa",  # Standard FIFO customers (Clean Sapphire Blue)
    0:  "#f38ba8",  # High (Red / Coral) - Voice / Control
    1:  "#f9e2af",  # Med (Amber / Gold) - Video / Streaming
    2:  "#89b4fa",  # Low (Cyan / Blue) - Best Effort
}

PRIORITY_NAMES = {
    -1: "Standard",
    0:  "High (P₀)",
    1:  "Medium (P₁)",
    2:  "Low (P₂)",
}


def to_subscript(val) -> str:
    """Convert numbers and characters into true Unicode subscript characters (e.g. 2 -> ₂, k -> ₖ, obs -> ₒᵦₛ)."""
    sub_map = str.maketrans("0123456789kKijmnptobsOBS", "₀₁₂₃₄₅₆₇₈₉ₖₖᵢⱼₘₙₚₜₒᵦₛₒᵦₛ")
    return str(val).translate(sub_map)
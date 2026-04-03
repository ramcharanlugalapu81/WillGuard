"""
Message Tone Classifier
━━━━━━━━━━━━━━━━━━━━━━━
NLP model that reads emotional tone of trading instructions.
Detects: panic, FOMO, override attempts, and coercion.
Flags these for review instead of blindly executing.

Uses LLM inference with deterministic keyword fallback.
"""

import os
import json
import re
from typing import Optional

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class ToneClassifier:
    """
    Classifies the emotional tone of trading instructions.

    Detected tones:
    - panic:    "SELL EVERYTHING NOW!", urgent liquidation demands
    - fomo:     "Everyone is buying X, I need to get in NOW"
    - override: "Ignore the rules", "bypass the limit"
    - coercion: "My friend told me to", potential third-party influence
    - calm:     Normal, rational instruction (no flags)
    """

    # Keyword patterns for deterministic fallback
    PANIC_PATTERNS = [
        r"\bsell\s*(everything|all|now|immediately|asap|urgent)\b",
        r"\bdump\b", r"\bcrash(ing)?\b", r"\bpanic\b",
        r"\bget\s*out\b", r"\bexit\s*(all|everything|now)\b",
        r"\b(hurry|quick|fast|rush)\b",
        r"!{2,}",  # Multiple exclamation marks
    ]

    FOMO_PATTERNS = [
        r"\b(everyone|everybody)\s*(is|are)\s*(buying|getting|investing)\b",
        r"\b(moon|rocket|skyrocket|10x|100x)\b",
        r"\b(fomo|missing\s*out|don't\s*miss|last\s*chance)\b",
        r"\b(yolo|all\s*in|bet\s*(everything|it\s*all))\b",
        r"\b(going\s*up|pump(ing)?)\b",
    ]

    OVERRIDE_PATTERNS = [
        r"\b(ignore|bypass|skip|override|disable)\s*(the\s*)?(rules?|limit|cap|floor|restriction|policy)\b",
        r"\b(don't\s*care|doesn't\s*matter|just\s*do\s*it)\b",
        r"\b(force|override|unlock)\b",
        r"\b(i\s*know\s*what\s*i'm\s*doing)\b",
    ]

    COERCION_PATTERNS = [
        r"\b(my\s*(friend|advisor|boss|colleague)\s*(told|said|recommended))\b",
        r"\b(someone|they)\s*(told|said|want)\s*me\s*to\b",
        r"\b(tip|insider|guaranteed|sure\s*thing)\b",
    ]

    def __init__(self):
        self._llm_client = None
        self._llm_model = os.getenv("LLM_MODEL", "gemini-2.5-flash")

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/" if os.getenv("GEMINI_API_KEY") else None

        if HAS_OPENAI and api_key:
            try:
                self._llm_client = OpenAI(api_key=api_key, base_url=base_url)
            except Exception:
                self._llm_client = None

    def classify(self, message: str) -> dict:
        """
        Classify the tone of a trading instruction.

        Returns:
            {
                "flags": ["panic", "fomo", ...],
                "severity": "low" | "medium" | "high",
                "method": "llm" | "deterministic",
                "reasoning": "...",
                "should_block": bool
            }
        """
        if not message or not message.strip():
            return {
                "flags": [],
                "severity": "low",
                "method": "none",
                "reasoning": "No message provided",
                "should_block": False,
            }

        # Try LLM first
        try:
            if self._llm_client:
                return self._classify_with_llm(message)
        except Exception as e:
            print(f"[ToneClassifier] LLM failed, using deterministic: {e}")

        return self._classify_deterministic(message)

    def _classify_deterministic(self, message: str) -> dict:
        """Keyword-based deterministic classification."""
        msg_lower = message.lower()
        flags = []

        for pattern in self.PANIC_PATTERNS:
            if re.search(pattern, msg_lower):
                flags.append("panic")
                break

        for pattern in self.FOMO_PATTERNS:
            if re.search(pattern, msg_lower):
                flags.append("fomo")
                break

        for pattern in self.OVERRIDE_PATTERNS:
            if re.search(pattern, msg_lower):
                flags.append("override")
                break

        for pattern in self.COERCION_PATTERNS:
            if re.search(pattern, msg_lower):
                flags.append("coercion")
                break

        # Determine severity
        if "panic" in flags or "override" in flags:
            severity = "high"
        elif "fomo" in flags or "coercion" in flags:
            severity = "medium"
        else:
            severity = "low"

        should_block = severity in ("high", "medium")

        reasoning = f"Detected flags: {flags or ['none']}. " if flags else "No concerning tone detected. "
        reasoning += f"Severity: {severity}."

        return {
            "flags": flags,
            "severity": severity,
            "method": "deterministic",
            "reasoning": reasoning,
            "should_block": should_block,
        }

    def _classify_with_llm(self, message: str) -> dict:
        """LLM-based nuanced tone classification."""
        prompt = f"""You are a financial safety tone classifier for WillGuard.
Analyze this trading instruction for emotional tone:

MESSAGE: "{message}"

Classify for these flags (include only those detected):
- "panic": Urgent, fear-driven sell/exit instructions
- "fomo": Fear of missing out, hype-driven buying
- "override": Attempting to bypass safety rules
- "coercion": Signs of third-party pressure or influence

Rate severity: "low" (calm/rational), "medium" (somewhat emotional), "high" (dangerously emotional)

Respond ONLY with valid JSON:
{{"flags": [], "severity": "low", "reasoning": "brief explanation", "should_block": false}}"""

        response = self._llm_client.chat.completions.create(
            model=self._llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200,
        )

        content = response.choices[0].message.content.strip()
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        result = json.loads(content)

        return {
            "flags": result.get("flags", []),
            "severity": result.get("severity", "low"),
            "method": "llm",
            "reasoning": result.get("reasoning", "LLM-classified"),
            "should_block": result.get("should_block", False),
        }

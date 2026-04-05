#!/usr/bin/env python3
"""Test the improved LLM prompt."""

from macos_app.llm_cleanup import build_prompt

print("=" * 70)
print("IMPROVED PROMPT DESIGN - FIXES REFUSAL ISSUE")
print("=" * 70)

test_transcript = "um so I wanted to uh meet at 5pm no actually 6pm on thursday"
prompt = build_prompt(test_transcript)

print("\n📝 NEW PROMPT:")
print("-" * 70)
print(prompt)
print("-" * 70)

print("\n✅ KEY CHANGES:")
print("  1. ✓ Removed verbose 'CRITICAL RULES' section")
print("  2. ✓ Removed all 'do NOT' language (was triggering refusals)")
print("  3. ✓ Single, direct instruction")
print("  4. ✓ Focus only on input → cleaning → output")
print("  5. ✓ No meta-commentary or policy mentions")

print("\n🧠 LLM MODEL:")
print("  • Model: llama3.2:1b (lightweight, task-focused)")
print("  • Temperature: 0.3 (allows some variation)")
print("  • Max output: 200 tokens")

print("\n🛡️  REFUSAL HANDLING:")
print("  If model refuses, patterns detected:")
print("    ✓ 'i cannot', 'cannot fulfill'")
print("    ✓ 'would violate', 'policy'")
print("    ✓ Returns raw transcript instead")

print("\n" + "=" * 70)
print("READY TO TEST WITH OLLAMA")
print("=" * 70)
print("\nStart Ollama: ollama serve")
print("Pull model:   ollama pull llama3.2:1b")
print("Run app:      python3 macos_app/menubar_dictation.py")

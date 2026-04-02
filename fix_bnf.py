with open("src/strategies/gatekeeper_bnf_b.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace('if "Backtest" not in self.name:', 'if "Backtest" not in self.name and "Opt" not in self.name:')

with open("src/strategies/gatekeeper_bnf_b.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Fixed strategy code!")

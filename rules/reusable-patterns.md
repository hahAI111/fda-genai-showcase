# Reusable Patterns Rule

## Rule

**When you solve a customer problem, always ask: "Is this a one-off fix or a reusable pattern?" If it's reusable, extract it into a skill or product feedback.**

## Pattern Extraction Flow

```
Customer Problem Solved
    │
    ├─ One-off (customer-specific config) → Document and move on
    │
    └─ Reusable pattern (seen ≥ 2 times) → Extract:
        ├─ New SKILL.md → skills/{pattern-name}/SKILL.md
        ├─ Product feedback → docs/PRODUCT_FEEDBACK.md
        └─ Documentation update → relevant reference docs
```

## Reusable Pattern Indicators

A problem is likely reusable when:
- You've seen it at ≥ 2 different customers
- The solution doesn't depend on customer-specific data
- It addresses a common enterprise deployment blocker
- It could be automated or templatized

## Why This Matters

- The FDA role's value isn't just solving one customer's problem
- It's making sure the **next** customer doesn't hit the same problem
- Skills are how field knowledge scales beyond one person
- Product feedback is how field friction becomes product improvement

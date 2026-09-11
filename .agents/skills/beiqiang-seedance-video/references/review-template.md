# Video Review Template

Create or append:

```text
output/seedance/reviews/<SKU>.md
```

Use one section per task ID.

```markdown
## <TASK_ID> — <DATE>

- Model:
- Prompt:
- Source images:
- Specifications:
- Tokens:
- Estimated cost:
- Output:
- QA run directory:
- Source ID:

### Scores

| Dimension | Score / 10 | Evidence |
|---|---:|---|
| Product identity |  |  |
| First-second hook |  |  |
| Benefit proof |  |  |
| Physical realism |  |  |
| Editing rhythm |  |  |
| Music and sound |  |  |
| B2B usefulness |  |  |
| Platform fit |  |  |

### What Worked

- 

### Problems

- `<start>–<end> | <severity> | <category> | <observable defect> | <KEEP/TRIM/REGENERATE>`

### Next Prompt Changes

1. 
2. 
```

## Review Rules

- Inspect the whole video, not only the first frame.
- Use the shared `video-use` contact-sheet and focused-candidate workflow; open suspicious frames at original resolution before assigning severity.
- Separate product-identity failures from creative-style preferences.
- Prioritize defects that misrepresent the real product.
- Write observable problems, not vague comments such as “make it better.”
- Preserve `first_bad_frame`, `peak_bad_frame`, and `recovery_frame` in the linked `qa_report.json` when they can be established.
- Carry the top two prompt changes into the next generation.

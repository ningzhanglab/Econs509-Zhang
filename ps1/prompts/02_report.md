# Prompt 02: Check the report

## Task

Check my draft `report.tex` against the saved results. Correct numbers and typos only; leave my explanations, interpretations, and reasons for each choice unchanged.

## Context

Start in `ps1/`. Read the agent file, `spec.md`, `tests.md`, `log.md`, `README.md`, my draft `report.tex`, and relevant files in `results/`. Confirm stage 4 is complete, my independent verification is recorded, and the draft and this prompt were committed together before the run. Report missing inputs or supporting results and stop.

Propose a short checking plan. The report source is `report.tex` in the assignment root; `prompts/` contains the checking instructions.

I handle Git manually in GitHub Desktop. Do not stage, commit, push, or tag. Prepare the report-check files and commit information, then wait for my manual commit. Read-only Git history and status checks are allowed.

## Constraints

Check every computed number in the text against `results/*.json`, allowing only rounding at the displayed precision. Check parameter and algorithm statements against `spec.md`. Compare Markdown tables with `results/tables.md`, and every table and figure reference with the corresponding file in `results/`.

Preserve my wording except for numerical corrections and typos. An explicit table or figure placeholder may be replaced with the corresponding generated table or image reference. Do not invent results, fill missing numerical or explanatory sentences, choose methods, rewrite arguments, or alter code, results, inputs, or manual work. Flag unsupported claims, substantive errors, and unclear references for my revision. Do not rerun experiments or install packages.

Check coverage of Question 2(a)–(h), the manual-derivation citation, final tests, and two independent verification checks, including the manual-kernel comparison. The verification section must distinguish agent claims from my checks and cite dated log entries. Cross-check its descriptions and dates against my entries in `log.md`; this review does not replace my verification. Check that the AI-use note identifies the agent, access mode, and who wrote what. Flag omissions without writing personal claims on my behalf.

## Output format

Append a dated entry to `log.md` naming the agent/model and `prompts/02_report.md`. List each correction with its location, old and new text, and supporting result file/key. Record checks performed and unresolved issues. Report the correction count and a readable diff.

Provide the changed-file list and proposed summary `report: checked against results/, N corrections`, with the actual count and accurate agent attribution. Record concerns in the log for my revision; the check does not endorse my explanations. **STOP for my manual report-check commit**. The stage-5 commit and final submission tag are mine.

## Success criteria

Every reported number and file reference is checked, corrections are traceable, and explanations remain intact. Report the correction count and concerns, then stop. Record the check commit hash only after confirmation. I will review the diff, make the report-check commit, resolve concerns, finish the text, build `report.pdf`, and make the stage-5 commit.

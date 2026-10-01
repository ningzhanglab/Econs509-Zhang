# Prompt 00: Build and verify the solver

## Task

Implement the solver and tests specified in `spec.md` and `tests.md`. Complete stages 2 and 3, then stop before the full experiments.

## Context

Start in `ps1/`. Read the agent-instructions file, `spec.md`, `tests.md`, and `log.md`. Confirm that stage 0, my manual work at stage 1, and this prompt were committed before implementation. Use the manual reference only for the kernel test; stop if it is missing or lacks the specified fields.

List missing or conflicting definitions before proceeding. If any remain, stop for my revision. Otherwise propose a short plan covering files, tests, validation runs, and commits; wait for my approval before large changes.

## Constraints

Take every model and numerical definition from `spec.md`. Implement tests before or together with the routines they test. Do not modify my input files, overwrite the manual reference, change criteria, install packages, or rewrite history. Report applicable test failures and stop. Follow the agent file's run limits and logging rules.

I handle Git manually in GitHub Desktop. Do not stage, commit, push, or tag. At each commit boundary, provide the changed-file list, measured Summary/Description text, and accurate agent attribution, then wait for my confirmation. Read-only Git history and status checks are allowed.

## Output format

Implement the model, all solver and distribution routines, Euler diagnostics, output writers, and reproduction driver in `code/`, and the specified checks in `tests/`.

Run the validation inputs in `spec.md`. Prepare the first running solver and implemented tests for stage 2, with actual iterations and exit metric in the proposed message. Append a dated log entry and **STOP for my manual commit**.

After I confirm stage 2 is committed, run all applicable stage-3 checks, including the kernel comparison. If they pass, provide the stage-3 changed files, measured kernel differences, test results, and dated log entry. **STOP for my manual commit**. Identify agent authorship at both boundaries.

## Success criteria

Report validation commands, kernel value difference, policy mismatch count, and each applicable test outcome. Record commit hashes only after confirmation. Distinguish results verified by running from claims, and mark stage-4 checks as pending. Stop and await the committed `prompts/01_experiments.md`; final method choices and report explanations are mine.

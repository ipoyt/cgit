# TODO: add an ability to update / create tests for the changed / added code
#
# A cgit tests [REV] command shaped like docs, and optionally run as a step in cgit commit:
# 
# 1. Inputs to the agent: the commit diff with docs files left out, the knowledge summary, 
#    and the existing test files. The agent copies the framework and style those tests already use, 
#    which is what keeps cgit agnostic. 
#    With no existing tests it follows the knowledge summary, and if that says nothing about testing, it skips with a message.
# 2. What it may touch: files matching a new tests glob setting (e.g. ["tests/*", "*_test.*", "*.test.*", "test_*"]). 
#    Unlike docs, it's allowed to create new files there. The same dirty_snapshot() guard from docs reverts anything else, 
#    so it can never edit source code.
# 3. Running the tests: cgit runs them itself. The agent doesn't get a shell tool, which keeps it from running arbitrary commands. 
#    The command comes from a test_command setting in .cgit.toml (e.g. pytest -q, npm test, go test ./...). If it isn't set, 
#    cgit suggests the command from the knowledge summary, asks once, and saves your answer. 
#    It never runs a command the AI guessed without your confirmation.
# 4. Fix loop: if tests fail, cgit sends the output back to the agent and lets it fix the tests, 
#    up to about 3 rounds.
# 5. Result: if the tests pass, cgit commits them separately (test: cover <sha>). If they still fail, it keeps them out of the commit, 
#    leaves them in the working tree and warns you. A new test that keeps failing may mean the code has a bug, 
#    and the agent mustn't hide that by weakening the test.

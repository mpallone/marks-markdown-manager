---
name: test-writer
description: Generate test cases for code, focusing on edge cases and coverage
---

# Test Writer

When asked to write tests:

1. Identify the function/class under test
2. Write tests for the happy path first
3. Add edge case tests (empty input, None, boundary values, large inputs)
4. Add error case tests (invalid input, expected exceptions)
5. Use descriptive test names that explain what is being tested
6. Prefer pytest style over unittest style
7. Mock external dependencies but not the code under test

---
name: mmt-api-hardening
description: Harden My Movie Tracker API inputs and server-authoritative behavior. Use for request validation, rating validation, ID/page/cursor/skip validation, quiz answer integrity, malformed payload handling, or API regression tests.
---
# My Movie Tracker API Hardening
Improve API correctness without redesigning unrelated features.
Read:
- `docs/API.md`
- `docs/FEATURES.md`
- `docs/TECH_DEBT.md`
## Validation principles
Validate at the server boundary.
Do not rely on frontend TypeScript types or UI controls as security or integrity controls.
Reject malformed values explicitly.
Prefer a single consistent validation path over repeated ad hoc casts.
## Rating
Ensure ratings:
- are integers;
- are within the supported product range;
- reject booleans, malformed strings and out-of-range values;
- do not silently coerce invalid values into acceptable values.
Preserve the current rating scale used by the product.
## Pagination and IDs
Validate relevant:
- movie IDs;
- user-visible IDs where still accepted;
- page;
- cursor;
- skip;
- media type;
- target type;
- filter values.
Avoid absurd or unbounded numeric inputs.
## Quiz integrity
The server must determine whether a quiz answer is correct.
The client may submit:
- a question/quiz identifier;
- the selected answer;
but must not be authoritative for `correct=true/false`.
Do not expose the correct answer to the frontend in a way that trivially defeats the quiz if the existing product can support a safer server-side design.
Use a bounded server-side or signed-token mechanism that fits the current architecture.
Avoid introducing unnecessary infrastructure solely for quiz state.
## Testing
Add focused tests for:
- valid values;
- boundary values;
- malformed values;
- missing values;
- quiz tampering;
- repeated submissions if they can affect points.
Do not redesign the entire quiz feature unless required to remove the trust flaw.

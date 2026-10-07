For **your part only (Wes)**, the document gives you seven tasks. [Team Tasks: 10_2_2026 - 10_12_2…](https://docs.google.com/document/d/18Jels3BXdCcmjEnUsNuy_2hGuGodRqSP5QjSnV4VKiM/edit)

Before **Monday, October 12**, I'd translate those into this concrete finish line:

- [x] **Backend setup is finished**
    - ABLE TO RUN LOCALLy NOT JUST MAKE A CONTAINER
   - `goal-stats-service` cleanly clones, sets up, runs, tests, and stops.
   - Docker/PostgreSQL/Redis startup is reliable.
   - Your branch is `member/wes`, not `master`. [Team Tasks: 10_2_2026 - 10_12_2…](https://docs.google.com/document/d/18Jels3BXdCcmjEnUsNuy_2hGuGodRqSP5QjSnV4VKiM/edit)

- [ ] **Get the real football data into the database**
   - Organize the datasets you're actually using.
   - Validate/clean the required fields.
   - Import/seed them into the database.
   - Confirm the records are actually queryable.

- [ ] **Finish the database persistence needed for Phase 1**
   - **Teams**
   - **Matches/Scenarios**
   - **Predictions**
   - Make sure the relationships/persistence work rather than just having CSV-backed behavior.

- [ ] **Give the frontend team usable Flask APIs**
   - Teams endpoint(s) for Esteban.
   - Match/scenario endpoint(s) for Esteban.
   - Prediction endpoint(s) for Mehla.
   - Whatever Home needs can be exposed if Nikita needs backend data.
   - Don't build endpoints nobody needs yet.

- [ ] **Verify the full backend flow**
   ```text
   Data
     ↓
   PostgreSQL
     ↓
   Flask API
     ↓
   frontend can consume it
   ```
   Test queries, API responses, creating/saving data, and retrieving it again.

- [ ] **Don't break the prediction engine**
   - Existing prediction API continues working.
   - Predictions use the database-backed team/scenario information where appropriate.
   - Saving/retrieving predictions works.

- [ ] **Give the team a tiny API/data reference**
   - What endpoint to call.
   - Request body.
   - Response shape.
   - Which fields are persisted.
   - Any endpoint that isn't ready yet.

### Your actual priority order

**Do these in this order:**

> **Data import → Teams DB/API → Scenarios DB/API → Predictions persistence/API → integration tests → frontend handoff documentation.**

Don't spend this week adding fancy backend features. Your job is to make sure that when Esteban or Mehla says **“I need Teams/Matches/Predictions data,” the answer is an endpoint they can call**, not “I'm still working on the infrastructure.” [Team Tasks: 10_2_2026 - 10_12_2…](https://docs.google.com/document/d/18Jels3BXdCcmjEnUsNuy_2hGuGodRqSP5QjSnV4VKiM/edit)

That's your Monday finish line.
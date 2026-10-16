# Option 2 Build-a-thon Preparation Answers

## Working title

Study Sprint Planner

## 1. Which problem are we choosing?

We are choosing **Option 2: Turn overwhelming study tasks into next steps**.

The app helps a student turn a group of competing assignments into a short, realistic plan for the study time available right now. The first version focuses on one study session instead of trying to manage the student's entire semester.

## System goal

For a student who feels overwhelmed by several assignments, produce a reviewable study-session plan with concrete next steps, measured by whether the plan fits the student's available time and identifies a sensible first action, without submitting work, inventing deadlines, or changing the student's calendar automatically.

## 2. What major tasks should the AI agent perform?

### User input

The student supplies:

- Assignment or study-task descriptions
- Due dates, if known
- Estimated effort or size
- Importance or grade impact
- Dependencies, such as “read the chapter before starting the quiz”
- Available study time for this session

### Workflow

1. **Validate the input.** Check that tasks have usable names, available time is positive, and dates or effort estimates are understandable.
2. **Interpret the workload.** Convert free-text task descriptions into structured task records.
3. **Prioritize the workload.** Rank tasks using deadline, importance, effort, dependencies, and the available study time.
4. **Choose a starting task.** Select the highest-value task that can make meaningful progress in the current session.
5. **Break it into next steps.** Generate two to four concrete actions that can be started immediately.
6. **Fit the steps into the session.** Use deterministic code to keep the total within the student's available minutes.
7. **Explain the recommendation.** Show why the first task was selected and what tradeoffs were made.
8. **Let the student review.** The student accepts the plan or edits the input and tries again.

### Endpoint

The workflow ends when the app displays a reviewable plan containing:

- A recommended first task
- Two to four concrete next steps
- Estimated minutes for each step
- The total planned time
- A short priority explanation
- Any missing or uncertain information

## 3. What AI models will we use?

The planned model is **OpenAI's Responses API with the fast text model `gpt-5.4-mini`**, subject to confirmation against the course's Week 6 model workbook.

The model will handle language interpretation and structured planning. It will not be trusted to perform arithmetic or enforce limits by itself. The local backend will validate the response and calculate the final time total.

The model should return structured JSON with fields similar to:

```json
{
  "summary": "Start the research outline because it is due soon and has a prerequisite reading step.",
  "ranked_task_ids": ["research-outline", "stats-quiz", "discussion-post"],
  "recommended_task_id": "research-outline",
  "next_steps": [
    {"title": "Read the assignment prompt and highlight deliverables", "minutes": 10},
    {"title": "Create a three-part outline", "minutes": 20},
    {"title": "Write the opening paragraph", "minutes": 15}
  ],
  "uncertainties": []
}
```

If the model response is invalid, the backend should show a recoverable error and ask the student to revise the input. The app should not silently invent a plan.

## 4. Do we have an API key?

Yes. The OpenAI API key is available locally for the live build, loaded from an ignored secret file. It is not committed to GitHub, printed in logs, or included in this planning document.

The student's ChatGPT login should not be assumed to provide developer API access. We need to confirm that the team has access to an API key, billing or course credits, and the correct model identifier before the buildathon.

The app also has a deterministic mock mode for offline UI testing; the live showcase path uses the real model when the key and network are available.

## 5. What tools or applications does the agent need?

The initial app only needs local tools:

- A browser dashboard for entering tasks and reviewing the plan
- A Python or Node backend for the model request and validation
- The OpenAI Responses API for the AI planning step
- A local JSON file for demo data and optional accepted plans

The first version does **not** need Gmail, Slack, a calendar, a recipe website, a social-media connection, or a task-management integration. These would add authentication and external side effects without helping the core workflow score.

## 6. Do we have API keys for the tools?

No external business-tool keys are required for the first version. We only need the selected model-provider API key. Local JSON storage, the browser interface, validation code, and the local backend do not require third-party credentials.

## Task types and automation levels

| Task | Course type | Level | Performer |
|---|---|---:|---|
| Accept the student's task list and available minutes | Sense | 0/1 | Student and app |
| Validate required fields and constraints | Verify | 1 | Local code |
| Interpret free-text task descriptions | Sense | 2 | AI model |
| Rank competing assignments | Decide | 2 | AI model inside a fixed procedure |
| Break the top assignment into next steps | Reason | 2 | AI model |
| Add minutes and fit steps into the session | Decide | 1 | Local code |
| Display the plan | Act | 1 | Local app |
| Accept or revise the plan | Verify | 0 | Student |

There is no required Level 3 task in this first version. The app uses a fixed route and fixed permitted output, so adding an “agent” branch would add risk without adding meaningful value.

## Skill decision

A small reusable study-planning Skill would be useful because the inputs change each time while the planning method stays stable. If we include one, it should define:

- Required task fields
- The priority rules
- How to handle missing or uncertain deadlines
- How to decompose a task into concrete actions
- The required structured output
- Boundaries such as no invented deadlines and no automatic submission

The Skill is optional for the first build. If time becomes tight, keep these instructions in the model prompt and explain that a separate Skill was omitted to reduce setup risk.

## Intentionally excluded features

- Automatic calendar changes
- Assignment submission
- Email or messaging
- Full-semester scheduling
- Web research about the assignment
- Persistent student profiles
- Multi-agent orchestration
- A Level 3 adaptive planner

These are outside the first workflow boundary and could make the demo unreliable.

## Three-minute demo scenario

1. Enter three assignments: a research outline due soon, a quiz, and a discussion post.
2. Set available study time to 45 minutes.
3. Show the AI-ranked workload and priority explanation.
4. Show the research outline broken into three steps totaling 45 minutes.
5. Point out that the backend—not the model—enforced the time limit.
6. Edit the available time to 20 minutes and rerun the workflow.
7. Show that the plan becomes smaller and remains actionable.

## Completion test for the buildathon

The preliminary design is ready to implement when the team can answer yes to all of these:

- Can a student enter a workload and available time?
- Does the running app call the selected model for a meaningful planning task?
- Does the app return a structured, readable plan?
- Does the plan fit within the available time?
- Can the student understand why the first task was selected?
- Can the student revise the inputs and run the workflow again?
- Can both teammates explain the model, tool, level, and Skill decisions?

The display also preserves every non-recommended assignment in a queue, uses `N/A` for missing due dates or effort estimates, and keeps the final remaining assignment as the last queue item.

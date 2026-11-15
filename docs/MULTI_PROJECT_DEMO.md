# Three-project synthetic demonstration

All projects, RFIs, people, timelines, and procedures are fictional portfolio-demo
material, not DeAngelis Diamond, Future Bylt, or Procore records. Project 101's
existing structured data is unchanged. No closed-state lifecycle is inferred.

| Project | Total | Blocking | Critical | Critical RFI IDs |
| --- | ---: | ---: | ---: | --- |
| 101 Naples Medical Center | 3 | 2 | 2 | 1, 3 |
| 202 Gulfshore Residential Tower | 6 | 3 | 2 | 1, 2 |
| 303 Southwest Logistics Center | 5 | 2 | 1 | 1 |

Critical remains `is_blocking and days_open > 7`. Project 202's blocking RFI 3 is
exactly seven days old and is not critical. Older nonblocking RFIs in projects
202/303 are also not critical. RFI IDs are local to each project.

The existing selector consumes `/projects` dynamically. Changing it refreshes
summary/critical endpoints, the register, and chat's optional `project_id` context.
Existing cache keys already include project and data fingerprints, so no cache
code or manual cache deletion is necessary. Cross-project evidence filtering is
unchanged. Shared synthetic policies remain available to all valid projects.

The new revision-1 project-scoped coordination documents add distinct release
packets: project 202's Orchid packet goes to fictional Elena Vale within two
working hours; project 303's Harbor packet goes to fictional Owen Reed within six
working hours. These are supplemental hold-release reviews, not replacements for
the shared Cedar critical-RFI escalation policy. None authorizes field work.

## Verify in the running application

1. Restart FastAPI (or let `--reload` refresh the project data).
2. Rebuild the index from the repository root:
   `.venv\Scripts\python.exe -m scripts.retrieve ingest --rebuild`.
3. Refresh the dashboard. The selector should show projects 101, 202, and 303.
4. Select each project and check the table above against its three KPI cards and
   register. Toggle **Critical only** and verify the listed IDs.
5. Ask `Give me the project RFI counts.` and `Which RFIs are critical?` on each
   project. Repeat after switching projects and returning to 101. These questions
   use deterministic routing and make no Claude calls.
6. On project 202 and then 303 ask: `According to the project-specific release
   procedure, who receives the packet and when? Cite your source.` Expect the
   distinct people/timelines above and the appropriate `BF-COORD-202` or
   `BF-COORD-303` source references. These UI requests use Claude and may incur
   configured API charges; they were tested offline with mocked Claude here.
7. Ask that same question in the local retrieval CLI to inspect actual sources
   without a paid call:

```powershell
.venv\Scripts\python.exe -m scripts.retrieve query "According to the project-specific release procedure, who receives the packet and when?" --project 202
.venv\Scripts\python.exe -m scripts.retrieve query "According to the project-specific release procedure, who receives the packet and when?" --project 303
.venv\Scripts\python.exe -m scripts.operations_report report
```

The retrieval evaluation now includes four project-202/303 questions in addition
to the original questions. `frontend/tests/multi-project.js` checks real API data,
all three selectors/KPIs/registers, and mocked chat context through Playwright MCP.
Backend tests isolate their data and databases; they do not create RFIs in the
running application's sample dataset. Project 999 remains nonexistent.

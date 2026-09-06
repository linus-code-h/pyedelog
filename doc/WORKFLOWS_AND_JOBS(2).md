# EDELOG Workflows and Jobs

## What this guide is used for

Use this guide to implement server-side automation that runs inside EDELOG. It covers event-driven workflows,
user-triggered workflow actions, and scheduled jobs, including the runtime context and Data API calls available to
custom JavaScript steps.

## How it is used in general

Create a workflow when an EDELOG event or user action should trigger code. Create a job when code should run on a
schedule and query records itself. EDELOG supplies the execution context and bearer token, so these automations do not
need their own OAuth client or separately deployed backend.

Use a [backend-only custom app](<ACCES_WITH_CUSTOM_APP(1).md>) when the logic needs its own deployment or broad interactive
API access. Use the [Data Sync API](<DATA_SYNC_API(1).md>) when an external system should submit write-oriented batches.

## Choose the Execution Model

| Model | Use it for | Available context |
| --- | --- | --- |
| Record workflow | Reacting to record creation or changes | Trigger record, changed fields, target database |
| Manual workflow / quick action | User-triggered operations with configured inputs | Action inputs and the triggering context |
| Interval job | Periodic checks, cleanup and reconciliation | Schedule inputs; records must be queried explicitly |

Typical examples:

- Recalculate a derived value after a source field changes: record workflow.
- Create records from a user-selected template: manual workflow.
- Find overdue records every night: interval job.

## Configure the Automation

For a record workflow:

1. Select the target database.
2. Add `data-record-created`, `data-record-updated`, or both as triggers.
3. Add a user-defined JavaScript step and map any required trigger outputs.
4. Save it and test it with one record before enabling it broadly.

For a scheduled job, create an `interval-based` schedule in the Jobs app. Set
its start date, interval, execution days and optional end date, then add the
schedule inputs and workflow steps. The JavaScript step receives schedule input
values through `inputs` but must query any database records it needs.

## Runtime API

Custom JavaScript runs as an async function with `inputs` and `environment`.
`input` is a legacy alias for `inputs`, and individual input names are also
available as globals. Prefer `inputs` in new code.

The most useful environment fields are:

```js
const baseUrl = environment.apiInternalBaseUrl.replace(/\/$/, "");
const jwt = environment.jwt;
const targetDatabaseId = environment.workflowTargetId;

const event = environment.payload?.event ?? {};
const record = event.data ?? {};
const changes = event.metadata?.changes ?? [];
```

- `apiInternalBaseUrl`: base URL for calls from the workflow runtime.
- `jwt`: token for the workflow's current or technical user.
- `workflowTargetId`: database UUID configured as the workflow target.
- `payload.event`: output of the trigger step.
- `inputs`: values configured or mapped for the current step.

Scheduled jobs normally do not have a triggering record. Do not depend on
`environment.payload.event.data` in an interval job.

## API Helper

The following helper is suitable for both workflows and jobs:

```js
const baseUrl = environment.apiInternalBaseUrl.replace(/\/$/, "");
const authHeaders = {
    Authorization: `Bearer ${environment.jwt}`,
};

const requestJson = async (path, options = {}) => {
    const response = await fetch(`${baseUrl}${path}`, {
        ...options,
        headers: {
            ...authHeaders,
            ...options.headers,
        },
    });

    if (!response.ok) {
        const body = await response.text();
        throw new Error(
            `${options.method ?? "GET"} ${path} failed: ${response.status}` +
            (body ? ` ${body}` : "")
        );
    }

    return response.status === 204 ? null : response.json();
};

const writeRecord = async (method, databaseId, recordId, values) => {
    const body = new FormData();
    body.append("data", JSON.stringify(values));

    const suffix = recordId ? `/${recordId}` : "";
    return requestJson(`/api/v4/data_types/${databaseId}/data${suffix}`, {
        method,
        body,
    });
};
```

Create and update records with:

```js
const created = await writeRecord("POST", databaseId, null, {
    title: "New record",
    status: "open",
});

await writeRecord("PUT", databaseId, recordId, {
    status: "done",
});
```

`PUT` accepts a partial set of column values. Always use technical column
names and values that match the configured column schema.

## Read Records with Pagination

Always paginate scheduled scans and select only the columns the job needs.
`viewOption=listable` excludes archived records.

```js
const findAll = async (databaseId, fields, filterStatement = null) => {
    const records = [];
    const limit = 200;

    for (let page = 1; ; page += 1) {
        const params = new URLSearchParams({
            limit: String(limit),
            page: String(page),
            select: fields.join(","),
            viewOption: "listable",
        });
        if (filterStatement) {
            params.set("filterStatement", filterStatement);
        }

        const result = await requestJson(
            `/api/v4/data_types/${databaseId}/data?${params}`
        );
        const pageRecords = result.data ?? [];
        records.push(...pageRecords);

        if (pageRecords.length < limit) break;
    }

    return records;
};
```

Example filter:

```js
const filterStatement = JSON.stringify({
    $and: [
        `status:eq:${JSON.stringify("open")}`,
        `due_date:lte:${JSON.stringify("2026-08-17")}`,
    ],
});
```

## Record Workflow Guard

An update made by a workflow can trigger the same workflow again. Exit before
writing when no relevant source field changed or the target value is already
correct.

```js
const record = environment.payload?.event?.data ?? {};
const changedFields = new Set(
    (environment.payload?.event?.metadata?.changes ?? [])
        .map(change => change?.name)
        .filter(Boolean)
);

const relevantFields = ["start_date", "end_date"];
if (
    changedFields.size > 0 &&
    !relevantFields.some(field => changedFields.has(field))
) {
    return;
}

const expectedDuration = calculateDuration(record);
if (Number(record.duration) === expectedDuration) return;

await writeRecord(
    "PUT",
    environment.workflowTargetId,
    record.id,
    {duration: expectedDuration}
);
```

## Reliability Rules

Treat every workflow and job as repeatable. Runs can be retried, schedules can
be duplicated and a previous run may have completed only some operations.

1. Before creating a record, query for a stable business key and skip or update
   the existing record.
2. Before updating, compare the current and expected values.
3. Limit record workflows to relevant changed fields to prevent update loops.
4. Use `viewOption=listable` unless archived records are explicitly required.
5. Use UTC operations for date-only values and write them as `YYYY-MM-DD`.
6. Check every HTTP response and include its body in errors.
7. Log a compact summary with checked, created, updated, skipped and failed
   counts. Never log the JWT or personal data unnecessarily.
8. Do not assume deleting a source record removes an independently created job
   schedule. Clean up record-bound schedules explicitly.

The header `Edelog-No-Enforced-Filters: 1` bypasses database-enforced filters.
Only add it to a technical-user request when the automation intentionally needs
organization-wide access.

## Verification Checklist

1. Test with one known record and inspect the workflow run output.
2. Run the same input twice and confirm the second run creates no duplicates.
3. Test missing links, missing dates and already-correct values.
4. For jobs, test more than one API page and archived records.
5. Confirm that a workflow's own update does not start an endless loop.
6. Review the next scheduled run and the completed-run log in the Jobs app.

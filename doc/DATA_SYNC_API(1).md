# EDELOG Data Sync API

## What this guide is used for

Use this guide when an external system needs to submit create, update, or delete operations to authorized EDELOG
databases as an asynchronous batch. It documents Data Sync Service registration, authentication, payload structure,
upserts, deletes, relationship resolution, reconciliation, and job errors.

## How it is used in general

An EDELOG administrator registers a Data Sync Service, selects the databases it may access, and gives the external
system a service ID and access key. The external system builds a complete version-1 JSON payload and submits it to the
Data Sync jobs endpoint. EDELOG queues the request and processes its ordered database collections asynchronously.

The API is independent of the external system's storage technology. The caller may be an ERP, CRM, integration
platform, scheduled script, or another service. It is primarily a write API: internal select statements can locate
records and relationships, but they do not return arbitrary query results to the caller.

Use a [backend-only custom app](<ACCES_WITH_CUSTOM_APP(1).md>) instead when the external service needs general-purpose reads
or interactive Data API access. Use [workflows and jobs](<WORKFLOWS_AND_JOBS(2).md>) when the automation should run inside
EDELOG.

The Data Sync API does not require a custom app. Its service ID and access key are separate from custom-app OAuth
credentials.

## 1. Concepts

| Term | Meaning |
| --- | --- |
| External service | The system sending data to EDELOG |
| Data Sync Service | A registered EDELOG integration with an ID, access key, and an allowlist of databases |
| Data Sync Request | One complete JSON document describing the desired changes |
| Data Sync Job | The asynchronous EDELOG job created from a submitted request |
| Database | An EDELOG data collection identified by its technical name |
| Field | A column in an EDELOG database, identified by its technical name |

The API is write-oriented. It can read EDELOG records internally to find update targets or resolve relationships, but it is not a general query API and does not return arbitrary database records to the caller.

## 2. Registration and credentials

An EDELOG administrator must register the external service as a Data Sync Service and configure which EDELOG databases it may access.

The administrator provides:

- the EDELOG base URL, such as `https://edelog.example.com`;
- a Data Sync Service ID;
- an access key; and
- the allowed database and field technical names.

The service can reference only its allowed databases. A request that targets or selects from another database fails during job execution.

Protect the access key like a password:

- store it in a secret manager;
- send it only over HTTPS;
- never place it in source control or logs; and
- rotate or deactivate it when compromised.

## 3. Submit a sync job

```text
POST /api/v4/sync_services/{DATA_SYNC_SERVICE_ID}/jobs
Authorization: Bearer {ACCESS_KEY}
```

Encode the request body as `multipart/form-data` or `application/x-www-form-urlencoded`. It must contain a field named `requestPayload`. The field value is the complete sync request serialized as JSON.

Example:

```bash
curl --fail-with-body \
  --request POST \
  --header 'Authorization: Bearer <access-key>' \
  --form 'requestPayload=<payload.json' \
  'https://edelog.example.com/api/v4/sync_services/<service-id>/jobs'
```

A successful submission returns HTTP `201 Created` with a job preview similar to:

```json
{
  "success": true,
  "data": {
    "_objectType": "sync-service-job",
    "id": "4a84f0ae-6225-4b23-a230-9efc9c7f3d90",
    "status": "enqueued",
    "createdAt": "2026-08-17T10:00:00Z",
    "updatedAt": "2026-08-17T10:00:00Z"
  }
}
```

`201 Created` means that EDELOG accepted and enqueued the job. It does **not** mean that the data changes have completed. Payload validation and database operations happen asynchronously.

If the service ID is unknown, inactive, or does not match the access key, the endpoint may return `404 Not Found` without revealing which credential was incorrect.

## 4. Request structure

Every request uses schema version `1` and contains one or more update collections:

```json
{
  "version": 1,
  "updateCollections": [
    {
      "databaseName": "customers",
      "tasks": [],
      "performOnNotMatchedRecords": "skip"
    }
  ]
}
```

An update collection targets exactly one EDELOG database. Collections execute in array order, and their tasks execute in array order.

All object properties are schema-controlled. Unknown properties, missing required properties, unsupported values, or a version other than `1` cause the asynchronous job to fail validation.

### Supported values

A normal field or filter value may be:

- `null`;
- a string;
- a number;
- a boolean; or
- an array of strings.

Send dates and timestamps in the string format required by the target EDELOG field, normally an ISO 8601 string. Confirm field types and allowed values with the EDELOG administrator.

## 5. Selecting records with `where`

Every update or delete task contains a `where` object:

```json
{
  "where": {
    "external_id": "CRM-4711",
    "status": "active"
  }
}
```

Selection rules:

- multiple conditions are combined with logical `AND`;
- an array value performs an `IN` match;
- every matching record is affected, not only the first record; and
- an empty `where` can match the entire database and must be avoided unless that is explicitly intended.

Use a stable, unique external key whenever possible. If the selected fields are not unique, one task can update or delete multiple records.

## 6. Update tasks

An update task has `type: "update-data"`:

```json
{
  "type": "update-data",
  "where": {
    "external_id": "CRM-4711"
  },
  "update": {
    "external_id": "CRM-4711",
    "name": "Example Customer",
    "active": true
  },
  "ifNotFound": "create-new"
}
```

Only fields present in `update` are written. Other fields on an existing record remain unchanged.

`ifNotFound` controls what happens when `where` matches no record:

| Value | Behavior |
| --- | --- |
| `skip` | Do nothing and continue the job |
| `throw-error` | Fail the job with a record-not-found error |
| `create-new` | Create a record and apply the `update` values |

When using `create-new`, values from `where` are **not automatically copied** to the new record. Include the external key and every required field in `update`.

## 7. Delete tasks

A delete task has `type: "delete-data"`:

```json
{
  "type": "delete-data",
  "where": {
    "external_id": "CRM-4711"
  },
  "ifNotFound": "skip"
}
```

Delete tasks support these `ifNotFound` values:

| Value | Behavior |
| --- | --- |
| `skip` | Continue if no record matches |
| `throw-error` | Fail if no record matches |

`create-new` is not valid for a delete task.

## 8. Reading values and resolving relationships

A field in `update` may contain a select statement instead of a static value. EDELOG executes the select internally and writes the selected value or values into the target field.

Example: connect a customer to a country record:

```json
{
  "type": "update-data",
  "where": {
    "external_id": "CRM-4711"
  },
  "update": {
    "external_id": "CRM-4711",
    "name": "Example Customer",
    "country": {
      "databaseName": "countries",
      "select": "id",
      "where": {
        "iso_code": "DE"
      },
      "returnFirstRecord": true
    }
  },
  "ifNotFound": "create-new"
}
```

A select statement contains:

| Property | Meaning |
| --- | --- |
| `databaseName` | Technical name of the database to read |
| `select` | Technical name of the field whose value is needed |
| `where` | Conditions combined with logical `AND` |
| `returnFirstRecord` | Optional; `false` by default |

Without `returnFirstRecord`, EDELOG writes an array containing the selected values. With `returnFirstRecord: true`, it writes the first selected value, or an empty value if nothing matched. Use `true` for single-record relationships and leave it `false` for collection relationships.

The selected database must normally be assigned to the same Data Sync Service.

### Organizational-unit lookup

Update values may also select from `system/organizational_units`. This is useful for references to EDELOG users and groups.

```json
{
  "owner": {
    "databaseName": "system/organizational_units",
    "select": "id",
    "where": {
      "email": "owner@example.com",
      "type": "User"
    },
    "returnFirstRecord": true
  }
}
```

Selectable fields are `id`, `fqn`, `email`, `display_name`, `first_name`, `last_name`, `type`, `created_at`, `updated_at`, and `app_id`. Filterable fields are `id`, `fqn`, `email`, `display_name`, `first_name`, `last_name`, and `type`.

Allowed `type` values are `User`, `RestrictedUser`, `TechnicalUser`, `Group`, and `DynamicGroup`.

## 9. Handling records not matched by the collection

After all tasks in a collection have run, EDELOG identifies records in the target database that were not selected by any task in that collection. `performOnNotMatchedRecords` controls what happens to them:

| Value | Behavior |
| --- | --- |
| `skip` | Leave unmatched records unchanged |
| `throw-error` | Fail if any target record was not matched |
| `delete` | Delete every unmatched record in the target database |

For ordinary incremental updates, use `skip`.

Use `delete` only for an authoritative full snapshot. It applies to the entire target database, not merely to records created by the caller. An empty task array combined with `delete` deletes every record in the database.

Additional safety rules:

- preview and count the complete source snapshot before using `delete`;
- do not split one authoritative database snapshot across multiple collections;
- avoid multiple reconciliation collections for the same database in one job; and
- test with `throw-error` before changing the action to `delete`.

## 10. Job processing and errors

EDELOG processes submitted jobs asynchronously. A job can have one of these states:

- `enqueued`;
- `processing`;
- `completed`; or
- `failed`.

EDELOG administrators can inspect job history, request payloads, result protocols, and failures in the Data Sync Service settings. Administrators are notified when execution fails.

Common failure categories include:

| Error | Meaning |
| --- | --- |
| Request payload is invalid | The JSON does not match schema version 1 |
| `reference-to-disallowed-database` | The service is not allowed to use the named database |
| `record-not-found` | A task used `ifNotFound: "throw-error"` and found nothing |
| `not-matched-records` | A collection used `throw-error` and left records unmatched |
| `reference-to-disallowed-field` | A system lookup used a field that is not exposed |
| `unknown-error` | An unexpected execution or data-validation error occurred |

Design requests to be idempotent: repeating the same request should lead to the same result. Use stable external IDs and upserts so a caller can safely retry after a network failure or uncertain job outcome.

Do not send a dependent job merely because the preceding submission returned `201`; wait until the preceding job is confirmed as completed through the operational process agreed with the EDELOG administrator.

## 11. Report an external synchronization error

An external service can create a failed job entry when it cannot build or submit normal sync data—for example, when its source system is unavailable.

```text
POST /api/v4/sync_services/{DATA_SYNC_SERVICE_ID}/jobs/error
Authorization: Bearer {ACCESS_KEY}
```

Send `errorMessage` as `multipart/form-data` or `application/x-www-form-urlencoded`:

```bash
curl --fail-with-body \
  --request POST \
  --header 'Authorization: Bearer <access-key>' \
  --form 'errorMessage=Source system was unavailable' \
  'https://edelog.example.com/api/v4/sync_services/<service-id>/jobs/error'
```

EDELOG stores the message as a failed sync job and makes it visible to administrators.

## 12. Schema reference

```typescript
type ColumnValue = null | string | number | boolean | string[];

interface DataSyncRequestBody {
  version: 1;
  updateCollections: DatabaseUpdateCollection[];
}

interface DatabaseUpdateCollection {
  databaseName: string;
  tasks: Array<UpdateTask | DeleteTask>;
  performOnNotMatchedRecords: 'skip' | 'throw-error' | 'delete';
}

interface DataSelectStatement {
  databaseName: string;
  select: string;
  where: Record<string, ColumnValue>;
  returnFirstRecord?: boolean;
}

interface UpdateTask {
  type: 'update-data';
  where: Record<string, ColumnValue | DataSelectStatement>;
  update: Record<string, ColumnValue | DataSelectStatement>;
  ifNotFound: 'skip' | 'throw-error' | 'create-new';
}

interface DeleteTask {
  type: 'delete-data';
  where: Record<string, ColumnValue | DataSelectStatement>;
  ifNotFound: 'skip' | 'throw-error';
}
```

## 13. Complete minimal example

This example creates or updates one customer using only an HTTP request. The names `customers`, `external_id`, `name`,
and `email` are examples; replace them with the technical names supplied by the EDELOG administrator.

Save the following as `payload.json`:

```json
{
  "version": 1,
  "updateCollections": [
    {
      "databaseName": "customers",
      "tasks": [
        {
          "type": "update-data",
          "where": {
            "external_id": "CRM-4711"
          },
          "update": {
            "external_id": "CRM-4711",
            "name": "Example Customer",
            "email": "contact@example.com"
          },
          "ifNotFound": "create-new"
        }
      ],
      "performOnNotMatchedRecords": "skip"
    }
  ]
}
```

Submit it:

```bash
curl --fail-with-body \
  --request POST \
  --header 'Authorization: Bearer <access-key>' \
  --form 'requestPayload=<payload.json' \
  'https://edelog.example.com/api/v4/sync_services/<service-id>/jobs'
```

The request is an idempotent upsert:

- if `external_id = "CRM-4711"` exists, EDELOG updates its name and email;
- if it does not exist, EDELOG creates a record from the `update` values; and
- all other customer records remain unchanged because `performOnNotMatchedRecords` is `skip`.

EDELOG returns the `201 Created` job preview shown in section 3. The response confirms that the job is enqueued, not
that it has completed. Keep the returned job ID for operational verification with the EDELOG administrator.

To publish a later change, submit the same stable external ID with new values in `update`. Retrying the same payload
does not blindly create another record because `where` finds the existing external ID.

## 14. Integration checklist

- [ ] An administrator registered the Data Sync Service.
- [ ] The service is active and allowlisted for every referenced database.
- [ ] The caller has the base URL, service ID, access key, and technical field names.
- [ ] Every upsert uses a stable and unique external key.
- [ ] Every `create-new` update includes its key and all required fields.
- [ ] Relationship selects return the scalar or array type expected by the target field.
- [ ] Normal incremental collections use `performOnNotMatchedRecords: "skip"`.
- [ ] Any reconciliation using `delete` has been reviewed as an authoritative full snapshot.
- [ ] The caller treats `201` as enqueued, not completed.
- [ ] Retries are idempotent and secrets are not logged.
- [ ] A process exists for reviewing failed jobs with an EDELOG administrator.

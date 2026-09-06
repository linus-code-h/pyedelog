# Backend-Only Custom App Data Access

## What this guide is used for

Use this guide to connect a trusted backend service directly to the EDELOG Data API. The backend authenticates through
an installed custom app and acts as that app's technical user. It can then query, create, and update records according
to the permissions approved for the app installation.

An EDELOG custom app does not need an Angular frontend or an app view. A custom app can exist only to provide OAuth
credentials, a technical-user identity, and a narrowly defined permission boundary for an external backend.

## How it is used in general

The general flow is:

1. An EDELOG administrator creates a custom app.
2. The app developer declares the API permissions the backend requires.
3. The developer enables the OAuth `client-credentials` grant.
4. An administrator installs the app in the target organization and approves its requested permissions.
5. The backend exchanges the app's client credentials and organization ID for an access token.
6. EDELOG creates or reuses the app's technical user and limits the token to the installation's approved permissions.
7. The backend calls `/api/v4` with that bearer token.

Use this approach for a continuously deployed service that needs general record reads as well as writes. For
write-oriented bulk synchronization, consider the [EDELOG Data Sync API](<DATA_SYNC_API(1).md>). For code that should run
inside EDELOG in response to events or schedules, see [EDELOG Workflows and Jobs](<WORKFLOWS_AND_JOBS(2).md>).

A custom app's OAuth client ID and secret are different from a Data Sync Service ID and access key. Do not interchange
the two authentication methods.

## Set up the custom app in EDELOG

The labels below refer to the current EDELOG app-management UI. An organization administrator is required to create
and install an app and to approve its permissions.

### 1. Create the app

1. Open **Apps** and choose **Manage Apps**.
2. Select the add (`+`) action and then **Create New App**.
3. Enter a unique technical name, preferably reverse-domain notation such as `com.example.integration`.
4. Enter a human-readable title and create the app.

Choose the technical name carefully. It identifies the app and its application scope and cannot be changed from the
normal app settings after creation.

No app view is required for a backend-only integration.

### 2. Request the API permissions

Open the new app, then go to **Developer Settings → App Capabilities → API Permissions**. Add only the capabilities
the backend needs and save them.

Common permission names are:

| Operation | Permission |
| --- | --- |
| Create the app's technical user | `Edelog:IAM:CreateTechnicalUser` |
| Resolve/read a database | `Edelog:DataLayer:Database:Show` |
| List/read records | `Edelog:DataLayer:DataRecord:Show` |
| Create records | `Edelog:DataLayer:Database:CreateRecord` |
| Update records | `Edelog:DataLayer:DataRecord:Update` |
| Delete records, if required | `Edelog:DataLayer:DataRecord:Destroy` |
| Read column values | `Edelog:DataLayer:DatabaseColumn:ShowValue` |
| Write column values | `Edelog:DataLayer:DatabaseColumn:UpdateValue` |

Grant only the permissions and database scope the app needs.

For permissions that offer a scope choice:

- **App Sandbox** limits access to resources in the app's own scope.
- **Global** permits organization-wide access for that capability.

A backend that must read existing organization data generally needs the relevant Data Layer capabilities approved as
**Global**. Prefer **App Sandbox** when the integration only manages resources belonging to its own app context.

### 3. Enable client-credentials authentication

Open **Developer Settings → OAuth**:

1. Enable **Client Credentials** in the supported grants table.
2. Save the OAuth settings.
3. Copy the displayed client ID and client secret into an approved secret manager.

The client ID is the app ID. The client secret must never be embedded in browser or mobile code. If it is exposed,
stop using it and coordinate credential replacement with an EDELOG administrator.

### 4. Install the app and approve its permissions

Open **Installation → Add Installation**, choose **Install App Locally**, review the requested capabilities, and approve
the installation.

If the app was already installed before new capabilities were requested, open the installation again and approve the
pending permission upgrade. Until pending permissions are approved, token or API access may fail with a permission
upgrade error.

The installation is organization-specific. Repeat this step in every organization where the backend should operate.
Each token request must name an organization in which the app is installed.

### 5. Prepare the backend configuration

Collect the following values:

- the EDELOG base URL;
- the OAuth client ID;
- the OAuth client secret;
- the target organization UUID; and
- the UUIDs or technical names of the databases and columns the backend uses.

The first successful client-credentials request creates the app's technical user for that organization if it does not
already exist. This requires the approved `Edelog:IAM:CreateTechnicalUser` capability.

## Configuration Values

Keep these values in deployment secrets, not source control:

```text
EDELOG_BASE_URL=https://core.example.edelog.com
EDELOG_CLIENT_ID=<app client id>
EDELOG_CLIENT_SECRET=<app client secret>
EDELOG_ORGANIZATION_ID=<organization uuid>
```

Never expose `EDELOG_CLIENT_SECRET` in browser code. Client credentials are for a trusted backend process only.

## Obtain an Access Token

Request a token for the app installation and organization:

```js
const getAccessToken = async () => {
    const url = new URL("/oauth/token", process.env.EDELOG_BASE_URL);
    const body = new URLSearchParams({
        grant_type: "client_credentials",
        client_id: process.env.EDELOG_CLIENT_ID,
        client_secret: process.env.EDELOG_CLIENT_SECRET,
        organization_id: process.env.EDELOG_ORGANIZATION_ID,
    });

    const response = await fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/x-www-form-urlencoded",
        },
        body,
    });

    if (!response.ok) {
        throw new Error(`OAuth failed: ${response.status} ${await response.text()}`);
    }

    return (await response.json()).access_token;
};
```

The token belongs to the app's technical user in the selected organization. Its access is limited by the permissions
granted to that app installation.

## Minimal Data Client

This example works on Node.js 20 or newer and requires no additional package:

```js
const baseUrl = process.env.EDELOG_BASE_URL.replace(/\/$/, "");

const createClient = accessToken => {
    const requestJson = async (path, options = {}) => {
        const response = await fetch(`${baseUrl}${path}`, {
            ...options,
            headers: {
                Authorization: `Bearer ${accessToken}`,
                ...options.headers,
            },
        });

        if (!response.ok) {
            const body = await response.text();
            throw new Error(
                `${options.method ?? "GET"} ${path} failed: ` +
                `${response.status}${body ? ` ${body}` : ""}`
            );
        }

        return response.status === 204 ? null : response.json();
    };

    const getRecord = async (databaseId, recordId, fields = []) => {
        const params = new URLSearchParams();
        if (fields.length) params.set("select", fields.join(","));
        const query = params.size ? `?${params}` : "";

        const result = await requestJson(
            `/api/v4/data_types/${databaseId}/data/${recordId}/payload${query}`
        );
        return result.data ?? null;
    };

    const listRecords = async (
        databaseId,
        {fields = [], filterStatement = null, viewOption = "listable"} = {}
    ) => {
        const all = [];
        const limit = 200;

        for (let page = 1; ; page += 1) {
            const params = new URLSearchParams({
                limit: String(limit),
                page: String(page),
                viewOption,
            });
            if (fields.length) params.set("select", fields.join(","));
            if (filterStatement) {
                params.set("filterStatement", filterStatement);
            }

            const result = await requestJson(
                `/api/v4/data_types/${databaseId}/data?${params}`
            );
            const records = result.data ?? [];
            all.push(...records);
            if (records.length < limit) break;
        }

        return all;
    };

    const writeRecord = async (method, databaseId, recordId, values) => {
        const form = new FormData();
        form.append("data", JSON.stringify(values));
        const suffix = recordId ? `/${recordId}` : "";

        return requestJson(`/api/v4/data_types/${databaseId}/data${suffix}`, {
            method,
            body: form,
        });
    };

    return {
        getRecord,
        listRecords,
        createRecord: (databaseId, values) =>
            writeRecord("POST", databaseId, null, values),
        updateRecord: (databaseId, recordId, values) =>
            writeRecord("PUT", databaseId, recordId, values),
    };
};
```

Usage:

```js
const token = await getAccessToken();
const edelog = createClient(token);

const employees = await edelog.listRecords(EMPLOYEES_DATABASE_ID, {
    fields: ["id", "first_name", "family_name", "personnel_number"],
});

const created = await edelog.createRecord(TASKS_DATABASE_ID, {
    title: "Review employee data",
    status: "open",
    targets: [employees[0].id],
});

await edelog.updateRecord(TASKS_DATABASE_ID, created.data.id, {
    status: "done",
});
```

## Resolve a Database by Technical Name

Prefer stable database UUIDs in production configuration. During setup, a UUID can be resolved from the technical name:

```js
const result = await requestJson(
    "/api/v4/data_types?includeHidden=1&limit=200"
);
const database = (result.data ?? []).find(item => item.name === "employees");
if (!database) throw new Error('Database "employees" not found');
```

Do not resolve databases by translated titles.

## Data Shapes

- Use technical column names, not labels shown in the UI.
- Date-only columns should normally be written as `YYYY-MM-DD`.
- Link columns normally contain record or organizational-unit UUIDs; multi-link columns use arrays of UUIDs.
- JSON columns must match the column's configured JSON schema. Do not invent a parallel JSON shape in the client.
- Record collections use their child-record endpoints and should not be flattened into the parent record payload.
- `viewOption=listable` returns active, non-archived records. Use
  `viewOption=archive` for archived records. Query both views separately if both are required.

## Production Checklist

1. Store the client secret in the deployment secret manager.
2. Request a new token at startup and again after an authentication failure.
3. Use timeouts and bounded retries for network or `5xx` failures; do not retry validation errors indefinitely.
4. Make creates idempotent by looking up a stable external ID before writing.
5. Paginate list requests and select only required columns.
6. Validate outbound values before writing and fail on non-2xx responses.
7. Log record IDs and summary counts, but not tokens or unnecessary personal data.
8. Test with a dedicated organization or a narrowly scoped app installation before enabling writes in production.

# pyedelog

## Für den Start mit EDELOG Data Sync

Wenn du Daten aus einem Python-Programm nach EDELOG schreiben willst, lies zuerst
die deutschsprachige [Data-Sync-Anleitung für Einsteiger](<doc/DATA_SYNC_EINSTIEG_DE.md>).
Sie erklärt die Einrichtung, ein vollständiges Beispiel und das Prüfen der Jobs.
Für diesen Weg brauchst du keine Custom App und keinen OAuth-Zugang.

Die eincheckbare Konfigurationsvorlage ist [.env.example](.env.example). Echte
Service-ID und Secret Key stellt ein EDELOG-Administrator aus; sie gehören nur in
die lokal ignorierte Datei `.env.local`.

Synchroner Python-Client für die EDELOG Data API und Data Sync API, ab Python 3.10.
Die Library bietet OAuth-Anmeldung, Datensatzzugriff, paginierte Abfragen und
validierte Sync-Aufträge. Workflows und Jobs innerhalb von EDELOG führen JavaScript
aus und sind kein Bestandteil dieses Python-Clients.

Der Stand ist eine **0.x-Version**. Lokale Tests ersetzen keinen Integrationstest
gegen die eingesetzte EDELOG-Version. Details zum Verhalten und zur Freigabe stehen
in [Library-Vertrag und Tests](doc/LIBRARY.md).

## Installation

Aus diesem Repository:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install .
```

Der Distributionsname ist `pyedelog`; importiert wird `edelog`.

## Data API: Anmeldung und Lesen

Ein Administrator muss die Custom App installieren, ihre Berechtigungen genehmigen
und den Client-Credentials-Grant aktivieren. Siehe
[Custom-App-Anleitung](<doc/ACCES_WITH_CUSTOM_APP(1).md>).

Diese Umgebungsvariablen über die lokale Umgebung oder den Secret Manager setzen:

- `EDELOG_BASE_URL`: Basis-URL der EDELOG-Instanz
- `EDELOG_CLIENT_ID`: OAuth-Client-ID
- `EDELOG_CLIENT_SECRET`: OAuth-Secret
- `EDELOG_ORGANIZATION_ID`: Organisations-UUID

`.env`-Dateien werden nicht automatisch geladen. Für echte Verbindungen HTTPS verwenden.

```python
from edelog import Edelog

with Edelog.from_env() as edelog:
    customers = edelog.data.database("customers")
    records = customers.list(fields=["id", "name"])
    for record in records:
        print(record["id"])
```

`database("customers")` löst den technischen Namen paginiert auf und speichert die
UUID für dieses Database-Objekt. UUIDs können direkt mit
`edelog.data.list_records(database_id="...")` verwendet werden.
`list()` liest alle Seiten in den Speicher. Für große Abfragen:

```python
with Edelog.from_env() as edelog:
    for record in edelog.data.database("customers").iter_records(fields=["id"]):
        print(record["id"])
```

Standardmäßig gilt `view_option="listable"` für nicht archivierte Datensätze.
Archivierte Datensätze werden separat mit `view_option="archive"` abgefragt.
Filter werden als `filter_statement` unverändert weitergegeben:

```python
import json

filter_statement = json.dumps({"$and": [f"status:eq:{json.dumps('open')}"]})
```

## Erstellen und Aktualisieren

```python
with Edelog.from_env() as edelog:
    customers = edelog.data.database("customers")
    result = customers.create({"external_id": "CRM-4711", "name": "Beispiel"})
    if result is not None:
        record_id = result["data"]["id"]
        customers.update(record_id, {"name": "Neuer Name"})
```

Technische Spaltennamen verwenden. Datumswerte als `YYYY-MM-DD`, Verknüpfungen als
UUID bzw. Liste von UUIDs senden. Die Library kennt das organisationsspezifische
Spaltenschema nicht; dessen Prüfung bleibt bei Anwendung und Server.

`get()` liefert einen Datensatz oder `None`, `list()` eine Liste.
`create()` und `update()` liefern zur Wahrung der bisherigen API die vollständige
JSON-Antwort, bei HTTP 204 `None`. Ein HTTP 404 löst `ApiError` aus.
Ein normales `create()` ist kein Upsert und verhindert keine Duplikate.

## Data Sync: unabhängige Anmeldung

Sync verwendet **Service-ID und Zugriffsschlüssel**, keine OAuth-Anmeldung.
Zusätzlich zur Basis-URL werden `EDELOG_SYNC_SERVICE_ID` und
`EDELOG_SYNC_ACCESS_KEY` benötigt. Siehe [Data-Sync-Anleitung](<doc/DATA_SYNC_API(1).md>).

```python
from edelog import DataSyncClient, DataSyncConfig, SyncRequest, select

request = SyncRequest()
request.database("customers").upsert(
    where={"external_id": "CRM-4711"},
    values={
        "external_id": "CRM-4711",
        "name": "Beispiel",
        "country": select("countries", "id", {"iso_code": "DE"}, first=True),
    },
)

with DataSyncClient(DataSyncConfig.from_env()) as sync:
    result = sync.submit(request)
    job_id = result["data"]["id"]
    status = result["data"]["status"]
```

Die Antwort beschreibt einen **asynchronen Job**. `enqueued` bedeutet angenommen,
noch nicht verarbeitet. Job-ID aufbewahren und den Abschluss mit dem Administrator
in der Sync-Verwaltung prüfen. Ein Status-Polling-Endpunkt ist in der vorliegenden
Anleitung nicht dokumentiert und wird von der Library nicht erfunden.

- `upsert(where, values)` erstellt bei fehlendem Treffer. Schlüssel aus `where`
  werden **nicht** automatisch in neue Datensätze übernommen; in `values` mitgeben.
- `update(..., if_not_found="throw-error")` und `delete(..., if_not_found="throw-error")`
  lassen fehlende Treffer den Job abbrechen; Standard ist jeweils `skip`.
- Stabile, eindeutige externe Schlüssel verwenden. Ein Filter kann mehrere Treffer haben.
- Normale Collections verwenden `perform_on_not_matched_records="skip"`.
- `delete` als Collection-Aktion löscht alle nicht getroffenen Datensätze der
  Ziel-Datenbank. Nur für vollständige, autoritative Snapshots verwenden.
  Leere Lösch-Snapshots und mehrere Collections derselben Datenbank bei
  Reconciliation (`delete`/`throw-error`) werden abgelehnt.
- Leere `where`-Filter werden bewusst auch in Select-Ausdrücken abgelehnt.

Ein externer Fehler lässt sich mit `sync.report_error("Quellsystem nicht erreichbar")`
als fehlgeschlagener Job melden. Optional bietet `Edelog.from_env(with_sync=True)`
beide Zugänge gemeinsam; dafür sind beide Zugangskonfigurationen erforderlich.

## Fehler und Wiederholungen

```python
from edelog import ApiError, EdelogError, TransportError

try:
    with Edelog.from_env() as edelog:
        records = edelog.data.list_records("database-uuid", fields=["id"])
except TransportError:
    # Bei Schreibzugriffen vor einem neuen Versuch den tatsächlichen Zustand prüfen.
    raise
except ApiError as error:
    print(f"EDELOG HTTP-Status: {error.status_code}")
except EdelogError:
    # Beispielsweise ungültige Serverantwort oder fehlgeschlagene Anmeldung.
    raise
```

Nur GET, HEAD und OPTIONS werden bei Netzwerkfehlern oder HTTP 5xx automatisch
wiederholt: standardmäßig höchstens zwei Wiederholungen mit exponentieller Pause
(0,5 s, 1 s; einzelne Pausen maximal 60 s). Andere HTTP-Fehler einschließlich 429
werden unmittelbar gemeldet. `max_retries=0` deaktiviert Wiederholungen.

POST und PUT sowie Sync-Einreichungen und Fehlermeldungen werden nach Netzwerk-
oder Serverfehlern **nicht automatisch wiederholt**. Ein verlorener Response kann
einen bereits ausgeführten Schreibvorgang verbergen. Die Data API erneuert bei 401
einmal das Token und versucht den abgelehnten Aufruf erneut; ein zweites 401 bricht ab.
OAuth-Tokenanfragen werden nicht automatisch wiederholt.

HTTP-Clients immer per `with` oder `close()` schließen. Selbst erzeugte Clients
gehören der Library; injizierte `httpx.Client`-Instanzen schließt der Aufrufer.
Konfigurationsdarstellungen blenden Secrets aus. API-Fehlertexte können fachliche
Daten enthalten; Fehler nicht ungeprüft öffentlich protokollieren.

## Entwicklung und Prüfung

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m build
```

Die Tests arbeiten mit simulierten HTTP-Antworten und benötigen keine Zugangsdaten.
Die manuellen Verbindungsskripte unter `examples/` führen ausschließlich Anmeldung
bzw. Lesezugriffe durch. Release- und Integrationstestschritte stehen in
[doc/LIBRARY.md](doc/LIBRARY.md).

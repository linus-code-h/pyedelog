# Library-Vertrag und Stabilitätsprüfung

## Umfang und öffentliche API

`edelog` exportiert `Edelog`, `EdelogConfig`, `EdelogAuth`, `DataSyncClient`,
`DataSyncConfig`, `SyncRequest`, `SyncCollection`, `select` und die Fehlerklassen.
`edelog.data` exportiert zusätzlich `DataClient` und `Database`.
Die API ist synchron. Async-Clients, Workflow-Ausführung und ein allgemeines ORM
sind nicht Teil dieses Standes. Die Anleitung zu
[Workflows und Jobs](<WORKFLOWS_AND_JOBS(2).md>) beschreibt die serverseitige Alternative.

| Aufruf | Ergebnis |
| --- | --- |
| `data.get_record(...)` / `database.get(...)` | Datensatz-Dictionary oder `None` bei JSON `data: null`; HTTP 404 bleibt Fehler |
| `data.list_records(...)` / `database.list(...)` | Liste aller gefundenen Datensätze |
| `data.iter_records(...)` / `database.iter_records(...)` | Lazy Iterator; lädt jeweils eine Seite mit 200 Datensätzen |
| `data.resolve_database(name)` | Datenbank-Dictionary mit gültiger `id` |
| `create_record` / `update_record`, `create` / `update` | Vollständige Antwort inklusive `data`, bei HTTP 204 `None` |
| `sync.submit(...)` / `sync.report_error(...)` | Vollständige Job-Antwort mit `data.id` und `data.status` |

Die unterschiedlichen Rückgabewerte für Lesen und Schreiben bleiben aus
Kompatibilitätsgründen erhalten. Anwendungen sollten vor `result["data"]` eine
mögliche 204-Antwort behandeln. JSON-Objekte ohne erwartete Lesedaten werden nicht
als leere Liste verschluckt. HTTP-Fehler werden vor dem JSON-Parsen behandelt.

Pagination folgt dem dokumentierten Protokoll: Seiten ab 1, Limit 200, Ende bei
einer kürzeren Seite. Sie erzeugt keinen transaktionalen Snapshot; parallele
Änderungen im Serverbestand können die Ergebnisse beeinflussen.

## Konfiguration, Authentifizierung und Lebensdauer

Konfiguration ist unveränderlich. URL, nicht leere Zugangswerte, endliche positive
Timeouts sowie nicht negative Backoff-Werte und ganzzahlige Retry-Zahlen werden
geprüft. Credentials in URLs, Query-Strings und Fragmente sind nicht zugelassen.
`from_env()` liest Zugangsdaten; Timeout und Retry-Werte lassen sich über den
jeweiligen Konfigurationskonstruktor festlegen.

OAuth-Tokens werden zwischengespeichert. Wenn `expires_in` geliefert wird, wird vor
Ablauf mit einem Vorlauf von 10 Prozent, maximal 30 Sekunden, neu angefordert.
Ohne Ablaufangabe gilt das Token bis zu `clear_token()` oder einer 401-Antwort.
Ein Lock schützt Tokenanforderung und Cache. Gleichzeitiges Schließen während
laufender Requests und paralleles Verändern von Sync-Buildern sind nicht unterstützt.

`Edelog` teilt einen HTTP-Client zwischen OAuth und Data API. Sync verwendet einen
separaten Zugang. `Edelog(..., client=raw, sync_client=sync_raw)` und die einzelnen
Clients erlauben HTTPX-Injektion für Tests oder eigene Transporte. Injizierte Clients
müssen Basis-URL, Timeout und Transport selbst passend konfigurieren; ihre Lebensdauer
verwaltet der Aufrufer. Nach `close()` ist der Library-Client nicht wiederverwendbar.
Der rohe HTTP-Zugang ist für vertrauenswürdige Anwendungspfade gedacht.

## Fehlervertrag

| Fehler | Bedeutung |
| --- | --- |
| `EdelogError` | Gemeinsame Basis der Library-Laufzeitfehler |
| `AuthenticationError` | OAuth abgelehnt oder Token-/Ablaufangaben ungültig |
| `ApiError` | Nicht erfolgreicher HTTP-Status; enthält `status_code` und `message` |
| `TransportError` | Netzwerkfehler nach der zulässigen Anzahl Versuche |
| `ResponseError` | Ungültiges JSON, unerwartete Antwortstruktur oder `success: false` trotz HTTP-Erfolg |
| `DatabaseNotFoundError` | Technischer Datenbankname auf keiner Seite gefunden |
| `ValueError` / `TypeError` | Ungültige lokale Eingaben bzw. nicht serialisierbare Werte |
| `RuntimeError` | Verwendung eines bereits geschlossenen Clients |

OAuth-Fehler enthalten keinen Response-Body. Netzwerkfehlertexte enthalten keine
URLs oder Zugangsdaten. `ApiError.message` enthält weiterhin den API-Response-Text
für die Diagnose und kann fachliche Daten enthalten.

Die Retry-Regeln stehen in der [README](../README.md#fehler-und-wiederholungen).
Die Library garantiert keine Exactly-once-Verarbeitung. Auch ein Lookup vor Create
ist ohne serverseitige Eindeutigkeitsgarantie bei konkurrierenden Schreibern kein
atomarer Upsert. Bei unklarem Schreibausgang den Zustand bzw. die Job-Historie prüfen.

## Sync-Validierung

Builder kopieren Eingaben und exportierte Payloads tief. Direkte Änderungen an
`tasks` oder `collections` werden vor jedem Versand erneut geprüft. Validiert werden
Version-1-Struktur, Task-Aktionen, Filter, Select-Ausdrücke, nicht leere Feldnamen,
endliche Zahlen und die dokumentierten primitiven Werte bzw. String-Arrays.

Es gibt keine automatische Umwandlung beliebiger Python-Objekte, Datumsobjekte oder
JSON-Spaltenschemata. Die Data API kann organisationsspezifische JSON-Werte schreiben;
die Sync API erlaubt nur die in ihrer Anleitung beschriebenen Formen. Ob Feldnamen,
Berechtigungen, Beziehungen und erforderliche Felder zur Zielorganisation passen,
muss serverseitig bzw. durch die Anwendung geprüft werden.

Für Upserts muss die Anwendung externe Schlüssel und Pflichtfelder in `values`
aufnehmen. Die Library kopiert `where` bewusst nicht automatisch: komplexe Filter
und Select-Ausdrücke sind keine eindeutige Vorlage für einen neuen Datensatz.

## Änderungen gegenüber dem bisherigen Prototyp

- Schreibzugriffe und Sync-Jobs werden bei 5xx/Netzwerkfehlern nicht mehr automatisch wiederholt.
- Netzwerk- und Antwortfehler besitzen eigene `EdelogError`-Unterklassen.
- HTTP 204 ist für Datensatz-Schreibantworten zulässig und liefert `None`.
- Datenbankauflösung liest alle Seiten; Record-Iterator ergänzt die Listen-API.
- Clients unterstützen `with` und `close()`; Konfigurationsdarstellungen verbergen Secrets.
- Sync-Eingaben werden kopiert und vor Versand validiert; riskante mehrfache
  Reconciliation-Collections derselben Datenbank werden abgelehnt.
- `if_not_found="throw-error"` wird von Sync-Update und -Delete unterstützt.

Diese Verhaltensänderungen müssen bestehende Nutzer beim Upgrade berücksichtigen.
Es wurde keine Version veröffentlicht; vor einem Release Versionsnummer und
Änderungshinweise entsprechend dem bisherigen Veröffentlichungsstand festlegen.

## Automatische Prüfungen und Release

Die CI prüft Python 3.10 bis 3.14, Unit- und HTTP-Vertragstests, Linting, Formatierung,
Typen sowie Wheel- und Source-Build. Ein separater Job installiert das Wheel und
führt Tests außerhalb des Quellbaums aus, damit fehlende Paketdateien auffallen.
`py.typed` macht die mitgelieferten Annotationen für Typprüfer nutzbar.

Vor einer Veröffentlichung:

1. Alle CI-Jobs erfolgreich abschließen.
2. Folgende Integrationstests in einer dedizierten EDELOG-Testorganisation ausführen.
3. Versionsnummer und Änderungshinweise prüfen, Wheel und Source-Archiv bauen.
4. Paketinstallation und dokumentierte Beispiele mit diesen Artefakten prüfen.
5. Erst nach fachlicher Prüfung veröffentlichen. Keine automatischen produktiven
   Schreibtests oder Paketveröffentlichungen sind eingerichtet.

## Manuelle Integrationstests

Voraussetzungen: separat installierte Test-App mit minimalen Rechten, eigener
Sync-Service und ausschließlich dafür vorgesehene Testdatenbanken. Die Beispiele
`examples/test_auth.py` und `examples/test_connection.py` melden sich an bzw. lesen
Datenbanken; sie werden von pytest nicht automatisch ausgeführt.

1. OAuth-Anmeldung und lesenden Zugriff mit technischen Namen und direkten UUIDs prüfen.
2. Einen eindeutig markierten Testdatensatz erstellen, lesen, teilweise aktualisieren
   und die übrigen Felder kontrollieren. Testdaten anschließend gezielt aufräumen.
3. Mehr als 200 Datensätze, Archivansicht, Filter und Feldprojektion prüfen.
4. Einen Sync-Upsert einreichen und anhand der Job-ID bis zum bestätigten Abschluss
   in EDELOG verfolgen. Danach denselben Upsert erneut ausführen: kein Duplikat erwarten.
5. Select-Beziehungen und `if_not_found="throw-error"` mit Testdaten kontrollieren.
6. Einen Lösch-Snapshot ausschließlich in einer vollständig entbehrlichen Testdatenbank
   prüfen; zuvor Payload und vollständige Datensatzmenge kontrollieren.
7. Abgelehnte Berechtigungen, ungültige Spaltenwerte und fehlgeschlagene Jobs prüfen.

Mock-Tests belegen Client-Verhalten, nicht den tatsächlichen API-Vertrag einer
konkreten Serverversion. Ohne diese Integrationstests ist keine Produktionsfreigabe
nachgewiesen.


## Live-Test vom 6. September 2026

Ein manuell begleiteter Data-Sync-Test wurde mit einem eigens markierten Datensatz
in der freigegebenen Testdatenbank durchgeführt. Zugangsdaten sind nicht Bestandteil
der Dokumentation.

| Schritt | Nachweis und Ergebnis |
| --- | --- |
| Verbindung und Einreichung | Sync-Service nahm die Aufträge an und lieferte Job-ID und `enqueued`. |
| Technischer Datenbankname | `TEST` wurde als nicht zugänglich abgelehnt; der bestätigte technische Name lautet `test`. |
| Erstellen per Upsert | Job-Historie zeigte `Completed`; Protokoll bestätigte Erstellung und Schreiben des neuen Datensatzes. Fünf nicht passende Datensätze wurden übersprungen. |
| Teilaktualisierung | Auftrag setzte `anzahl` auf den Textwert `"2"`; Protokoll bestätigte die Aktualisierung derselben Record-ID und übersprang fünf andere Datensätze. Kein separater Lesevergleich durchgeführt. |
| Gezieltes Löschen | Protokoll bestätigte das Entfernen derselben Record-ID. Fünf andere Datensätze wurden übersprungen. |

Die Basis-URL muss auf das Backend zeigen: In dieser Installation nennt die
UI-Konfiguration `https://core.industrial.edelog.com/api/v4`; für die Library ist
`https://core.industrial.edelog.com` ohne API-Suffix einzutragen. Die UI-Adresse
lieferte auch unter API-Pfaden HTML und ist dafür ungeeignet.

Noch nicht live nachgewiesen sind insbesondere OAuth/Data-API-Lesezugriffe,
Pagination, wiederholte Upserts ohne Duplikate, Beziehungen und Snapshot-Reconciliation.
Der erfolgreiche Create-/Update-Test ist keine vollständige Produktionsfreigabe.

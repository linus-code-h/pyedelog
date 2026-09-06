# EDELOG Data Sync: Anleitung für Einsteiger

Diese Anleitung zeigt, wie ein Python-Programm Daten in EDELOG schreibt. Sie nutzt
den Data-Sync-Weg. Dafür brauchst du keine Custom App und keinen OAuth-Zugang.

## Was passiert bei einem Sync?

Dein Programm schickt EDELOG einen Auftrag, zum Beispiel: "Suche den Datensatz mit
dieser Kennung. Wenn er fehlt, lege ihn an. Wenn er schon existiert, aktualisiere
ihn." EDELOG verarbeitet den Auftrag im Hintergrund.

Darum gibt es immer zwei Schritte:

1. Das Programm gibt `enqueued` und eine Job-ID aus.
2. Du öffnest **Settings → Data Sync → dein Service** und prüfst den Job.

Erst `Completed` ist ein erfolgreicher Import. Bei `Failed` lädst du das Protokoll
herunter; es enthält die Fehlermeldung.

## Was muss vorher eingerichtet sein?

Ein EDELOG-Administrator legt einmalig einen aktiven **Sync Service** an und gibt
die Zieldatenbank für diesen Service frei. Nur der Administrator kann dafür in
EDELOG eine Service-ID und einen Secret Key ausstellen oder einen Key ersetzen.
Bitte ihn ausdrücklich um diese Werte:

| Wert | Beispiel | Zweck |
| --- | --- | --- |
| Backend-URL | `https://core.industrial.edelog.com` | Adresse der EDELOG-API |
| Sync Service ID | UUID | Kennung des Sync Services |
| Sync Service Secret Key | geheime Zeichenfolge | Passwort für den Service |

Außerdem brauchst du die **technischen Namen** der Datenbank und Felder. Das ist
nicht immer der sichtbare Name in EDELOG: Die sichtbare Datenbank `TEST` hatte im
Live-Test den technischen Namen `test`.

Bei der Industrial-Installation ist `https://ui.industrial.edelog.com` nur die
Oberfläche. Die Backend-Adresse lautet `https://core.industrial.edelog.com`.
In die Konfiguration gehört die Backend-Adresse ohne `/api/v4`; die Library ergänzt
den API-Pfad selbst.

## Installation

Im Projektordner ausführen:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install .
```

Unter Windows PowerShell aktivierst du die Umgebung so:

```powershell
.venv\Scripts\Activate.ps1
```

## Zugangsdaten sicher speichern

Im Repository liegt die sichere Vorlage [.env.example](<../.env.example>). Sie
enthält nur Platzhalter und wird absichtlich mit dem Repository geteilt. Kopiere
sie lokal nach `.env.local`:

```bash
cp .env.example .env.local
```

Dann öffne **nur** `.env.local` und ersetze die beiden Platzhalter mit den Werten,
die du vom Administrator bekommen hast:

```dotenv
EDELOG_BASE_URL=https://core.industrial.edelog.com
EDELOG_SYNC_SERVICE_ID=hier-die-service-id
EDELOG_SYNC_ACCESS_KEY=hier-der-geheime-schluessel
```

`.env.local` ist in `.gitignore` eingetragen und wird nicht gepusht. Prüfe vor
jedem Commit mit `git status`, dass dort nur `.env.example`, niemals `.env.local`
auftaucht. Der Secret Key ist ein Passwort und gehört weder in Git, in E-Mails noch
in Screenshots. Wurde er geteilt, muss der Administrator ihn ersetzen.

Vor jedem Start in einem Bash- oder Linux-Terminal laden:

```bash
set -a
source .env.local
set +a
```

Die Library liest die Werte dann mit `DataSyncConfig.from_env()`.

## Erster Import: anlegen oder aktualisieren

Dieses Beispiel passt zur Testdatenbank `test` mit den Textfeldern `anzahl`,
`bauteil`, `funktion`, `pos_y9t` und `produkt`. Für eine andere Datenbank ersetzt
du Datenbank- und Feldnamen durch ihre technischen Namen.

```python
from edelog import DataSyncClient, DataSyncConfig, SyncRequest

kennung = "import-auftrag-4711"

auftrag = SyncRequest()
auftrag.database("test").upsert(
    where={"bauteil": kennung},
    values={
        "bauteil": kennung,
        "anzahl": "1",
        "funktion": "Montage",
        "pos_y9t": "10",
        "produkt": "Beispielprodukt",
    },
)

with DataSyncClient(DataSyncConfig.from_env()) as sync:
    antwort = sync.submit(auftrag)
    print("Job-ID:", antwort["data"]["id"])
    print("Status:", antwort["data"]["status"])
```

Speichere den Code etwa als `mein_import.py` und starte ihn mit:

```bash
python mein_import.py
```

Dasselbe Beispiel liegt auch als [sync_test_database.py](<../examples/sync_test_database.py>)
im Repository. Vor dem Ausführen dort die Kennung und die Feldwerte anpassen.

`upsert` bedeutet: existiert ein Datensatz mit dieser Kennung, wird er geändert.
Existiert keiner, wird ein neuer Datensatz angelegt. Deshalb ist die Kennung wichtig:
Sie muss pro Datensatz eindeutig und dauerhaft sein. Im Beispiel ist `bauteil` die
Kennung. Sie steht absichtlich in `where` und `values`; Werte aus `where` werden
nicht automatisch in einen neuen Datensatz übernommen.

## Auftrag prüfen

1. Notiere die ausgegebene Job-ID.
2. Öffne **Settings → Data Sync** in EDELOG.
3. Wähle deinen Sync Service und den neuesten Job.
4. Prüfe, ob der Job `Completed` ist.

Das Protokoll nennt zum Beispiel `Creating new record ...` oder
`Updating record ...`. Bei einem Fehler lade das Protokoll ebenfalls herunter.

## Nur ein Feld eines vorhandenen Datensatzes ändern

Wenn der Datensatz vorhanden sein muss, verwende `update`:

```python
auftrag = SyncRequest()
auftrag.database("test").update(
    where={"bauteil": "import-auftrag-4711"},
    values={"anzahl": "2"},
    if_not_found="throw-error",
)
```

Hier wird nur `anzahl` geändert. Die anderen Felder bleiben erhalten. Fehlt der
Datensatz, schlägt der Job bewusst fehl.

## Einen eigenen Testdatensatz löschen

Löschen ist endgültig. Lösche nur über eine eindeutige Kennung, die du selbst
angelegt hast:

```python
auftrag = SyncRequest()
auftrag.database("test").delete(
    where={"bauteil": "import-auftrag-4711"},
    if_not_found="throw-error",
)
```

Danach den Job erneut in EDELOG prüfen. Im Live-Test wurde so genau ein markierter
Datensatz gelöscht; fünf andere Datensätze blieben unverändert.

## Regeln, die Daten schützen

- Verwende eine stabile, eindeutige Kennung wie Artikel-, Auftrags- oder externe ID.
- Prüfe beim ersten Mal nur einen einzelnen Testdatensatz.
- Prüfe jeden Job in der Data-Sync-Historie.
- Bei einem Netzwerkfehler denselben Schreibauftrag nicht blind erneut senden.
  Prüfe zuerst die Job-Historie; der Server könnte ihn bereits verarbeitet haben.
- Verwende bei normalen Imports niemals `perform_on_not_matched_records="delete"`.
  Diese Option kann alle nicht im Auftrag genannten Datensätze löschen.
- Gib den Service Key nie aus und speichere ihn nicht im Quellcode.

## Häufige Fehler

| Meldung | Lösung |
| --- | --- |
| `reference-to-disallowed-database` | Technischen Datenbanknamen und Freigabe im Sync Service prüfen. |
| `record-not-found` | Die Kennung im Filter wurde nicht gefunden. Kennung prüfen oder Upsert nutzen. |
| HTTP 404 beim Einreichen | Service-ID, Secret Key, Aktivierung des Services oder Backend-URL prüfen. |
| HTML statt API-Antwort | Wahrscheinlich wurde die UI-Adresse statt der Backend-Adresse eingetragen. |
| `enqueued`, aber keine Daten sichtbar | Job-Historie und Protokoll abwarten und prüfen. |

Für Beziehungen zwischen Datenbanken, vollständige Datenabgleiche und alle
Schema-Details gibt es die ausführliche [Data-Sync-Referenz](<DATA_SYNC_API(1).md>).

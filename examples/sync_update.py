"""Ändere nur ein Feld eines vorhandenen Testdatensatzes.

Vor dem Start .env.local laden. Die Kennung muss genau zu einem eigenen Datensatz
passen, sonst meldet EDELOG absichtlich einen Fehler.
"""

from edelog import DataSyncClient, DataSyncConfig, SyncRequest


def main() -> None:
    kennung = "mein-import-4711"

    auftrag = SyncRequest()
    auftrag.database("test").update(
        where={"bauteil": kennung},
        values={"anzahl": "2"},
        if_not_found="throw-error",
    )

    with DataSyncClient(DataSyncConfig.from_env()) as sync:
        antwort = sync.submit(auftrag)

    print(f"Job-ID: {antwort['data']['id']}")
    print(f"Status: {antwort['data']['status']}")
    print("Den Abschluss in Settings → Data Sync prüfen.")


if __name__ == "__main__":
    main()

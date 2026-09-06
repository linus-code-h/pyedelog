"""Lösche genau einen eigenen Testdatensatz.

Vor dem Start .env.local laden. Löschen ist endgültig: Die Kennung muss eindeutig
sein und darf nur einen selbst angelegten Testdatensatz treffen.
"""

from edelog import DataSyncClient, DataSyncConfig, SyncRequest


def main() -> None:
    kennung = "mein-import-4711"

    auftrag = SyncRequest()
    auftrag.database("test").delete(
        where={"bauteil": kennung},
        if_not_found="throw-error",
    )

    with DataSyncClient(DataSyncConfig.from_env()) as sync:
        antwort = sync.submit(auftrag)

    print(f"Job-ID: {antwort['data']['id']}")
    print(f"Status: {antwort['data']['status']}")
    print("Den Abschluss in Settings → Data Sync prüfen.")


if __name__ == "__main__":
    main()

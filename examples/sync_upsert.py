"""Lege einen Testdatensatz an oder aktualisiere ihn.

Vor dem Start .env.local laden und die Kennung sowie Feldwerte unten anpassen.
Dieses Beispiel schreibt in die Testdatenbank ``test``.
"""

from edelog import DataSyncClient, DataSyncConfig, SyncRequest


def main() -> None:
    kennung = "mein-import-4711"

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

    print(f"Job-ID: {antwort['data']['id']}")
    print(f"Status: {antwort['data']['status']}")
    print("Den Abschluss in Settings → Data Sync prüfen.")


if __name__ == "__main__":
    main()

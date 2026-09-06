# pyedelog auf PyPI veröffentlichen

Dieser Ablauf veröffentlicht das Paket auf [PyPI](https://pypi.org/), damit Nutzer
es später einfach mit `pip install pyedelog` installieren können.

## Einmalig: PyPI mit GitHub verbinden

1. Auf [PyPI](https://pypi.org/account/register/) ein Benutzerkonto erstellen oder
   anmelden.
2. Unter **Publishing → Add a new pending publisher** auswählen.
3. Diese Werte eintragen:

   | Feld | Wert |
   | --- | --- |
   | PyPI project name | `pyedelog` |
   | Owner | `linus-code-h` |
   | Repository name | `pyedelog` |
   | Workflow name | `publish.yml` |
   | Environment name | `pypi` |

4. Speichern. Es ist kein PyPI-Passwort und kein API-Token im Repository nötig.

GitHub bestätigt die Veröffentlichung über diesen Trusted Publisher. Der Workflow
[publish.yml](<../.github/workflows/publish.yml>) startet nur bei einem Versions-Tag
wie `v0.1.0`.

## Vor jeder Version

1. `version` in `pyproject.toml` erhöhen.
2. Die neue Version und ihre Änderungen in `CHANGELOG.md` eintragen.
3. Lokal prüfen:

   ```bash
   python -m pytest -q
   python -m ruff check .
   python -m ruff format --check .
   python -m mypy
   python -m build
   ```

4. Änderungen committen und nach GitHub pushen.
5. Prüfen, dass CI auf `main` erfolgreich ist.

## Version veröffentlichen

Erst nachdem die PyPI-Verbindung eingerichtet und CI grün ist:

```bash
git tag -a v0.1.0 -m "Release 0.1.0"
git push origin v0.1.0
```

GitHub baut dann Wheel und Source-Archiv und veröffentlicht beide auf PyPI. Danach
testest du die veröffentlichte Version in einer neuen virtuellen Umgebung:

```bash
python -m venv /tmp/pyedelog-release-test
source /tmp/pyedelog-release-test/bin/activate
python -m pip install pyedelog==0.1.0
python -c "from edelog import DataSyncClient; print('Installation erfolgreich')"
```

Eine veröffentlichte PyPI-Version kann nicht mit denselben Versionsdaten ersetzt
werden. Bei einem Fehler die Versionsnummer erhöhen und eine neue Version erstellen.

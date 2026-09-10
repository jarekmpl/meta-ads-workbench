# Przygotowanie wydania

Publikujemy czysty eksport kodu, a nie bieżący katalog pracy specjalisty. `release-files.json` jest jawną listą plików przeznaczonych do dystrybucji. Nowy plik trzeba dopisać po sprawdzeniu jego zawartości. Nie dopisuj katalogu klienta, raportów ani danych z API.

```bash
python3 package_release.py --check
python3 package_release.py --destination dist/meta-ads-workbench-VERSJA
```

Powstają katalog repozytorium, ZIP oraz plik SHA-256 archiwum. Katalog zawiera `RELEASE-MANIFEST.json` z sumami plików, które instalator sprawdza przed kopiowaniem. To kontrola integralności, nie podpis kryptograficzny autora.

Skrypt odrzuca katalogi prywatne i typowe wzorce sekretów. Taki skan nie zastępuje przeglądu listy oraz treści plików. Do GitHuba wysyłamy wyłącznie wyeksportowany katalog. Nie uruchamiaj `git add .` w katalogu ze starymi raportami.

Przed publikacją wykonaj testy z README, instalację do nowego pustego katalogu i `workbench.py doctor`. Sprawdź, że konto nie jest skonfigurowane i żaden materiał klienta nie został skopiowany. Przetestuj import przykładowego kontekstu i blokadę polecenia innego klienta. Testy nie mogą wykonywać zmian na rzeczywistych kontach Meta.

Instalator nie aktualizuje istniejącego klienta. Poprawki wydajemy jako nową wersję, sprawdzamy na czystej instalacji, a migrację istniejącej przestrzeni wykonujemy jawnie po kopii zapasowej. Zaktualizuj numer w pyproject.toml, __init__.py, uv.lock, install.py i package_release.py.

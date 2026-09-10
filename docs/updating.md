# Aktualizacja z zachowaniem danych

Od wersji 0.6 narzędzie ma aktualizator `update.py`. Pobiera wydanie z GitHuba albo korzysta z rozpakowanej paczki, sprawdza sumy plików i aktualizuje tylko pliki dostarczone z narzędziem. Nie wykonuje migracji danych biznesowych ani operacji w Meta.

Zachowuje `context/`, `projects/`, `data/`, `reports/`, `output/`, `artifacts/`, `config/`, `secrets/`, profil specjalisty, `specialist.json`, `workspace.json`, prywatny `.gitignore` i ustawienia użytkownika. Nie dotyka nieznanych plików, także własnych plików w podkatalogach kodu. Gdy nowa paczka chce zająć ich ścieżkę, zgłasza konflikt.

Aktualizowane są pliki kodu, ogólne skille i wiedza, dokumentacja, schematy, przykłady, zasoby, instalator i wrappery. Zarządzany plik `.agents/rules/meta-ads.md` jest odświeżany z adaptera. Wcześniej dostarczony plik kodu, którego nie ma już w wydaniu, może zostać usunięty po sprawdzeniu zgodności i zapisaniu kopii. Nieznane pliki pozostają na miejscu. Jeśli zmieniono plik zarządzany, aktualizacja zatrzymuje się przed nadpisaniem.

## Z GitHuba

Potrzebne są Python 3.11+, `uv` i GitHub CLI `gh` z dostępem do repozytorium. Aktualizator korzysta z opublikowanych stabilnych wydań `jarekmpl/meta-ads-workbench`. Autoryzację `gh` wykonaj lokalnie; nie przekazuj tokena w rozmowie. Wersja i materiały są pobierane przez to narzędzie, bez zapisywania poświadczeń w kliencie.

W przestrzeni klienta:

```bash
python3 update.py --github
python3 update.py --github --version v0.6.0 --apply
```

Pierwsza komenda daje podgląd zmian. Druga wykonuje aktualizację do wskazanej wersji. Podawaj wersję zwróconą w podglądzie, aby nowe wydanie opublikowane w międzyczasie nie zmieniło zakresu. `--gh` i `--uv` pozwalają wskazać programy, jeśli nie znajdują się w PATH. Pobieranie ZIP oraz pliku SHA-256 i porównanie manifestu wykrywają uszkodzenie paczki. Zaufanie do kodu wynika z wybranego repozytorium i dostępu do niego; suma kontrolna nie jest niezależnym podpisem autora.

Przed aktualizacją zakończ inne operacje tego klienta. Od 0.6 komendy CLI i aktualizator korzystają ze wspólnej blokady. Nie obejmuje ona ręcznych zapisów edytora ani starszych procesów 0.5 i wcześniejszych. Aktualizator ponownie sprawdza pliki po przygotowaniu zależności i przed ich wymianą.

## Pierwsza aktualizacja starszej instalacji

Wersje do 0.5 nie zawierają aktualizatora ani pełnego zapisu sum zainstalowanych plików. Pobierz nową paczkę do osobnego katalogu, rozpakuj ją i uruchom jej skrypt:

```bash
python3 /SCIEZKA/DO/NOWEJ/PACZKI/update.py --workspace /SCIEZKA/DO/KLIENTA --github --version v0.6.0
python3 /SCIEZKA/DO/NOWEJ/PACZKI/update.py --workspace /SCIEZKA/DO/KLIENTA --github --version v0.6.0 --apply
```

Aktualizator pobierze również oryginalne wydanie zapisane w `workspace.json` i porówna z nim pliki. Ręczne poprawki zatrzymają proces. Nie zgaduj sum starej instalacji i nie twórz installed.json z bieżących plików, aby ukryć różnice.

## Z lokalnej paczki

```bash
python3 /SCIEZKA/DO/PACZKI/update.py --workspace /SCIEZKA/DO/KLIENTA --source /SCIEZKA/DO/PACZKI
python3 /SCIEZKA/DO/PACZKI/update.py --workspace /SCIEZKA/DO/KLIENTA --source /SCIEZKA/DO/PACZKI --apply
```

Paczką jest rozpakowany katalog z `RELEASE-MANIFEST.json`, a nie dowolny checkout. Przy starszej instalacji dodatkowo podaj `--baseline /SCIEZKA/DO/ORYGINALNEJ/STAREJ/PACZKI`. Dzięki temu aktualizacja plików działa także bez GitHuba. Instalacja zależności wymaga sieci lub kompletnego cache `uv`.

## Co dzieje się podczas aktualizacji

1. Skrypt sprawdza manifest, sumy, dozwolone ścieżki, wersję bazową i lokalne zmiany.
2. Kopiuje sprawdzoną paczkę do katalogu transakcji. Buduje osobne środowisko Python z przypiętych zależności; dotychczasowe pozostaje dostępne.
3. Zapisuje kopię zmienianych plików narzędzia oraz dziennik w `.workbench/updates/`. Następnie wymienia pliki.
4. Sprawdza środowisko i zapisuje aktywną wersję oraz ścieżkę Pythona w `.workbench/installed.json`. `workspace.json` zachowuje oryginalną metrykę instalacji.
5. Po błędzie przywraca poprzednie pliki i wskaźnik środowiska. Kopia i dziennik pozostają dostępne.

To kopia plików narzędzia, nie pełny backup klienta. Dane i profil nadal wymagają własnych kopii zapasowych. Aktualizator nie kopiuje sekretów do katalogu transakcji i nie sprząta starych środowisk automatycznie. Katalog `.workbench/` jest prywatnym stanem instalacji, nie materiałem do GitHuba. Nie edytuj go ręcznie.

Po aktualizacji korzystaj z:

```bash
python3 workbench.py doctor
python3 workbench.py meta capabilities
python3 workbench.py specialist list
```

`workbench.py` wybiera aktywne środowisko. Stare `.venv/bin/meta-ads` może mieć wcześniejsze zależności; nie używaj go w zaktualizowanej przestrzeni. W repozytorium deweloperskim nadal korzystamy z `.venv` zgodnie z README. Po zmianie wersji przeładuj instrukcje agenta lub rozpocznij nową rozmowę w tym samym projekcie klienta.

## Przerwany proces i konflikty

Jeśli proces przerwano podczas wymiany plików, komendy zatrzymują się z `WORKSPACE_MAINTENANCE`. Uruchom skrypt z kompletnej paczki poza klientem:

```bash
python3 /SCIEZKA/DO/PACZKI/update.py --workspace /SCIEZKA/DO/KLIENTA --rollback
```

Odtworzenie dotyczy przerwanej transakcji. Sprawdza sumy kopii i bieżących plików; nie nadpisze późniejszych ręcznych zmian. Nie jest poleceniem dowolnego obniżania wersji. Przy konflikcie zachowaj lokalną poprawkę i rozstrzygnij ją przed ponowną próbą. Nie usuwaj pending.json, aby ominąć blokadę.

Zmiany własnych metod przenieś do profilu specjalisty. Zmiany kodu, które mają zostać, opracuj jako część przyszłego wydania. Instalator `install.py` nadal służy do nowych przestrzeni; `--resume` ponawia wyłącznie instalację zależności, nie aktualizuje kodu klienta.

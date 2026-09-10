# Działające demo v0.1

## Co jest dostępne

Z flagą `--demo` CLI działa lokalnie na syntetycznych danych dwóch klientów. Nie odczytuje tokenów, nie łączy się z siecią i nie wykonuje zmian reklamowych. Zakres danych jest stały: **2026-07-11–2026-09-08** (60 dni). `--last-days` liczy dni wstecz od końca zestawu lub analizowanego snapshotu, a nie od dzisiejszej daty. Domyślna synchronizacja nadal obejmuje 14 dni; dla raportu miesięcznego jawnie pobierz 30 dni.

Użytkownik może zlecać te działania [przez rozmowę z agentem](conversational-use.md); poniższe komendy opisują interfejs techniczny.

| Klient | Konto | Cel | Kampanie |
| --- | --- | --- | --- |
| `demo-leads` | `act_DEMO_LEADS` | `leads-pl` | Dwie kampanie leadowe |
| `demo-shop` | `act_DEMO_SHOP` | `commerce-pl` | Dwie kampanie sprzedażowe |

Plik [profilu przykładowego](../examples/client-profile.json) z klientem `demo` ilustruje osobno kontrakt konfiguracji. Nie jest automatycznie importowany do bazy klientów. Klienci dostępni w działającym demo pochodzą z pakietu `fixtures/demo.json`.

## Instalacja i podstawowy przepływ

```bash
uv sync --locked --python 3.11
uv run --locked meta-ads --help
uv run --locked meta-ads --demo clients list
uv run --locked meta-ads --demo accounts list --client demo-leads

uv run --locked meta-ads --demo sync --client demo-leads --account act_DEMO_LEADS
uv run --locked meta-ads --demo sync --client demo-shop --account act_DEMO_SHOP

uv run --locked meta-ads --demo --format text analyze --client demo-leads --account act_DEMO_LEADS --goal leads-pl
uv run --locked meta-ads --demo --format text analyze --client demo-shop --account act_DEMO_SHOP --goal commerce-pl
```

Bez `--format text` stdout zawiera dokładnie jeden dokument JSON z polami `schema_version`, `request_id`, `ok`, `data`, `warnings`, `error`. Dotyczy to także błędów argumentów. Wyjątki: standardowe `--help` i `--version` zwracają tekst.

Nie ustawiamy domyślnego klienta ani ostatnio używanego konta. Błędne połączenie `--client demo-leads --account act_DEMO_SHOP` daje kod 3, zanim aplikacja otworzy bazę lub pobierze snapshot.

## Raporty i historia

Raport wszystkich kampanii za 30 dni oraz audyt konta:

```bash
uv run --locked meta-ads capabilities
uv run --locked meta-ads --demo sync --client demo-shop --account act_DEMO_SHOP --last-days 30
uv run --locked meta-ads --demo report campaigns --client demo-shop --account act_DEMO_SHOP --last-days 30
uv run --locked meta-ads --demo audit --client demo-shop --account act_DEMO_SHOP --last-days 30
```

Obie komendy przyjmują również `--since` i `--until` oraz `--snapshot`. Jeśli snapshot nie obejmuje całego żądanego okresu, dostajesz `INSUFFICIENT_DATA`; zakres nie jest automatycznie skracany. Raport obejmuje wszystkie kampanie snapshotu, bez filtrowania po statusie. Wyniki konwersji są agregowane osobno dla profili celów, a kampanie bez mapowania celu pozostają widoczne jako `unmapped`.

`audit` zwraca `status: PARTIAL`, ponieważ w danych demo nie ma m.in. kreacji, targetowania, budżetów i konfiguracji pomiaru. `coverage` odróżnia obszary sprawdzone od niedostępnych. Rekomendacje mają dowody i nie wykonują żadnych zmian. Komenda może poprawnie wykonać audyt częściowy (`ok: true`); nie oznacza to pełnego pokrycia danych.

Poniżej eksport dotychczasowej analizy tygodniowej:

```bash
uv run --locked meta-ads --demo --output reports/shop-review.json analyze --client demo-shop --account act_DEMO_SHOP --goal commerce-pl
```

`--output` zapisuje sam obiekt `data`, a stdout nadal zawiera odpowiedź z metadanymi. Istniejący plik nie jest nadpisywany. Wybierz nową nazwę przy kolejnym eksporcie. Parametry globalne muszą występować przed poleceniem.

Każda synchronizacja zapisuje osobny snapshot. Kolejna analiza korzysta z najnowszego snapshotu dla wskazanego klienta i konta; nie sumuje kolejnych wersji tych samych faktów. Każdy raport przechowuje identyfikator snapshotu, profil celu, wersję kodu, specyfikację metryk i daty.

Zastąp poniższe identyfikatory wartościami z odpowiedzi CLI:

```bash
uv run --locked meta-ads --demo sync status --client demo-shop --account act_DEMO_SHOP --run sync_ID
uv run --locked meta-ads --demo report show --client demo-shop --account act_DEMO_SHOP --run analysis_ID
uv run --locked meta-ads --demo analyze --client demo-shop --account act_DEMO_SHOP --goal commerce-pl --snapshot sync_ID
```

Odczyt raportu zwraca zapisany wynik. Ponowna analiza wskazanego snapshotu tworzy nowy raport z nowym identyfikatorem i czasem, ale te same dane dają te same obliczenia przy tej samej wersji kodu i profilu celu.

Baza znajduje się domyślnie w `data/demo.sqlite3`. `--data-dir` zmienia katalog. Baza, raporty i lokalne sekrety są wyłączone z Gita. SQLite oddziela zakresy i wymusza powiązanie raportu z kontem snapshotu; nie jest to granica bezpieczeństwa wobec osoby z dostępem do pliku bazy.

## Interpretacja wyników

`weekly-review` porównuje ostatnie siedem dni snapshotu z poprzednimi siedmioma. Wymaga 14 pełnych dni; krótszy snapshot zwraca `INSUFFICIENT_DATA` (kod 6). Nie próbuje uzupełniać luk innym snapshotem.

W obecnym zestawie, w okresie 2026-09-02–2026-09-08:

| Profil | Wydatki | Konwersje | Koszt wyniku | ROAS |
| --- | --- | --- | --- | --- |
| Leady | 1400 PLN | 63 | CPL 22,222222 PLN | Nie dotyczy |
| Sprzedaż | 1400 PLN | 35 | CPA 40 PLN | 4,5 |

Kwoty i wartości dziesiętne w JSON są tekstem, aby uniknąć utraty precyzji. CTR jest procentem, ROAS ilorazem. Brak pomiaru oznacza `null` z powodem `unavailable`; zero konwersji daje `zero_denominator` dla kosztu konwersji. Reach i frequency nie są sumowane. Dostępne są wyniki zbiorcze, wyniki kampanii i procentowe zmiany wskaźników.

Cele CPL/CPA/ROAS w zestawie są demonstracyjne. Ich ocena jest prostym porównaniem arytmetycznym, nie rekomendacją optymalizacji. Program nie ocenia jakości leadów, marży, rentowności ani przyczynowości zmian; pole `recommendations` jest puste.

## Walidacja i schematy

```bash
uv run --locked meta-ads validate --file examples/client-profile.json
uv run --locked meta-ads validate --file examples/campaign-brief-leads.json
uv run --locked meta-ads validate --file examples/campaign-brief-commerce.json
uv run --locked meta-ads validate --file examples/change-proposal.json
uv run --locked meta-ads schema export --kind client_profile
```

Walidator odrzuca nieznane pola, powtórzone klucze JSON, błędne referencje w profilu oraz nieprawidłowe typy liczb. Kwoty podawaj jako tekst, np. `"100.00"`. Walidacja briefu lub propozycji dotyczy tylko struktury lokalnego dokumentu i zwraca `execution_ready: false`. Nie sprawdza konta ani zasobów w Mecie.

Wersja 0.1 akceptuje tylko politykę `analyst` bez operacji zapisu. Schemat propozycji obejmuje wyłącznie zmianę budżetu jako przykład kontraktu; nie ma wykonawcy. Skille raportowania i audytu są dostępne w repozytorium. Dodano [konfigurację i test połączenia Meta](meta-setup.md), w tym `auth check`. `campaign plan`, `changes apply`, import profili produkcyjnych nie są jeszcze dostępne. Podstawowa synchronizacja Meta, raporty kampanii i częściowy audyt działają bez flagi `--demo`.

## Testy i pakowanie

```bash
uv run --locked pytest -q
uv run --locked ruff check src tests
uv build
```

Testy nie wymagają tokenów ani połączenia z Metą. Obejmują obliczenia, brak danych, kompletność okresu, izolację klientów, historię snapshotów, zgodność schematów, bezpieczne błędy i uruchomienie CLI spoza repozytorium.

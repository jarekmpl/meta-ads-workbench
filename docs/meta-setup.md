# Pierwsze połączenie z Meta

Aktualny etap: konfiguracja własnego konta i test dostępu w trybie odczytu. Dostępne są `auth init`, `auth status`, `auth store-token` i `auth check`. Działają też synchronizacja, raporty kampanii i częściowy audyt na rzeczywistych danych.

## Aplikacja Meta

W [panelu aplikacji](https://developers.facebook.com/apps/) wybierz `Create App`. W kreatorze sprawdzonym 2026-09-09:

1. Podaj nazwę aplikacji i adres kontaktowy.
2. Wybierz **Create & manage ads with Marketing API**. Wariant **Create & manage app ads with Meta Ads Manager** dotyczy promowania aplikacji i według opisu w kreatorze nie udostępnia Marketing API.
3. Wybierz własne portfolio i sprawdź wyświetlane wymagania.
4. Przejrzyj podsumowanie. Końcowe `Create app` oznacza akceptację Meta Platform Terms i Developer Policies; właściciel musi świadomie zatwierdzić ten krok.

Po utworzeniu aplikacji zapisz jej ID. ID portfolio i ID konta reklamowego to inne identyfikatory. Wersję Graph API wybierz na podstawie aktualnego panelu/dokumentacji — program wymaga jawnej wartości.

Materiały: [oficjalne SDK Mety](https://github.com/facebook/facebook-python-business-sdk) oraz [kolekcja Marketing API Mety](https://www.postman.com/meta/facebook-marketing-api/collection/0zr4mes/facebook-marketing-api-mapi).

## Przydział dostępu

Dla stałej integracji własnego portfolio sprawdzamy możliwość użycia użytkownika systemowego z przydziałem do aplikacji i wskazanego konta. Pierwszy test może użyć tokena użytkownika, jeśli panel udostępnia tę ścieżkę. Czas ważności i rodzaj tokena ustalamy na podstawie ustawień Mety.

Na początek potrzebny jest odczyt danych reklamowych (`ads_read`) i przydział konta. Samo utworzenie aplikacji nie daje automatycznie dostępu do wszystkich kont. Nadanie dostępu i wygenerowanie poświadczeń to osobne działania. Dla kont klientów trzeba dodatkowo sprawdzić wymagania autoryzacji, App Review i poziomy dostępu.

## Konfiguracja lokalna

Przykładowy alias to `moja-firma`. W przestrzeni operatora użyj kodu z `workspace.json`. Plik `config/local/meta-KOD.json` powstaje dopiero po `auth init` lub przejściu kreatora i nie zawiera tokena. Po odczytaniu identyfikatorów z panelu uzupełniamy `app_id`, `account_id`, `api_version` i opcjonalnie `business_id`. Konto ma format `act_` z numerem konta.

```bash
.venv/bin/meta-ads auth status --client moja-firma
```

Dla kolejnego klienta `auth init --client NAZWA` tworzy nowy plik. Opcjonalne argumenty to `--app-id`, `--account`, `--business-id` i `--api-version`. Istniejące konfiguracje nie są nadpisywane.

## Wprowadzenie tokena

Po wygenerowaniu tokena właściciel wpisuje go w lokalnym interaktywnym terminalu:

```bash
.venv/bin/meta-ads auth store-token --client moja-firma
```

Jeśli aplikacja wymaga App Secret Proof, dodaj `--with-app-secret`. Oba pola wejściowe są ukryte. Komenda nie przyjmuje tokena jako argumentu ani przez zwykły potok. Zapisuje poświadczenia w `secrets/meta-moja-firma.json` z uprawnieniami `600`, poza Gitem. To lokalny plik z ograniczonym dostępem, nie zaszyfrowany sejf.

Nie czytaj zawartości pliku sekretów do rozmowy ani logów. `auth status` sprawdza tylko obecność pliku i kompletność konfiguracji. Istniejące poświadczenia nie są nadpisywane; rotacja będzie osobną, jawną procedurą.

## Test dostępu

```bash
.venv/bin/meta-ads auth check --client moja-firma
```

Test wykonuje wyłącznie GET na `https://graph.facebook.com`: odczyt wskazanego konta i minimalne zapytanie Insights za wczoraj. Sprawdza zgodność ID konta. Pusta lista Insights może być poprawna przy braku emisji.

Token trafia do nagłówka Authorization. Przekierowania są blokowane, błędy nie zawierają surowych odpowiedzi ani sekretów. Jeśli zapisano App Secret, program wylicza App Secret Proof.

`VERIFIED` potwierdza dwa odczyty. Nie potwierdza wszystkich uprawnień, czasu ważności tokena, aplikacji wystawiającej token ani poprawności pomiaru konwersji. Wynik jawnie wskazuje te ograniczenia. Po teście można pobierać rzeczywiste dane poniższymi poleceniami.

Testy automatyczne używają fikcyjnych tokenów i odpowiedzi. Weryfikują zakres konta, brak sekretów w URL i błędach, blokadę przekierowań oraz uprawnienia plików. Nie zastępują testu na rzeczywistym koncie.

## Synchronizacja i raportowanie

Z katalogu projektu agent wykonuje:

```bash
.venv/bin/meta-ads clients list
.venv/bin/meta-ads accounts list --client moja-firma
.venv/bin/meta-ads sync --client moja-firma --account act_NUMER_KONTA --last-days 30
.venv/bin/meta-ads report campaigns --client moja-firma --account act_NUMER_KONTA --last-days 30 --snapshot SYNC_ID
.venv/bin/meta-ads audit --client moja-firma --account act_NUMER_KONTA --last-days 30 --snapshot SYNC_ID
```

`SYNC_ID` zastępuje identyfikator zakończonej synchronizacji. `act_NUMER_KONTA` zastąp rzeczywistym identyfikatorem z konfiguracji; to oznaczenie nie jest poprawnym ID do wysłania. Katalog klientów i kont obejmuje tylko połączenia zapisane lokalnie; obecnie jedno konto na konfigurację klienta.

Synchronizacja pobiera wszystkie strony dostępnej listy kampanii (w tym wstrzymanych i archiwalnych), dzienne Insights i podsumowanie konta. Endpoint listy kampanii odrzuca żądanie usuniętych obiektów (potwierdzono w pilocie, błąd Meta 1815001). Kampanie usunięte trafiają do snapshotu, jeśli zwróci je Insights dla wskazanego okresu; bez takich wyników nie ma gwarancji pełnej historycznej listy. Suma wydatków, wyświetleń i kliknięć musi zgadzać się dokładnie z podsumowaniem API. Rozbieżność, także z powodu zaokrągleń, blokuje zapis zamiast ukrywać różnicę. Brakujące wiersze dnia uzupełniane są zerami emisji dopiero po tej kontroli; konwersje bez mapowania pozostają `null`.

Dane i raporty zapisują się w `data/meta.sqlite3`, oddzielnie od `data/demo.sqlite3`. Raporty i audyty korzystają z lokalnego snapshotu bez kolejnego połączenia API. `report show` odtwarza wcześniejszy raport. Daty względne w Meta kończą się wczoraj w strefie konta; do historycznej reprodukcji podaj dokładne daty.

Zakres: wydatki, wyświetlenia, kliknięcia linku, CPM, CTR linku, CPC linku, cel reklamowy i osobne typy zdarzeń. Ustawienia atrybucji są jawne: `7d_click`, `1d_view`, `action_report_time=impression`. Reach i częstotliwość nie są sumowane z dni. Aliasy zdarzeń mogą się nakładać; mapowanie leadów/zakupów i obliczenia CPL/CPA/ROAS na Meta pozostają do wdrożenia.

Zaimplementowano wyłącznie GET do stałego hosta Graph API. Paginacja używa kursorów, nie adresów `next` zawierających tokeny. Limit to 366 pełnych dni oraz 1000 stron; błędy limitów i sieci kończą synchronizację bez kompletnego snapshotu. Raporty asynchroniczne i automatyczne wznawianie nie są dostępne.

Parametry odczytu zweryfikowano z [oficjalnym SDK Meta: AdAccount](https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/adobjects/adaccount.py), [Campaign](https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/adobjects/campaign.py) i [AdsInsights](https://github.com/facebook/facebook-python-business-sdk/blob/main/facebook_business/adobjects/adsinsights.py).
